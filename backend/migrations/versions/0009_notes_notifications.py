"""Editable notes and recipient-private in-app notifications.

Revision ID: 0009
Revises: 0008
"""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

ORG = "org_id=(select nullif(current_setting('app.current_org_id',true),'')::uuid)"
USER = "recipient_id=(select nullif(current_setting('app.current_user_id',true),'')::uuid)"


def upgrade():
    op.execute(
        "alter table memberships add constraint memberships_org_user_key unique(org_id,user_id)"
    )
    op.execute("alter table candidate_notes add constraint notes_org_id_key unique(org_id,id)")
    op.execute(
        "alter table candidate_applications add constraint applications_org_candidate_id_key "
        "unique(org_id,candidate_id,id)"
    )
    op.execute(
        "alter table candidate_notes add column edited_at timestamptz, "
        "add column editor_id uuid references users(id)"
    )
    op.execute("""alter table candidate_notes
        add constraint notes_candidate_tenant_fk foreign key(org_id,candidate_id)
          references candidates(org_id,id) on delete cascade,
        add constraint notes_author_tenant_fk foreign key(org_id,author_id)
          references memberships(org_id,user_id),
        add constraint notes_editor_tenant_fk foreign key(org_id,editor_id)
          references memberships(org_id,user_id),
        add constraint notes_application_candidate_fk
          foreign key(org_id,candidate_id,application_id)
          references candidate_applications(org_id,candidate_id,id)
          deferrable initially deferred""")
    op.execute("revoke update on candidate_notes from hr_app")
    op.execute(
        "grant update(body,edited_at,editor_id,candidate_id,application_id) "
        "on candidate_notes to hr_app"
    )
    op.execute("""create table note_mentions(
        org_id uuid not null references orgs(id) on delete cascade,
        note_id uuid not null, user_id uuid not null,
        primary key(org_id,note_id,user_id),
        foreign key(org_id,note_id) references candidate_notes(org_id,id) on delete cascade,
        foreign key(org_id,user_id) references memberships(org_id,user_id))""")
    op.execute("""create table notifications(
        id uuid primary key default gen_random_uuid(),
        org_id uuid not null references orgs(id) on delete cascade,
        recipient_id uuid not null, kind text not null, dedupe_key text not null,
        note_id uuid, created_at timestamptz not null default now(),
        read_at timestamptz,
        unique(org_id,recipient_id,dedupe_key),
        foreign key(org_id,recipient_id) references memberships(org_id,user_id),
        foreign key(org_id,note_id) references candidate_notes(org_id,id) on delete cascade)""")
    op.execute(
        "create index notifications_inbox_idx "
        "on notifications(org_id,recipient_id,created_at desc,id)"
    )
    op.execute("create index notifications_note_idx on notifications(org_id,note_id)")
    op.execute("create index note_mentions_user_idx on note_mentions(org_id,user_id)")
    for table in ("note_mentions", "notifications"):
        op.execute(f"alter table {table} enable row level security")
        op.execute(f"alter table {table} force row level security")
        op.execute(f"revoke all on {table} from public")
    op.execute(
        "create policy note_mentions_isolation on note_mentions for all to hr_app "
        f"using ({ORG}) with check ({ORG})"
    )
    op.execute("grant select,insert,delete on note_mentions to hr_app")
    op.execute(
        "create policy notifications_insert on notifications for insert to hr_app "
        f"with check ({ORG})"
    )
    op.execute(
        "create policy notifications_read on notifications for select to hr_app "
        f"using ({ORG} and {USER})"
    )
    op.execute(
        "create policy notifications_update on notifications for update to hr_app "
        f"using ({ORG} and {USER}) with check ({ORG} and {USER})"
    )
    # Mention links resolve via the reparented Note; no notification UPDATE during Merge.
    op.execute("grant select,insert on notifications to hr_app")
    op.execute("grant update(read_at) on notifications to hr_app")
    op.execute("create index notes_author_idx on candidate_notes(org_id,author_id)")
    op.execute("create index notes_editor_idx on candidate_notes(org_id,editor_id)")


def downgrade():
    op.execute("drop index notes_author_idx, notes_editor_idx")
    op.execute("drop table notifications, note_mentions")
    for name in (
        "notes_application_candidate_fk",
        "notes_editor_tenant_fk",
        "notes_author_tenant_fk",
        "notes_candidate_tenant_fk",
        "notes_org_id_key",
    ):
        op.execute(f"alter table candidate_notes drop constraint {name}")
    op.execute("alter table candidate_notes drop column edited_at, drop column editor_id")
    op.execute(
        "alter table candidate_applications drop constraint applications_org_candidate_id_key"
    )
    op.execute("alter table memberships drop constraint memberships_org_user_key")
    op.execute("grant update on candidate_notes to hr_app")
