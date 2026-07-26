"""Integration checks for StudentLessonProgress transitions (requires dev DB + seed).

Usage (from backend/ with venv active):
  python scripts/verify_student_progress_transitions.py
"""

from __future__ import annotations

import asyncio
import sys
import uuid

sys.path.insert(0, ".")

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import SessionLocal
from app.models.cohort import Cohort, Enrollment
from app.models.conversation import Author, Conversation, MessageSource
from app.models.student_progress import StudentLessonProgress, StudentLessonProgressStatus
from app.models.track import Module, Track
from app.models.user import User
from app.services.conversation_service import record_message
from app.services.lesson_completion_service import complete_lesson
from app.services.student_progress_service import StudentProgressService


async def _seed_context(db):
    cohort = await db.scalar(select(Cohort).limit(1))
    if cohort is None:
        raise RuntimeError("Nenhuma turma no banco — rode bin/db-reset")

    track = await db.scalar(
        select(Track)
        .where(Track.id == cohort.track_id)
        .options(selectinload(Track.modules).selectinload(Module.lessons))
    )
    if track is None:
        raise RuntimeError("Trilha da turma não encontrada")

    lessons = []
    for mod in sorted(track.modules, key=lambda m: m.position):
        for lesson in sorted(mod.lessons, key=lambda l: l.position):
            if mod.is_active and lesson.is_active:
                lessons.append(lesson)
    if len(lessons) < 2:
        raise RuntimeError("Seed precisa de ao menos 2 aulas ativas")

    student = await db.scalar(
        select(User)
        .join(Enrollment, Enrollment.student_id == User.id)
        .where(Enrollment.cohort_id == cohort.id)
        .limit(1)
    )
    if student is None:
        raise RuntimeError("Nenhum aluno matriculado — rode bin/db-reset")

    return cohort, lessons, student


async def _get_or_create_conversation(
    db, cohort_id: uuid.UUID, user_id: uuid.UUID, lesson_id: uuid.UUID
) -> Conversation:
    from app.models.conversation import ConversationScope

    existing = await db.scalar(
        select(Conversation).where(
            Conversation.cohort_id == cohort_id,
            Conversation.user_id == user_id,
            Conversation.lesson_id == lesson_id,
        )
    )
    if existing is not None:
        return existing

    conversation = Conversation(
        cohort_id=cohort_id,
        user_id=user_id,
        lesson_id=lesson_id,
        scope=ConversationScope.STUDENT_LESSON,
    )
    db.add(conversation)
    await db.flush()
    return conversation


async def _clear_progress(db, cohort_id: uuid.UUID) -> None:
    rows = (
        await db.scalars(
            select(StudentLessonProgress).where(
                StudentLessonProgress.cohort_id == cohort_id
            )
        )
    ).all()
    for row in rows:
        await db.delete(row)
    await db.flush()


async def test_complete_lesson_creates_disparada() -> None:
    async with SessionLocal() as db:
        cohort, lessons, student = await _seed_context(db)
        await _clear_progress(db, cohort.id)

        await complete_lesson(db, cohort.id, lessons[0].id, "Relato teste")
        await db.commit()

        row = await db.scalar(
            select(StudentLessonProgress).where(
                StudentLessonProgress.cohort_id == cohort.id,
                StudentLessonProgress.student_id == student.id,
                StudentLessonProgress.lesson_id == lessons[0].id,
            )
        )
        assert row is not None, "DISPARADA não criada após complete_lesson"
        assert row.status == StudentLessonProgressStatus.DISPARADA
        print("OK complete_lesson → DISPARADA para matriculados")


async def test_first_interaction_activates() -> None:
    async with SessionLocal() as db:
        cohort, lessons, student = await _seed_context(db)
        await _clear_progress(db, cohort.id)

        await StudentProgressService.on_professor_complete_lesson(
            db, cohort.id, lessons[0].id
        )

        conversation = await _get_or_create_conversation(
            db, cohort.id, student.id, lessons[0].id
        )
        await record_message(
            db,
            conversation,
            Author.STUDENT,
            "Primeira mensagem",
            source=MessageSource.IN_APP_TEXT,
        )
        await db.commit()

        row = await db.scalar(
            select(StudentLessonProgress).where(
                StudentLessonProgress.cohort_id == cohort.id,
                StudentLessonProgress.student_id == student.id,
                StudentLessonProgress.lesson_id == lessons[0].id,
            )
        )
        assert row is not None
        assert row.status == StudentLessonProgressStatus.ATIVA
        assert row.activated_at is not None
        print("OK 1ª interação → ATIVA")


