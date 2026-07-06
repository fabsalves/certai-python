import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.context_builder import ContextBuilder
from app.ai.engine import respond
from app.ai.humanizer import humanize
from app.ai.tools import ToolContext
from app.models.conversation import (
    Author,
    Conversation,
    ConversationChannel,
    ConversationScope,
    Message,
)
from app.schemas import AgentResponse

logger = logging.getLogger(__name__)


async def get_or_create_conversation(
    db: AsyncSession,
    cohort_id: uuid.UUID,
    user_id: uuid.UUID,
    lesson_id: uuid.UUID,
    *,
    channel: ConversationChannel = ConversationChannel.IN_APP,
) -> Conversation:
    conversation = await db.scalar(
        select(Conversation).where(
            Conversation.cohort_id == cohort_id,
            Conversation.user_id == user_id,
            Conversation.lesson_id == lesson_id,
            Conversation.channel == channel,
        )
    )
    if conversation is None:
        conversation = Conversation(
            cohort_id=cohort_id,
            user_id=user_id,
            lesson_id=lesson_id,
            scope=ConversationScope.STUDENT_LESSON,
            channel=channel,
        )
        db.add(conversation)
        await db.flush()
    return conversation


async def record_message(
    db: AsyncSession,
    conversation: Conversation,
    author: Author,
    content: str,
    *,
    provider_message_id: str | None = None,
    delivery_status: str | None = None,
) -> Message:
    message = Message(
        conversation_id=conversation.id,
        author=author,
        content=content,
        provider_message_id=provider_message_id,
        delivery_status=delivery_status,
    )
    db.add(message)
    await db.flush()
    return message


async def conversation_history(conversation_id: uuid.UUID, db: AsyncSession) -> list[dict]:
    msgs = (
        await db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
    ).all()
    return [
        {"role": "user" if m.author == Author.STUDENT else "assistant", "content": m.content}
        for m in msgs
    ]


async def generate_lesson_reply(
    db: AsyncSession,
    conversation: Conversation,
    cohort_id: uuid.UUID,
    lesson_id: uuid.UUID,
    student_id: uuid.UUID,
) -> str:
    history = await conversation_history(conversation.id, db)
    bundle = await ContextBuilder(db).build_lesson(cohort_id, lesson_id)
    tool_ctx = ToolContext(db, cohort_id, student_id, lesson_id)

    raw = await respond(bundle, history, tool_ctx)
    final = await humanize(raw)

    await record_message(db, conversation, Author.AGENT, final)
    return final


async def student_lesson_message(
    db: AsyncSession,
    cohort_id: uuid.UUID,
    lesson_id: uuid.UUID,
    student_id: uuid.UUID,
    content: str,
) -> AgentResponse:
    """Persiste a mensagem do aluno e devolve a resposta da Lira."""
    conversation = await get_or_create_conversation(
        db, cohort_id, student_id, lesson_id, channel=ConversationChannel.IN_APP
    )
    await record_message(db, conversation, Author.STUDENT, content)
    final = await generate_lesson_reply(db, conversation, cohort_id, lesson_id, student_id)
    return AgentResponse(conversation_id=conversation.id, response=final)
