"""Assembles generation context strictly from retrieved RAG chunks - never a
full-document dump. A requirement's own source chunk is always included (the
exact text it was extracted from); a small number of additional hybrid-search
hits for the requirement's text fill out any needed surrounding context."""

from __future__ import annotations

from app.rag import service as rag_service
from app.rag.models import Chunk
from app.requirements.models import Requirement

DEFAULT_CONTEXT_TOP_K = 5
MAX_CONTEXT_CHUNKS = 6


def gather_context(project_id: str, requirement: Requirement, top_k: int = DEFAULT_CONTEXT_TOP_K) -> list[Chunk]:
    chunks: list[Chunk] = []
    seen_ids: set[int] = set()

    own_chunks = rag_service.chunks_for_document(project_id, requirement.source.document_id)
    for chunk in own_chunks:
        if chunk.chunk_id in requirement.source.chunk_ids and chunk.chunk_id not in seen_ids:
            chunks.append(chunk)
            seen_ids.add(chunk.chunk_id)

    hits = rag_service.search(project_id, requirement.text, top_k=top_k, mode="hybrid")
    for hit in hits:
        if hit.chunk.chunk_id not in seen_ids:
            chunks.append(hit.chunk)
            seen_ids.add(hit.chunk.chunk_id)

    return chunks[:MAX_CONTEXT_CHUNKS]
