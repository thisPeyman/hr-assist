"""RLS seam: cross-Org access must fail at the database itself.

Connects exactly like the app does (TCP, non-superuser ``hr_app`` role) and
drives raw SQL with the ``app.current_org_id`` GUC the request layer sets.
"""

import pytest
import sqlalchemy as sa

ORG_A = "aaaaaaaa-0000-0000-0000-000000000001"
ORG_B = "aaaaaaaa-0000-0000-0000-000000000002"


async def _seed_org_with_activity(engine, org_id: str, name: str) -> None:
    """Seed as hr_app — pinning the org's own GUC before the activity INSERT,
    exactly like the app's request layer does."""
    async with engine.begin() as conn:
        await conn.execute(
            sa.text("insert into orgs (id, name, slug) values (:id, :n, :s)"),
            {"id": org_id, "n": name, "s": org_id[-6:]},
        )
        await _set_org(conn, org_id)
        await conn.execute(
            sa.text(
                "insert into org_activity (org_id, event_type) "
                "values (:id, 'org_created')"
            ),
            {"id": org_id},
        )


async def _set_org(conn, org_id: str) -> None:
    """Transaction-local GUC — same semantics as the app's request layer, and
    never leaks across pooled connections."""
    await conn.execute(
        sa.text("select set_config('app.current_org_id', :v, true)"), {"v": org_id}
    )


class TestReadIsolation:
    async def test_org_a_sees_only_own_rows(self, app_engine):
        await _seed_org_with_activity(app_engine, ORG_A, "A")
        await _seed_org_with_activity(app_engine, ORG_B, "B")

        async with app_engine.connect() as conn:
            await _set_org(conn, ORG_A)
            rows = await conn.execute(sa.text("select org_id from org_activity"))
            assert [str(r[0]) for r in rows] == [ORG_A]

    async def test_org_b_cannot_read_org_a_rows(self, app_engine):
        await _seed_org_with_activity(app_engine, ORG_A, "A")

        async with app_engine.connect() as conn:
            await _set_org(conn, ORG_B)
            rows = await conn.execute(sa.text("select org_id from org_activity"))
            assert rows.fetchall() == []

    async def test_unset_guc_denies_everything(self, app_engine):
        """A connection that never set the GUC (e.g. before auth) sees no rows."""
        await _seed_org_with_activity(app_engine, ORG_A, "A")

        async with app_engine.connect() as conn:
            rows = await conn.execute(sa.text("select org_id from org_activity"))
            assert rows.fetchall() == []


class TestWriteIsolation:
    async def test_cannot_insert_into_other_org(self, app_engine):
        await _seed_org_with_activity(app_engine, ORG_A, "A")
        await _seed_org_with_activity(app_engine, ORG_B, "B")

        async with app_engine.connect() as conn:
            await _set_org(conn, ORG_A)
            with pytest.raises(sa.exc.DBAPIError, match="row-level security"):
                await conn.execute(
                    sa.text(
                        "insert into org_activity (org_id, event_type) "
                        "values (:id, 'org_created')"
                    ),
                    {"id": ORG_B},
                )

    async def test_cannot_update_other_org_rows(self, app_engine):
        """Cross-Org UPDATE fails twice over: privilege revoked (append-only)
        and, had it not been, the RLS policy would scope it to 0 rows."""
        await _seed_org_with_activity(app_engine, ORG_A, "A")
        await _seed_org_with_activity(app_engine, ORG_B, "B")

        async with app_engine.connect() as conn:
            await _set_org(conn, ORG_A)
            with pytest.raises(sa.exc.DBAPIError, match="permission denied"):
                await conn.execute(
                    sa.text(
                        "update org_activity set event_type = 'tampered' "
                        "where org_id = :id"
                    ),
                    {"id": ORG_B},
                )

    async def test_cannot_delete_other_org_rows(self, app_engine):
        await _seed_org_with_activity(app_engine, ORG_A, "A")
        await _seed_org_with_activity(app_engine, ORG_B, "B")

        async with app_engine.connect() as conn:
            await _set_org(conn, ORG_A)
            with pytest.raises(sa.exc.DBAPIError, match="permission denied"):
                await conn.execute(
                    sa.text("delete from org_activity where org_id = :id"),
                    {"id": ORG_B},
                )


# --------------------------------------------------------------------------
# Ticket 11 — parsing & Talent Pool tables
# --------------------------------------------------------------------------

# parse_jobs is excluded from the parametrized isolation lists: pending rows
# are deliberately visible across Orgs (the queue — workers must claim before
# they can pin an Org). Its own tests below pin the exact contract.


