"""Verify lesson-scope student assessment.

Two modes:
  1) Trigger wiring (no DB / Celery / Lira):
       python scripts/verify_lesson_assessment.py --check-trigger

  2) Direct assessment for an already-concluded (cohort, student, lesson):
       python scripts/verify_lesson_assessment.py \\
         --cohort-id UUID --student-id UUID --lesson-id UUID

     With --force, runs even if progress is missing / not concluded (warns only).

Usage (from backend/ with venv active).
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import sys
import uuid

sys.path.insert(0, ".")


def test_conclude_enqueues_lesson_assessment() -> None:
    """Conclude must enqueue assess_student_lesson after commit (no Celery needed)."""
    from app.ai import tools

    source = inspect.getsource(tools._conclude_lesson)
    assert "enqueue_after_commit" in source
    assert "assess_student_lesson" in source
    print("OK _conclude_lesson enfileira assess_student_lesson via enqueue_after_commit")


async def run_direct_assessment(
    cohort_id: uuid.UUID,
    student_id: uuid.UUID,
    lesson_id: uuid.UUID,
    *,
    force: bool = False,
) -> None:
    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models.assessment import AssessmentScope, StudentAssessment
    from app.services.assessment.lesson_assessment_service import LessonAssessmentService
    from app.services.student_progress_service import StudentProgressService

    async with SessionLocal() as db:
        progress = await StudentProgressService._get_progress(
            db, cohort_id, student_id, lesson_id
        )
        if progress is None or progress.concluded_at is None:
            msg = (
                "Progresso não encontrado ou aula ainda não concluída "
                f"(cohort={cohort_id} student={student_id} lesson={lesson_id})."
            )
            if force:
                print(f"AVISO: {msg} Continuando com --force.")
            else:
                raise SystemExit(msg)

        row = await LessonAssessmentService.assess(
            db, cohort_id, student_id, lesson_id
        )
        await db.commit()

        persisted = await db.scalar(
            select(StudentAssessment)
            .where(
                StudentAssessment.cohort_id == cohort_id,
                StudentAssessment.student_id == student_id,
                StudentAssessment.scope == AssessmentScope.LESSON,
                StudentAssessment.lesson_id == lesson_id,
            )
            .order_by(StudentAssessment.created_at.desc())
            .limit(1)
        )
        assert persisted is not None, "StudentAssessment não foi persistido"
        assert persisted.id == row.id

        level = persisted.level.value if persisted.level is not None else None
        print("OK avaliação de aula persistida")
        print(f"  assessment_id: {persisted.id}")
        print(f"  level: {level}")
        print(f"  assessment: {persisted.assessment[:500]}")
        print(f"  gaps: {persisted.gaps[:500]}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify lesson assessment flow")
    parser.add_argument(
        "--check-trigger",
        action="store_true",
        help="Only assert conclude → enqueue wiring (no DB)",
    )
    parser.add_argument("--cohort-id", type=uuid.UUID, default=None)
    parser.add_argument("--student-id", type=uuid.UUID, default=None)
    parser.add_argument("--lesson-id", type=uuid.UUID, default=None)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run even if progress is missing or lesson is not concluded",
    )
    args = parser.parse_args()

    if args.check_trigger:
        test_conclude_enqueues_lesson_assessment()
        print("\nChecagem do gatilho passou.")
        return

    missing = [
        name
        for name, value in (
            ("--cohort-id", args.cohort_id),
            ("--student-id", args.student_id),
            ("--lesson-id", args.lesson_id),
        )
        if value is None
    ]
    if missing:
        parser.error(
            "modo direto exige "
            + ", ".join(missing)
            + " (ou use --check-trigger)"
        )

    asyncio.run(
        run_direct_assessment(
            args.cohort_id,
            args.student_id,
            args.lesson_id,
            force=args.force,
        )
    )
    print("\nAvaliação direta concluída.")


if __name__ == "__main__":
    main()
