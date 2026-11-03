from __future__ import annotations

import pytest

from app.parsers.models import BlockType, ExtractedBlock


@pytest.fixture
def rag_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path / "local_data"))
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield


def _blocks(texts: list[str]) -> list[ExtractedBlock]:
    return [
        ExtractedBlock(block_id=f"b{i}", type=BlockType.PARAGRAPH, text=t, page=1, section="Login")
        for i, t in enumerate(texts)
    ]


def _blocks_distinct_sections(texts: list[str]) -> list[ExtractedBlock]:
    """Each text gets its own section, so chunking keeps them as separate
    chunks (chunking intentionally merges same-section text)."""
    return [
        ExtractedBlock(block_id=f"b{i}", type=BlockType.PARAGRAPH, text=t, page=1, section=f"Section {i}")
        for i, t in enumerate(texts)
    ]


def test_add_document_and_semantic_search(rag_env):
    from app.rag.index_store import RagProjectIndex

    index = RagProjectIndex("proj-a")
    count = index.add_document(
        "doc-1",
        "requirements.txt",
        _blocks_distinct_sections(
            [
                "Users must enter a valid email address to register.",
                "The system calculates monthly loan interest automatically.",
            ]
        ),
    )
    assert count == 2
    assert index.chunk_count() == 2

    hits = index.search_semantic("How does a user sign up with an email?", top_k=5)
    assert hits
    top_chunk = index._chunk_by_id(hits[0][0])
    assert "email" in top_chunk.text.lower()


def test_keyword_search_finds_exact_terms(rag_env):
    from app.rag.index_store import RagProjectIndex

    index = RagProjectIndex("proj-b")
    index.add_document(
        "doc-1",
        "spec.txt",
        _blocks(["REQ-42: orders over 1000 require manager approval."]),
    )
    hits = index.search_keyword("REQ-42 manager approval", top_k=5)
    assert hits
    # BM25's raw score can be negative in a tiny (single-document) corpus -
    # what matters is that the matching chunk was found at all.
    top_chunk = index._chunk_by_id(hits[0][0])
    assert "manager approval" in top_chunk.text.lower()


def test_keyword_search_excludes_non_matching_chunks(rag_env):
    from app.rag.index_store import RagProjectIndex

    index = RagProjectIndex("proj-b2")
    index.add_document(
        "doc-1",
        "spec.txt",
        _blocks_distinct_sections(
            [
                "Orders over 1000 require manager approval.",
                "The dashboard displays total revenue per region.",
            ]
        ),
    )
    hits = index.search_keyword("manager approval", top_k=5)
    assert len(hits) == 1
    top_chunk = index._chunk_by_id(hits[0][0])
    assert "manager approval" in top_chunk.text.lower()


def test_hybrid_search_combines_scores(rag_env):
    from app.rag.index_store import RagProjectIndex

    index = RagProjectIndex("proj-c")
    index.add_document(
        "doc-1",
        "spec.txt",
        _blocks(
            [
                "Password reset requires a valid registered email.",
                "Login sessions expire after 30 minutes of inactivity.",
            ]
        ),
    )
    results = index.search("password reset email", top_k=5, mode="hybrid")
    assert results
    assert results[0].chunk.text.startswith("Password reset")


def test_remove_document_clears_its_chunks(rag_env):
    from app.rag.index_store import RagProjectIndex

    index = RagProjectIndex("proj-d")
    index.add_document("doc-1", "a.txt", _blocks(["Content A"]))
    index.add_document("doc-2", "b.txt", _blocks(["Content B"]))
    assert index.chunk_count() == 2

    index.remove_document("doc-1")
    assert index.chunk_count() == 1
    assert index.chunks[0].document_id == "doc-2"


def test_reindexing_same_document_replaces_old_chunks(rag_env):
    from app.rag.index_store import RagProjectIndex

    index = RagProjectIndex("proj-e")
    index.add_document("doc-1", "a.txt", _blocks(["Old content"]))
    assert index.chunk_count() == 1

    index.add_document("doc-1", "a.txt", _blocks_distinct_sections(["New content", "More new content"]))
    assert index.chunk_count() == 2
    assert all(c.document_id == "doc-1" for c in index.chunks)
    assert all("Old content" != c.text for c in index.chunks)


def test_index_persists_and_reloads_from_disk(rag_env):
    from app.rag.index_store import RagProjectIndex

    index = RagProjectIndex("proj-f")
    index.add_document("doc-1", "a.txt", _blocks(["Persisted content about refunds."]))

    reloaded = RagProjectIndex("proj-f")
    assert reloaded.chunk_count() == 1
    hits = reloaded.search_semantic("refund policy", top_k=5)
    assert hits


def test_rebuild_recovers_from_corrupt_faiss_file(rag_env):
    from app.core.paths import vector_index_faiss_file
    from app.rag.index_store import RagProjectIndex

    index = RagProjectIndex("proj-g")
    index.add_document("doc-1", "a.txt", _blocks(["Some durable content."]))

    faiss_path = vector_index_faiss_file("proj-g")
    faiss_path.write_bytes(b"not a real faiss index")

    recovered = RagProjectIndex("proj-g")
    assert recovered.chunk_count() == 1
    hits = recovered.search_semantic("durable content", top_k=5)
    assert hits


def test_project_isolation(rag_env):
    from app.rag.index_store import RagProjectIndex

    index_a = RagProjectIndex("isolated-a")
    index_a.add_document("doc-1", "a.txt", _blocks(["Only in project A"]))

    index_b = RagProjectIndex("isolated-b")
    assert index_b.chunk_count() == 0
    hits = index_b.search_semantic("Only in project A", top_k=5)
    assert hits == []
