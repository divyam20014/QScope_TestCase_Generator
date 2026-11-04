from __future__ import annotations

import io

from app.ai.exceptions import GeminiNotConfiguredError
from app.generator.models import GeneratedTestBatchLLM, GeneratedTestCaseLLM, Priority
from app.requirements.models import ClassificationState, ExtractedRequirementLLM, ExtractionBatchLLM, RequirementType
from app.validators.models import QualityIssueLLM, QualityReviewBatchLLM


def _create_project(client, name="Quality Test Project"):
    return client.post("/api/projects", json={"name": name}).json()


def _upload_extract_and_generate(client, monkeypatch, project_id):
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
                title="Test case",
                expected_result="It works correctly.",
                priority=Priority.MEDIUM,
            )
        ]
    )
    monkeypatch.setattr("app.generator.service.ai_service.generate_json", lambda **kwargs: fake_batch)
    client.post(
        f"/api/projects/{project_id}/generation/jobs", json={"test_types": ["system"], "test_categories": ["positive"]}
    )
    return client.get(f"/api/projects/{project_id}/test-cases").json()


def test_quality_review_requires_existing_project(client):
    resp = client.post("/api/projects/does-not-exist/quality-review", json={})
    assert resp.status_code == 404


def test_quality_review_without_gemini_configured_returns_400(client, monkeypatch):
    project = _create_project(client)
    _upload_extract_and_generate(client, monkeypatch, project["id"])

    def raise_not_configured(**kwargs):
        raise GeminiNotConfiguredError("GEMINI_API_KEY is not set - add it to .env")

    # `app.ai.service` is a single shared module - every `from app.ai import
    # service as ai_service` alias (requirements/generator/quality_review)
    # resolves `generate_json` on it at call time, so patching it here is
    # exactly what the real "no API key configured" path looks like to a
    # caller, without needing to touch env vars the `client` fixture relies on.
    monkeypatch.setattr("app.ai.service.generate_json", raise_not_configured)

    resp = client.post(f"/api/projects/{project['id']}/quality-review", json={})
    assert resp.status_code == 400


def test_quality_review_flags_real_issue_and_drops_hallucinated_id(client, monkeypatch):
    project = _create_project(client)
    test_cases = _upload_extract_and_generate(client, monkeypatch, project["id"])
    real_id = test_cases[0]["id"]

    fake_review = QualityReviewBatchLLM(
        issues=[
            QualityIssueLLM(
                test_case_id=real_id,
                issue_type="weak_expected_result",
                explanation="'It works correctly' is not a verifiable outcome.",
                suggested_fix="State the specific UI change or data result expected.",
            ),
            QualityIssueLLM(
                test_case_id="TC-9999-does-not-exist",
                issue_type="other",
                explanation="Hallucinated reference to a test case that was never given.",
            ),
        ]
    )
    monkeypatch.setattr("app.validators.quality_review.ai_service.generate_json", lambda **kwargs: fake_review)

    resp = client.post(f"/api/projects/{project['id']}/quality-review", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["requirements_reviewed"] == 1
    assert body["issues_found"] == 1  # the hallucinated-id issue was dropped

    issues = client.get(f"/api/projects/{project['id']}/quality-review/issues").json()
    assert len(issues) == 1
    assert issues[0]["test_case_id"] == real_id
    assert issues[0]["issue_type"] == "weak_expected_result"
    assert issues[0]["status"] == "open"


def test_rerunning_review_for_requirement_replaces_its_issues(client, monkeypatch):
    project = _create_project(client)
    test_cases = _upload_extract_and_generate(client, monkeypatch, project["id"])
    real_id = test_cases[0]["id"]

    first_review = QualityReviewBatchLLM(
        issues=[QualityIssueLLM(test_case_id=real_id, issue_type="weak_expected_result", explanation="First pass issue.")]
    )
    monkeypatch.setattr("app.validators.quality_review.ai_service.generate_json", lambda **kwargs: first_review)
    client.post(f"/api/projects/{project['id']}/quality-review", json={})
    assert len(client.get(f"/api/projects/{project['id']}/quality-review/issues").json()) == 1

    second_review = QualityReviewBatchLLM(issues=[])
    monkeypatch.setattr("app.validators.quality_review.ai_service.generate_json", lambda **kwargs: second_review)
    client.post(f"/api/projects/{project['id']}/quality-review", json={})
    assert client.get(f"/api/projects/{project['id']}/quality-review/issues").json() == []


def test_resolve_quality_issue(client, monkeypatch):
    project = _create_project(client)
    test_cases = _upload_extract_and_generate(client, monkeypatch, project["id"])
    real_id = test_cases[0]["id"]

    fake_review = QualityReviewBatchLLM(
        issues=[QualityIssueLLM(test_case_id=real_id, issue_type="unclear_steps", explanation="Steps skip a precondition.")]
    )
    monkeypatch.setattr("app.validators.quality_review.ai_service.generate_json", lambda **kwargs: fake_review)
    client.post(f"/api/projects/{project['id']}/quality-review", json={})

    issue_id = client.get(f"/api/projects/{project['id']}/quality-review/issues").json()[0]["id"]
    resp = client.post(
        f"/api/projects/{project['id']}/quality-review/issues/{issue_id}/resolve",
        json={"resolution_note": "Steps rewritten manually."},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "resolved"
    assert resp.json()["resolution_note"] == "Steps rewritten manually."


def test_resolve_unknown_quality_issue_404(client):
    project = _create_project(client)
    resp = client.post(f"/api/projects/{project['id']}/quality-review/issues/does-not-exist/resolve", json={})
    assert resp.status_code == 404
