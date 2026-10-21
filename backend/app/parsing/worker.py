"""Postgres-as-queue worker (spec §7.3): ``SELECT … FOR UPDATE SKIP LOCKED``.

One loop, two ways in: :func:`drain_pending_jobs` (process until empty —
tests and one-shot backfills) and :func:`run_worker_forever` (the long-lived
worker an async ingestion path — email-in, ticket 16 — or a separate worker
process runs). Single uploads never wait for it: the API's sync path runs
:func:`app.parsing.pipeline.process_parse_job` inline. No Redis, no Celery.
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.models import ParseJob, ParseJobStatus, ResumeFile
from app.parsing.llm import ResumeExtractor
from app.parsing.pipeline import process_parse_job
from app.rls import set_current_org

_FIND_OLDEST = (
    select(ParseJob.id, ParseJob.org_id)
    .where(ParseJob.status == ParseJobStatus.PENDING)
    .order_by(ParseJob.created_at, ParseJob.id)
    .limit(1)
)


async def claim_next_pending_job(session: AsyncSession) -> ParseJob | None:
    """Claim the oldest pending job for this transaction.

    Two phases, because RLS makes a one-shot claim impossible: pending rows
    are SELECT-visible across Orgs (queue policy) but ``FOR UPDATE`` also
    checks the UPDATE policy, which is Org-scoped. So: find the oldest
    pending row, pin its Org, then lock it — skipping rows another worker
    already holds (``SKIP LOCKED``). A raced row is retried via the next
    oldest until the queue is empty.
    """
    attempted: set = set()
    while True:
        row = (
            await session.execute(
                _FIND_OLDEST.where(ParseJob.id.not_in(attempted))
            )
        ).first()
        if row is None:
            return None
        job_id, org_id = row
        await set_current_org(session, org_id)
        job = (
            await session.execute(
                select(ParseJob)
                .where(ParseJob.id == job_id)
                .with_for_update(skip_locked=True)
            )
        ).scalar()
        if job is not None and job.status == ParseJobStatus.PENDING:
            return job
        attempted.add(job_id)


async def drain_pending_jobs(
    session_factory: async_sessionmaker, extractor: ResumeExtractor
) -> int:
    """Process every pending job once; returns how many were processed."""
    processed = 0
    while True:
        async with session_factory() as session:
            job = await claim_next_pending_job(session)
            if job is None:
                return processed
            # The GUC is transaction-local: pin the job's org before any
            # tenant read/write in this transaction.
            await set_current_org(session, job.org_id)
            resume_file = await session.get(ResumeFile, job.resume_file_id)
            await process_parse_job(session, job, resume_file, extractor=extractor)
            await session.commit()
            processed += 1


async def run_worker_forever(
    session_factory: async_sessionmaker,
    extractor: ResumeExtractor,
    poll_seconds: float | None = None,
) -> None:
    """Long-lived loop: drain, then poll. Cancel the task to stop."""
    poll = settings.worker_poll_seconds if poll_seconds is None else poll_seconds
    while True:
        processed = await drain_pending_jobs(session_factory, extractor)
        if processed == 0:
            await asyncio.sleep(poll)
