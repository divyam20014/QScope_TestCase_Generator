from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class BlockType(str, Enum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    LIST_ITEM = "list_item"


class ExtractedBlock(BaseModel):
    """A single piece of extracted content with its source location.

    `page` is a 1-based page number (PDF/PPTX slide), `sheet` is an Excel
    sheet name, and `section` is the nearest preceding heading text — these
    are what every downstream requirement/test case traces back to.
    """

    block_id: str
    type: BlockType
    text: str
    level: int | None = None  # heading level, 1 = top
    page: int | None = None
    sheet: str | None = None
    section: str | None = None
    table_data: list[list[str]] | None = None


class ExtractionWarning(BaseModel):
    message: str
    page: int | None = None
    sheet: str | None = None


class ExtractionResult(BaseModel):
    blocks: list[ExtractedBlock] = Field(default_factory=list)
    warnings: list[ExtractionWarning] = Field(default_factory=list)
    page_count: int | None = None
    requires_ocr: bool = False
