"""Candidate search at the public HTTP + actual pgvector/Postgres seam."""

import json

import pytest

from app.ai.actions import EmbeddingProvider, get_actions, get_embedding_provider
from app.config import settings
from app.main import app
from app.parsing.llm import get_extractor

from .factories import extraction_payload
from .test_ingest_api import signup, upload
from .test_profile_merge_summary import install


@pytest.fixture(autouse=True)
def clear_providers():
    yield
    app.dependency_overrides.pop(get_extractor, None)
    app.dependency_overrides.pop(get_actions, None)
    app.dependency_overrides.pop(get_embedding_provider, None)


def events(response):
    assert response.status_code == 200, response.text
    return [
        json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")
    ]


async def test_parse_failure_streams_visible_normalized_lexical_pool_results(api_client):
    await signup(api_client, "search@example.com", "Search")
    install([extraction_payload(contact={"full_name": "علي كريمي", "email": "ali@example.com"})])
    candidate = (await upload(api_client, b"Search lexical resume")).json()["candidate"]["id"]
    response = await api_client.post("/api/search", json={"query": "علی کریمی"})
    stream = events(response)
    assert stream[0]["type"] == "filters"
    assert stream[0]["mode"] == "lexical"
    assert stream[0]["warnings"] == ["SEARCH_PARSE_FAILED"]
    assert stream[0]["dsl"]["filters"] == []
    assert [item["candidate"]["id"] for item in stream if item["type"] == "candidate"] == [
        candidate
    ]
    assert stream[-1] == {"type": "done", "count": 1, "relax_filter_id": None}


def constraint(field, value, op="contains", softness=0, id="f1"):
    return {"id": id, "field": field, "op": op, "value": value, "constraint_softness": softness}


async def test_real_cosine_rrf_hard_numbers_negation_and_chip_only_sql(api_client, monkeypatch):
    monkeypatch.setattr(settings, "search_embedding_model", "test-multilingual")
    monkeypatch.setattr(settings, "search_embedding_dimensions", 3)
    embedded = []

    async def embed(self, value):
        embedded.append(value)
        return "[0,1,0]" if "java" in value else "[1,0,0]"

    monkeypatch.setattr(EmbeddingProvider, "embed", embed)
    await signup(api_client, "hybrid@example.com", "Hybrid")
    jobs = [
        {
            "title": "Engineer",
            "company": "Team",
            "start_date": "2015-01-01",
            "end_date": "2021-01-01",
            "current": False,
            "bullets": [],
        }
    ]
    install(
        [
            extraction_payload(
                contact={"full_name": "پیمان الف", "email": "a@example.com"},
                skills=["Python"],
                work_experience=jobs,
            ),
            extraction_payload(
                contact={"full_name": "پیمان ب", "email": "b@example.com"},
                skills=["Java"],
                work_experience=jobs,
            ),
            extraction_payload(
                contact={"full_name": "پیمان ج", "email": "c@example.com"},
                skills=["Python"],
                work_experience=[],
            ),
        ]
    )
    ids = [
        (await upload(api_client, f"Hybrid resume {i}".encode())).json()["candidate"]["id"]
        for i in range(3)
    ]
    embedded.clear()
    parsed_queries = []
    dsl = {
        "filters": [
            constraint("years_experience_total", "۵", "gte", id="f1"),
            constraint("skill", "Java", "not_contains", 0.8, "f2"),
        ],
        "semantic_query": "distributed systems",
    }

    class Parser:
        async def run(self, action, payload, schema):
            parsed_queries.append(payload)
            return dsl

    app.dependency_overrides[get_actions] = Parser
    result = events(
        await api_client.post(
            "/api/search", json={"query": "۵ سال سابقه بدون Java؛ distributed systems"}
        )
    )
    assert result[0]["dsl"]["filters"][0]["value"] == "5"
    assert [r["candidate"]["id"] for r in result if r["type"] == "candidate"] == [ids[0]]
    assert parsed_queries == ["5 سال سابقه بدون java؛ distributed systems"]
    assert embedded == ["distributed systems"]  # never numbers/negations/Profiles
    again = events(
        await api_client.post(
            "/api/search", json={"query": "۵ سال سابقه بدون Java؛ distributed systems"}
        )
    )
    assert again[-1]["count"] == 1 and len(parsed_queries) == 1
    # Editing a chip re-runs SQL including lexical residual, no embedding/reparse.
    embedded.clear()
    corrected = result[0]["dsl"]
    corrected["semantic_query"] = "python"
    corrected["filters"][0]["value"] = "7"
    empty = events(await api_client.post("/api/search", json={"dsl": corrected}))
    assert empty[-1] == {"type": "done", "count": 0, "relax_filter_id": "f2"}
    assert embedded == [] and len(parsed_queries) == 1
    # Relax removes the declared softest only; strict YOE remains enforced.
    relaxed = events(await api_client.post("/api/search", json={"dsl": corrected, "relax": True}))
    assert relaxed[0]["relaxed_filter_id"] == "f2" and relaxed[-1]["count"] == 0


