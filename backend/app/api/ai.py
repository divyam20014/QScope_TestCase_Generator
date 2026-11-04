from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.ai import service as ai_service
from app.ai.models import AIConfig, AIConfigUpdate, ConnectionTestResult, ModelCapability, UsageStats

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.get("/models", response_model=list[ModelCapability])
def list_models() -> list[ModelCapability]:
    return ai_service.list_models()


@router.get("/config", response_model=AIConfig)
def get_config() -> AIConfig:
    return ai_service.get_config()


@router.put("/config", response_model=AIConfig)
def update_config(update: AIConfigUpdate) -> AIConfig:
    try:
        return ai_service.update_config(update)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/test-connection", response_model=ConnectionTestResult)
def test_connection(model: str | None = None) -> ConnectionTestResult:
    return ai_service.test_connection(model)


@router.get("/usage", response_model=UsageStats)
def usage() -> UsageStats:
    return ai_service.get_usage_stats()
