"""whatsapp integration fields

Revision ID: 006_whatsapp
Revises: 005_normalize_user_emails
Create Date: 2026-07-05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "006_whatsapp"
down_revision = "005_normalize_user_emails"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("whatsapp", sa.String(length=20), nullable=True))
    op.create_index(op.f("ix_users_whatsapp"), "users", ["whatsapp"], unique=True)

    op.add_column(
        "conversations",
        sa.Column(
            "channel",
            sa.String(length=20),
            nullable=False,
            server_default="in_app",
        ),
    )

    op.add_column(
        "messages",
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "messages",
        sa.Column("delivery_status", sa.String(length=32), nullable=True),
    )
    op.create_index(
        op.f("ix_messages_provider_message_id"),
        "messages",
        ["provider_message_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_messages_provider_message_id"), table_name="messages")
    op.drop_column("messages", "delivery_status")
    op.drop_column("messages", "provider_message_id")
    op.drop_column("conversations", "channel")
    op.drop_index(op.f("ix_users_whatsapp"), table_name="users")
    op.drop_column("users", "whatsapp")
