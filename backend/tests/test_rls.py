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
        await _seed_org_with_activity(app_engine, ORG_A, "A")
        await _seed_org_with_activity(app_engine, ORG_B, "B")

        async with app_engine.connect() as conn:
            await _set_org(conn, ORG_A)
            result = await conn.execute(
                sa.text(
                    "update org_activity set event_type = 'tampered' "
                    "where org_id = :id"
                ),
                {"id": ORG_B},
            )
            assert result.rowcount == 0

    async def test_cannot_delete_other_org_rows(self, app_engine):
        await _seed_org_with_activity(app_engine, ORG_A, "A")
        await _seed_org_with_activity(app_engine, ORG_B, "B")

        async with app_engine.connect() as conn:
            await _set_org(conn, ORG_A)
            result = await conn.execute(
                sa.text("delete from org_activity where org_id = :id"), {"id": ORG_B}
            )
            assert result.rowcount == 0
