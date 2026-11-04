from __future__ import annotations

import io
import json

from app.generator.models import GeneratedTestBatchLLM, GeneratedTestCaseLLM, Priority
from app.requirements.models import ClassificationState, ExtractedRequirementLLM, ExtractionBatchLLM, RequirementType


def _create_project(client, name="Export Test Project"):
    return client.post("/api/projects", json={"name": name}).json()


def _build_full_dataset(client, monkeypatch, project_id):
    doc = client.post(
        f"/api/projects/{project_id}/documents",
        files=[("files", ("s.txt", io.BytesIO(b"REQ-1: Users can reset their password via email.\n"), "text/plain"))],
    ).json()[0]

    fake_extraction = ExtractionBatchLLM(
        requirements=[
            ExtractedRequirementLLM(
                source_chunk_index=0,
                source_id_hint="REQ-1",
                text="Users can reset their password via email.",
                requirement_type=RequirementType.FUNCTIONAL,
                classification_state=ClassificationState.CLEAR,
            )
        ]
    )
    monkeypatch.setattr("app.requirements.extraction.ai_service.generate_json", lambda **kwargs: fake_extraction)
    client.post(f"/api/projects/{project_id}/requirements/extract/{doc['id']}")

    fake_batch = GeneratedTestBatchLLM(
        test_cases=[
            GeneratedTestCaseLLM(
                scenario_description="Scenario",
                title="Reset password",
                expected_result="Email sent",
                priority=Priority.HIGH,
            )
        ]
    )
    monkeypatch.setattr("app.generator.service.ai_service.generate_json", lambda **kwargs: fake_batch)
    client.post(
        f"/api/projects/{project_id}/generation/jobs", json={"test_types": ["system"], "test_categories": ["positive"]}
    )
    client.get(f"/api/projects/{project_id}/coverage")  # stamps coverage_status


def test_create_export_requires_existing_project(client):
    resp = client.post("/api/projects/does-not-exist/exports", json={"format": "json"})
    assert resp.status_code == 404


def test_create_and_download_json_export(client, monkeypatch):
    project = _create_project(client)
    _build_full_dataset(client, monkeypatch, project["id"])

    resp = client.post(f"/api/projects/{project['id']}/exports", json={"format": "json"})
    assert resp.status_code == 200
    record = resp.json()
    assert record["format"] == "json"
    assert record["test_case_count"] == 1

    download = client.get(f"/api/projects/{project['id']}/exports/{record['id']}/download")
    assert download.status_code == 200
    assert download.headers["content-type"].startswith("application/json")
    payload = json.loads(download.content)
    assert len(payload["test_cases"]) == 1
    assert payload["test_cases"][0]["Requirement ID"] == "REQ-1"
    assert len(payload["traceability_matrix"]) == 1
    assert payload["traceability_matrix"][0]["Coverage Status"] in ("covered", "partial")


def test_all_five_formats_produce_downloadable_content(client, monkeypatch):
    project = _create_project(client)
    _build_full_dataset(client, monkeypatch, project["id"])

    expected_content_types = {
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pdf": "application/pdf",
        "csv": "text/csv",
        "json": "application/json",
    }
    for fmt, content_type in expected_content_types.items():
        resp = client.post(f"/api/projects/{project['id']}/exports", json={"format": fmt})
        assert resp.status_code == 200, fmt
        record = resp.json()

        download = client.get(f"/api/projects/{project['id']}/exports/{record['id']}/download")
        assert download.status_code == 200, fmt
        assert download.headers["content-type"].startswith(content_type), fmt
        assert len(download.content) > 0, fmt


def test_export_scoped_by_requirement_id_filters_traceability_too(client, monkeypatch):
    project = _create_project(client)
    _build_full_dataset(client, monkeypatch, project["id"])

    # Add a second, unrelated requirement with no test cases.
    doc2 = client.post(
        f"/api/projects/{project['id']}/documents",
        files=[("files", ("b.txt", io.BytesIO(b"REQ-2: Users can log out.\n"), "text/plain"))],
    ).json()[0]
    fake_extraction_2 = ExtractionBatchLLM(
        requirements=[
            ExtractedRequirementLLM(
                source_chunk_index=0,
                source_id_hint="REQ-2",
                text="Users can log out.",
                requirement_type=RequirementType.FUNCTIONAL,
                classification_state=ClassificationState.CLEAR,
            )
        ]
    )
    monkeypatch.setattr("app.requirements.extraction.ai_service.generate_json", lambda **kwargs: fake_extraction_2)
    client.post(f"/api/projects/{project['id']}/requirements/extract/{doc2['id']}")

    resp = client.post(
        f"/api/projects/{project['id']}/exports", json={"format": "json", "scope": {"requirement_ids": ["REQ-1"]}}
    )
    record = resp.json()
    assert record["test_case_count"] == 1

    download = client.get(f"/api/projects/{project['id']}/exports/{record['id']}/download")
    payload = json.loads(download.content)
    assert len(payload["traceability_matrix"]) == 1
    assert payload["traceability_matrix"][0]["Requirement ID"] == "REQ-1"


def test_list_exports(client, monkeypatch):
    project = _create_project(client)
    _build_full_dataset(client, monkeypatch, project["id"])
    client.post(f"/api/projects/{project['id']}/exports", json={"format": "csv"})
    client.post(f"/api/projects/{project['id']}/exports", json={"format": "json"})

    resp = client.get(f"/api/projects/{project['id']}/exports")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_download_unknown_export_404(client):
    project = _create_project(client)
    resp = client.get(f"/api/projects/{project['id']}/exports/does-not-exist/download")
    assert resp.status_code == 404
