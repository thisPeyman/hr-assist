"""Schema seam: migrations must produce the tenancy layout the spec locks.

Source of truth: ticket 10 + spec §10 — orgs/users/memberships, org_id on
tenant-owned rows, RLS enabled AND forced on tenant data, least-privilege app
role, one-org-per-user constraint.
"""

import pytest
import sqlalchemy as sa

TABLES = {"users", "orgs", "memberships", "org_activity", "access_tokens"}


async def test_all_core_tables_exist(superuser_engine):
    async with superuser_engine.connect() as conn:
        rows = await conn.execute(
            sa.text(
                "select table_name from information_schema.tables "
                "where table_schema = 'public'"
            )
        )
        assert TABLES <= {r[0] for r in rows}


async def test_membership_role_enum_has_admin_and_member(superuser_engine):
    async with superuser_engine.connect() as conn:
        rows = await conn.execute(
            sa.text("select unnest(enum_range(null::membership_role))")
        )
        assert [r[0] for r in rows] == ["admin", "member"]


async def test_membership_is_one_org_per_user(superuser_engine):
    """v1 locks one Org per User — the DB must reject a second membership."""
    async with superuser_engine.begin() as conn:
        user_id = "11111111-1111-1111-1111-111111111111"
        org_id = "22222222-2222-2222-2222-222222222222"
        await conn.execute(
            sa.text(
                "insert into users (id, email, hashed_password) "
                "values (:uid, 'dupe@example.com', 'x')"
            ),
            {"uid": user_id},
        )
        await conn.execute(
            sa.text("insert into orgs (id, name, slug) values (:oid, 'A', 'a')"),
            {"oid": org_id},
        )
        await conn.execute(
            sa.text(
                "insert into memberships (user_id, org_id, role) "
                "values (:uid, :oid, 'member')"
            ),
            {"uid": user_id, "oid": org_id},
        )
        with pytest.raises(sa.exc.DBAPIError):
            await conn.execute(
                sa.text(
                    "insert into memberships (user_id, org_id, role) "
                    "values (:uid, '33333333-3333-3333-3333-333333333333', 'member')"
                ),
                {"uid": user_id},
            )


async def test_tenant_tables_carry_org_id(superuser_engine):
    async with superuser_engine.connect() as conn:
        rows = await conn.execute(
            sa.text(
                "select table_name from information_schema.columns "
                "where table_schema = 'public' and column_name = 'org_id'"
            )
        )
        assert {"memberships", "org_activity"} <= {r[0] for r in rows}


async def test_rls_enabled_and_forced_on_org_activity(superuser_engine):
    async with superuser_engine.connect() as conn:
        row = await conn.execute(
            sa.text(
                "select relrowsecurity, relforcerowsecurity "
                "from pg_class where relname = 'org_activity'"
            )
        )
        rls_enabled, rls_forced = row.one()
        assert rls_enabled, "RLS must be enabled on org_activity"
        assert rls_forced, "RLS must be FORCED so even the table owner is scoped"


async def test_isolation_policy_targets_app_role(superuser_engine):
    async with superuser_engine.connect() as conn:
        row = await conn.execute(
            sa.text(
                "select cmd, roles from pg_policies "
                "where tablename = 'org_activity' and policyname = 'org_activity_isolation'"
            )
        )
        cmd, roles = row.one()
        assert cmd == "ALL"
        assert "hr_app" in roles


async def test_app_role_exists_least_privilege(superuser_engine):
    """The app must connect as a non-superuser, non-BYPASSRLS role."""
    async with superuser_engine.connect() as conn:
        row = await conn.execute(
            sa.text(
                "select rolsuper, rolbypassrls, rolcanlogin "
                "from pg_roles where rolname = 'hr_app'"
            )
        )
        super_, bypassrls, canlogin = row.one()
        assert not super_
        assert not bypassrls
        assert canlogin


async def test_app_role_least_privilege_on_tenancy_tables(superuser_engine):
    """Signup needs INSERT on tenancy tables, but the app must not mutate them."""
    async with superuser_engine.connect() as conn:
        for table in ("users", "orgs", "memberships"):
            insert_ok = await conn.execute(
                sa.text(f"select has_table_privilege('hr_app', '{table}', 'INSERT')")
            )
            assert insert_ok.scalar(), f"hr_app needs INSERT on {table} for signup"
            for denied in ("UPDATE", "DELETE", "TRUNCATE"):
                priv = await conn.execute(
                    sa.text(
                        f"select has_table_privilege('hr_app', '{table}', '{denied}')"
                    )
                )
                assert not priv.scalar(), f"hr_app must not {denied} {table}"


async def test_app_role_cannot_run_ddl(superuser_engine):
    async with superuser_engine.connect() as conn:
        priv = await conn.execute(
            sa.text("select has_schema_privilege('hr_app', 'public', 'CREATE')")
        )
        assert not priv.scalar()
