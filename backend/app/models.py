"""ORM models for the SaaS skeleton (spec §10).

Tenancy layout: ``orgs`` + ``users`` + ``memberships`` are reference tables
(app-layer scoped); ``org_activity`` is the first tenant-owned data table — it
carries ``org_id`` and is protected by Postgres RLS (migration 0002). Every
later tenant-owned table (candidates, roles, applications, …) follows the same
pattern.
"""

import enum
import uuid
from datetime import datetime

from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import UserDefinedType


class Base(DeclarativeBase):
    pass


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Org(Base):
    __tablename__ = "orgs"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MembershipRole(enum.Enum):
    ADMIN = "admin"
    MEMBER = "member"


class Membership(Base):
    __tablename__ = "memberships"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="cascade"), nullable=False, unique=True
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orgs.id", ondelete="cascade"), nullable=False, index=True
    )
    role: Mapped[MembershipRole] = mapped_column(
        Enum(
            MembershipRole,
            name="membership_role",
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
        default=MembershipRole.MEMBER,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class OrgActivity(Base):
    """Org-level Activity stream — append-only system events for admin actions."""

    __tablename__ = "org_activity"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orgs.id", ondelete="cascade"), nullable=False, index=True
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="set null"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AccessToken(Base):
    """Session tokens for fastapi-users' DatabaseStrategy (cookie auth)."""

    __tablename__ = "access_tokens"

    token: Mapped[str] = mapped_column(String(43), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="cascade"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


# --------------------------------------------------------------------------
# Ticket 11 — upload → parse → Candidate in the Talent Pool (spec §5, §12)
# --------------------------------------------------------------------------


class Candidate(Base):
    """A person + Profile in the org-wide Talent Pool (GLOSSARY)."""

    __tablename__ = "candidates"
    __table_args__ = (UniqueConstraint("org_id", "id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orgs.id", ondelete="cascade"), nullable=False, index=True
    )
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    headline: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    normalized_email: Mapped[str | None] = mapped_column(Text, index=True)
    normalized_phone: Mapped[str | None] = mapped_column(Text, index=True)
    human_fields: Mapped[list] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    latest_resume_version: Mapped[str | None] = mapped_column(String(64))
    new_resume_received: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    # Structured, HR-editable Profile (GLOSSARY) — raw model JSON lives in
    # resume_extractions; this is the reviewed source of truth.
    profile: Mapped[dict | None] = mapped_column(JSONB().with_variant(JSON(), "sqlite"))
    years_experience_total: Mapped[float | None] = mapped_column(Float)
    experience_computed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class CandidateActivity(Base):
    """Candidate-level Activity — append-only system events (GLOSSARY)."""

    __tablename__ = "candidate_activity"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orgs.id", ondelete="cascade"), nullable=False, index=True
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidates.id", ondelete="cascade"), nullable=False, index=True
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="set null"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ResumeFile(Base):
    """An uploaded resume: original bytes kept verbatim, deduped by SHA-256."""

    __tablename__ = "resume_files"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orgs.id", ondelete="cascade"), nullable=False, index=True
    )
    # Linked once the parse creates the Candidate (column-level grant).
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("candidates.id", ondelete="set null"), nullable=True, index=True
    )
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    __table_args__ = (UniqueConstraint("org_id", "sha256", name="resume_files_org_sha_key"),)


class ParseJobStatus(enum.Enum):
    """Every submitted document ends in an explicit terminal status (spec §4.2).
    ocr_applied/vision_used are recorded by ticket 21's routes; the enum ships
    complete so it never needs an ALTER."""

    PENDING = "pending"
    EXTRACTED = "extracted"
    OCR_APPLIED = "ocr_applied"
    VISION_USED = "vision_used"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"
    NOT_A_RESUME = "not_a_resume"


class ParseJob(Base):
    """One unit of parse work on the Postgres jobs table (spec §7.3)."""

    __tablename__ = "parse_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orgs.id", ondelete="cascade"), nullable=False, index=True
    )
    resume_file_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resume_files.id", ondelete="cascade"), nullable=False, index=True
    )
    status: Mapped[ParseJobStatus] = mapped_column(
        Enum(
            ParseJobStatus,
            name="parse_job_status",
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
        default=ParseJobStatus.PENDING,
    )
    attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    # Model/prompt/schema provenance per row (spec §7.3) — never load-bearing
    # in code (spec §4.5).
    model: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str | None] = mapped_column(Text)
    schema_version: Mapped[int | None] = mapped_column(Integer)
    reason: Mapped[str | None] = mapped_column(Text)  # terminal why, if not extracted
    extract_ms: Mapped[int | None] = mapped_column(Integer)
    llm_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ResumeExtraction(Base):
    """Raw text + raw model JSON kept for replay/re-parse campaigns (spec §7.3)."""

    __tablename__ = "resume_extractions"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orgs.id", ondelete="cascade"), nullable=False, index=True
    )
    parse_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("parse_jobs.id", ondelete="cascade"), nullable=False, index=True
    )
    resume_file_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resume_files.id", ondelete="cascade"), nullable=False, index=True
    )
    raw_text: Mapped[str | None] = mapped_column(Text)
    raw_json: Mapped[dict | None] = mapped_column(JSONB().with_variant(JSON(), "sqlite"))
    model: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str | None] = mapped_column(Text)
    schema_version: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class InboundMail(Base):
    """Durable raw-MIME receipt; only pending metadata is worker-visible."""

    __tablename__ = "inbound_mail"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orgs.id", ondelete="cascade"), nullable=False, index=True
    )
    message_id: Mapped[str] = mapped_column(Text, nullable=False)
    recipient: Mapped[str] = mapped_column(Text, nullable=False)
    raw_key: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    __table_args__ = (
        UniqueConstraint("message_id", "recipient", name="inbound_mail_delivery_key"),
    )


