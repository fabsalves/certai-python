"""normalize user emails to lowercase

Revision ID: 005_normalize_user_emails
Revises: 004_unique_module_lesson_titles
Create Date: 2026-07-05

"""

from alembic import op

revision = "005_normalize_user_emails"
down_revision = "004_unique_module_lesson_titles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE users SET email = lower(trim(email)) WHERE email <> lower(trim(email))")


def downgrade() -> None:
    pass
