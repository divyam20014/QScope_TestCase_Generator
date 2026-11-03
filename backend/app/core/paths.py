"""Filesystem sandboxing helpers.

All project data lives under `local_data/`. Every path derived from
user-controlled input (project IDs, document IDs, filenames) must be
resolved through `safe_join` so that path traversal (`..`, absolute paths,
symlink escapes) cannot reach outside the sandbox root.
"""

from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings


class PathTraversalError(ValueError):
    pass


def get_data_root() -> Path:
    root = get_settings().local_data_dir
    root.mkdir(parents=True, exist_ok=True)
    return root


def safe_join(root: Path, *parts: str) -> Path:
    """Join `parts` onto `root`, guaranteeing the result stays under `root`."""
    root = root.resolve()
    candidate = root.joinpath(*parts).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise PathTraversalError(f"Path '{candidate}' escapes sandbox root '{root}'") from exc
    return candidate


def project_dir(project_id: str) -> Path:
    path = safe_join(get_data_root(), "projects", project_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def projects_index_file() -> Path:
    return safe_join(get_data_root(), "projects", "_index.json")


def documents_dir(project_id: str) -> Path:
    path = safe_join(get_data_root(), "documents", project_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def documents_index_file(project_id: str) -> Path:
    return project_dir(project_id) / "documents.json"


def extracted_content_dir(project_id: str) -> Path:
    path = safe_join(get_data_root(), "extracted_content", project_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def vector_index_dir(project_id: str) -> Path:
    path = safe_join(get_data_root(), "vector_indexes", project_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def vector_index_faiss_file(project_id: str) -> Path:
    return vector_index_dir(project_id) / "faiss.index"


def vector_index_chunks_file(project_id: str) -> Path:
    return vector_index_dir(project_id) / "chunks.json"


def vector_index_meta_file(project_id: str) -> Path:
    return vector_index_dir(project_id) / "meta.json"


def requirements_dir(project_id: str) -> Path:
    path = safe_join(get_data_root(), "requirements", project_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_cases_dir(project_id: str) -> Path:
    path = safe_join(get_data_root(), "test_cases", project_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def reports_dir(project_id: str) -> Path:
    path = safe_join(get_data_root(), "reports", project_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def history_dir(project_id: str) -> Path:
    path = safe_join(get_data_root(), "history", project_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def configurations_dir() -> Path:
    path = safe_join(get_data_root(), "configurations")
    path.mkdir(parents=True, exist_ok=True)
    return path


def templates_dir(project_id: str | None = None) -> Path:
    path = safe_join(get_data_root(), "templates", project_id or "global")
    path.mkdir(parents=True, exist_ok=True)
    return path
