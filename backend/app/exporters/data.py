"""Selects and shapes the data every export format writer consumes, so the
17-column test-case schema (ARCHITECTURE.md section 6), the traceability
matrix, and the clarification register are defined exactly once."""

from __future__ import annotations

from dataclasses import dataclass

from app.coverage import service as coverage_service
from app.coverage.models import TraceabilityRow
from app.exporters.models import ExportScope
from app.generator import service as generator_service
from app.generator.models import TestCase
from app.requirements import service as requirements_service
from app.requirements.models import ClarificationItem

TEST_CASE_COLUMNS = [
    "Requirement ID",
    "Scenario ID",
    "Scenario Description",
    "Test Case ID",
    "Test Case",
    "Test Type",
    "Test Category",
    "Preconditions",
    "Test Data",
    "Test Steps",
    "Expected Result",
    "Priority",
    "Source Document",
    "Source Page",
    "Source Section",
    "Coverage Status",
    "Assumption Status",
]

TRACEABILITY_COLUMNS = [
    "Requirement ID",
    "Requirement Text",
    "Requirement Type",
    "Classification State",
    "Coverage Status",
    "Test Case IDs",
]

CLARIFICATION_COLUMNS = ["Clarification ID", "Requirement ID", "Question", "Status", "Resolution Note"]


@dataclass
class ExportDataset:
    test_cases: list[TestCase]
    traceability: list[TraceabilityRow]
    clarifications: list[ClarificationItem]


def select_test_cases(project_id: str, scope: ExportScope) -> list[TestCase]:
    test_cases = generator_service.list_test_cases(project_id)
    if scope.requirement_ids is not None:
        wanted = set(scope.requirement_ids)
        test_cases = [t for t in test_cases if t.requirement_id in wanted]
    if scope.test_types is not None:
        wanted_types = set(scope.test_types)
        test_cases = [t for t in test_cases if t.test_type in wanted_types]
    if scope.test_categories is not None:
        wanted_categories = set(scope.test_categories)
        test_cases = [t for t in test_cases if t.test_category in wanted_categories]
    return test_cases


def build_export_dataset(project_id: str, scope: ExportScope) -> ExportDataset:
    test_cases = select_test_cases(project_id, scope)
    traceability = coverage_service.get_traceability_matrix(project_id)
    clarifications = requirements_service.list_clarifications(project_id)

    if scope.requirement_ids is not None:
        wanted = set(scope.requirement_ids)
        traceability = [r for r in traceability if r.requirement_id in wanted]
        clarifications = [c for c in clarifications if c.requirement_id in wanted]

    return ExportDataset(test_cases=test_cases, traceability=traceability, clarifications=clarifications)


def test_case_to_row(tc: TestCase) -> dict:
    return {
        "Requirement ID": tc.requirement_id,
        "Scenario ID": tc.scenario_id,
        "Scenario Description": tc.scenario_description,
        "Test Case ID": tc.id,
        "Test Case": tc.title,
        "Test Type": tc.test_type.value,
        "Test Category": tc.test_category.value,
        "Preconditions": tc.preconditions,
        "Test Data": tc.test_data,
        "Test Steps": "\n".join(f"{i + 1}. {step}" for i, step in enumerate(tc.steps)),
        "Expected Result": tc.expected_result,
        "Priority": tc.priority.value,
        "Source Document": tc.source_document,
        "Source Page": tc.source_page if tc.source_page is not None else "",
        "Source Section": tc.source_section or "",
        "Coverage Status": tc.coverage_status,
        "Assumption Status": tc.assumption_status,
    }


def traceability_to_row(row: TraceabilityRow) -> dict:
    return {
        "Requirement ID": row.requirement_id,
        "Requirement Text": row.requirement_text,
        "Requirement Type": row.requirement_type.value,
        "Classification State": row.classification_state.value,
        "Coverage Status": row.coverage_status,
        "Test Case IDs": ", ".join(row.test_case_ids),
    }


def clarification_to_row(item: ClarificationItem) -> dict:
    return {
        "Clarification ID": item.id,
        "Requirement ID": item.requirement_id,
        "Question": item.question,
        "Status": item.status,
        "Resolution Note": item.resolution_note or "",
    }
