"""Rewinding a test cohort — so the real cycle can be run again, in production.

Two actions, both refusing any cohort that is not marked as a test cohort:

  - `undo_last_closure` rewinds the most recent lesson closure. The tester's loop:
    a bug shows up, it gets fixed and deployed, and only that step is redone.
    Applied repeatedly, it walks backwards.
  - `reset_progress` clears the whole progression. The fallback.

The line both respect: **the setup stays, the progression goes**. Cohort,
enrollments, teaching classes and the roster survive, and so does `AiUsageEvent`
-- the money was really spent, and deleting that would misreport consumption.

Nothing here is a parallel test path: after a rewind the cohort goes through the
same `complete_lesson`, the same engine and the same prompts as a real one.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import (
    CohortLessonNote,
    LessonCoverage,
    MicroScore,
    StudentAssessment,
)
from app.models.cohort import Cohort, CohortModuleProfessor, CohortProgress
from app.models.conversation import Conversation
from app.models.student_progress import (
    StudentLessonProgress,
    StudentLessonProgressStatus,
)
from app.models.track import Lesson
from app.models.user import User
from app.services.cohort.module_class_service import ModuleClassService
from app.services.student_progress_service import StudentProgressService

logger = logging.getLogger(__name__)


class SandboxOnlyError(Exception):
    """The cohort is a real one. There is no override -- see Cohort.is_sandbox."""


class NothingToUndoError(Exception):
    """The cohort has no closure left to rewind."""


def _assert_sandbox(cohort: Cohort) -> None:
    if not cohort.is_sandbox:
        raise SandboxOnlyError(cohort.name)


class SandboxService:
    @staticmethod
    async def undo_last_closure(db: AsyncSession, cohort: Cohort) -> dict:
        """Rewind the cohort's most recent lesson closure.

        Always the most recent one: an arbitrary closure in the middle would be
        ambiguous, this one is not. Returns what was undone and what was removed.
        """
        _assert_sandbox(cohort)

        note = await db.scalar(
            select(CohortLessonNote)
            .where(CohortLessonNote.cohort_id == cohort.id)
            .order_by(CohortLessonNote.created_at.desc())
            .limit(1)
        )
        if note is None:
            raise NothingToUndoError(cohort.name)

        lesson = await db.get(Lesson, note.lesson_id)
        module_class = await db.get(CohortModuleProfessor, note.module_professor_id)
        professor = (
            await db.get(User, module_class.professor_id)
            if module_class is not None
            else None
        )
        student_ids = (
            await ModuleClassService.student_ids_of(db, module_class)
            if module_class is not None
            else []
        )

        removed: dict[str, int] = {}

        # The note goes first: LessonCoverage hangs off note_id with CASCADE, so
        # every segment of this session -- including a carryover that closed an
        # earlier lesson's tail -- goes with it. That is what makes the previous
        # lesson's pendency come back on its own: its standing coverage reverts to
        # the older row. Nothing to restore; the absence of the new row is already
        # the right answer.
        await db.delete(note)
        removed["relatos"] = 1

        removed["progresso_turma"] = await _delete(
            db,
            delete(CohortProgress).where(
                CohortProgress.cohort_id == cohort.id,
                CohortProgress.lesson_id == note.lesson_id,
                CohortProgress.module_professor_id == note.module_professor_id,
            ),
        )

        if student_ids:
            removed["progresso_alunos"] = await _delete(
                db,
                delete(StudentLessonProgress).where(
                    StudentLessonProgress.cohort_id == cohort.id,
                    StudentLessonProgress.lesson_id == note.lesson_id,
                    StudentLessonProgress.student_id.in_(student_ids),
                ),
            )
            # Cascades into Message and VoiceSession.
            removed["conversas"] = await _delete(
                db,
                delete(Conversation).where(
                    Conversation.cohort_id == cohort.id,
                    Conversation.lesson_id == note.lesson_id,
                    Conversation.user_id.in_(student_ids),
                ),
            )
            removed["micro_scores"] = await _delete(
                db,
                delete(MicroScore).where(
                    MicroScore.cohort_id == cohort.id,
                    MicroScore.lesson_id == note.lesson_id,
                    MicroScore.student_id.in_(student_ids),
                ),
            )
            removed["avaliacoes"] = await _delete(
                db,
                delete(StudentAssessment).where(
                    StudentAssessment.cohort_id == cohort.id,
                    StudentAssessment.lesson_id == note.lesson_id,
                    StudentAssessment.student_id.in_(student_ids),
                ),
            )

            await _reopen_previous_lesson(
                db, cohort_id=cohort.id, lesson_id=note.lesson_id, student_ids=student_ids
            )

        await db.flush()
        logger.info(
            "sandbox undo cohort=%s lesson=%s class=%s removed=%s",
            cohort.id,
            note.lesson_id,
            note.module_professor_id,
            removed,
        )
        return {
            "action": "undo_last_closure",
            "lesson_title": lesson.title if lesson is not None else "",
            "professor_name": professor.name if professor is not None else "",
            "removed": removed,
        }

    @staticmethod
    async def reset_progress(db: AsyncSession, cohort: Cohort) -> dict:
        """Clear the cohort's whole progression, keeping its setup."""
        _assert_sandbox(cohort)

        removed: dict[str, int] = {
            "relatos": await _delete(
                db,
                delete(CohortLessonNote).where(
                    CohortLessonNote.cohort_id == cohort.id
                ),
            ),
            # Redundant after the notes cascade, and deliberately so: a coverage
            # row orphaned by any future path still goes.
            "cobertura": await _delete(
                db, delete(LessonCoverage).where(LessonCoverage.cohort_id == cohort.id)
            ),
            "progresso_turma": await _delete(
                db, delete(CohortProgress).where(CohortProgress.cohort_id == cohort.id)
            ),
            "progresso_alunos": await _delete(
                db,
                delete(StudentLessonProgress).where(
                    StudentLessonProgress.cohort_id == cohort.id
                ),
            ),
            "conversas": await _delete(
                db, delete(Conversation).where(Conversation.cohort_id == cohort.id)
            ),
            "micro_scores": await _delete(
                db, delete(MicroScore).where(MicroScore.cohort_id == cohort.id)
            ),
            "avaliacoes": await _delete(
                db,
                delete(StudentAssessment).where(
                    StudentAssessment.cohort_id == cohort.id
                ),
            ),
        }

        await db.flush()
        logger.info("sandbox reset cohort=%s removed=%s", cohort.id, removed)
        return {"action": "reset_progress", "removed": removed}


