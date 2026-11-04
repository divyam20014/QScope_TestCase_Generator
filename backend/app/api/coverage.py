from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core import project_service
from app.core.project_service import ProjectNotFoundError
from app.coverage import service as coverage_service
from app.coverage.models import ProjectCoverage, TraceabilityRow
from app.validators import service as validators_service
from app.validators.models import DuplicateGroup

router = APIRouter(prefix="/api/projects/{project_id}/coverage", tags=["coverage"])


def _ensure_project_exists(project_id: str) -> None:
    try:
        project_service.get_project(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.get("", response_model=ProjectCoverage)
def get_coverage(project_id: str) -> ProjectCoverage:
    _ensure_project_exists(project_id)
    return coverage_service.get_project_coverage(project_id)


@router.get("/traceability", response_model=list[TraceabilityRow])
def get_traceability(project_id: str) -> list[TraceabilityRow]:
    _ensure_project_exists(project_id)
    return coverage_service.get_traceability_matrix(project_id)


@router.get("/duplicates", response_model=list[DuplicateGroup])
def get_duplicates(project_id: str) -> list[DuplicateGroup]:
    _ensure_project_exists(project_id)
    return validators_service.find_duplicates(project_id)
