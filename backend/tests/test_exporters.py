from __future__ import annotations

import csv
import io
import json

from app.coverage.models import TraceabilityRow
from app.exporters.csv_writer import write_csv
from app.exporters.data import ExportDataset
from app.exporters.docx_writer import write_docx
from app.exporters.json_writer import write_json
from app.exporters.pdf_writer import write_pdf
from app.exporters.xlsx_writer import write_xlsx
from app.generator.models import Priority, TestCase, TestCategory, TestType
from app.requirements.models import ClarificationItem, ClassificationState, RequirementType


def _dataset() -> ExportDataset:
    test_case = TestCase(
        id="TC-0001",
        project_id="p1",
        batch_id="b1",
        requirement_id="REQ-1",
        scenario_id="SC-0001",
        scenario_description="User resets password",
        title="Reset password with valid email",
        test_type=TestType.SYSTEM,
        test_category=TestCategory.POSITIVE,
        preconditions="User has an account",
        test_data="email=user@example.com",
        steps=["Open reset page", "Enter email", "Submit"],
        expected_result="A reset email is sent",
        priority=Priority.HIGH,
        source_document="spec.txt",
        source_page=1,
        coverage_status="covered",
        assumption_status="none",
    )
    traceability = TraceabilityRow(
        requirement_id="REQ-1",
        requirement_text="Users can reset their password via email.",
        requirement_type=RequirementType.FUNCTIONAL,
        classification_state=ClassificationState.CLEAR,
        coverage_status="covered",
        test_case_ids=["TC-0001"],
    )
    clarification = ClarificationItem(
        id="CL-1", project_id="p1", requirement_id="REQ-1", question="[partial] needs more detail"
    )
    return ExportDataset(test_cases=[test_case], traceability=[traceability], clarifications=[clarification])


def test_write_csv_contains_header_and_row():
    content = write_csv(_dataset())
    rows = list(csv.reader(io.StringIO(content.decode("utf-8"))))
    assert rows[0][0] == "Requirement ID"
    assert rows[1][0] == "REQ-1"
    assert rows[1][3] == "TC-0001"


def test_write_json_contains_all_three_sections():
    payload = json.loads(write_json(_dataset()).decode("utf-8"))
    assert len(payload["test_cases"]) == 1
    assert payload["test_cases"][0]["Test Case ID"] == "TC-0001"
    assert len(payload["traceability_matrix"]) == 1
    assert len(payload["clarification_register"]) == 1
    assert payload["clarification_register"][0]["Clarification ID"] == "CL-1"


def test_write_xlsx_has_three_sheets_with_data():
    from openpyxl import load_workbook

    content = write_xlsx(_dataset())
    wb = load_workbook(io.BytesIO(content))
    assert wb.sheetnames == ["Test Cases", "Traceability Matrix", "Clarification Register"]

    tc_sheet = wb["Test Cases"]
    assert tc_sheet.cell(row=1, column=1).value == "Requirement ID"
    assert tc_sheet.cell(row=2, column=4).value == "TC-0001"

    trace_sheet = wb["Traceability Matrix"]
    assert trace_sheet.cell(row=2, column=1).value == "REQ-1"

    clar_sheet = wb["Clarification Register"]
    assert clar_sheet.cell(row=2, column=1).value == "CL-1"


def test_write_docx_has_three_headings_and_tables():
    from docx import Document

    content = write_docx(_dataset(), "Demo Project")
    doc = Document(io.BytesIO(content))
    heading_texts = [p.text for p in doc.paragraphs if p.style.name.startswith("Heading")]
    assert "Test Cases" in heading_texts
    assert "Traceability Matrix" in heading_texts
    assert "Clarification Register" in heading_texts
    assert len(doc.tables) == 3
    # header row + 1 data row for the Test Cases table
    assert len(doc.tables[0].rows) == 2


def test_write_pdf_produces_valid_pdf_bytes():
    content = write_pdf(_dataset(), "Demo Project")
    assert content.startswith(b"%PDF")
    assert len(content) > 500


def test_writers_handle_empty_dataset_without_crashing():
    empty = ExportDataset(test_cases=[], traceability=[], clarifications=[])
    assert write_csv(empty)
    assert json.loads(write_json(empty).decode("utf-8"))["test_cases"] == []
    assert write_xlsx(empty)
    assert write_docx(empty, "Empty Project")
    assert write_pdf(empty, "Empty Project").startswith(b"%PDF")