async def test_vector_sql_failure_degrades_to_structured_lexical(api_client, monkeypatch):
    await signup(api_client, "vectorfail@example.com", "Vector failure")
    install([extraction_payload(skills=["Python"])])
    candidate = (await upload(api_client, b"Vector failure resume")).json()["candidate"]["id"]

    class Parser:
        async def run(self, *args):
            return {"filters": [constraint("skill", "python")], "semantic_query": "python"}

    class BrokenVector:
        model = "test"
        dimensions = 3

        async def embed(self, value):
            return "[broken]"  # malformed external response / SQL vector error

    app.dependency_overrides[get_actions] = Parser
    app.dependency_overrides[get_embedding_provider] = BrokenVector
    result = events(await api_client.post("/api/search", json={"query": "python"}))
    assert {"type": "warning", "code": "SEARCH_VECTOR_FAILED"} in result
    assert [r["candidate"]["id"] for r in result if r["type"] == "candidate"] == [candidate]


@pytest.mark.parametrize(
    "query",
    [
        "female backend",
        "gender_identity female",
        "date_of_birth 1990",
        "marital-status single",
        "مهندس زن",
        "جنسيت مرد",
        "زیر ۳۰ سال سن",
        "قوميت",
        "تابعیت ایرانی",
        "بدون معلولیت",
    ],
)
async def test_protected_queries_rejected_before_provider(api_client, query):
    await signup(api_client, "protected@example.com", "Protected")
    response = await api_client.post("/api/search", json={"query": query})
    assert response.status_code == 422


@pytest.mark.parametrize(
    "filter",
    [
        constraint("gender", "female"),
        constraint("skill", "جنسیت"),
        constraint("skill", "python", "gt"),
        constraint("stage", "fake", "eq"),
        constraint("years_experience_total", "5 OR true", "gte"),
        constraint("role_id", "not-a-uuid", "eq"),
        constraint("owner_id", "x", "contains"),
    ],
)
async def test_dsl_is_validated_in_code(api_client, filter):
    await signup(api_client, "validation@example.com", "Validation")
    response = await api_client.post("/api/search", json={"dsl": {"filters": [filter]}})
    assert response.status_code == 422


@pytest.mark.parametrize("residual", ["5 years", "۵ سال", "without java", "بدون جاوا", "نه پایتون"])
async def test_numeric_and_negated_residual_rejected(api_client, residual):
    await signup(api_client, "residual@example.com", "Residual")
    assert (
        await api_client.post("/api/search", json={"dsl": {"semantic_query": residual}})
    ).status_code == 422


async def test_pipeline_filters_share_one_application_and_negation_excludes_any_matching(
    api_client,
):
    from .test_pipeline_board import open_role

    await signup(api_client, "search-pipeline@example.com", "Pipeline search")
    install([extraction_payload()])
    candidate = (await upload(api_client, b"Pipeline search resume")).json()["candidate"]["id"]
    one, two = await open_role(api_client, "One"), await open_role(api_client, "Two")
    application = (
        await api_client.post(f"/api/roles/{one}/applications", json={"candidate_id": candidate})
    ).json()
    await api_client.post(f"/api/roles/{two}/applications", json={"candidate_id": candidate})
    stages = {s["kind"]: s for s in (await api_client.get("/api/pipeline/stages")).json()["items"]}
    await api_client.post(
        f"/api/applications/{application['id']}/stage",
        json={
            "stage_id": stages["interview"]["id"],
            "expected_stage_id": application["stage_id"],
        },
    )
    filters = [constraint("role_id", two, "eq"), constraint("stage", "interview", "eq", id="f2")]
    result = events(await api_client.post("/api/search", json={"dsl": {"filters": filters}}))
    assert result[-1]["count"] == 0  # no accidental cross-application AND
    filters[0]["value"] = one
    result = events(await api_client.post("/api/search", json={"dsl": {"filters": filters}}))
    assert result[-1]["count"] == 1
    result = events(
        await api_client.post(
            "/api/search",
            json={
                "dsl": {
                    "filters": [constraint("stage", "interview", "ne")],
                }
            },
        )
    )
    assert result[-1]["count"] == 0


