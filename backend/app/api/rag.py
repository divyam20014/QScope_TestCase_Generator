from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.core import project_service
from app.core.project_service import ProjectNotFoundError
from app.rag import service as rag_service
from app.rag.models import SearchHit

router = APIRouter(prefix="/api/projects/{project_id}/rag", tags=["rag"])


def _ensure_project_exists(project_id: str) -> None:
    try:
        project_service.get_project(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.get("/search", response_model=list[SearchHit])
def search(
    project_id: str,
    q: str = Query(..., min_length=1),
    top_k: int = Query(5, ge=1, le=50),
    mode: str = Query("hybrid", pattern="^(hybrid|semantic|keyword)$"),
    semantic_weight: float = Query(0.5, ge=0.0, le=1.0),
) -> list[SearchHit]:
    _ensure_project_exists(project_id)
    return rag_service.search(project_id, q, top_k=top_k, mode=mode, semantic_weight=semantic_weight)


@router.post("/reindex")
def reindex(project_id: str) -> dict:
    _ensure_project_exists(project_id)
    return rag_service.reindex_project(project_id)


@router.get("/stats")
def stats(project_id: str) -> dict:
    _ensure_project_exists(project_id)
    return rag_service.stats(project_id)
