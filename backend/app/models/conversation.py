import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String, Text, UniqueConstraint
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


class MessageSource(str, enum.Enum):
    WHATSAPP_TEXT = "whatsapp_text"
    WHATSAPP_AUDIO = "whatsapp_audio"
    REALTIME_VOICE = "realtime_voice"
    IN_APP_TEXT = "in_app_text"


def _enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    """Persist enum .value (snake_case) — alinhado ao plano e à migration 009."""
    return [member.value for member in enum_cls]


class Conversation(Base):
    """Conversation session. Always tied to a cohort (segregation)."""

    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint(
            "cohort_id", "user_id", "lesson_id", name="uq_conversation_cohort_user_lesson"
        ),
    )

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
        Enum(ConversationScope, values_callable=_enum_values, native_enum=False, length=30)
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", order_by="Message.created_at", cascade="all, delete-orphan"
    )
    voice_sessions: Mapped[list["VoiceSession"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    author: Mapped[Author] = mapped_column(
        Enum(Author, values_callable=_enum_values, native_enum=False, length=20)
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(
        String(255), unique=True, index=True, nullable=True
    )
    delivery_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source: Mapped[MessageSource | None] = mapped_column(
        Enum(MessageSource, values_callable=_enum_values, native_enum=False, length=20),
        nullable=True,
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(255), unique=True, index=True, nullable=True
    )

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
