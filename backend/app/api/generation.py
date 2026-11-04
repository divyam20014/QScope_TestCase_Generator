from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core import project_service
from app.core.project_service import ProjectNotFoundError
from app.generator import service as generator_service
from app.generator.models import (
    GenerationJob,
    ManualTestCaseCreate,
    TestCase,
    TestCategory,
    TestCaseUpdate,
    TestType,
)

router = APIRouter(prefix="/api/projects/{project_id}", tags=["generation"])


def _ensure_project_exists(project_id: str) -> None:
    try:
        project_service.get_project(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


def _run_and_translate_errors(fn, *args, **kwargs):
    """`run_job`/`resume_job` absorb every Gemini failure into the job's own
    state (paused on quota, failed otherwise) rather than raising - so only
    job-lookup/state errors ever reach here."""
    try:
        return fn(*args, **kwargs)
    except generator_service.JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Generation job not found") from exc
    except generator_service.InvalidJobStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


class CreateJobRequest(BaseModel):
    requirement_ids: list[str] | None = None
    test_types: list[TestType] = Field(min_length=1)
    test_categories: list[TestCategory] = Field(min_length=1)
    model: str | None = None


@router.post("/generation/jobs", response_model=GenerationJob)
def create_and_run_job(project_id: str, body: CreateJobRequest) -> GenerationJob:
    _ensure_project_exists(project_id)
    job = generator_service.create_job(
        project_id,
        requirement_ids=body.requirement_ids,
        test_types=body.test_types,
        test_categories=body.test_categories,
        model=body.model,
    )
    return _run_and_translate_errors(generator_service.run_job, project_id, job.id)


@router.get("/generation/jobs", response_model=list[GenerationJob])
def list_jobs(project_id: str) -> list[GenerationJob]:
    _ensure_project_exists(project_id)
    return generator_service.list_jobs(project_id)


@router.get("/generation/jobs/{job_id}", response_model=GenerationJob)
def get_job(project_id: str, job_id: str) -> GenerationJob:
    _ensure_project_exists(project_id)
    return _run_and_translate_errors(generator_service.get_job, project_id, job_id)


@router.post("/generation/jobs/{job_id}/resume", response_model=GenerationJob)
def resume_job(project_id: str, job_id: str) -> GenerationJob:
    _ensure_project_exists(project_id)
    return _run_and_translate_errors(generator_service.resume_job, project_id, job_id)


@router.post("/generation/jobs/{job_id}/cancel", response_model=GenerationJob)
def cancel_job(project_id: str, job_id: str) -> GenerationJob:
    _ensure_project_exists(project_id)
    return _run_and_translate_errors(generator_service.cancel_job, project_id, job_id)


def _translate_test_case_errors(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except generator_service.TestCaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Test case not found") from exc
    except generator_service.TestCaseLockedError as exc:
        raise HTTPException(status_code=409, detail="Test case is locked") from exc


@router.get("/test-cases", response_model=list[TestCase])
def list_test_cases(project_id: str) -> list[TestCase]:
    _ensure_project_exists(project_id)
    return generator_service.list_test_cases(project_id)


@router.post("/test-cases", response_model=TestCase)
def create_test_case(project_id: str, body: ManualTestCaseCreate) -> TestCase:
    _ensure_project_exists(project_id)
    return generator_service.create_manual_test_case(project_id, body)


@router.patch("/test-cases/{test_case_id}", response_model=TestCase)
def update_test_case(project_id: str, test_case_id: str, body: TestCaseUpdate) -> TestCase:
    _ensure_project_exists(project_id)
    return _translate_test_case_errors(generator_service.update_test_case, project_id, test_case_id, body)


@router.delete("/test-cases/{test_case_id}")
def delete_test_case(project_id: str, test_case_id: str) -> dict:
    _ensure_project_exists(project_id)
    _translate_test_case_errors(generator_service.delete_test_case, project_id, test_case_id)
    return {"deleted": True}


@router.post("/test-cases/{test_case_id}/copy", response_model=TestCase)
def copy_test_case(project_id: str, test_case_id: str) -> TestCase:
    _ensure_project_exists(project_id)
    return _translate_test_case_errors(generator_service.copy_test_case, project_id, test_case_id)


@router.post("/test-cases/{test_case_id}/approve", response_model=TestCase)
def approve_test_case(project_id: str, test_case_id: str, approved: bool = True) -> TestCase:
    _ensure_project_exists(project_id)
    return _translate_test_case_errors(generator_service.set_approved, project_id, test_case_id, approved)


@router.post("/test-cases/{test_case_id}/lock", response_model=TestCase)
def lock_test_case(project_id: str, test_case_id: str, locked: bool = True) -> TestCase:
    _ensure_project_exists(project_id)
    return _translate_test_case_errors(generator_service.set_locked, project_id, test_case_id, locked)


@router.get("/test-cases/{test_case_id}/history")
def get_test_case_history(project_id: str, test_case_id: str) -> list[dict]:
    _ensure_project_exists(project_id)
    return generator_service.get_test_case_history(project_id, test_case_id)


class BulkActionRequest(BaseModel):
    ids: list[str] = Field(min_length=1)
    action: str  # "approve" | "unapprove" | "lock" | "unlock" | "delete"


@router.post("/test-cases/bulk")
def bulk_test_case_action(project_id: str, body: BulkActionRequest) -> dict:
    _ensure_project_exists(project_id)
    try:
        return generator_service.bulk_update(project_id, body.ids, body.action)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
