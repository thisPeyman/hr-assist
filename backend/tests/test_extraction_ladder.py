"""Pipeline seam: the retry ladder (spec §7.3, research 02 §5).

pydantic validation → one repair-retry on the same model → escalate →
`needs_review`, never a drop. Transport failures retry once on the
escalation model (model churn resilience), then land in `failed`.
"""

import json
from types import SimpleNamespace

import pytest

from app.config import settings
from app.parsing.llm import (
    ExtractorError,
    OpenAIResumeExtractor,
    _api_error_reason,
    run_extraction_ladder,
)
from app.parsing.prompt import PROMPT_VERSION
from app.parsing.schema import SCHEMA_VERSION

from .factories import extraction_payload, invalid_payload

TEXT = "پیمان رضایی — Senior Backend Engineer"


class FakeExtractor:
    """Scripted responses; records every call for ladder verification."""

    def __init__(self, script: list):
        self.script = list(script)
        self.calls: list[dict] = []

    async def extract(self, text: str, *, model: str, repair: list[str] | None = None):
        self.calls.append({"text": text, "model": model, "repair": repair})
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


class TestHappyPaths:
    async def test_clean_document_succeeds_first_try(self):
        extractor = FakeExtractor([extraction_payload()])
        outcome = await run_extraction_ladder(extractor, TEXT)
        assert outcome.kind == "ok"
        assert outcome.attempts == 1
        assert outcome.model == settings.resume_extract_model
        assert outcome.extraction.contact.full_name == "پیمان رضایی"
        assert extractor.calls[0]["repair"] is None

    async def test_versions_carried_on_outcome(self):
        extractor = FakeExtractor([extraction_payload()])
        outcome = await run_extraction_ladder(extractor, TEXT)
        assert outcome.prompt_version == PROMPT_VERSION
        assert outcome.schema_version == SCHEMA_VERSION
        assert outcome.raw_json["contact"]["full_name"] == "پیمان رضایی"


class TestRepairLadder:
    async def test_invalid_then_repair_retry_same_model_succeeds(self):
        extractor = FakeExtractor([invalid_payload(), extraction_payload()])
        outcome = await run_extraction_ladder(extractor, TEXT)
        assert outcome.kind == "ok"
        assert outcome.attempts == 2
        # The repair retry runs on the SAME model and carries the errors.
        assert extractor.calls[1]["model"] == settings.resume_extract_model
        assert extractor.calls[1]["repair"], "repair call must carry validation errors"

    async def test_two_failures_then_escalation_succeeds(self):
        extractor = FakeExtractor(
            [invalid_payload(), invalid_payload(), extraction_payload()]
        )
        outcome = await run_extraction_ladder(extractor, TEXT)
        assert outcome.kind == "ok"
        assert outcome.attempts == 3
        assert outcome.model == settings.resume_extract_model_escalation
        assert extractor.calls[2]["model"] == settings.resume_extract_model_escalation

    async def test_all_three_fail_lands_invalid_never_raises(self):
        extractor = FakeExtractor([invalid_payload()] * 3)
        outcome = await run_extraction_ladder(extractor, TEXT)
        assert outcome.kind == "invalid"
        assert outcome.attempts == 3
        assert outcome.model == settings.resume_extract_model_escalation
        assert outcome.validation_errors, "errors feed ticket-20 review context"
        # The last (invalid) payload is kept — partial data for the queue.
        assert outcome.raw_json == invalid_payload()


class TestTransportErrors:
    async def test_forbidden_access_is_normalized_and_not_escalated(self):
        error = RuntimeError("Forbidden")
        error.status_code = 403
        reason = _api_error_reason(error)
        assert reason == "provider_access_denied"
        outcome = await run_extraction_ladder(FakeExtractor([ExtractorError(reason)]), TEXT)
        assert outcome.kind == "api_error" and outcome.attempts == 1

    @pytest.mark.parametrize("provider", ["ollama", "groq"])
    async def test_chat_provider_vision_uses_schema_and_image(self, monkeypatch, provider):
        model = "qwen3-vl:4b" if provider == "ollama" else "qwen/qwen3.8-27b"

        class FakeCompletions:
            async def create(self, **kwargs):
                assert kwargs["model"] == model
                assert kwargs["response_format"]["type"] == "json_schema"
                assert kwargs["messages"][1]["content"][1]["image_url"]["url"].startswith(
                    "data:image/png;base64,"
                )
                return SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(extraction_payload())))]
                )

        monkeypatch.setattr(settings, "resume_ai_provider", provider)
        client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
        payload = await OpenAIResumeExtractor(client).extract_images(
            "", [b"image"], model=model
        )
        assert payload["contact"]["full_name"] == "پیمان رضایی"

    async def test_exhausted_credit_stops_without_escalation(self):
        extractor = FakeExtractor([ExtractorError("credit_balance_exhausted")])
        outcome = await run_extraction_ladder(extractor, TEXT)
        assert outcome.kind == "api_error"
        assert outcome.error == "credit_balance_exhausted"
        assert outcome.attempts == 1

    def test_billing_code_is_kept_without_verbose_api_response(self):
        error = RuntimeError("verbose provider response")
        error.body = {"code": "credit_balance_exhausted"}
        assert _api_error_reason(error) == "credit_balance_exhausted"

    async def test_transport_error_jumps_to_escalation(self):
        extractor = FakeExtractor(
            [ExtractorError("connection reset"), extraction_payload()]
        )
        outcome = await run_extraction_ladder(extractor, TEXT)
        assert outcome.kind == "ok"
        assert outcome.attempts == 2
        assert outcome.model == settings.resume_extract_model_escalation

    async def test_transport_errors_everywhere_fail_explicitly(self):
        extractor = FakeExtractor(
            [ExtractorError("down"), ExtractorError("still down")]
        )
        outcome = await run_extraction_ladder(extractor, TEXT)
        assert outcome.kind == "api_error"
        assert "still down" in outcome.error
