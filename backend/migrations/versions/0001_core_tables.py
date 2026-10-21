"""org & auth walking skeleton: core tables

Revision ID: 0001
Revises:
Create Date: 2026-10-21

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=1024), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "is_superuser", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "is_verified", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("email", name="users_email_key"),
    )
    op.create_table(
        "orgs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("slug", name="orgs_slug_key"),
    )
    sa.Enum("admin", "member", name="membership_role")  # created with memberships below
    op.create_table(
        "memberships",
        sa.Column(
            "id", sa.BigInteger(), sa.Identity(), primary_key=True
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="cascade"),
            nullable=False,
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orgs.id", ondelete="cascade"),
            nullable=False,
        ),
        sa.Column(
            "role",
            sa.Enum("admin", "member", name="membership_role"),
            nullable=False,
            server_default="member",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("user_id", name="memberships_user_id_key"),
    )
    op.create_index("memberships_org_id_idx", "memberships", ["org_id"])
    op.create_table(
        "org_activity",
        sa.Column(
            "id", sa.BigInteger(), sa.Identity(), primary_key=True
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orgs.id", ondelete="cascade"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="set null"),
            nullable=True,
        ),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column(
            "data",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("org_activity_org_id_idx", "org_activity", ["org_id"])
    op.create_table(
        "access_tokens",
        sa.Column("token", sa.String(length=43), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="cascade"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("access_tokens_created_at_idx", "access_tokens", ["created_at"])


def downgrade() -> None:
    op.drop_index("access_tokens_created_at_idx", table_name="access_tokens")
    op.drop_table("access_tokens")
    op.drop_index("org_activity_org_id_idx", table_name="org_activity")
    op.drop_table("org_activity")
    op.drop_index("memberships_org_id_idx", table_name="memberships")
    op.drop_table("memberships")
    sa.Enum("admin", "member", name="membership_role").drop(op.get_bind())
    op.drop_table("orgs")
    op.drop_table("users")
