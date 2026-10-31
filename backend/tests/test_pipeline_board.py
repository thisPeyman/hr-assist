"""Pipeline behavior through HTTP and the restricted PostgreSQL role."""

import asyncio

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.main import app
from app.parsing.llm import get_extractor

from .factories import extraction_payload
from .test_ingest_api import PASSWORD, signup, upload
from .test_profile_merge_summary import install


@pytest.fixture(autouse=True)
def clear_extractor():
    yield
    app.dependency_overrides.pop(get_extractor, None)


async def test_member_can_create_open_and_assign_role_and_org_has_stable_stages(api_client):
    await signup(api_client, "board@example.com", "Pipeline")
    me = (await api_client.get("/api/me")).json()
    stages_response = await api_client.get("/api/pipeline/stages")
    assert stages_response.status_code == 200
    stages = stages_response.json()["items"]
    assert [stage["kind"] for stage in stages] == [
        "sourced",
        "screening",
        "interview",
        "offer",
        "hired",
        "rejected",
        "withdrawn",
    ]
    assert len({stage["id"] for stage in stages}) == 7
    role = await api_client.post("/api/roles", json={"title": "مهندس نرم‌افزار"})
    assert role.status_code == 201, role.text
    role = role.json()
    assert role["status"] == "draft" and role["owner_id"] is None
    opened = await api_client.patch(
        f"/api/roles/{role['id']}", json={"status": "open", "owner_id": me["id"]}
    )
    assert opened.status_code == 200, opened.text
    assert opened.json()["owner_id"] == me["id"]
    assert opened.json()["status"] == "open"
    board = (await api_client.get("/api/pipeline/board")).json()
    assert board["applications"] == []
    assert board["roles"][0]["title"] == "مهندس نرم‌افزار"
    assert board["stages"] == stages


async def test_canonical_application_concurrent_add_explicit_moves_and_terminal_reuse(api_client):
    await signup(api_client, "canonical@example.com", "Canonical")
    install([extraction_payload()])
    candidate = (await upload(api_client, b"Pipeline candidate resume")).json()["candidate"]["id"]
    role = (await api_client.post("/api/roles", json={"title": "Developer"})).json()
    await api_client.patch(f"/api/roles/{role['id']}", json={"status": "open"})
    path = f"/api/roles/{role['id']}/applications"
    results = await asyncio.gather(
        *[api_client.post(path, json={"candidate_id": candidate}) for _ in range(4)]
    )
    assert all(r.status_code == 200 for r in results), [r.text for r in results]
    application = results[0].json()
    assert len({r.json()["id"] for r in results}) == 1
    stages = {s["kind"]: s for s in (await api_client.get("/api/pipeline/stages")).json()["items"]}
    assert application["stage_id"] == stages["sourced"]["id"]
    moved = await api_client.post(
        f"/api/applications/{application['id']}/stage",
        json={
            "stage_id": stages["rejected"]["id"],
            "expected_stage_id": application["stage_id"],
            "context": "تصمیم پس از بررسی انسانی",
            "reason": "experience",
        },
    )
    assert moved.status_code == 200, moved.text
    history = (await api_client.get(f"/api/applications/{application['id']}")).json()["activity"]
    assert [e["event_type"] for e in history] == ["application_added", "stage_changed"]
    assert history[-1]["data"]["context"] == "تصمیم پس از بررسی انسانی"
    assert history[-1]["data"]["reason"] == "experience"
    reopened = (await api_client.post(path, json={"candidate_id": candidate})).json()
    assert reopened["id"] == application["id"]
    assert reopened["stage_id"] == stages["sourced"]["id"]
    detail = (await api_client.get(f"/api/applications/{application['id']}")).json()
    assert detail["activity"][-1]["event_type"] == "application_reopened"
    stale = await api_client.post(
        f"/api/applications/{application['id']}/stage",
        json={"stage_id": stages["offer"]["id"], "expected_stage_id": stages["rejected"]["id"]},
    )
    assert stale.status_code == 409
    # Repeated add of live candidacy and reads do not move it or add activity.
    await api_client.post(path, json={"candidate_id": candidate})
    board = (await api_client.get("/api/pipeline/board")).json()
    assert len(board["applications"]) == 1
    assert board["applications"][0]["full_name"] == "پیمان رضایی"
    assert board["applications"][0]["owner_id"] is None
    assert (
        len((await api_client.get(f"/api/applications/{application['id']}")).json()["activity"])
        == 3
    )


