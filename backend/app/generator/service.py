"""Batched test-case generation with a resumable job state machine.

One batch = one (requirement, test_type, test_category) triple. Batches run
strictly in order; after each one finishes (success or failure) both the
generated test cases and the job's progress are persisted immediately, so a
crash or an explicit stop never loses more than the batch in flight -
`resume_job` always continues from exactly the next unfinished batch.
"""

from __future__ import annotations

import itertools
import uuid

from app.ai import service as ai_service
from app.ai.exceptions import GeminiQuotaExceededError
from app.core.models import utcnow
from app.core.paths import generation_jobs_file, test_cases_file, version_history_file
from app.generator import context as context_module
from app.generator import prompts
from app.generator.id_generator import SequentialIdAllocator
from app.generator.models import (
    GeneratedTestBatchLLM,
    GenerationBatchResult,
    GenerationBatchSpec,
    GenerationJob,
    JobStatus,
    ManualTestCaseCreate,
    TestCase,
    TestCategory,
    TestCaseUpdate,
    TestType,
)
from app.requirements import service as requirements_service
from app.storage.json_store import read_json, write_json


class JobNotFoundError(LookupError):
    pass


class InvalidJobStateError(ValueError):
    pass


class TestCaseNotFoundError(LookupError):
    pass


class TestCaseLockedError(ValueError):
    pass


# -- persistence --------------------------------------------------------


def list_test_cases(project_id: str) -> list[TestCase]:
    raw = read_json(test_cases_file(project_id), default=[])
    return [TestCase.model_validate(t) for t in raw]


def _save_test_cases(project_id: str, test_cases: list[TestCase]) -> None:
    write_json(test_cases_file(project_id), [t.model_dump(mode="json") for t in test_cases])


def replace_all_test_cases(project_id: str, test_cases: list[TestCase]) -> None:
    """Public entry point for whole-list rewrites by other modules (e.g. the
    coverage engine stamping `coverage_status` onto every test case)."""
    _save_test_cases(project_id, test_cases)


def _replace_scope_test_cases(
    project_id: str, requirement_id: str, test_type: TestType, test_category: TestCategory, new_cases: list[TestCase]
) -> None:
    """Idempotent for everything *not* protected, scoped by (requirement,
    test_type, test_category) rather than by batch id - so this covers both
    retrying the exact same batch AND a brand new job later targeting the
    same requirement/type/category (i.e. "regenerate this"). Any matching
    test case that is locked, approved, or has been manually edited is kept
    as-is and never dropped or overwritten; regeneration only ever adds
    alongside it."""

    def in_scope(t: TestCase) -> bool:
        return t.requirement_id == requirement_id and t.test_type == test_type and t.test_category == test_category

    existing = list_test_cases(project_id)
    protected = [t for t in existing if in_scope(t) and (t.locked or t.approved or t.manually_edited)]
    out_of_scope = [t for t in existing if not in_scope(t)]
    _save_test_cases(project_id, out_of_scope + protected + new_cases)


def _record_version(project_id: str, previous: TestCase) -> None:
    entries = read_json(version_history_file(project_id), default=[])
    entries.append(
        {
            "id": str(uuid.uuid4()),
            "test_case_id": previous.id,
            "snapshot": previous.model_dump(mode="json"),
            "created_at": utcnow().isoformat(),
        }
    )
    write_json(version_history_file(project_id), entries)


def get_test_case_history(project_id: str, test_case_id: str) -> list[dict]:
    entries = read_json(version_history_file(project_id), default=[])
    return [e for e in entries if e["test_case_id"] == test_case_id]


def get_test_case(project_id: str, test_case_id: str) -> TestCase:
    for test_case in list_test_cases(project_id):
        if test_case.id == test_case_id:
            return test_case
    raise TestCaseNotFoundError(test_case_id)


def create_manual_test_case(project_id: str, data: ManualTestCaseCreate) -> TestCase:
    existing = list_test_cases(project_id)
    tc_allocator = SequentialIdAllocator("TC", {t.id for t in existing})
    sc_allocator = SequentialIdAllocator("SC", {t.scenario_id for t in existing})

    test_case = TestCase(
        id=tc_allocator.allocate(),
        project_id=project_id,
        batch_id="manual",
        requirement_id=data.requirement_id,
        scenario_id=sc_allocator.allocate(),
        scenario_description=data.scenario_description,
        title=data.title,
        test_type=data.test_type,
        test_category=data.test_category,
        preconditions=data.preconditions,
        test_data=data.test_data,
        steps=data.steps,
        expected_result=data.expected_result,
        priority=data.priority,
        source_document=data.source_document,
        source_page=data.source_page,
        source_section=data.source_section,
        assumptions=data.assumptions,
        assumption_status="has_assumptions" if data.assumptions else "none",
        destructive=data.test_category == TestCategory.DESTRUCTIVE,
        manually_edited=True,
    )
    _save_test_cases(project_id, existing + [test_case])
    return test_case


