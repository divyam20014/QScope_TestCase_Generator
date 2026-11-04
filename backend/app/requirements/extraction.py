from __future__ import annotations

from app.ai import service as ai_service
from app.rag.models import Chunk
from app.requirements.batching import batch_chunks
from app.requirements.models import ExtractedRequirementLLM, ExtractionBatchLLM
from app.requirements.prompts import build_extraction_prompt


def extract_from_chunks(
    document_name: str, chunks: list[Chunk], *, model: str | None = None
) -> list[tuple[ExtractedRequirementLLM, Chunk]]:
    """Batch a document's chunks into Gemini calls and pair each extracted
    requirement with the exact chunk it was attributed to, so every
    requirement carries a real page/section/document source ref."""
    results: list[tuple[ExtractedRequirementLLM, Chunk]] = []
    for batch in batch_chunks(chunks):
        prompt = build_extraction_prompt(document_name, batch)
        parsed = ai_service.generate_json(prompt=prompt, response_schema=ExtractionBatchLLM, model=model)
        for item in parsed.requirements:
            index = item.source_chunk_index
            source_chunk = batch[index] if 0 <= index < len(batch) else batch[0]
            results.append((item, source_chunk))
    return results
