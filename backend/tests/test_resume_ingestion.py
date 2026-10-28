"""Email durability, quarantine, human review, isolation and document route seams."""

import io
import json
from email.message import EmailMessage
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from sqlalchemy import select, text

from app.config import settings
from app.inbound import drain_inbound_mail, mime_documents, storage_path
from app.main import app
from app.models import InboundMail, ResumeExtraction
from app.parsing.documents import prepare_document, scan_attachment
from app.parsing.extract_text import ExtractionError
from app.parsing.llm import OpenAIResumeExtractor, get_extractor
from app.parsing.worker import drain_pending_jobs
from app.rls import set_current_org

from .factories import extraction_payload
from .test_extract_text import make_pdf
from .test_ingest_api import install_extractor, signup, upload
from .test_pipeline import FakeExtractor


@pytest.fixture
def mail_settings(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "inbound_domain", "jobs.example.com")
    monkeypatch.setattr(settings, "inbound_webhook_secret", "test-webhook-secret")
    monkeypatch.setattr(settings, "inbound_storage_dir", str(tmp_path))
    monkeypatch.setattr(settings, "inbound_s3_bucket", "")


@pytest.fixture(autouse=True)
def clear_extractor_override():
    yield
    app.dependency_overrides.pop(get_extractor, None)


def email_bytes(message_id="<resume-1@example.com>", *, attachment=True):
    message = EmailMessage()
    message["From"] = "hr@example.com"
    message["To"] = "ignored@example.com"  # Envelope recipient determines tenancy.
    message["Subject"] = "رزومهٔ علی رضایی"
    message["Message-ID"] = message_id
    message.set_content("علی رضایی\nPython engineer\n-- \nامضای فرستنده\n")
    if attachment:
        message.add_attachment(
            "علی رضایی\nPython engineer".encode(),
            maintype="text",
            subtype="plain",
            filename="رزومه.txt",
        )
    return message.as_bytes()


async def receive(api_client, recipient, raw):
    return await api_client.post(
        "/hooks/inbound-mail",
        content=raw,
        headers={
            "X-Webhook-Secret": "test-webhook-secret",
            "X-Envelope-To": recipient,
        },
    )


async def test_durable_email_duplicate_and_async_candidate(
    api_client,
    app_session_factory,
    mail_settings,
    monkeypatch,
):
    await signup(api_client, "mail-hr@example.com", "Mail test")
    me = (await api_client.get("/api/me")).json()
    recipient = f"resumes+{me['org']['slug']}@jobs.example.com"
    raw = email_bytes()
    first = await receive(api_client, recipient, raw)
    second = await receive(api_client, recipient, raw)
    assert first.status_code == 200 and first.json()["duplicate"] is False
    assert second.json()["duplicate"] is True
    assert (await api_client.get("/api/candidates")).json()["items"] == []
    async with app_session_factory() as session:
        await set_current_org(session, me["org"]["id"])
        mail = (await session.execute(select(InboundMail))).scalar_one()
        assert storage_path(mail.raw_key).read_bytes() == raw
        assert mail.status == "pending"
    monkeypatch.setattr("app.inbound.scan_attachment", lambda data: None)
    assert await drain_inbound_mail(app_session_factory) == 1
    assert await drain_inbound_mail(app_session_factory) == 0
    assert await drain_pending_jobs(app_session_factory, FakeExtractor([extraction_payload()])) == 1
    assert len((await api_client.get("/api/candidates")).json()["items"]) == 1
    assert (await api_client.get("/api/ingestion/settings")).json()["email_address"] == recipient


async def test_webhook_auth_unknown_recipient_and_size(api_client, mail_settings, monkeypatch):
    res = await api_client.post("/hooks/inbound-mail", content=b"raw")
    assert res.status_code == 403
    assert (await receive(api_client, "wrong@jobs.example.com", b"raw")).status_code == 404
    assert (
        await receive(api_client, "resumes+missing@jobs.example.com", b"raw")
    ).status_code == 404
    await signup(api_client, "size@example.com", "Mail size")
    me = (await api_client.get("/api/me")).json()
    monkeypatch.setattr(settings, "inbound_max_bytes", 3)
    recipient = f"resumes+{me['org']['slug']}@jobs.example.com"
    assert (await receive(api_client, recipient, b"long")).status_code == 413


