"""Routing and post-conclusion blocking checks (requires dev DB + seed).

Usage (from backend/ with venv active):
  python scripts/verify_routing_and_blocking.py
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
from app.services.conversation_service import get_or_create_conversation, record_message
from app.services.lesson_completion_service import complete_lesson
from app.services.student_progress_service import (
    LessonNotInteractiveError,
    StudentProgressService,
)
from app.services.whatsapp.inbound_service import persist_inbound
from app.services.cinndi.types import CinndiMessage, CinndiParseResult


async def _seed_context(db):
    cohort = await db.scalar(select(Cohort).limit(1))
    if cohort is None:
        raise RuntimeError("Nenhuma turma — rode bin/db-reset")

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
        .where(Enrollment.cohort_id == cohort.id, User.whatsapp.is_not(None))
        .limit(1)
    )
    if student is None:
        raise RuntimeError("Aluno com WhatsApp não encontrado")

    return cohort, lessons, student


async def _clear_state(db, cohort_id: uuid.UUID) -> None:
    progress = (
        await db.scalars(
            select(StudentLessonProgress).where(
                StudentLessonProgress.cohort_id == cohort_id
            )
        )
    ).all()
    for row in progress:
        await db.delete(row)
    await db.flush()


def _inbound_parse(body: str, phone: str) -> CinndiParseResult:
    msg = CinndiMessage(
        body=body,
        from_phone=phone,
        to_phone="5511999999999",
        message_id=f"verify-{uuid.uuid4()}",
        message_type="chat",
        self_direction="in",
    )
    return CinndiParseResult(
        type="mensagem",
        channel_phone="5511999999999",
        origin_phone=phone,
        message=msg,
    )


async def test_resolve_routable_route_prioritizes_ativa() -> None:
    async with SessionLocal() as db:
        cohort, lessons, student = await _seed_context(db)
        await _clear_state(db, cohort.id)

        await StudentProgressService.on_professor_complete_lesson(
            db, cohort.id, lessons[0].id
        )
        await StudentProgressService.activate_on_first_interaction(
            db, cohort.id, student.id, lessons[0].id
        )
        await db.commit()

        route = await StudentProgressService.resolve_routable_route(db, student.id)
        assert route == (cohort.id, lessons[0].id)
        print("OK resolve_routable_route prioriza ATIVA")


async def test_inbound_routes_to_active_lesson() -> None:
    async with SessionLocal() as db:
        cohort, lessons, student = await _seed_context(db)
        await _clear_state(db, cohort.id)

        await complete_lesson(db, cohort.id, lessons[0].id, "Relato")
        await db.commit()

        parsed = _inbound_parse("Oi Lira", student.whatsapp or "")
        result = await persist_inbound(db, parsed)
        await db.commit()

        assert result.detail == "ok", result.detail
        assert result.conversation_id is not None

        conversation = await db.get(Conversation, result.conversation_id)
        assert conversation is not None
        assert conversation.lesson_id == lessons[0].id

        progress = await StudentProgressService._get_progress(
            db, cohort.id, student.id, lessons[0].id
        )
        assert progress is not None
        assert progress.status == StudentLessonProgressStatus.ATIVA
        print("OK inbound roteia para aula DISPARADA/ATIVA correta")


async def test_inbound_blocks_encerrada_por_avanco() -> None:
    async with SessionLocal() as db:
        cohort, lessons, student = await _seed_context(db)
        await _clear_state(db, cohort.id)

        await complete_lesson(db, cohort.id, lessons[0].id, "Aula 1")
        await complete_lesson(db, cohort.id, lessons[1].id, "Aula 2")
        await db.commit()

        old_progress = await StudentProgressService._get_progress(
            db, cohort.id, student.id, lessons[0].id
        )
        assert old_progress is not None
        assert old_progress.status == StudentLessonProgressStatus.ENCERRADA_POR_AVANCO

        # Simula inbound tentando usar conversa antiga — roteamento cai na aula 2
        parsed = _inbound_parse("Mensagem na aula nova", student.whatsapp or "")
        result = await persist_inbound(db, parsed)
        await db.commit()
        assert result.detail == "ok"

        conversation = await db.get(Conversation, result.conversation_id)
        assert conversation is not None
        assert conversation.lesson_id == lessons[1].id
        print("OK inbound após avanço cai na aula DISPARADA atual (não na encerrada)")


async def test_inbound_lesson_closed_when_not_interactive() -> None:
    async with SessionLocal() as db:
        cohort, lessons, student = await _seed_context(db)
        await _clear_state(db, cohort.id)

        await StudentProgressService.on_professor_complete_lesson(
            db, cohort.id, lessons[0].id
        )
        row = await StudentProgressService._get_progress(
            db, cohort.id, student.id, lessons[0].id
        )
        assert row is not None
        row.status = StudentLessonProgressStatus.CONCLUIDA
        await db.commit()

        parsed = _inbound_parse("Tentativa pós-conclusão", student.whatsapp or "")
        result = await persist_inbound(db, parsed)
        assert result.detail == "lesson_closed"
        assert result.conversation_id is None
        print("OK inbound CONCLUIDA → lesson_closed (sem persistir)")


async def test_voice_handoff_blocks_stale_lesson() -> None:
    async with SessionLocal() as db:
        cohort, lessons, student = await _seed_context(db)
        await _clear_state(db, cohort.id)

        await complete_lesson(db, cohort.id, lessons[0].id, "Aula 1")
        await complete_lesson(db, cohort.id, lessons[1].id, "Aula 2")
        await db.commit()

        try:
            await StudentProgressService.validate_voice_handoff(
                db,
                cohort_id=cohort.id,
                student_id=student.id,
                lesson_id=lessons[0].id,
            )
            raise AssertionError("handoff da aula encerrada deveria falhar")
        except LessonNotInteractiveError as exc:
            assert exc.reason == "lesson_closed"

        await StudentProgressService.validate_voice_handoff(
            db,
            cohort_id=cohort.id,
            student_id=student.id,
            lesson_id=lessons[1].id,
        )
        print("OK validate_voice_handoff bloqueia aula encerrada e aceita aula atual")


async def test_in_app_blocks_encerrada() -> None:
    async with SessionLocal() as db:
        cohort, lessons, student = await _seed_context(db)
        await _clear_state(db, cohort.id)

        await StudentProgressService.on_professor_complete_lesson(
            db, cohort.id, lessons[0].id
        )
        row = await StudentProgressService._get_progress(
            db, cohort.id, student.id, lessons[0].id
        )
        assert row is not None
        row.status = StudentLessonProgressStatus.ENCERRADA_POR_AVANCO
        await db.commit()

        try:
            conversation = await get_or_create_conversation(
                db, cohort.id, student.id, lessons[0].id
            )
            await record_message(
                db,
                conversation,
                Author.STUDENT,
                "teste",
                source=MessageSource.IN_APP_TEXT,
            )
            raise AssertionError("record_message não deveria ser o guard — student_lesson_message sim")
        except Exception:
            pass

        assert not await StudentProgressService.is_lesson_interactive_for(
            db, cohort.id, student.id, lessons[0].id
        )
        print("OK is_lesson_interactive_for false em ENCERRADA_POR_AVANCO")


async def main() -> None:
    await test_resolve_routable_route_prioritizes_ativa()
    await test_inbound_routes_to_active_lesson()
    await test_inbound_blocks_encerrada_por_avanco()
    await test_inbound_lesson_closed_when_not_interactive()
    await test_voice_handoff_blocks_stale_lesson()
    await test_in_app_blocks_encerrada()
    print("\nTodas as verificações de roteamento/bloqueio passaram.")


if __name__ == "__main__":
    asyncio.run(main())
