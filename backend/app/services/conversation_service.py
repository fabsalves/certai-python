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
    ConversationScope,
    Message,
    MessageSource,
)
from app.schemas import AgentResponse

logger = logging.getLogger(__name__)


def agent_source_for_entry(entry_source: MessageSource | None) -> MessageSource:
    if entry_source in (MessageSource.WHATSAPP_TEXT, MessageSource.WHATSAPP_AUDIO):
        return MessageSource.WHATSAPP_TEXT
    if entry_source == MessageSource.REALTIME_VOICE:
        return MessageSource.REALTIME_VOICE
    return MessageSource.IN_APP_TEXT


async def get_or_create_conversation(
    db: AsyncSession,
    cohort_id: uuid.UUID,
    user_id: uuid.UUID,
    lesson_id: uuid.UUID,
) -> Conversation:
    conversation = await db.scalar(
        select(Conversation).where(
            Conversation.cohort_id == cohort_id,
            Conversation.user_id == user_id,
            Conversation.lesson_id == lesson_id,
        )
    )
    if conversation is None:
        conversation = Conversation(
            cohort_id=cohort_id,
            user_id=user_id,
            lesson_id=lesson_id,
            scope=ConversationScope.STUDENT_LESSON,
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
    source: MessageSource | None = None,
    idempotency_key: str | None = None,
) -> tuple[Message, bool]:
    """Persiste mensagem. Retorna (message, created) — created=False se idempotency_key duplicada."""
    if idempotency_key:
        existing = await db.scalar(
            select(Message).where(Message.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return existing, False

    message = Message(
        conversation_id=conversation.id,
        author=author,
        content=content,
        provider_message_id=provider_message_id,
        delivery_status=delivery_status,
        source=source,
        idempotency_key=idempotency_key,
    )
    db.add(message)
    await db.flush()

    if author == Author.STUDENT and conversation.lesson_id is not None:
        from app.services.student_progress_service import StudentProgressService

        await StudentProgressService.activate_on_first_interaction(
            db,
            conversation.cohort_id,
            conversation.user_id,
            conversation.lesson_id,
        )

    return message, True


async def list_lesson_messages(
    db: AsyncSession,
    cohort_id: uuid.UUID,
    student_id: uuid.UUID,
    lesson_id: uuid.UUID,
) -> list[Message]:
    """All messages for a student in a lesson (unified conversation, mixed sources)."""
    conversation = await db.scalar(
        select(Conversation).where(
            Conversation.cohort_id == cohort_id,
            Conversation.user_id == student_id,
            Conversation.lesson_id == lesson_id,
        )
    )
    if conversation is None:
        return []
    return (
        await db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at)
        )
    ).all()


async def lesson_conversation_history(
    db: AsyncSession,
    cohort_id: uuid.UUID,
    student_id: uuid.UUID,
    lesson_id: uuid.UUID,
) -> list[dict]:
    """Conversation history for the AI — single unified conversation per lesson."""
    conversation = await db.scalar(
        select(Conversation).where(
            Conversation.cohort_id == cohort_id,
            Conversation.user_id == student_id,
            Conversation.lesson_id == lesson_id,
        )
    )
    if conversation is None:
        return []
    return await conversation_history(conversation.id, db)


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
    *,
    entry_source: MessageSource = MessageSource.IN_APP_TEXT,
) -> str:
    history = await conversation_history(conversation.id, db)
    bundle = await ContextBuilder(db).build_lesson(cohort_id, lesson_id)
    tool_ctx = ToolContext(
        db,
        cohort_id,
        student_id,
        lesson_id,
        conversation_id=conversation.id,
        entry_source=entry_source,
    )

    raw = await respond(bundle, history, tool_ctx)
    final = await humanize(raw)

    await record_message(
        db,
        conversation,
        Author.AGENT,
        final,
        source=agent_source_for_entry(entry_source),
    )
    return final


async def student_lesson_message(
    db: AsyncSession,
    cohort_id: uuid.UUID,
    lesson_id: uuid.UUID,
    student_id: uuid.UUID,
    content: str,
) -> AgentResponse:
    """Persiste a mensagem do aluno e devolve a resposta da Lira."""
    from app.services.student_progress_service import (
        LessonNotInteractiveError,
        StudentProgressService,
    )

    if not await StudentProgressService.is_lesson_interactive_for(
        db, cohort_id, student_id, lesson_id
    ):
        row = await StudentProgressService._get_progress(
            db, cohort_id, student_id, lesson_id
        )
        raise LessonNotInteractiveError(
            "lesson_closed" if row is not None else "no_active_lesson"
        )

    conversation = await get_or_create_conversation(db, cohort_id, student_id, lesson_id)
    await record_message(
        db, conversation, Author.STUDENT, content, source=MessageSource.IN_APP_TEXT
    )
    final = await generate_lesson_reply(
        db,
        conversation,
        cohort_id,
        lesson_id,
        student_id,
        entry_source=MessageSource.IN_APP_TEXT,
    )
    return AgentResponse(conversation_id=conversation.id, response=final)
