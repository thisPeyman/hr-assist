"""One persisted AI summary per resume SHA; reading never calls the model."""

import copy
import re
from datetime import UTC, datetime

from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy import select

from app.ai.prompting import action_prompt
from app.config import settings
from app.models import ResumeSummary
from app.profiles import activity

PROMPT_VERSION = "v1"
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
        "grounded_fields": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["text", "unclear_or_missing", "grounded_fields"],
    "additionalProperties": False,
}


class SummaryData(BaseModel):
    text: str
    unclear_or_missing: list[str] = Field(max_length=20)
    grounded_fields: list[str] = Field(min_length=1)

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
    def valid_evidence(cls, value):
        if any(field not in (*GROUNDING_FIELDS, "location") for field in value):
            raise ValueError("evidence must reference supplied fields")
        return value


def summary_prompt():
    return action_prompt("resume_summary", PROMPT_VERSION)


def guardrails(text):
    if re.search(
        r"\b(جنسیت|تأهل|مذهب|قومیت|نژاد|ملیت|معلولیت|بیماری|سن|متأهل|مجرد|gender|religion|ethnicity|disability)\b",
        text,
        re.I,
    ):
        raise ValueError("protected characteristics must not appear")
    if any(
        phrase in text
        for phrase in ("پیشنهاد استخدام", "بهترین گزینه", "مناسب استخدام", "استخدام او توصیه")
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
            result = SummaryData.model_validate(payload)
            break
        except ValidationError as exc:
            if attempt == 1:
                raise
            repair = [error["msg"] for error in exc.errors()][:5]
    missing = {
        "headline": "عنوان حرفه‌ای",
        "work_experience": "سوابق کاری",
        "skills": "مهارت‌ها",
        "industries": "صنایع",
        "education": "تحصیلات",
        "languages": "زبان‌ها",
        "location": "محل زندگی",
    }
    result.unclear_or_missing = list(
        dict.fromkeys(
            result.unclear_or_missing
            + [
                f"{label} در رزومه ذکر نشده است"
                for key, label in missing.items()
                if not data.get(key)
            ]
        )
    )
    if data["experience_years"] is None:
        result.unclear_or_missing = list(
            dict.fromkeys(
                result.unclear_or_missing
                + ["سابقهٔ کل از تاریخ‌های رزومه به‌طور قطعی قابل محاسبه نیست"]
            )
        )
    return result


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
    row.model = settings.resume_summary_model or settings.resume_extract_model
    row.prompt_version = PROMPT_VERSION
    try:
        result = await generate_summary_data(profile, generator)
        row.content = result.model_dump()
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
            model=row.model,
            prompt_version=PROMPT_VERSION,
        )
    await session.flush()
    return row
