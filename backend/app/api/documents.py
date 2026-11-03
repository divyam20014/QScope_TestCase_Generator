from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.core import document_service, project_service
from app.core.config import get_settings
from app.core.document_models import DocumentRecord, DocumentStatus
from app.core.document_service import DocumentNotFoundError, UnsupportedFormatError
from app.core.paths import documents_dir
from app.core.project_service import ProjectNotFoundError
from app.parsers.models import ExtractionResult
from app.rag import service as rag_service

router = APIRouter(prefix="/api/projects/{project_id}/documents", tags=["documents"])


def _ensure_project_exists(project_id: str) -> None:
    try:
        project_service.get_project(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.get("", response_model=list[DocumentRecord])
def list_documents(project_id: str) -> list[DocumentRecord]:
    _ensure_project_exists(project_id)
    return document_service.list_documents(project_id)


@router.post("", response_model=list[DocumentRecord], status_code=201)
async def upload_documents(project_id: str, files: list[UploadFile]) -> list[DocumentRecord]:
    _ensure_project_exists(project_id)
    max_size = get_settings().max_upload_size_mb * 1024 * 1024

    results: list[DocumentRecord] = []
    for file in files:
        content = await file.read()
        if len(content) > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"'{file.filename}' exceeds the {get_settings().max_upload_size_mb}MB upload limit",
            )
        try:
            record = document_service.upload_document(project_id, file.filename or "untitled", content)
        except UnsupportedFormatError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        if record.status == DocumentStatus.COMPLETED:
            rag_service.index_document(project_id, record.id)
            record = document_service.get_document(project_id, record.id)
        results.append(record)
    return results


@router.get("/{document_id}", response_model=DocumentRecord)
def get_document(project_id: str, document_id: str) -> DocumentRecord:
    _ensure_project_exists(project_id)
    try:
        return document_service.get_document(project_id, document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc


@router.get("/{document_id}/preview", response_model=ExtractionResult)
def preview_document(project_id: str, document_id: str) -> ExtractionResult:
    _ensure_project_exists(project_id)
    try:
        return document_service.get_extraction(project_id, document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc


@router.get("/{document_id}/download")
def download_document(project_id: str, document_id: str) -> FileResponse:
    _ensure_project_exists(project_id)
    try:
        record = document_service.get_document(project_id, document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc

    file_path = documents_dir(project_id) / f"{document_id}{record.extension}"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Original file is missing from storage")
    return FileResponse(file_path, filename=record.filename)


@router.post("/{document_id}/authoritative", response_model=DocumentRecord)
def mark_authoritative(project_id: str, document_id: str, value: bool = True) -> DocumentRecord:
    _ensure_project_exists(project_id)
    try:
        return document_service.set_authoritative(project_id, document_id, value)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc


@router.delete("/{document_id}", status_code=204, response_model=None)
def delete_document(project_id: str, document_id: str) -> None:
    _ensure_project_exists(project_id)
    try:
        document_service.delete_document(project_id, document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
    rag_service.remove_document(project_id, document_id)
