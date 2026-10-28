"""Pipeline seam: process_parse_job — every submitted document ends in an
explicit terminal status; a Candidate appears in the Talent Pool when — and
only when — the parse produced a trustworthy identity (spec §4.2, §7.3).
"""

import uuid

import sqlalchemy as sa

from app.models import (
    Candidate,
    CandidateActivity,
    ParseJob,
    ParseJobStatus,
    ResumeExtraction,
    ResumeFile,
)
from app.parsing.llm import ExtractorError
from app.parsing.pipeline import process_parse_job
from app.rls import set_current_org

from .factories import extraction_payload
from .test_extract_text import make_pdf

PERSIAN_RESUME = """پیمان رضایی
Senior Backend Engineer — مهندس ارشد نرم‌افزار
ایمیل: peyman@example.com — تلفن: 09123456789
مهارت‌ها: Python, PostgreSQL, Docker
""".encode()


class FakeExtractor:
    def __init__(self, script: list):
        self.script = list(script)

    async def extract(self, text: str, *, model: str, repair: list[str] | None = None):
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


async def create_job(session_factory, org_id: str, *, data: bytes, filename: str):
    """Create resume_file + pending parse_job rows, GUC-pinned like the app."""
    import hashlib

    from app.models import ParseJob, ResumeFile

    async with session_factory() as session:
        await set_current_org(session, org_id)
        resume = ResumeFile(
            org_id=org_id,
            original_filename=filename,
            mime_type="application/octet-stream",
            sha256=hashlib.sha256(data).hexdigest(),
            bytes=data,
        )
        session.add(resume)
        await session.flush()
        job = ParseJob(org_id=org_id, resume_file_id=resume.id)
        session.add(job)
        await session.commit()
        return job.id, resume.id


async def load_job(session_factory, job_id, org_id):
    async with session_factory() as session:
        await set_current_org(session, org_id)
        job = await session.get(ParseJob, job_id)
        return job


class TestHappyPath:
    async def test_persian_resume_becomes_candidate_in_pool(
        self, app_session_factory
    ):
        from tests.conftest import seed_org_with_admin

        org_id, user_id = await seed_org_with_admin(app_session_factory)
        job_id, resume_id = await create_job(
            app_session_factory, org_id, data=PERSIAN_RESUME, filename="resume.txt"
        )

        async with app_session_factory() as session:
            await set_current_org(session, org_id)
            job = await session.get(ParseJob, job_id)
            resume = await session.get(ResumeFile, resume_id)
            await process_parse_job(
                session,
                job,
                resume,
                extractor=FakeExtractor([extraction_payload()]),
                actor_user_id=uuid.UUID(user_id),
            )
            await session.commit()

        job = await load_job(app_session_factory, job_id, org_id)
        assert job.status == ParseJobStatus.EXTRACTED
        assert job.reason is None
        assert job.attempts == 1
        assert job.model  # from config, recorded per row
        assert job.prompt_version == "v1"
        assert job.schema_version == 1
        assert job.finished_at is not None
        assert job.extract_ms >= 0
        assert job.llm_ms >= 0

        async with app_session_factory() as session:
            await set_current_org(session, org_id)
            candidate = (await session.execute(sa.select(Candidate))).scalar_one()
            assert candidate.full_name == "پیمان رضایی"
            assert candidate.email == "peyman@example.com"
            assert candidate.headline == "Senior Backend Engineer"
            assert candidate.profile["skills"] == ["Python", "PostgreSQL", "Docker"]
            # Values verbatim, never translated
            assert candidate.profile["work_experience"][0]["company"] == "دیجی‌کالا"
            # Dates normalized in Python post-processing
            assert candidate.profile["work_experience"][0]["start_date"] == "2022-03-01"

            resume = await session.get(ResumeFile, resume_id)
            assert resume.candidate_id == candidate.id  # linked

            activity = (
                await session.execute(sa.select(CandidateActivity))
            ).scalar_one()
            assert activity.event_type == "resume_added"
            assert str(activity.candidate_id) == str(candidate.id)

            extraction_row = (
                await session.execute(sa.select(ResumeExtraction))
            ).scalar_one()
            assert "پیمان رضایی" in extraction_row.raw_text
            assert extraction_row.raw_json["contact"]["full_name"] == "پیمان رضایی"
            assert extraction_row.model == job.model
            assert extraction_row.prompt_version == "v1"
            assert extraction_row.schema_version == 1


