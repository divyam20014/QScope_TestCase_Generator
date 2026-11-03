from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core import project_service
from app.core.models import Project, ProjectCreate, ProjectStatus, ProjectUpdate
from app.core.project_service import ProjectNotFoundError
from app.rag.service import drop_cached_index

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[Project])
def list_projects(include_archived: bool = True) -> list[Project]:
    return project_service.list_projects(include_archived=include_archived)


@router.post("", response_model=Project, status_code=201)
def create_project(payload: ProjectCreate) -> Project:
    return project_service.create_project(payload)


@router.get("/{project_id}", response_model=Project)
def get_project(project_id: str) -> Project:
    try:
        return project_service.get_project(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.patch("/{project_id}", response_model=Project)
def update_project(project_id: str, payload: ProjectUpdate) -> Project:
    try:
        return project_service.update_project(project_id, payload)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.post("/{project_id}/archive", response_model=Project)
def archive_project(project_id: str) -> Project:
    try:
        return project_service.set_project_status(project_id, ProjectStatus.ARCHIVED)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.post("/{project_id}/restore", response_model=Project)
def restore_project(project_id: str) -> Project:
    try:
        return project_service.set_project_status(project_id, ProjectStatus.ACTIVE)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.post("/{project_id}/duplicate", response_model=Project, status_code=201)
def duplicate_project(project_id: str) -> Project:
    try:
        return project_service.duplicate_project(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.delete("/{project_id}", status_code=204, response_model=None)
def delete_project(project_id: str) -> None:
    try:
        project_service.delete_project(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    drop_cached_index(project_id)
