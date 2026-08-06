"""Completion checks for chaining module/track assessments.

Uses existing StudentLessonProgress + StudentAssessment — no new state machine.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.assessment import AssessmentScope, StudentAssessment
from app.models.student_progress import StudentLessonProgress, StudentLessonProgressStatus
from app.models.track import Lesson, Module, Track
from app.services.assessment.evaluator import latest_assessments_for_scope_ids


async def active_lessons_for_module(
    db: AsyncSession, module_id: uuid.UUID
) -> list[Lesson]:
    module = await db.scalar(
        select(Module)
        .where(Module.id == module_id)
        .options(selectinload(Module.lessons))
    )
    if module is None or not module.is_active:
        return []
    return sorted(
        (lesson for lesson in module.lessons if lesson.is_active),
        key=lambda lesson: lesson.position,
    )


async def active_modules_for_track(
    db: AsyncSession, track_id: uuid.UUID
) -> list[Module]:
    track = await db.scalar(
        select(Track)
        .where(Track.id == track_id)
        .options(selectinload(Track.modules).selectinload(Module.lessons))
    )
    if track is None:
        return []
    return sorted(
        (module for module in track.modules if module.is_active),
        key=lambda module: module.position,
    )


async def active_lesson_ids_for_track(
    db: AsyncSession, track_id: uuid.UUID
) -> list[uuid.UUID]:
    modules = await active_modules_for_track(db, track_id)
    lesson_ids: list[uuid.UUID] = []
    for module in modules:
        for lesson in sorted(module.lessons, key=lambda item: item.position):
            if lesson.is_active:
                lesson_ids.append(lesson.id)
    return lesson_ids


async def module_lessons_all_concluded(
    db: AsyncSession,
    *,
    cohort_id: uuid.UUID,
    student_id: uuid.UUID,
    module_id: uuid.UUID,
) -> bool:
    """True when every active lesson of the module is terminal for the student.

    Terminal = CONCLUIDA (finished with Lira) or ENCERRADA_POR_AVANCO (class
    moved on). Either path yields a lesson assessment, so the module chain
    must not stall on advance-only lessons.
    """
    lessons = await active_lessons_for_module(db, module_id)
    if not lessons:
        return False

    lesson_ids = [lesson.id for lesson in lessons]
    settled = (
        await db.scalars(
            select(StudentLessonProgress.lesson_id).where(
                StudentLessonProgress.cohort_id == cohort_id,
                StudentLessonProgress.student_id == student_id,
                StudentLessonProgress.lesson_id.in_(lesson_ids),
                StudentLessonProgress.status.in_(
                    (
                        StudentLessonProgressStatus.CONCLUIDA,
                        StudentLessonProgressStatus.ENCERRADA_POR_AVANCO,
                    )
                ),
            )
        )
    ).all()
    return set(settled) == set(lesson_ids)


async def track_modules_all_assessed(
    db: AsyncSession,
    *,
    cohort_id: uuid.UUID,
    student_id: uuid.UUID,
    track_id: uuid.UUID,
) -> bool:
    modules = await active_modules_for_track(db, track_id)
    if not modules:
        return False

    module_ids = [module.id for module in modules]
    latest = await latest_assessments_for_scope_ids(
        db,
        cohort_id=cohort_id,
        student_id=student_id,
        scope=AssessmentScope.MODULE,
        scope_fk_column=StudentAssessment.module_id,
        scope_ids=module_ids,
    )
    return len(latest) == len(module_ids)
