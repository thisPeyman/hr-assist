"""The structured-extraction contract (research 02 §4, spec §7.3).

Three representations of one contract, deliberately kept together:

- :class:`ResumeExtractionData` — the pydantic validator. Everything is optional
  (nullable) except the routing triple ``is_resume``/``confidence``/
  ``needs_review``: the pipeline degrades, it never crashes on partial data.
- :func:`strict_json_schema` — the OpenAI wire format. Strict structured
  outputs require ``additionalProperties: false`` and every property listed
  in ``required`` at every object level; nullable fields become
  ``anyOf: [T, null]`` which strict mode accepts.
- :func:`build_profile` — Python post-processing: dates normalize to ISO
  prefixes only when confidently Gregorian; everything else stays verbatim,
  in the resume's own language (spec §3 — never translated).

``schema_version`` bumps whenever the contract changes; the pipeline stores
it per row (spec §7.3).
"""

import re

from pydantic import BaseModel, ConfigDict, Field, ValidationError

SCHEMA_VERSION = 1

_ENGLISH_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

# [0-9] (not \d): \d also matches Persian digits, and a Jalali date like
# «۱۴۰۱/۰۵» must never match a "confidently Gregorian" pattern.
_ISO_DAY = re.compile(r"^([0-9]{4})-([0-9]{1,2})-([0-9]{1,2})$")
_ISO_MONTH = re.compile(r"^([0-9]{4})[-/]([0-9]{1,2})$")
_YEAR = re.compile(r"^([0-9]{4})$")
_ENGLISH_MONTH_YEAR = re.compile(r"^([A-Za-z]+)\.? ([0-9]{4})$")


def normalize_date(value: str | None) -> str | None:
    """Normalize a date string to an ISO prefix when — and only when — it is
    confidently Gregorian. Persian-calendar dates (۱۴۰۱, «مهر ۱۴۰۱») and any
    other fragment stay verbatim: reinterpreting a Jalali date as Gregorian
    would silently corrupt work history."""
    if value is None:
        return None
    text = value.strip()
    if not text:
        return value

    if match := _ISO_DAY.match(text):
        y, m, d = match.groups()
        if not (1 <= int(m) <= 12 and 1 <= int(d) <= 31):
            return value
        return f"{y}-{int(m):02d}-{int(d):02d}"
    if match := _ISO_MONTH.match(text):
        y, m = match.groups()
        if not (1 <= int(m) <= 12):
            return value
        return f"{y}-{int(m):02d}"
    if match := _YEAR.match(text):
        return match.group(1)
    if match := _ENGLISH_MONTH_YEAR.match(text):
        name, year = match.groups()
        month = _ENGLISH_MONTHS.get(name[:3].lower())
        if month is not None:
            return f"{year}-{month:02d}"
    return value


# --------------------------------------------------------------------------
# Pydantic contract
# --------------------------------------------------------------------------


class Link(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str | None = None
    url: str | None = None


class Contact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    links: list[Link] | None = None


class WorkExperience(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    company: str | None = None
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    current: bool = False
    bullets: list[str] | None = None


class Education(BaseModel):
    model_config = ConfigDict(extra="forbid")

    degree: str | None = None
    field: str | None = None
    institution: str | None = None
    start_date: str | None = None
    end_date: str | None = None


class Certification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    issuer: str | None = None
    date: str | None = None


class Language(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: str | None = None
    proficiency: str | None = None


class ResumeExtractionData(BaseModel):
    """Wire contract for the one structured-output call (research 02 §4).

    Named …Data to stay distinct from the ORM's ``ResumeExtraction`` row
    (app.models) — same domain concept, different layers.
    """

    model_config = ConfigDict(extra="forbid")

    is_resume: bool
    confidence: float = Field(ge=0.0, le=1.0)
    needs_review: bool
    contact: Contact
    headline: str | None = None
    summary: str | None = None
    work_experience: list[WorkExperience]
    education: list[Education]
    skills: list[str]
    industries: list[str]
    certifications: list[Certification]
    languages: list[Language]
    document_language: str | None = None
    extraction_notes: list[str]


# --------------------------------------------------------------------------
# Strict JSON schema (OpenAI wire format)
# --------------------------------------------------------------------------


def strict_json_schema() -> dict:
    """Pydantic's schema, converted for OpenAI strict structured outputs."""
    schema = ResumeExtractionData.model_json_schema()
    return _to_strict(schema, defs=schema.get("$defs", {}))


# Strict structured outputs reject keywords outside their supported subset
# (numeric bounds, patterns, formats…). Our pydantic validator enforces all
# of these on our side of the wire, so they are dropped from the wire schema.
_UNSUPPORTED_KEYWORDS = frozenset(
    {
        "title",
        "default",
        "$defs",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
        "minLength",
        "maxLength",
        "pattern",
        "format",
        "minItems",
        "maxItems",
    }
)


def _to_strict(node: dict, defs: dict) -> dict:
    if not isinstance(node, dict):
        return node
    if "$ref" in node:
        return _to_strict(defs[node["$ref"].removeprefix("#/$defs/")], defs)
    out: dict = {}
    for key, value in node.items():
        if key in _UNSUPPORTED_KEYWORDS:
            continue
        if key == "anyOf":
            out["anyOf"] = [_to_strict(branch, defs) for branch in value]
        elif key == "items":
            out["items"] = _to_strict(value, defs)
        elif key == "properties" and isinstance(value, dict):
            out["properties"] = {k: _to_strict(v, defs) for k, v in value.items()}
        else:
            out[key] = value
    if "properties" in out:
        # Strict mode: every property required; optionality is expressed as
        # nullable types, which the anyOf branches carry.
        out["required"] = list(out["properties"])
        out["additionalProperties"] = False
    return out


# --------------------------------------------------------------------------
# Post-processing → the HR-editable Profile (GLOSSARY)
# --------------------------------------------------------------------------


def _dated(model: BaseModel, *date_fields: str) -> dict:
    """model_dump with the date fields normalized — work experience,
    education, and certifications all share this shape."""
    dump = model.model_dump(exclude=set(date_fields))
    for field in date_fields:
        dump[field] = normalize_date(getattr(model, field))
    return dump


def build_profile(extraction: ResumeExtractionData) -> dict:
    """The structured, HR-editable Profile of a Candidate's latest resume.

    Routing fields (is_resume/confidence/needs_review) stay on the parse job;
    the Profile carries only what HR sees and edits. Dates normalize here —
    the raw model JSON is never mutated (re-parse campaigns stay possible).
    """
    return {
        "contact": extraction.contact.model_dump(),
        "headline": extraction.headline,
        "summary": extraction.summary,
        "work_experience": [
            _dated(job, "start_date", "end_date") for job in extraction.work_experience
        ],
        "education": [
            _dated(item, "start_date", "end_date") for item in extraction.education
        ],
        "skills": extraction.skills,
        "industries": extraction.industries,
        "certifications": [
            _dated(cert, "date") for cert in extraction.certifications
        ],
        "languages": [lang.model_dump() for lang in extraction.languages],
        "document_language": extraction.document_language,
        "extraction_notes": extraction.extraction_notes,
    }


__all__ = [
    "SCHEMA_VERSION",
    "ResumeExtractionData",
    "ValidationError",
    "build_profile",
    "normalize_date",
    "strict_json_schema",
]