async def _seed_parsing_rows(engine, org_id: str, slug: str) -> None:
    """Seed one org's full ingest chain: candidate → resume → job, pinning
    the org GUC exactly like the app's request layer does."""
    async with engine.begin() as conn:
        await conn.execute(
            sa.text("insert into orgs (id, name, slug) values (:id, :n, :s)"),
            {"id": org_id, "n": slug, "s": slug},
        )
        await _set_org(conn, org_id)
        candidate = await conn.execute(
            sa.text(
                "insert into candidates (org_id, full_name) "
                "values (:id, 'پیمان رضایی') returning id"
            ),
            {"id": org_id},
        )
        candidate_id = candidate.scalar()
        await conn.execute(
            sa.text(
                "insert into candidate_activity (org_id, candidate_id, event_type)"
                " values (:id, :cid, 'resume_added')"
            ),
            {"id": org_id, "cid": candidate_id},
        )
        resume = await conn.execute(
            sa.text(
                "insert into resume_files (org_id, original_filename, mime_type,"
                " sha256, bytes) values (:id, :fn, 'text/plain', :sha, 'x')"
                " returning id"
            ),
            {"id": org_id, "fn": f"{slug}.txt", "sha": slug * 64},
        )
        resume_id = resume.scalar()
        await conn.execute(
            sa.text(
                "update resume_files set candidate_id = :cid where id = :rid"
            ),
            {"cid": candidate_id, "rid": resume_id},
        )
        job = await conn.execute(
            sa.text(
                "insert into parse_jobs (org_id, resume_file_id) "
                "values (:id, :rid) returning id"
            ),
            {"id": org_id, "rid": resume_id},
        )
        job_id = job.scalar()
        await conn.execute(
            sa.text(
                "insert into resume_extractions (org_id, parse_job_id,"
                " resume_file_id, raw_text) values (:id, :jid, :rid, 'متن')"
            ),
            {"id": org_id, "jid": job_id, "rid": resume_id},
        )


class TestParsingReadIsolation:
    @pytest.mark.parametrize(
        "table",
        [
            "candidates",
            "candidate_activity",
            "resume_files",
            "resume_extractions",
        ],
    )
    async def test_other_org_sees_no_rows(self, app_engine, table):
        await _seed_parsing_rows(app_engine, ORG_A, "a")

        async with app_engine.connect() as conn:
            await _set_org(conn, ORG_B)
            rows = await conn.execute(sa.text(f"select org_id from {table}"))
            assert rows.fetchall() == []

    @pytest.mark.parametrize(
        "table",
        [
            "candidates",
            "candidate_activity",
            "resume_files",
            "resume_extractions",
        ],
    )
    async def test_unset_guc_denies_everything(self, app_engine, table):
        await _seed_parsing_rows(app_engine, ORG_A, "a")

        async with app_engine.connect() as conn:
            rows = await conn.execute(sa.text(f"select org_id from {table}"))
            assert rows.fetchall() == []


class TestParseJobQueueVisibility:
    """The one deliberate RLS carve-out: pending rows are visible to the
    worker across Orgs (queue metadata only); everything else about the
    table stays strictly Org-scoped."""

    async def test_other_org_sees_only_pending_rows(self, app_engine):
        await _seed_parsing_rows(app_engine, ORG_A, "a")
        async with app_engine.begin() as conn:
            await _set_org(conn, ORG_A)
            job_id = (
                await conn.execute(sa.text("select id from parse_jobs"))
            ).scalar()
            # The seeded job reaches a terminal status.
            await conn.execute(
                sa.text(
                    "update parse_jobs set status = 'extracted' where id = :jid"
                ),
                {"jid": job_id},
            )
        await _seed_parsing_rows(app_engine, ORG_B, "b")

        async with app_engine.connect() as conn:
            await _set_org(conn, ORG_A)
            rows = await conn.execute(
                sa.text("select org_id, status from parse_jobs order by org_id")
            )
            visible = [(str(r[0]), r[1]) for r in rows]
            # Org A sees its own extracted job + Org B's pending job (queue).
            assert visible == [(ORG_A, "extracted"), (ORG_B, "pending")]

    async def test_cannot_update_other_orgs_pending_job(self, app_engine):
        """Pending rows may be SEEN for claiming, but a session pinned to
        Org A can never mutate Org B's job — the UPDATE policy scopes it to
        zero rows."""
        await _seed_parsing_rows(app_engine, ORG_B, "b")

        async with app_engine.begin() as conn:
            await _set_org(conn, ORG_A)
            result = await conn.execute(
                sa.text("update parse_jobs set status = 'failed'")
            )
            assert result.rowcount == 0
        async with app_engine.connect() as conn:
            await _set_org(conn, ORG_B)
            status = await conn.execute(sa.text("select status from parse_jobs"))
            assert status.scalar() == "pending"


class TestParsingWriteIsolation:
    async def test_cannot_insert_candidate_into_other_org(self, app_engine):
        await _seed_parsing_rows(app_engine, ORG_A, "a")
        await _seed_parsing_rows(app_engine, ORG_B, "b")

        async with app_engine.connect() as conn:
            await _set_org(conn, ORG_A)
            with pytest.raises(sa.exc.DBAPIError, match="row-level security"):
                await conn.execute(
                    sa.text(
                        "insert into candidates (org_id, full_name) "
                        "values (:id, 'مهمان')"
                    ),
                    {"id": ORG_B},
                )

    async def test_update_scopes_to_own_org_only(self, app_engine):
        """parse_jobs carries UPDATE (status transitions); RLS must scope a
        cross-Org UPDATE to zero rows rather than touching Org B's job."""
        await _seed_parsing_rows(app_engine, ORG_A, "a")
        await _seed_parsing_rows(app_engine, ORG_B, "b")

        async with app_engine.begin() as conn:
            await _set_org(conn, ORG_A)
            result = await conn.execute(
                sa.text("update parse_jobs set status = 'failed'")
            )
            assert result.rowcount == 1  # only Org A's job
        async with app_engine.connect() as conn:
            await _set_org(conn, ORG_B)
            status = await conn.execute(sa.text("select status from parse_jobs"))
            assert status.scalar() == "pending"  # Org B untouched