class ProfileChange(Base):
    __tablename__ = "profile_changes"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="cascade"), index=True)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidates.id", ondelete="cascade"), index=True
    )
    resume_version: Mapped[str] = mapped_column(String(64))
    field_path: Mapped[str] = mapped_column(Text)
    old_value: Mapped[object | None] = mapped_column(JSONB(none_as_null=True))
    new_value: Mapped[object | None] = mapped_column(JSONB(none_as_null=True))
    status: Mapped[str] = mapped_column(Text, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ResumeSummary(Base):
    __tablename__ = "resume_summaries"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="cascade"), index=True)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidates.id", ondelete="cascade"), index=True
    )
    resume_version: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(Text, default="pending")
    content: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str] = mapped_column(Text, default="v1")
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("candidate_id", "resume_version", name="summary_candidate_version_key"),
    )


class CandidateNote(Base):
    __tablename__ = "candidate_notes"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="cascade"), index=True)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidates.id", ondelete="cascade"), index=True
    )
    application_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    author_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="set null"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        ForeignKeyConstraint(
            ["org_id", "application_id"],
            ["candidate_applications.org_id", "candidate_applications.id"],
        ),
    )


class CandidateApplication(Base):
    """One canonical Candidate × Role; legacy title/stage retained as snapshots."""

    __tablename__ = "candidate_applications"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="cascade"), index=True)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidates.id", ondelete="cascade"), index=True
    )
    role_title: Mapped[str] = mapped_column(Text)
    stage: Mapped[str] = mapped_column(Text, default="received")
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    role_id: Mapped[uuid.UUID] = mapped_column(index=True)
    stage_id: Mapped[uuid.UUID] = mapped_column(index=True)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint("candidate_id", "role_id", name="application_candidate_role_key"),
        UniqueConstraint("org_id", "id"),
        ForeignKeyConstraint(["org_id", "role_id"], ["roles.org_id", "roles.id"]),
        ForeignKeyConstraint(
            ["org_id", "stage_id"], ["pipeline_stages.org_id", "pipeline_stages.id"]
        ),
        ForeignKeyConstraint(["org_id", "candidate_id"], ["candidates.org_id", "candidates.id"]),
    )


class ApplicationActivity(Base):
    """Immutable event payload; only application_id may change during Merge."""

    __tablename__ = "application_activity"
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="cascade"), index=True)
    application_id: Mapped[uuid.UUID] = mapped_column(index=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="set null")
    )
    event_type: Mapped[str] = mapped_column(Text)
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        ForeignKeyConstraint(
            ["org_id", "application_id"],
            ["candidate_applications.org_id", "candidate_applications.id"],
            ondelete="CASCADE",
        ),
    )


class PipelineStage(Base):
    __tablename__ = "pipeline_stages"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="cascade"), index=True)
    name: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)
    __table_args__ = (UniqueConstraint("org_id", "kind"), UniqueConstraint("org_id", "id"))


class Role(Base):
    __tablename__ = "roles"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="cascade"), index=True)
    title: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="draft")
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint("org_id", "id"),
        CheckConstraint("status in ('draft','open','paused','closed')"),
    )


class Vector(UserDefinedType):
    """Wire vector literals as text; cosine arithmetic stays in pgvector SQL."""

    cache_ok = True

    def get_col_spec(self, **kw):
        return "vector"


class CandidateSearchDoc(Base):
    __tablename__ = "candidate_search_docs"
    candidate_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    search_text: Mapped[str] = mapped_column(Text)
    normalized_name: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(Text)
    embedding: Mapped[str | None] = mapped_column(Vector())
    embedding_model: Mapped[str] = mapped_column(Text)
    embedding_dimensions: Mapped[int] = mapped_column(Integer)
    embedding_status: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(
            ["org_id", "candidate_id"], ["candidates.org_id", "candidates.id"], ondelete="CASCADE"
        ),
    )


class SearchQueryCache(Base):
    __tablename__ = "search_query_cache"
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orgs.id", ondelete="CASCADE"), primary_key=True
    )
    query_key: Mapped[str] = mapped_column(Text, primary_key=True)
    dsl: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
