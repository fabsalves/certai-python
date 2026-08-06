"""Catch-up when a student joins a teaching class mid-track.

Materializes terminal progress (+ lesson assessment) for lessons the class
already closed, and DISPARADA on the class's next open lesson — so module/track
gating is not blocked forever by missing rows.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cohort import Cohort, CohortModuleProfessor, CohortProgress
from app.models.student_progress import StudentLessonProgress, StudentLessonProgressStatus
from app.services.cohort.module_class_service import ModuleClassService
from app.services.student_progress_service import StudentProgressService
from app.services.track_structure import ordered_active_lessons


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MidJoinService:
    @staticmethod
    async def next_open_lesson_id(
        db: AsyncSession, cohort: Cohort, module_class: CohortModuleProfessor
    ) -> uuid.UUID | None:
        """First active lesson of this class's module not yet closed by the class."""
        closed = set(
            (
                await db.scalars(
                    select(CohortProgress.lesson_id).where(
                        CohortProgress.cohort_id == cohort.id,
                        CohortProgress.module_professor_id == module_class.id,
                    )
                )
            ).all()
        )
        for lesson in await ordered_active_lessons(db, cohort.track_id):
            if lesson.module_id != module_class.module_id:
                continue
            if lesson.id not in closed:
                return lesson.id
        return None

    @staticmethod
    async def catch_up_student_to_class(
        db: AsyncSession,
        cohort: Cohort,
        module_class: CohortModuleProfessor,
        student_id: uuid.UUID,
    ) -> dict:
        """Align one student to a class that may already have progressed.

        Returns counts for logging/tests: {closed, assessed_enqueued, disparada}.
        """
        closed_lesson_ids = set(
            (
                await db.scalars(
                    select(CohortProgress.lesson_id).where(
                        CohortProgress.cohort_id == cohort.id,
                        CohortProgress.module_professor_id == module_class.id,
                    )
                )
            ).all()
        )
        module_lessons = [
            lesson
            for lesson in await ordered_active_lessons(db, cohort.track_id)
            if lesson.module_id == module_class.module_id
        ]

        closed_count = 0
        enqueued = 0
        for lesson in module_lessons:
            if lesson.id not in closed_lesson_ids:
                continue
            created = await MidJoinService._ensure_terminal_missing(
                db, cohort.id, student_id, lesson.id
            )
            if created:
                closed_count += 1
                enqueued += 1

        disparada = False
        next_id = await MidJoinService.next_open_lesson_id(db, cohort, module_class)
        if next_id is not None:
            before = await StudentProgressService._get_progress(
                db, cohort.id, student_id, next_id
            )
            await StudentProgressService._ensure_disparada(
                db, cohort.id, student_id, next_id
            )
            disparada = before is None

        return {
            "closed": closed_count,
            "assessed_enqueued": enqueued,
            "disparada": disparada,
        }

    @staticmethod
    async def _ensure_terminal_missing(
        db: AsyncSession,
        cohort_id: uuid.UUID,
        student_id: uuid.UUID,
        lesson_id: uuid.UUID,
    ) -> bool:
        """Create ENCERRADA_POR_AVANCO + enqueue assessment when no progress exists.

        Returns True only when a new terminal row was created (idempotent otherwise).
        """
        row = await StudentProgressService._get_progress(
            db, cohort_id, student_id, lesson_id
        )
        if row is not None:
            return False

        now = _utcnow()
        db.add(
            StudentLessonProgress(
                cohort_id=cohort_id,
                student_id=student_id,
                lesson_id=lesson_id,
                status=StudentLessonProgressStatus.ENCERRADA_POR_AVANCO,
                encerrada_por_avanco_at=now,
            )
        )
        await db.flush()

        from app.core.db_events import enqueue_after_commit
        from app.workers.tasks import assess_student_lesson

        enqueue_after_commit(
            db,
            assess_student_lesson,
            str(cohort_id),
            str(student_id),
            str(lesson_id),
        )
        return True

    @staticmethod
    async def catch_up_on_enroll(
        db: AsyncSession, cohort: Cohort, student_ids: list[uuid.UUID]
    ) -> None:
        """Single-professor modules: new enrollments join the class automatically."""
        if not student_ids:
            return

        classes = await db.scalars(
            select(CohortModuleProfessor).where(
                CohortModuleProfessor.cohort_id == cohort.id
            )
        )
        by_module: dict[uuid.UUID, list[CohortModuleProfessor]] = {}
        for module_class in classes:
            by_module.setdefault(module_class.module_id, []).append(module_class)

        for module_classes in by_module.values():
            if len(module_classes) != 1:
                continue
            module_class = module_classes[0]
            for student_id in student_ids:
                await MidJoinService.catch_up_student_to_class(
                    db, cohort, module_class, student_id
                )

    @staticmethod
    async def catch_up_roster_additions(
        db: AsyncSession,
        cohort: Cohort,
        additions: list[tuple[CohortModuleProfessor, uuid.UUID]],
    ) -> None:
        """Run catch-up for (class, student) pairs newly added to a roster."""
        for module_class, student_id in additions:
            await MidJoinService.catch_up_student_to_class(
                db, cohort, module_class, student_id
            )

    @staticmethod
    async def claim_student(
        db: AsyncSession,
        cohort: Cohort,
        module_id: uuid.UUID,
        professor_id: uuid.UUID,
        student_id: uuid.UUID,
    ) -> CohortModuleProfessor:
        """Assign an unassigned enrolled student to this professor's class."""
        from app.models.cohort import CohortModuleStudent, Enrollment
        from app.models.user import Role, User

        student = await db.get(User, student_id)
        if student is None or student.role != Role.STUDENT:
            raise ValueError("Aluno inválido")

        enrolled = await db.scalar(
            select(Enrollment.id).where(
                Enrollment.cohort_id == cohort.id,
                Enrollment.student_id == student_id,
            )
        )
        if enrolled is None:
            raise ValueError("Aluno não está matriculado nesta turma")

        module_class = await ModuleClassService.class_of_professor(
            db, cohort.id, module_id, professor_id
        )
        if module_class is None:
            raise PermissionError("Você não leciona este módulo")

        classes = await ModuleClassService.classes_of_module(db, cohort.id, module_id)
        if len(classes) <= 1:
            raise ValueError(
                "Este módulo tem um único professor — a turma inteira já é a classe"
            )

        unassigned = await ModuleClassService.unassigned_student_ids(
            db, cohort.id, module_id
        )
        if student_id not in unassigned:
            # Already in some class of this module?
            existing = await ModuleClassService.resolve_for_student(
                db, cohort.id, module_id, student_id
            )
            if existing is not None and existing.id == module_class.id:
                await MidJoinService.catch_up_student_to_class(
                    db, cohort, module_class, student_id
                )
                return module_class
            if existing is not None:
                raise ValueError("Aluno já está em outra turma deste módulo")
            raise ValueError("Aluno não está disponível para vínculo neste módulo")

        db.add(
            CohortModuleStudent(
                module_professor_id=module_class.id, student_id=student_id
            )
        )
        await db.flush()
        await MidJoinService.catch_up_student_to_class(
            db, cohort, module_class, student_id
        )
        return module_class
