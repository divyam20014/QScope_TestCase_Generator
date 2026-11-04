from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.core.models import utcnow


class ModelCapability(BaseModel):
    model_id: str
    display_name: str
    description: str = ""
    supports_structured_output: bool = True
    context_window_tokens: int
    is_default: bool = False


class AIConfig(BaseModel):
    selected_model: str
    temperature: float = Field(0.2, ge=0.0, le=2.0)
    max_output_tokens: int = Field(8192, ge=1, le=65536)
    updated_at: datetime = Field(default_factory=utcnow)


class AIConfigUpdate(BaseModel):
    selected_model: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_output_tokens: int | None = Field(default=None, ge=1, le=65536)


class ConnectionTestResult(BaseModel):
    success: bool
    model: str
    latency_ms: int | None = None
    error: str | None = None
    tested_at: datetime = Field(default_factory=utcnow)


class UsageRecord(BaseModel):
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    request_count: int = 0
    last_used_at: datetime | None = None


class UsageStats(BaseModel):
    by_model: dict[str, UsageRecord] = Field(default_factory=dict)
    total_requests: int = 0
    total_tokens: int = 0
