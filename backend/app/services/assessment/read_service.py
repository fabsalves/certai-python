"""Read-side helpers for persisted StudentAssessments (no AI)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import AssessmentScope, StudentAssessment
from app.models.cohort import Cohort, Enrollment
from app.models.student_progress import StudentLessonProgress, StudentLessonProgressStatus
from app.models.track import Lesson, Module, Track
from app.models.user import User


@dataclass(frozen=True)
class AssessmentReadRow:
    id: uuid.UUID
    student_id: uuid.UUID
    student_name: str
    scope: str
    lesson_id: uuid.UUID | None
    module_id: uuid.UUID | None
    track_id: uuid.UUID | None
    scope_title: str
    level: str | None
    assessment: str
    gaps: str
    created_at: datetime


@dataclass(frozen=True)
class PendingStudentRow:
    student_id: uuid.UUID
    student_name: str


@dataclass(frozen=True)
class LessonAssessmentsResult:
    lesson_id: uuid.UUID
    assessments: list[AssessmentReadRow]
    pending: list[PendingStudentRow]


@dataclass(frozen=True)
class StudentAssessmentsResult:
    student_id: uuid.UUID
    student_name: str
    assessments: list[AssessmentReadRow]


def _level_value(row: StudentAssessment) -> str | None:
    return row.level.value if row.level is not None else None


def _scope_key(row: StudentAssessment) -> tuple[str, uuid.UUID] | None:
    if row.scope == AssessmentScope.LESSON and row.lesson_id is not None:
        return ("lesson", row.lesson_id)
    if row.scope == AssessmentScope.MODULE and row.module_id is not None:
        return ("module", row.module_id)
    if row.scope == AssessmentScope.TRACK and row.track_id is not None:
        return ("track", row.track_id)
    return None


class StudentAssessmentReadService:
    """Latest StudentAssessment reads for platform exposure."""

    @staticmethod
    async def latest_lesson_assessments(
        db: AsyncSession,
        *,
        cohort_id: uuid.UUID,
        lesson_id: uuid.UUID,
    ) -> LessonAssessmentsResult:
        cohort = await db.get(Cohort, cohort_id)
        if cohort is None:
            raise ValueError("Turma não encontrada")

        lesson = await db.scalar(
            select(Lesson)
            .join(Module, Lesson.module_id == Module.id)
            .where(Lesson.id == lesson_id, Module.track_id == cohort.track_id)
        )
        if lesson is None:
            raise ValueError("Aula não encontrada nesta turma")

        assessment_rows = (
            await db.execute(
                select(StudentAssessment, User.name)
                .join(User, StudentAssessment.student_id == User.id)
                .where(
                    StudentAssessment.cohort_id == cohort_id,
                    StudentAssessment.scope == AssessmentScope.LESSON,
                    StudentAssessment.lesson_id == lesson_id,
                )
                .order_by(StudentAssessment.created_at.desc())
            )
        ).all()

        latest_by_student: dict[uuid.UUID, tuple[StudentAssessment, str]] = {}
        for row, student_name in assessment_rows:
            if row.student_id in latest_by_student:
                continue
            latest_by_student[row.student_id] = (row, student_name)

        assessments = [
            AssessmentReadRow(
                id=row.id,
                student_id=row.student_id,
                student_name=student_name,
                scope=AssessmentScope.LESSON.value,
                lesson_id=row.lesson_id,
                module_id=row.module_id,
                track_id=row.track_id,
                scope_title=lesson.title,
                level=_level_value(row),
                assessment=row.assessment,
                gaps=row.gaps,
                created_at=row.created_at,
            )
            for row, student_name in sorted(
                latest_by_student.values(),
                key=lambda item: item[1].lower(),
            )
        ]

        concluded_rows = (
            await db.execute(
                select(StudentLessonProgress.student_id, User.name)
                .join(User, StudentLessonProgress.student_id == User.id)
                .where(
                    StudentLessonProgress.cohort_id == cohort_id,
                    StudentLessonProgress.lesson_id == lesson_id,
                    StudentLessonProgress.status
                    == StudentLessonProgressStatus.CONCLUIDA,
                )
                .order_by(User.name)
            )
        ).all()

        assessed_ids = set(latest_by_student.keys())
        pending = [
            PendingStudentRow(student_id=student_id, student_name=student_name)
            for student_id, student_name in concluded_rows
            if student_id not in assessed_ids
        ]

        return LessonAssessmentsResult(
            lesson_id=lesson_id,
            assessments=assessments,
            pending=pending,
        )

    @staticmethod
    async def latest_for_student(
        db: AsyncSession,
        *,
        cohort_id: uuid.UUID,
        student_id: uuid.UUID,
    ) -> StudentAssessmentsResult:
        cohort = await db.get(Cohort, cohort_id)
        if cohort is None:
            raise ValueError("Turma não encontrada")

        enrollment = await db.scalar(
            select(Enrollment.id).where(
                Enrollment.cohort_id == cohort_id,
                Enrollment.student_id == student_id,
            )
        )
        if enrollment is None:
            raise ValueError("Aluno não matriculado nesta turma")

        student = await db.get(User, student_id)
        if student is None:
            raise ValueError("Aluno não encontrado")

        rows = list(
            (
                await db.scalars(
                    select(StudentAssessment)
                    .where(
                        StudentAssessment.cohort_id == cohort_id,
                        StudentAssessment.student_id == student_id,
                    )
                    .order_by(StudentAssessment.created_at.desc())
                )
            ).all()
        )

        latest_by_key: dict[tuple[str, uuid.UUID], StudentAssessment] = {}
        for row in rows:
            key = _scope_key(row)
            if key is None or key in latest_by_key:
                continue
            latest_by_key[key] = row

        lesson_ids = [
            scope_id for scope, scope_id in latest_by_key if scope == "lesson"
        ]
        module_ids = [
            scope_id for scope, scope_id in latest_by_key if scope == "module"
        ]
        track_ids = [
            scope_id for scope, scope_id in latest_by_key if scope == "track"
        ]

        lesson_titles: dict[uuid.UUID, str] = {}
        if lesson_ids:
            lesson_titles = dict(
                (
                    await db.execute(
                        select(Lesson.id, Lesson.title).where(Lesson.id.in_(lesson_ids))
                    )
                ).all()
            )

        module_titles: dict[uuid.UUID, str] = {}
        if module_ids:
            module_titles = dict(
                (
                    await db.execute(
                        select(Module.id, Module.title).where(Module.id.in_(module_ids))
                    )
                ).all()
            )

        track_titles: dict[uuid.UUID, str] = {}
        if track_ids:
            track_titles = dict(
                (
                    await db.execute(
                        select(Track.id, Track.title).where(Track.id.in_(track_ids))
                    )
                ).all()
            )

        def scope_title_for(row: StudentAssessment) -> str:
            if row.scope == AssessmentScope.LESSON and row.lesson_id is not None:
                return lesson_titles.get(row.lesson_id, "")
            if row.scope == AssessmentScope.MODULE and row.module_id is not None:
                return module_titles.get(row.module_id, "")
            if row.scope == AssessmentScope.TRACK and row.track_id is not None:
                return track_titles.get(row.track_id, "")
            return ""

        scope_order = {
            AssessmentScope.TRACK.value: 0,
            AssessmentScope.MODULE.value: 1,
            AssessmentScope.LESSON.value: 2,
        }
        ordered_rows = sorted(
            latest_by_key.values(),
            key=lambda row: (
                scope_order.get(row.scope.value, 99),
                scope_title_for(row).lower(),
            ),
        )

        assessments = [
            AssessmentReadRow(
                id=row.id,
                student_id=row.student_id,
                student_name=student.name,
                scope=row.scope.value,
                lesson_id=row.lesson_id,
                module_id=row.module_id,
                track_id=row.track_id,
                scope_title=scope_title_for(row),
                level=_level_value(row),
                assessment=row.assessment,
                gaps=row.gaps,
                created_at=row.created_at,
            )
            for row in ordered_rows
        ]

        return StudentAssessmentsResult(
            student_id=student_id,
            student_name=student.name,
            assessments=assessments,
        )
