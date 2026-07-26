"""Centralized mutations for StudentLessonProgress — the only place that changes status."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.cohort import Cohort, Enrollment
from app.models.student_progress import StudentLessonProgress, StudentLessonProgressStatus
from app.models.track import Module, Track


class LessonNotInteractiveError(Exception):
    """Raised when a lesson cannot accept new student interactions."""

    def __init__(self, reason: str = "lesson_closed") -> None:
        self.reason = reason
        super().__init__(reason)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StudentProgressService:
    @staticmethod
    def is_lesson_interactive(status: StudentLessonProgressStatus) -> bool:
        return status in (
            StudentLessonProgressStatus.DISPARADA,
            StudentLessonProgressStatus.ATIVA,
        )

    @staticmethod
    async def resolve_routable_lesson(
        db: AsyncSession,
        student_id: uuid.UUID,
        cohort_id: uuid.UUID,
    ) -> uuid.UUID | None:
        """ATIVA first; otherwise the most recent DISPARADA."""
        ativa = await db.scalar(
            select(StudentLessonProgress.lesson_id).where(
                StudentLessonProgress.cohort_id == cohort_id,
                StudentLessonProgress.student_id == student_id,
                StudentLessonProgress.status == StudentLessonProgressStatus.ATIVA,
            )
        )
        if ativa is not None:
            return ativa

        return await db.scalar(
            select(StudentLessonProgress.lesson_id)
            .where(
                StudentLessonProgress.cohort_id == cohort_id,
                StudentLessonProgress.student_id == student_id,
                StudentLessonProgress.status == StudentLessonProgressStatus.DISPARADA,
            )
            .order_by(StudentLessonProgress.disparada_at.desc())
            .limit(1)
        )

    @staticmethod
    async def resolve_routable_route(
        db: AsyncSession,
        student_id: uuid.UUID,
    ) -> tuple[uuid.UUID, uuid.UUID] | None:
        """Returns (cohort_id, lesson_id) for inbound routing without cohort context."""
        row = await db.scalar(
            select(StudentLessonProgress)
            .where(
                StudentLessonProgress.student_id == student_id,
                StudentLessonProgress.status == StudentLessonProgressStatus.ATIVA,
            )
            .limit(1)
        )
        if row is not None:
            return row.cohort_id, row.lesson_id

        row = await db.scalar(
            select(StudentLessonProgress)
            .where(
                StudentLessonProgress.student_id == student_id,
                StudentLessonProgress.status == StudentLessonProgressStatus.DISPARADA,
            )
            .order_by(StudentLessonProgress.disparada_at.desc())
            .limit(1)
        )
        if row is not None:
            return row.cohort_id, row.lesson_id
        return None

    @staticmethod
    async def is_lesson_interactive_for(
        db: AsyncSession,
        cohort_id: uuid.UUID,
        student_id: uuid.UUID,
        lesson_id: uuid.UUID,
    ) -> bool:
        row = await StudentProgressService._get_progress(
            db, cohort_id, student_id, lesson_id
        )
        return row is not None and StudentProgressService.is_lesson_interactive(row.status)

    @staticmethod
    async def validate_voice_handoff(
        db: AsyncSession,
        *,
        cohort_id: uuid.UUID,
        student_id: uuid.UUID,
        lesson_id: uuid.UUID,
    ) -> None:
        """Ensures handoff lesson matches the student's routable interactive lesson."""
        routable = await StudentProgressService.resolve_routable_lesson(
            db, student_id, cohort_id
        )
        if routable is None:
            raise LessonNotInteractiveError("no_active_lesson")
        if routable != lesson_id:
            raise LessonNotInteractiveError("lesson_closed")

        row = await StudentProgressService._get_progress(
            db, cohort_id, student_id, lesson_id
        )
        if row is None or not StudentProgressService.is_lesson_interactive(row.status):
            raise LessonNotInteractiveError("lesson_closed")

    @staticmethod
    async def activate_on_first_interaction(
        db: AsyncSession,
        cohort_id: uuid.UUID,
        student_id: uuid.UUID,
        lesson_id: uuid.UUID,
    ) -> StudentLessonProgress | None:
        """DISPARADA → ATIVA on first student turn; at most one ATIVA per student in cohort."""
        row = await StudentProgressService._get_progress(
            db, cohort_id, student_id, lesson_id
        )
        if row is None:
            return None

        if row.status == StudentLessonProgressStatus.ATIVA:
            return row

        if row.status != StudentLessonProgressStatus.DISPARADA:
            return row

        await StudentProgressService._close_other_active_lessons(
            db, cohort_id, student_id, except_lesson_id=lesson_id
        )

        now = _utcnow()
        row.status = StudentLessonProgressStatus.ATIVA
        row.activated_at = now
        await db.flush()
        return row

    @staticmethod
    async def conclude(
        db: AsyncSession,
        cohort_id: uuid.UUID,
        student_id: uuid.UUID,
        lesson_id: uuid.UUID,
    ) -> StudentLessonProgress:
        """ATIVA → CONCLUIDA (called by conclude_lesson tool in Phase 3)."""
        row = await StudentProgressService._get_progress(
            db, cohort_id, student_id, lesson_id
        )
        if row is None or row.status != StudentLessonProgressStatus.ATIVA:
            raise ValueError("Progresso não está ATIVA para conclusão")

        now = _utcnow()
        row.status = StudentLessonProgressStatus.CONCLUIDA
        row.concluded_at = now
        await db.flush()
        return row

    @staticmethod
    async def close_by_advance(
        db: AsyncSession,
        cohort_id: uuid.UUID,
        student_id: uuid.UUID,
        lesson_id: uuid.UUID,
    ) -> StudentLessonProgress | None:
        """DISPARADA/ATIVA → ENCERRADA_POR_AVANCO when the professor unlocks the next lesson."""
        row = await StudentProgressService._get_progress(
            db, cohort_id, student_id, lesson_id
        )
        if row is None:
            return None

        if row.status not in (
            StudentLessonProgressStatus.DISPARADA,
            StudentLessonProgressStatus.ATIVA,
        ):
            return row

        now = _utcnow()
        row.status = StudentLessonProgressStatus.ENCERRADA_POR_AVANCO
        row.encerrada_por_avanco_at = now
        await db.flush()
        return row

    @staticmethod
    async def on_professor_complete_lesson(
        db: AsyncSession,
        cohort_id: uuid.UUID,
        lesson_id: uuid.UUID,
    ) -> None:
        """DISPARADA for all enrolled students; close previous lesson if still open."""
        previous_lesson_id = await StudentProgressService._previous_lesson_id(
            db, cohort_id, lesson_id
        )

        student_ids = (
            await db.scalars(
                select(Enrollment.student_id).where(Enrollment.cohort_id == cohort_id)
            )
        ).all()

        for student_id in student_ids:
            if previous_lesson_id is not None:
                await StudentProgressService.close_by_advance(
                    db, cohort_id, student_id, previous_lesson_id
                )
            await StudentProgressService._ensure_disparada(
                db, cohort_id, student_id, lesson_id
            )

    @staticmethod
    async def _ensure_disparada(
        db: AsyncSession,
        cohort_id: uuid.UUID,
        student_id: uuid.UUID,
        lesson_id: uuid.UUID,
    ) -> StudentLessonProgress:
        row = await StudentProgressService._get_progress(
            db, cohort_id, student_id, lesson_id
        )
        if row is not None:
            return row

        row = StudentLessonProgress(
            cohort_id=cohort_id,
            student_id=student_id,
            lesson_id=lesson_id,
            status=StudentLessonProgressStatus.DISPARADA,
        )
        db.add(row)
        await db.flush()
        return row

    @staticmethod
    async def _close_other_active_lessons(
        db: AsyncSession,
        cohort_id: uuid.UUID,
        student_id: uuid.UUID,
        *,
        except_lesson_id: uuid.UUID,
    ) -> None:
        others = (
            await db.scalars(
                select(StudentLessonProgress).where(
                    StudentLessonProgress.cohort_id == cohort_id,
                    StudentLessonProgress.student_id == student_id,
                    StudentLessonProgress.status == StudentLessonProgressStatus.ATIVA,
                    StudentLessonProgress.lesson_id != except_lesson_id,
                )
            )
        ).all()
        if not others:
            return

        now = _utcnow()
        for row in others:
            row.status = StudentLessonProgressStatus.ENCERRADA_POR_AVANCO
            row.encerrada_por_avanco_at = now
        await db.flush()

    @staticmethod
    async def _get_progress(
        db: AsyncSession,
        cohort_id: uuid.UUID,
        student_id: uuid.UUID,
        lesson_id: uuid.UUID,
    ) -> StudentLessonProgress | None:
        return await db.scalar(
            select(StudentLessonProgress).where(
                StudentLessonProgress.cohort_id == cohort_id,
                StudentLessonProgress.student_id == student_id,
                StudentLessonProgress.lesson_id == lesson_id,
            )
        )

    @staticmethod
    async def _previous_lesson_id(
        db: AsyncSession,
        cohort_id: uuid.UUID,
        lesson_id: uuid.UUID,
    ) -> uuid.UUID | None:
        ordered = await StudentProgressService._ordered_active_lesson_ids(db, cohort_id)
        try:
            index = ordered.index(lesson_id)
        except ValueError:
            return None
        if index == 0:
            return None
        return ordered[index - 1]

    @staticmethod
    async def _ordered_active_lesson_ids(
        db: AsyncSession,
        cohort_id: uuid.UUID,
    ) -> list[uuid.UUID]:
        cohort = await db.get(Cohort, cohort_id)
        if cohort is None:
            return []

        track = await db.scalar(
            select(Track)
            .where(Track.id == cohort.track_id)
            .options(selectinload(Track.modules).selectinload(Module.lessons))
        )
        if track is None:
            return []

        lesson_ids: list[uuid.UUID] = []
        for mod in sorted(track.modules, key=lambda m: m.position):
            if not mod.is_active:
                continue
            for lesson in sorted(mod.lessons, key=lambda l: l.position):
                if lesson.is_active:
                    lesson_ids.append(lesson.id)
        return lesson_ids
