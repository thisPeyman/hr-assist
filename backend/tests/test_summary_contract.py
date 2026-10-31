"""Summary coverage is application-owned; model prose is not a factuality oracle."""

import copy
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.main import app
from app.models import ResumeSummary
from app.parsing.llm import OpenAIResumeExtractor, get_extractor
from app.rls import set_current_org

from .factories import extraction_payload
from .test_ingest_api import signup, upload
from .test_profile_merge_summary import SUMMARY_TEXT, Extractor, install


@pytest.fixture(autouse=True)
def clear_override():
    yield
    app.dependency_overrides.pop(get_extractor, None)


async def test_summary_projects_supplied_categories_and_persists_snapshot(
    api_client, app_session_factory
):
    await signup(api_client, "coverage@example.com", "Coverage")
    fake = install(
        [
            extraction_payload(
                headline="Platform Engineer",
                work_experience=[
                    {
                        "title": "Engineer",
                        "company": "Past Labs",
                        "current": False,
                        "start_date": "2020-01-01",
                        "end_date": "2022-01-01",
                        "location": "Tabriz",
                    },
                    {
                        "title": "Consultant",
                        "company": "Now Labs",
                        "current": True,
                        "start_date": "2021-01-01",
                        "end_date": "2023-01-01",
                        "location": "Remote",
                    },
                    {
                        "title": "Advisor",
                        "company": "Other Labs",
                        "current": True,
                        "start_date": "2022-01-01",
                        "end_date": "2023-01-01",
                    },
                ],
            )
        ]
    )
    candidate = (await upload(api_client, b"Coverage resume in English")).json()["candidate"]["id"]
    url = f"/api/candidates/{candidate}/workspace"
    workspace = (await api_client.get(url)).json()
    summary = workspace["summary"]
    assert summary["status"] == "ready"
    assert summary["coverage_status"] == "structured_v2"
    facts = summary["content"]["facts"]
    assert set(facts) == {
        "headline",
        "current_titles",
        "current_employers",
        "experience_years",
        "skills",
        "employers",
        "industries",
        "education",
        "languages",
        "residence",
        "locations",
    }
    assert facts["headline"]["items"] == [{"value": "Platform Engineer", "evidence": ["headline"]}]
    assert facts["current_titles"]["items"] == [
        {
            "value": "Consultant",
            "evidence": ["work_experience.1.title", "work_experience.1.current"],
        },
        {"value": "Advisor", "evidence": ["work_experience.2.title", "work_experience.2.current"]},
    ]
    assert [item["value"] for item in facts["current_employers"]["items"]] == [
        "Now Labs",
        "Other Labs",
    ]
    assert facts["experience_years"]["items"][0]["value"] == 3.0
    assert summary["content"]["evidence"]["work_experience.0.start_date"] == "2020-01-01"
    assert summary["content"]["evidence"]["work_experience.1.current"] is True
    assert [item["value"] for item in facts["locations"]["items"]] == ["تهران", "Tabriz", "Remote"]
    assert all(category["state"] == "supplied" for category in facts.values())
    me = (await api_client.get("/api/me")).json()
    async with app_session_factory() as session:
        await set_current_org(session, me["org"]["id"])
        row = (await session.execute(select(ResumeSummary))).scalar_one()
        assert row.content == summary["content"]
    edited = workspace["profile"]
    edited["headline"] = "Human correction"
    assert (
        await api_client.put(f"/api/candidates/{candidate}/profile", json={"profile": edited})
    ).status_code == 200
    assert (await api_client.get(url)).json()["summary"] == summary
    assert fake.summary_calls == 1
    duplicate = await upload(api_client, b"Coverage resume in English")
    assert duplicate.json()["candidate"]["id"] == candidate
    assert (await api_client.get(url)).json()["summary"] == summary
    assert fake.summary_calls == 1
    await api_client.post(f"/api/candidates/{candidate}/summary/regenerate")
    regenerated = (await api_client.get(url)).json()["summary"]
    assert regenerated["content"]["facts"]["headline"]["items"][0]["value"] == "Human correction"
    assert fake.summary_calls == 2


