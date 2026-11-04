from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.ai.exceptions import GeminiNotConfiguredError, GeminiQuotaExceededError, GeminiRequestError
from app.core import project_service
from app.core.document_service import DocumentNotFoundError
from app.core.project_service import ProjectNotFoundError
from app.requirements import service as requirements_service
from app.requirements.models import ClarificationItem, Requirement

router = APIRouter(prefix="/api/projects/{project_id}/requirements", tags=["requirements"])


def _ensure_project_exists(project_id: str) -> None:
    try:
        project_service.get_project(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


def _raise_for_gemini_error(exc: Exception) -> None:
    if isinstance(exc, GeminiNotConfiguredError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, GeminiQuotaExceededError):
        raise HTTPException(
            status_code=429,
            detail={"message": str(exc), "retry_after_seconds": exc.retry_after_seconds},
        ) from exc
    if isinstance(exc, GeminiRequestError):
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    raise exc


class ExtractRequest(BaseModel):
    model: str | None = None


class ResolveClarificationRequest(BaseModel):
    resolution_note: str | None = None


@router.post("/extract")
def extract(project_id: str, body: ExtractRequest = ExtractRequest()) -> dict:
    _ensure_project_exists(project_id)
    try:
        return requirements_service.extract_for_project(project_id, model=body.model)
    except (GeminiNotConfiguredError, GeminiQuotaExceededError, GeminiRequestError) as exc:
        _raise_for_gemini_error(exc)


@router.post("/extract/{document_id}", response_model=list[Requirement])
def extract_document(project_id: str, document_id: str, body: ExtractRequest = ExtractRequest()) -> list[Requirement]:
    _ensure_project_exists(project_id)
    try:
        return requirements_service.extract_for_document(project_id, document_id, model=body.model)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
    except (GeminiNotConfiguredError, GeminiQuotaExceededError, GeminiRequestError) as exc:
        _raise_for_gemini_error(exc)


@router.get("", response_model=list[Requirement])
def list_requirements(project_id: str) -> list[Requirement]:
    _ensure_project_exists(project_id)
    return requirements_service.list_requirements(project_id)


@router.get("/clarifications", response_model=list[ClarificationItem])
def list_clarifications(project_id: str) -> list[ClarificationItem]:
    _ensure_project_exists(project_id)
    return requirements_service.list_clarifications(project_id)


@router.post("/clarifications/{clarification_id}/resolve", response_model=ClarificationItem)
def resolve_clarification(
    project_id: str, clarification_id: str, body: ResolveClarificationRequest = ResolveClarificationRequest()
) -> ClarificationItem:
    _ensure_project_exists(project_id)
    try:
        return requirements_service.resolve_clarification(project_id, clarification_id, body.resolution_note)
    except requirements_service.ClarificationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Clarification not found") from exc
