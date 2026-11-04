from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.ai.exceptions import AIProviderNotConfiguredError, AIProviderQuotaExceededError, AIProviderRequestError
from app.core import project_service
from app.core.project_service import ProjectNotFoundError
from app.validators import service as validators_service
from app.validators.models import QualityIssue

router = APIRouter(prefix="/api/projects/{project_id}/quality-review", tags=["quality"])


def _ensure_project_exists(project_id: str) -> None:
    try:
        project_service.get_project(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


class RunReviewRequest(BaseModel):
    requirement_id: str | None = None
    model: str | None = None


@router.post("")
def run_review(project_id: str, body: RunReviewRequest = RunReviewRequest()) -> dict:
    _ensure_project_exists(project_id)
    try:
        return validators_service.run_quality_review(project_id, requirement_id=body.requirement_id, model=body.model)
    except AIProviderNotConfiguredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AIProviderQuotaExceededError as exc:
        raise HTTPException(
            status_code=429, detail={"message": str(exc), "retry_after_seconds": exc.retry_after_seconds}
        ) from exc
    except AIProviderRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/issues", response_model=list[QualityIssue])
def list_issues(project_id: str) -> list[QualityIssue]:
    _ensure_project_exists(project_id)
    return validators_service.list_quality_issues(project_id)


class ResolveIssueRequest(BaseModel):
    resolution_note: str | None = None


@router.post("/issues/{issue_id}/resolve", response_model=QualityIssue)
def resolve_issue(project_id: str, issue_id: str, body: ResolveIssueRequest = ResolveIssueRequest()) -> QualityIssue:
    _ensure_project_exists(project_id)
    try:
        return validators_service.resolve_quality_issue(project_id, issue_id, body.resolution_note)
    except validators_service.QualityIssueNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Quality issue not found") from exc