async def test_sparse_nested_gaps_and_partial_current_jobs(api_client):
    await signup(api_client, "sparse-summary@example.com", "Sparse")
    install(
        [
            extraction_payload(
                headline=None,
                education=[{}],
                languages=[{}, {"proficiency": "B2"}],
                industries=[],
                skills=["SQL"],
                contact={"full_name": "Person", "email": "sparse@example.com", "location": None},
                work_experience=[
                    {
                        "title": "Past title",
                        "company": "Past employer",
                        "current": False,
                        "location": "Tabriz",
                        "start_date": "2020",
                        "end_date": "2022",
                    },
                    {"current": True},
                    {"current": True, "title": "Advisor", "company": "Current employer"},
                ],
            )
        ]
    )
    candidate = (await upload(api_client, b"Sparse structured resume")).json()["candidate"]["id"]
    summary = (await api_client.get(f"/api/candidates/{candidate}/workspace")).json()["summary"]
    assert summary["status"] == "ready"
    facts = summary["content"]["facts"]
    for key in (
        "headline",
        "education",
        "languages",
        "industries",
        "residence",
        "experience_years",
    ):
        assert facts[key] == {"state": "unknown", "items": []}
    assert facts["current_titles"] == {
        "state": "partial",
        "items": [
            {
                "value": "Advisor",
                "evidence": ["work_experience.2.title", "work_experience.2.current"],
            }
        ],
    }
    assert facts["current_employers"]["state"] == "partial"
    assert facts["locations"]["items"] == [
        {"value": "Tabriz", "evidence": ["work_experience.0.location"]}
    ]
    gaps = " ".join(summary["content"]["unclear_or_missing"])
    for label in ("عنوان شغلی فعلی", "کارفرمای فعلی", "محل زندگی", "تحصیلات", "زبان‌ها", "سابقهٔ کل"):
        assert label in gaps


class SummaryPayloadExtractor(Extractor):
    def __init__(self, payload, output):
        super().__init__([payload])
        self.output = output
        self.repairs = []

    async def summarize(self, data, *, repair=None):
        self.summary_calls += 1
        self.repairs.append(repair)
        return copy.deepcopy(self.output)


@pytest.mark.parametrize(
    "change",
    [
        {"grounded_fields": ["certifications"]},  # valid name, absent evidence
        {"grounded_fields": ["work_experience.99.title"]},
        {"current_employer": "Invented Labs"},  # model cannot author deterministic fields
        {"experience_years": 99},
        {"facts": {"headline": "Invented"}},
        {"text": "An English-only summary " * 45},
        {"text": " ".join(SUMMARY_TEXT.split()[:119])},
        {"text": " ".join((SUMMARY_TEXT + " " + SUMMARY_TEXT).split()[:181])},
        *[
            {"text": SUMMARY_TEXT + " " + phrase}
            for phrase in (
                "age",
                "nationality",
                "marital status",
                "recommend hiring",
                "بهترین گزینه",
                "جنسیت",
            )
        ],
        {"unclear_or_missing": ["nationality در رزومه مشخص نیست"]},
        {"unclear_or_missing": ["پیشنهاد استخدام"]},
    ],
)
async def test_invalid_summary_repairs_once_then_caches_safe_failure(api_client, change):
    await signup(api_client, "invalid-summary@example.com", "Invalid")
    output = {
        "text": SUMMARY_TEXT,
        "unclear_or_missing": [],
        "grounded_fields": ["skills"],
        **change,
    }
    fake = SummaryPayloadExtractor(extraction_payload(certifications=[]), output)
    app.dependency_overrides[get_extractor] = lambda: fake
    uploaded = (await upload(api_client, b"Invalid output test resume")).json()
    assert uploaded["job"]["status"] == "extracted"
    candidate = uploaded["candidate"]["id"]
    for _ in range(2):
        summary = (await api_client.get(f"/api/candidates/{candidate}/workspace")).json()["summary"]
        assert summary["status"] == "error"
        assert summary["error"] == "invalid_summary"
        assert summary["content"] is None
        assert summary["coverage_status"] == "unavailable"
    assert fake.summary_calls == 2
    assert fake.repairs[0] is None and fake.repairs[1]


@pytest.mark.parametrize("words", [120, 180])
async def test_summary_accepts_word_boundaries_and_empty_evidence(api_client, words):
    await signup(api_client, "boundary@example.com", "Boundary")
    output = {
        "text": " ".join((SUMMARY_TEXT + " " + SUMMARY_TEXT).split()[:words]),
        "unclear_or_missing": [f"ابهام در بخش شمارهٔ {index}" for index in range(20)],
        "grounded_fields": [],
    }
    fake = SummaryPayloadExtractor(
        extraction_payload(
            headline=None,
            work_experience=[],
            skills=[],
            industries=[],
            education=[],
            languages=[],
            certifications=[],
            contact={"full_name": "Person"},
        ),
        output,
    )
    app.dependency_overrides[get_extractor] = lambda: fake
    candidate = (await upload(api_client, b"Empty professional profile")).json()["candidate"]["id"]
    summary = (await api_client.get(f"/api/candidates/{candidate}/workspace")).json()["summary"]
    assert summary["status"] == "ready"
    assert all(
        value == {"state": "unknown", "items": []} for value in summary["content"]["facts"].values()
    )
    assert fake.summary_calls == 1


