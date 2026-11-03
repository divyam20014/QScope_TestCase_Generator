from __future__ import annotations

from app.parsers.models import ExtractionResult


class ParseError(Exception):
    """Raised when a document cannot be parsed at all (corrupt/unreadable)."""


class BlockIdFactory:
    def __init__(self) -> None:
        self._counter = 0

    def next(self) -> str:
        self._counter += 1
        return f"b{self._counter}"


class DocumentParser:
    """Base interface every format-specific parser implements."""

    def parse(self, file_path: str) -> ExtractionResult:
        raise NotImplementedError
