"""One persisted AI summary per resume SHA; reading never calls the model."""

import copy
import re
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import select

from app.ai.prompting import action_prompt
from app.config import settings
from app.models import ResumeSummary
from app.profiles import activity
from app.summary_facts import evidence_snapshot, meaningful, missing_labels, project_facts

PROMPT_VERSION = "v2"
GROUNDING_FIELDS = (
    "headline",
    "work_experience",
    "skills",
    "industries",
    "education",
    "languages",
    "certifications",
    "experience_years",
)
SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "unclear_or_missing": {"type": "array", "items": {"type": "string"}},
        "grounded_fields": {
            "type": "array",
            "items": {"type": "string", "enum": [*GROUNDING_FIELDS, "location"]},
        },
    },
    "required": ["text", "unclear_or_missing", "grounded_fields"],
    "additionalProperties": False,
}


class SummaryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    unclear_or_missing: list[str] = Field(max_length=20)
    grounded_fields: list[str]

    @field_validator("unclear_or_missing")
    @classmethod
    def persian_gaps(cls, value):
        if any(not re.search(r"[\u0600-\u06ff]", item) for item in value):
            raise ValueError("missing-information labels must be Persian")
        for item in value:
            guardrails(item)
        return value

    @field_validator("text")
    @classmethod
    def persian_and_length(cls, value):
        if not 120 <= len(value.split()) <= 180:
            raise ValueError("Persian summary must contain 120–180 words")
        if len(re.findall(r"[\u0600-\u06ff]", value)) < 100:
            raise ValueError("summary must be Persian")
        guardrails(value)
        return value

    @field_validator("grounded_fields")
    @classmethod
    def valid_evidence(cls, value, info):
        if any(field not in (*GROUNDING_FIELDS, "location") for field in value):
            raise ValueError("evidence must reference supplied fields")
        if info.context and any(not meaningful(info.context.get(field)) for field in value):
            raise ValueError("evidence field has no supplied value")
        return value


class GeneratedSummary(SummaryData):
    # Up to 20 validated model gaps plus 12 deterministic category/history gaps.
    unclear_or_missing: list[str] = Field(max_length=32)
    contract_version: int = 2
    facts: dict
    evidence: dict


def summary_prompt():
    return action_prompt("resume_summary", PROMPT_VERSION)


def guardrails(text):
    if re.search(
        r"\b(جنسیت|تأهل|مذهب|قومیت|نژاد|ملیت|معلولیت|بیماری|سن|متأهل|مجرد|"
        r"gender|religion|ethnicity|disability|age|nationality|marital\s+status|"
        r"race|health|appearance|family\s+status)\b",
        text,
        re.I,
    ):
        raise ValueError("protected characteristics must not appear")
    if any(
        phrase in text.casefold()
        for phrase in (
            "پیشنهاد استخدام",
            "بهترین گزینه",
            "مناسب استخدام",
            "استخدام او توصیه",
            "recommend hiring",
            "best candidate",
            "suitable for hiring",
            "hire this",
        )
    ):
        raise ValueError("summary must be descriptive, not evaluative")


def experience_years(profile):
    intervals = []
    for job in profile.get("work_experience") or []:
        start, end = job.get("start_date"), job.get("end_date")
        if job.get("current") and not end:
            end = datetime.now(UTC).date().isoformat()
        if not all(
            isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
            for value in (start, end)
        ):
            return None
        try:
            first, last = datetime.fromisoformat(start).date(), datetime.fromisoformat(end).date()
        except ValueError:
            return None
        if first > last or last > datetime.now(UTC).date():
            return None
        intervals.append((first, last))
    if not intervals:
        return None
    merged = []
    for first, last in sorted(intervals):
        if merged and first <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(last, merged[-1][1]))
        else:
            merged.append((first, last))
    return round(sum((last - first).days for first, last in merged) / 365.25, 1)


def grounding(profile):
    # Explicit allowlist: contact identifiers, photographs and raw text are excluded.
    data = {key: copy.deepcopy(profile.get(key)) for key in GROUNDING_FIELDS}
    data["location"] = (profile.get("contact") or {}).get("location")
    data["current_date"] = datetime.now(UTC).date().isoformat()
    data["experience_years"] = experience_years(profile)
    return data


async def generate_summary_data(profile, generator):
    method = getattr(generator, "summarize", None)
    if method is None:
        raise RuntimeError("summary_generator_unavailable")
    data = grounding(profile)
    repair = None
    for attempt in range(2):
        payload = await method(data, repair=repair)
        try:
            result = SummaryData.model_validate(payload, context=data)
            break
        except ValidationError as exc:
            if attempt == 1:
                raise
            repair = [error["msg"] for error in exc.errors()][:5]
    facts = project_facts(data)
    result.unclear_or_missing = list(
        dict.fromkeys(result.unclear_or_missing + missing_labels(data, facts))
    )
    return GeneratedSummary(
        **result.model_dump(), facts=facts, evidence=evidence_snapshot(data, facts)
    )


async def ensure_summary(
    session, candidate, version, profile, generator, *, force=False, actor=None
):
    row = (
        await session.execute(
            select(ResumeSummary).where(
                ResumeSummary.candidate_id == candidate.id, ResumeSummary.resume_version == version
            )
        )
    ).scalar_one_or_none()
    if row is not None and not force:
        return row
    if row is None:
        row = ResumeSummary(
            org_id=candidate.org_id,
            candidate_id=candidate.id,
            resume_version=version,
            status="pending",
            prompt_version=PROMPT_VERSION,
        )
        session.add(row)
    attempted_model = settings.resume_summary_model or settings.resume_extract_model
    try:
        result = await generate_summary_data(profile, generator)
        row.content = result.model_dump()
        # These columns describe the retained successful content, not a failed attempt.
        row.model = attempted_model
        row.prompt_version = PROMPT_VERSION
        row.status, row.error = "ready", None
        row.generated_at = datetime.now(UTC)
    except Exception as exc:
        row.status = "error"
        cause = exc.__cause__ or exc
        code = getattr(cause, "status_code", None)
        row.error = (
            "invalid_summary"
            if isinstance(exc, ValidationError)
            else {
                401: "provider_authentication_failed",
                403: "provider_access_denied",
                429: "provider_limit_reached",
            }.get(code, "summary_generation_unavailable")
        )
    if force:
        activity(
            session,
            candidate,
            "ai_summary_regenerated",
            actor,
            resume_version=version,
            status=row.status,
            model=attempted_model,
            prompt_version=PROMPT_VERSION,
        )
    await session.flush()
    return row
