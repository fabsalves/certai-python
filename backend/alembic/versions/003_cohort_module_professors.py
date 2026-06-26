"""assign professors per module within cohort

Revision ID: 003_cohort_module_professors
Revises: 002_is_active
Create Date: 2026-06-26
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "003_cohort_module_professors"
down_revision = "002_is_active"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cohort_module_professors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("cohort_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("module_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("professor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["cohort_id"], ["cohorts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["module_id"], ["modules.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["professor_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cohort_id", "module_id", name="uq_cohort_module_professor"),
    )
    op.create_index(
        op.f("ix_cohort_module_professors_cohort_id"),
        "cohort_module_professors",
        ["cohort_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cohort_module_professors_module_id"),
        "cohort_module_professors",
        ["module_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cohort_module_professors_professor_id"),
        "cohort_module_professors",
        ["professor_id"],
        unique=False,
    )

    op.execute(
        """
        INSERT INTO cohort_module_professors (id, cohort_id, module_id, professor_id)
        SELECT gen_random_uuid(), c.id, m.id, c.professor_id
        FROM cohorts c
        JOIN modules m ON m.track_id = c.track_id AND m.is_active = true
        """
    )

    op.drop_index(op.f("ix_cohorts_professor_id"), table_name="cohorts")
    op.drop_column("cohorts", "professor_id")


def downgrade() -> None:
    op.add_column("cohorts", sa.Column("professor_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index(op.f("ix_cohorts_professor_id"), "cohorts", ["professor_id"], unique=False)

    op.execute(
        """
        UPDATE cohorts c
        SET professor_id = sub.professor_id
        FROM (
            SELECT DISTINCT ON (cohort_id) cohort_id, professor_id
            FROM cohort_module_professors
            ORDER BY cohort_id, module_id
        ) sub
        WHERE c.id = sub.cohort_id
        """
    )

    op.alter_column("cohorts", "professor_id", nullable=False)
    op.create_foreign_key(
        "cohorts_professor_id_fkey",
        "cohorts",
        "users",
        ["professor_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.drop_index(op.f("ix_cohort_module_professors_professor_id"), table_name="cohort_module_professors")
    op.drop_index(op.f("ix_cohort_module_professors_module_id"), table_name="cohort_module_professors")
    op.drop_index(op.f("ix_cohort_module_professors_cohort_id"), table_name="cohort_module_professors")
    op.drop_table("cohort_module_professors")
