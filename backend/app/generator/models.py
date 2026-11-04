from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.ai.schema import GeminiSchemaModel
from app.core.models import utcnow


class TestType(str, Enum):
    BUSINESS = "business"
    APPLICATION = "application"
    SYSTEM = "system"
    INTEGRATION = "integration"
    E2E = "e2e"
    SECURITY = "security"


class TestCategory(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    EDGE = "edge"
    BOUNDARY = "boundary"
    DESTRUCTIVE = "destructive"


class Priority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class GeneratedTestCaseLLM(BaseModel):
    """What Gemini returns per test case - deliberately minimal. The model
    never produces an id, requirement id, scenario id, or source location;
    those are always assigned/copied locally, the same anti-fabrication
    pattern used for requirement ids in Phase 5."""

    scenario_description: str
    title: str
    preconditions: str = ""
    test_data: str = ""
    steps: list[str] = Field(default_factory=list)
    expected_result: str
    priority: Priority
    assumptions: str | None = None


class GeneratedTestBatchLLM(GeminiSchemaModel):
    test_cases: list[GeneratedTestCaseLLM] = Field(default_factory=list)


class TestCase(BaseModel):
    """Canonical stored record - always carries the brief's full 17-column
    schema (ARCHITECTURE.md section 6), plus a few internal bookkeeping
    fields (`project_id`, `batch_id`) not part of that schema."""

    id: str
    project_id: str
    batch_id: str

    requirement_id: str
    scenario_id: str
    scenario_description: str
    title: str  # "Test Case" column
    test_type: TestType
    test_category: TestCategory
    preconditions: str = ""
    test_data: str = ""
    steps: list[str] = Field(default_factory=list)
    expected_result: str
    priority: Priority
    source_document: str
    source_page: int | None = None
    source_section: str | None = None
    coverage_status: str = "not_assessed"  # finalized by Phase 7's coverage engine
    assumptions: str | None = None
    assumption_status: str = "none"  # "none" | "has_assumptions"
    destructive: bool = False

    approved: bool = False
    locked: bool = False
    manually_edited: bool = False

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class ManualTestCaseCreate(BaseModel):
    requirement_id: str
    scenario_description: str
    title: str
    test_type: TestType
    test_category: TestCategory
    preconditions: str = ""
    test_data: str = ""
    steps: list[str] = Field(default_factory=list)
    expected_result: str
    priority: Priority = Priority.MEDIUM
    source_document: str = "Manual"
    source_page: int | None = None
    source_section: str | None = None
    assumptions: str | None = None


class TestCaseUpdate(BaseModel):
    scenario_description: str | None = None
    title: str | None = None
    test_type: TestType | None = None
    test_category: TestCategory | None = None
    preconditions: str | None = None
    test_data: str | None = None
    steps: list[str] | None = None
    expected_result: str | None = None
    priority: Priority | None = None
    assumptions: str | None = None


class GenerationBatchSpec(BaseModel):
    batch_id: str
    requirement_id: str
    test_type: TestType
    test_category: TestCategory


class GenerationBatchResult(BaseModel):
    batch_id: str
    status: str  # "completed" | "failed"
    test_case_count: int = 0
    error: str | None = None
    completed_at: datetime | None = None


class GenerationJob(BaseModel):
    id: str
    project_id: str
    status: JobStatus = JobStatus.QUEUED
    requirement_ids: list[str]
    test_types: list[TestType]
    test_categories: list[TestCategory]
    model: str | None = None
    batches: list[GenerationBatchSpec] = Field(default_factory=list)
    results: dict[str, GenerationBatchResult] = Field(default_factory=dict)
    next_batch_index: int = 0
    error: str | None = None
    retry_after_seconds: float | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
