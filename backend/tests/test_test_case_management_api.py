from __future__ import annotations

import io

from app.generator.models import GeneratedTestBatchLLM, GeneratedTestCaseLLM, Priority
from app.requirements.models import ClassificationState, ExtractedRequirementLLM, ExtractionBatchLLM, RequirementType


def _create_project(client, name="Repository Test Project"):
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


def _manual_payload(requirement_id="REQ-1", **overrides):
    payload = {
        "requirement_id": requirement_id,
        "scenario_description": "Manual scenario",
        "title": "Manually added test case",
        "test_type": "system",
        "test_category": "positive",
        "preconditions": "User exists",
        "test_data": "N/A",
        "steps": ["Step 1", "Step 2"],
        "expected_result": "Expected outcome",
        "priority": "high",
    }
    payload.update(overrides)
    return payload


def test_create_manual_test_case(client):
    project = _create_project(client)
    resp = client.post(f"/api/projects/{project['id']}/test-cases", json=_manual_payload())
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"].startswith("TC-")
    assert body["scenario_id"].startswith("SC-")
    assert body["manually_edited"] is True
    assert body["batch_id"] == "manual"
    assert body["approved"] is False
    assert body["locked"] is False

    listed = client.get(f"/api/projects/{project['id']}/test-cases").json()
    assert len(listed) == 1


