from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.ai.schema import GeminiSchemaModel
from app.core.models import utcnow


class DuplicateGroup(BaseModel):
    method: str  # "exact" | "normalized" | "semantic"
    test_case_ids: list[str]
    similarity: float | None = None  # set only for "semantic" groups


class QualityIssueLLM(BaseModel):
    test_case_id: str
    issue_type: str  # "weak_expected_result" | "miscategorized" | "unclear_steps" | "other"
    explanation: str
    suggested_fix: str | None = None


class QualityReviewBatchLLM(GeminiSchemaModel):
    issues: list[QualityIssueLLM] = Field(default_factory=list)


class QualityIssue(BaseModel):
    id: str
    project_id: str
    requirement_id: str
    test_case_id: str
    issue_type: str
    explanation: str
    suggested_fix: str | None = None
    status: str = "open"
    created_at: datetime = Field(default_factory=utcnow)
    resolved_at: datetime | None = None
    resolution_note: str | None = None
