"""track description source file (audio/doc import)

Revision ID: 015_track_description_source
Revises: 014_lesson_content_source
Create Date: 2026-08-06
"""

from alembic import op
import sqlalchemy as sa

revision = "015_track_description_source"
down_revision = "014_lesson_content_source"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tracks",
        sa.Column("description_source_storage_key", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "tracks",
        sa.Column("description_source_filename", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "tracks",
        sa.Column("description_source_content_type", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "tracks",
        sa.Column("description_source_kind", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tracks", "description_source_kind")
    op.drop_column("tracks", "description_source_content_type")
    op.drop_column("tracks", "description_source_filename")
    op.drop_column("tracks", "description_source_storage_key")
