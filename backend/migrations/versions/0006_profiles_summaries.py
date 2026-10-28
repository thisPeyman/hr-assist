"""Identity matching, profile proposals, and versioned summary cache.

Revision ID: 0006
Revises: 0005
"""

import re

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

TABLES = ("profile_changes", "resume_summaries", "candidate_notes", "candidate_applications")


def upgrade():
    op.add_column("candidates", sa.Column("normalized_email", sa.Text()))
    op.add_column("candidates", sa.Column("normalized_phone", sa.Text()))
    op.add_column(
        "candidates", sa.Column("human_fields", JSONB(), nullable=False, server_default="[]")
    )
    op.add_column("candidates", sa.Column("latest_resume_version", sa.String(64)))
    op.add_column(
        "candidates",
        sa.Column("new_resume_received", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    for field in ("normalized_email", "normalized_phone"):
        op.create_index(
            f"candidates_{field}_idx",
            "candidates",
            ["org_id", field],
            postgresql_where=sa.text(f"{field} is not null"),
        )
    connection = op.get_bind()
    rows = (
        connection.execute(sa.text("select id, email, phone, profile from candidates"))
        .mappings()
        .all()
    )
    for row in rows:
        phone = re.sub(
            r"\D",
            "",
            (row["phone"] or "").translate(
                str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
            ),
        )
        if phone.startswith("00"):
            phone = phone[2:]
        elif len(phone) == 11 and phone.startswith("09"):
            phone = "98" + phone[1:]
        connection.execute(
            sa.text(
                "update candidates set normalized_email=:email, normalized_phone=:phone "
                "where id=:id"
            ),
            {
                "id": row["id"],
                "email": (row["email"] or "").strip().lower() or None,
                "phone": phone or None,
            },
        )
        edited = connection.execute(
            sa.text(
                "select 1 from candidate_activity where candidate_id=:id "
                "and event_type in ('resume_profile_edited','profile_review_accepted') limit 1"
            ),
            {"id": row["id"]},
        ).first()
        if edited:
            profile = row["profile"] or {}
            protected = [key for key in profile if key != "contact"] + [
                f"contact.{key}" for key in (profile.get("contact") or {})
            ]
            statement = sa.text(
                "update candidates set human_fields=:fields where id=:id"
            ).bindparams(sa.bindparam("fields", type_=JSONB))
            connection.execute(statement, {"id": row["id"], "fields": protected})
    op.execute(
        """update candidates c set latest_resume_version=(
            select sha256 from resume_files r where r.candidate_id=c.id
            order by r.created_at desc,r.id desc limit 1)"""
    )
    for table in TABLES:
        columns = [
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "org_id",
                UUID(as_uuid=True),
                sa.ForeignKey("orgs.id", ondelete="cascade"),
                nullable=False,
            ),
            sa.Column(
                "candidate_id",
                UUID(as_uuid=True),
                sa.ForeignKey("candidates.id", ondelete="cascade"),
                nullable=False,
            ),
        ]
        if table == "profile_changes":
            columns += [
                sa.Column("resume_version", sa.String(64), nullable=False),
                sa.Column("field_path", sa.Text(), nullable=False),
                sa.Column("old_value", JSONB()),
                sa.Column("new_value", JSONB()),
                sa.Column("status", sa.Text(), nullable=False),
                sa.Column(
                    "created_at",
                    sa.DateTime(timezone=True),
                    server_default=sa.func.now(),
                    nullable=False,
                ),
            ]
        elif table == "resume_summaries":
            columns += [
                sa.Column("resume_version", sa.String(64), nullable=False),
                sa.Column("status", sa.Text(), nullable=False),
                sa.Column("content", JSONB()),
                sa.Column("error", sa.Text()),
                sa.Column("model", sa.Text()),
                sa.Column("prompt_version", sa.Text(), nullable=False),
                sa.Column("generated_at", sa.DateTime(timezone=True)),
                sa.UniqueConstraint(
                    "candidate_id", "resume_version", name="summary_candidate_version_key"
                ),
            ]
        elif table == "candidate_notes":
            columns += [
                sa.Column(
                    "author_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="set null")
                ),
                sa.Column("body", sa.Text(), nullable=False),
                sa.Column(
                    "created_at",
                    sa.DateTime(timezone=True),
                    server_default=sa.func.now(),
                    nullable=False,
                ),
            ]
        else:
            columns += [
                sa.Column("role_title", sa.Text(), nullable=False),
                sa.Column("stage", sa.Text(), nullable=False),
                sa.Column("data", JSONB(), nullable=False),
                sa.Column(
                    "created_at",
                    sa.DateTime(timezone=True),
                    server_default=sa.func.now(),
                    nullable=False,
                ),
            ]
        op.create_table(table, *columns)
        op.create_index(f"{table}_org_candidate_idx", table, ["org_id", "candidate_id"])
        op.execute(f"alter table {table} enable row level security")
        op.execute(f"alter table {table} force row level security")
        op.execute(
            f"""create policy {table}_isolation on {table} for all to hr_app
            using (org_id=(select nullif(current_setting('app.current_org_id',true),'')::uuid))
            with check (org_id=(select
                nullif(current_setting('app.current_org_id',true),'')::uuid))"""
        )
        op.execute(f"grant select, insert, update, delete on {table} to hr_app")
        op.execute(f"revoke all on {table} from public")
    op.execute(
        "grant update (normalized_email,normalized_phone,human_fields,latest_resume_version,"
        "new_resume_received) on candidates to hr_app"
    )
    op.execute("grant update (candidate_id) on candidate_activity to hr_app")


def downgrade():
    for table in reversed(TABLES):
        op.drop_table(table)
    op.execute(
        "revoke update (normalized_email,normalized_phone,human_fields,latest_resume_version,"
        "new_resume_received) on candidates from hr_app"
    )
    op.execute("revoke update (candidate_id) on candidate_activity from hr_app")
    for field in ("normalized_email", "normalized_phone"):
        op.drop_index(f"candidates_{field}_idx", table_name="candidates")
    for field in (
        "normalized_email",
        "normalized_phone",
        "human_fields",
        "latest_resume_version",
        "new_resume_received",
    ):
        op.drop_column("candidates", field)
