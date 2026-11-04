from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.ai.schema import GeminiSchemaModel
from app.core.models import utcnow


class RequirementType(str, Enum):
    FUNCTIONAL = "functional"
    BUSINESS = "business"
    NON_FUNCTIONAL = "non_functional"
    RULE = "rule"
    VALIDATION = "validation"
    WORKFLOW = "workflow"
    ROLE = "role"
    OTHER = "other"


class ClassificationState(str, Enum):
    CLEAR = "clear"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    CONFLICTING = "conflicting"
    MISSING = "missing"
    NOT_TESTABLE = "not_testable"


class RequirementSource(BaseModel):
    document_id: str
    document_name: str
    page: int | None = None
    sheet: str | None = None
    section: str | None = None
    chunk_ids: list[int] = Field(default_factory=list)


class Requirement(BaseModel):
    id: str
    project_id: str
    source_id_hint: str | None = None
    text: str
    requirement_type: RequirementType
    classification_state: ClassificationState
    rationale: str | None = None
    source: RequirementSource
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class ClarificationItem(BaseModel):
    id: str
    project_id: str
    requirement_id: str
    question: str
    status: str = "open"
    created_at: datetime = Field(default_factory=utcnow)
    resolved_at: datetime | None = None
    resolution_note: str | None = None


class ExtractedRequirementLLM(BaseModel):
    """What Gemini returns per requirement - deliberately minimal. The model
    never produces an id, project_id, or final source metadata; those are
    assigned locally so a fabricated/garbled model response can never inject
    a fake stable id or source location."""

    source_chunk_index: int
    source_id_hint: str | None = None
    text: str
    requirement_type: RequirementType
    classification_state: ClassificationState
    rationale: str | None = None


class ExtractionBatchLLM(GeminiSchemaModel):
    requirements: list[ExtractedRequirementLLM] = Field(default_factory=list)
