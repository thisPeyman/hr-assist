"""Pipeline seam: the retry ladder (spec §7.3, research 02 §5).

pydantic validation → one repair-retry on the same model → escalate →
`needs_review`, never a drop. Transport failures retry once on the
escalation model (model churn resilience), then land in `failed`.
"""

from app.config import settings
from app.parsing.llm import ExtractorError, run_extraction_ladder
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