async def test_failed_forced_generation_retains_success_provenance_and_legacy_cache(
    api_client,
    app_session_factory,
    monkeypatch,
):
    import app.summaries as summaries
    from app.config import settings

    await signup(api_client, "provenance@example.com", "Provenance")
    fake = install([extraction_payload()])
    candidate = (await upload(api_client, b"Retained summary provenance")).json()["candidate"]["id"]
    url = f"/api/candidates/{candidate}/workspace"
    initial = (await api_client.get(url)).json()["summary"]
    monkeypatch.setattr(settings, "resume_summary_model", "new-model")
    monkeypatch.setattr(summaries, "PROMPT_VERSION", "v-next-test")
    fake.fail_summary = True
    response = await api_client.post(f"/api/candidates/{candidate}/summary/regenerate")
    assert response.status_code == 200
    assert response.json() == {"status": "error", "error": "summary_generation_unavailable"}
    workspace = (await api_client.get(url)).json()
    failed = workspace["summary"]
    for key in ("content", "generated_at", "model", "prompt_version"):
        assert failed[key] == initial[key]
    events = [
        item for item in workspace["activity"] if item["event_type"] == "ai_summary_regenerated"
    ]
    assert len(events) == 1
    assert events[0]["data"]["status"] == "error"
    assert events[0]["data"]["model"] == "new-model"
    assert events[0]["data"]["prompt_version"] == "v-next-test"
    assert fake.summary_calls == 2
    fake.fail_summary = False
    assert (await api_client.post(f"/api/candidates/{candidate}/summary/regenerate")).json()[
        "status"
    ] == "ready"
    recovered = (await api_client.get(url)).json()["summary"]
    assert recovered["error"] is None and recovered["model"] == "new-model"
    assert recovered["prompt_version"] == "v-next-test"
    # Simulate a pre-contract stored row, not a paid backfill on GET.
    me = (await api_client.get("/api/me")).json()
    async with app_session_factory() as session:
        await set_current_org(session, me["org"]["id"])
        row = (await session.execute(select(ResumeSummary))).scalar_one()
        row.content = {
            key: value
            for key, value in row.content.items()
            if key not in {"facts", "contract_version"}
        }
        row.prompt_version = "v1"
        await session.commit()
    for _ in range(2):
        legacy = (await api_client.get(url)).json()["summary"]
        assert legacy["coverage_status"] == "legacy_unverified"
        assert "facts" not in legacy["content"]
        assert legacy["status"] == "ready"
    assert fake.summary_calls == 3


@pytest.mark.parametrize("provider", ["openai", "groq"])
async def test_summary_http_uses_configured_transport_and_action_aware_repair(
    api_client,
    monkeypatch,
    provider,
):
    from app.config import settings

    await signup(api_client, "transport@example.com", "Transport")
    # Upload through the real API first; then manually regenerate with the production
    # adapter and a fake SDK boundary. Neither branch opens a socket.
    install([extraction_payload(summary="PRIVATE RAW SUMMARY")])
    candidate = (await upload(api_client, b"Private raw resume blob")).json()["candidate"]["id"]
    calls = []

    async def create(**kwargs):
        calls.append(kwargs)
        output = {
            "text": SUMMARY_TEXT,
            "unclear_or_missing": [],
            "grounded_fields": ["location"] if len(calls) > 1 else ["not_a_field"],
        }
        encoded = json.dumps(output)
        return SimpleNamespace(
            output_text=encoded, choices=[SimpleNamespace(message=SimpleNamespace(content=encoded))]
        )

    sdk = SimpleNamespace(
        responses=SimpleNamespace(create=create),
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
    )
    monkeypatch.setattr(settings, "resume_ai_provider", provider)
    monkeypatch.setattr(settings, "resume_summary_model", "configured-summary-model")
    adapter = OpenAIResumeExtractor(client=sdk)
    app.dependency_overrides[get_extractor] = lambda: adapter
    result = await api_client.post(f"/api/candidates/{candidate}/summary/regenerate")
    assert result.json() == {"status": "ready", "error": None}
    assert len(calls) == 2
    for request in calls:
        assert request["model"] == "configured-summary-model"
        if provider == "openai":
            prompt = request["instructions"]
            schema = request["text"]["format"]
            grounding_text = request["input"][-1]["content"]
        else:
            prompt = request["messages"][0]["content"]
            schema = request["response_format"]["json_schema"]
            grounding_text = request["messages"][-1]["content"]
        assert "contract v2" in prompt and "untrusted" in prompt
        assert schema["strict"] is True
        assert schema["schema"]["additionalProperties"] is False
        assert "location" in schema["schema"]["properties"]["grounded_fields"]["items"]["enum"]
        for private in (
            "peyman@example.com",
            "+98 912",
            "PRIVATE RAW SUMMARY",
            "Private raw resume blob",
            "full_name",
        ):
            assert private not in grounding_text
    assert "Correct the resume summary" in str(calls[1])
    assert "Re-extract the resume" not in str(calls[1])
