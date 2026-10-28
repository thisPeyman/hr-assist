"""Durable inbound receipts and human review permissions.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inbound_mail",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orgs.id", ondelete="cascade"),
            nullable=False,
        ),
        sa.Column("message_id", sa.Text(), nullable=False),
        sa.Column("recipient", sa.Text(), nullable=False),
        sa.Column("raw_key", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("reason", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("message_id", "recipient", name="inbound_mail_delivery_key"),
        sa.CheckConstraint(
            "status in ('pending', 'processed', 'failed')", name="inbound_mail_status_check"
        ),
    )
    op.create_index("inbound_mail_org_id_idx", "inbound_mail", ["org_id"])
    op.create_index(
        "inbound_mail_pending_idx",
        "inbound_mail",
        ["created_at", "id"],
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.execute("alter table inbound_mail enable row level security")
    op.execute("alter table inbound_mail force row level security")
    op.execute("""
        create policy inbound_mail_isolation on inbound_mail for all to hr_app
        using (org_id = (select nullif(current_setting('app.current_org_id', true), '')::uuid))
        with check (org_id =
            (select nullif(current_setting('app.current_org_id', true), '')::uuid))
    """)
    # raw bytes live outside SQL; the pending worker projection contains opaque keys only.
    op.execute("""
        create policy inbound_mail_pending_visible on inbound_mail for select to hr_app
        using (status = 'pending')
    """)
    op.execute("grant select, insert on inbound_mail to hr_app")
    op.execute("grant update (status, reason) on inbound_mail to hr_app")
    op.execute(
        "grant update (full_name, headline, email, phone, location, profile, updated_at) "
        "on candidates to hr_app"
    )
    op.execute("revoke all on inbound_mail from public")


def downgrade() -> None:
    op.execute(
        "revoke update (full_name, headline, email, phone, location, profile, updated_at) "
        "on candidates from hr_app"
    )
    op.drop_table("inbound_mail")
