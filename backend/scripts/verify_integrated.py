"""End-to-end integration runner for student lesson progression (requires dev DB + seed).

Exercises the state machine in one narrative flow, then runs existing verify_* scripts.

Usage (from backend/ with venv active):
  python scripts/verify_integrated.py
"""

from __future__ import annotations

import asyncio
import secrets
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, ".")

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.ai.tools import ToolContext, dispatch
from app.core.database import SessionLocal
from app.models.cohort import Cohort, Enrollment
from app.models.conversation import (
    Author,
    Conversation,
    ConversationScope,
    MessageSource,
)
from app.models.student_progress import StudentLessonProgress, StudentLessonProgressStatus
from app.models.track import Module, Track
from app.models.user import User
from app.models.voice_session import VoiceSession, VoiceSessionStatus
from app.services.cinndi.types import CinndiMessage, CinndiParseResult
from app.services.conversation_service import get_or_create_conversation, record_message
from app.services.lesson_completion_service import complete_lesson
from app.services.realtime.voice_session_service import VoiceSessionService
from app.services.student_progress_service import StudentProgressService
from app.services.whatsapp.inbound_service import persist_inbound

BACKEND_ROOT = Path(__file__).resolve().parent.parent
VERIFY_SCRIPTS = [
    "verify_student_progress_transitions.py",
    "verify_routing_and_blocking.py",
    "verify_conclude_lesson.py",
    "verify_ingestion_flow.py",
    "verify_dispatch_voice_invite.py",
]


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

    students = (
        await db.scalars(
            select(User)
            .join(Enrollment, Enrollment.student_id == User.id)
            .where(Enrollment.cohort_id == cohort.id)
            .order_by(User.email)
        )
    ).all()
    if len(students) < 2:
        raise RuntimeError("Seed precisa de ao menos 2 alunos matriculados")

    student_whatsapp = next((s for s in students if s.whatsapp), None)
    if student_whatsapp is None:
        raise RuntimeError("Aluno com WhatsApp não encontrado")

    return cohort, lessons, students, student_whatsapp


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


async def test_end_to_end_state_machine() -> None:
    async with SessionLocal() as db:
        cohort, lessons, students, student_whatsapp = await _seed_context(db)
        cohort_id = cohort.id
        lesson_n_id = lessons[0].id
        lesson_n1_id = lessons[1].id
        student_whatsapp_id = student_whatsapp.id
        student_whatsapp_phone = student_whatsapp.whatsapp or ""
        student_ids = [student.id for student in students]
        other_student_id = next(sid for sid in student_ids if sid != student_whatsapp_id)
        await _clear_progress(db, cohort_id)

        await complete_lesson(db, cohort_id, lesson_n_id, "Relato integrado N")
        await db.commit()

        for student_id in student_ids:
            row = await StudentProgressService._get_progress(
                db, cohort_id, student_id, lesson_n_id
            )
            assert row is not None, "DISPARADA ausente para aluno matriculado"
            assert row.status == StudentLessonProgressStatus.DISPARADA
        print("OK complete_lesson → DISPARADA para todos os matriculados")

        conversation = await get_or_create_conversation(
            db, cohort_id, student_whatsapp_id, lesson_n_id
        )
        await record_message(
            db,
            conversation,
            Author.STUDENT,
            "Primeira mensagem integrada",
            source=MessageSource.IN_APP_TEXT,
        )
        await db.commit()

        active_row = await StudentProgressService._get_progress(
            db, cohort_id, student_whatsapp_id, lesson_n_id
        )
        assert active_row is not None
        assert active_row.status == StudentLessonProgressStatus.ATIVA
        assert active_row.activated_at is not None
        print("OK 1ª interação → ATIVA")

        ctx = ToolContext(db, cohort_id, student_whatsapp_id, lesson_n_id)
        out = await dispatch("conclude_lesson", {"reason": "integrado"}, ctx)
        await db.commit()
        assert out == "Aula marcada como concluída para este aluno.", out

        concluded = await StudentProgressService._get_progress(
            db, cohort_id, student_whatsapp_id, lesson_n_id
        )
        assert concluded is not None
        assert concluded.status == StudentLessonProgressStatus.CONCLUIDA
        assert concluded.concluded_at is not None
        assert (
            await StudentProgressService._get_progress(
                db, cohort_id, student_whatsapp_id, lesson_n1_id
            )
        ) is None
        print("OK conclude_lesson → CONCLUIDA sem criar próxima aula")

        await _clear_progress(db, cohort_id)
        await complete_lesson(db, cohort_id, lesson_n_id, "Relato N reset")
        await db.commit()
        conv2 = await get_or_create_conversation(
            db, cohort_id, student_whatsapp_id, lesson_n_id
        )
        await record_message(
            db, conv2, Author.STUDENT, "Ativa de novo", source=MessageSource.IN_APP_TEXT
        )
        await db.commit()

        other_row = await StudentProgressService._get_progress(
            db, cohort_id, other_student_id, lesson_n_id
        )
        assert other_row is not None
        assert other_row.status == StudentLessonProgressStatus.DISPARADA

        await complete_lesson(db, cohort_id, lesson_n1_id, "Relato N+1")
        await db.commit()

        closed = await StudentProgressService._get_progress(
            db, cohort_id, student_whatsapp_id, lesson_n_id
        )
        next_row = await StudentProgressService._get_progress(
            db, cohort_id, student_whatsapp_id, lesson_n1_id
        )
        other_next = await StudentProgressService._get_progress(
            db, cohort_id, other_student_id, lesson_n1_id
        )
        assert closed is not None
        assert closed.status == StudentLessonProgressStatus.ENCERRADA_POR_AVANCO
        assert closed.encerrada_por_avanco_at is not None
        assert next_row is not None and next_row.status == StudentLessonProgressStatus.DISPARADA
        assert other_next is not None and other_next.status == StudentLessonProgressStatus.DISPARADA
        print("OK complete_lesson N+1 → anterior ENCERRADA_POR_AVANCO (mesmo ATIVA) + nova DISPARADA")

        parsed = _inbound_parse("Inbound integrado", student_whatsapp_phone)
        result = await persist_inbound(db, parsed)
        await db.commit()
        assert result.detail == "ok", result.detail
        routed = await db.get(Conversation, result.conversation_id)
        assert routed is not None
        assert routed.lesson_id == lesson_n1_id
        print("OK inbound roteia para aula corrente")

        await _clear_progress(db, cohort_id)
        await StudentProgressService.on_professor_complete_lesson(
            db, cohort_id, lesson_n_id
        )
        row = await StudentProgressService._get_progress(
            db, cohort_id, student_whatsapp_id, lesson_n_id
        )
        assert row is not None
        row.status = StudentLessonProgressStatus.CONCLUIDA
        await db.commit()

        blocked = await persist_inbound(
            db, _inbound_parse("Pós-conclusão", student_whatsapp_phone)
        )
        assert blocked.detail == "lesson_closed"
        assert blocked.conversation_id is None
        print("OK inbound CONCLUIDA → lesson_closed (sem LLM/persistência)")

        await _clear_progress(db, cohort_id)
        await StudentProgressService.on_professor_complete_lesson(
            db, cohort_id, lesson_n_id
        )
        first = await get_or_create_conversation(
            db, cohort_id, student_whatsapp_id, lesson_n_id
        )
        second = await get_or_create_conversation(
            db, cohort_id, student_whatsapp_id, lesson_n_id
        )
        assert first.id == second.id

        dup = Conversation(
            cohort_id=cohort_id,
            user_id=student_whatsapp_id,
            lesson_id=lesson_n_id,
            scope=ConversationScope.STUDENT_LESSON,
        )
        db.add(dup)
        try:
            await db.flush()
            raise AssertionError("duplicata cohort+user+lesson deveria falhar")
        except IntegrityError:
            await db.rollback()
        print("OK unicidade de conversa (uma por cohort+user+lesson)")