async def test_stage_identity_survives_rename_and_rejection_reason_is_never_required(
    api_client, superuser_engine
):
    await signup(api_client, "stage-kinds@example.com", "Stage kinds")
    install([extraction_payload()])
    candidate = (await upload(api_client, b"Stable stage candidate")).json()["candidate"]["id"]
    role = await open_role(api_client)
    assert (
        await api_client.patch(f"/api/roles/{role}", json={"status": "draft"})
    ).status_code == 409
    application = (
        await api_client.post(f"/api/roles/{role}/applications", json={"candidate_id": candidate})
    ).json()
    stages = {s["kind"]: s for s in (await api_client.get("/api/pipeline/stages")).json()["items"]}
    async with superuser_engine.begin() as conn:
        await conn.execute(
            text("update pipeline_stages set name='نام تازه' where id=:id"),
            {"id": stages["rejected"]["id"]},
        )
    for kind in ("rejected", "withdrawn", "hired"):
        moved = await api_client.post(
            f"/api/applications/{application['id']}/stage",
            json={"stage_id": stages[kind]["id"], "expected_stage_id": application["stage_id"]},
        )
        assert moved.status_code == 200, moved.text
        application = (
            await api_client.post(
                f"/api/roles/{role}/applications", json={"candidate_id": candidate}
            )
        ).json()
        assert application["stage_id"] == stages["sourced"]["id"]
    history = (await api_client.get(f"/api/applications/{application['id']}")).json()["activity"]
    assert len(history) == 7
    rejection = next(e for e in history if e["event_type"] == "stage_changed")
    assert rejection["data"]["reason"] is None and rejection["data"]["context"] is None
    assert rejection["data"]["to_stage_name"] == "نام تازه"


async def test_board_uses_current_title_when_headline_is_missing(api_client):
    await signup(api_client, "current-title@example.com", "Current title")
    install(
        [
            extraction_payload(
                headline=None,
                work_experience=[
                    {
                        "title": "مدیر محصول",
                        "company": "تست",
                        "current": True,
                        "start_date": None,
                        "end_date": None,
                        "location": None,
                        "bullets": [],
                    }
                ],
            )
        ]
    )
    candidate = (await upload(api_client, b"Current title resume")).json()["candidate"]["id"]
    role = await open_role(api_client)
    await api_client.post(f"/api/roles/{role}/applications", json={"candidate_id": candidate})
    board = (await api_client.get("/api/pipeline/board")).json()
    assert board["applications"][0]["headline"] == "مدیر محصول"


async def open_role(client, title="Engineer"):
    role = (await client.post("/api/roles", json={"title": title})).json()
    response = await client.patch(f"/api/roles/{role['id']}", json={"status": "open"})
    assert response.status_code == 200, response.text
    return role["id"]


