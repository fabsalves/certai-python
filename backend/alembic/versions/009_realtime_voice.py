"""realtime voice channel — source, idempotency_key, voice_sessions

Revision ID: 009_realtime_voice
Revises: 008_ai_ingestion
Create Date: 2026-07-13
"""

from alembic import op
import sqlalchemy as sa

revision = "009_realtime_voice"
down_revision = "008_ai_ingestion"
branch_labels = None
depends_on = None

# conversations.channel é varchar(20) no banco (migration 006, native_enum=False no ORM).
# Enum values minúsculos (student, realtime_voice, …) vêm do values_callable nos models.


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("source", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "messages",
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
    )
    op.create_index(
        op.f("ix_messages_idempotency_key"),
        "messages",
        ["idempotency_key"],
        unique=True,
    )

    op.execute(
        """
        UPDATE messages m
        SET source = CASE
            WHEN c.channel = 'whatsapp' THEN 'whatsapp_text'
            WHEN c.channel = 'in_app' THEN 'in_app_text'
            ELSE NULL
        END
        FROM conversations c
        WHERE m.conversation_id = c.id AND m.source IS NULL
        """
    )

    op.create_table(
        "voice_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="created"),
        sa.Column("lock_token", sa.String(length=64), nullable=False),
        sa.Column("lock_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_reason", sa.String(length=32), nullable=True),
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
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lock_token"),
    )
    op.create_index(
        op.f("ix_voice_sessions_conversation_id"),
        "voice_sessions",
        ["conversation_id"],
        unique=False,
    )

    # Uma VoiceSession ativa por conversation (plano §2.3).
    op.create_index(
        "uq_voice_sessions_active_conversation",
        "voice_sessions",
        ["conversation_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('created', 'active', 'reconnecting')"),
    )

    # Etapa F: job Celery de abandono varre status + last_heartbeat_at.
    op.create_index(
        "ix_voice_sessions_status_last_heartbeat_active",
        "voice_sessions",
        ["status", "last_heartbeat_at"],
        postgresql_where=sa.text("status IN ('active', 'reconnecting')"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_voice_sessions_status_last_heartbeat_active",
        table_name="voice_sessions",
    )
    op.drop_index(
        "uq_voice_sessions_active_conversation",
        table_name="voice_sessions",
    )
    op.drop_index(op.f("ix_voice_sessions_conversation_id"), table_name="voice_sessions")
    op.drop_table("voice_sessions")
    op.drop_index(op.f("ix_messages_idempotency_key"), table_name="messages")
    op.drop_column("messages", "idempotency_key")
    op.drop_column("messages", "source")
