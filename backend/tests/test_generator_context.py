from __future__ import annotations

import io

from app.generator.context import MAX_CONTEXT_CHUNKS, gather_context
from app.rag import service as rag_service
from app.requirements.models import ClassificationState, Requirement, RequirementSource, RequirementType


def test_gather_context_includes_own_source_chunk_first(client):
    project = client.post("/api/projects", json={"name": "Ctx Test"}).json()
    doc = client.post(
        f"/api/projects/{project['id']}/documents",
        files=[("files", ("s.txt", io.BytesIO(b"REQ-1: Users can reset their password via email.\n"), "text/plain"))],
    ).json()[0]

    chunks = rag_service.chunks_for_document(project["id"], doc["id"])
    assert len(chunks) >= 1
    own_chunk = chunks[0]

    requirement = Requirement(
        id="REQ-1",
        project_id=project["id"],
        text="Users can reset their password via email.",
        requirement_type=RequirementType.FUNCTIONAL,
        classification_state=ClassificationState.CLEAR,
        source=RequirementSource(
            document_id=doc["id"],
            document_name=doc["filename"],
            page=own_chunk.page,
            section=own_chunk.section,
            chunk_ids=[own_chunk.chunk_id],
        ),
    )

    context_chunks = gather_context(project["id"], requirement)
    assert context_chunks[0].chunk_id == own_chunk.chunk_id
    assert len(context_chunks) <= MAX_CONTEXT_CHUNKS
    # No duplicate chunk ids even though the own chunk will also match the search.
    assert len({c.chunk_id for c in context_chunks}) == len(context_chunks)
