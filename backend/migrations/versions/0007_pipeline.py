"""Org pipeline and Roles; evolve the canonical Application store.

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

STAGES = (
    ("sourced", "شناسایی‌شده"),
    ("screening", "بررسی اولیه"),
    ("interview", "مصاحبه"),
    ("offer", "پیشنهاد همکاری"),
    ("hired", "استخدام‌شده"),
    ("rejected", "ردشده"),
    ("withdrawn", "انصراف‌داده"),
)


def tenant_table(table):
    op.execute(f"alter table {table} enable row level security")
    op.execute(f"alter table {table} force row level security")
    op.execute(f"""create policy {table}_isolation on {table} for all to hr_app
        using (org_id=(select nullif(current_setting('app.current_org_id',true),'')::uuid))
        with check (org_id=(select nullif(current_setting('app.current_org_id',true),'')::uuid))""")
    op.execute(f"revoke all on {table} from public")


def upgrade():
    for table in ("pipeline_stages", "roles"):
        columns = [
            sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column(
                "org_id", UUID(), sa.ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False
            ),
        ]
        if table == "pipeline_stages":
            columns += [
                sa.Column("name", sa.Text(), nullable=False),
                sa.Column("kind", sa.Text(), nullable=False),
                sa.Column("position", sa.Integer(), nullable=False),
                sa.UniqueConstraint("org_id", "kind"),
            ]
        else:
            columns += [
                sa.Column("title", sa.Text(), nullable=False),
                sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
                sa.Column("owner_id", UUID(), sa.ForeignKey("users.id")),
                sa.Column(
                    "created_at",
                    sa.DateTime(timezone=True),
                    nullable=False,
                    server_default=sa.func.now(),
                ),
                sa.CheckConstraint("status in ('draft','open','paused','closed')"),
            ]
        op.create_table(table, *columns, sa.UniqueConstraint("org_id", "id"))
        op.create_index(f"{table}_org_idx", table, ["org_id"])
        tenant_table(table)
    op.execute("grant select,insert on pipeline_stages to hr_app")
    op.execute("grant select,insert on roles to hr_app")
    op.execute("grant update(title,status,owner_id) on roles to hr_app")
    op.create_index("roles_owner_idx", "roles", ["owner_id"])
    connection = op.get_bind()
    for position, (kind, name) in enumerate(STAGES):
        connection.execute(
            sa.text(
                "insert into pipeline_stages(org_id,name,kind,position) "
                "select id,:name,:kind,:position from orgs"
            ),
            {"name": name, "kind": kind, "position": position},
        )
    op.add_column("candidate_applications", sa.Column("role_id", UUID()))
    op.add_column("candidate_applications", sa.Column("stage_id", UUID()))
    op.add_column(
        "candidate_applications", sa.Column("owner_id", UUID(), sa.ForeignKey("users.id"))
    )
    op.create_index("applications_owner_idx", "candidate_applications", ["owner_id"])
    # A title is not a Role identity: each legacy record gets its own Draft Role.
    # IDs, legacy text, data and candidate linkage are preserved verbatim.
    op.execute("""insert into roles(id,org_id,title,status)
        select id,org_id,role_title,'draft' from candidate_applications""")
    op.execute("""update candidate_applications a set role_id=a.id, stage_id=s.id
        from pipeline_stages s where s.org_id=a.org_id and s.kind=case
          when lower(a.stage) in
            ('sourced','screening','interview','offer','hired','rejected','withdrawn')
          then lower(a.stage) else 'sourced' end""")
    # received and unknown historical stage labels map to Sourced, never a guessed ending.
    for column in ("role_id", "stage_id"):
        op.alter_column("candidate_applications", column, nullable=False)
        op.create_index(
            f"applications_org_{column}_idx", "candidate_applications", ["org_id", column]
        )
    op.create_unique_constraint("candidates_org_id_key", "candidates", ["org_id", "id"])
    op.create_unique_constraint(
        "applications_org_id_key", "candidate_applications", ["org_id", "id"]
    )
    op.create_unique_constraint(
        "application_candidate_role_key", "candidate_applications", ["candidate_id", "role_id"]
    )
    for column, table in (
        ("candidate_id", "candidates"),
        ("role_id", "roles"),
        ("stage_id", "pipeline_stages"),
    ):
        op.create_foreign_key(
            f"applications_tenant_{column}_fk",
            "candidate_applications",
            table,
            ["org_id", column],
            ["org_id", "id"],
        )
    op.create_table(
        "application_activity",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("org_id", UUID(), sa.ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("application_id", UUID(), nullable=False),
        sa.Column("actor_user_id", UUID(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("data", JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["org_id", "application_id"],
            ["candidate_applications.org_id", "candidate_applications.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "application_activity_org_app_idx", "application_activity", ["org_id", "application_id"]
    )
    op.create_index("application_activity_actor_idx", "application_activity", ["actor_user_id"])
    tenant_table("application_activity")
    op.execute("grant select,insert on application_activity to hr_app")
    op.execute("grant update(application_id) on application_activity to hr_app")
    op.execute("grant usage,select on sequence application_activity_id_seq to hr_app")
    op.execute("""insert into application_activity(org_id,application_id,event_type,data,created_at)
        select org_id,id,'legacy_application_imported',
        jsonb_build_object('legacy_stage',stage,'role_title',role_title,'legacy_data',data),created_at
        from candidate_applications""")
    op.add_column("candidate_notes", sa.Column("application_id", UUID()))
    op.create_foreign_key(
        "notes_application_fk",
        "candidate_notes",
        "candidate_applications",
        ["org_id", "application_id"],
        ["org_id", "id"],
    )
    op.create_index(
        "candidate_notes_application_idx", "candidate_notes", ["org_id", "application_id"]
    )


def downgrade():
    op.drop_constraint("notes_application_fk", "candidate_notes", type_="foreignkey")
    op.drop_index("candidate_notes_application_idx", table_name="candidate_notes")
    op.drop_column("candidate_notes", "application_id")
    op.drop_table("application_activity")
    for column in ("candidate_id", "role_id", "stage_id"):
        op.drop_constraint(
            f"applications_tenant_{column}_fk", "candidate_applications", type_="foreignkey"
        )
    for key in ("applications_org_id_key", "application_candidate_role_key"):
        op.drop_constraint(key, "candidate_applications", type_="unique")
    op.drop_constraint("candidates_org_id_key", "candidates", type_="unique")
    for column in ("role_id", "stage_id", "owner_id"):
        op.drop_column("candidate_applications", column)
    op.drop_table("roles")
    op.drop_table("pipeline_stages")
