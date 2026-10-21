"""The one paid step: a strict structured-output OpenAI call (spec §7.3).

Seams kept deliberately narrow:

- :class:`ResumeExtractor` — the transport protocol
  (``extract(text, model=…, repair=…) -> dict``). Tests inject a fake;
  production uses :class:`OpenAIResumeExtractor` on the Responses API with
  ``json_schema`` strict mode, so malformed JSON is impossible and the
  repair ladder only fires on semantic validation failures.
- :func:`run_extraction_ladder` — the retry ladder as a pure function:
  workhorse → repair-retry (same model, validation errors appended) →
  escalation model → give up. Every failure kind is explicit; nothing
  raises out of the ladder.

Model names come from config, prompts from versioned files (spec §4.5).
"""

import json
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal, Protocol

from pydantic import ValidationError

from app.config import settings
from app.parsing.prompt import PROMPT_VERSION, load_system_prompt
from app.parsing.schema import (
    SCHEMA_VERSION,
    ResumeExtractionData,
    strict_json_schema,
)

_MAX_REPAIR_ERRORS = 8


class ExtractorError(Exception):
    """Transport/API failure — the SDK already retried; this is terminal."""


class ResumeExtractor(Protocol):
    async def extract(
        self, text: str, *, model: str, repair: list[str] | None = None
    ) -> dict: ...


class OpenAIResumeExtractor:
    """Production transport: one Responses API call per attempt.

    The client is constructed lazily so an unconfigured environment (no API
    key yet) degrades to explicit ``failed`` jobs instead of crashing the
    dependency wiring.
    """

    def __init__(self, client=None):
        self._provided_client = client
        self._client = client

    async def extract(
        self, text: str, *, model: str, repair: list[str] | None = None
    ) -> dict:
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(
                api_key=settings.openai_api_key, timeout=60.0
            )
        messages: list[dict] = []
        if repair:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Your previous extraction failed validation:\n"
                        + "\n".join(f"- {error}" for error in repair)
                        + "\n\nRe-extract the resume and return the corrected JSON."
                    ),
                }
            )
        messages.append({"role": "user", "content": text})
        try:
            response = await self._client.responses.create(
                model=model,
                instructions=load_system_prompt(),
                input=messages,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "resume_extraction",
                        "strict": True,
                        "schema": strict_json_schema(),
                    }
                },
            )
            return json.loads(response.output_text)
        except ExtractorError:
            raise
        except Exception as exc:  # noqa: BLE001 — any SDK/API failure
            raise ExtractorError(str(exc)) from exc


@lru_cache(maxsize=1)
def _default_extractor() -> OpenAIResumeExtractor:
    return OpenAIResumeExtractor()


async def get_extractor() -> ResumeExtractor:
    """FastAPI dependency — tests override it with a fake extractor."""
    return _default_extractor()


@dataclass
class LadderOutcome:
    kind: Literal["ok", "invalid", "api_error"]
    attempts: int = 0
    model: str | None = None
    prompt_version: str = PROMPT_VERSION
    schema_version: int = SCHEMA_VERSION
    extraction: ResumeExtractionData | None = None
    raw_json: dict | None = None  # last payload — kept even when invalid
    error: str | None = None
    validation_errors: list[str] = field(default_factory=list)


def _short_errors(exc: ValidationError) -> list[str]:
    errors = []
    for error in exc.errors()[:_MAX_REPAIR_ERRORS]:
        location = ".".join(str(part) for part in error["loc"]) or "(root)"
        errors.append(f"{location}: {error['msg']}")
    return errors


async def run_extraction_ladder(
    extractor: ResumeExtractor, text: str
) -> LadderOutcome:
    """Attempt plan (research 02 §5):

    1. workhorse model
    2. repair-retry on the SAME model, validation errors appended
    3. escalation model (also gets the errors)

    A transport failure jumps straight to the escalation entry (model churn
    resilience); a transport failure there is terminal ``api_error``. The
    ladder never raises and never drops the document — the caller maps
    ``invalid`` to ``needs_review`` and ``api_error`` to ``failed``.
    """
    plan = [
        # (model, is_escalation, with_repair_errors)
        (settings.resume_extract_model, False, False),
        (settings.resume_extract_model, False, True),
        (settings.resume_extract_model_escalation, True, True),
    ]
    outcome = LadderOutcome(kind="invalid")
    errors: list[str] = []
    transport_failed = False

    for model, is_escalation, with_repair in plan:
        if transport_failed and not is_escalation:
            continue  # same model just failed at transport; jump to escalation

        repair = errors if with_repair else None
        try:
            payload = await extractor.extract(text, model=model, repair=repair)
        except ExtractorError as exc:
            transport_failed = True
            outcome.model = model
            outcome.error = str(exc)
            outcome.attempts += 1
            continue

        try:
            extraction = ResumeExtractionData.model_validate(payload)
        except ValidationError as exc:
            errors.extend(_short_errors(exc))
            outcome.model = model
            outcome.attempts += 1
            outcome.raw_json = payload  # partial data for the review queue
            continue

        return LadderOutcome(
            kind="ok",
            attempts=outcome.attempts + 1,
            model=model,
            extraction=extraction,
            raw_json=payload,
        )

    if transport_failed:
        outcome.kind = "api_error"
    else:
        outcome.validation_errors = errors
    return outcome