async def _delete(db: AsyncSession, statement) -> int:
    result = await db.execute(statement)
    return int(result.rowcount or 0)


async def _reopen_previous_lesson(
    db: AsyncSession,
    *,
    cohort_id: uuid.UUID,
    lesson_id: uuid.UUID,
    student_ids: list[uuid.UUID],
) -> None:
    """Undo the side effect that closing a lesson had on the previous one.

    Closing a lesson pushes the previous one to ENCERRADA_POR_AVANCO. Where it
    goes back to is derivable, with no guesswork: a row that was once activated
    has an `activated_at`, so it returns to ATIVA; otherwise it was only ever
    DISPARADA.
    """
    previous_lesson_id = await StudentProgressService._previous_lesson_id(
        db, cohort_id, lesson_id
    )
    if previous_lesson_id is None:
        return

    rows = (
        await db.scalars(
            select(StudentLessonProgress).where(
                StudentLessonProgress.cohort_id == cohort_id,
                StudentLessonProgress.lesson_id == previous_lesson_id,
                StudentLessonProgress.student_id.in_(student_ids),
                StudentLessonProgress.status
                == StudentLessonProgressStatus.ENCERRADA_POR_AVANCO,
            )
        )
    ).all()

    for row in rows:
        row.status = (
            StudentLessonProgressStatus.ATIVA
            if row.activated_at is not None
            else StudentLessonProgressStatus.DISPARADA
        )
        row.encerrada_por_avanco_at = None