async def test_voice_session_does_not_change_lesson_progress() -> None:
    async with SessionLocal() as db:
        cohort, lessons, _students, student_whatsapp = await _seed_context(db)
        cohort_id = cohort.id
        lesson_n_id = lessons[0].id
        student_whatsapp_id = student_whatsapp.id

        await _clear_progress(db, cohort_id)
        await StudentProgressService.on_professor_complete_lesson(
            db, cohort_id, lesson_n_id
        )
        await StudentProgressService.activate_on_first_interaction(
            db, cohort_id, student_whatsapp_id, lesson_n_id
        )
        voice_conv = await get_or_create_conversation(
            db, cohort_id, student_whatsapp_id, lesson_n_id
        )
        await db.commit()

        voice_service = VoiceSessionService()
        now = datetime.now(timezone.utc)
        lock_token = secrets.token_urlsafe(32)
        session = VoiceSession(
            conversation_id=voice_conv.id,
            status=VoiceSessionStatus.ACTIVE,
            lock_token=lock_token,
            lock_expires_at=now + timedelta(seconds=120),
            last_heartbeat_at=now,
            started_at=now,
        )
        db.add(session)
        await db.flush()
        session_id = session.id
        await db.commit()

        progress_before = await StudentProgressService._get_progress(
            db, cohort_id, student_whatsapp_id, lesson_n_id
        )
        assert progress_before is not None
        assert progress_before.status == StudentLessonProgressStatus.ATIVA

        await voice_service.end_session(
            db, session_id, lock_token, reason="explicit", final_sequence=0
        )
        await db.commit()

        progress_after = await StudentProgressService._get_progress(
            db, cohort_id, student_whatsapp_id, lesson_n_id
        )
        ended = await db.get(VoiceSession, session_id)
        assert ended is not None and ended.status == VoiceSessionStatus.ENDED
        assert progress_after is not None
        assert progress_after.status == StudentLessonProgressStatus.ATIVA
        print("OK encerrar VoiceSession não altera status da aula")


def _run_script(name: str) -> None:
    path = BACKEND_ROOT / "scripts" / name
    print(f"\n--- {name} ---")
    result = subprocess.run(
        [sys.executable, str(path)],
        cwd=str(BACKEND_ROOT),
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"{name} falhou (exit {result.returncode})")


async def main() -> None:
    print("=== verify_integrated: fluxo end-to-end ===")
    await test_end_to_end_state_machine()
    await test_voice_session_does_not_change_lesson_progress()
    print("\n=== verify_integrated: scripts existentes ===")
    for script in VERIFY_SCRIPTS:
        _run_script(script)
    print("\nverify_integrated: todas as verificações passaram.")


if __name__ == "__main__":
    asyncio.run(main())
