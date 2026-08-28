"""organizations, org_settings, tenant FKs, roles, token_version

Revision ID: 018_organizations
Revises: 017_ai_usage_events
Create Date: 2026-08-28
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "018_organizations"
down_revision = "017_ai_usage_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)

    op.create_table(
        "org_settings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("secrets", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id"),
    )
    op.create_index("ix_org_settings_organization_id", "org_settings", ["organization_id"], unique=True)

    op.add_column("users", sa.Column("organization_id", sa.UUID(), nullable=True))
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_users_organization_id", "users", ["organization_id"])
    op.create_foreign_key(
        "fk_users_organization_id",
        "users",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.add_column("tracks", sa.Column("organization_id", sa.UUID(), nullable=True))
    op.create_index("ix_tracks_organization_id", "tracks", ["organization_id"])
    op.create_foreign_key(
        "fk_tracks_organization_id",
        "tracks",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.add_column("cohorts", sa.Column("organization_id", sa.UUID(), nullable=True))
    op.create_index("ix_cohorts_organization_id", "cohorts", ["organization_id"])
    op.create_foreign_key(
        "fk_cohorts_organization_id",
        "cohorts",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.execute("UPDATE users SET role = 'org_admin' WHERE role IN ('admin', 'designer')")

    conn = op.get_bind()
    has_users = conn.execute(sa.text("SELECT 1 FROM users LIMIT 1")).first()
    if has_users:
        org_id = conn.execute(sa.text("SELECT gen_random_uuid()")).scalar()
        conn.execute(
            sa.text(
                """
                INSERT INTO organizations (id, name, slug, is_active)
                VALUES (:id, 'Organização', 'org', true)
                """
            ),
            {"id": org_id},
        )
        conn.execute(
            sa.text(
                """
                INSERT INTO org_settings (id, organization_id, settings, secrets)
                VALUES (gen_random_uuid(), :id, '{}'::jsonb, '{}'::jsonb)
                """
            ),
            {"id": org_id},
        )
        conn.execute(
            sa.text(
                "UPDATE users SET organization_id = :id WHERE role <> 'superadmin'"
            ),
            {"id": org_id},
        )
        conn.execute(
            sa.text("UPDATE tracks SET organization_id = :id"),
            {"id": org_id},
        )
        conn.execute(
            sa.text("UPDATE cohorts SET organization_id = :id"),
            {"id": org_id},
        )

    op.alter_column("tracks", "organization_id", nullable=False)
    op.alter_column("cohorts", "organization_id", nullable=False)


def downgrade() -> None:
    op.drop_constraint("fk_cohorts_organization_id", "cohorts", type_="foreignkey")
    op.drop_index("ix_cohorts_organization_id", table_name="cohorts")
    op.drop_column("cohorts", "organization_id")

    op.drop_constraint("fk_tracks_organization_id", "tracks", type_="foreignkey")
    op.drop_index("ix_tracks_organization_id", table_name="tracks")
    op.drop_column("tracks", "organization_id")

    op.drop_constraint("fk_users_organization_id", "users", type_="foreignkey")
    op.drop_index("ix_users_organization_id", table_name="users")
    op.drop_column("users", "token_version")
    op.drop_column("users", "organization_id")

    op.drop_index("ix_org_settings_organization_id", table_name="org_settings")
    op.drop_table("org_settings")
    op.drop_index("ix_organizations_slug", table_name="organizations")
    op.drop_table("organizations")