def test_mime_persian_attachment_and_body_quote_stripping():
    documents = mime_documents(email_bytes())
    assert documents[0][0] == "رزومه.txt"
    assert "علی رضایی" in documents[0][1].decode()
    body = mime_documents(email_bytes(attachment=False))[0][1].decode()
    assert "علی رضایی" in body and "امضای" not in body


@pytest.mark.parametrize("reason", ["malware_detected", "scanner_unavailable"])
async def test_quarantine_cannot_be_accepted_or_downloaded(
    api_client,
    app_session_factory,
    mail_settings,
    monkeypatch,
    reason,
):
    await signup(api_client, "quarantine@example.com", "Quarantine")
    me = (await api_client.get("/api/me")).json()
    recipient = f"resumes+{me['org']['slug']}@jobs.example.com"
    assert (await receive(api_client, recipient, email_bytes())).status_code == 200

    def scanner(data):
        raise ExtractionError(reason)

    monkeypatch.setattr("app.inbound.scan_attachment", scanner)
    await drain_inbound_mail(app_session_factory)
    row = (await api_client.get("/api/review")).json()["items"][0]
    assert row["blocked"] and row["reason"] == f"inbound:{reason}"
    assert (await api_client.get(f"/api/review/{row['id']}/document")).status_code == 409
    accept = {"action": "accept", "extraction": extraction_payload()}
    assert (
        await api_client.post(f"/api/review/{row['id']}/resolve", json=accept)
    ).status_code == 409
    dismiss = await api_client.post(f"/api/review/{row['id']}/resolve", json={"action": "failed"})
    assert dismiss.status_code == 200
    assert (await api_client.get("/api/review")).json()["items"] == []
    # Dismissal must not remove quarantine protection or allow an accept replay.
    assert (await api_client.get(f"/api/review/{row['id']}/document")).status_code == 409
    assert (
        await api_client.post(f"/api/review/{row['id']}/resolve", json=accept)
    ).status_code == 409


async def test_review_partial_accept_raw_retained_and_tenant_isolation(
    api_client, app_session_factory
):
    await signup(api_client, "review@example.com", "Review")
    first_me = (await api_client.get("/api/me")).json()
    install_extractor([extraction_payload(contact={"full_name": None, "email": "a@example.com"})])
    outcome = (await upload(api_client, b"Name missing but skills Python")).json()
    job_id = outcome["job"]["id"]
    assert outcome["job"]["status"] == "needs_review"
    detail = (await api_client.get(f"/api/review/{job_id}")).json()
    assert detail["raw_json"]["contact"]["full_name"] is None
    assert "Python" in detail["raw_text"]
    assert (await api_client.get("/api/ingestion/settings")).json()["review_count"] == 1
    doc = await api_client.get(f"/api/review/{job_id}/document")
    assert doc.status_code == 200 and "attachment" in doc.headers["content-disposition"]
    corrected = extraction_payload(contact={"full_name": "نام اصلاح‌شده", "email": "a@example.com"})
    resolved = await api_client.post(
        f"/api/review/{job_id}/resolve", json={"action": "accept", "extraction": corrected}
    )
    assert resolved.status_code == 200, resolved.text
    candidate_id = resolved.json()["candidate_id"]
    candidate = (await api_client.get(f"/api/candidates/{candidate_id}")).json()
    assert candidate["full_name"] == "نام اصلاح‌شده"
    assert (await api_client.get("/api/review")).json()["items"] == []
    again = await api_client.post(
        f"/api/review/{job_id}/resolve", json={"action": "accept", "extraction": corrected}
    )
    assert again.status_code == 409
    async with app_session_factory() as session:
        await set_current_org(session, first_me["org"]["id"])
        raw = (await session.execute(select(ResumeExtraction))).scalar_one()
        assert raw.raw_json["contact"]["full_name"] is None
    await api_client.post("/auth/logout")
    await signup(api_client, "other-review@example.com", "Other")
    for suffix in ("", "/document"):
        assert (await api_client.get(f"/api/review/{job_id}{suffix}")).status_code == 404
    assert (
        await api_client.post(f"/api/review/{job_id}/resolve", json={"action": "failed"})
    ).status_code == 404
    assert (await api_client.get("/api/review")).json()["items"] == []


