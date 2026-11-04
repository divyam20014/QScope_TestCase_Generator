from __future__ import annotations

import io

from app.exporters.data import (
    CLARIFICATION_COLUMNS,
    TEST_CASE_COLUMNS,
    TRACEABILITY_COLUMNS,
    ExportDataset,
    clarification_to_row,
    test_case_to_row,
    traceability_to_row,
)


def _write_sheet(ws, columns: list[str], rows: list[dict]) -> None:
    from openpyxl.utils import get_column_letter

    ws.append(columns)
    for row in rows:
        ws.append([row.get(c, "") for c in columns])
    for i in range(1, len(columns) + 1):
        ws.column_dimensions[get_column_letter(i)].width = 24


def write_xlsx(dataset: ExportDataset) -> bytes:
    from openpyxl import Workbook

    workbook = Workbook()
    test_cases_sheet = workbook.active
    test_cases_sheet.title = "Test Cases"
    _write_sheet(test_cases_sheet, TEST_CASE_COLUMNS, [test_case_to_row(t) for t in dataset.test_cases])

    traceability_sheet = workbook.create_sheet("Traceability Matrix")
    _write_sheet(traceability_sheet, TRACEABILITY_COLUMNS, [traceability_to_row(r) for r in dataset.traceability])

    clarifications_sheet = workbook.create_sheet("Clarification Register")
    _write_sheet(
        clarifications_sheet, CLARIFICATION_COLUMNS, [clarification_to_row(c) for c in dataset.clarifications]
    )

    buf = io.BytesIO()
    workbook.save(buf)
    return buf.getvalue()
