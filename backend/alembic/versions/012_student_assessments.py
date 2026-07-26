"""student assessments — layered evaluation persistence

Revision ID: 012_student_assessments
Revises: 011_lesson_note_audio_metadata
Create Date: 2026-07-26
"""

from alembic import op
import sqlalchemy as sa

revision = "012_student_assessments"
down_revision = "011_lesson_note_audio_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "student_assessments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("cohort_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column("lesson_id", sa.UUID(), nullable=True),
        sa.Column("module_id", sa.UUID(), nullable=True),
        sa.Column("track_id", sa.UUID(), nullable=True),
        sa.Column("level", sa.String(length=20), nullable=True),
        sa.Column("assessment", sa.Text(), nullable=False, server_default=""),
        sa.Column("gaps", sa.Text(), nullable=False, server_default=""),
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
        sa.ForeignKeyConstraint(["lesson_id"], ["lessons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["module_id"], ["modules.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["track_id"], ["tracks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_student_assessments_cohort_id"),
        "student_assessments",
        ["cohort_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_student_assessments_student_id"),
        "student_assessments",
        ["student_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_student_assessments_student_id"), table_name="student_assessments"
    )
    op.drop_index(
        op.f("ix_student_assessments_cohort_id"), table_name="student_assessments"
    )
    op.drop_table("student_assessments")