def test_legacy_gate_and_conversion(monkeypatch):
    monkeypatch.setattr(settings, "legacy_conversion_enabled", False)
    with pytest.raises(ExtractionError, match="legacy_reupload"):
        prepare_document(b"{\\rtf1 old resume}", "resume.rtf")
    monkeypatch.setattr(settings, "legacy_conversion_enabled", True)

    def converter(arguments):
        source = Path(arguments[-1])
        source.with_suffix(".pdf").write_bytes(
            make_pdf(["A sufficiently long resume describing Python and engineering skills."])
        )

    monkeypatch.setattr("app.parsing.documents.run_command", converter)
    assert "Python" in prepare_document(b"{\\rtf1 old resume}", "resume.rtf").text


def test_scanned_pdf_ocr_and_vision_fallback(monkeypatch):
    scanned = make_pdf([])
    monkeypatch.setattr(settings, "ocr_enabled", True)

    def ocr(arguments):
        assert arguments[arguments.index("--language") + 1] == "fas+eng"
        Path(arguments[-1]).write_bytes(
            make_pdf(["Resume text after OCR: engineer with Python and PostgreSQL experience."])
        )

    monkeypatch.setattr("app.parsing.documents.run_command", ocr)
    prepared = prepare_document(scanned, "resume.pdf")
    assert prepared.route == "ocr_applied" and "Python" in prepared.text

    def failed_ocr(arguments):
        raise ExtractionError("document_conversion_failed")

    monkeypatch.setattr("app.parsing.documents.run_command", failed_ocr)
    prepared = prepare_document(scanned, "resume.pdf")
    assert prepared.route == "vision_used" and prepared.images[0].startswith(b"\x89PNG")


def test_image_route_and_corrupt_image():
    output = io.BytesIO()
    Image.new("RGB", (40, 40), "white").save(output, format="PNG")
    assert prepare_document(output.getvalue(), "resume.png").route == "vision_used"
    with pytest.raises(ExtractionError, match="image_unreadable"):
        prepare_document(b"\x89PNG\r\n\x1a\ninvalid", "resume.png")


def test_scanner_fail_closed_and_malware(monkeypatch):
    def unavailable(*args, **kwargs):
        raise FileNotFoundError()

    monkeypatch.setattr("app.parsing.documents.subprocess.run", unavailable)
    with pytest.raises(ExtractionError, match="scanner_unavailable"):
        scan_attachment(b"resume")
    monkeypatch.setattr(
        "app.parsing.documents.subprocess.run", lambda *a, **k: SimpleNamespace(returncode=1)
    )
    with pytest.raises(ExtractionError, match="malware_detected"):
        scan_attachment(b"infected")


async def test_vision_transport_sends_images_as_images():
    captured = {}

    async def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(output_text=json.dumps(extraction_payload()))

    client = SimpleNamespace(responses=SimpleNamespace(create=create))
    result = await OpenAIResumeExtractor(client).extract_images(
        "", [b"image"], model="vision-model"
    )
    assert result["is_resume"]
    assert captured["input"][0]["content"][1]["type"] == "input_image"


async def test_new_inbound_rls_and_immutable_provenance(superuser_engine):
    async with superuser_engine.connect() as connection:
        flags = (
            await connection.execute(
                text(
                    "select relrowsecurity, relforcerowsecurity from pg_class "
                    "where relname='inbound_mail'"
                )
            )
        ).one()
        assert flags == (True, True)
        for column in ("org_id", "raw_key", "recipient"):
            assert not (
                await connection.execute(
                    text(
                        "select has_column_privilege('hr_app', 'inbound_mail', :column, 'UPDATE')"
                    ),
                    {"column": column},
                )
            ).scalar()


