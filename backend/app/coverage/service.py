from __future__ import annotations

from app.coverage.engine import build_traceability_matrix, compute_project_coverage
from app.coverage.models import ProjectCoverage, TraceabilityRow
from app.generator import service as generator_service
from app.requirements import service as requirements_service


def get_project_coverage(project_id: str) -> ProjectCoverage:
    requirements = requirements_service.list_requirements(project_id)
    test_cases = generator_service.list_test_cases(project_id)
    coverage = compute_project_coverage(requirements, test_cases)
    _stamp_coverage_status(project_id, test_cases, coverage)
    return coverage


def get_traceability_matrix(project_id: str) -> list[TraceabilityRow]:
    requirements = requirements_service.list_requirements(project_id)
    test_cases = generator_service.list_test_cases(project_id)
    return build_traceability_matrix(requirements, test_cases)


def _stamp_coverage_status(project_id: str, test_cases, coverage: ProjectCoverage) -> None:
    """Writes the just-computed, deterministic coverage status onto every
    test case's `coverage_status` column so exports/UI reflect it without
    recomputing - recomputed fresh on every `get_project_coverage` call, so
    it can never drift from the current requirements/test cases."""
    status_by_requirement = {c.requirement_id: c.status for c in coverage.per_requirement}
    changed = False
    for test_case in test_cases:
        new_status = status_by_requirement.get(test_case.requirement_id, "not_covered")
        if test_case.coverage_status != new_status:
            test_case.coverage_status = new_status
            changed = True
    if changed:
        generator_service.replace_all_test_cases(project_id, test_cases)
