"""lesson content source file (audio/doc import)

Revision ID: 014_lesson_content_source
Revises: 013_module_classes
Create Date: 2026-08-06
"""

from alembic import op
import sqlalchemy as sa

revision = "014_lesson_content_source"
down_revision = "013_module_classes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "lessons",
        sa.Column("content_source_storage_key", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "lessons",
        sa.Column("content_source_filename", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "lessons",
        sa.Column("content_source_content_type", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "lessons",
        sa.Column("content_source_kind", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("lessons", "content_source_kind")
    op.drop_column("lessons", "content_source_content_type")
    op.drop_column("lessons", "content_source_filename")
    op.drop_column("lessons", "content_source_storage_key")