async def test_second_complete_lesson_closes_previous() -> None:
    async with SessionLocal() as db:
        cohort, lessons, student = await _seed_context(db)
        await _clear_progress(db, cohort.id)

        await complete_lesson(db, cohort.id, lessons[0].id, "Aula 1")
        await db.commit()

        conversation = await _get_or_create_conversation(
            db, cohort.id, student.id, lessons[0].id
        )
        await record_message(
            db, conversation, Author.STUDENT, "Oi", source=MessageSource.IN_APP_TEXT
        )
        await db.commit()

        await complete_lesson(db, cohort.id, lessons[1].id, "Aula 2")
        await db.commit()

        prev = await db.scalar(
            select(StudentLessonProgress).where(
                StudentLessonProgress.cohort_id == cohort.id,
                StudentLessonProgress.student_id == student.id,
                StudentLessonProgress.lesson_id == lessons[0].id,
            )
        )
        nxt = await db.scalar(
            select(StudentLessonProgress).where(
                StudentLessonProgress.cohort_id == cohort.id,
                StudentLessonProgress.student_id == student.id,
                StudentLessonProgress.lesson_id == lessons[1].id,
            )
        )
        assert prev is not None
        assert prev.status == StudentLessonProgressStatus.ENCERRADA_POR_AVANCO
        assert prev.encerrada_por_avanco_at is not None
        assert nxt is not None
        assert nxt.status == StudentLessonProgressStatus.DISPARADA
        print("OK 2º complete_lesson → anterior ENCERRADA_POR_AVANCO + nova DISPARADA")


async def test_one_ativa_per_student() -> None:
    async with SessionLocal() as db:
        cohort, lessons, student = await _seed_context(db)
        await _clear_progress(db, cohort.id)

        await StudentProgressService.on_professor_complete_lesson(
            db, cohort.id, lessons[0].id
        )
        await StudentProgressService.on_professor_complete_lesson(
            db, cohort.id, lessons[1].id
        )

        row0 = await StudentProgressService._get_progress(
            db, cohort.id, student.id, lessons[0].id
        )
        row1 = await StudentProgressService._get_progress(
            db, cohort.id, student.id, lessons[1].id
        )
        assert row0 is not None and row0.status == StudentLessonProgressStatus.ENCERRADA_POR_AVANCO
        assert row1 is not None and row1.status == StudentLessonProgressStatus.DISPARADA

        await StudentProgressService.activate_on_first_interaction(
            db, cohort.id, student.id, lessons[1].id
        )
        await db.commit()

        from sqlalchemy import func

        count = await db.scalar(
            select(func.count())
            .select_from(StudentLessonProgress)
            .where(
                StudentLessonProgress.cohort_id == cohort.id,
                StudentLessonProgress.student_id == student.id,
                StudentLessonProgress.status == StudentLessonProgressStatus.ATIVA,
            )
        )
        assert count == 1
        print("OK no máximo uma ATIVA por aluno na turma")


async def test_resolve_routable_lesson() -> None:
    async with SessionLocal() as db:
        cohort, lessons, student = await _seed_context(db)
        await _clear_progress(db, cohort.id)

        await StudentProgressService.on_professor_complete_lesson(
            db, cohort.id, lessons[0].id
        )
        await StudentProgressService.activate_on_first_interaction(
            db, cohort.id, student.id, lessons[0].id
        )
        await db.commit()

        resolved = await StudentProgressService.resolve_routable_lesson(
            db, student.id, cohort.id
        )
        assert resolved == lessons[0].id
        print("OK resolve_routable_lesson prioriza ATIVA")


async def test_is_lesson_interactive() -> None:
    assert StudentProgressService.is_lesson_interactive(
        StudentLessonProgressStatus.DISPARADA
    )
    assert StudentProgressService.is_lesson_interactive(
        StudentLessonProgressStatus.ATIVA
    )
    assert not StudentProgressService.is_lesson_interactive(
        StudentLessonProgressStatus.CONCLUIDA
    )
    assert not StudentProgressService.is_lesson_interactive(
        StudentLessonProgressStatus.ENCERRADA_POR_AVANCO
    )
    print("OK is_lesson_interactive")


async def main() -> None:
    await test_is_lesson_interactive()
    await test_complete_lesson_creates_disparada()
    await test_first_interaction_activates()
    await test_second_complete_lesson_closes_previous()
    await test_one_ativa_per_student()
    await test_resolve_routable_lesson()
    print("\nTodas as verificações de progressão passaram.")


if __name__ == "__main__":
    asyncio.run(main())
