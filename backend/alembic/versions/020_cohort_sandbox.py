"""cohort sandbox mark — a test cohort whose progression can be rewound

Additive. Existing cohorts are real cohorts: they default to false and, with the
field absent from `CohortUpdate`, can never become sandbox.

Revision ID: 020_cohort_sandbox
Revises: 019_lesson_coverage
Create Date: 2026-09-02
"""

from alembic import op
import sqlalchemy as sa

revision = "020_cohort_sandbox"
down_revision = "019_lesson_coverage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cohorts",
        sa.Column(
            "is_sandbox",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("cohorts", "is_sandbox")
