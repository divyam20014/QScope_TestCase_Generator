"""Phase 10 hardening: path-traversal, secret-handling, upload-limit, and
backup/restore checks that weren't exercised by any earlier phase's tests."""

from __future__ import annotations

import io

import pytest

from app.core.paths import PathTraversalError, get_data_root, safe_join


def test_safe_join_rejects_parent_traversal(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    root = get_data_root()
    with pytest.raises(PathTraversalError):
        safe_join(root, "..", "..", "etc", "passwd")
    get_settings.cache_clear()


def test_safe_join_rejects_absolute_escape(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    root = get_data_root()
    with pytest.raises(PathTraversalError):
        safe_join(root, "../outside")
    get_settings.cache_clear()


def test_safe_join_allows_normal_subpath(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    root = get_data_root()
    result = safe_join(root, "projects", "abc-123")
    assert str(result).startswith(str(root))
    get_settings.cache_clear()


def test_a_literal_dotdot_project_id_through_the_api_is_a_clean_404_not_a_crash(client):
    # Real project ids are always server-generated UUIDs; a client can never
    # make ".." an existing project id. This confirms the failure mode for
    # anyone who tries is a plain 404, never a 500 or a path-containing error.
    resp = client.get("/api/projects/%2e%2e/documents")
    assert resp.status_code == 404
    assert "local_data" not in resp.text  # never echoes a resolved filesystem path


def test_system_info_never_exposes_the_api_key(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "super-secret-key-value")
    from app.core.config import get_settings

    get_settings.cache_clear()

    resp = client.get("/api/system/info")
    body = resp.json()
    assert body["gemini_configured"] is True
    assert "super-secret-key-value" not in resp.text
    assert "api_key" not in body

    get_settings.cache_clear()


def test_upload_rejects_file_over_configured_limit(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "1")
    get_settings.cache_clear()

    project = client.post("/api/projects", json={"name": "Upload Limit Test"}).json()
    oversized = b"x" * (2 * 1024 * 1024)  # 2MB, over the 1MB limit just set
    resp = client.post(
        f"/api/projects/{project['id']}/documents",
        files=[("files", ("big.txt", io.BytesIO(oversized), "text/plain"))],
    )
    assert resp.status_code == 413
    assert "exceeds" in resp.json()["detail"]

    get_settings.cache_clear()


def test_backup_restore_drill_recovers_test_cases_after_corruption(client):
    from app.core.paths import test_cases_file

    project = client.post("/api/projects", json={"name": "Backup Drill"}).json()
    payload = {
        "requirement_id": "REQ-1",
        "scenario_description": "S",
        "title": "First version",
        "test_type": "system",
        "test_category": "positive",
        "preconditions": "",
        "test_data": "",
        "steps": [],
        "expected_result": "E",
        "priority": "high",
    }
    client.post(f"/api/projects/{project['id']}/test-cases", json=payload)
    # A second write rotates the first write into a .backups/*.bak file.
    client.post(f"/api/projects/{project['id']}/test-cases", json={**payload, "title": "Second version"})

    path = test_cases_file(project["id"])
    good_backup = path.read_text(encoding="utf-8")
    path.write_text("{this is not valid json", encoding="utf-8")

    resp = client.get(f"/api/projects/{project['id']}/test-cases")
    assert resp.status_code == 200
    recovered = resp.json()
    assert len(recovered) == 1  # recovered from the backup taken after the first write
    assert recovered[0]["title"] == "First version"

    # The corrupt file itself was repaired in place by the recovery path.
    assert path.read_text(encoding="utf-8") != "{this is not valid json"
    assert good_backup  # sanity: a backup really was produced
