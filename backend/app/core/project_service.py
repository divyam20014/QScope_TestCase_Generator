from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from app.core.models import Project, ProjectCreate, ProjectStatus, ProjectUpdate, utcnow
from app.core.paths import (
    documents_dir,
    documents_index_file,
    extracted_content_dir,
    get_data_root,
    history_dir,
    project_dir,
    reports_dir,
    requirements_dir,
    safe_join,
    test_cases_dir,
    vector_index_dir,
)
from app.storage.json_store import read_json, write_json


class ProjectNotFoundError(LookupError):
    pass


def _project_file(project_id: str) -> Path:
    return project_dir(project_id) / "project.json"


def _with_live_counts(project: Project) -> Project:
    """Document/requirement/test-case counts are derived from their own
    stores, not trusted as independently-mutated fields on project.json —
    this keeps them from drifting out of sync."""
    documents = read_json(documents_index_file(project.id), default=[])
    return project.model_copy(update={"document_count": len(documents)})


def _ensure_project_tree(project_id: str) -> None:
    documents_dir(project_id)
    extracted_content_dir(project_id)
    vector_index_dir(project_id)
    requirements_dir(project_id)
    test_cases_dir(project_id)
    reports_dir(project_id)
    history_dir(project_id)


def list_projects(include_archived: bool = True) -> list[Project]:
    projects_root = safe_join(get_data_root(), "projects")
    if not projects_root.exists():
        return []
    projects: list[Project] = []
    for entry in sorted(projects_root.iterdir()):
        if not entry.is_dir():
            continue
        data = read_json(entry / "project.json")
        if not data:
            continue
        project = _with_live_counts(Project.model_validate(data))
        if not include_archived and project.status == ProjectStatus.ARCHIVED:
            continue
        projects.append(project)
    projects.sort(key=lambda p: p.updated_at, reverse=True)
    return projects


def get_project(project_id: str) -> Project:
    data = read_json(_project_file(project_id))
    if not data:
        raise ProjectNotFoundError(project_id)
    return _with_live_counts(Project.model_validate(data))


def create_project(payload: ProjectCreate) -> Project:
    project_id = str(uuid.uuid4())
    project = Project(
        id=project_id,
        name=payload.name,
        description=payload.description,
        business_domain=payload.business_domain,
    )
    _ensure_project_tree(project_id)
    write_json(_project_file(project_id), project.model_dump(mode="json"))
    return project


def update_project(project_id: str, payload: ProjectUpdate) -> Project:
    project = get_project(project_id)
    updates = payload.model_dump(exclude_unset=True)
    updated = project.model_copy(update={**updates, "updated_at": utcnow()})
    write_json(_project_file(project_id), updated.model_dump(mode="json"))
    return updated


def set_project_status(project_id: str, status: ProjectStatus) -> Project:
    project = get_project(project_id)
    updated = project.model_copy(update={"status": status, "updated_at": utcnow()})
    write_json(_project_file(project_id), updated.model_dump(mode="json"))
    return updated


def duplicate_project(project_id: str) -> Project:
    source = get_project(project_id)
    new_id = str(uuid.uuid4())
    new_project = source.model_copy(
        update={
            "id": new_id,
            "name": f"{source.name} (Copy)",
            "created_at": utcnow(),
            "updated_at": utcnow(),
        }
    )
    source_dir = project_dir(project_id)
    dest_dir = project_dir(new_id)
    for child in source_dir.iterdir():
        if child.name == "project.json":
            continue
        dest = dest_dir / child.name
        if child.is_dir():
            shutil.copytree(child, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(child, dest)

    for other_root_name in (
        "documents",
        "extracted_content",
        "vector_indexes",
        "requirements",
        "test_cases",
        "reports",
        "history",
    ):
        src = safe_join(get_data_root(), other_root_name, project_id)
        if src.exists():
            dst = safe_join(get_data_root(), other_root_name, new_id)
            shutil.copytree(src, dst, dirs_exist_ok=True)

    documents = read_json(documents_index_file(new_id), default=[])
    if documents:
        for doc in documents:
            doc["project_id"] = new_id
        write_json(documents_index_file(new_id), documents)

    chunks_file = safe_join(get_data_root(), "vector_indexes", new_id, "chunks.json")
    chunks = read_json(chunks_file, default=[])
    if chunks:
        for chunk in chunks:
            chunk["project_id"] = new_id
        write_json(chunks_file, chunks)

    write_json(_project_file(new_id), new_project.model_dump(mode="json"))
    return new_project


def delete_project(project_id: str) -> None:
    get_project(project_id)  # raises ProjectNotFoundError if missing
    for root_name in (
        "projects",
        "documents",
        "extracted_content",
        "vector_indexes",
        "requirements",
        "test_cases",
        "reports",
        "history",
    ):
        path = safe_join(get_data_root(), root_name, project_id)
        if path.exists():
            shutil.rmtree(path)
