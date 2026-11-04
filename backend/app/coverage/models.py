from __future__ import annotations

from pydantic import BaseModel, Field

from app.generator.models import TestCategory, TestType
from app.requirements.models import ClassificationState, RequirementType


class RequirementCoverage(BaseModel):
    requirement_id: str
    status: str  # "covered" | "partial" | "not_covered"
    test_case_count: int
    categories_covered: list[TestCategory] = Field(default_factory=list)
    types_covered: list[TestType] = Field(default_factory=list)
    missing_categories: list[TestCategory] = Field(default_factory=list)


class ProjectCoverage(BaseModel):
    total_requirements: int
    covered: int
    partial: int
    not_covered: int
    coverage_percentage: float
    weighted_coverage_percentage: float
    per_requirement: list[RequirementCoverage] = Field(default_factory=list)


class TraceabilityRow(BaseModel):
    requirement_id: str
    requirement_text: str
    requirement_type: RequirementType
    classification_state: ClassificationState
    coverage_status: str
    test_case_ids: list[str] = Field(default_factory=list)
