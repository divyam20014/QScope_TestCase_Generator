from __future__ import annotations

from app.rag.models import Chunk
from app.requirements.batching import batch_chunks
from app.requirements.extraction import extract_from_chunks
from app.requirements.models import ClassificationState, ExtractedRequirementLLM, ExtractionBatchLLM, RequirementType
from app.requirements.prompts import build_extraction_prompt


def _chunk(chunk_id: int, text: str, page: int = 1) -> Chunk:
    return Chunk(chunk_id=chunk_id, project_id="p1", document_id="d1", document_name="spec.txt", page=page, text=text)


def test_batch_chunks_splits_on_char_budget():
    chunks = [_chunk(i, "x" * 50) for i in range(5)]
    batches = batch_chunks(chunks, max_chars=120)
    assert sum(len(b) for b in batches) == 5
    for batch in batches:
        assert sum(len(c.text) for c in batch) <= 120 or len(batch) == 1


def test_batch_chunks_never_empty_for_oversized_single_chunk():
    chunks = [_chunk(0, "x" * 500)]
    batches = batch_chunks(chunks, max_chars=100)
    assert batches == [[chunks[0]]]


def test_build_extraction_prompt_numbers_chunks_and_includes_text():
    chunks = [_chunk(0, "REQ-1: Users can log in."), _chunk(1, "REQ-2: Users can log out.")]
    prompt = build_extraction_prompt("spec.txt", chunks)
    assert "[chunk 0]" in prompt
    assert "[chunk 1]" in prompt
    assert "REQ-1: Users can log in." in prompt
    assert "spec.txt" in prompt


def test_extract_from_chunks_maps_source_chunk_index(monkeypatch):
    chunks = [_chunk(10, "REQ-1: Users can log in.", page=1), _chunk(11, "REQ-2: Users can log out.", page=2)]

    fake_result = ExtractionBatchLLM(
        requirements=[
            ExtractedRequirementLLM(
                source_chunk_index=1,
                source_id_hint="REQ-2",
                text="Users can log out.",
                requirement_type=RequirementType.FUNCTIONAL,
                classification_state=ClassificationState.CLEAR,
            )
        ]
    )
    monkeypatch.setattr("app.requirements.extraction.ai_service.generate_json", lambda **kwargs: fake_result)

    results = extract_from_chunks("spec.txt", chunks)
    assert len(results) == 1
    item, source_chunk = results[0]
    assert item.source_id_hint == "REQ-2"
    assert source_chunk.chunk_id == 11
    assert source_chunk.page == 2


def test_extract_from_chunks_clamps_out_of_range_index(monkeypatch):
    chunks = [_chunk(10, "REQ-1: Users can log in.")]

    fake_result = ExtractionBatchLLM(
        requirements=[
            ExtractedRequirementLLM(
                source_chunk_index=99,
                text="Users can log in.",
                requirement_type=RequirementType.FUNCTIONAL,
                classification_state=ClassificationState.CLEAR,
            )
        ]
    )
    monkeypatch.setattr("app.requirements.extraction.ai_service.generate_json", lambda **kwargs: fake_result)

    results = extract_from_chunks("spec.txt", chunks)
    assert len(results) == 1
    _, source_chunk = results[0]
    assert source_chunk.chunk_id == 10
