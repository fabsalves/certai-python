import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.conversation import _enum_values


class Level(str, enum.Enum):
    """Qualitative assessment, in place of a numeric grade."""

    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AssessmentScope(str, enum.Enum):
    """Scope of a consolidated student assessment."""

    LESSON = "lesson"
    MODULE = "module"
    TRACK = "track"


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


class StudentAssessment(Base):
    """Consolidated qualitative assessment of a student's understanding at a scope
    (lesson, module, or track). Append-only: readers take the latest row."""

    __tablename__ = "student_assessments"

    cohort_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cohorts.id", ondelete="CASCADE"), index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    scope: Mapped[AssessmentScope] = mapped_column(
        Enum(
            AssessmentScope,
            values_callable=_enum_values,
            native_enum=False,
            length=20,
        ),
        nullable=False,
    )
    # Exactly one of lesson_id / module_id / track_id is set, matching scope.
    # Enforced in the service layer, not via DB constraint.
    lesson_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lessons.id", ondelete="CASCADE"), nullable=True
    )
    module_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("modules.id", ondelete="CASCADE"), nullable=True
    )
    track_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tracks.id", ondelete="CASCADE"), nullable=True
    )
    # Null = insufficient evidence to assign a level (valid outcome).
    level: Mapped[Level | None] = mapped_column(
        Enum(Level, native_enum=False, length=20), nullable=True
    )
    assessment: Mapped[str] = mapped_column(Text, default="")
    gaps: Mapped[str] = mapped_column(Text, default="")


class CohortLessonNote(Base):
    """Notes about a lesson as taught by one professor to their class.
    Consolidated by the AI at completion. Tied to the class that studied it --
    never to the lesson content (which is immutable)."""

    __tablename__ = "cohort_lesson_notes"

    cohort_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cohorts.id", ondelete="CASCADE"), index=True
    )
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lessons.id", ondelete="CASCADE"), index=True
    )
    module_professor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cohort_module_professors.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
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


class CoverageKind(str, enum.Enum):
    """Where a covered segment sits relative to the session's anchor lesson."""

    PLANNED = "planned"      # the anchor lesson itself
    CARRYOVER = "carryover"  # tail of an earlier lesson, closed in this session
    ADVANCE = "advance"      # content of a later lesson, taught ahead of plan


class CoverageExtent(str, enum.Enum):
    FULL = "full"
    PARTIAL = "partial"


class LessonCoverage(Base):
    """What one teaching session actually covered, per lesson.

    A session (one CohortLessonNote) keeps its anchor lesson, and declares here
    the real shape of what was taught: the anchor itself, the tail of an earlier
    lesson, content of a later one -- or all three.

    Append-only, like StudentAssessment: the standing coverage of a lesson is the
    most recent row for that class. A later session that covers a pending tail
    writes a new row with an empty `pending`, so pendency resolves with no UPDATE
    and no parallel state machine.
    """

    __tablename__ = "lesson_coverage"

    note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cohort_lesson_notes.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # cohort_id and module_professor_id are denormalized from the note on purpose:
    # standing-pendency lookups are per teaching class and run on the hot path of
    # both context assembly and assessment.
    cohort_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cohorts.id", ondelete="CASCADE"), index=True
    )
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lessons.id", ondelete="CASCADE"), index=True
    )
    module_professor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cohort_module_professors.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    kind: Mapped[CoverageKind] = mapped_column(
        Enum(CoverageKind, values_callable=_enum_values, native_enum=False, length=20),
        nullable=False,
    )
    extent: Mapped[CoverageExtent] = mapped_column(
        Enum(CoverageExtent, values_callable=_enum_values, native_enum=False, length=20),
        nullable=False,
    )
    covered: Mapped[str] = mapped_column(Text, default="")  # what was taught, pt-BR
    pending: Mapped[str] = mapped_column(Text, default="")  # what this lesson still owes
    # "ai" = proposal accepted as-is | "professor" = adjusted before submitting.
    source: Mapped[str] = mapped_column(String(20), default="ai", nullable=False)
