"""Orchestrates requirement extraction: pulls a document's indexed RAG
chunks, calls Gemini (via app.ai.service) to extract+classify requirements,
assigns stable ids, and persists requirements + a clarification register per
project. Re-extracting a document is idempotent - it replaces exactly that
document's requirements and clarifications, leaving every other document's
requirements untouched (mirrors the RAG index's per-document replace
semantics)."""

from __future__ import annotations

import uuid

from app.core import document_service
from app.core.document_models import DocumentStatus
from app.core.models import utcnow
from app.core.paths import clarifications_file, requirements_file
from app.rag import service as rag_service
from app.requirements import extraction
from app.requirements.id_generator import RequirementIdAllocator
from app.requirements.models import ClarificationItem, ClassificationState, Requirement, RequirementSource
from app.storage.json_store import read_json, write_json


class ClarificationNotFoundError(LookupError):
    pass


def list_requirements(project_id: str) -> list[Requirement]:
    raw = read_json(requirements_file(project_id), default=[])
    return [Requirement.model_validate(r) for r in raw]


def _save_requirements(project_id: str, requirements: list[Requirement]) -> None:
    write_json(requirements_file(project_id), [r.model_dump(mode="json") for r in requirements])


def list_clarifications(project_id: str) -> list[ClarificationItem]:
    raw = read_json(clarifications_file(project_id), default=[])
    return [ClarificationItem.model_validate(c) for c in raw]


def _save_clarifications(project_id: str, items: list[ClarificationItem]) -> None:
    write_json(clarifications_file(project_id), [c.model_dump(mode="json") for c in items])


def _clarification_question(requirement: Requirement) -> str:
    state = requirement.classification_state.value
    if requirement.rationale:
        return f"[{state}] {requirement.rationale}"
    return f"Requirement is {state} and needs review."


def resolve_clarification(project_id: str, clarification_id: str, resolution_note: str | None = None) -> ClarificationItem:
    items = list_clarifications(project_id)
    target = None
    for item in items:
        if item.id == clarification_id:
            item.status = "resolved"
            item.resolved_at = utcnow()
            item.resolution_note = resolution_note
            target = item
    if target is None:
        raise ClarificationNotFoundError(clarification_id)
    _save_clarifications(project_id, items)
    return target


def extract_for_document(project_id: str, document_id: str, *, model: str | None = None) -> list[Requirement]:
    document = document_service.get_document(project_id, document_id)  # raises DocumentNotFoundError
    chunks = rag_service.chunks_for_document(project_id, document_id)

    existing_all = list_requirements(project_id)
    other_doc_requirements = [r for r in existing_all if r.source.document_id != document_id]
    old_doc_requirement_ids = {r.id for r in existing_all if r.source.document_id == document_id}

    new_requirements: list[Requirement] = []
    if chunks:
        extracted = extraction.extract_from_chunks(document.filename, chunks, model=model)
        allocator = RequirementIdAllocator({r.id for r in other_doc_requirements})

        for item, source_chunk in extracted:
            requirement = Requirement(
                id=allocator.allocate(item.requirement_type, item.source_id_hint),
                project_id=project_id,
                source_id_hint=item.source_id_hint,
                text=item.text,
                requirement_type=item.requirement_type,
                classification_state=item.classification_state,
                rationale=item.rationale,
                source=RequirementSource(
                    document_id=document_id,
                    document_name=document.filename,
                    page=source_chunk.page,
                    sheet=source_chunk.sheet,
                    section=source_chunk.section,
                    chunk_ids=[source_chunk.chunk_id],
                ),
            )
            new_requirements.append(requirement)

    _save_requirements(project_id, other_doc_requirements + new_requirements)

    new_clarifications = [
        ClarificationItem(
            id=str(uuid.uuid4()),
            project_id=project_id,
            requirement_id=requirement.id,
            question=_clarification_question(requirement),
        )
        for requirement in new_requirements
        if requirement.classification_state != ClassificationState.CLEAR
    ]
    remaining_clarifications = [c for c in list_clarifications(project_id) if c.requirement_id not in old_doc_requirement_ids]
    _save_clarifications(project_id, remaining_clarifications + new_clarifications)

    return new_requirements


def extract_for_project(project_id: str, *, model: str | None = None) -> dict:
    documents = [d for d in document_service.list_documents(project_id) if d.status == DocumentStatus.COMPLETED]
    per_document: dict[str, int] = {}
    total = 0
    for document in documents:
        requirements = extract_for_document(project_id, document.id, model=model)
        per_document[document.id] = len(requirements)
        total += len(requirements)
    return {"documents_processed": len(documents), "requirements_extracted": total, "per_document": per_document}


