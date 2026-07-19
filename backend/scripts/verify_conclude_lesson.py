"""Smoke checks for conclude_lesson tool (DB required).

Usage (from backend/ with venv active):
  python scripts/verify_conclude_lesson.py
"""

from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.ai.tools import ToolContext, dispatch
from app.core.database import SessionLocal
from app.models.cohort import Cohort, Enrollment
from app.models.student_progress import StudentLessonProgressStatus
from app.models.track import Module, Track
from app.models.user import User
from app.services.student_progress_service import StudentProgressService


async def _seed_context(db):
    cohort = await db.scalar(select(Cohort).limit(1))
    track = await db.scalar(
        select(Track)
        .where(Track.id == cohort.track_id)
        .options(selectinload(Track.modules).selectinload(Module.lessons))
    )
    lessons = []
    for mod in sorted(track.modules, key=lambda m: m.position):
        for lesson in sorted(mod.lessons, key=lambda l: l.position):
            if mod.is_active and lesson.is_active:
                lessons.append(lesson)

    student = await db.scalar(
        select(User)
        .join(Enrollment, Enrollment.student_id == User.id)
        .where(Enrollment.cohort_id == cohort.id)
        .limit(1)
    )
    return cohort, lessons, student


async def test_conclude_lesson_from_ativa() -> None:
    async with SessionLocal() as db:
        cohort, lessons, student = await _seed_context(db)

        from app.models.student_progress import StudentLessonProgress

        existing = (
            await db.scalars(
                select(StudentLessonProgress).where(
                    StudentLessonProgress.cohort_id == cohort.id,
                    StudentLessonProgress.student_id == student.id,
                )
            )
        ).all()
        for row in existing:
            await db.delete(row)
        await db.flush()

        await StudentProgressService.on_professor_complete_lesson(
            db, cohort.id, lessons[0].id
        )
        await StudentProgressService.activate_on_first_interaction(
            db, cohort.id, student.id, lessons[0].id
        )
        await db.commit()

        ctx = ToolContext(
            db,
            cohort.id,
            student.id,
            lessons[0].id,
        )
        out = await dispatch("conclude_lesson", {"reason": "teste"}, ctx)
        await db.commit()

        assert out == "Aula marcada como concluída para este aluno.", out

        row = await StudentProgressService._get_progress(
            db, cohort.id, student.id, lessons[0].id
        )
        assert row is not None
        assert row.status == StudentLessonProgressStatus.CONCLUIDA
        assert row.concluded_at is not None

        next_row = await StudentProgressService._get_progress(
            db, cohort.id, student.id, lessons[1].id
        )
        assert next_row is None
        print("OK conclude_lesson ATIVA → CONCLUIDA sem criar próxima aula")


async def test_conclude_lesson_rejects_non_ativa() -> None:
    async with SessionLocal() as db:
        cohort, lessons, student = await _seed_context(db)

        ctx = ToolContext(db, cohort.id, student.id, lessons[0].id)
        out = await dispatch("conclude_lesson", {}, ctx)
        assert out == "Progresso não está ATIVA para conclusão."
        print("OK conclude_lesson rejeita quando não está ATIVA")


async def test_tool_schema_present() -> None:
    from app.ai.tools import TOOL_SCHEMAS
    from app.services.realtime.realtime_tools import SERVER_TOOL_NAMES

    names = {s["function"]["name"] for s in TOOL_SCHEMAS}
    assert "conclude_lesson" in names
    assert "conclude_lesson" in SERVER_TOOL_NAMES
    print("OK schema e SERVER_TOOL_NAMES incluem conclude_lesson")


async def main() -> None:
    await test_tool_schema_present()
    await test_conclude_lesson_rejects_non_ativa()
    await test_conclude_lesson_from_ativa()
    print("\nTodas as verificações de conclude_lesson passaram.")


if __name__ == "__main__":
    asyncio.run(main())
