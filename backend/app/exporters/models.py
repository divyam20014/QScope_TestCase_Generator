from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.core.models import utcnow
from app.generator.models import TestCategory, TestType


class ExportFormat(str, Enum):
    XLSX = "xlsx"
    DOCX = "docx"
    PDF = "pdf"
    CSV = "csv"
    JSON = "json"


class ExportScope(BaseModel):
    """`requirement_ids=None` means the whole project. When given, it also
    scopes which requirements appear in the traceability matrix and
    clarification register - not just which test cases are included.
    `test_types`/`test_categories` only ever filter test case rows."""

    requirement_ids: list[str] | None = None
    test_types: list[TestType] | None = None
    test_categories: list[TestCategory] | None = None


class ExportRecord(BaseModel):
    id: str
    project_id: str
    format: ExportFormat
    filename: str
    size_bytes: int
    scope: ExportScope
    test_case_count: int
    created_at: datetime = Field(default_factory=utcnow)
