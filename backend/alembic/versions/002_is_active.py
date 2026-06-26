"""add is_active to tracks, modules, lessons

Revision ID: 002_is_active
Revises:
Create Date: 2026-06-26
"""

from alembic import op
import sqlalchemy as sa

revision = "002_is_active"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tracks", sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("modules", sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("lessons", sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"))


def downgrade() -> None:
    op.drop_column("lessons", "is_active")
    op.drop_column("modules", "is_active")
    op.drop_column("tracks", "is_active")
