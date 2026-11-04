from __future__ import annotations

import io

from app.ai.exceptions import AIProviderQuotaExceededError
from app.generator.models import GeneratedTestBatchLLM, GeneratedTestCaseLLM, Priority
from app.requirements.models import ClassificationState, ExtractedRequirementLLM, ExtractionBatchLLM, RequirementType


def _create_project(client, name="Generation Test Project"):
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


def _fixed_batch(n=2):
    return GeneratedTestBatchLLM(
        test_cases=[
            GeneratedTestCaseLLM(
                scenario_description=f"Scenario {i}",
                title=f"Test case {i}",
                preconditions="User has an account.",
                test_data="email=user@example.com",
                steps=["Open reset page", "Submit email"],
                expected_result="A reset email is sent.",
                priority=Priority.HIGH,
            )
            for i in range(n)
        ]
    )


def test_create_job_requires_existing_project(client):
    resp = client.post(
        "/api/projects/does-not-exist/generation/jobs",
        json={"test_types": ["system"], "test_categories": ["positive"]},
    )
    assert resp.status_code == 404


def test_create_and_run_job_generates_schema_valid_test_cases(client, monkeypatch):
    project = _create_project(client)
    _upload_and_extract(client, monkeypatch, project["id"])

    monkeypatch.setattr("app.generator.service.ai_service.generate_json", lambda **kwargs: _fixed_batch())

    resp = client.post(
        f"/api/projects/{project['id']}/generation/jobs",
        json={"test_types": ["system", "security"], "test_categories": ["positive", "negative"]},
    )
    assert resp.status_code == 200
    job = resp.json()
    assert job["status"] == "completed"
    assert len(job["batches"]) == 4  # 1 requirement x 2 types x 2 categories
    assert all(r["status"] == "completed" for r in job["results"].values())

    test_cases = client.get(f"/api/projects/{project['id']}/test-cases").json()
    assert len(test_cases) == 8  # 4 batches x 2 test cases each

    ids = {t["id"] for t in test_cases}
    assert len(ids) == 8  # all unique
    scenario_ids = {t["scenario_id"] for t in test_cases}
    assert len(scenario_ids) == 8

    sample = test_cases[0]
    assert sample["requirement_id"] == "REQ-1"
    assert sample["source_document"] == "s.txt"
    assert sample["priority"] == "high"
    assert sample["destructive"] is False
    assert sample["assumption_status"] == "none"


def test_destructive_category_flags_test_cases(client, monkeypatch):
    project = _create_project(client)
    _upload_and_extract(client, monkeypatch, project["id"])
    monkeypatch.setattr("app.generator.service.ai_service.generate_json", lambda **kwargs: _fixed_batch(1))

    resp = client.post(
        f"/api/projects/{project['id']}/generation/jobs",
        json={"test_types": ["security"], "test_categories": ["destructive"]},
    )
    assert resp.status_code == 200
    test_cases = client.get(f"/api/projects/{project['id']}/test-cases").json()
    assert len(test_cases) == 1
    assert test_cases[0]["destructive"] is True
    assert test_cases[0]["test_category"] == "destructive"


def test_job_pauses_on_quota_exceeded_and_resumes(client, monkeypatch):
    project = _create_project(client)
    _upload_and_extract(client, monkeypatch, project["id"])

    state = {"should_fail": True}

    def flaky(**kwargs):
        if state["should_fail"]:
            raise AIProviderQuotaExceededError("quota exceeded", retry_after_seconds=12.5)
        return _fixed_batch(1)

    monkeypatch.setattr("app.generator.service.ai_service.generate_json", flaky)

    resp = client.post(
        f"/api/projects/{project['id']}/generation/jobs",
        json={"test_types": ["system"], "test_categories": ["positive", "negative"]},
    )
    job = resp.json()
    assert job["status"] == "paused"
    assert job["retry_after_seconds"] == 12.5
    assert job["next_batch_index"] == 0
    assert client.get(f"/api/projects/{project['id']}/test-cases").json() == []

    state["should_fail"] = False
    resp2 = client.post(f"/api/projects/{project['id']}/generation/jobs/{job['id']}/resume")
    job2 = resp2.json()
    assert job2["status"] == "completed"
    assert job2["next_batch_index"] == 2

    test_cases = client.get(f"/api/projects/{project['id']}/test-cases").json()
    assert len(test_cases) == 2  # 2 batches x 1 test case each


def test_interrupted_job_resumes_from_last_successful_batch_without_duplicating(client, monkeypatch):
    project = _create_project(client)
    _upload_and_extract(client, monkeypatch, project["id"])

    calls = {"n": 0}

    def flaky(**kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("simulated transient failure")
        return _fixed_batch(1)

    monkeypatch.setattr("app.generator.service.ai_service.generate_json", flaky)

    resp = client.post(
        f"/api/projects/{project['id']}/generation/jobs",
        json={"test_types": ["system"], "test_categories": ["positive", "negative", "edge"]},
    )
    job = resp.json()
    assert job["status"] == "failed"
    assert job["next_batch_index"] == 1  # batch 0 succeeded, batch 1 failed and will be retried

    test_cases_after_failure = client.get(f"/api/projects/{project['id']}/test-cases").json()
    assert len(test_cases_after_failure) == 1  # only batch 0's output persisted

    resp2 = client.post(f"/api/projects/{project['id']}/generation/jobs/{job['id']}/resume")
    job2 = resp2.json()
    assert job2["status"] == "completed"

    test_cases_after_resume = client.get(f"/api/projects/{project['id']}/test-cases").json()
    assert len(test_cases_after_resume) == 3  # 3 batches total, no duplicates from the retried batch


def test_resuming_completed_job_is_rejected(client, monkeypatch):
    project = _create_project(client)
    _upload_and_extract(client, monkeypatch, project["id"])
    monkeypatch.setattr("app.generator.service.ai_service.generate_json", lambda **kwargs: _fixed_batch(1))

    resp = client.post(
        f"/api/projects/{project['id']}/generation/jobs",
        json={"test_types": ["system"], "test_categories": ["positive"]},
    )
    job = resp.json()
    assert job["status"] == "completed"

    resp2 = client.post(f"/api/projects/{project['id']}/generation/jobs/{job['id']}/resume")
    assert resp2.status_code == 409


def test_cancel_job(client, monkeypatch):
    project = _create_project(client)
    _upload_and_extract(client, monkeypatch, project["id"])

    def always_quota(**kwargs):
        raise AIProviderQuotaExceededError("quota exceeded")

    monkeypatch.setattr("app.generator.service.ai_service.generate_json", always_quota)

    resp = client.post(
        f"/api/projects/{project['id']}/generation/jobs",
        json={"test_types": ["system"], "test_categories": ["positive"]},
    )
    job = resp.json()
    assert job["status"] == "paused"

    resp2 = client.post(f"/api/projects/{project['id']}/generation/jobs/{job['id']}/cancel")
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "cancelled"

    resp3 = client.post(f"/api/projects/{project['id']}/generation/jobs/{job['id']}/resume")
    assert resp3.status_code == 409


def test_get_unknown_job_404(client):
    project = _create_project(client)
    resp = client.get(f"/api/projects/{project['id']}/generation/jobs/does-not-exist")
    assert resp.status_code == 404
