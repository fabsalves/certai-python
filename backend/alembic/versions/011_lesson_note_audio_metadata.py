"""lesson note audio filename and source metadata

Revision ID: 011_lesson_note_audio_metadata
Revises: 010_student_lesson_progress
Create Date: 2026-07-20
"""

from alembic import op
import sqlalchemy as sa

revision = "011_lesson_note_audio_metadata"
down_revision = "010_student_lesson_progress"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cohort_lesson_notes",
        sa.Column("audio_filename", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "cohort_lesson_notes",
        sa.Column("audio_source", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cohort_lesson_notes", "audio_source")
    op.drop_column("cohort_lesson_notes", "audio_filename")
