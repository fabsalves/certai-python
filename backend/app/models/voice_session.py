import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.conversation import _enum_values


class VoiceSessionStatus(str, enum.Enum):
    CREATED = "created"
    ACTIVE = "active"
    RECONNECTING = "reconnecting"
    ENDED = "ended"
    ABANDONED = "abandoned"


class VoiceSession(Base):
    """Lifecycle de uma chamada de voz Realtime."""

    __tablename__ = "voice_sessions"
    __table_args__ = (
        Index(
            "uq_voice_sessions_active_conversation",
            "conversation_id",
            unique=True,
            postgresql_where=text("status IN ('created', 'active', 'reconnecting')"),
        ),
        Index(
            "ix_voice_sessions_status_last_heartbeat_active",
            "status",
            "last_heartbeat_at",
            postgresql_where=text("status IN ('active', 'reconnecting')"),
        ),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[VoiceSessionStatus] = mapped_column(
        Enum(VoiceSessionStatus, values_callable=_enum_values, native_enum=False, length=20),
        default=VoiceSessionStatus.CREATED,
        server_default="created",
        nullable=False,
    )
    lock_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    lock_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)

    conversation: Mapped["Conversation"] = relationship(back_populates="voice_sessions")
