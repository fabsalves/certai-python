"""Persist inbound WhatsApp messages and route to the correct conversation."""

from __future__ import annotations

import base64
import logging
import uuid
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.phone import normalize_br_phone, phone_lookup_variants
from app.models.conversation import Author, Conversation, ConversationChannel, Message, MessageSource
from app.models.user import Role, User
from app.services.cinndi.types import CinndiParseResult
from app.services.conversation_service import record_message
from app.services.transcription_service import transcribe_audio

logger = logging.getLogger(__name__)


@dataclass
class InboundResult:
    conversation_id: uuid.UUID | None
    detail: str


async def apply_delivery_ack(db, parsed: CinndiParseResult) -> bool:
    if not parsed.is_ack or parsed.ack is None:
        return False
    message_id = parsed.ack.message_id
    if not message_id:
        return False

    msg = await db.scalar(
        select(Message).where(Message.provider_message_id == message_id)
    )
    if msg is None:
        return False

    msg.delivery_status = parsed.ack.status
    await db.flush()
    return True


async def _find_student_by_phone(db, raw_phone: str) -> User | None:
    variants = phone_lookup_variants(raw_phone)
    if not variants:
        return None

    for variant in variants:
        user = await db.scalar(
            select(User).where(
                User.whatsapp == variant,
                User.role == Role.STUDENT,
                User.is_active.is_(True),
            )
        )
        if user is not None:
            return user
    return None


async def _latest_whatsapp_conversation(db, student_id: uuid.UUID) -> Conversation | None:
    stmt = (
        select(Conversation)
        .where(
            Conversation.user_id == student_id,
            Conversation.channel == ConversationChannel.WHATSAPP,
        )
        .options(selectinload(Conversation.messages))
        .order_by(Conversation.updated_at.desc())
        .limit(1)
    )
    return await db.scalar(stmt)


def _message_source(parsed: CinndiParseResult) -> MessageSource:
    if parsed.message is None:
        return MessageSource.WHATSAPP_TEXT
    msg_type = parsed.message.message_type.lower()
    if msg_type in {"audio", "ptt"}:
        return MessageSource.WHATSAPP_AUDIO
    return MessageSource.WHATSAPP_TEXT


async def _resolve_text(parsed: CinndiParseResult) -> str:
    if parsed.message is None:
        return ""

    msg = parsed.message
    body = (msg.body or msg.caption or "").strip()
    msg_type = msg.message_type.lower()

    if msg_type in {"chat", "button", "interactive"}:
        return body

    if msg_type not in {"audio", "ptt"}:
        return body

    audio_bytes: bytes | None = None
    filename = msg.media_filename or "audio.ogg"

    if msg.media_data:
        try:
            audio_bytes = base64.b64decode(msg.media_data)
        except Exception:  # noqa: BLE001
            audio_bytes = None

    if audio_bytes is None and msg.url_arquivo:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(msg.url_arquivo)
                response.raise_for_status()
                audio_bytes = response.content
        except Exception as exc:  # noqa: BLE001
            logger.warning("failed to download inbound audio: %s", exc)
            return body

    if not audio_bytes:
        return body

    try:
        return await transcribe_audio(audio_bytes, filename=filename)
    except Exception as exc:  # noqa: BLE001
        logger.warning("failed to transcribe inbound audio: %s", exc)
        return body


async def persist_inbound(db, parsed: CinndiParseResult) -> InboundResult:
    if not parsed.is_inbound_chat or parsed.message is None:
        return InboundResult(conversation_id=None, detail="ignored")

    message = parsed.message
    if not message.from_phone:
        return InboundResult(conversation_id=None, detail="missing_sender")

    if message.message_id:
        existing = await db.scalar(
            select(Message.id).where(Message.provider_message_id == message.message_id)
        )
        if existing is not None:
            return InboundResult(conversation_id=None, detail="duplicate")

    normalized = normalize_br_phone(message.from_phone)
    if normalized is None:
        return InboundResult(conversation_id=None, detail="invalid_phone")

    student = await _find_student_by_phone(db, message.from_phone)
    if student is None:
        logger.info("inbound whatsapp from unknown phone=%s", message.from_phone)
        return InboundResult(conversation_id=None, detail="unknown_student")

    conversation = await _latest_whatsapp_conversation(db, student.id)
    if conversation is None:
        return InboundResult(conversation_id=None, detail="no_conversation")

    text = await _resolve_text(parsed)
    if not text.strip():
        return InboundResult(conversation_id=None, detail="empty_message")

    await record_message(
        db,
        conversation,
        Author.STUDENT,
        text.strip(),
        provider_message_id=message.message_id or None,
        source=_message_source(parsed),
    )
    return InboundResult(conversation_id=conversation.id, detail="ok")
