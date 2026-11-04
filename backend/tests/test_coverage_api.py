from __future__ import annotations

import io

from app.generator.models import GeneratedTestBatchLLM, GeneratedTestCaseLLM, Priority
from app.requirements.models import ClassificationState, ExtractedRequirementLLM, ExtractionBatchLLM, RequirementType


def _create_project(client, name="Coverage Test Project"):
    return client.post("/api/projects", json={"name": name}).json()


def _upload_and_extract(client, monkeypatch, project_id):
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
    return doc


def _fixed_batch():
    return GeneratedTestBatchLLM(
        test_cases=[
            GeneratedTestCaseLLM(
                scenario_description="Scenario",
                title="Test case",
                expected_result="Expected",
                priority=Priority.MEDIUM,
            )
        ]
    )


def test_coverage_requires_existing_project(client):
    resp = client.get("/api/projects/does-not-exist/coverage")
    assert resp.status_code == 404


def test_coverage_not_covered_with_no_test_cases(client, monkeypatch):
    project = _create_project(client)
    _upload_and_extract(client, monkeypatch, project["id"])

    resp = client.get(f"/api/projects/{project['id']}/coverage")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_requirements"] == 1
    assert body["not_covered"] == 1
    assert body["coverage_percentage"] == 0.0


def test_coverage_becomes_covered_and_stamps_test_cases(client, monkeypatch):
    project = _create_project(client)
    _upload_and_extract(client, monkeypatch, project["id"])
    monkeypatch.setattr("app.generator.service.ai_service.generate_json", lambda **kwargs: _fixed_batch())

    client.post(
        f"/api/projects/{project['id']}/generation/jobs",
        json={"test_types": ["system"], "test_categories": ["positive", "negative"]},
    )

    resp = client.get(f"/api/projects/{project['id']}/coverage")
    body = resp.json()
    assert body["covered"] == 1
    assert body["coverage_percentage"] == 100.0
    assert body["per_requirement"][0]["status"] == "covered"

    test_cases = client.get(f"/api/projects/{project['id']}/test-cases").json()
    assert all(t["coverage_status"] == "covered" for t in test_cases)


def test_traceability_matrix_links_requirement_and_test_cases(client, monkeypatch):
    project = _create_project(client)
    _upload_and_extract(client, monkeypatch, project["id"])
    monkeypatch.setattr("app.generator.service.ai_service.generate_json", lambda **kwargs: _fixed_batch())
    client.post(
        f"/api/projects/{project['id']}/generation/jobs",
        json={"test_types": ["system"], "test_categories": ["positive"]},
    )

    resp = client.get(f"/api/projects/{project['id']}/coverage/traceability")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["requirement_id"] == "REQ-1"
    assert len(rows[0]["test_case_ids"]) == 1


def test_duplicates_endpoint_flags_identical_test_cases(client, monkeypatch):
    project = _create_project(client)
    _upload_and_extract(client, monkeypatch, project["id"])

    def duplicate_batch(**kwargs):
        return GeneratedTestBatchLLM(
            test_cases=[
                GeneratedTestCaseLLM(
                    scenario_description="Same scenario",
                    title="Same title",
                    expected_result="Same expected result",
                    priority=Priority.MEDIUM,
                )
            ]
        )

    monkeypatch.setattr("app.generator.service.ai_service.generate_json", duplicate_batch)
    # Two separate jobs/batches produce two test cases with identical content.
    client.post(f"/api/projects/{project['id']}/generation/jobs", json={"test_types": ["system"], "test_categories": ["positive"]})
    client.post(f"/api/projects/{project['id']}/generation/jobs", json={"test_types": ["business"], "test_categories": ["positive"]})

    resp = client.get(f"/api/projects/{project['id']}/coverage/duplicates")
    assert resp.status_code == 200
    groups = resp.json()
    assert len(groups) == 1
    assert groups[0]["method"] == "exact"
    assert len(groups[0]["test_case_ids"]) == 2
