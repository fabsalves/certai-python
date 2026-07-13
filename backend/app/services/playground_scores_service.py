"""Read-only micro-score snapshot for the admin playground."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import MicroScore
from app.models.cohort import Cohort
from app.models.track import Lesson, Track


async def build_playground_scores(
    db: AsyncSession,
    cohort_id: uuid.UUID,
    student_id: uuid.UUID,
    lesson_id: uuid.UUID,
) -> dict:
    """Return micro-scores for a student, split by the lesson in focus."""
    cohort = await db.get(Cohort, cohort_id)
    if cohort is None:
        raise ValueError("Turma não encontrada")

    track = await db.get(Track, cohort.track_id)
    lesson = await db.get(Lesson, lesson_id)
    if lesson is None:
        raise ValueError("Aula não encontrada")

    rows = (
        await db.execute(
            select(MicroScore, Lesson.title)
            .outerjoin(Lesson, MicroScore.lesson_id == Lesson.id)
            .where(
                MicroScore.cohort_id == cohort_id,
                MicroScore.student_id == student_id,
            )
            .order_by(MicroScore.created_at.desc())
        )
    ).all()

    def _serialize(score: MicroScore, lesson_title: str | None) -> dict:
        return {
            "id": score.id,
            "lesson_id": score.lesson_id,
            "lesson_title": lesson_title or "",
            "competency": score.competency,
            "level": score.level.value,
            "evidence": score.evidence,
            "created_at": score.created_at,
        }

    scores_in_lesson: list[dict] = []
    scores_other_lessons: list[dict] = []
    for score, title in rows:
        item = _serialize(score, title)
        if score.lesson_id == lesson_id:
            scores_in_lesson.append(item)
        else:
            scores_other_lessons.append(item)

    return {
        "track_competency": track.competency if track else "",
        "lesson_focus": {"lesson_id": lesson_id, "lesson_title": lesson.title},
        "scores_in_lesson": scores_in_lesson,
        "scores_other_lessons": scores_other_lessons,
    }
