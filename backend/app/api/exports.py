from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from app.core import project_service
from app.core.project_service import ProjectNotFoundError
from app.exporters import service as exporters_service
from app.exporters.models import ExportFormat, ExportRecord, ExportScope

router = APIRouter(prefix="/api/projects/{project_id}/exports", tags=["exports"])


def _ensure_project_exists(project_id: str) -> None:
    try:
        project_service.get_project(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


class CreateExportRequest(BaseModel):
    format: ExportFormat
    scope: ExportScope = ExportScope()


@router.post("", response_model=ExportRecord)
def create_export(project_id: str, body: CreateExportRequest) -> ExportRecord:
    _ensure_project_exists(project_id)
    try:
        return exporters_service.create_export(project_id, body.format, body.scope)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.get("", response_model=list[ExportRecord])
def list_exports(project_id: str) -> list[ExportRecord]:
    _ensure_project_exists(project_id)
    return exporters_service.list_exports(project_id)


@router.get("/{export_id}/download")
def download_export(project_id: str, export_id: str) -> Response:
    _ensure_project_exists(project_id)
    try:
        record, content = exporters_service.get_export_content(project_id, export_id)
    except exporters_service.ExportNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Export not found") from exc
    return Response(
        content=content,
        media_type=exporters_service.CONTENT_TYPES[record.format],
        headers={"Content-Disposition": f'attachment; filename="{record.filename}"'},
    )