async def test_accepted_edits_proposals_merge_and_typo_names_refresh_document(api_client):
    await signup(api_client, "search-edit@example.com", "Search edits")
    one = extraction_payload(
        contact={"full_name": "علی کریمی", "email": "ali@example.com"},
        skills=["Python"],
        work_experience=[
            {"title": "Engineer", "start_date": "2018-01-01", "end_date": "2022-01-01"},
            {"title": "Engineer", "start_date": "2020-01-01", "end_date": "2024-01-01"},
        ],
    )
    install([one, {**one, "skills": ["Rust"]}])
    candidate = (await upload(api_client, b"Search editing first")).json()["candidate"]["id"]
    result = events(await api_client.post("/api/search", json={"query": "علی کرمی"}))
    assert result[-1]["count"] == 1  # actual trgm typo, no substring/FTS match
    assert (
        next(r["candidate"] for r in result if r["type"] == "candidate")["years_experience_total"]
        == 5.9
    )
    await upload(api_client, b"Search editing second")
    rust = {"filters": [constraint("skill", "rust")]}
    assert events(await api_client.post("/api/search", json={"dsl": rust}))[-1]["count"] == 0
    workspace = (await api_client.get(f"/api/candidates/{candidate}/workspace")).json()
    change = next(c for c in workspace["changes"] if c["field_path"] == "skills")
    await api_client.post(
        f"/api/candidates/{candidate}/changes/{change['id']}", json={"action": "accept"}
    )
    assert events(await api_client.post("/api/search", json={"dsl": rust}))[-1]["count"] == 1
    profile = workspace["profile"]
    profile["skills"] = ["Go"]
    profile["work_experience"][0]["start_date"] = "2018"
    await api_client.put(f"/api/candidates/{candidate}/profile", json={"profile": profile})
    assert events(await api_client.post("/api/search", json={"dsl": rust}))[-1]["count"] == 0
    result = events(await api_client.post("/api/search", json={"dsl": {"filters": []}}))
    assert (
        next(r["candidate"] for r in result if r["type"] == "candidate")["years_experience_total"]
        is None
    )
    resume = workspace["resume_id"]
    patched = await api_client.patch(
        f"/api/resumes/{resume}", json={"full_name": "علی کریمی", "skills": ["Elixir"]}
    )
    assert patched.status_code == 200, patched.text
    assert (
        events(
            await api_client.post(
                "/api/search",
                json={
                    "dsl": {
                        "filters": [constraint("skill", "elixir")],
                    }
                },
            )
        )[-1]["count"]
        == 1
    )


async def test_relax_softest_is_actual_sql_action(api_client):
    await signup(api_client, "relax@example.com", "Relax")
    install([extraction_payload(skills=["Python"])])
    await upload(api_client, b"Relax resume")
    dsl = {
        "filters": [
            constraint("skill", "rust", softness=0.9),
            constraint("location", "تهران", softness=0.1, id="f2"),
        ]
    }
    assert events(await api_client.post("/api/search", json={"dsl": dsl}))[-1]["count"] == 0
    result = events(await api_client.post("/api/search", json={"dsl": dsl, "relax": True}))
    assert result[0]["relaxed_filter_id"] == "f1"
    assert result[0]["dsl"]["filters"] == [dsl["filters"][1]]
    assert result[-1]["count"] == 1


