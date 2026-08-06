"""Read-only micro-scores for professor cohort UI (lesson-scoped)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import MicroScore
from app.models.cohort import Cohort, Enrollment
from app.models.track import Lesson
from app.models.user import User


@dataclass(frozen=True)
class LessonMicroScoreRow:
    id: uuid.UUID
    competency: str
    level: str
    evidence: str
    created_at: datetime


@dataclass(frozen=True)
class LessonMicroScoresResult:
    student_id: uuid.UUID
    student_name: str
    lesson_id: uuid.UUID
    lesson_title: str
    scores: list[LessonMicroScoreRow]


class MicroScoreReadService:
    @staticmethod
    async def list_for_student_lesson(
        db: AsyncSession,
        *,
        cohort_id: uuid.UUID,
        student_id: uuid.UUID,
        lesson_id: uuid.UUID,
    ) -> LessonMicroScoresResult:
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

        lesson = await db.get(Lesson, lesson_id)
        if lesson is None:
            raise ValueError("Aula não encontrada")

        rows = (
            await db.scalars(
                select(MicroScore)
                .where(
                    MicroScore.cohort_id == cohort_id,
                    MicroScore.student_id == student_id,
                    MicroScore.lesson_id == lesson_id,
                )
                .order_by(MicroScore.created_at.desc())
            )
        ).all()

        return LessonMicroScoresResult(
            student_id=student.id,
            student_name=student.name,
            lesson_id=lesson.id,
            lesson_title=lesson.title,
            scores=[
                LessonMicroScoreRow(
                    id=row.id,
                    competency=row.competency,
                    level=row.level.value,
                    evidence=row.evidence,
                    created_at=row.created_at,
                )
                for row in rows
            ],
        )
