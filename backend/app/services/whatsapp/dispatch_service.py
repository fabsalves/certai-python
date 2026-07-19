"""Dispatch lesson invite templates to enrolled students via WhatsApp."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.cohort import Cohort, Enrollment
from app.models.conversation import Author, Message, MessageSource
from app.models.track import Lesson, Module, Track
from app.models.user import Role, User
from app.services.cinndi.outbound import CinndiOutboundError, send_template_message
from app.services.conversation_service import get_or_create_conversation, record_message
from app.services.realtime.voice_link_service import VoiceLinkService

logger = logging.getLogger(__name__)

_voice_link_service = VoiceLinkService()

INVITE_TEMPLATE_BODY = (
    "Oi {first_name}! Aqui é a {assistant}, sua parceira de estudos no CertAI.\n"
    'Quero conversar com você sobre a aula "{lesson_title}" da trilha "{track_title}".\n'
    "Vamos explorar o que você fixou e tirar dúvidas? Pode responder por aqui, texto ou áudio."
)

VOICE_INVITE_TEMPLATE_BODY = (
    "Oi {first_name}! 👋 Aqui é a {assistant}, sua parceira de estudos no CertAI.\n"
    'Quero conversar com você sobre a aula "{lesson_title}" da trilha "{track_title}".\n\n'
    "🎙️ Prefere falar comigo ao vivo? Toque no botão abaixo.\n"
    "Ou responda por aqui, texto ou áudio, como preferir. 🙂"
)


def _first_name(full_name: str) -> str:
    parts = full_name.strip().split()
    return parts[0] if parts else full_name


def render_invite_body(
    *,
    first_name: str,
    lesson_title: str,
    track_title: str,
    assistant_name: str,
) -> str:
    return INVITE_TEMPLATE_BODY.format(
        first_name=first_name,
        assistant=assistant_name,
        lesson_title=lesson_title,
        track_title=track_title,
    )


def render_voice_invite_body(
    *,
    first_name: str,
    lesson_title: str,
    track_title: str,
    assistant_name: str,
) -> str:
    return VOICE_INVITE_TEMPLATE_BODY.format(
        first_name=first_name,
        assistant=assistant_name,
        lesson_title=lesson_title,
        track_title=track_title,
    )


async def _already_dispatched(db, conversation_id: uuid.UUID) -> bool:
    existing = await db.scalar(
        select(Message.id).where(
            Message.conversation_id == conversation_id,
            Message.author == Author.AGENT,
        )
    )
    return existing is not None


async def dispatch_lesson_invites(
    db, cohort_id: uuid.UUID, lesson_id: uuid.UUID
) -> dict:
    cohort = await db.get(Cohort, cohort_id)
    if cohort is None:
        return {"status": "cohort_not_found"}

    lesson = await db.get(Lesson, lesson_id)
    if lesson is None:
        return {"status": "lesson_not_found"}

    track = await db.scalar(
        select(Track)
        .where(Track.id == cohort.track_id)
        .options(selectinload(Track.modules).selectinload(Module.lessons))
    )
    track_title = track.title if track else ""

    stmt = (
        select(User)
        .join(Enrollment, Enrollment.student_id == User.id)
        .where(
            Enrollment.cohort_id == cohort_id,
            User.role == Role.STUDENT,
            User.is_active.is_(True),
            User.whatsapp.is_not(None),
        )
    )
    students = (await db.execute(stmt)).scalars().all()

    sent = 0
    skipped = 0
    errors = 0
    use_voice_template = settings.WHATSAPP_INVITE_USE_VOICE_TEMPLATE

    for student in students:
        conversation = await get_or_create_conversation(
            db,
            cohort_id,
            student.id,
            lesson_id,
        )

        if await _already_dispatched(db, conversation.id):
            skipped += 1
            continue

        first_name = _first_name(student.name)
        assistant = settings.ASSISTANT_NAME
        params = [first_name, lesson.title, track_title, assistant]
        button_suffix: str | None = None

        if use_voice_template:
            link = _voice_link_service.generate_token(
                user_id=student.id,
                cohort_id=cohort_id,
                lesson_id=lesson_id,
                conversation_id=conversation.id,
            )
            handoff_token = link.token
            body_text = render_voice_invite_body(
                first_name=first_name,
                lesson_title=lesson.title,
                track_title=track_title,
                assistant_name=assistant,
            )
            template_name = settings.WHATSAPP_INVITE_VOICE_TEMPLATE
            button_suffix = handoff_token
        else:
            body_text = render_invite_body(
                first_name=first_name,
                lesson_title=lesson.title,
                track_title=track_title,
                assistant_name=assistant,
            )
            template_name = settings.WHATSAPP_INVITE_TEMPLATE

        try:
            provider_id = send_template_message(
                to_phone=student.whatsapp or "",
                template_name=template_name,
                body_params=params,
                code=settings.WHATSAPP_TEMPLATE_LANG,
                button_suffix=button_suffix,
            )
        except CinndiOutboundError as exc:
            logger.warning(
                "whatsapp invite failed student=%s lesson=%s: %s",
                student.id,
                lesson_id,
                exc,
            )
            errors += 1
            continue

        await record_message(
            db,
            conversation,
            Author.AGENT,
            body_text,
            provider_message_id=provider_id,
            delivery_status="sent",
            source=MessageSource.WHATSAPP_TEXT,
        )
        sent += 1

    await db.commit()
    return {
        "status": "planned",
        "cohort_id": str(cohort_id),
        "lesson_id": str(lesson_id),
        "sent": sent,
        "skipped": skipped,
        "errors": errors,
        "voice_template": use_voice_template,
    }
