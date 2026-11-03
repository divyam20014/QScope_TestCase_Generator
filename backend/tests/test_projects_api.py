from __future__ import annotations


def test_health(client):
    resp = client.get("/api/system/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_create_list_get_project(client):
    resp = client.post("/api/projects", json={"name": "Loan App QA", "description": "d", "business_domain": "Banking"})
    assert resp.status_code == 201
    project = resp.json()
    assert project["name"] == "Loan App QA"
    assert project["status"] == "active"

    resp = client.get("/api/projects")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    resp = client.get(f"/api/projects/{project['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == project["id"]


def test_get_missing_project_404(client):
    resp = client.get("/api/projects/does-not-exist")
    assert resp.status_code == 404


def test_update_project(client):
    project = client.post("/api/projects", json={"name": "Original"}).json()
    resp = client.patch(f"/api/projects/{project['id']}", json={"name": "Renamed"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed"


def test_archive_and_restore_project(client):
    project = client.post("/api/projects", json={"name": "P"}).json()
    resp = client.post(f"/api/projects/{project['id']}/archive")
    assert resp.json()["status"] == "archived"

    active_only = client.get("/api/projects", params={"include_archived": False}).json()
    assert active_only == []

    resp = client.post(f"/api/projects/{project['id']}/restore")
    assert resp.json()["status"] == "active"


def test_duplicate_project(client):
    project = client.post("/api/projects", json={"name": "P"}).json()
    resp = client.post(f"/api/projects/{project['id']}/duplicate")
    assert resp.status_code == 201
    dup = resp.json()
    assert dup["id"] != project["id"]
    assert dup["name"] == "P (Copy)"

    all_projects = client.get("/api/projects").json()
    assert len(all_projects) == 2


def test_delete_project(client):
    project = client.post("/api/projects", json={"name": "P"}).json()
    resp = client.delete(f"/api/projects/{project['id']}")
    assert resp.status_code == 204

    resp = client.get(f"/api/projects/{project['id']}")
    assert resp.status_code == 404


def test_project_persists_across_app_restart(client, tmp_path):
    project = client.post("/api/projects", json={"name": "Persisted"}).json()

    from app.core.config import get_settings

    get_settings.cache_clear()
    from app.main import app
    from fastapi.testclient import TestClient

    new_client = TestClient(app)
    resp = new_client.get(f"/api/projects/{project['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Persisted"
