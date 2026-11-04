from __future__ import annotations

import json

from app.exporters.data import ExportDataset, clarification_to_row, test_case_to_row, traceability_to_row


def write_json(dataset: ExportDataset) -> bytes:
    payload = {
        "test_cases": [test_case_to_row(t) for t in dataset.test_cases],
        "traceability_matrix": [traceability_to_row(r) for r in dataset.traceability],
        "clarification_register": [clarification_to_row(c) for c in dataset.clarifications],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