def update_test_case(project_id: str, test_case_id: str, update: TestCaseUpdate) -> TestCase:
    test_cases = list_test_cases(project_id)
    target_index = next((i for i, t in enumerate(test_cases) if t.id == test_case_id), None)
    if target_index is None:
        raise TestCaseNotFoundError(test_case_id)

    current = test_cases[target_index]
    if current.locked:
        raise TestCaseLockedError(test_case_id)

    changes = update.model_dump(exclude_unset=True)
    if "assumptions" in changes:
        changes["assumption_status"] = "has_assumptions" if changes["assumptions"] else "none"
    if "test_category" in changes:
        changes["destructive"] = changes["test_category"] == TestCategory.DESTRUCTIVE
    changes["manually_edited"] = True
    changes["updated_at"] = utcnow()

    _record_version(project_id, current)
    updated = current.model_copy(update=changes)
    test_cases[target_index] = updated
    _save_test_cases(project_id, test_cases)
    return updated


def delete_test_case(project_id: str, test_case_id: str) -> None:
    test_cases = list_test_cases(project_id)
    target = next((t for t in test_cases if t.id == test_case_id), None)
    if target is None:
        raise TestCaseNotFoundError(test_case_id)
    if target.locked:
        raise TestCaseLockedError(test_case_id)
    _save_test_cases(project_id, [t for t in test_cases if t.id != test_case_id])


def copy_test_case(project_id: str, test_case_id: str) -> TestCase:
    source = get_test_case(project_id, test_case_id)
    existing = list_test_cases(project_id)
    tc_allocator = SequentialIdAllocator("TC", {t.id for t in existing})
    sc_allocator = SequentialIdAllocator("SC", {t.scenario_id for t in existing})

    copy = source.model_copy(
        update={
            "id": tc_allocator.allocate(),
            "scenario_id": sc_allocator.allocate(),
            "approved": False,
            "locked": False,
            "manually_edited": True,
            "created_at": utcnow(),
            "updated_at": utcnow(),
        }
    )
    _save_test_cases(project_id, existing + [copy])
    return copy


def set_approved(project_id: str, test_case_id: str, approved: bool) -> TestCase:
    return _set_flag(project_id, test_case_id, "approved", approved)


def set_locked(project_id: str, test_case_id: str, locked: bool) -> TestCase:
    return _set_flag(project_id, test_case_id, "locked", locked)


def _set_flag(project_id: str, test_case_id: str, field: str, value: bool) -> TestCase:
    test_cases = list_test_cases(project_id)
    target_index = next((i for i, t in enumerate(test_cases) if t.id == test_case_id), None)
    if target_index is None:
        raise TestCaseNotFoundError(test_case_id)
    updated = test_cases[target_index].model_copy(update={field: value, "updated_at": utcnow()})
    test_cases[target_index] = updated
    _save_test_cases(project_id, test_cases)
    return updated


_BULK_FLAG_ACTIONS = {
    "approve": ("approved", True),
    "unapprove": ("approved", False),
    "lock": ("locked", True),
    "unlock": ("locked", False),
}


def bulk_update(project_id: str, test_case_ids: list[str], action: str) -> dict:
    """Approve/unapprove/lock/unlock always apply regardless of current lock
    state (you must be able to unlock something, and approving never changes
    content). Only "delete" respects lock - a locked test case is skipped,
    never deleted, even when explicitly selected."""
    test_cases = list_test_cases(project_id)
    id_set = set(test_case_ids)

    if action == "delete":
        skipped_locked = [t.id for t in test_cases if t.id in id_set and t.locked]
        remaining = [t for t in test_cases if not (t.id in id_set and not t.locked)]
        changed = sum(1 for t in test_cases if t.id in id_set and not t.locked)
        _save_test_cases(project_id, remaining)
        return {"changed": changed, "skipped_locked": skipped_locked}

    if action not in _BULK_FLAG_ACTIONS:
        raise ValueError(f"Unknown bulk action '{action}'")
    field, value = _BULK_FLAG_ACTIONS[action]
    changed = sum(1 for t in test_cases if t.id in id_set)
    updated = [
        t.model_copy(update={field: value, "updated_at": utcnow()}) if t.id in id_set else t for t in test_cases
    ]
    _save_test_cases(project_id, updated)
    return {"changed": changed, "skipped_locked": []}


def list_jobs(project_id: str) -> list[GenerationJob]:
    raw = read_json(generation_jobs_file(project_id), default=[])
    return [GenerationJob.model_validate(j) for j in raw]


def get_job(project_id: str, job_id: str) -> GenerationJob:
    for job in list_jobs(project_id):
        if job.id == job_id:
            return job
    raise JobNotFoundError(job_id)


def _save_job(project_id: str, job: GenerationJob) -> None:
    jobs = [j for j in list_jobs(project_id) if j.id != job.id]
    jobs.append(job)
    write_json(generation_jobs_file(project_id), [j.model_dump(mode="json") for j in jobs])


# -- job creation --------------------------------------------------------