class TestTerminalStatuses:
    async def test_not_a_resume(self, app_session_factory):
        from tests.conftest import seed_org_with_admin

        org_id, _ = await seed_org_with_admin(app_session_factory)
        job_id, _ = await create_job(
            app_session_factory,
            org_id,
            data=b"Dear hiring team, I am excited to apply...",
            filename="cover-letter.txt",
        )
        async with app_session_factory() as session:
            await set_current_org(session, org_id)
            job = await session.get(ParseJob, job_id)
            resume = await session.get(ResumeFile, job.resume_file_id)
            await process_parse_job(
                session,
                job,
                resume,
                extractor=FakeExtractor([extraction_payload(is_resume=False)]),
            )
            await session.commit()

        job = await load_job(app_session_factory, job_id, org_id)
        assert job.status == ParseJobStatus.NOT_A_RESUME
        async with app_session_factory() as session:
            await set_current_org(session, org_id)
            assert (await session.execute(sa.select(Candidate))).scalar() is None

    async def test_low_confidence_still_creates_candidate_but_flags(
        self, app_session_factory
    ):
        from tests.conftest import seed_org_with_admin

        org_id, _ = await seed_org_with_admin(app_session_factory)
        job_id, _ = await create_job(
            app_session_factory, org_id, data=PERSIAN_RESUME, filename="resume.txt"
        )
        async with app_session_factory() as session:
            await set_current_org(session, org_id)
            job = await session.get(ParseJob, job_id)
            resume = await session.get(ResumeFile, job.resume_file_id)
            await process_parse_job(
                session,
                job,
                resume,
                extractor=FakeExtractor([extraction_payload(confidence=0.2)]),
            )
            await session.commit()

        job = await load_job(app_session_factory, job_id, org_id)
        assert job.status == ParseJobStatus.NEEDS_REVIEW
        assert job.reason == "low_confidence"
        async with app_session_factory() as session:
            await set_current_org(session, org_id)
            assert (await session.execute(sa.select(Candidate))).scalar_one()

    async def test_missing_identity_no_candidate(self, app_session_factory):
        from tests.conftest import seed_org_with_admin

        org_id, _ = await seed_org_with_admin(app_session_factory)
        payload = extraction_payload()
        payload["contact"] = {"full_name": None, "email": None, "phone": None}
        job_id, _ = await create_job(
            app_session_factory, org_id, data=PERSIAN_RESUME, filename="resume.txt"
        )
        async with app_session_factory() as session:
            await set_current_org(session, org_id)
            job = await session.get(ParseJob, job_id)
            resume = await session.get(ResumeFile, job.resume_file_id)
            await process_parse_job(
                session, job, resume, extractor=FakeExtractor([payload])
            )
            await session.commit()

        job = await load_job(app_session_factory, job_id, org_id)
        assert job.status == ParseJobStatus.NEEDS_REVIEW
        assert job.reason == "missing_identity"
        async with app_session_factory() as session:
            await set_current_org(session, org_id)
            assert (await session.execute(sa.select(Candidate))).scalar() is None

    async def test_corrupt_pdf_needs_review_with_reason(self, app_session_factory):
        from tests.conftest import seed_org_with_admin

        org_id, _ = await seed_org_with_admin(app_session_factory)
        job_id, _ = await create_job(
            app_session_factory,
            org_id,
            data=b"%PDF-1.4\nnot really a pdf",
            filename="broken.pdf",
        )
        async with app_session_factory() as session:
            await set_current_org(session, org_id)
            job = await session.get(ParseJob, job_id)
            resume = await session.get(ResumeFile, job.resume_file_id)
            await process_parse_job(
                session, job, resume, extractor=FakeExtractor([])
            )
            await session.commit()

        job = await load_job(app_session_factory, job_id, org_id)
        assert job.status == ParseJobStatus.NEEDS_REVIEW
        assert job.reason == "extraction:corrupt_pdf"

    async def test_validation_ladder_exhausted_needs_review(self, app_session_factory):
        from tests.conftest import seed_org_with_admin

        org_id, _ = await seed_org_with_admin(app_session_factory)
        job_id, _ = await create_job(
            app_session_factory, org_id, data=PERSIAN_RESUME, filename="resume.txt"
        )
        bad = extraction_payload(confidence=1.5)
        async with app_session_factory() as session:
            await set_current_org(session, org_id)
            job = await session.get(ParseJob, job_id)
            resume = await session.get(ResumeFile, job.resume_file_id)
            await process_parse_job(
                session, job, resume, extractor=FakeExtractor([bad, bad, bad])
            )
            await session.commit()

        job = await load_job(app_session_factory, job_id, org_id)
        assert job.status == ParseJobStatus.NEEDS_REVIEW
        assert job.reason == "validation_failed"
        assert job.attempts == 3
        # Raw text is kept even when the model never produced valid JSON —
        # and so is the last (invalid) payload: the needs_review queue
        # (ticket 20) shows the document and whatever the model did emit.
        async with app_session_factory() as session:
            await set_current_org(session, org_id)
            row = (await session.execute(sa.select(ResumeExtraction))).scalar_one()
            assert "پیمان رضایی" in row.raw_text
            assert row.raw_json is not None
            assert row.raw_json["contact"]["full_name"] == "پیمان رضایی"

    async def test_api_failure_is_failed_not_dropped(self, app_session_factory):
        from tests.conftest import seed_org_with_admin

        org_id, _ = await seed_org_with_admin(app_session_factory)
        job_id, _ = await create_job(
            app_session_factory, org_id, data=PERSIAN_RESUME, filename="resume.txt"
        )
        async with app_session_factory() as session:
            await set_current_org(session, org_id)
            job = await session.get(ParseJob, job_id)
            resume = await session.get(ResumeFile, job.resume_file_id)
            await process_parse_job(
                session,
                job,
                resume,
                extractor=FakeExtractor(
                    [ExtractorError("api unreachable"), ExtractorError("still down")]
                ),
            )
            await session.commit()

        job = await load_job(app_session_factory, job_id, org_id)
        assert job.status == ParseJobStatus.FAILED
        assert "still down" in job.reason

    async def test_corrupt_image_needs_review(self, app_session_factory):
        from tests.conftest import seed_org_with_admin

        org_id, _ = await seed_org_with_admin(app_session_factory)
        job_id, _ = await create_job(
            app_session_factory,
            org_id,
            data=b"\x89PNG\r\n\x1a\n" + bytes(64),
            filename="photo.png",
        )
        async with app_session_factory() as session:
            await set_current_org(session, org_id)
            job = await session.get(ParseJob, job_id)
            resume = await session.get(ResumeFile, job.resume_file_id)
            await process_parse_job(
                session, job, resume, extractor=FakeExtractor([])
            )
            await session.commit()

        job = await load_job(app_session_factory, job_id, org_id)
        assert job.status == ParseJobStatus.NEEDS_REVIEW
        assert job.reason == "extraction:image_unreadable"

    async def test_real_pdf_text_reaches_the_extractor(self, app_session_factory):
        """The OSS extraction layer feeds the model — a real (tiny) PDF's text
        must arrive at the extractor verbatim."""
        from tests.conftest import seed_org_with_admin

        org_id, _ = await seed_org_with_admin(app_session_factory)
        pdf = make_pdf(
            [
                "John Doe",
                "Senior Backend Engineer",
                "Skills: Python, PostgreSQL, Docker, Kubernetes",
                "Experience: Acme Corp 2020-2024, Beta Inc 2018-2020",
            ]
        )
        job_id, _ = await create_job(
            app_session_factory, org_id, data=pdf, filename="resume.pdf"
        )
        seen: list[str] = []

        class RecordingExtractor:
            async def extract(self, text, *, model, repair=None):
                seen.append(text)
                return extraction_payload()

        async with app_session_factory() as session:
            await set_current_org(session, org_id)
            job = await session.get(ParseJob, job_id)
            resume = await session.get(ResumeFile, job.resume_file_id)
            await process_parse_job(
                session, job, resume, extractor=RecordingExtractor()
            )
            await session.commit()

        assert any("John Doe" in text for text in seen)
