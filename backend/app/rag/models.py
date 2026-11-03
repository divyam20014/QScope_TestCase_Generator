from __future__ import annotations

from pydantic import BaseModel


class Chunk(BaseModel):
    """A retrievable unit of document content, carrying enough metadata to
    trace any answer built from it back to its exact source location."""

    chunk_id: int
    project_id: str
    document_id: str
    document_name: str
    page: int | None = None
    sheet: str | None = None
    section: str | None = None
    text: str
    requirement_id: str | None = None


class SearchHit(BaseModel):
    chunk: Chunk
    score: float
    semantic_score: float | None = None
    keyword_score: float | None = None


class SearchMode:
    HYBRID = "hybrid"
    SEMANTIC = "semantic"
    KEYWORD = "keyword"
