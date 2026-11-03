from __future__ import annotations

import hashlib
import uuid
from pathlib import Path, PurePosixPath

from app.core.document_models import DocumentRecord, DocumentStatus
from app.core.models import utcnow
from app.core.paths import documents_dir, documents_index_file, extracted_content_dir
from app.parsers.base import ParseError
from app.parsers.models import ExtractionResult, ExtractionWarning
from app.parsers.registry import SUPPORTED_EXTENSIONS, get_parser
from app.storage.json_store import read_json, write_json


class DocumentNotFoundError(LookupError):
    pass


class UnsupportedFormatError(ValueError):
    pass


def _index_path(project_id: str) -> Path:
    return documents_index_file(project_id)


def _load_index(project_id: str) -> list[DocumentRecord]:
    raw = read_json(_index_path(project_id), default=[])
    return [DocumentRecord.model_validate(item) for item in raw]


def _save_index(project_id: str, records: list[DocumentRecord]) -> None:
    write_json(_index_path(project_id), [r.model_dump(mode="json") for r in records])


def _safe_extension(filename: str) -> str:
    return PurePosixPath(filename).suffix.lower()


def list_documents(project_id: str) -> list[DocumentRecord]:
    records = _load_index(project_id)
    records.sort(key=lambda r: r.uploaded_at, reverse=True)
    return records


def get_document(project_id: str, document_id: str) -> DocumentRecord:
    for record in _load_index(project_id):
        if record.id == document_id:
            return record
    raise DocumentNotFoundError(document_id)


def get_extraction(project_id: str, document_id: str) -> ExtractionResult:
    get_document(project_id, document_id)  # raises if missing
    path = extracted_content_dir(project_id) / f"{document_id}.json"
    data = read_json(path, default=None)
    if data is None:
        return ExtractionResult()
    return ExtractionResult.model_validate(data)


def upload_document(project_id: str, filename: str, content: bytes) -> DocumentRecord:
    extension = _safe_extension(filename)
    if extension not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFormatError(
            f"Unsupported file type '{extension}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    content_hash = hashlib.sha256(content).hexdigest()
    document_id = str(uuid.uuid4())
    records = _load_index(project_id)

    duplicate_of = next((r.id for r in records if r.content_hash == content_hash), None)

    # Conflict = same filename (name AND format) but different content.
    # Different formats sharing a stem (e.g. spec.docx vs spec.pdf) are not
    # conflicting - they're just two documents that happen to share a name.
    normalized_name = PurePosixPath(filename).name.strip().lower()
    possible_conflicts = [
        r.id
        for r in records
        if r.content_hash != content_hash
        and PurePosixPath(r.filename).name.strip().lower() == normalized_name
    ]

    stored_path = documents_dir(project_id) / f"{document_id}{extension}"
    stored_path.write_bytes(content)

    record = DocumentRecord(
        id=document_id,
        project_id=project_id,
        filename=filename,
        extension=extension,
        size_bytes=len(content),
        content_hash=content_hash,
        status=DocumentStatus.PROCESSING,
        duplicate_of=duplicate_of,
        possible_conflicts=possible_conflicts,
    )

    parser = get_parser(extension)
    if parser is None:
        record.status = DocumentStatus.FAILED
        record.error = f"No parser registered for '{extension}'"
    else:
        try:
            result = parser.parse(str(stored_path))
        except ParseError as exc:
            record.status = DocumentStatus.FAILED
            record.error = str(exc)
        except Exception as exc:  # noqa: BLE001 - never let a bad document crash the upload
            record.status = DocumentStatus.FAILED
            record.error = f"Unexpected error while parsing: {exc}"
        else:
            record.status = DocumentStatus.COMPLETED
            record.warnings = [_format_warning(w) for w in result.warnings]
            record.page_count = result.page_count
            record.requires_ocr = result.requires_ocr
            record.block_count = len(result.blocks)
            write_json(extracted_content_dir(project_id) / f"{document_id}.json", result.model_dump(mode="json"))

    record.processed_at = utcnow()
    records.append(record)
    _save_index(project_id, records)

    for conflict_id in possible_conflicts:
        _flag_conflict(project_id, records, conflict_id, document_id)

    return record


def _format_warning(warning: ExtractionWarning) -> str:
    location = []
    if warning.page is not None:
        location.append(f"page {warning.page}")
    if warning.sheet is not None:
        location.append(f"sheet '{warning.sheet}'")
    suffix = f" ({', '.join(location)})" if location else ""
    return f"{warning.message}{suffix}"


def _flag_conflict(project_id: str, records: list[DocumentRecord], existing_id: str, new_id: str) -> None:
    for record in records:
        if record.id == existing_id and new_id not in record.possible_conflicts:
            record.possible_conflicts.append(new_id)
    _save_index(project_id, records)


def set_authoritative(project_id: str, document_id: str, is_authoritative: bool) -> DocumentRecord:
    records = _load_index(project_id)
    target = None
    for record in records:
        if record.id == document_id:
            record.is_authoritative = is_authoritative
            target = record
    if target is None:
        raise DocumentNotFoundError(document_id)
    _save_index(project_id, records)
    return target


def set_index_status(
    project_id: str, document_id: str, *, indexed: bool, chunk_count: int = 0, error: str | None = None
) -> DocumentRecord:
    records = _load_index(project_id)
    target = None
    for record in records:
        if record.id == document_id:
            record.indexed = indexed
            record.indexed_chunk_count = chunk_count
            record.index_error = error
            target = record
    if target is None:
        raise DocumentNotFoundError(document_id)
    _save_index(project_id, records)
    return target


def delete_document(project_id: str, document_id: str) -> None:
    records = _load_index(project_id)
    target = next((r for r in records if r.id == document_id), None)
    if target is None:
        raise DocumentNotFoundError(document_id)

    remaining = [r for r in records if r.id != document_id]
    for record in remaining:
        if document_id in record.possible_conflicts:
            record.possible_conflicts.remove(document_id)
        if record.duplicate_of == document_id:
            record.duplicate_of = None
    _save_index(project_id, remaining)

    raw_path = documents_dir(project_id) / f"{document_id}{target.extension}"
    raw_path.unlink(missing_ok=True)
    extracted_path = extracted_content_dir(project_id) / f"{document_id}.json"
    extracted_path.unlink(missing_ok=True)
