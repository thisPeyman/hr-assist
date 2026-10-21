"""Schema seam: migrations must produce the tenancy layout the spec locks.

Source of truth: ticket 10 + spec §10 — orgs/users/memberships, org_id on
tenant-owned rows, RLS enabled AND forced on tenant data, least-privilege app
role, one-org-per-user constraint. Ticket 11 + spec §12 adds the parsing and
Talent Pool tables with the same pattern.
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


async def test_activity_is_append_only_for_app(superuser_engine):
    """Activity is an immutable, append-only stream (GLOSSARY) — the app role
    must not be able to UPDATE or DELETE it, even inside its own Org."""
    async with superuser_engine.connect() as conn:
        for denied in ("UPDATE", "DELETE"):
            priv = await conn.execute(
                sa.text(
                    f"select has_table_privilege('hr_app', 'org_activity', '{denied}')"
                )
            )
            assert not priv.scalar()


# --------------------------------------------------------------------------
# Ticket 11 — upload → parse → Candidate in the Talent Pool (spec §12)
# --------------------------------------------------------------------------

PARSING_TABLES = {
    "candidates",
    "candidate_activity",
    "resume_files",
    "parse_jobs",
    "resume_extractions",
}


async def test_parsing_tables_exist(superuser_engine):
    async with superuser_engine.connect() as conn:
        rows = await conn.execute(
            sa.text(
                "select table_name from information_schema.tables "
                "where table_schema = 'public'"
            )
        )
        assert PARSING_TABLES <= {r[0] for r in rows}


async def test_parsing_tables_carry_org_id(superuser_engine):
    async with superuser_engine.connect() as conn:
        rows = await conn.execute(
            sa.text(
                "select table_name from information_schema.columns "
                "where table_schema = 'public' and column_name = 'org_id'"
            )
        )
        assert PARSING_TABLES <= {r[0] for r in rows}


async def test_parse_job_status_enum_covers_all_routes(superuser_engine):
    """pending + ticket-11 terminals, plus the OCR/vision routes ticket 21
    will record — the enum ships complete so it never needs a migration."""
    async with superuser_engine.connect() as conn:
        rows = await conn.execute(
            sa.text("select unnest(enum_range(null::parse_job_status))")
        )
        assert [r[0] for r in rows] == [
            "pending",
            "extracted",
            "ocr_applied",
            "vision_used",
            "needs_review",
            "failed",
            "not_a_resume",
        ]


async def test_resume_files_sha256_is_unique_per_org(superuser_engine):
    """Identical files dedupe by SHA-256 (spec §7.3) — the DB rejects a
    second row with the same (org_id, sha256)."""
    async with superuser_engine.begin() as conn:
        org_id = "44444444-4444-4444-4444-444444444444"
        await conn.execute(
            sa.text("insert into orgs (id, name, slug) values (:oid, 'P', 'p')"),
            {"oid": org_id},
        )
        await conn.execute(
            sa.text(
                "insert into resume_files (org_id, original_filename, mime_type,"
                " sha256, bytes) values (:oid, 'resume.txt', 'text/plain', :sha, 'x')"
            ),
            {"oid": org_id, "sha": "a" * 64},
        )
        with pytest.raises(sa.exc.DBAPIError):
            await conn.execute(
                sa.text(
                    "insert into resume_files (org_id, original_filename,"
                    " mime_type, sha256, bytes) values (:oid, 'again.txt',"
                    " 'text/plain', :sha, 'x')"
                ),
                {"oid": org_id, "sha": "a" * 64},
            )


async def test_rls_enabled_and_forced_on_parsing_tables(superuser_engine):
    async with superuser_engine.connect() as conn:
        rows = await conn.execute(
            sa.text(
                "select relname, relrowsecurity, relforcerowsecurity from pg_class "
                "where relname = any(:tables)"
            ),
            {"tables": list(PARSING_TABLES)},
        )
        checked = {row[0]: (row[1], row[2]) for row in rows}
        assert set(checked) == PARSING_TABLES
        for table, (enabled, forced) in checked.items():
            assert enabled, f"RLS must be enabled on {table}"
            assert forced, f"RLS must be FORCED on {table}"


async def test_isolation_policies_target_app_role_on_parsing_tables(
    superuser_engine,
):
    async with superuser_engine.connect() as conn:
        for table in PARSING_TABLES:
            row = await conn.execute(
                sa.text(
                    "select cmd, roles from pg_policies "
                    f"where tablename = '{table}' "
                    f"and policyname = '{table}_isolation'"
                )
            )
            cmd, roles = row.one()
            assert cmd == "ALL"
            assert "hr_app" in roles


async def test_parse_job_queue_visibility_policy_is_select_only(superuser_engine):
    """Workers must see pending rows across Orgs to claim them (SKIP LOCKED)
    — a SELECT-only carve-out; every write path stays strictly Org-scoped."""
    async with superuser_engine.connect() as conn:
        row = await conn.execute(
            sa.text(
                "select cmd, roles, qual from pg_policies "
                "where tablename = 'parse_jobs' "
                "and policyname = 'parse_jobs_pending_queue_visible'"
            )
        )
        cmd, roles, qual = row.one()
        assert cmd == "SELECT"
        assert "hr_app" in roles
        assert "pending" in qual


async def test_hr_app_privileges_on_parsing_tables(superuser_engine):
    """Least privilege for the full ingest loop: what ticket 11 needs and
    nothing more (Profile edits arrive with ticket 13, hard delete with 26)."""
    async with superuser_engine.connect() as conn:
        expected = {
            "candidates": {"SELECT", "INSERT"},
            "candidate_activity": {"SELECT", "INSERT"},  # append-only (GLOSSARY)
            "resume_files": {"SELECT", "INSERT"},
            "parse_jobs": {"SELECT", "INSERT", "UPDATE"},  # status transitions
            "resume_extractions": {"SELECT", "INSERT"},
        }
        for table, wanted in expected.items():
            granted = set()
            for priv in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE"):
                ok = await conn.execute(
                    sa.text(
                        f"select has_table_privilege('hr_app', '{table}', '{priv}')"
                    )
                )
                if ok.scalar():
                    granted.add(priv)
            assert granted == wanted, f"{table}: {granted} != {wanted}"


async def test_hr_app_can_only_update_resume_file_candidate_link(superuser_engine):
    """The pipeline links a resume to its Candidate after the parse; that is
    the only mutation resume_files ever needs in v1."""
    async with superuser_engine.connect() as conn:
        ok = await conn.execute(
            sa.text(
                "select has_column_privilege('hr_app', 'resume_files',"
                " 'candidate_id', 'UPDATE')"
            )
        )
        assert ok.scalar()
        for column in ("sha256", "bytes", "org_id"):
            denied = await conn.execute(
                sa.text(
                    f"select has_column_privilege('hr_app', 'resume_files',"
                    f" '{column}', 'UPDATE')"
                )
            )
            assert not denied.scalar(), f"hr_app must not UPDATE resume_files.{column}"
