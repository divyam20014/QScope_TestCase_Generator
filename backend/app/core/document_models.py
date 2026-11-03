from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.core.models import utcnow


class DocumentStatus(str, Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentRecord(BaseModel):
    id: str
    project_id: str
    filename: str
    extension: str
    size_bytes: int
    content_hash: str
    status: DocumentStatus
    error: str | None = None
    warnings: list[str] = Field(default_factory=list)
    page_count: int | None = None
    requires_ocr: bool = False
    block_count: int = 0
    is_authoritative: bool = False
    duplicate_of: str | None = None
    possible_conflicts: list[str] = Field(default_factory=list)
    indexed: bool = False
    index_error: str | None = None
    indexed_chunk_count: int = 0
    uploaded_at: datetime = Field(default_factory=utcnow)
    processed_at: datetime | None = None
