import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Level(str, enum.Enum):
    """Qualitative assessment, in place of a numeric grade."""

    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class MicroScore(Base):
    """Point-in-time understanding record. Written by the AI via tool when there is
    enough signal in the conversation -- not on every interaction."""

    __tablename__ = "micro_scores"

    cohort_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cohorts.id", ondelete="CASCADE"), index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    lesson_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lessons.id", ondelete="SET NULL"), nullable=True
    )
    competency: Mapped[str] = mapped_column(String(255), default="")
    level: Mapped[Level] = mapped_column(Enum(Level, native_enum=False, length=20))
    evidence: Mapped[str] = mapped_column(Text, default="")  # why the AI assigned this level


class CohortLessonNote(Base):
    """Notes about a specific cohort's lesson. Consolidated by the AI at completion.
    Tied to cohort+lesson -- never to the lesson content (which is immutable)."""

    __tablename__ = "cohort_lesson_notes"

    cohort_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cohorts.id", ondelete="CASCADE"), index=True
    )
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lessons.id", ondelete="CASCADE"), index=True
    )
    summary: Mapped[str] = mapped_column(Text, default="")            # AI consolidation
    unclear_points: Mapped[str] = mapped_column(Text, default="")
    professor_transcript: Mapped[str] = mapped_column(Text, default="")  # transcribed audio
    attachment_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    attachment_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attachment_content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    attachment_extracted_text: Mapped[str] = mapped_column(Text, default="")  # raw attachment text
    attachment_knowledge_base: Mapped[str] = mapped_column(Text, default="")  # AI consolidation
    audio_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    audio_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    audio_content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # "recording" | "file" — how the professor provided the audio for the report.
    audio_source: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # pending -> processing -> done | failed. Dispatch to students only after done.
    ingestion_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
