from __future__ import annotations

import uuid

from app.core import project_service
from app.core.paths import report_file, reports_index_file
from app.exporters import csv_writer, docx_writer, json_writer, pdf_writer, xlsx_writer
from app.exporters.data import build_export_dataset
from app.exporters.models import ExportFormat, ExportRecord, ExportScope
from app.storage.json_store import read_json, write_json

CONTENT_TYPES: dict[ExportFormat, str] = {
    ExportFormat.XLSX: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ExportFormat.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ExportFormat.PDF: "application/pdf",
    ExportFormat.CSV: "text/csv",
    ExportFormat.JSON: "application/json",
}


class ExportNotFoundError(LookupError):
    pass


def _write_content(export_format: ExportFormat, dataset, project_name: str) -> bytes:
    if export_format == ExportFormat.XLSX:
        return xlsx_writer.write_xlsx(dataset)
    if export_format == ExportFormat.DOCX:
        return docx_writer.write_docx(dataset, project_name)
    if export_format == ExportFormat.PDF:
        return pdf_writer.write_pdf(dataset, project_name)
    if export_format == ExportFormat.CSV:
        return csv_writer.write_csv(dataset)
    return json_writer.write_json(dataset)


def list_exports(project_id: str) -> list[ExportRecord]:
    raw = read_json(reports_index_file(project_id), default=[])
    return [ExportRecord.model_validate(r) for r in raw]


def _save_export_record(project_id: str, record: ExportRecord) -> None:
    records = list_exports(project_id)
    records.append(record)
    write_json(reports_index_file(project_id), [r.model_dump(mode="json") for r in records])


def create_export(project_id: str, export_format: ExportFormat, scope: ExportScope) -> ExportRecord:
    project = project_service.get_project(project_id)  # raises ProjectNotFoundError
    dataset = build_export_dataset(project_id, scope)
    content = _write_content(export_format, dataset, project.name)

    export_id = str(uuid.uuid4())
    filename = f"{export_id}.{export_format.value}"
    report_file(project_id, filename).write_bytes(content)

    record = ExportRecord(
        id=export_id,
        project_id=project_id,
        format=export_format,
        filename=filename,
        size_bytes=len(content),
        scope=scope,
        test_case_count=len(dataset.test_cases),
    )
    _save_export_record(project_id, record)
    return record


def get_export_content(project_id: str, export_id: str) -> tuple[ExportRecord, bytes]:
    record = next((r for r in list_exports(project_id) if r.id == export_id), None)
    if record is None:
        raise ExportNotFoundError(export_id)
    path = report_file(project_id, record.filename)
    if not path.exists():
        raise ExportNotFoundError(export_id)
    return record, path.read_bytes()