@pytest.mark.parametrize("route", ["ocr_applied", "vision_used"])
@pytest.mark.parametrize("flagged", [False, True])
async def test_document_routes_over_api_and_review(api_client, monkeypatch, route, flagged):
    await signup(api_client, "route@example.com", "Document routes")
    payload = extraction_payload(confidence=0.3 if flagged else 0.95)

    class VisionFake(FakeExtractor):
        async def extract_images(self, text, images, **kwargs):
            assert images and images[0].startswith(b"\x89PNG")
            return payload

    app.dependency_overrides[get_extractor] = lambda: VisionFake([payload])
    monkeypatch.setattr(settings, "ocr_enabled", route == "ocr_applied")

    def ocr(arguments):
        Path(arguments[-1]).write_bytes(
            make_pdf(["A resume with Python, PostgreSQL and software engineering work history."])
        )

    monkeypatch.setattr("app.parsing.documents.run_command", ocr)
    response = await upload(api_client, make_pdf([]), "scanned.pdf")
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["job"]["status"] == ("needs_review" if flagged else route)
    job_id = result["job"]["id"]
    preview = await api_client.get(f"/api/review/{job_id}/preview")
    assert preview.status_code == 200 and preview.content.startswith(b"\x89PNG")
    assert preview.headers["x-page-count"] == "1"
    assert (await api_client.get(f"/api/review/{job_id}/preview?page=1")).status_code == 404
    rows = (await api_client.get("/api/review")).json()["items"]
    assert len(rows) == (1 if flagged else 0)
    if flagged:
        accepted = await api_client.post(
            f"/api/review/{job_id}/resolve",
            json={
                "action": "accept",
                "extraction": extraction_payload(),
            },
        )
        assert accepted.status_code == 200
    all_rows = (await api_client.get("/api/review?view=all")).json()["items"]
    assert len(all_rows) == 1


async def test_failed_raw_storage_never_acknowledges(api_client, mail_settings, monkeypatch):
    await signup(api_client, "durability@example.com", "Durability")
    me = (await api_client.get("/api/me")).json()

    def broken_storage(*args):
        raise OSError("disk unavailable")

    monkeypatch.setattr("app.inbound.save_raw", broken_storage)
    recipient = f"resumes+{me['org']['slug']}@jobs.example.com"
    with pytest.raises(OSError):
        await receive(api_client, recipient, email_bytes())


def test_s3_storage_adapter(mail_settings, monkeypatch):
    import uuid

    from app.inbound import read_raw, save_raw

    objects = {}

    class S3:
        def put_object(self, **kwargs):
            objects[kwargs["Key"]] = kwargs["Body"]

        def get_object(self, **kwargs):
            return {"Body": io.BytesIO(objects[kwargs["Key"]])}

    monkeypatch.setattr(settings, "inbound_s3_bucket", "test-bucket")
    monkeypatch.setattr("boto3.client", lambda *args, **kwargs: S3())
    key = save_raw(uuid.uuid4(), b"raw MIME")
    assert read_raw(key) == b"raw MIME"


async def test_inbound_lock_skips_locked_receipt(
    api_client, app_session_factory, mail_settings, monkeypatch
):
    await signup(api_client, "locked@example.com", "Locked")
    me = (await api_client.get("/api/me")).json()
    recipient = f"resumes+{me['org']['slug']}@jobs.example.com"
    await receive(api_client, recipient, email_bytes())
    monkeypatch.setattr("app.inbound.scan_attachment", lambda data: None)
    async with app_session_factory() as session:
        await set_current_org(session, me["org"]["id"])
        await session.execute(select(InboundMail).with_for_update())
        assert await drain_inbound_mail(app_session_factory) == 0
        await session.commit()
    assert await drain_inbound_mail(app_session_factory) == 1
    assert await drain_inbound_mail(app_session_factory) == 0


async def test_quarantined_file_can_only_retry_after_successful_scan(
    api_client,
    app_session_factory,
    mail_settings,
    monkeypatch,
):
    await signup(api_client, "rescan@example.com", "Rescan")
    me = (await api_client.get("/api/me")).json()
    recipient = f"resumes+{me['org']['slug']}@jobs.example.com"
    await receive(api_client, recipient, email_bytes())

    def unavailable(data):
        raise ExtractionError("scanner_unavailable")

    monkeypatch.setattr("app.inbound.scan_attachment", unavailable)
    await drain_inbound_mail(app_session_factory)
    job = (await api_client.get("/api/review")).json()["items"][0]
    monkeypatch.setattr("app.review.scan_attachment", unavailable)
    url = f"/api/review/{job['id']}/resolve"
    assert (await api_client.post(url, json={"action": "rescan"})).status_code == 200
    assert (await api_client.get(f"/api/review/{job['id']}")).json()["blocked"]
    monkeypatch.setattr("app.review.scan_attachment", lambda data: None)
    assert (await api_client.post(url, json={"action": "rescan"})).status_code == 200
    detail = (await api_client.get(f"/api/review/{job['id']}")).json()
    assert detail["status"] == "pending" and detail["blocked"] is False
    assert await drain_pending_jobs(app_session_factory, FakeExtractor([extraction_payload()])) == 1


