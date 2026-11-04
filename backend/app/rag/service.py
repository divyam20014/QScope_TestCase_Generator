from __future__ import annotations

from app.core import document_service
from app.core.document_models import DocumentStatus
from app.rag.index_store import RagProjectIndex
from app.rag.models import Chunk, SearchHit

# One live index instance per project for the life of the process - avoids
# re-reading the FAISS file from disk on every request. Safe because all
# mutation goes through these cached instances.
_INDEX_CACHE: dict[str, RagProjectIndex] = {}


def _get_index(project_id: str) -> RagProjectIndex:
    if project_id not in _INDEX_CACHE:
        _INDEX_CACHE[project_id] = RagProjectIndex(project_id)
    return _INDEX_CACHE[project_id]


def drop_cached_index(project_id: str) -> None:
    """Call when a project's on-disk index is deleted/replaced out from
    under the cache (project delete/duplicate)."""
    _INDEX_CACHE.pop(project_id, None)


def index_document(project_id: str, document_id: str) -> None:
    """Index (or re-index) a single successfully-parsed document. Indexing
    failures never fail the upload itself - they're recorded on the
    document so the user can see and retry."""
    try:
        record = document_service.get_document(project_id, document_id)
        if record.status != DocumentStatus.COMPLETED:
            return
        extraction = document_service.get_extraction(project_id, document_id)
        index = _get_index(project_id)
        chunk_count = index.add_document(document_id, record.filename, extraction.blocks)
        document_service.set_index_status(project_id, document_id, indexed=True, chunk_count=chunk_count)
    except Exception as exc:  # noqa: BLE001 - never let indexing crash the request
        try:
            document_service.set_index_status(project_id, document_id, indexed=False, error=str(exc))
        except document_service.DocumentNotFoundError:
            pass


def remove_document(project_id: str, document_id: str) -> None:
    index = _get_index(project_id)
    index.remove_document(document_id)


def reindex_project(project_id: str) -> dict:
    """Full rebuild from every completed document's extracted content."""
    documents = [
        (d.id, d.filename, document_service.get_extraction(project_id, d.id).blocks)
        for d in document_service.list_documents(project_id)
        if d.status == DocumentStatus.COMPLETED
    ]
    index = _get_index(project_id)
    total_chunks = index.rebuild(documents)

    chunks_by_doc: dict[str, int] = {}
    for chunk in index.chunks:
        chunks_by_doc[chunk.document_id] = chunks_by_doc.get(chunk.document_id, 0) + 1
    for document_id, _, _ in documents:
        document_service.set_index_status(
            project_id, document_id, indexed=True, chunk_count=chunks_by_doc.get(document_id, 0)
        )

    return {"documents_indexed": len(documents), "total_chunks": total_chunks}


def search(project_id: str, query: str, top_k: int = 5, mode: str = "hybrid", semantic_weight: float = 0.5) -> list[SearchHit]:
    index = _get_index(project_id)
    return index.search(query, top_k=top_k, mode=mode, semantic_weight=semantic_weight)


def chunks_for_document(project_id: str, document_id: str) -> list[Chunk]:
    """All indexed chunks for one document, in the order they were chunked
    (document reading order) - used by requirement extraction to rebuild a
    document's content from RAG chunks instead of re-reading raw files."""
    index = _get_index(project_id)
    return [c for c in index.chunks if c.document_id == document_id]


def stats(project_id: str) -> dict:
    index = _get_index(project_id)
    documents = document_service.list_documents(project_id)
    return {
        "chunk_count": index.chunk_count(),
        "indexed_document_count": sum(1 for d in documents if d.indexed),
        "completed_document_count": sum(1 for d in documents if d.status == DocumentStatus.COMPLETED),
    }