async def test_tenant_cache_and_vector_ranking_never_leak(api_client, monkeypatch):
    from httpx import ASGITransport, AsyncClient

    monkeypatch.setattr(settings, "search_embedding_model", "tenant-test")
    monkeypatch.setattr(settings, "search_embedding_dimensions", 3)

    async def embed(self, value):
        return "[1,0,0]" if "python" in value else "[0,1,0]"

    monkeypatch.setattr(EmbeddingProvider, "embed", embed)
    calls = []

    class Parser:
        async def run(self, action, payload, schema):
            calls.append(payload)
            return {"filters": [], "semantic_query": "python"}

    app.dependency_overrides[get_actions] = Parser
    await signup(api_client, "tenant-one@example.com", "One")
    install(
        [
            extraction_payload(
                contact={"full_name": "Java person", "email": "java@example.com"}, skills=["Java"]
            ),
            extraction_payload(
                contact={"full_name": "Python person", "email": "python@example.com"},
                skills=["Python"],
            ),
        ]
    )
    ids = [
        (await upload(api_client, f"Tenant one resume {i}".encode())).json()["candidate"]["id"]
        for i in range(2)
    ]
    result = events(await api_client.post("/api/search", json={"query": "python"}))
    ranked = [r["candidate"]["id"] for r in result if r["type"] == "candidate"]
    assert ranked == [ids[1], ids[0]]  # lexical + cosine wins RRF, nonlexical semantic survives
    assert calls == ["python"]

    # No lexical hits: cosine alone orders Java before Python for [0,1,0].
    class SemanticOnly:
        async def run(self, *args):
            return {"filters": [], "semantic_query": "event driven"}

    app.dependency_overrides[get_actions] = SemanticOnly
    semantic = events(await api_client.post("/api/search", json={"query": "event driven"}))
    assert [r["candidate"]["id"] for r in semantic if r["type"] == "candidate"] == ids
    app.dependency_overrides[get_actions] = Parser
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as other:
        await signup(other, "tenant-two@example.com", "Two")
        install([extraction_payload(skills=["Python"])])
        theirs = (await upload(other, b"Tenant two resume")).json()["candidate"]["id"]
        result = events(await other.post("/api/search", json={"query": "python"}))
        assert [r["candidate"]["id"] for r in result if r["type"] == "candidate"] == [theirs]
        assert calls == ["python", "python"]  # same query, different tenant cache
        assert (
            await other.post("/api/search/index", json={"candidate_ids": [ids[0]]})
        ).status_code == 404
    again = events(await api_client.post("/api/search", json={"query": "python"}))
    assert again[-1]["count"] == 2 and len(calls) == 2


async def test_failed_embedding_can_be_explicitly_retried_and_model_change_is_not_mislabeled(
    api_client, monkeypatch
):
    await signup(api_client, "reindex@example.com", "Reindex")
    install([extraction_payload()])
    candidate = (await upload(api_client, b"Retry embedding resume")).json()["candidate"]["id"]
    monkeypatch.setattr(settings, "search_embedding_model", "model-v2")
    monkeypatch.setattr(settings, "search_embedding_dimensions", 3)
    calls = []

    async def embed(self, value):
        calls.append(value)
        return "[1,0,0]"

    monkeypatch.setattr(EmbeddingProvider, "embed", embed)
    response = await api_client.post("/api/search/index", json={"candidate_ids": [candidate]})
    assert response.status_code == 200, response.text
    indexed = response.json()["items"][0]
    assert indexed["embedding_status"] == "ready"
    assert indexed["embedding_model"] == "model-v2" and indexed["embedding_dimensions"] == 3
    assert indexed["computed_at"] and len(calls) == 1
    await api_client.post("/api/search/index", json={"candidate_ids": [candidate]})
    assert len(calls) == 1  # unchanged successful model/content is cached
    monkeypatch.setattr(settings, "search_embedding_model", "model-v3")

    async def fail(self, value):
        raise RuntimeError("provider offline")

    monkeypatch.setattr(EmbeddingProvider, "embed", fail)
    result = (
        await api_client.post("/api/search/index", json={"candidate_ids": [candidate]})
    ).json()["items"][0]
    assert result["embedding_status"] == "unavailable" and result["embedding_model"] == "model-v3"

    # No stale v2 vector is claimed as a v3 success.
    class Parser:
        async def run(self, *args):
            return {"filters": [], "semantic_query": "python"}

    app.dependency_overrides[get_actions] = Parser
    result = events(await api_client.post("/api/search", json={"query": "python"}))
    assert {"type": "warning", "code": "SEARCH_VECTOR_FAILED"} in result
    assert result[-1]["count"] == 1


