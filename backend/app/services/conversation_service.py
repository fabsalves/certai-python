import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.context_builder import ContextBuilder
from app.ai.engine import respond
from app.ai.humanizer import humanize
from app.ai.tools import ToolContext
from app.models.conversation import Author, Conversation, ConversationScope, Message
from app.schemas import AgentResponse


async def student_lesson_message(
    db: AsyncSession,
    cohort_id: uuid.UUID,
    lesson_id: uuid.UUID,
    student_id: uuid.UUID,
    content: str,
) -> AgentResponse:
    """Persiste a mensagem do aluno e devolve a resposta da Lira."""
    conversation = await db.scalar(
        select(Conversation).where(
            Conversation.cohort_id == cohort_id,
            Conversation.user_id == student_id,
            Conversation.lesson_id == lesson_id,
        )
    )
    if conversation is None:
        conversation = Conversation(
            cohort_id=cohort_id,
            user_id=student_id,
            lesson_id=lesson_id,
            scope=ConversationScope.STUDENT_LESSON,
        )
        db.add(conversation)
        await db.flush()

    db.add(Message(conversation_id=conversation.id, author=Author.STUDENT, content=content))
    await db.flush()

    msgs = (
        await db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at)
        )
    ).all()
    history = [
        {"role": "user" if m.author == Author.STUDENT else "assistant", "content": m.content}
        for m in msgs
    ]

    bundle = await ContextBuilder(db).build_lesson(cohort_id, lesson_id)
    tool_ctx = ToolContext(db, cohort_id, student_id, lesson_id)

    raw = await respond(bundle, history, tool_ctx)
    final = await humanize(raw)

    db.add(Message(conversation_id=conversation.id, author=Author.AGENT, content=final))
    await db.flush()

    return AgentResponse(conversation_id=conversation.id, response=final)
