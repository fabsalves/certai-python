"""student lesson progress + unified conversation

Revision ID: 010_student_lesson_progress
Revises: 009_realtime_voice
Create Date: 2026-07-15
"""

from alembic import op
import sqlalchemy as sa

revision = "010_student_lesson_progress"
down_revision = "009_realtime_voice"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "student_lesson_progress",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("cohort_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("lesson_id", sa.UUID(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default="disparada",
        ),
        sa.Column(
            "disparada_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("concluded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("encerrada_por_avanco_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["lesson_id"], ["lessons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "cohort_id", "student_id", "lesson_id", name="uq_student_lesson_progress"
        ),
    )
    op.create_index(
        op.f("ix_student_lesson_progress_cohort_id"),
        "student_lesson_progress",
        ["cohort_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_student_lesson_progress_lesson_id"),
        "student_lesson_progress",
        ["lesson_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_student_lesson_progress_student_id"),
        "student_lesson_progress",
        ["student_id"],
        unique=False,
    )

    op.drop_column("conversations", "channel")

    op.create_unique_constraint(
        "uq_conversation_cohort_user_lesson",
        "conversations",
        ["cohort_id", "user_id", "lesson_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_conversation_cohort_user_lesson", "conversations", type_="unique"
    )
    op.add_column(
        "conversations",
        sa.Column(
            "channel",
            sa.String(length=20),
            nullable=False,
            server_default="in_app",
        ),
    )
    op.drop_index(
        op.f("ix_student_lesson_progress_student_id"), table_name="student_lesson_progress"
    )
    op.drop_index(
        op.f("ix_student_lesson_progress_lesson_id"), table_name="student_lesson_progress"
    )
    op.drop_index(
        op.f("ix_student_lesson_progress_cohort_id"), table_name="student_lesson_progress"
    )
    op.drop_table("student_lesson_progress")
