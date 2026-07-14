"""Meta WhatsApp 24h session window detection."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Author, Conversation, ConversationChannel, Message

SESSION_WINDOW_HOURS = 24


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def is_session_window_open(db: AsyncSession, student_id: uuid.UUID) -> bool:
    """True when the student sent a WhatsApp message within the last 24 hours.

    Returns False when the student has never sent a WhatsApp message (NULL MAX);
    Meta window is closed and only template messages are allowed.
    """
    last_student_at = await db.scalar(
        select(func.max(Message.created_at))
        .select_from(Message)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            Conversation.user_id == student_id,
            Conversation.channel == ConversationChannel.WHATSAPP,
            Message.author == Author.STUDENT,
        )
    )
    if last_student_at is None:
        return False

    if last_student_at.tzinfo is None:
        last_student_at = last_student_at.replace(tzinfo=timezone.utc)

    return (_utcnow() - last_student_at) < timedelta(hours=SESSION_WINDOW_HOURS)
