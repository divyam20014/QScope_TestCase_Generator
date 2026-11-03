from __future__ import annotations

from app.parsers.models import BlockType, ExtractedBlock
from app.rag.chunking import chunk_blocks


def _block(**kwargs) -> ExtractedBlock:
    defaults = {"block_id": "b1", "type": BlockType.PARAGRAPH, "text": ""}
    defaults.update(kwargs)
    return ExtractedBlock(**defaults)


def test_table_blocks_become_their_own_chunk():
    blocks = [
        _block(type=BlockType.HEADING, text="Rules", level=1),
        _block(type=BlockType.TABLE, text="Table (1 rows)", table_data=[["A", "B"], ["1", "2"]]),
    ]
    chunks = chunk_blocks(blocks)
    table_chunks = [c for c in chunks if "A | B" in c["text"]]
    assert len(table_chunks) == 1
    assert "1 | 2" in table_chunks[0]["text"]


def test_paragraphs_accumulate_under_same_section():
    blocks = [
        _block(type=BlockType.HEADING, text="Login", level=1, section="Login"),
        _block(type=BlockType.PARAGRAPH, text="Users must enter a valid email.", section="Login"),
        _block(type=BlockType.PARAGRAPH, text="Passwords must be 8+ characters.", section="Login"),
    ]
    chunks = chunk_blocks(blocks)
    combined = [c for c in chunks if "valid email" in c["text"] and "8+ characters" in c["text"]]
    assert len(combined) == 1
    assert combined[0]["section"] == "Login"


def test_chunk_splits_on_max_chars():
    long_text_1 = "A" * 500
    long_text_2 = "B" * 500
    blocks = [
        _block(type=BlockType.PARAGRAPH, text=long_text_1, section="S"),
        _block(type=BlockType.PARAGRAPH, text=long_text_2, section="S"),
    ]
    chunks = chunk_blocks(blocks, max_chars=800)
    assert len(chunks) == 2


def test_section_change_starts_new_chunk():
    blocks = [
        _block(type=BlockType.HEADING, text="A", level=1),
        _block(type=BlockType.PARAGRAPH, text="text under A"),
        _block(type=BlockType.HEADING, text="B", level=1),
        _block(type=BlockType.PARAGRAPH, text="text under B"),
    ]
    chunks = chunk_blocks(blocks)
    sections = {c["section"] for c in chunks}
    assert "A" in sections and "B" in sections


def test_exact_duplicate_text_is_deduplicated():
    blocks = [
        _block(type=BlockType.PARAGRAPH, text="Repeated boilerplate header"),
        _block(type=BlockType.HEADING, text="Section 2", level=1),
        _block(type=BlockType.PARAGRAPH, text="Repeated boilerplate header"),
    ]
    chunks = chunk_blocks(blocks)
    texts = [c["text"] for c in chunks]
    assert texts.count("Repeated boilerplate header") == 1


def test_empty_blocks_produce_no_chunks():
    assert chunk_blocks([]) == []
    assert chunk_blocks([_block(type=BlockType.PARAGRAPH, text="   ")]) == []
