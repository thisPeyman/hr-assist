"""Resume CRUD preserves extracted detail and tenant boundaries."""

import pytest

from app.main import app
from app.parsing.llm import get_extractor

from .factories import extraction_payload
from .test_ingest_api import install_extractor, signup, upload


@pytest.fixture(autouse=True)
def clear_extractor():
    yield
    app.dependency_overrides.pop(get_extractor, None)


async def test_resume_list_edit_delete(api_client):
    await signup(api_client, "workspace@example.com", "Workspace")
    install_extractor([extraction_payload()])
    uploaded = (await upload(api_client, b"Resume with Python skills", "person.txt")).json()
    listing = await api_client.get("/api/resumes")
    assert listing.status_code == 200
    item = listing.json()["items"][0]
    resume_id = item["id"]
    assert item["filename"] == "person.txt"
    detail = (await api_client.get(f"/api/resumes/{resume_id}")).json()
    work = detail["profile"]["work_experience"]
    updated = await api_client.patch(
        f"/api/resumes/{resume_id}",
        json={"full_name": "Corrected name", "email": "corrected@example.com", "skills": ["React"]},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["candidate_name"] == "Corrected name"
    assert updated.json()["profile"]["work_experience"] == work
    assert (await api_client.delete(f"/api/resumes/{resume_id}")).status_code == 204
    assert (await api_client.get(f"/api/resumes/{resume_id}")).status_code == 404
    assert (await api_client.get("/api/resumes")).json()["items"] == []
    candidate_id = uploaded["candidate"]["id"]
    assert (await api_client.get(f"/api/candidates/{candidate_id}")).status_code == 404


async def test_resume_crud_is_tenant_scoped(api_client):
    await signup(api_client, "owner@example.com", "Owner")
    install_extractor([extraction_payload()])
    await upload(api_client, b"Owner resume Python", "private.txt")
    resume_id = (await api_client.get("/api/resumes")).json()["items"][0]["id"]
    await api_client.post("/auth/logout")
    await signup(api_client, "other@example.com", "Other")
    assert (await api_client.get("/api/resumes")).json()["items"] == []
    assert (await api_client.get(f"/api/resumes/{resume_id}")).status_code == 404
    assert (
        await api_client.patch(f"/api/resumes/{resume_id}", json={"full_name": "Forged"})
    ).status_code == 404
    assert (await api_client.delete(f"/api/resumes/{resume_id}")).status_code == 404


async def test_resume_cursor_and_search(api_client):
    await signup(api_client, "pages@example.com", "Pages")
    install_extractor(
        [
            extraction_payload(
                contact={
                    "full_name": f"Person {index}",
                    "email": f"person{index}@example.com",
                    "phone": None,
                }
            )
            for index in range(3)
        ]
    )
    for index in range(3):
        await upload(api_client, f"Resume with Python skills {index}".encode(), f"file{index}.txt")
    first = (await api_client.get("/api/resumes", params={"limit": 2})).json()
    assert len(first["items"]) == 2 and first["next_cursor"]
    second = (
        await api_client.get("/api/resumes", params={"limit": 2, "before": first["next_cursor"]})
    ).json()
    assert len(second["items"]) == 1
    assert {item["id"] for item in first["items"]}.isdisjoint(
        item["id"] for item in second["items"]
    )
    filtered = (await api_client.get("/api/resumes", params={"search": "file1"})).json()
    assert [item["filename"] for item in filtered["items"]] == ["file1.txt"]
