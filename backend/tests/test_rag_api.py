from __future__ import annotations

import io


def _create_project(client, name="RAG Test Project"):
    return client.post("/api/projects", json={"name": name}).json()


def test_upload_triggers_indexing(client):
    project = _create_project(client)
    content = b"REQ-1: The system shall allow users to reset their password via email.\n"
    doc = client.post(
        f"/api/projects/{project['id']}/documents",
        files=[("files", ("req.txt", io.BytesIO(content), "text/plain"))],
    ).json()[0]

    assert doc["indexed"] is True
    assert doc["indexed_chunk_count"] > 0

    stats = client.get(f"/api/projects/{project['id']}/rag/stats").json()
    assert stats["chunk_count"] > 0
    assert stats["indexed_document_count"] == 1


def test_search_returns_relevant_chunk(client):
    project = _create_project(client)
    client.post(
        f"/api/projects/{project['id']}/documents",
        files=[
            (
                "files",
                (
                    "req.txt",
                    io.BytesIO(b"REQ-1: Users can reset their password using a verification email.\n"),
                    "text/plain",
                ),
            )
        ],
    )

    resp = client.get(f"/api/projects/{project['id']}/rag/search", params={"q": "password reset email"})
    assert resp.status_code == 200
    hits = resp.json()
    assert len(hits) > 0
    assert "password" in hits[0]["chunk"]["text"].lower()


def test_search_modes(client):
    project = _create_project(client)
    client.post(
        f"/api/projects/{project['id']}/documents",
        files=[("files", ("req.txt", io.BytesIO(b"Orders over 1000 require manager approval.\n"), "text/plain"))],
    )

    for mode in ("hybrid", "semantic", "keyword"):
        resp = client.get(
            f"/api/projects/{project['id']}/rag/search", params={"q": "manager approval", "mode": mode}
        )
        assert resp.status_code == 200, mode
        assert len(resp.json()) > 0, mode


def test_delete_document_removes_its_chunks(client):
    project = _create_project(client)
    doc = client.post(
        f"/api/projects/{project['id']}/documents",
        files=[("files", ("req.txt", io.BytesIO(b"Some indexable requirement text here.\n"), "text/plain"))],
    ).json()[0]

    stats_before = client.get(f"/api/projects/{project['id']}/rag/stats").json()
    assert stats_before["chunk_count"] > 0

    client.delete(f"/api/projects/{project['id']}/documents/{doc['id']}")

    stats_after = client.get(f"/api/projects/{project['id']}/rag/stats").json()
    assert stats_after["chunk_count"] == 0


def test_reindex_rebuilds_from_all_documents(client):
    project = _create_project(client)
    client.post(
        f"/api/projects/{project['id']}/documents",
        files=[("files", ("a.txt", io.BytesIO(b"First requirement about login.\n"), "text/plain"))],
    )
    client.post(
        f"/api/projects/{project['id']}/documents",
        files=[("files", ("b.txt", io.BytesIO(b"Second requirement about payments.\n"), "text/plain"))],
    )

    resp = client.post(f"/api/projects/{project['id']}/rag/reindex")
    assert resp.status_code == 200
    body = resp.json()
    assert body["documents_indexed"] == 2
    assert body["total_chunks"] >= 2


def test_rag_project_isolation(client):
    project_a = _create_project(client, "A")
    project_b = _create_project(client, "B")
    client.post(
        f"/api/projects/{project_a['id']}/documents",
        files=[("files", ("a.txt", io.BytesIO(b"Secret content unique to project A.\n"), "text/plain"))],
    )

    stats_b = client.get(f"/api/projects/{project_b['id']}/rag/stats").json()
    assert stats_b["chunk_count"] == 0

    hits_b = client.get(f"/api/projects/{project_b['id']}/rag/search", params={"q": "secret content"}).json()
    assert hits_b == []


def test_search_requires_existing_project(client):
    resp = client.get("/api/projects/does-not-exist/rag/search", params={"q": "test"})
    assert resp.status_code == 404