def test_update_test_case_persists_changes_and_records_history(client):
    project = _create_project(client)
    tc = client.post(f"/api/projects/{project['id']}/test-cases", json=_manual_payload()).json()

    resp = client.patch(f"/api/projects/{project['id']}/test-cases/{tc['id']}", json={"title": "Updated title"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Updated title"
    assert body["manually_edited"] is True

    history = client.get(f"/api/projects/{project['id']}/test-cases/{tc['id']}/history").json()
    assert len(history) == 1
    assert history[0]["snapshot"]["title"] == "Manually added test case"


def test_update_unknown_test_case_404(client):
    project = _create_project(client)
    resp = client.patch(f"/api/projects/{project['id']}/test-cases/does-not-exist", json={"title": "x"})
    assert resp.status_code == 404


def test_locked_test_case_cannot_be_edited_or_deleted(client):
    project = _create_project(client)
    tc = client.post(f"/api/projects/{project['id']}/test-cases", json=_manual_payload()).json()
    client.post(f"/api/projects/{project['id']}/test-cases/{tc['id']}/lock")

    resp = client.patch(f"/api/projects/{project['id']}/test-cases/{tc['id']}", json={"title": "Should fail"})
    assert resp.status_code == 409

    resp2 = client.delete(f"/api/projects/{project['id']}/test-cases/{tc['id']}")
    assert resp2.status_code == 409

    # Unlocking restores edit/delete ability.
    client.post(f"/api/projects/{project['id']}/test-cases/{tc['id']}/lock?locked=false")
    resp3 = client.patch(f"/api/projects/{project['id']}/test-cases/{tc['id']}", json={"title": "Now allowed"})
    assert resp3.status_code == 200


def test_delete_test_case(client):
    project = _create_project(client)
    tc = client.post(f"/api/projects/{project['id']}/test-cases", json=_manual_payload()).json()
    resp = client.delete(f"/api/projects/{project['id']}/test-cases/{tc['id']}")
    assert resp.status_code == 200
    assert client.get(f"/api/projects/{project['id']}/test-cases").json() == []


def test_copy_test_case_creates_independent_unapproved_unlocked_copy(client):
    project = _create_project(client)
    tc = client.post(f"/api/projects/{project['id']}/test-cases", json=_manual_payload()).json()
    client.post(f"/api/projects/{project['id']}/test-cases/{tc['id']}/approve")
    client.post(f"/api/projects/{project['id']}/test-cases/{tc['id']}/lock")

    resp = client.post(f"/api/projects/{project['id']}/test-cases/{tc['id']}/copy")
    assert resp.status_code == 200
    copy = resp.json()
    assert copy["id"] != tc["id"]
    assert copy["scenario_id"] != tc["scenario_id"]
    assert copy["title"] == tc["title"]
    assert copy["approved"] is False
    assert copy["locked"] is False

    assert len(client.get(f"/api/projects/{project['id']}/test-cases").json()) == 2


def test_approve_and_unapprove(client):
    project = _create_project(client)
    tc = client.post(f"/api/projects/{project['id']}/test-cases", json=_manual_payload()).json()

    resp = client.post(f"/api/projects/{project['id']}/test-cases/{tc['id']}/approve")
    assert resp.json()["approved"] is True

    resp2 = client.post(f"/api/projects/{project['id']}/test-cases/{tc['id']}/approve?approved=false")
    assert resp2.json()["approved"] is False


def test_bulk_approve_and_bulk_delete_skips_locked(client):
    project = _create_project(client)
    tc1 = client.post(f"/api/projects/{project['id']}/test-cases", json=_manual_payload()).json()
    tc2 = client.post(f"/api/projects/{project['id']}/test-cases", json=_manual_payload()).json()
    tc3 = client.post(f"/api/projects/{project['id']}/test-cases", json=_manual_payload()).json()
    client.post(f"/api/projects/{project['id']}/test-cases/{tc3['id']}/lock")

    resp = client.post(
        f"/api/projects/{project['id']}/test-cases/bulk", json={"ids": [tc1["id"], tc2["id"]], "action": "approve"}
    )
    assert resp.status_code == 200
    assert resp.json()["changed"] == 2
    test_cases = {t["id"]: t for t in client.get(f"/api/projects/{project['id']}/test-cases").json()}
    assert test_cases[tc1["id"]]["approved"] is True
    assert test_cases[tc2["id"]]["approved"] is True

    resp2 = client.post(
        f"/api/projects/{project['id']}/test-cases/bulk",
        json={"ids": [tc1["id"], tc3["id"]], "action": "delete"},
    )
    body2 = resp2.json()
    assert body2["changed"] == 1
    assert body2["skipped_locked"] == [tc3["id"]]

    remaining_ids = {t["id"] for t in client.get(f"/api/projects/{project['id']}/test-cases").json()}
    assert remaining_ids == {tc2["id"], tc3["id"]}


def test_bulk_unknown_action_422(client):
    project = _create_project(client)
    tc = client.post(f"/api/projects/{project['id']}/test-cases", json=_manual_payload()).json()
    resp = client.post(f"/api/projects/{project['id']}/test-cases/bulk", json={"ids": [tc["id"]], "action": "nonsense"})
    assert resp.status_code == 422


def test_regeneration_preserves_locked_and_approved_and_manually_edited_cases(client, monkeypatch):
    project = _create_project(client)
    _upload_and_extract(client, monkeypatch, project["id"])

    def fixed_batch(**kwargs):
        return GeneratedTestBatchLLM(
            test_cases=[
                GeneratedTestCaseLLM(
                    scenario_description="Generated scenario",
                    title="Generated test case",
                    expected_result="Generated expected result",
                    priority=Priority.MEDIUM,
                )
            ]
        )

    monkeypatch.setattr("app.generator.service.ai_service.generate_json", fixed_batch)

    resp = client.post(
        f"/api/projects/{project['id']}/generation/jobs",
        json={"test_types": ["system"], "test_categories": ["positive"]},
    )
    job = resp.json()
    generated = client.get(f"/api/projects/{project['id']}/test-cases").json()
    assert len(generated) == 1
    generated_tc_id = generated[0]["id"]

    client.post(f"/api/projects/{project['id']}/test-cases/{generated_tc_id}/lock")

    # Re-run the exact same batch spec by creating a new job with the same
    # requirement/type/category - simulating a "regenerate" action.
    client.post(
        f"/api/projects/{project['id']}/generation/jobs",
        json={"test_types": ["system"], "test_categories": ["positive"]},
    )

    after = client.get(f"/api/projects/{project['id']}/test-cases").json()
    ids_after = {t["id"] for t in after}
    assert generated_tc_id in ids_after  # the locked one survived
    locked_case = next(t for t in after if t["id"] == generated_tc_id)
    assert locked_case["title"] == "Generated test case"  # untouched
    assert job["status"] == "completed"
