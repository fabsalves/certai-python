"""ai usage events — LLM spend attribution per cohort/student/lesson

Revision ID: 017_ai_usage_events
Revises: 016_module_description
Create Date: 2026-08-20
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "017_ai_usage_events"
down_revision = "016_module_description"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_usage_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("cohort_id", sa.UUID(), nullable=True),
        sa.Column("student_id", sa.UUID(), nullable=True),
        sa.Column("lesson_id", sa.UUID(), nullable=True),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("operation", sa.String(length=60), nullable=False),
        sa.Column("cost_kind", sa.String(length=60), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=False, server_default="tokens"),
        sa.Column("estimated_cost_usd", sa.Numeric(12, 6), nullable=True),
        sa.Column("provider_event_id", sa.String(length=120), nullable=False),
        sa.Column("raw", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["cohort_id"], ["cohorts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lesson_id"], ["lessons.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "provider_event_id",
            "cost_kind",
            name="uq_ai_usage_events_provider_event_kind",
        ),
    )
    op.create_index(
        "ix_ai_usage_events_cohort_id", "ai_usage_events", ["cohort_id"]
    )
    op.create_index(
        "ix_ai_usage_events_student_id", "ai_usage_events", ["student_id"]
    )
    op.create_index(
        "ix_ai_usage_events_lesson_id", "ai_usage_events", ["lesson_id"]
    )
    op.create_index(
        "ix_ai_usage_events_cohort_occurred",
        "ai_usage_events",
        ["cohort_id", "occurred_at"],
    )
    op.create_index(
        "ix_ai_usage_events_cohort_student_lesson",
        "ai_usage_events",
        ["cohort_id", "student_id", "lesson_id"],
    )
    op.create_index(
        "ix_ai_usage_events_kind", "ai_usage_events", ["provider", "cost_kind"]
    )


def downgrade() -> None:
    op.drop_index("ix_ai_usage_events_kind", table_name="ai_usage_events")
    op.drop_index(
        "ix_ai_usage_events_cohort_student_lesson", table_name="ai_usage_events"
    )
    op.drop_index("ix_ai_usage_events_cohort_occurred", table_name="ai_usage_events")
    op.drop_index("ix_ai_usage_events_lesson_id", table_name="ai_usage_events")
    op.drop_index("ix_ai_usage_events_student_id", table_name="ai_usage_events")
    op.drop_index("ix_ai_usage_events_cohort_id", table_name="ai_usage_events")
    op.drop_table("ai_usage_events")
