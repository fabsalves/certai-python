import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Author(str, enum.Enum):
    STUDENT = "student"
    AGENT = "agent"
    PROFESSOR = "professor"


class ConversationScope(str, enum.Enum):
    STUDENT_LESSON = "student_lesson"            # student talking inside a lesson
    PROFESSOR_COMPLETION = "professor_completion"  # professor completing a lesson


class ConversationChannel(str, enum.Enum):
    IN_APP = "in_app"
    WHATSAPP = "whatsapp"


class Conversation(Base):
    """Conversation session. Always tied to a cohort (segregation)."""

    __tablename__ = "conversations"

    cohort_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cohorts.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    lesson_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lessons.id", ondelete="SET NULL"), nullable=True
    )
    scope: Mapped[ConversationScope] = mapped_column(
        Enum(ConversationScope, native_enum=False, length=30)
    )
    channel: Mapped[ConversationChannel] = mapped_column(
        Enum(ConversationChannel, native_enum=False, length=20),
        default=ConversationChannel.IN_APP,
        nullable=False,
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", order_by="Message.created_at", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    author: Mapped[Author] = mapped_column(Enum(Author, native_enum=False, length=20))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(
        String(255), unique=True, index=True, nullable=True
    )
    delivery_status: Mapped[str | None] = mapped_column(String(32), nullable=True)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
