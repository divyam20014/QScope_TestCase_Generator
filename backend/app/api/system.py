from __future__ import annotations

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/info")
def info() -> dict:
    settings = get_settings()
    return {
        "app_name": settings.app_name,
        "gemini_configured": bool(settings.gemini_api_key),
        "gemini_default_model": settings.gemini_default_model,
        "local_data_dir": str(settings.local_data_dir),
    }