async def test_real_configurable_adapters_send_query_only_and_use_real_pgvector(
    api_client, monkeypatch
):
    from types import SimpleNamespace

    import app.ai.actions as transport

    monkeypatch.setattr(settings, "search_query_model", "cheap-query-model")
    monkeypatch.setattr(settings, "search_api_key", "test-only")
    monkeypatch.setattr(settings, "search_base_url", "http://query.invalid/v1")
    monkeypatch.setattr(settings, "search_embedding_model", "multilingual-embed")
    monkeypatch.setattr(settings, "search_embedding_dimensions", 3)
    monkeypatch.setattr(settings, "search_embedding_api_key", "test-only")
    monkeypatch.setattr(settings, "search_embedding_base_url", "http://embed.invalid/v1")
    calls = []

    class SDK:
        def __init__(self, **kwargs):
            self.base_url = kwargs["base_url"]
            self.embeddings = self
            self.chat = SimpleNamespace(completions=self)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def create(self, **kwargs):
            calls.append((self.base_url, kwargs))
            if "messages" in kwargs:
                return SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(
                                content=json.dumps(
                                    {
                                        "filters": [
                                            constraint("years_experience_total", "۲", "gte")
                                        ],
                                        "semantic_query": "python",
                                    }
                                )
                            )
                        )
                    ]
                )
            return SimpleNamespace(data=[SimpleNamespace(embedding=[1.0, 0.0, 0.0])])

    monkeypatch.setattr(transport, "AsyncOpenAI", SDK)
    await signup(api_client, "adapter@example.com", "Adapter")
    install([extraction_payload()])
    candidate = (await upload(api_client, b"Adapter resume private content")).json()["candidate"][
        "id"
    ]
    result = events(await api_client.post("/api/search", json={"query": "پایتون، ۲ سال سابقه"}))
    assert result[-1]["count"] == 1
    assert next(r["candidate"]["id"] for r in result if r["type"] == "candidate") == candidate
    parse_call = next(payload for base, payload in calls if base == "http://query.invalid/v1")
    assert parse_call["model"] == "cheap-query-model"
    assert parse_call["messages"][-1] == {"role": "user", "content": "پایتون، 2 سال سابقه"}
    assert "پیمان" not in str(parse_call) and "peyman@example.com" not in str(parse_call)
    assert parse_call["response_format"]["json_schema"]["strict"] is True
    assert calls[-1] == (
        "http://embed.invalid/v1",
        {
            "model": "multilingual-embed",
            "dimensions": 3,
            "input": "python",
        },
    )


async def test_review_acceptance_and_merge_refresh_search_truth(api_client):
    await signup(api_client, "review-search@example.com", "Review search")
    review = extraction_payload(
        needs_review=True,
        skills=["Rust"],
        contact={
            "full_name": "Reviewed",
            "email": "reviewed@example.com",
        },
    )
    target_profile = extraction_payload(
        skills=["Python"],
        industries=[],
        contact={
            "full_name": "Target",
            "email": "target@example.com",
        },
    )
    source_profile = extraction_payload(
        skills=[],
        industries=["Robotics"],
        contact={
            "full_name": "Source",
            "email": "source@example.com",
        },
    )
    install([review, target_profile, source_profile])
    submitted = (await upload(api_client, b"Needs review search resume")).json()
    review["skills"] = ["Elixir"]
    rust = {"filters": [constraint("skill", "elixir")]}
    assert events(await api_client.post("/api/search", json={"dsl": rust}))[-1]["count"] == 0
    resolved = await api_client.post(
        f"/api/review/{submitted['job']['id']}/resolve",
        json={
            "action": "accept",
            "extraction": review,
            "edited_fields": ["skills"],
            "expected_values": {"skills": ["Rust"]},
        },
    )
    assert resolved.status_code == 200, resolved.text
    assert events(await api_client.post("/api/search", json={"dsl": rust}))[-1]["count"] == 1
    target = (await upload(api_client, b"Merge search target")).json()["candidate"]["id"]
    source = (await upload(api_client, b"Merge search source")).json()["candidate"]["id"]
    merged = await api_client.post(f"/api/candidates/{source}/merge", json={"target_id": target})
    assert merged.status_code == 200, merged.text
    result = events(
        await api_client.post(
            "/api/search",
            json={
                "dsl": {
                    "filters": [constraint("industry", "robotics")],
                }
            },
        )
    )
    assert [r["candidate"]["id"] for r in result if r["type"] == "candidate"] == [target]
    lexical = events(await api_client.post("/api/search", json={"query": "Robotics"}))
    assert [r["candidate"]["id"] for r in lexical if r["type"] == "candidate"] == [target]