async def test_merge_same_role_coalesces_and_preserves_history_notes_data_and_target_stage(
    api_client, app_session_factory
):
    from sqlalchemy import select

    from app.models import CandidateApplication, CandidateNote
    from app.rls import set_current_org

    await signup(api_client, "merge-board@example.com", "Merge board")
    install(
        [
            extraction_payload(contact={"full_name": "Same", "email": "one@example.com"}),
            extraction_payload(contact={"full_name": "Same", "email": "two@example.com"}),
        ]
    )
    target = (await upload(api_client, b"Target resume")).json()["candidate"]["id"]
    source = (await upload(api_client, b"Source resume")).json()["candidate"]["id"]
    role = await open_role(api_client)
    one, two = [
        (
            await api_client.post(
                f"/api/roles/{role}/applications", json={"candidate_id": candidate}
            )
        ).json()
        for candidate in (target, source)
    ]
    stages = (await api_client.get("/api/pipeline/stages")).json()["items"]
    await api_client.post(
        f"/api/applications/{two['id']}/stage",
        json={
            "stage_id": stages[2]["id"],
            "expected_stage_id": two["stage_id"],
            "context": "Source interview",
        },
    )
    me = (await api_client.get("/api/me")).json()
    async with app_session_factory() as session:
        await set_current_org(session, me["org"]["id"])
        source_app = await session.scalar(
            select(CandidateApplication).where(CandidateApplication.id == two["id"])
        )
        source_app.data = {"legacy": "preserved"}
        session.add(
            CandidateNote(
                org_id=me["org"]["id"],
                candidate_id=source,
                application_id=two["id"],
                body="Application note",
            )
        )
        await session.commit()
    response = await api_client.post(f"/api/candidates/{source}/merge", json={"target_id": target})
    assert response.status_code == 200, response.text
    board = (await api_client.get("/api/pipeline/board")).json()
    assert len(board["applications"]) == 1
    assert board["applications"][0]["id"] == one["id"]
    assert board["applications"][0]["stage_id"] == one["stage_id"]
    detail = (await api_client.get(f"/api/applications/{one['id']}")).json()
    events = detail["activity"]
    assert len(events) == 4
    assert [e for e in events if e["event_type"] == "stage_changed"][0]["data"][
        "context"
    ] == "Source interview"
    merged = next(e for e in events if e["event_type"] == "application_merged")
    assert merged["data"]["source_application_id"] == two["id"]
    assert merged["data"]["source_data"] == {"legacy": "preserved"}
    async with app_session_factory() as session:
        await set_current_org(session, me["org"]["id"])
        note = await session.scalar(select(CandidateNote))
        assert str(note.application_id) == one["id"] and str(note.candidate_id) == target


async def test_member_permissions_owner_validation_and_tenant_boundary(
    api_client, superuser_engine
):
    await signup(api_client, "member-board@example.com", "Member board")
    me = (await api_client.get("/api/me")).json()
    async with superuser_engine.begin() as conn:
        await conn.execute(
            text("update memberships set role='member' where user_id=:id"), {"id": me["id"]}
        )
    role = await open_role(api_client)
    install([extraction_payload()])
    candidate = (await upload(api_client, b"Tenant candidate")).json()["candidate"]["id"]
    application = (
        await api_client.post(f"/api/roles/{role}/applications", json={"candidate_id": candidate})
    ).json()
    stages = (await api_client.get("/api/pipeline/stages")).json()["items"]
    assert (
        await api_client.patch(
            f"/api/applications/{application['id']}/owner", json={"owner_id": me["id"]}
        )
    ).status_code == 200
    # Member cannot edit stage definitions through this ticket's read-only seam.
    assert (
        await api_client.patch(f"/api/pipeline/stages/{stages[0]['id']}", json={"name": "forged"})
    ).status_code in (404, 405)
    await api_client.post("/auth/logout")
    await signup(api_client, "other-board@example.com", "Other board")
    outsider = (await api_client.get("/api/me")).json()
    other_role = await open_role(api_client)
    assert (
        await api_client.patch(f"/api/roles/{other_role}", json={"owner_id": me["id"]})
    ).status_code == 422
    assert (
        await api_client.post(
            f"/api/roles/{other_role}/applications", json={"candidate_id": candidate}
        )
    ).status_code == 404
    assert (
        await api_client.post(f"/api/roles/{role}/applications", json={"candidate_id": candidate})
    ).status_code == 404
    assert (await api_client.get(f"/api/applications/{application['id']}")).status_code == 404
    assert (
        await api_client.patch(
            f"/api/applications/{application['id']}/owner", json={"owner_id": outsider["id"]}
        )
    ).status_code == 404
    assert (
        await api_client.post(
            f"/api/applications/{application['id']}/stage",
            json={"stage_id": stages[1]["id"], "expected_stage_id": stages[0]["id"]},
        )
    ).status_code == 404
    async with superuser_engine.begin() as conn:
        await conn.execute(text("update users set is_active=false where id=:id"), {"id": me["id"]})
    await api_client.post("/auth/logout")
    # Existing inactive-owner attribution remains stored, but assignment is refused.
    async with superuser_engine.begin() as conn:
        await conn.execute(text("update users set is_active=true where id=:id"), {"id": me["id"]})
        inactive = (
            await conn.execute(
                text(
                    "insert into users(email,hashed_password,is_active) "
                    "values ('inactive@example.com','x',false) returning id"
                )
            )
        ).scalar_one()
        await conn.execute(
            text("insert into memberships(user_id,org_id,role) values (:u,:o,'member')"),
            {"u": inactive, "o": me["org"]["id"]},
        )
    await api_client.post(
        "/auth/login", data={"username": "member-board@example.com", "password": PASSWORD}
    )
    assert (
        await api_client.patch(f"/api/roles/{role}", json={"owner_id": str(inactive)})
    ).status_code == 422
    assert (
        await api_client.patch(
            f"/api/applications/{application['id']}/owner", json={"owner_id": str(inactive)}
        )
    ).status_code == 422
    assert (
        await api_client.patch(f"/api/roles/{role}", json={"owner_id": None})
    ).status_code == 200