def create_job(
    project_id: str,
    *,
    requirement_ids: list[str] | None,
    test_types: list[TestType],
    test_categories: list[TestCategory],
    model: str | None = None,
) -> GenerationJob:
    all_requirements = requirements_service.list_requirements(project_id)
    if requirement_ids is None:
        requirement_ids = [r.id for r in all_requirements]

    batches = [
        GenerationBatchSpec(batch_id=str(uuid.uuid4()), requirement_id=requirement_id, test_type=test_type, test_category=test_category)
        for requirement_id, test_type, test_category in itertools.product(requirement_ids, test_types, test_categories)
    ]

    job = GenerationJob(
        id=str(uuid.uuid4()),
        project_id=project_id,
        requirement_ids=requirement_ids,
        test_types=test_types,
        test_categories=test_categories,
        model=model,
        batches=batches,
    )
    _save_job(project_id, job)
    return job


# -- execution -------------------------------------------------------------


def run_job(project_id: str, job_id: str) -> GenerationJob:
    job = get_job(project_id, job_id)
    if job.status not in (JobStatus.QUEUED, JobStatus.PAUSED, JobStatus.FAILED):
        raise InvalidJobStateError(f"Job '{job_id}' is '{job.status.value}' and cannot be run/resumed")

    job.status = JobStatus.RUNNING
    job.error = None
    job.retry_after_seconds = None
    job.updated_at = utcnow()
    _save_job(project_id, job)

    requirements_by_id = {r.id: r for r in requirements_service.list_requirements(project_id)}
    existing_test_case_ids = {t.id for t in list_test_cases(project_id)}
    existing_scenario_ids = {t.scenario_id for t in list_test_cases(project_id)}
    tc_allocator = SequentialIdAllocator("TC", existing_test_case_ids)
    sc_allocator = SequentialIdAllocator("SC", existing_scenario_ids)

    for index in range(job.next_batch_index, len(job.batches)):
        batch = job.batches[index]
        try:
            new_cases = _run_batch(project_id, job, batch, requirements_by_id, tc_allocator, sc_allocator)
        except GeminiQuotaExceededError as exc:
            job.status = JobStatus.PAUSED
            job.error = str(exc)
            job.retry_after_seconds = exc.retry_after_seconds
            job.updated_at = utcnow()
            _save_job(project_id, job)
            return job
        except Exception as exc:  # noqa: BLE001 - record and stop; resume retries this exact batch
            job.results[batch.batch_id] = GenerationBatchResult(batch_id=batch.batch_id, status="failed", error=str(exc))
            job.status = JobStatus.FAILED
            job.error = str(exc)
            job.updated_at = utcnow()
            _save_job(project_id, job)
            return job

        _replace_scope_test_cases(project_id, batch.requirement_id, batch.test_type, batch.test_category, new_cases)
        job.results[batch.batch_id] = GenerationBatchResult(
            batch_id=batch.batch_id, status="completed", test_case_count=len(new_cases), completed_at=utcnow()
        )
        job.next_batch_index = index + 1
        job.updated_at = utcnow()
        _save_job(project_id, job)

    job.status = JobStatus.COMPLETED
    job.updated_at = utcnow()
    _save_job(project_id, job)
    return job


def _run_batch(
    project_id: str,
    job: GenerationJob,
    batch: GenerationBatchSpec,
    requirements_by_id: dict,
    tc_allocator: SequentialIdAllocator,
    sc_allocator: SequentialIdAllocator,
) -> list[TestCase]:
    requirement = requirements_by_id.get(batch.requirement_id)
    if requirement is None:
        # The requirement was deleted/re-extracted away since the job was
        # created - nothing to generate, not a failure of generation itself.
        return []

    context_chunks = context_module.gather_context(project_id, requirement)
    prompt = prompts.build_generation_prompt(requirement, context_chunks, batch.test_type, batch.test_category)
    parsed: GeneratedTestBatchLLM = ai_service.generate_json(
        prompt=prompt, response_schema=GeneratedTestBatchLLM, model=job.model
    )

    test_cases: list[TestCase] = []
    for item in parsed.test_cases:
        test_cases.append(
            TestCase(
                id=tc_allocator.allocate(),
                project_id=project_id,
                batch_id=batch.batch_id,
                requirement_id=requirement.id,
                scenario_id=sc_allocator.allocate(),
                scenario_description=item.scenario_description,
                title=item.title,
                test_type=batch.test_type,
                test_category=batch.test_category,
                preconditions=item.preconditions,
                test_data=item.test_data,
                steps=item.steps,
                expected_result=item.expected_result,
                priority=item.priority,
                source_document=requirement.source.document_name,
                source_page=requirement.source.page,
                source_section=requirement.source.section,
                assumptions=item.assumptions,
                assumption_status="has_assumptions" if item.assumptions else "none",
                destructive=batch.test_category == TestCategory.DESTRUCTIVE,
            )
        )
    return test_cases


def resume_job(project_id: str, job_id: str) -> GenerationJob:
    return run_job(project_id, job_id)


def cancel_job(project_id: str, job_id: str) -> GenerationJob:
    job = get_job(project_id, job_id)
    if job.status in (JobStatus.COMPLETED, JobStatus.CANCELLED):
        raise InvalidJobStateError(f"Job '{job_id}' is already '{job.status.value}'")
    job.status = JobStatus.CANCELLED
    job.updated_at = utcnow()
    _save_job(project_id, job)
    return job
