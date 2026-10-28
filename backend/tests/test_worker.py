"""Worker seam: the Postgres jobs table as the queue (spec §7.3).

``SELECT … FOR UPDATE SKIP LOCKED`` is the whole concurrency story — no
Redis, no Celery. A crash mid-processing rolls the row back to ``pending``
and another worker simply picks it up again.
"""

import sqlalchemy as sa

from app.models import Candidate, ParseJob, ParseJobStatus, ResumeFile
from app.parsing.worker import claim_next_pending_job, drain_pending_jobs
from app.rls import set_current_org

from .factories import extraction_payload
from .test_pipeline import PERSIAN_RESUME, FakeExtractor, create_job


async def seed_two_pending_jobs(session_factory, org_id: str):
    first = await create_job(session_factory, org_id, data=PERSIAN_RESUME, filename="first.txt")
    second = await create_job(
        session_factory, org_id, data=PERSIAN_RESUME + b" v2", filename="second.txt"
    )
    return first, second


class TestClaimSkipsLockedRows:
    async def test_second_session_skips_row_locked_by_first(self, app_session_factory):
        from tests.conftest import seed_org_with_admin

        org_id, _ = await seed_org_with_admin(app_session_factory)
        first, second = await seed_two_pending_jobs(app_session_factory, org_id)

        # Session A claims the oldest job and holds the row lock (no commit).
        session_a = await app_session_factory().__aenter__()
        await set_current_org(session_a, org_id)
        claimed_a = await claim_next_pending_job(session_a)
        assert claimed_a.id == first[0]

        # Session B must SKIP the locked row and get the next one.
        async with app_session_factory() as session_b:
            await set_current_org(session_b, org_id)
            claimed_b = await claim_next_pending_job(session_b)
            assert claimed_b.id == second[0]

        # Releasing the lock puts the row back on the queue (crash = retry).
        await session_a.rollback()
        await app_session_factory().__aexit__(None, None, None)
        async with app_session_factory() as session_c:
            await set_current_org(session_c, org_id)
            reclaimed = await claim_next_pending_job(session_c)
            assert reclaimed.id == first[0]


class TestDrain:
    async def test_drains_all_pending_jobs_to_terminal(self, app_session_factory):
        from tests.conftest import seed_org_with_admin

        org_id, _ = await seed_org_with_admin(app_session_factory)
        for i in range(3):
            await create_job(
                app_session_factory,
                org_id,
                data=PERSIAN_RESUME + f"\n#{i}".encode(),
                filename=f"resume-{i}.txt",
            )

        processed = await drain_pending_jobs(
            app_session_factory,
            FakeExtractor(
                [
                    extraction_payload(
                        contact={
                            "full_name": f"Person {i}",
                            "email": f"person{i}@example.com",
                            "phone": None,
                        }
                    )
                    for i in range(3)
                ]
            ),
        )
        assert processed == 3

        async with app_session_factory() as session:
            await set_current_org(session, org_id)
            jobs = (await session.execute(sa.select(ParseJob))).scalars().all()
            assert {job.status for job in jobs} == {ParseJobStatus.EXTRACTED}
            candidates = (await session.execute(sa.select(Candidate))).scalars().all()
            assert len(candidates) == 3
            # Each resume linked to its candidate.
            resumes = (await session.execute(sa.select(ResumeFile))).scalars().all()
            assert all(resume.candidate_id is not None for resume in resumes)

    async def test_drain_with_empty_queue_returns_zero(self, app_session_factory):
        assert await drain_pending_jobs(app_session_factory, FakeExtractor([])) == 0
