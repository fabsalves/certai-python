"""unique module and lesson titles within parent

Revision ID: 004_unique_module_lesson_titles
Revises: 003_cohort_module_professors
Create Date: 2026-07-05

"""

from alembic import op

revision = "004_unique_module_lesson_titles"
down_revision = "003_cohort_module_professors"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE UNIQUE INDEX uq_module_title_per_track
        ON modules (track_id, lower(trim(title)))
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_lesson_title_per_module
        ON lessons (module_id, lower(trim(title)))
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_lesson_title_per_module")
    op.execute("DROP INDEX IF EXISTS uq_module_title_per_track")
