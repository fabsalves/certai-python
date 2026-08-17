"""module description + source file (audio/doc import)

Revision ID: 016_module_description
Revises: 015_track_description_source
Create Date: 2026-08-17
"""

from alembic import op
import sqlalchemy as sa

revision = "016_module_description"
down_revision = "015_track_description_source"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("modules", sa.Column("description", sa.Text(), nullable=False, server_default=""))
    op.add_column(
        "modules",
        sa.Column("description_source_storage_key", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "modules",
        sa.Column("description_source_filename", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "modules",
        sa.Column("description_source_content_type", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "modules",
        sa.Column("description_source_kind", sa.String(length=20), nullable=True),
    )
    op.alter_column("modules", "description", server_default=None)


def downgrade() -> None:
    op.drop_column("modules", "description_source_kind")
    op.drop_column("modules", "description_source_content_type")
    op.drop_column("modules", "description_source_filename")
    op.drop_column("modules", "description_source_storage_key")
    op.drop_column("modules", "description")
