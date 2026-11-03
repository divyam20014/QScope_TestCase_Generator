from __future__ import annotations

import csv

from app.parsers.base import BlockIdFactory, DocumentParser, ParseError
from app.parsers.models import BlockType, ExtractedBlock, ExtractionResult, ExtractionWarning


def _read_text(file_path: str) -> str:
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            with open(file_path, encoding=encoding) as f:
                return f.read()
        except (UnicodeDecodeError, LookupError):
            continue
    raise ParseError("Could not decode file with any supported text encoding")


class PlainTextParser(DocumentParser):
    def parse(self, file_path: str) -> ExtractionResult:
        try:
            content = _read_text(file_path)
        except OSError as exc:
            raise ParseError(f"Could not read file: {exc}") from exc

        ids = BlockIdFactory()
        blocks: list[ExtractedBlock] = []
        for line in content.splitlines():
            text = line.strip()
            if text:
                blocks.append(ExtractedBlock(block_id=ids.next(), type=BlockType.PARAGRAPH, text=text))

        warnings = []
        if not blocks:
            warnings.append(ExtractionWarning(message="File is empty"))

        return ExtractionResult(blocks=blocks, warnings=warnings)


class MarkdownParser(DocumentParser):
    def parse(self, file_path: str) -> ExtractionResult:
        try:
            content = _read_text(file_path)
        except OSError as exc:
            raise ParseError(f"Could not read file: {exc}") from exc

        ids = BlockIdFactory()
        blocks: list[ExtractedBlock] = []
        current_section: str | None = None

        for line in content.splitlines():
            text = line.strip()
            if not text:
                continue
            if text.startswith("#"):
                level = len(text) - len(text.lstrip("#"))
                heading_text = text.lstrip("#").strip()
                if heading_text:
                    current_section = heading_text
                    blocks.append(
                        ExtractedBlock(
                            block_id=ids.next(),
                            type=BlockType.HEADING,
                            text=heading_text,
                            level=min(level, 6),
                            section=current_section,
                        )
                    )
                    continue
            if text.startswith(("-", "*", "+")) or (len(text) > 1 and text[0].isdigit() and text[1] in ".)"):
                blocks.append(
                    ExtractedBlock(
                        block_id=ids.next(),
                        type=BlockType.LIST_ITEM,
                        text=text.lstrip("-*+ ").strip(),
                        section=current_section,
                    )
                )
                continue
            blocks.append(
                ExtractedBlock(
                    block_id=ids.next(), type=BlockType.PARAGRAPH, text=text, section=current_section
                )
            )

        warnings = []
        if not blocks:
            warnings.append(ExtractionWarning(message="File is empty"))

        return ExtractionResult(blocks=blocks, warnings=warnings)


class CsvParser(DocumentParser):
    def parse(self, file_path: str) -> ExtractionResult:
        try:
            content = _read_text(file_path)
        except OSError as exc:
            raise ParseError(f"Could not read file: {exc}") from exc

        try:
            dialect = csv.Sniffer().sniff(content[:4096]) if content.strip() else csv.excel
        except csv.Error:
            dialect = csv.excel

        ids = BlockIdFactory()
        warnings: list[ExtractionWarning] = []
        try:
            reader = csv.reader(content.splitlines(), dialect)
            rows = [row for row in reader if any(cell.strip() for cell in row)]
        except csv.Error as exc:
            raise ParseError(f"Could not parse CSV: {exc}") from exc

        blocks: list[ExtractedBlock] = []
        if rows:
            blocks.append(
                ExtractedBlock(
                    block_id=ids.next(),
                    type=BlockType.TABLE,
                    text=f"Table ({len(rows)} rows)",
                    table_data=rows,
                )
            )
        else:
            warnings.append(ExtractionWarning(message="CSV file is empty"))

        return ExtractionResult(blocks=blocks, warnings=warnings)
