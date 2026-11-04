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


def _add_table(doc, columns: list[str], rows: list[dict]) -> None:
    if not rows:
        doc.add_paragraph("(none)")
        return
    table = doc.add_table(rows=1, cols=len(columns))
    table.style = "Light Grid Accent 1"
    for i, col in enumerate(columns):
        table.rows[0].cells[i].text = col
    for row in rows:
        cells = table.add_row().cells
        for i, col in enumerate(columns):
            cells[i].text = str(row.get(col, ""))


def write_docx(dataset: ExportDataset, project_name: str) -> bytes:
    from docx import Document

    doc = Document()
    doc.add_heading(f"{project_name} - Test Case Report", level=1)

    doc.add_heading("Test Cases", level=2)
    _add_table(doc, TEST_CASE_COLUMNS, [test_case_to_row(t) for t in dataset.test_cases])

    doc.add_heading("Traceability Matrix", level=2)
    _add_table(doc, TRACEABILITY_COLUMNS, [traceability_to_row(r) for r in dataset.traceability])

    doc.add_heading("Clarification Register", level=2)
    _add_table(doc, CLARIFICATION_COLUMNS, [clarification_to_row(c) for c in dataset.clarifications])

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
