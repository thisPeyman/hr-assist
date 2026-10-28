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

import base64
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


_NON_RETRYABLE_API_CODES = {
    "provider_access_denied",
    "provider_authentication_failed",
    "credit_balance_exhausted",
    "organization_spend_limit_exceeded",
    "project_spend_limit_exceeded",
    "organization_usage_limit_exceeded",
    "invalid_api_key",
}


def _api_error_reason(exc: Exception) -> str:
    if getattr(exc, "status_code", None) == 403:
        return "provider_access_denied"
    if getattr(exc, "status_code", None) == 401:
        return "provider_authentication_failed"
    body = getattr(exc, "body", None)
    code = body.get("code") if isinstance(body, dict) else None
    if code in _NON_RETRYABLE_API_CODES:
        return code
    return str(exc)


class ResumeExtractor(Protocol):
    async def extract(self, text: str, *, model: str, repair: list[str] | None = None) -> dict: ...


class OpenAIResumeExtractor:
    """Production transport: one Responses API call per attempt.

    The client is constructed lazily so an unconfigured environment (no API
    key yet) degrades to explicit ``failed`` jobs instead of crashing the
    dependency wiring.
    """

    def __init__(self, client=None):
        self._provided_client = client
        self._client = client

    async def extract(self, text: str, *, model: str, repair: list[str] | None = None) -> dict:
        return await self._extract(text, model=model, repair=repair)

    async def extract_images(
        self, text: str, images: list[bytes], *, model: str, repair: list[str] | None = None
    ) -> dict:
        return await self._extract(text, model=model, repair=repair, images=images)

    async def summarize(self, grounding: dict, *, repair: list[str] | None = None) -> dict:
        from app.summaries import SUMMARY_SCHEMA, summary_prompt

        return await self._extract(
            json.dumps(grounding, ensure_ascii=False),
            model=settings.resume_summary_model or settings.resume_extract_model,
            repair=repair,
            instructions=summary_prompt(),
            output_schema=SUMMARY_SCHEMA,
            schema_name="resume_summary",
        )

    async def _extract(
        self,
        text: str,
        *,
        model: str,
        repair: list[str] | None = None,
        images: list[bytes] | None = None,
        instructions: str | None = None,
        output_schema: dict | None = None,
        schema_name: str = "resume_extraction",
    ) -> dict:
        provider = settings.resume_ai_provider
        local = provider == "ollama"
        chat_provider = provider in {"ollama", "groq"}
        if self._client is None:
            from openai import AsyncOpenAI

            if provider == "openai" and not settings.openai_api_key:
                raise ExtractorError("openai_not_configured")
            if provider == "groq" and not settings.groq_api_key:
                raise ExtractorError("groq_not_configured")
            try:
                if local:
                    api_key, base_url = "ollama", settings.ollama_base_url
                elif provider == "groq":
                    api_key, base_url = settings.groq_api_key, settings.groq_base_url
                else:
                    api_key, base_url = settings.openai_api_key, settings.openai_base_url
                self._client = AsyncOpenAI(
                    api_key=api_key,
                    base_url=base_url,
                    timeout=300.0 if local else 60.0,
                    max_retries=0 if local else 2,
                )
            except Exception as exc:
                raise ExtractorError("openai_client_unavailable") from exc
        if chat_provider:
            user_text = text or "Extract this resume verbatim."
            if repair:
                user_text += "\n\nCorrect these validation errors: " + "; ".join(repair)
            user_content: str | list[dict] = user_text
            if images:
                user_content = [{"type": "text", "text": user_text}]
                for image in images:
                    encoded = base64.b64encode(image).decode("ascii")
                    user_content.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{encoded}"},
                        }
                    )
            try:
                response = await self._client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": instructions or load_system_prompt()},
                        {"role": "user", "content": user_content},
                    ],
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": schema_name,
                            "strict": True,
                            "schema": output_schema or strict_json_schema(),
                        },
                    },
                    temperature=0,
                )
                return json.loads(response.choices[0].message.content or "")
            except Exception as exc:  # noqa: BLE001 — local server/model failure
                raise ExtractorError(_api_error_reason(exc)) from exc
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
        content = [{"type": "input_text", "text": text or "Extract this resume verbatim."}]
        for image in images or []:
            encoded = base64.b64encode(image).decode("ascii")
            content.append({"type": "input_image", "image_url": f"data:image/png;base64,{encoded}"})
        messages.append({"role": "user", "content": content if images else text})
        try:
            response = await self._client.responses.create(
                model=model,
                instructions=instructions or load_system_prompt(),
                input=messages,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": schema_name,
                        "strict": True,
                        "schema": output_schema or strict_json_schema(),
                    }
                },
            )
            return json.loads(response.output_text)
        except ExtractorError:
            raise
        except Exception as exc:  # noqa: BLE001 — any SDK/API failure
            raise ExtractorError(_api_error_reason(exc)) from exc


class VisionResumeExtractor:
    def __init__(self, extractor: ResumeExtractor, images: list[bytes]):
        self.extractor = extractor
        self.images = images

    async def extract(self, text: str, *, model: str, repair: list[str] | None = None) -> dict:
        method = getattr(self.extractor, "extract_images", None)
        if method is None:
            raise ExtractorError("vision_unavailable")
        return await method(text, self.images, model=model, repair=repair)


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


async def run_extraction_ladder(extractor: ResumeExtractor, text: str) -> LadderOutcome:
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
            if outcome.error in _NON_RETRYABLE_API_CODES | {"openai_not_configured"}:
                break
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
