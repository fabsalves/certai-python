"""several professors per module, each with their own class of students

Revision ID: 013_module_classes
Revises: 012_student_assessments
Create Date: 2026-08-04
"""

from alembic import op
import sqlalchemy as sa

revision = "013_module_classes"
down_revision = "012_student_assessments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_cohort_module_professor", "cohort_module_professors", type_="unique"
    )
    op.create_unique_constraint(
        "uq_cohort_module_professor",
        "cohort_module_professors",
        ["cohort_id", "module_id", "professor_id"],
    )

    op.create_table(
        "cohort_module_students",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("module_professor_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
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
            ["module_professor_id"],
            ["cohort_module_professors.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "module_professor_id", "student_id", name="uq_cohort_module_student"
        ),
    )
    op.create_index(
        op.f("ix_cohort_module_students_module_professor_id"),
        "cohort_module_students",
        ["module_professor_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cohort_module_students_student_id"),
        "cohort_module_students",
        ["student_id"],
        unique=False,
    )

    # Existing rows had exactly one professor per module (the constraint dropped
    # above guaranteed it), so the class is unambiguous.
    op.add_column(
        "cohort_progress", sa.Column("module_professor_id", sa.UUID(), nullable=True)
    )
    op.execute(
        """
        UPDATE cohort_progress p
        SET module_professor_id = cmp.id
        FROM lessons l
        JOIN cohort_module_professors cmp ON cmp.module_id = l.module_id
        WHERE l.id = p.lesson_id AND cmp.cohort_id = p.cohort_id
        """
    )
    op.execute("DELETE FROM cohort_progress WHERE module_professor_id IS NULL")
    op.alter_column("cohort_progress", "module_professor_id", nullable=False)
    op.create_index(
        op.f("ix_cohort_progress_module_professor_id"),
        "cohort_progress",
        ["module_professor_id"],
        unique=False,
    )
    op.create_foreign_key(
        "cohort_progress_module_professor_id_fkey",
        "cohort_progress",
        "cohort_module_professors",
        ["module_professor_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint("uq_progress", "cohort_progress", type_="unique")
    op.create_unique_constraint(
        "uq_progress",
        "cohort_progress",
        ["cohort_id", "lesson_id", "module_professor_id"],
    )

    op.add_column(
        "cohort_lesson_notes",
        sa.Column("module_professor_id", sa.UUID(), nullable=True),
    )
    op.execute(
        """
        UPDATE cohort_lesson_notes n
        SET module_professor_id = cmp.id
        FROM lessons l
        JOIN cohort_module_professors cmp ON cmp.module_id = l.module_id
        WHERE l.id = n.lesson_id AND cmp.cohort_id = n.cohort_id
        """
    )
    op.execute("DELETE FROM cohort_lesson_notes WHERE module_professor_id IS NULL")
    op.alter_column("cohort_lesson_notes", "module_professor_id", nullable=False)
    op.create_index(
        op.f("ix_cohort_lesson_notes_module_professor_id"),
        "cohort_lesson_notes",
        ["module_professor_id"],
        unique=False,
    )
    op.create_foreign_key(
        "cohort_lesson_notes_module_professor_id_fkey",
        "cohort_lesson_notes",
        "cohort_module_professors",
        ["module_professor_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "cohort_lesson_notes_module_professor_id_fkey",
        "cohort_lesson_notes",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_cohort_lesson_notes_module_professor_id"),
        table_name="cohort_lesson_notes",
    )
    op.drop_column("cohort_lesson_notes", "module_professor_id")

    op.drop_constraint("uq_progress", "cohort_progress", type_="unique")
    op.drop_constraint(
        "cohort_progress_module_professor_id_fkey",
        "cohort_progress",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_cohort_progress_module_professor_id"), table_name="cohort_progress"
    )
    op.drop_column("cohort_progress", "module_professor_id")
    op.create_unique_constraint(
        "uq_progress", "cohort_progress", ["cohort_id", "lesson_id"]
    )

    op.drop_index(
        op.f("ix_cohort_module_students_student_id"),
        table_name="cohort_module_students",
    )
    op.drop_index(
        op.f("ix_cohort_module_students_module_professor_id"),
        table_name="cohort_module_students",
    )
    op.drop_table("cohort_module_students")

    op.drop_constraint(
        "uq_cohort_module_professor", "cohort_module_professors", type_="unique"
    )
    op.create_unique_constraint(
        "uq_cohort_module_professor",
        "cohort_module_professors",
        ["cohort_id", "module_id"],
    )
