"""Deterministic, rule-based coverage engine - no LLM call anywhere in this
module, so results are exactly reproducible from the same requirements/test
cases every time.

A requirement is "covered" once it has at least one positive AND one
negative test case (the minimum baseline for "this is actually tested"),
"partial" if it has test cases but not both, and "not_covered" if it has
none at all.
"""

from __future__ import annotations

from app.coverage.models import ProjectCoverage, RequirementCoverage, TraceabilityRow
from app.generator.models import TestCase, TestCategory
from app.requirements.models import Requirement

REQUIRED_CATEGORIES_FOR_COVERED = {TestCategory.POSITIVE, TestCategory.NEGATIVE}


def compute_requirement_coverage(requirement_id: str, test_cases: list[TestCase]) -> RequirementCoverage:
    cases = [t for t in test_cases if t.requirement_id == requirement_id]
    categories = {t.test_category for t in cases}
    types = {t.test_type for t in cases}

    if not cases:
        status = "not_covered"
    elif REQUIRED_CATEGORIES_FOR_COVERED.issubset(categories):
        status = "covered"
    else:
        status = "partial"

    return RequirementCoverage(
        requirement_id=requirement_id,
        status=status,
        test_case_count=len(cases),
        categories_covered=sorted(categories, key=lambda c: c.value),
        types_covered=sorted(types, key=lambda t: t.value),
        missing_categories=sorted(REQUIRED_CATEGORIES_FOR_COVERED - categories, key=lambda c: c.value),
    )


def compute_project_coverage(requirements: list[Requirement], test_cases: list[TestCase]) -> ProjectCoverage:
    per_requirement = [compute_requirement_coverage(r.id, test_cases) for r in requirements]
    total = len(per_requirement)
    covered = sum(1 for c in per_requirement if c.status == "covered")
    partial = sum(1 for c in per_requirement if c.status == "partial")
    not_covered = total - covered - partial

    coverage_percentage = round((covered / total) * 100, 2) if total else 0.0
    weighted_coverage_percentage = round(((covered + 0.5 * partial) / total) * 100, 2) if total else 0.0

    return ProjectCoverage(
        total_requirements=total,
        covered=covered,
        partial=partial,
        not_covered=not_covered,
        coverage_percentage=coverage_percentage,
        weighted_coverage_percentage=weighted_coverage_percentage,
        per_requirement=per_requirement,
    )


def build_traceability_matrix(requirements: list[Requirement], test_cases: list[TestCase]) -> list[TraceabilityRow]:
    test_case_ids_by_requirement: dict[str, list[str]] = {}
    for t in test_cases:
        test_case_ids_by_requirement.setdefault(t.requirement_id, []).append(t.id)

    rows = []
    for requirement in requirements:
        coverage = compute_requirement_coverage(requirement.id, test_cases)
        rows.append(
            TraceabilityRow(
                requirement_id=requirement.id,
                requirement_text=requirement.text,
                requirement_type=requirement.requirement_type,
                classification_state=requirement.classification_state,
                coverage_status=coverage.status,
                test_case_ids=test_case_ids_by_requirement.get(requirement.id, []),
            )
        )
    return rows