async def test_raw_text_survives_model_input_truncation(api_client, monkeypatch):
    await signup(api_client, "long@example.com", "Long text")
    monkeypatch.setattr(settings, "resume_text_cap_chars", 10)
    install_extractor([extraction_payload(needs_review=True)])
    data = b"Very long resume text that must not be lost when the model input is truncated"
    result = (await upload(api_client, data)).json()
    detail = (await api_client.get(f"/api/review/{result['job']['id']}")).json()
    assert detail["raw_text"] == data.decode()


async def test_inbound_rls_rejects_other_org_writes(app_session_factory):
    import uuid

    from sqlalchemy.exc import DBAPIError

    from tests.conftest import seed_org_with_admin

    owner, _ = await seed_org_with_admin(app_session_factory)
    other, _ = await seed_org_with_admin(app_session_factory)
    mail_id = uuid.uuid4()
    async with app_session_factory() as session:
        await set_current_org(session, owner)
        session.add(
            InboundMail(
                id=mail_id,
                org_id=uuid.UUID(owner),
                message_id="owner-message",
                recipient="resumes+owner@jobs.example.com",
                raw_key="opaque-key",
                status="processed",
            )
        )
        await session.commit()
    async with app_session_factory() as session:
        await set_current_org(session, other)
        assert (
            await session.execute(select(InboundMail).where(InboundMail.id == mail_id))
        ).scalar_one_or_none() is None
        result = await session.execute(
            text("update inbound_mail set status='failed' where id=:id"), {"id": mail_id}
        )
        assert result.rowcount == 0
        session.add(
            InboundMail(
                org_id=uuid.UUID(owner), message_id="forged", recipient="forged", raw_key="forged"
            )
        )
        with pytest.raises(DBAPIError):
            await session.flush()
        await session.rollback()


async def test_unconfigured_vision_ends_in_review(api_client, monkeypatch):
    monkeypatch.setattr(settings, "resume_ai_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", "")
    await signup(api_client, "missing-key@example.com", "Missing key")
    app.dependency_overrides[get_extractor] = lambda: OpenAIResumeExtractor()
    buffer = io.BytesIO()
    Image.new("RGB", (40, 40)).save(buffer, format="PNG")
    result = (await upload(api_client, buffer.getvalue(), "resume.png")).json()
    assert result["job"]["status"] == "needs_review"
    assert result["job"]["reason"] == "api_error:openai_not_configured"

    class AvailableVisionExtractor:
        async def extract_images(self, text, images, *, model, repair=None):
            assert images
            return extraction_payload()

    app.dependency_overrides[get_extractor] = lambda: AvailableVisionExtractor()
    retried = (await upload(api_client, buffer.getvalue(), "resume.png")).json()
    assert retried["duplicate"] is False
    assert retried["job"]["status"] == "vision_used"
    assert retried["candidate"] is not None


async def test_reprocessing_does_not_overwrite_human_accepted_profile(
    api_client, app_session_factory
):
    from app.models import ParseJob, ResumeFile
    from app.parsing.pipeline import process_parse_job

    await signup(api_client, "protected@example.com", "Protected corrections")
    me = (await api_client.get("/api/me")).json()
    install_extractor([extraction_payload(needs_review=True)])
    result = (await upload(api_client, b"Resume with Python skills to review")).json()
    corrected = extraction_payload(
        contact={"full_name": "Human accepted name", "email": "corrected@example.com"}
    )
    job_id = result["job"]["id"]
    accepted = await api_client.post(
        f"/api/review/{job_id}/resolve", json={"action": "accept", "extraction": corrected}
    )
    candidate_id = accepted.json()["candidate_id"]
    async with app_session_factory() as session:
        await set_current_org(session, me["org"]["id"])
        original_job = (await session.execute(select(ParseJob))).scalar_one()
        resume = await session.get(ResumeFile, original_job.resume_file_id)
        replay = ParseJob(org_id=original_job.org_id, resume_file_id=resume.id)
        session.add(replay)
        await session.flush()
        await process_parse_job(
            session, replay, resume, extractor=FakeExtractor([extraction_payload()])
        )
        assert replay.reason == "existing_profile"
        await session.commit()
    candidate = (await api_client.get(f"/api/candidates/{candidate_id}")).json()
    assert candidate["full_name"] == "Human accepted name"
    assert candidate["email"] == "corrected@example.com"
