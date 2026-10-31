"""Collaboration through HTTP and the isolated Postgres app-role boundary."""

from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from .test_ingest_api import PASSWORD, signup
from .test_pipeline_board import open_role


async def seed_candidate(client, app_session_factory):
    me = (await client.get("/api/me")).json()
    async with app_session_factory() as session:
        await session.execute(
            text("select set_config('app.current_org_id', :org, true)"), {"org": me["org"]["id"]}
        )
        candidate = await session.scalar(
            text("insert into candidates(full_name,org_id) values ('کاندیدا',:org) returning id"),
            {"org": UUID(me["org"]["id"])},
        )
        await session.commit()
    return str(candidate)


async def test_candidate_note_edit_mentions_and_recipient_read_state(
    api_client, app_session_factory
):
    await signup(api_client, "notes@example.com", "Notes")
    me = (await api_client.get("/api/me")).json()
    candidate = await seed_candidate(api_client, app_session_factory)
    response = await api_client.post(
        f"/api/candidates/{candidate}/notes",
        json={
            "body": "بررسی تجربه @notes",
            "mention_user_ids": [me["id"], me["id"]],
        },
    )
    assert response.status_code == 201, response.text
    note = response.json()
    assert note["author"]["id"] == me["id"]
    assert note["mention_user_ids"] == [me["id"]]
    inbox = (await api_client.get("/api/notifications")).json()
    assert inbox["unread_count"] == 1
    notification = inbox["items"][0]
    assert notification["href"] == f"/candidates/{candidate}?tab=notes&note={note['id']}"
    assert (
        await api_client.patch(f"/api/notifications/{notification['id']}", json={"read": True})
    ).status_code == 200
    response = await api_client.put(
        f"/api/notes/{note['id']}",
        json={
            "body": "اصلاح بررسی @notes",
            "mention_user_ids": [me["id"]],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["edited_at"] is not None
    inbox = (await api_client.get("/api/notifications")).json()
    assert len(inbox["items"]) == 1 and inbox["unread_count"] == 0
    workspace = (await api_client.get(f"/api/candidates/{candidate}/workspace")).json()
    assert workspace["notes"][0]["body"] == "اصلاح بررسی @notes"
    assert {"note_added", "note_edited"} <= {e["event_type"] for e in workspace["activity"]}


async def seed_member(engine, org_id, email="member-notes@example.com", active=True):
    from fastapi_users.password import PasswordHelper

    password_helper = PasswordHelper()
    async with engine.begin() as conn:
        uid = await conn.scalar(
            text(
                "insert into users(email,hashed_password,is_active) "
                "values (:email,:password,:active) returning id"
            ),
            {"email": email, "password": password_helper.hash(PASSWORD), "active": active},
        )
        await conn.execute(
            text("insert into memberships(org_id,user_id,role) values (:org,:user,'member')"),
            {"org": UUID(org_id), "user": uid},
        )
    return str(uid)


async def login(client, email):
    await client.post("/auth/logout")
    result = await client.post("/auth/login", data={"username": email, "password": PASSWORD})
    assert result.status_code == 204, result.text


async def test_member_collaboration_new_removed_mentions_and_inactive_attribution(
    api_client, app_session_factory, superuser_engine
):
    await signup(api_client, "collab@example.com", "Collab")
    me = (await api_client.get("/api/me")).json()
    member = await seed_member(superuser_engine, me["org"]["id"])
    inactive = await seed_member(superuser_engine, me["org"]["id"], "inactive@example.com", False)
    candidate = await seed_candidate(api_client, app_session_factory)
    path = f"/api/candidates/{candidate}/notes"
    users = (await api_client.get("/api/notes/mention-users")).json()["items"]
    assert {u["id"] for u in users} == {me["id"], member}
    assert (
        await api_client.post(path, json={"body": " ", "mention_user_ids": []})
    ).status_code == 422
    assert (
        await api_client.post(path, json={"body": "متن", "author_id": inactive})
    ).status_code == 422
    assert (
        await api_client.post(path, json={"body": "متن", "mention_user_ids": [inactive]})
    ).status_code == 422
    note = (
        await api_client.post(path, json={"body": "نظر اولیه", "mention_user_ids": [me["id"]]})
    ).json()
    own_notification = (await api_client.get("/api/notifications")).json()["items"][0]
    await login(api_client, "member-notes@example.com")
    assert (await api_client.get("/api/notifications")).json() == {"items": [], "unread_count": 0}
    assert (
        await api_client.patch(f"/api/notifications/{own_notification['id']}", json={"read": True})
    ).status_code == 404
    edited = await api_client.put(
        f"/api/notes/{note['id']}",
        json={"body": "بررسی همکار", "mention_user_ids": [me["id"], member]},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["author"]["id"] == me["id"] and edited.json()["editor"]["id"] == member
    member_notification = (await api_client.get("/api/notifications")).json()["items"][0]
    await api_client.patch(f"/api/notifications/{member_notification['id']}", json={"read": True})
    for recipients in ([], [member], [member]):
        result = await api_client.put(
            f"/api/notes/{note['id']}", json={"body": "نظر نهایی", "mention_user_ids": recipients}
        )
        assert result.status_code == 200, result.text
    inbox = (await api_client.get("/api/notifications")).json()
    assert len(inbox["items"]) == 1 and inbox["unread_count"] == 0
    await api_client.patch(f"/api/notifications/{member_notification['id']}", json={"read": False})
    assert (await api_client.get("/api/notifications")).json()["unread_count"] == 1
    async with superuser_engine.begin() as conn:
        await conn.execute(
            text("update users set is_active=false where id=:id"), {"id": UUID(member)}
        )
    assert (await api_client.get("/api/notifications")).status_code == 401
    await login(api_client, "collab@example.com")
    note = (await api_client.get(f"/api/candidates/{candidate}/workspace")).json()["notes"][0]
    assert note["editor"]["id"] == member and note["editor"]["active"] is False
    assert note["mentions"][0]["active"] is False
    assert (
        await api_client.put(
            f"/api/notes/{note['id']}",
            json={"body": "حفظ اشاره قبلی", "mention_user_ids": [member]},
        )
    ).status_code == 200


async def test_application_aggregation_merge_reparents_and_notification_links_follow(
    api_client, app_session_factory
):
    await signup(api_client, "merge-notes@example.com", "Merge notes")
    me = (await api_client.get("/api/me")).json()
    target = await seed_candidate(api_client, app_session_factory)
    source = await seed_candidate(api_client, app_session_factory)
    role = await open_role(api_client)
    apps = [
        (await api_client.post(f"/api/roles/{role}/applications", json={"candidate_id": c})).json()
        for c in (target, source)
    ]
    general = (
        await api_client.post(f"/api/candidates/{source}/notes", json={"body": "کل پرونده"})
    ).json()
    note = (
        await api_client.post(
            f"/api/applications/{apps[1]['id']}/notes",
            json={"body": "درخواست مشخص", "mention_user_ids": [me["id"]]},
        )
    ).json()
    second_role = await open_role(api_client, "Another role")
    second_app = (
        await api_client.post(
            f"/api/roles/{second_role}/applications", json={"candidate_id": source}
        )
    ).json()
    second_note = (
        await api_client.post(
            f"/api/applications/{second_app['id']}/notes", json={"body": "بررسی درخواست دوم"}
        )
    ).json()
    assert note["application_id"] == apps[1]["id"]
    workspace = (await api_client.get(f"/api/candidates/{source}/workspace")).json()
    assert {n["id"] for n in workspace["notes"]} == {general["id"], note["id"], second_note["id"]}
    detail = (await api_client.get(f"/api/applications/{apps[1]['id']}")).json()
    assert [n["id"] for n in detail["notes"]] == [note["id"]]
    before_activity = detail["activity"]
    assert before_activity[-1]["event_type"] == "note_added"
    assert not any(
        e["event_type"] == "note_added" and e["data"].get("note_id") == note["id"]
        for e in workspace["activity"]
    )
    merged = await api_client.post(f"/api/candidates/{source}/merge", json={"target_id": target})
    assert merged.status_code == 200, merged.text
    detail = (await api_client.get(f"/api/applications/{apps[0]['id']}")).json()
    assert detail["notes"][0]["id"] == note["id"] and detail["notes"][0]["candidate_id"] == target
    for old in before_activity:
        assert old in detail["activity"]
    link = (await api_client.get("/api/notifications")).json()["items"][0]["href"]
    assert link == f"/candidates/{target}?tab=notes&note={note['id']}&application={apps[0]['id']}"
    edited = await api_client.put(
        f"/api/notes/{note['id']}",
        json={"body": "اصلاح پس از ادغام", "mention_user_ids": [me["id"]]},
    )
    assert edited.status_code == 200
    own_view = (await api_client.get(f"/api/applications/{apps[0]['id']}")).json()
    assert own_view["activity"][-1]["event_type"] == "note_edited"
    for event in before_activity:
        assert event in own_view["activity"]
    assert [n["id"] for n in own_view["notes"]] == [note["id"]]
    other_view = (await api_client.get(f"/api/applications/{second_app['id']}")).json()
    assert other_view["notes"][0]["candidate_id"] == target
    assert other_view["notes"][0]["application_id"] == second_app["id"]
    assert len((await api_client.get("/api/notifications")).json()["items"]) == 1


async def test_cross_org_mentions_notes_applications_and_notifications_denied(
    api_client, app_session_factory
):
    await signup(api_client, "private-notes@example.com", "Private")
    private = (await api_client.get("/api/me")).json()
    candidate = await seed_candidate(api_client, app_session_factory)
    role = await open_role(api_client)
    application = (
        await api_client.post(f"/api/roles/{role}/applications", json={"candidate_id": candidate})
    ).json()
    note = (
        await api_client.post(
            f"/api/applications/{application['id']}/notes",
            json={"body": "خصوصی", "mention_user_ids": [private["id"]]},
        )
    ).json()
    notification = (await api_client.get("/api/notifications")).json()["items"][0]
    await api_client.post("/auth/logout")
    await signup(api_client, "other-notes@example.com", "Other")
    other_candidate = await seed_candidate(api_client, app_session_factory)
    assert (
        await api_client.post(
            f"/api/candidates/{other_candidate}/notes",
            json={"body": "متن", "mention_user_ids": [private["id"]]},
        )
    ).status_code == 422
    assert (
        await api_client.put(f"/api/notes/{note['id']}", json={"body": "دستکاری"})
    ).status_code == 404
    assert (
        await api_client.post(
            f"/api/applications/{application['id']}/notes", json={"body": "دستکاری"}
        )
    ).status_code == 404
    assert (
        await api_client.patch(f"/api/notifications/{notification['id']}", json={"read": True})
    ).status_code == 404
    assert (await api_client.get("/api/notifications")).json()["items"] == []


async def test_app_role_forced_rls_recipient_privacy_grants_and_tenant_fks(
    api_client, app_session_factory, app_engine
):
    await signup(api_client, "rls-notes@example.com", "RLS")
    me = (await api_client.get("/api/me")).json()
    candidate = await seed_candidate(api_client, app_session_factory)
    note = (
        await api_client.post(
            f"/api/candidates/{candidate}/notes",
            json={"body": "محفوظ", "mention_user_ids": [me["id"]]},
        )
    ).json()
    notification = (await api_client.get("/api/notifications")).json()["items"][0]
    await api_client.post("/auth/logout")
    await signup(api_client, "foreign-rls-notes@example.com", "Foreign RLS")
    other = (await api_client.get("/api/me")).json()
    foreign_candidate = await seed_candidate(api_client, app_session_factory)
    async with app_engine.connect() as conn:
        assert await conn.scalar(text("select current_user")) == "hr_app"
        for table in ("candidate_notes", "note_mentions", "notifications"):
            assert (
                await conn.execute(
                    text(
                        "select relrowsecurity,relforcerowsecurity "
                        "from pg_class where relname=:table"
                    ),
                    {"table": table},
                )
            ).one() == (True, True)
        assert not await conn.scalar(
            text("select has_table_privilege('hr_app','notifications','DELETE')")
        )
        assert not await conn.scalar(
            text("select has_table_privilege('hr_app','notifications','UPDATE')")
        )
        assert not await conn.scalar(
            text("select has_column_privilege('hr_app','candidate_notes','author_id','UPDATE')")
        )
        assert await conn.scalar(
            text("select has_column_privilege('hr_app','notifications','read_at','UPDATE')")
        )
        for table in ("candidate_notes", "note_mentions", "notifications"):
            assert await conn.scalar(text(f"select count(*) from {table}")) == 0
        await conn.rollback()
        await conn.execute(
            text("select set_config('app.current_org_id', :org, true)"), {"org": me["org"]["id"]}
        )
        assert await conn.scalar(text("select count(*) from candidate_notes")) == 1
        assert await conn.scalar(text("select count(*) from notifications")) == 0  # no user GUC
        await conn.execute(
            text("select set_config('app.current_user_id', :user, true)"), {"user": me["id"]}
        )
        assert await conn.scalar(text("select count(*) from notifications")) == 1
        await conn.execute(
            text("select set_config('app.current_user_id', :user, true)"), {"user": other["id"]}
        )
        assert await conn.scalar(text("select count(*) from notifications")) == 0
        assert (
            await conn.execute(
                text("update notifications set read_at=now() where id=:id"),
                {"id": UUID(notification["id"])},
            )
        ).rowcount == 0
        await conn.rollback()
        await conn.execute(
            text("select set_config('app.current_org_id', :org, true)"), {"org": other["org"]["id"]}
        )
        await conn.execute(
            text("select set_config('app.current_user_id', :user, true)"), {"user": other["id"]}
        )
        for table in ("candidate_notes", "note_mentions", "notifications"):
            assert await conn.scalar(text(f"select count(*) from {table}")) == 0
        assert (
            await conn.execute(
                text("update notifications set read_at=now() where id=:id"),
                {"id": UUID(notification["id"])},
            )
        ).rowcount == 0
        assert (
            await conn.execute(
                text("delete from note_mentions where note_id=:id"), {"id": UUID(note["id"])}
            )
        ).rowcount == 0
        # Tenant RLS and tenant consistency are distinct; prove both as hr_app.
        for sql, params in [
            (
                "insert into notifications(org_id,recipient_id,kind,dedupe_key) "
                "values (:org,:recipient,'note_mention','forged')",
                {"org": me["org"]["id"], "recipient": me["id"]},
            ),
            (
                "insert into notifications(org_id,recipient_id,kind,dedupe_key) "
                "values (:org,:recipient,'note_mention','foreign-recipient')",
                {"org": other["org"]["id"], "recipient": me["id"]},
            ),
            (
                "insert into note_mentions(org_id,note_id,user_id) values (:org,:note,:recipient)",
                {"org": other["org"]["id"], "note": note["id"], "recipient": other["id"]},
            ),
            (
                "insert into candidate_notes(id,org_id,candidate_id,body) "
                "values (gen_random_uuid(),:org,:candidate,'bad')",
                {"org": other["org"]["id"], "candidate": candidate},
            ),
            (
                "insert into candidate_notes(id,org_id,candidate_id,author_id,body) "
                "values (gen_random_uuid(),:org,:candidate,:author,'bad')",
                {"org": other["org"]["id"], "candidate": foreign_candidate, "author": me["id"]},
            ),
        ]:
            with pytest.raises(DBAPIError):
                async with conn.begin_nested():
                    await conn.execute(
                        text(sql), {key: UUID(value) for key, value in params.items()}
                    )
        await conn.rollback()


async def test_mentions_never_send_external_mail_and_unchanged_edit_is_noop(
    api_client, app_session_factory, monkeypatch
):
    import asyncio
    import smtplib

    from httpx import AsyncHTTPTransport

    def forbidden(*args, **kwargs):
        raise AssertionError("mention must never send mail or make a live HTTP request")

    monkeypatch.setattr(smtplib, "SMTP", forbidden)
    monkeypatch.setattr(smtplib, "SMTP_SSL", forbidden)
    monkeypatch.setattr(AsyncHTTPTransport, "handle_async_request", forbidden)
    await signup(api_client, "no-mail@example.com", "No mail")
    me = (await api_client.get("/api/me")).json()
    candidate = await seed_candidate(api_client, app_session_factory)
    payload = {"body": "همکار گرامی", "mention_user_ids": [me["id"]]}
    note = (await api_client.post(f"/api/candidates/{candidate}/notes", json=payload)).json()
    responses = await asyncio.gather(
        *[api_client.put(f"/api/notes/{note['id']}", json=payload) for _ in range(3)]
    )
    assert all(r.status_code == 200 for r in responses)
    assert all(r.json()["edited_at"] is None for r in responses)
    workspace = (await api_client.get(f"/api/candidates/{candidate}/workspace")).json()
    assert [e["event_type"] for e in workspace["activity"]] == ["note_added"]
    inbox = (await api_client.get("/api/notifications")).json()
    assert len(inbox["items"]) == 1 and inbox["unread_count"] == 1


async def test_note_cannot_reference_another_candidates_application_even_in_same_org(
    api_client, app_session_factory, app_engine
):
    await signup(api_client, "note-attribution@example.com", "Attribution")
    me = (await api_client.get("/api/me")).json()
    candidate = await seed_candidate(api_client, app_session_factory)
    other = await seed_candidate(api_client, app_session_factory)
    role = await open_role(api_client)
    application = (
        await api_client.post(f"/api/roles/{role}/applications", json={"candidate_id": candidate})
    ).json()
    async with app_engine.connect() as conn:
        await conn.execute(
            text("select set_config('app.current_org_id', :org, true)"), {"org": me["org"]["id"]}
        )
        with pytest.raises(DBAPIError):
            async with conn.begin_nested():
                await conn.execute(
                    text(
                        "insert into candidate_notes(id,org_id,candidate_id,application_id,body) "
                        "values (gen_random_uuid(),:org,:candidate,:application,"
                        "'invalid attribution')"
                    ),
                    {
                        "org": UUID(me["org"]["id"]),
                        "candidate": UUID(other),
                        "application": UUID(application["id"]),
                    },
                )
                await conn.execute(text("set constraints notes_application_candidate_fk immediate"))
