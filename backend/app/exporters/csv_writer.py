"""CSV is inherently single-table, so (unlike xlsx/docx/pdf/json) a CSV
export contains only the Test Cases table - the traceability matrix and
clarification register have no sheet/section to live in. Documented as a
known limitation rather than worked around with a zip-of-CSVs."""

from __future__ import annotations

import csv
import io

from app.exporters.data import TEST_CASE_COLUMNS, ExportDataset, test_case_to_row


def write_csv(dataset: ExportDataset) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=TEST_CASE_COLUMNS)
    writer.writeheader()
    for test_case in dataset.test_cases:
        writer.writerow(test_case_to_row(test_case))
    return buf.getvalue().encode("utf-8")
