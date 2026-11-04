"""17 columns at landscape-letter width is dense even at a small font - a
known readability trade-off for keeping the PDF's schema identical to every
other format rather than silently dropping columns. Documented in
IMPLEMENTATION_STATUS.md."""

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


def _build_table(columns: list[str], rows: list[dict], styles):
    from reportlab.lib import colors
    from reportlab.platypus import Paragraph, Table, TableStyle

    cell_style = styles["BodyText"]
    cell_style.fontSize = 7
    cell_style.leading = 9

    if not rows:
        return Paragraph("(none)", styles["Normal"])

    header = [Paragraph(f"<b>{c}</b>", cell_style) for c in columns]
    data = [header]
    for row in rows:
        data.append([Paragraph(str(row.get(c, "")).replace("\n", "<br/>"), cell_style) for c in columns])

    table = Table(data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5e7eb")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def write_pdf(dataset: ExportDataset, project_name: str) -> bytes:
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(letter))
    styles = getSampleStyleSheet()

    elements = [Paragraph(f"{project_name} - Test Case Report", styles["Title"]), Spacer(1, 12)]

    elements.append(Paragraph("Test Cases", styles["Heading2"]))
    elements.append(_build_table(TEST_CASE_COLUMNS, [test_case_to_row(t) for t in dataset.test_cases], styles))
    elements.append(Spacer(1, 16))

    elements.append(Paragraph("Traceability Matrix", styles["Heading2"]))
    elements.append(_build_table(TRACEABILITY_COLUMNS, [traceability_to_row(r) for r in dataset.traceability], styles))
    elements.append(Spacer(1, 16))

    elements.append(Paragraph("Clarification Register", styles["Heading2"]))
    elements.append(
        _build_table(CLARIFICATION_COLUMNS, [clarification_to_row(c) for c in dataset.clarifications], styles)
    )

    doc.build(elements)
    return buf.getvalue()
