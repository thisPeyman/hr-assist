"""upload → parse → Candidate: Talent Pool + parsing tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-21

Ticket 11 (spec §5, §7.2–7.3, §12): candidates, candidate_activity,
resume_files, parse_jobs, resume_extractions. Every table is tenant-owned —
``org_id`` + RLS enabled AND forced, exactly like ``org_activity`` (0002) —
and the ``hr_app`` role gets least-privilege grants for the ingest loop.

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GUC_POLICY = """
    org_id = (select nullif(current_setting('app.current_org_id', true), '')::uuid)
"""

# Tenant-owned tables created here; every one gets the RLS treatment.
TABLES = [
    "candidates",
    "candidate_activity",
    "resume_files",
    "parse_jobs",
    "resume_extractions",
]


def upgrade() -> None:
    op.create_table(
        "candidates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orgs.id", ondelete="cascade"),
            nullable=False,
        ),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("headline", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("profile", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("candidates_org_id_idx", "candidates", ["org_id"])

    op.create_table(
        "candidate_activity",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orgs.id", ondelete="cascade"),
            nullable=False,
        ),
        sa.Column(
            "candidate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("candidates.id", ondelete="cascade"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="set null"),
            nullable=True,
        ),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column(
            "data",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("candidate_activity_org_id_idx", "candidate_activity", ["org_id"])
    op.create_index(
        "candidate_activity_candidate_id_idx", "candidate_activity", ["candidate_id"]
    )
    op.create_index(
        "candidate_activity_actor_user_id_idx", "candidate_activity", ["actor_user_id"]
    )

    op.create_table(
        "resume_files",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orgs.id", ondelete="cascade"),
            nullable=False,
        ),
        sa.Column(
            "candidate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("candidates.id", ondelete="set null"),
            nullable=True,
        ),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("bytes", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("org_id", "sha256", name="resume_files_org_sha_key"),
    )
    op.create_index("resume_files_org_id_idx", "resume_files", ["org_id"])
    op.create_index("resume_files_candidate_id_idx", "resume_files", ["candidate_id"])

    sa.Enum(
        "pending",
        "extracted",
        "ocr_applied",
        "vision_used",
        "needs_review",
        "failed",
        "not_a_resume",
        name="parse_job_status",
    )  # created with parse_jobs below
    op.create_table(
        "parse_jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orgs.id", ondelete="cascade"),
            nullable=False,
        ),
        sa.Column(
            "resume_file_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("resume_files.id", ondelete="cascade"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "extracted",
                "ocr_applied",
                "vision_used",
                "needs_review",
                "failed",
                "not_a_resume",
                name="parse_job_status",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("prompt_version", sa.Text(), nullable=True),
        sa.Column("schema_version", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("extract_ms", sa.Integer(), nullable=True),
        sa.Column("llm_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("parse_jobs_org_id_idx", "parse_jobs", ["org_id"])
    op.create_index(
        "parse_jobs_resume_file_id_idx", "parse_jobs", ["resume_file_id"]
    )
    # Queue claim: WHERE status = 'pending' ORDER BY created_at FOR UPDATE
    # SKIP LOCKED (spec §7.3).
    op.create_index("parse_jobs_status_idx", "parse_jobs", ["status", "created_at"])

    op.create_table(
        "resume_extractions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orgs.id", ondelete="cascade"),
            nullable=False,
        ),
        sa.Column(
            "parse_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("parse_jobs.id", ondelete="cascade"),
            nullable=False,
        ),
        sa.Column(
            "resume_file_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("resume_files.id", ondelete="cascade"),
            nullable=False,
        ),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("raw_json", postgresql.JSONB(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("prompt_version", sa.Text(), nullable=True),
        sa.Column("schema_version", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("resume_extractions_org_id_idx", "resume_extractions", ["org_id"])
    op.create_index(
        "resume_extractions_parse_job_id_idx", "resume_extractions", ["parse_job_id"]
    )
    op.create_index(
        "resume_extractions_resume_file_id_idx",
        "resume_extractions",
        ["resume_file_id"],
    )

    # The walking-skeleton tables relied on client-side UUID defaults only;
    # raw-SQL paths (worker backfills, admin imports) need a server default.
    op.execute("alter table users alter column id set default gen_random_uuid()")
    op.execute("alter table orgs alter column id set default gen_random_uuid()")

    # Least privilege for the ingest loop. resume_files.candidate_id is the
    # only column the pipeline ever mutates after INSERT.
    op.execute("grant select, insert on public.candidates to hr_app")
    op.execute("grant select, insert on public.candidate_activity to hr_app")
    op.execute("grant select, insert on public.resume_files to hr_app")
    op.execute("grant update (candidate_id) on public.resume_files to hr_app")
    op.execute("grant select, insert, update on public.parse_jobs to hr_app")
    op.execute("grant select, insert on public.resume_extractions to hr_app")
    op.execute("grant usage, select on sequence candidate_activity_id_seq to hr_app")
    op.execute("revoke all on all tables in schema public from public")

    # RLS belt-and-braces, same pattern as org_activity (0002).
    for table in TABLES:
        op.execute(f"alter table {table} enable row level security")
        op.execute(f"alter table {table} force row level security")
        op.execute(
            f"""
            create policy {table}_isolation on {table}
                for all to hr_app
                using ({GUC_POLICY.strip()})
                with check ({GUC_POLICY.strip()})
            """
        )
    # …with one deliberate carve-out: the jobs queue. A worker must see
    # pending rows across Orgs to claim them (SELECT … FOR UPDATE SKIP
    # LOCKED) before it knows which Org to pin. Pending rows carry queue
    # metadata only (no resume content — that lives in resume_files /
    # resume_extractions, which stay strictly Org-scoped), and every write
    # path remains gated by the isolation policy above.
    op.execute(
        """
        create policy parse_jobs_pending_queue_visible on parse_jobs
            for select to hr_app
            using (status = 'pending')
        """
    )


def downgrade() -> None:
    op.execute("alter table orgs alter column id drop default")
    op.execute("alter table users alter column id drop default")
    op.execute("drop policy if exists parse_jobs_pending_queue_visible on parse_jobs")
    for table in TABLES:
        op.execute(f"drop policy if exists {table}_isolation on {table}")
        op.execute(f"alter table {table} no force row level security")
        op.execute(f"alter table {table} disable row level security")
    op.execute("revoke all on all tables in schema public from hr_app")
    op.execute("revoke usage, select on sequence candidate_activity_id_seq from hr_app")
    op.drop_index(
        "resume_extractions_resume_file_id_idx", table_name="resume_extractions"
    )
    op.drop_index("resume_extractions_parse_job_id_idx", table_name="resume_extractions")
    op.drop_index("resume_extractions_org_id_idx", table_name="resume_extractions")
    op.drop_table("resume_extractions")
    op.drop_index("parse_jobs_status_idx", table_name="parse_jobs")
    op.drop_index("parse_jobs_resume_file_id_idx", table_name="parse_jobs")
    op.drop_index("parse_jobs_org_id_idx", table_name="parse_jobs")
    op.drop_table("parse_jobs")
    sa.Enum(
        "pending",
        "extracted",
        "ocr_applied",
        "vision_used",
        "needs_review",
        "failed",
        "not_a_resume",
        name="parse_job_status",
    ).drop(op.get_bind())
    op.drop_index("resume_files_candidate_id_idx", table_name="resume_files")
    op.drop_index("resume_files_org_id_idx", table_name="resume_files")
    op.drop_table("resume_files")
    op.drop_index(
        "candidate_activity_actor_user_id_idx", table_name="candidate_activity"
    )
    op.drop_index(
        "candidate_activity_candidate_id_idx", table_name="candidate_activity"
    )
    op.drop_index("candidate_activity_org_id_idx", table_name="candidate_activity")
    op.drop_table("candidate_activity")
    op.drop_index("candidates_org_id_idx", table_name="candidates")
    op.drop_table("candidates")
