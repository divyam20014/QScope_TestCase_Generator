from __future__ import annotations

import io

from app.requirements.models import ClassificationState, ExtractedRequirementLLM, ExtractionBatchLLM, RequirementType


def _create_project(client, name="Requirements Test Project"):
    return client.post("/api/projects", json={"name": name}).json()


def _upload(client, project_id, filename="spec.txt", content=b"REQ-1: The system shall allow login.\n"):
    return client.post(
        f"/api/projects/{project_id}/documents",
        files=[("files", (filename, io.BytesIO(content), "text/plain"))],
    ).json()[0]


def _fake_extraction(requirements):
    return ExtractionBatchLLM(requirements=requirements)


def test_extract_document_requires_existing_project(client):
    resp = client.post("/api/projects/does-not-exist/requirements/extract/doc-1")
    assert resp.status_code == 404


def test_extract_without_gemini_configured_returns_400(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    get_settings.cache_clear()

    project = _create_project(client)
    doc = _upload(client, project["id"])

    resp = client.post(f"/api/projects/{project['id']}/requirements/extract/{doc['id']}")
    assert resp.status_code == 400
    assert "GEMINI_API_KEY" in resp.json()["detail"]

    get_settings.cache_clear()


def test_extract_document_produces_requirements_with_source_refs_and_classification(client, monkeypatch):
    project = _create_project(client)
    doc = _upload(client, project["id"], content=b"REQ-1: The system shall allow login.\nThe system should be nice.\n")

    fake = _fake_extraction(
        [
            ExtractedRequirementLLM(
                source_chunk_index=0,
                source_id_hint="REQ-1",
                text="The system shall allow login.",
                requirement_type=RequirementType.FUNCTIONAL,
                classification_state=ClassificationState.CLEAR,
            ),
            ExtractedRequirementLLM(
                source_chunk_index=0,
                text="The system should be nice.",
                requirement_type=RequirementType.NON_FUNCTIONAL,
                classification_state=ClassificationState.NOT_TESTABLE,
                rationale="Too vague to derive a test case from.",
            ),
        ]
    )
    monkeypatch.setattr("app.requirements.extraction.ai_service.generate_json", lambda **kwargs: fake)

    resp = client.post(f"/api/projects/{project['id']}/requirements/extract/{doc['id']}")
    assert resp.status_code == 200
    requirements = resp.json()
    assert len(requirements) == 2

    clear_req = next(r for r in requirements if r["classification_state"] == "clear")
    assert clear_req["id"] == "REQ-1"
    assert clear_req["source"]["document_id"] == doc["id"]
    assert clear_req["source"]["document_name"] == "spec.txt"

    not_testable_req = next(r for r in requirements if r["classification_state"] == "not_testable")
    assert not_testable_req["id"].startswith("NFR-")
    assert not_testable_req["rationale"]

    list_resp = client.get(f"/api/projects/{project['id']}/requirements")
    assert len(list_resp.json()) == 2

    clarifications = client.get(f"/api/projects/{project['id']}/requirements/clarifications").json()
    assert len(clarifications) == 1
    assert clarifications[0]["requirement_id"] == not_testable_req["id"]
    assert clarifications[0]["status"] == "open"


def test_reextracting_document_replaces_its_requirements_not_duplicates(client, monkeypatch):
    project = _create_project(client)
    doc = _upload(client, project["id"])

    fake_v1 = _fake_extraction(
        [
            ExtractedRequirementLLM(
                source_chunk_index=0,
                source_id_hint="REQ-1",
                text="The system shall allow login.",
                requirement_type=RequirementType.FUNCTIONAL,
                classification_state=ClassificationState.CLEAR,
            )
        ]
    )
    monkeypatch.setattr("app.requirements.extraction.ai_service.generate_json", lambda **kwargs: fake_v1)
    client.post(f"/api/projects/{project['id']}/requirements/extract/{doc['id']}")

    fake_v2 = _fake_extraction(
        [
            ExtractedRequirementLLM(
                source_chunk_index=0,
                source_id_hint="REQ-1",
                text="The system shall allow login via SSO.",
                requirement_type=RequirementType.FUNCTIONAL,
                classification_state=ClassificationState.CLEAR,
            )
        ]
    )
    monkeypatch.setattr("app.requirements.extraction.ai_service.generate_json", lambda **kwargs: fake_v2)
    client.post(f"/api/projects/{project['id']}/requirements/extract/{doc['id']}")

    requirements = client.get(f"/api/projects/{project['id']}/requirements").json()
    assert len(requirements) == 1
    assert requirements[0]["text"] == "The system shall allow login via SSO."
    assert requirements[0]["id"] == "REQ-1"


def test_extract_for_project_covers_all_completed_documents(client, monkeypatch):
    project = _create_project(client)
    doc_a = _upload(client, project["id"], filename="a.txt", content=b"First requirement.\n")
    doc_b = _upload(client, project["id"], filename="b.txt", content=b"Second requirement.\n")

    def fake_generate(**kwargs):
        return _fake_extraction(
            [
                ExtractedRequirementLLM(
                    source_chunk_index=0,
                    text="A requirement.",
                    requirement_type=RequirementType.FUNCTIONAL,
                    classification_state=ClassificationState.CLEAR,
                )
            ]
        )

    monkeypatch.setattr("app.requirements.extraction.ai_service.generate_json", fake_generate)

    resp = client.post(f"/api/projects/{project['id']}/requirements/extract")
    assert resp.status_code == 200
    body = resp.json()
    assert body["documents_processed"] == 2
    assert body["requirements_extracted"] == 2
    assert set(body["per_document"]) == {doc_a["id"], doc_b["id"]}


def test_resolve_clarification(client, monkeypatch):
    project = _create_project(client)
    doc = _upload(client, project["id"])

    fake = _fake_extraction(
        [
            ExtractedRequirementLLM(
                source_chunk_index=0,
                text="Something ambiguous.",
                requirement_type=RequirementType.FUNCTIONAL,
                classification_state=ClassificationState.AMBIGUOUS,
                rationale="Unclear which role this applies to.",
            )
        ]
    )
    monkeypatch.setattr("app.requirements.extraction.ai_service.generate_json", lambda **kwargs: fake)
    client.post(f"/api/projects/{project['id']}/requirements/extract/{doc['id']}")

    clarifications = client.get(f"/api/projects/{project['id']}/requirements/clarifications").json()
    assert len(clarifications) == 1
    clarification_id = clarifications[0]["id"]

    resp = client.post(
        f"/api/projects/{project['id']}/requirements/clarifications/{clarification_id}/resolve",
        json={"resolution_note": "Confirmed with stakeholder: applies to admin role only."},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "resolved"
    assert body["resolution_note"] == "Confirmed with stakeholder: applies to admin role only."
    assert body["resolved_at"] is not None


def test_resolve_unknown_clarification_404(client):
    project = _create_project(client)
    resp = client.post(f"/api/projects/{project['id']}/requirements/clarifications/does-not-exist/resolve", json={})
    assert resp.status_code == 404


def test_requirements_project_isolation(client, monkeypatch):
    project_a = _create_project(client, "A")
    project_b = _create_project(client, "B")
    doc = _upload(client, project_a["id"])

    fake = _fake_extraction(
        [
            ExtractedRequirementLLM(
                source_chunk_index=0,
                text="Secret requirement in A.",
                requirement_type=RequirementType.FUNCTIONAL,
                classification_state=ClassificationState.CLEAR,
            )
        ]
    )
    monkeypatch.setattr("app.requirements.extraction.ai_service.generate_json", lambda **kwargs: fake)
    client.post(f"/api/projects/{project_a['id']}/requirements/extract/{doc['id']}")

    assert client.get(f"/api/projects/{project_a['id']}/requirements").json() != []
    assert client.get(f"/api/projects/{project_b['id']}/requirements").json() == []
