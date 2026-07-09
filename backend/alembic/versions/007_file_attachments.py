"""track material and lesson note attachments

Revision ID: 007_file_attachments
Revises: 006_whatsapp
Create Date: 2026-07-09
"""

from alembic import op
import sqlalchemy as sa

revision = "007_file_attachments"
down_revision = "006_whatsapp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tracks", sa.Column("material_storage_key", sa.String(length=512), nullable=True))
    op.add_column("tracks", sa.Column("material_filename", sa.String(length=255), nullable=True))
    op.add_column("tracks", sa.Column("material_content_type", sa.String(length=128), nullable=True))

    op.add_column(
        "cohort_lesson_notes",
        sa.Column("attachment_storage_key", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "cohort_lesson_notes",
        sa.Column("attachment_filename", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "cohort_lesson_notes",
        sa.Column("attachment_content_type", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "cohort_lesson_notes",
        sa.Column("audio_storage_key", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "cohort_lesson_notes",
        sa.Column("audio_content_type", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cohort_lesson_notes", "audio_content_type")
    op.drop_column("cohort_lesson_notes", "audio_storage_key")
    op.drop_column("cohort_lesson_notes", "attachment_content_type")
    op.drop_column("cohort_lesson_notes", "attachment_filename")
    op.drop_column("cohort_lesson_notes", "attachment_storage_key")
    op.drop_column("tracks", "material_content_type")
    op.drop_column("tracks", "material_filename")
    op.drop_column("tracks", "material_storage_key")
