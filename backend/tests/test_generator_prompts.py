from __future__ import annotations

from app.generator.models import TestCategory, TestType
from app.generator.prompts import build_generation_prompt
from app.rag.models import Chunk
from app.requirements.models import ClassificationState, Requirement, RequirementSource, RequirementType


def _requirement() -> Requirement:
    return Requirement(
        id="REQ-1",
        project_id="p1",
        text="Users can reset their password via email.",
        requirement_type=RequirementType.FUNCTIONAL,
        classification_state=ClassificationState.CLEAR,
        source=RequirementSource(document_id="d1", document_name="spec.txt", page=3, chunk_ids=[0]),
    )


def _chunk() -> Chunk:
    return Chunk(chunk_id=0, project_id="p1", document_id="d1", document_name="spec.txt", page=3, text="REQ-1: Users can reset their password via email.")


def test_prompt_includes_requirement_id_and_text():
    prompt = build_generation_prompt(_requirement(), [_chunk()], TestType.SYSTEM, TestCategory.POSITIVE)
    assert "REQ-1" in prompt
    assert "Users can reset their password via email." in prompt


def test_prompt_includes_category_and_type_definitions():
    prompt = build_generation_prompt(_requirement(), [_chunk()], TestType.SECURITY, TestCategory.DESTRUCTIVE)
    assert "destructive" in prompt
    assert "security" in prompt
    assert "safe, isolated test" in prompt


def test_prompt_numbers_context_chunks_with_source():
    prompt = build_generation_prompt(_requirement(), [_chunk()], TestType.SYSTEM, TestCategory.POSITIVE)
    assert "[context 0]" in prompt
    assert "spec.txt" in prompt
    assert "page 3" in prompt


def test_prompt_marks_source_content_as_untrusted():
    prompt = build_generation_prompt(_requirement(), [_chunk()], TestType.SYSTEM, TestCategory.POSITIVE)
    assert "untrusted" in prompt.lower()
