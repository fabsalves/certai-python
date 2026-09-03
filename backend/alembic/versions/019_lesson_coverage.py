"""lesson coverage — what a teaching session actually covered, per lesson

Additive only, no backfill: sessions recorded before this migration have no
coverage rows, and every reader treats "no coverage" as the happy path (the
anchor lesson, fully covered).

Revision ID: 019_lesson_coverage
Revises: 018_organizations
Create Date: 2026-09-02
"""

from alembic import op
import sqlalchemy as sa

revision = "019_lesson_coverage"
down_revision = "018_organizations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lesson_coverage",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("note_id", sa.UUID(), nullable=False),
        sa.Column("cohort_id", sa.UUID(), nullable=False),
        sa.Column("lesson_id", sa.UUID(), nullable=False),
        sa.Column("module_professor_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("extent", sa.String(length=20), nullable=False),
        sa.Column("covered", sa.Text(), nullable=False, server_default=""),
        sa.Column("pending", sa.Text(), nullable=False, server_default=""),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="ai"),
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
        sa.ForeignKeyConstraint(
            ["note_id"], ["cohort_lesson_notes.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["cohort_id"], ["cohorts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lesson_id"], ["lessons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["module_professor_id"],
            ["cohort_module_professors.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_lesson_coverage_note_id"), "lesson_coverage", ["note_id"], unique=False
    )
    op.create_index(
        op.f("ix_lesson_coverage_cohort_id"),
        "lesson_coverage",
        ["cohort_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lesson_coverage_lesson_id"),
        "lesson_coverage",
        ["lesson_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lesson_coverage_module_professor_id"),
        "lesson_coverage",
        ["module_professor_id"],
        unique=False,
    )
    # Standing coverage of a lesson for one class = most recent row. This index
    # serves that lookup, which runs on the context and assessment hot paths.
    op.create_index(
        "ix_lesson_coverage_standing",
        "lesson_coverage",
        ["cohort_id", "module_professor_id", "lesson_id", sa.text("created_at DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_lesson_coverage_standing", table_name="lesson_coverage")
    op.drop_index(
        op.f("ix_lesson_coverage_module_professor_id"), table_name="lesson_coverage"
    )
    op.drop_index(op.f("ix_lesson_coverage_lesson_id"), table_name="lesson_coverage")
    op.drop_index(op.f("ix_lesson_coverage_cohort_id"), table_name="lesson_coverage")
    op.drop_index(op.f("ix_lesson_coverage_note_id"), table_name="lesson_coverage")
    op.drop_table("lesson_coverage")
