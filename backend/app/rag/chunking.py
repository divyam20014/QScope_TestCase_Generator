from __future__ import annotations

from app.parsers.models import BlockType, ExtractedBlock

DEFAULT_MAX_CHARS = 800


class PendingChunk:
    def __init__(self, page: int | None, sheet: str | None, section: str | None) -> None:
        self.page = page
        self.sheet = sheet
        self.section = section
        self.parts: list[str] = []

    def char_count(self) -> int:
        return sum(len(p) for p in self.parts)

    def text(self) -> str:
        return "\n".join(self.parts)


def _table_to_text(block: ExtractedBlock) -> str:
    if not block.table_data:
        return block.text
    rows = [" | ".join(cell for cell in row) for row in block.table_data]
    return "\n".join(rows)


def chunk_blocks(
    blocks: list[ExtractedBlock], max_chars: int = DEFAULT_MAX_CHARS
) -> list[dict]:
    """Group extracted blocks into semantically coherent chunks.

    Tables are always their own chunk (mixing tabular and prose content
    confuses retrieval). Headings start a new section context. Paragraphs
    and list items accumulate under the current section until `max_chars`
    is reached, then flush — never splitting a block mid-text. Exact-text
    duplicate chunks (e.g. a repeated boilerplate header) are dropped.
    """
    results: list[dict] = []
    seen_text: set[str] = set()
    pending: PendingChunk | None = None
    current_section: str | None = None

    def flush() -> None:
        nonlocal pending
        if pending is not None and pending.parts:
            text = pending.text().strip()
            if text and text not in seen_text:
                seen_text.add(text)
                results.append(
                    {"page": pending.page, "sheet": pending.sheet, "section": pending.section, "text": text}
                )
        pending = None

    for block in blocks:
        if block.type == BlockType.TABLE:
            flush()
            text = _table_to_text(block).strip()
            if text and text not in seen_text:
                seen_text.add(text)
                results.append({"page": block.page, "sheet": block.sheet, "section": block.section, "text": text})
            continue

        if block.type == BlockType.HEADING:
            flush()
            current_section = block.text
            pending = PendingChunk(block.page, block.sheet, current_section)
            pending.parts.append(block.text)
            continue

        text = block.text.strip()
        if not text:
            continue

        if pending is None or pending.section != (block.section or current_section):
            flush()
            pending = PendingChunk(block.page, block.sheet, block.section or current_section)

        if pending.char_count() + len(text) > max_chars and pending.parts:
            flush()
            pending = PendingChunk(block.page, block.sheet, block.section or current_section)

        pending.parts.append(text)

    flush()
    return results
