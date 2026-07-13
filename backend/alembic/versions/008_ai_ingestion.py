"""AI ingestion of track material and lesson note attachments

Revision ID: 008_ai_ingestion
Revises: 007_file_attachments
Create Date: 2026-07-12
"""

from alembic import op
import sqlalchemy as sa

revision = "008_ai_ingestion"
down_revision = "007_file_attachments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tracks",
        sa.Column("material_extracted_text", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "tracks",
        sa.Column("material_guide", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "tracks",
        sa.Column("material_ingestion_status", sa.String(length=20), nullable=True),
    )

    op.add_column(
        "cohort_lesson_notes",
        sa.Column("attachment_extracted_text", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "cohort_lesson_notes",
        sa.Column("attachment_knowledge_base", sa.Text(), nullable=False, server_default=""),
    )
    # Legacy notes were consolidated synchronously (and already dispatched): done.
    op.add_column(
        "cohort_lesson_notes",
        sa.Column(
            "ingestion_status", sa.String(length=20), nullable=False, server_default="done"
        ),
    )


def downgrade() -> None:
    op.drop_column("cohort_lesson_notes", "ingestion_status")
    op.drop_column("cohort_lesson_notes", "attachment_knowledge_base")
    op.drop_column("cohort_lesson_notes", "attachment_extracted_text")
    op.drop_column("tracks", "material_ingestion_status")
    op.drop_column("tracks", "material_guide")
    op.drop_column("tracks", "material_extracted_text")
