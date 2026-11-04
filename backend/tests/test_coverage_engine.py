from __future__ import annotations

from app.coverage.engine import build_traceability_matrix, compute_project_coverage, compute_requirement_coverage
from app.generator.models import Priority, TestCase, TestCategory, TestType
from app.requirements.models import ClassificationState, Requirement, RequirementSource, RequirementType


def _requirement(req_id: str) -> Requirement:
    return Requirement(
        id=req_id,
        project_id="p1",
        text=f"Requirement {req_id}",
        requirement_type=RequirementType.FUNCTIONAL,
        classification_state=ClassificationState.CLEAR,
        source=RequirementSource(document_id="d1", document_name="spec.txt"),
    )


def _test_case(requirement_id: str, category: TestCategory, tc_id: str | None = None) -> TestCase:
    return TestCase(
        id=tc_id or f"TC-{requirement_id}-{category.value}",
        project_id="p1",
        batch_id="b1",
        requirement_id=requirement_id,
        scenario_id=f"SC-{requirement_id}-{category.value}",
        scenario_description="scenario",
        title="title",
        test_type=TestType.SYSTEM,
        test_category=category,
        expected_result="expected",
        priority=Priority.MEDIUM,
        source_document="spec.txt",
    )


def test_requirement_with_no_test_cases_is_not_covered():
    coverage = compute_requirement_coverage("REQ-1", [])
    assert coverage.status == "not_covered"
    assert coverage.test_case_count == 0
    assert coverage.missing_categories == [TestCategory.NEGATIVE, TestCategory.POSITIVE]


def test_requirement_with_only_positive_is_partial():
    cases = [_test_case("REQ-1", TestCategory.POSITIVE)]
    coverage = compute_requirement_coverage("REQ-1", cases)
    assert coverage.status == "partial"
    assert coverage.missing_categories == [TestCategory.NEGATIVE]


def test_requirement_with_positive_and_negative_is_covered():
    cases = [_test_case("REQ-1", TestCategory.POSITIVE), _test_case("REQ-1", TestCategory.NEGATIVE)]
    coverage = compute_requirement_coverage("REQ-1", cases)
    assert coverage.status == "covered"
    assert coverage.missing_categories == []
    assert coverage.categories_covered == [TestCategory.NEGATIVE, TestCategory.POSITIVE]


def test_project_coverage_percentages_are_deterministic():
    requirements = [_requirement("REQ-1"), _requirement("REQ-2"), _requirement("REQ-3")]
    test_cases = [
        _test_case("REQ-1", TestCategory.POSITIVE),
        _test_case("REQ-1", TestCategory.NEGATIVE),
        _test_case("REQ-2", TestCategory.POSITIVE),
        # REQ-3 has no test cases at all.
    ]
    coverage = compute_project_coverage(requirements, test_cases)
    assert coverage.total_requirements == 3
    assert coverage.covered == 1
    assert coverage.partial == 1
    assert coverage.not_covered == 1
    assert coverage.coverage_percentage == round(1 / 3 * 100, 2)
    assert coverage.weighted_coverage_percentage == round((1 + 0.5) / 3 * 100, 2)

    # Recomputing from the exact same inputs must yield the exact same numbers.
    coverage_again = compute_project_coverage(requirements, test_cases)
    assert coverage_again.model_dump() == coverage.model_dump()


def test_project_coverage_handles_zero_requirements():
    coverage = compute_project_coverage([], [])
    assert coverage.total_requirements == 0
    assert coverage.coverage_percentage == 0.0
    assert coverage.weighted_coverage_percentage == 0.0


def test_traceability_matrix_links_requirement_to_its_test_case_ids():
    requirements = [_requirement("REQ-1")]
    test_cases = [
        _test_case("REQ-1", TestCategory.POSITIVE, tc_id="TC-0001"),
        _test_case("REQ-1", TestCategory.NEGATIVE, tc_id="TC-0002"),
    ]
    rows = build_traceability_matrix(requirements, test_cases)
    assert len(rows) == 1
    assert rows[0].requirement_id == "REQ-1"
    assert sorted(rows[0].test_case_ids) == ["TC-0001", "TC-0002"]
    assert rows[0].coverage_status == "covered"
