"""Search database deployment/backfill/index/RLS contract, real PostgreSQL."""

import json
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from .test_rls import ORG_A, ORG_B, _set_org


async def seed(engine):
    ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    async with engine.begin() as conn:
        for org, candidate in zip((ORG_A, ORG_B), ids, strict=True):
            await conn.execute(
                text("INSERT INTO orgs(id,name,slug) VALUES (:o,'Search',:slug)"),
                {"o": org, "slug": org},
            )
            await conn.execute(
                text("INSERT INTO candidates(id,org_id,full_name) VALUES (:c,:o,'Test')"),
                {"c": candidate, "o": org},
            )
            await conn.execute(
                text("""INSERT INTO candidate_search_docs
                (candidate_id,org_id,search_text,normalized_name,content_hash)
                VALUES (:c,:o,'python','test','x')"""),
                {"c": candidate, "o": org},
            )
            await conn.execute(
                text(
                    "INSERT INTO search_query_cache(org_id,query_key,dsl) VALUES (:o,'test','{}')"
                ),
                {"o": org},
            )
    return ids


@pytest.mark.parametrize("table", ["candidate_search_docs", "search_query_cache"])
async def test_search_tables_force_rls_and_scope_all_operations(
    superuser_engine, app_engine, table
):
    ids = await seed(superuser_engine)
    async with superuser_engine.connect() as conn:
        row = (
            await conn.execute(
                text("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE relname=:t"),
                {"t": table},
            )
        ).one()
        assert row == (True, True)
        assert not (
            await conn.execute(
                text("SELECT has_table_privilege('hr_app',:t,'TRUNCATE')"), {"t": table}
            )
        ).scalar()
    async with app_engine.begin() as conn:
        assert (await conn.execute(text(f"SELECT * FROM {table}"))).all() == []
        await _set_org(conn, ORG_A)
        assert [
            str(r.org_id) for r in (await conn.execute(text(f"SELECT org_id FROM {table}"))).all()
        ] == [ORG_A]
        field = "content_hash" if table == "candidate_search_docs" else "query_key"
        assert (
            await conn.execute(
                text(f"UPDATE {table} SET {field}='changed' WHERE org_id=:o"), {"o": ORG_B}
            )
        ).rowcount == 0
        assert (
            await conn.execute(text(f"DELETE FROM {table} WHERE org_id=:o"), {"o": ORG_B})
        ).rowcount == 0
        with pytest.raises(DBAPIError, match="row-level security"):
            async with conn.begin_nested():
                if table == "candidate_search_docs":
                    await conn.execute(
                        text("""INSERT INTO candidate_search_docs
                        (candidate_id,org_id,search_text,normalized_name,content_hash)
                        VALUES (:c,:o,'x','x','x')"""),
                        {"c": str(uuid.uuid4()), "o": ORG_B},
                    )
                else:
                    await conn.execute(
                        text(
                            "INSERT INTO search_query_cache(org_id,query_key,dsl) "
                            "VALUES (:o,'forged','{}')"
                        ),
                        {"o": ORG_B},
                    )
    # Same-org RLS cannot forge a cross-tenant Candidate link either.
    if table == "candidate_search_docs":
        async with app_engine.begin() as conn:
            await _set_org(conn, ORG_A)
            with pytest.raises(DBAPIError):
                await conn.execute(
                    text("""INSERT INTO candidate_search_docs
                    (candidate_id,org_id,search_text,normalized_name,content_hash)
                    VALUES (:c,:o,'x','x','x')"""),
                    {"c": ids[1], "o": ORG_A},
                )


async def test_search_deploys_real_generated_fts_gin_trgm_hnsw_and_tenant_index(superuser_engine):
    async with superuser_engine.connect() as conn:
        indexes = dict(
            (
                await conn.execute(
                    text(
                        "SELECT indexname,indexdef FROM pg_indexes "
                        "WHERE tablename='candidate_search_docs'"
                    )
                )
            ).all()
        )
        assert "USING gin (tsv)" in indexes["search_docs_tsv"]
        assert "gin_trgm_ops" in indexes["search_docs_name"]
        assert "USING hnsw" in indexes["search_docs_hnsw_1536"]
        assert "vector_cosine_ops" in indexes["search_docs_hnsw_1536"]
        assert "USING btree (org_id)" in indexes["search_docs_org"]
        generated = (
            await conn.execute(
                text("""SELECT is_generated,generation_expression
            FROM information_schema.columns WHERE table_name='candidate_search_docs'
            AND column_name='tsv'""")
            )
        ).one()
        assert generated[0] == "ALWAYS" and "simple" in generated[1]


async def test_upgrade_backfills_existing_candidates_without_provider_calls(superuser_engine):
    """Exercise upgrade's real SQL in a rollback-only isolated DDL transaction."""
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    spec = importlib.util.spec_from_file_location(
        "search_upgrade", Path("migrations/versions/0008_candidate_search.py")
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    async with superuser_engine.connect() as conn:
        transaction = await conn.begin()
        try:
            await conn.execute(text("DROP TABLE search_query_cache,candidate_search_docs"))
            await conn.execute(
                text(
                    "ALTER TABLE candidates DROP COLUMN years_experience_total, "
                    "DROP COLUMN experience_computed_at"
                )
            )
            org, candidate = str(uuid.uuid4()), str(uuid.uuid4())
            await conn.execute(
                text("INSERT INTO orgs(id,name,slug) VALUES (:o,'Old',:slug)"),
                {"o": org, "slug": org},
            )
            profile = {
                "skills": ["پایتون"],
                "work_experience": [
                    {"start_date": "2020-01-01", "end_date": "2024-01-01"},
                ],
            }
            await conn.execute(
                text(
                    "INSERT INTO candidates(id,org_id,full_name,profile) "
                    "VALUES (:c,:o,'علي كريمي',CAST(:p AS jsonb))"
                ),
                {"c": candidate, "o": org, "p": json.dumps(profile)},
            )

            def upgrade(sync_conn):
                with Operations.context(MigrationContext.configure(sync_conn)):
                    migration.upgrade()

            await conn.run_sync(upgrade)
            row = (
                await conn.execute(
                    text("""SELECT c.years_experience_total,c.experience_computed_at,
                d.search_text,d.embedding,d.embedding_status FROM candidates c
                JOIN candidate_search_docs d ON c.id=d.candidate_id WHERE c.id=:c"""),
                    {"c": candidate},
                )
            ).one()
            assert row[0] == 4.0 and row[1] is not None
            assert "علی کریمی" in row[2] and "پایتون" in row[2]
            assert row[3] is None and row[4] == "unavailable"
        finally:
            await transaction.rollback()
