"""API seam: signup → login/logout → /api/me over HTTP against real Postgres."""

import sqlalchemy as sa

PASSWORD = "correct-horse-battery"


async def test_signup_creates_org_with_admin_creator(api_client, superuser_engine):
    email = "founder@example.com"
    res = await api_client.post(
        "/auth/signup",
        json={"email": email, "password": PASSWORD, "org_name": "Acme Corp"},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["email"] == email
    assert body["is_active"] is True  # signup is immediately active (spec §10)
    assert body["org"]["name"] == "Acme Corp"
    assert body["org"]["slug"] == "acme-corp"
    assert body["role"] == "admin"  # creator is the first Admin
    assert "password" not in body and "hashed_password" not in body

    async with superuser_engine.connect() as conn:
        membership = await conn.execute(
            sa.text(
                "select m.role, o.name from memberships m join orgs o on o.id = m.org_id "
                "join users u on u.id = m.user_id where u.email = :email"
            ),
            {"email": email},
        )
        assert membership.one() == ("admin", "Acme Corp")

        activity = await conn.execute(
            sa.text(
                "select a.event_type from org_activity a join orgs o on o.id = a.org_id "
                "where o.slug = 'acme-corp'"
            )
        )
        assert [r[0] for r in activity] == ["org_created"]


async def test_signup_sets_session_cookie(api_client):
    res = await api_client.post(
        "/auth/signup",
        json={
            "email": "cookie@example.com",
            "password": PASSWORD,
            "org_name": "Cookie Co",
        },
    )
    assert res.status_code == 201
    assert "hr_session" in res.cookies


async def test_signup_persian_org_name_gets_slug(api_client):
    res = await api_client.post(
        "/auth/signup",
        json={
            "email": "tehran@example.com",
            "password": PASSWORD,
            "org_name": "شرکت پارس فناور",
        },
    )
    assert res.status_code == 201
    assert res.json()["org"]["slug"].startswith("org")


async def test_signup_duplicate_email_rejected(api_client):
    payload = {"email": "dupe@example.com", "password": PASSWORD, "org_name": "A"}
    await api_client.post("/auth/signup", json=payload)
    res = await api_client.post(
        "/auth/signup", json={**payload, "org_name": "B"}
    )
    assert res.status_code == 400
    assert res.json()["detail"] == "REGISTER_USER_ALREADY_EXISTS"


async def test_signup_short_password_rejected(api_client):
    res = await api_client.post(
        "/auth/signup",
        json={"email": "short@example.com", "password": "short", "org_name": "A"},
    )
    assert res.status_code == 400
    assert res.json()["detail"]["code"] == "REGISTER_INVALID_PASSWORD"


async def test_me_requires_session(api_client):
    res = await api_client.get("/api/me")
    assert res.status_code == 401


async def test_login_logout_round_trip(api_client):
    email = "roundtrip@example.com"
    await api_client.post(
        "/auth/signup",
        json={"email": email, "password": PASSWORD, "org_name": "Round Trip"},
    )

    login = await api_client.post(
        "/auth/login", data={"username": email, "password": PASSWORD}
    )
    assert login.status_code == 204, login.text
    assert "hr_session" in api_client.cookies

    me = await api_client.get("/api/me")
    assert me.status_code == 200, me.text
    body = me.json()
    assert body["email"] == email
    assert body["org"]["name"] == "Round Trip"
    assert body["role"] == "admin"

    logout = await api_client.post("/auth/logout")
    assert logout.status_code == 204

    after = await api_client.get("/api/me")
    assert after.status_code == 401


async def test_login_wrong_password_rejected(api_client):
    email = "wrongpw@example.com"
    await api_client.post(
        "/auth/signup",
        json={"email": email, "password": PASSWORD, "org_name": "Wrong PW"},
    )
    res = await api_client.post(
        "/auth/login", data={"username": email, "password": "not-the-password"}
    )
    assert res.status_code == 400
    assert res.json()["detail"] == "LOGIN_BAD_CREDENTIALS"
