"""Upgrade legacy placeholder Applications without inventing Role identity."""

import asyncio
import uuid

from alembic import command
from alembic.config import Config
from sqlalchemy import text


async def test_legacy_application_backfill_preserves_ids_data_and_distinct_roles(superuser_engine):
    await asyncio.to_thread(command.downgrade, Config("alembic.ini"), "0006")
    org, candidate = uuid.uuid4(), uuid.uuid4()
    ids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]
    try:
        async with superuser_engine.begin() as conn:
            await conn.execute(
                text("insert into orgs(id,name,slug) values (:id,'Legacy','legacy')"), {"id": org}
            )
            await conn.execute(
                text(
                    "insert into candidates(id,org_id,full_name) values (:id,:org,'Legacy person')"
                ),
                {"id": candidate, "org": org},
            )
            for identifier, stage in zip(
                ids, ("received", "rejected", "Custom old label"), strict=True
            ):
                await conn.execute(
                    text(
                        "insert into candidate_applications(id,org_id,candidate_id,"
                        "role_title,stage,data) values "
                        "(:id,:org,:candidate,'Same title',:stage,'{\"private\":\"kept\"}')"
                    ),
                    {"id": identifier, "org": org, "candidate": candidate, "stage": stage},
                )
        await asyncio.to_thread(command.upgrade, Config("alembic.ini"), "head")
        async with superuser_engine.connect() as conn:
            rows = (
                (
                    await conn.execute(
                        text(
                            "select a.id,a.role_id,a.data,s.kind from candidate_applications a "
                            "join pipeline_stages s on s.id=a.stage_id order by a.stage"
                        )
                    )
                )
                .mappings()
                .all()
            )
            assert {row["id"] for row in rows} == set(ids)
            assert len({row["role_id"] for row in rows}) == 3
            assert sorted(row["kind"] for row in rows) == ["rejected", "sourced", "sourced"]
            assert all(row["data"] == {"private": "kept"} for row in rows)
            assert (
                await conn.execute(
                    text(
                        "select count(*) from application_activity "
                        "where event_type='legacy_application_imported'"
                    )
                )
            ).scalar_one() == 3
    finally:
        await asyncio.to_thread(command.upgrade, Config("alembic.ini"), "head")
