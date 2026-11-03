from __future__ import annotations

import io


def _create_project(client, name="Doc Test Project"):
    return client.post("/api/projects", json={"name": name}).json()


def test_upload_requires_existing_project(client):
    resp = client.post(
        "/api/projects/does-not-exist/documents",
        files=[("files", ("a.txt", io.BytesIO(b"hello"), "text/plain"))],
    )
    assert resp.status_code == 404


def test_upload_txt_document_and_list(client):
    project = _create_project(client)
    resp = client.post(
        f"/api/projects/{project['id']}/documents",
        files=[("files", ("requirements.txt", io.BytesIO(b"REQ-1: user can log in\n"), "text/plain"))],
    )
    assert resp.status_code == 201
    docs = resp.json()
    assert len(docs) == 1
    assert docs[0]["status"] == "completed"
    assert docs[0]["filename"] == "requirements.txt"

    resp = client.get(f"/api/projects/{project['id']}/documents")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    project_after = client.get(f"/api/projects/{project['id']}").json()
    assert project_after["document_count"] == 1


def test_upload_rejects_unsupported_extension(client):
    project = _create_project(client)
    resp = client.post(
        f"/api/projects/{project['id']}/documents",
        files=[("files", ("virus.exe", io.BytesIO(b"MZ"), "application/octet-stream"))],
    )
    assert resp.status_code == 422


def test_upload_corrupt_pdf_reports_failed_without_crashing(client):
    project = _create_project(client)
    resp = client.post(
        f"/api/projects/{project['id']}/documents",
        files=[("files", ("broken.pdf", io.BytesIO(b"not a real pdf"), "application/pdf"))],
    )
    assert resp.status_code == 201
    doc = resp.json()[0]
    assert doc["status"] == "failed"
    assert doc["error"]


def test_upload_exact_duplicate_is_flagged(client):
    project = _create_project(client)
    content = b"Duplicate content for hashing"
    first = client.post(
        f"/api/projects/{project['id']}/documents",
        files=[("files", ("doc1.txt", io.BytesIO(content), "text/plain"))],
    ).json()[0]
    second = client.post(
        f"/api/projects/{project['id']}/documents",
        files=[("files", ("doc2.txt", io.BytesIO(content), "text/plain"))],
    ).json()[0]
    assert second["duplicate_of"] == first["id"]


def test_upload_same_name_different_content_flags_conflict(client):
    project = _create_project(client)
    first = client.post(
        f"/api/projects/{project['id']}/documents",
        files=[("files", ("spec.txt", io.BytesIO(b"version one"), "text/plain"))],
    ).json()[0]
    second = client.post(
        f"/api/projects/{project['id']}/documents",
        files=[("files", ("spec.txt", io.BytesIO(b"version two, different"), "text/plain"))],
    ).json()[0]

    updated_first = client.get(f"/api/projects/{project['id']}/documents/{first['id']}").json()
    assert second["possible_conflicts"] == [first["id"]]
    assert updated_first["possible_conflicts"] == [second["id"]]


def test_preview_returns_extracted_blocks(client):
    project = _create_project(client)
    doc = client.post(
        f"/api/projects/{project['id']}/documents",
        files=[("files", ("notes.md", io.BytesIO(b"# Title\nSome text\n"), "text/markdown"))],
    ).json()[0]

    resp = client.get(f"/api/projects/{project['id']}/documents/{doc['id']}/preview")
    assert resp.status_code == 200
    blocks = resp.json()["blocks"]
    assert any(b["text"] == "Title" for b in blocks)


def test_mark_authoritative(client):
    project = _create_project(client)
    doc = client.post(
        f"/api/projects/{project['id']}/documents",
        files=[("files", ("a.txt", io.BytesIO(b"content"), "text/plain"))],
    ).json()[0]

    resp = client.post(f"/api/projects/{project['id']}/documents/{doc['id']}/authoritative?value=true")
    assert resp.status_code == 200
    assert resp.json()["is_authoritative"] is True


def test_delete_document_updates_count_and_clears_conflicts(client):
    project = _create_project(client)
    first = client.post(
        f"/api/projects/{project['id']}/documents",
        files=[("files", ("x.txt", io.BytesIO(b"aaa"), "text/plain"))],
    ).json()[0]
    second = client.post(
        f"/api/projects/{project['id']}/documents",
        files=[("files", ("x.txt", io.BytesIO(b"bbb"), "text/plain"))],
    ).json()[0]

    resp = client.delete(f"/api/projects/{project['id']}/documents/{first['id']}")
    assert resp.status_code == 204

    remaining = client.get(f"/api/projects/{project['id']}/documents").json()
    assert len(remaining) == 1
    assert remaining[0]["id"] == second["id"]
    assert remaining[0]["possible_conflicts"] == []

    project_after = client.get(f"/api/projects/{project['id']}").json()
    assert project_after["document_count"] == 1


def test_project_isolation_for_documents(client):
    project_a = _create_project(client, "A")
    project_b = _create_project(client, "B")
    client.post(
        f"/api/projects/{project_a['id']}/documents",
        files=[("files", ("a.txt", io.BytesIO(b"only in A"), "text/plain"))],
    )
    docs_b = client.get(f"/api/projects/{project_b['id']}/documents").json()
    assert docs_b == []
