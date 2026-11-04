from __future__ import annotations

from app.rag.models import Chunk

DEFAULT_MAX_BATCH_CHARS = 6000


def batch_chunks(chunks: list[Chunk], max_chars: int = DEFAULT_MAX_BATCH_CHARS) -> list[list[Chunk]]:
    """Group a document's ordered chunks into Gemini-prompt-sized batches,
    never splitting a chunk's text across two batches."""
    batches: list[list[Chunk]] = []
    current: list[Chunk] = []
    current_chars = 0
    for chunk in chunks:
        if current and current_chars + len(chunk.text) > max_chars:
            batches.append(current)
            current = []
            current_chars = 0
        current.append(chunk)
        current_chars += len(chunk.text)
    if current:
        batches.append(current)
    return batches