async def test_pipeline_database_rls_canonical_key_and_immutable_activity(api_client, app_engine):
    await signup(api_client, "db-board@example.com", "DB board")
    me = (await api_client.get("/api/me")).json()
    role = await open_role(api_client)
    install([extraction_payload()])
    candidate = (await upload(api_client, b"DB pipeline candidate")).json()["candidate"]["id"]
    application = (
        await api_client.post(f"/api/roles/{role}/applications", json={"candidate_id": candidate})
    ).json()
    for table in ("roles", "pipeline_stages", "application_activity"):
        async with app_engine.begin() as conn:
            assert (await conn.execute(text(f"select count(*) from {table}"))).scalar_one() == 0
            await conn.execute(
                text("select set_config('app.current_org_id',:org,true)"), {"org": me["org"]["id"]}
            )
            assert (await conn.execute(text(f"select count(*) from {table}"))).scalar_one() > 0
        for operation in (
            "update application_activity set data='{}'",
            "delete from application_activity",
        ):
            async with app_engine.connect() as conn:
                await conn.execute(
                    text("select set_config('app.current_org_id',:org,true)"),
                    {"org": me["org"]["id"]},
                )
                with pytest.raises(DBAPIError):
                    await conn.execute(text(operation))
                await conn.rollback()
    async with app_engine.connect() as conn:
        await conn.execute(
            text("select set_config('app.current_org_id',:org,true)"), {"org": me["org"]["id"]}
        )
        with pytest.raises(DBAPIError):
            await conn.execute(
                text(
                    "insert into candidate_applications(id,org_id,candidate_id,role_id,"
                    "stage_id,role_title,stage,data) "
                    "values (gen_random_uuid(),:o,:c,:r,:s,'x','sourced','{}')"
                ),
                {"o": me["org"]["id"], "c": candidate, "r": role, "s": application["stage_id"]},
            )
        await conn.rollback()
    await api_client.post("/auth/logout")
    await signup(api_client, "db-other@example.com", "DB other")
    other = (await api_client.get("/api/me")).json()
    other_role = await open_role(api_client)
    other_stage = (await api_client.get("/api/pipeline/stages")).json()["items"][0]["id"]
    for column, value in (("role_id", other_role), ("stage_id", other_stage)):
        async with app_engine.connect() as conn:
            await conn.execute(
                text("select set_config('app.current_org_id',:org,true)"), {"org": me["org"]["id"]}
            )
            with pytest.raises(DBAPIError):
                await conn.execute(
                    text(f"update candidate_applications set {column}=:value where id=:id"),
                    {"value": value, "id": application["id"]},
                )
            await conn.rollback()
    # INSERT policy failures, not just invisibility, under a real restricted role.
    for statement in (
        "insert into roles(id,org_id,title,status) values (gen_random_uuid(),:org,'x','draft')",
        "insert into pipeline_stages(id,org_id,name,kind,position) "
        "values (gen_random_uuid(),:org,'x','custom',9)",
        "insert into application_activity(org_id,application_id,event_type,data) "
        "values (:org,:application,'forged','{}')",
    ):
        async with app_engine.connect() as conn:
            await conn.execute(
                text("select set_config('app.current_org_id',:org,true)"),
                {"org": other["org"]["id"]},
            )
            with pytest.raises(DBAPIError):
                await conn.execute(
                    text(statement), {"org": me["org"]["id"], "application": application["id"]}
                )
            await conn.rollback()
    async with app_engine.begin() as conn:
        await conn.execute(
            text("select set_config('app.current_org_id',:org,true)"), {"org": other["org"]["id"]}
        )
        for table in ("roles", "pipeline_stages", "application_activity"):
            assert (
                await conn.execute(
                    text(f"select count(*) from {table} where org_id=:org"),
                    {"org": me["org"]["id"]},
                )
            ).scalar_one() == 0
        assert (
            await conn.execute(
                text("update candidate_applications set stage='forged' where id=:id"),
                {"id": application["id"]},
            )
        ).rowcount == 0


