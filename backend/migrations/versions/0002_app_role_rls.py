"""least-privilege app role + RLS belt-and-braces on tenant data

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-21

Creates the non-superuser ``hr_app`` login role the application connects as,
grants it exactly what the walking skeleton needs, and enables (and FORCES)
row-level security on ``org_activity`` scoped by the ``app.current_org_id``
GUC that the request layer sets per transaction.

"""
import os
from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Kept in sync with app.config.Settings.app_db_password's default.
_DEFAULT_PASSWORD = "hr_app_dev"


def _app_db_password() -> str:
    return os.environ.get("HR_APP_DB_PASSWORD", _DEFAULT_PASSWORD).replace("'", "''")


def upgrade() -> None:
    password = _app_db_password()
    op.execute(
        f"""
        do $$
        begin
            if not exists (select 1 from pg_roles where rolname = 'hr_app') then
                create role hr_app login password '{password}' nosuperuser nobypassrls;
            else
                alter role hr_app login password '{password}' nosuperuser nobypassrls;
            end if;
        end
        $$;
        """
    )
    # Least privilege: the app can do exactly what signup/login/me need.
    op.execute("grant usage on schema public to hr_app")
    op.execute("grant select, insert on public.users to hr_app")
    op.execute("grant select, insert on public.orgs to hr_app")
    op.execute("grant select, insert on public.memberships to hr_app")
    op.execute(
        "grant select, insert, update, delete on public.org_activity to hr_app"
    )
    op.execute("grant select, insert, delete on public.access_tokens to hr_app")
    op.execute("grant usage, select on sequence memberships_id_seq to hr_app")
    op.execute("grant usage, select on sequence org_activity_id_seq to hr_app")

    # RLS belt-and-braces: policies deny by default when the GUC is unset, and
    # FORCED means even the table owner is subject to them.
    op.execute("alter table org_activity enable row level security")
    op.execute("alter table org_activity force row level security")
    op.execute(
        """
        create policy org_activity_isolation on org_activity
            for all to hr_app
            using (
                org_id = (select nullif(current_setting('app.current_org_id', true), '')::uuid)
            )
            with check (
                org_id = (select nullif(current_setting('app.current_org_id', true), '')::uuid)
            )
        """
    )


def downgrade() -> None:
    op.execute("drop policy if exists org_activity_isolation on org_activity")
    op.execute("alter table org_activity no force row level security")
    op.execute("alter table org_activity disable row level security")
    op.execute("revoke all on all tables in schema public from hr_app")
    op.execute("revoke usage on schema public from hr_app")
