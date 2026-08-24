"""LLM usage metering.

One row per *cost line*, not per API call: a single `response.done` from the
Realtime API expands into several rows (fresh audio in, cached audio in, audio
out, text out, ...). Prices differ ~8x between text and audio and ~80x between
fresh and cached audio, so collapsing them into a single `input_tokens` column
would destroy the only information that matters.

Cost is estimated and frozen at ingest. Updating the rate card does not rewrite
history; `raw` keeps the provider payload so a re-pricing pass is always possible.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AiUsageEvent(Base):
    """One priced usage line from an LLM provider event.

    Idempotency is (provider, provider_event_id, cost_kind): the browser may
    relay the same `response.done` twice, and a repeat is a silent no-op.
    """

    __tablename__ = "ai_usage_events"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_event_id",
            "cost_kind",
            name="uq_ai_usage_events_provider_event_kind",
        ),
        Index("ix_ai_usage_events_cohort_occurred", "cohort_id", "occurred_at"),
        Index(
            "ix_ai_usage_events_cohort_student_lesson",
            "cohort_id",
            "student_id",
            "lesson_id",
        ),
        Index("ix_ai_usage_events_kind", "provider", "cost_kind"),
    )

    # Nullable because track-material ingestion belongs to a Track, which serves
    # many cohorts. Those rows are real spend with no cohort to charge: the read
    # side surfaces them as unattributed overhead instead of dropping them.
    cohort_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cohorts.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    # Null on cohort- or track-wide work, which is not attributable to one student.
    student_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    lesson_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lessons.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    # The model the API actually reported, never the one from settings.
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    operation: Mapped[str] = mapped_column(String(60), nullable=False)
    cost_kind: Mapped[str] = mapped_column(String(60), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="tokens")
    # NULL means "no known rate for this model/kind" -- never 0, which would make
    # an unpriced model look free.
    estimated_cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6), nullable=True
    )
    provider_event_id: Mapped[str] = mapped_column(String(120), nullable=False)
    raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