async def test_pipeline_schema_forces_rls_and_restricts_grants(superuser_engine):
    async with superuser_engine.connect() as conn:
        for table in ("roles", "pipeline_stages", "application_activity"):
            row = (
                await conn.execute(
                    text(
                        "select relrowsecurity,relforcerowsecurity from pg_class "
                        "where relname=:table"
                    ),
                    {"table": table},
                )
            ).one()
            assert row.relrowsecurity and row.relforcerowsecurity
            grants = set(
                (
                    await conn.execute(
                        text(
                            "select privilege_type from information_schema.role_table_grants "
                            "where grantee='hr_app' and table_name=:table"
                        ),
                        {"table": table},
                    )
                ).scalars()
            )
            assert grants == {"SELECT", "INSERT"}


async def test_resume_updates_and_role_owner_edits_never_move_applications(api_client):
    await signup(api_client, "no-auto-board@example.com", "No automatic moves")
    install([extraction_payload(), extraction_payload(headline="Updated profile headline")])
    candidate = (await upload(api_client, b"First stage resume")).json()["candidate"]["id"]
    draft = (await api_client.post("/api/roles", json={"title": "Draft"})).json()
    assert (
        await api_client.post(
            f"/api/roles/{draft['id']}/applications", json={"candidate_id": candidate}
        )
    ).status_code == 409
    role = await open_role(api_client)
    application = (
        await api_client.post(f"/api/roles/{role}/applications", json={"candidate_id": candidate})
    ).json()
    stages = (await api_client.get("/api/pipeline/stages")).json()["items"]
    assert (
        await api_client.post(
            f"/api/applications/{application['id']}/stage",
            json={
                "stage_id": stages[2]["id"],
                "expected_stage_id": application["stage_id"],
                "reason": "skills",
            },
        )
    ).status_code == 422
    moved = await api_client.post(
        f"/api/applications/{application['id']}/stage",
        json={"stage_id": stages[2]["id"], "expected_stage_id": application["stage_id"]},
    )
    assert moved.status_code == 200
    await upload(api_client, b"New resume must not move candidacy")
    me = (await api_client.get("/api/me")).json()
    await api_client.patch(f"/api/roles/{role}", json={"title": "Renamed", "owner_id": me["id"]})
    board = (await api_client.get("/api/pipeline/board")).json()
    assert board["applications"][0]["stage_id"] == stages[2]["id"]
    assert board["applications"][0]["owner_id"] is None  # Role ownership is independent.
    assert board["applications"][0]["role_title"] == "Renamed"
    detail = (await api_client.get(f"/api/applications/{application['id']}")).json()
    assert len(detail["activity"]) == 2
