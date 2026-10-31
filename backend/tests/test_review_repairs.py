"""Public API regressions for the human ingestion paths."""

import copy

import pytest

from app.main import app
from app.parsing.llm import get_extractor

from .factories import extraction_payload
from .test_ingest_api import signup, upload
from .test_profile_merge_summary import install


@pytest.fixture(autouse=True)
def clear_override():
    yield
    app.dependency_overrides.pop(get_extractor, None)


async def test_review_reuses_identity_preserves_corrections_and_initializes_summary(api_client):
    await signup(api_client, "repair@example.com", "Repair")
    original = extraction_payload()
    invalid = extraction_payload(contact={"full_name": None, "email": None, "phone": None})
    fake = install([original, invalid])
    first = (await upload(api_client, b"Original resume Python")).json()
    candidate_id = first["candidate"]["id"]
    workspace_url = f"/api/candidates/{candidate_id}/workspace"
    old = (await api_client.get(workspace_url)).json()
    corrected = copy.deepcopy(old["profile"])
    corrected["headline"] = "Human correction"
    await api_client.put(f"/api/candidates/{candidate_id}/profile", json={"profile": corrected})
    second = (await upload(api_client, b"Another resume needing identity review")).json()
    accepted = await api_client.post(
        f"/api/review/{second['job']['id']}/resolve",
        json={"action": "accept", "extraction": original},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["candidate_id"] == candidate_id
    current = (await api_client.get(workspace_url)).json()
    assert current["profile"]["headline"] == "Human correction"
    assert any(c["field_path"] == "headline" for c in current["changes"])
    assert current["resume_version"] != old["resume_version"]
    assert current["summary"]["status"] == "ready"
    assert fake.summary_calls == 2


async def test_review_explicit_edits_require_current_baseline_and_retire_proposals(api_client):
    await signup(api_client, "safe@example.com", "Safe edits")
    payload = extraction_payload(needs_review=True)
    install([payload])
    uploaded = (await upload(api_client, b"Flagged resume Python")).json()
    cid, jid = uploaded["candidate"]["id"], uploaded["job"]["id"]
    url = f"/api/candidates/{cid}/workspace"
    profile = (await api_client.get(url)).json()["profile"]
    profile["headline"] = "First correction"
    await api_client.put(f"/api/candidates/{cid}/profile", json={"profile": profile})
    edited = copy.deepcopy(payload)
    edited["headline"] = "Explicit second correction"
    body = {
        "action": "accept",
        "extraction": edited,
        "edited_fields": ["headline"],
        "expected_values": {"headline": payload["headline"]},
    }
    stale = await api_client.post(f"/api/review/{jid}/resolve", json=body)
    assert stale.status_code == 409
    assert (await api_client.get(url)).json()["profile"]["headline"] == "First correction"
    body["expected_values"]["headline"] = "First correction"
    accepted = await api_client.post(f"/api/review/{jid}/resolve", json=body)
    assert accepted.status_code == 200, accepted.text
    current = (await api_client.get(url)).json()
    assert current["profile"]["headline"] == "Explicit second correction"
    assert not any(c["field_path"] == "headline" for c in current["changes"])
    assert len((await api_client.get("/api/resumes")).json()["items"]) == 1


async def test_manual_patch_creation_reuses_identity_version_and_summary(api_client):
    await signup(api_client, "patch@example.com", "Patch")
    fake = install([extraction_payload(contact={"full_name": None, "email": None, "phone": None})])
    await upload(api_client, b"Manual profile requiring a name")
    resume = (await api_client.get("/api/resumes")).json()["items"][0]
    response = await api_client.patch(
        f"/api/resumes/{resume['id']}",
        json={"full_name": "Human Name", "email": "identity@example.com", "skills": ["Python"]},
    )
    assert response.status_code == 200, response.text
    cid = response.json()["candidate_id"]
    current = (await api_client.get(f"/api/candidates/{cid}/workspace")).json()
    assert current["resume_version"]
    assert current["summary"]["status"] == "ready"
    assert fake.summary_calls == 1
    assert current["profile"]["work_experience"] == extraction_payload()["work_experience"]
    # A second unassigned file must attach to the same identity, not create a twin.
    fake.payloads.append(
        extraction_payload(contact={"full_name": None, "email": None, "phone": None})
    )
    await upload(api_client, b"A different manually corrected resume")
    second = (await api_client.get("/api/resumes")).json()["items"][0]
    updated = await api_client.patch(
        f"/api/resumes/{second['id']}",
        json={"full_name": "Human Name", "email": "IDENTITY@example.com"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["candidate_id"] == cid
    assert updated.json()["profile"]["skills"] == ["Python"]
    assert len((await api_client.get("/api/resumes")).json()["items"]) == 1
    assert fake.summary_calls == 2


async def test_profile_edit_supersedes_a_pending_proposal_even_if_value_later_returns(api_client):
    await signup(api_client, "proposal@example.com", "Proposals")
    install([extraction_payload(), extraction_payload(headline="New proposal")])
    first = (await upload(api_client, b"First version Python")).json()
    cid = first["candidate"]["id"]
    await upload(api_client, b"Second version Python")
    url = f"/api/candidates/{cid}/workspace"
    current = (await api_client.get(url)).json()
    change = next(c for c in current["changes"] if c["field_path"] == "headline")
    profile = current["profile"]
    original = profile["headline"]
    for value in ("Human correction", original):
        profile["headline"] = value
        await api_client.put(f"/api/candidates/{cid}/profile", json={"profile": profile})
    response = await api_client.post(
        f"/api/candidates/{cid}/changes/{change['id']}", json={"action": "accept"}
    )
    assert response.status_code == 409


async def test_old_review_cannot_replace_newer_resume(api_client):
    await signup(api_client, "old@example.com", "Out of order")
    invalid = extraction_payload(contact={"full_name": None, "email": None, "phone": None})
    install([invalid, invalid])
    old = (await upload(api_client, b"Older review document")).json()
    new = (await upload(api_client, b"Newer review document")).json()
    body = {"action": "accept", "extraction": extraction_payload()}
    accepted = await api_client.post(f"/api/review/{new['job']['id']}/resolve", json=body)
    cid = accepted.json()["candidate_id"]
    before = (await api_client.get(f"/api/candidates/{cid}/workspace")).json()
    rejected = await api_client.post(f"/api/review/{old['job']['id']}/resolve", json=body)
    assert rejected.status_code == 409
    after = (await api_client.get(f"/api/candidates/{cid}/workspace")).json()
    assert after["profile"] == before["profile"]
    assert after["resume_version"] == before["resume_version"]
    assert after["activity"] == before["activity"]


async def test_member_file_deletion_preserves_candidate_notes_and_activity(
    api_client, superuser_engine
):
    from sqlalchemy import text

    await signup(api_client, "member-delete@example.com", "Member deletion")
    install([extraction_payload()])
    uploaded = (await upload(api_client, b"Member resume deletion")).json()
    cid = uploaded["candidate"]["id"]
    await api_client.post(f"/api/candidates/{cid}/notes", json={"body": "Retained note"})
    before = (await api_client.get(f"/api/candidates/{cid}/workspace")).json()
    me = (await api_client.get("/api/me")).json()
    async with superuser_engine.begin() as conn:
        await conn.execute(
            text("update memberships set role='member' where user_id=:id"), {"id": me["id"]}
        )
    assert (await api_client.get("/api/me")).json()["role"] == "member"
    assert (await api_client.delete(f"/api/resumes/{before['resume_id']}")).status_code == 204
    after = (await api_client.get(f"/api/candidates/{cid}/workspace")).json()
    assert after["notes"] == before["notes"]
    assert {e["id"] for e in after["activity"]} >= {e["id"] for e in before["activity"]}
    assert after["resume_id"] is None


async def test_patch_stale_write_rejected_and_omitted_fields_preserved(api_client):
    await signup(api_client, "stale-patch@example.com", "Stale patch")
    install([extraction_payload()])
    uploaded = (await upload(api_client, b"Existing profile with headline")).json()
    cid = uploaded["candidate"]["id"]
    url = f"/api/candidates/{cid}/workspace"
    current = (await api_client.get(url)).json()
    resume_url = f"/api/resumes/{current['resume_id']}"
    name = current["profile"]["contact"]["full_name"]
    first = await api_client.patch(resume_url, json={"full_name": name, "headline": "First edit"})
    assert first.status_code == 200
    stale = await api_client.patch(
        resume_url,
        json={
            "full_name": name,
            "headline": "Stale edit",
            "expected_values": {
                "contact.full_name": name,
                "headline": current["profile"]["headline"],
            },
        },
    )
    assert stale.status_code == 409
    after = (await api_client.get(url)).json()
    assert after["profile"]["headline"] == "First edit"
    assert after["profile"]["contact"]["email"] == current["profile"]["contact"]["email"]
    assert after["profile"]["skills"] == current["profile"]["skills"]


async def test_review_summary_outage_is_cached_without_blocking_acceptance(api_client):
    await signup(api_client, "outage-review@example.com", "Review outage")
    fake = install([extraction_payload(contact={"full_name": None, "email": None})])
    uploaded = (await upload(api_client, b"Resume missing a name")).json()
    fake.fail_summary = True
    accepted = await api_client.post(
        f"/api/review/{uploaded['job']['id']}/resolve",
        json={"action": "accept", "extraction": extraction_payload()},
    )
    assert accepted.status_code == 200, accepted.text
    cid = accepted.json()["candidate_id"]
    for _ in range(2):
        current = (await api_client.get(f"/api/candidates/{cid}/workspace")).json()
        assert current["resume_version"]
        assert current["summary"]["status"] == "error"
    assert fake.summary_calls == 1


async def test_invalid_partial_extraction_can_be_corrected_without_losing_raw_data(api_client):
    await signup(api_client, "partial@example.com", "Invalid partial")
    malformed = {**extraction_payload(), "contact": "invalid contact"}
    install([malformed, malformed, malformed])
    uploaded = (await upload(api_client, b"Malformed partial extraction to review")).json()
    jid = uploaded["job"]["id"]
    before = (await api_client.get(f"/api/review/{jid}")).json()
    assert before["raw_json"]["contact"] == "invalid contact"
    response = await api_client.post(
        f"/api/review/{jid}/resolve", json={"action": "accept", "extraction": extraction_payload()}
    )
    assert response.status_code == 200, response.text
    assert (await api_client.get(f"/api/review/{jid}")).json()["raw_json"] == before["raw_json"]