@pytest.mark.parametrize("query", ["without Java", "پنج سال سابقه", "۵ سال تجربه"])
async def test_parser_cannot_silently_drop_numbers_or_negation(api_client, query):
    await signup(api_client, "omitted@example.com", "Omitted")

    class Parser:
        async def run(self, *args):
            return {"filters": [], "semantic_query": "backend"}

    class NeverEmbed:
        model = "unused"
        dimensions = 3

        async def embed(self, value):
            pytest.fail("invalid numeric/negated interpretation must not reach embeddings")

    app.dependency_overrides[get_actions] = Parser
    app.dependency_overrides[get_embedding_provider] = NeverEmbed
    result = events(await api_client.post("/api/search", json={"query": query}))
    assert result[0]["mode"] == "lexical" and result[0]["warnings"] == ["SEARCH_PARSE_FAILED"]


@pytest.mark.parametrize(
    ("op", "value", "count"),
    [
        ("gt", "2", 1),
        ("gte", "2.4", 1),
        ("lt", "2.4", 0),
        ("lte", "2.4", 1),
        ("eq", "2.4", 1),
        ("ne", "2.4", 0),
    ],
)
async def test_all_numeric_operators_are_sql_hard_predicates(api_client, op, value, count):
    await signup(api_client, "numeric@example.com", "Numeric")
    install([extraction_payload()])
    await upload(api_client, b"Numeric SQL resume")
    result = events(
        await api_client.post(
            "/api/search",
            json={
                "dsl": {
                    "filters": [constraint("years_experience_total", value, op)],
                }
            },
        )
    )
    assert result[-1]["count"] == count
    injection = events(
        await api_client.post(
            "/api/search",
            json={
                "dsl": {
                    "filters": [constraint("skill", "%' OR true --")],
                }
            },
        )
    )
    assert injection[-1]["count"] == 0


async def test_zwnj_arabic_chars_and_numerals_normalize_sql_and_lexical(api_client):
    await signup(api_client, "normalization@example.com", "Normalize")
    install([extraction_payload(skills=["نسخه‌۲"], industries=["فین‌تک"])])
    await upload(api_client, b"Normalization resume")
    dsl = {
        "filters": [
            constraint("skill", "نسخه 2", "eq"),
            constraint("industry", "فین تک", "eq", id="f2"),
        ]
    }
    assert events(await api_client.post("/api/search", json={"dsl": dsl}))[-1]["count"] == 1
    lexical = events(await api_client.post("/api/search", json={"query": "نسخه ٢"}))
    assert lexical[0]["mode"] == "lexical" and lexical[-1]["count"] == 1


@pytest.mark.parametrize("embedding", [[0.0, 0.0, 0.0], [1.0, 0.0], [float("inf"), 0.0, 0.0]])
async def test_real_embedding_adapter_rejects_invalid_external_vectors(
    api_client, monkeypatch, embedding
):
    from types import SimpleNamespace

    import app.ai.actions as transport

    monkeypatch.setattr(settings, "search_embedding_model", "validated")
    monkeypatch.setattr(settings, "search_embedding_api_key", "test-only")
    monkeypatch.setattr(settings, "search_embedding_dimensions", 3)

    class SDK:
        def __init__(self, **kwargs):
            self.embeddings = self

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def create(self, **kwargs):
            return SimpleNamespace(data=[SimpleNamespace(embedding=embedding)])

    monkeypatch.setattr(transport, "AsyncOpenAI", SDK)
    await signup(api_client, "invalid-vector@example.com", "Invalid vector")
    install([extraction_payload()])
    candidate = (await upload(api_client, b"Invalid embedding resume")).json()["candidate"]["id"]
    response = await api_client.post("/api/search/index", json={"candidate_ids": [candidate]})
    assert response.status_code == 200, response.text
    assert response.json()["items"][0]["embedding_status"] == "unavailable"

    class Parser:
        async def run(self, *args):
            return {"filters": [], "semantic_query": "python"}

    app.dependency_overrides[get_actions] = Parser
    result = events(await api_client.post("/api/search", json={"query": "python"}))
    assert {"type": "warning", "code": "SEARCH_VECTOR_FAILED"} in result
    assert result[-1]["count"] == 1
