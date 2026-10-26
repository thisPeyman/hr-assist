"""API seam: upload → parse → Candidate in the Talent Pool over HTTP, with a
fake extractor injected at the dependency seam (no network in tests)."""

import pytest
import sqlalchemy as sa

from app.main import app
from app.parsing.llm import get_extractor

from .factories import extraction_payload
from .test_pipeline import PERSIAN_RESUME

PASSWORD = "correct-horse-battery"


class FakeExtractor:
    def __init__(self, script: list):
        self.script = list(script)

    async def extract(self, text: str, *, model: str, repair: list[str] | None = None):
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.pop(get_extractor, None)


def install_extractor(script: list) -> FakeExtractor:
    fake = FakeExtractor(script)
    app.dependency_overrides[get_extractor] = lambda: fake
    return fake


async def signup(api_client, email: str, org: str) -> None:
    res = await api_client.post(
        "/auth/signup", json={"email": email, "password": PASSWORD, "org_name": org}
    )
    assert res.status_code == 201, res.text


async def upload(api_client, data: bytes, filename: str = "resume.txt"):
    return await api_client.post(
        "/api/candidates/upload", files={"file": (filename, data, "application/octet-stream")}
    )


class TestUploadToPool:
    async def test_upload_persian_resume_creates_candidate(self, api_client):
        await signup(api_client, "hr@example.com", "Acme")
        install_extractor([extraction_payload()])

        res = await upload(api_client, PERSIAN_RESUME)
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["duplicate"] is False
        assert body["job"]["status"] == "extracted"
        assert body["job"]["attempts"] == 1
        assert body["job"]["model"]
        assert body["job"]["prompt_version"] == "v1"
        assert body["job"]["schema_version"] == 1
        assert body["candidate"]["full_name"] == "پیمان رضایی"

        pool = await api_client.get("/api/candidates")
        assert pool.status_code == 200
        items = pool.json()["items"]
        assert [c["full_name"] for c in items] == ["پیمان رضایی"]

        detail = await api_client.get(f"/api/candidates/{body['candidate']['id']}")
        assert detail.status_code == 200
        candidate = detail.json()
        assert candidate["email"] == "peyman@example.com"
        profile = candidate["profile"]
        assert profile["contact"]["full_name"] == "پیمان رضایی"
        assert profile["skills"] == ["Python", "PostgreSQL", "Docker"]
        assert profile["work_experience"][0]["company"] == "دیجی‌کالا"
        assert profile["work_experience"][0]["start_date"] == "2022-03-01"
        assert candidate["resume"]["filename"] == "resume.txt"
        assert candidate["resume"]["parse_status"] == "extracted"

    async def test_identical_file_dedupes_by_sha256(self, api_client):
        await signup(api_client, "hr2@example.com", "Acme Two")
        install_extractor([extraction_payload()])

        first = await upload(api_client, PERSIAN_RESUME)
        assert first.status_code == 201
        install_extractor([extraction_payload()])  # second upload would call again
        second = await upload(api_client, PERSIAN_RESUME)

        assert second.status_code == 201, second.text
        body = second.json()
        assert body["duplicate"] is True
        assert body["candidate"]["id"] == first.json()["candidate"]["id"]

        pool = await api_client.get("/api/candidates")
        assert len(pool.json()["items"]) == 1  # no duplicate Candidate

    async def test_not_a_resume_is_explicit_terminal(self, api_client):
        await signup(api_client, "hr3@example.com", "Acme Three")
        install_extractor([extraction_payload(is_resume=False)])

        res = await upload(api_client, b"Dear team, I am writing to apply...")
        assert res.status_code == 201
        body = res.json()
        assert body["job"]["status"] == "not_a_resume"
        assert body["candidate"] is None
        pool = await api_client.get("/api/candidates")
        assert pool.json()["items"] == []

    async def test_needs_review_creates_candidate_and_flags(self, api_client):
        await signup(api_client, "hr4@example.com", "Acme Four")
        install_extractor([extraction_payload(confidence=0.2)])

        res = await upload(api_client, PERSIAN_RESUME)
        body = res.json()
        assert body["job"]["status"] == "needs_review"
        assert body["job"]["reason"] == "low_confidence"
        assert body["candidate"]["full_name"] == "پیمان رضایی"

    async def test_api_failure_lands_failed(self, api_client):
        from app.parsing.llm import ExtractorError

        await signup(api_client, "hr5@example.com", "Acme Five")
        install_extractor(
            [ExtractorError("api unreachable"), ExtractorError("still down")]
        )

        res = await upload(api_client, PERSIAN_RESUME)
        assert res.status_code == 201
        body = res.json()
        assert body["job"]["status"] == "failed"
        assert "api_error" in body["job"]["reason"]
        assert body["candidate"] is None

    async def test_retrying_a_failed_identical_upload_reprocesses_the_file(self, api_client):
        from app.parsing.llm import ExtractorError

        await signup(api_client, "hr5-retry@example.com", "Acme Five Retry")
        install_extractor([ExtractorError("api unreachable"), ExtractorError("still down")])

        first = await upload(api_client, PERSIAN_RESUME)
        assert first.status_code == 201
        assert first.json()["job"]["status"] == "failed"

        install_extractor([extraction_payload()])
        retry = await upload(api_client, PERSIAN_RESUME)

        assert retry.status_code == 201, retry.text
        body = retry.json()
        assert body["duplicate"] is False
        assert body["job"]["status"] == "extracted"
        assert body["candidate"]["full_name"] == "پیمان رضایی"

        pool = await api_client.get("/api/candidates")
        assert len(pool.json()["items"]) == 1


class TestUploadValidation:
    async def test_requires_session(self, api_client):
        res = await api_client.post(
            "/api/candidates/upload",
            files={"file": ("resume.txt", b"some resume", "text/plain")},
        )
        assert res.status_code == 401

    async def test_empty_file_rejected(self, api_client):
        await signup(api_client, "hr6@example.com", "Acme Six")
        res = await upload(api_client, b"")
        assert res.status_code == 400
        assert res.json()["detail"] == "EMPTY_FILE"

    async def test_oversize_rejected(self, api_client, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "resume_max_bytes", 100)
        await signup(api_client, "hr7@example.com", "Acme Seven")
        res = await upload(api_client, b"x" * 200)
        assert res.status_code == 413
        assert res.json()["detail"] == "FILE_TOO_LARGE"


class TestTenancy:
    async def test_pool_is_org_scoped(self, api_client):
        await signup(api_client, "a@example.com", "Org A")
        install_extractor([extraction_payload()])
        first = await upload(api_client, PERSIAN_RESUME)
        candidate_id = first.json()["candidate"]["id"]

        # A second Org (fresh client cookies) sees nothing.
        api_client.cookies.clear()
        await signup(api_client, "b@example.com", "Org B")
        pool = await api_client.get("/api/candidates")
        assert pool.json()["items"] == []
        detail = await api_client.get(f"/api/candidates/{candidate_id}")
        assert detail.status_code == 404

    async def test_rls_denies_cross_org_at_db_level(
        self, api_client, superuser_engine
    ):
        await signup(api_client, "c@example.com", "Org C")
        install_extractor([extraction_payload()])
        await upload(api_client, PERSIAN_RESUME)

        async with superuser_engine.connect() as conn:
            orgs = await conn.execute(
                sa.text(
                    "select count(*) from candidates c "
                    "where c.org_id = (select id from orgs where name = 'Org C')"
                )
            )
            assert orgs.scalar() == 1
