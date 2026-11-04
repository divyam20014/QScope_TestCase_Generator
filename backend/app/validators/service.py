from __future__ import annotations

import uuid

from app.core.models import utcnow
from app.core.paths import quality_issues_file
from app.generator import service as generator_service
from app.requirements import service as requirements_service
from app.storage.json_store import read_json, write_json
from app.validators import duplicates as duplicates_module
from app.validators import quality_review
from app.validators.models import DuplicateGroup, QualityIssue


class QualityIssueNotFoundError(LookupError):
    pass


def find_duplicates(project_id: str) -> list[DuplicateGroup]:
    test_cases = generator_service.list_test_cases(project_id)
    return duplicates_module.find_duplicates(test_cases)


def list_quality_issues(project_id: str) -> list[QualityIssue]:
    raw = read_json(quality_issues_file(project_id), default=[])
    return [QualityIssue.model_validate(q) for q in raw]


def _save_quality_issues(project_id: str, issues: list[QualityIssue]) -> None:
    write_json(quality_issues_file(project_id), [q.model_dump(mode="json") for q in issues])


def resolve_quality_issue(project_id: str, issue_id: str, resolution_note: str | None = None) -> QualityIssue:
    issues = list_quality_issues(project_id)
    target = None
    for issue in issues:
        if issue.id == issue_id:
            issue.status = "resolved"
            issue.resolved_at = utcnow()
            issue.resolution_note = resolution_note
            target = issue
    if target is None:
        raise QualityIssueNotFoundError(issue_id)
    _save_quality_issues(project_id, issues)
    return target


def run_quality_review(project_id: str, *, requirement_id: str | None = None, model: str | None = None) -> dict:
    """Idempotent per reviewed requirement: replaces that requirement's
    previously found issues rather than piling up stale duplicates across
    repeated review runs."""
    requirements = requirements_service.list_requirements(project_id)
    if requirement_id is not None:
        requirements = [r for r in requirements if r.id == requirement_id]
    reviewed_requirement_ids = {r.id for r in requirements}

    test_cases = generator_service.list_test_cases(project_id)

    new_issues: list[QualityIssue] = []
    for requirement in requirements:
        requirement_test_cases = [t for t in test_cases if t.requirement_id == requirement.id]
        for llm_issue in quality_review.review_test_cases(requirement, requirement_test_cases, model=model):
            new_issues.append(
                QualityIssue(
                    id=str(uuid.uuid4()),
                    project_id=project_id,
                    requirement_id=requirement.id,
                    test_case_id=llm_issue.test_case_id,
                    issue_type=llm_issue.issue_type,
                    explanation=llm_issue.explanation,
                    suggested_fix=llm_issue.suggested_fix,
                )
            )

    remaining = [i for i in list_quality_issues(project_id) if i.requirement_id not in reviewed_requirement_ids]
    _save_quality_issues(project_id, remaining + new_issues)

    return {"requirements_reviewed": len(requirements), "issues_found": len(new_issues)}
