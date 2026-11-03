from __future__ import annotations

from docx import Document as DocxDocument
from docx.table import Table as DocxTable
from docx.text.paragraph import Paragraph as DocxParagraph

from app.parsers.base import BlockIdFactory, DocumentParser, ParseError
from app.parsers.models import BlockType, ExtractedBlock, ExtractionResult, ExtractionWarning


class DocxParser(DocumentParser):
    def parse(self, file_path: str) -> ExtractionResult:
        try:
            doc = DocxDocument(file_path)
        except Exception as exc:
            raise ParseError(f"Could not open DOCX: {exc}") from exc

        ids = BlockIdFactory()
        blocks: list[ExtractedBlock] = []
        warnings: list[ExtractionWarning] = []
        current_section: str | None = None

        for item in self._iter_block_items(doc):
            if isinstance(item, DocxParagraph):
                text = item.text.strip()
                if not text:
                    continue
                style_name = (item.style.name or "").lower() if item.style else ""
                if style_name.startswith("heading") or style_name == "title":
                    current_section = text
                    level = 1
                    digits = "".join(ch for ch in style_name if ch.isdigit())
                    if digits:
                        level = int(digits)
                    blocks.append(
                        ExtractedBlock(
                            block_id=ids.next(),
                            type=BlockType.HEADING,
                            text=text,
                            level=level,
                            section=current_section,
                        )
                    )
                elif style_name.startswith("list"):
                    blocks.append(
                        ExtractedBlock(
                            block_id=ids.next(),
                            type=BlockType.LIST_ITEM,
                            text=text,
                            section=current_section,
                        )
                    )
                else:
                    blocks.append(
                        ExtractedBlock(
                            block_id=ids.next(),
                            type=BlockType.PARAGRAPH,
                            text=text,
                            section=current_section,
                        )
                    )
            elif isinstance(item, DocxTable):
                try:
                    rows = [[cell.text.strip() for cell in row.cells] for row in item.rows]
                    if any(any(cell for cell in row) for row in rows):
                        blocks.append(
                            ExtractedBlock(
                                block_id=ids.next(),
                                type=BlockType.TABLE,
                                text=f"Table ({len(rows)} rows)",
                                section=current_section,
                                table_data=rows,
                            )
                        )
                except Exception:  # noqa: BLE001
                    warnings.append(ExtractionWarning(message="Failed to extract a table"))

        if not blocks:
            warnings.append(ExtractionWarning(message="No extractable text found in this document"))

        return ExtractionResult(blocks=blocks, warnings=warnings)

    @staticmethod
    def _iter_block_items(doc: DocxDocument):
        """Yield paragraphs and tables in the order they appear in the document body."""
        from docx.oxml.ns import qn

        parent_elm = doc.element.body
        for child in parent_elm.iterchildren():
            if child.tag == qn("w:p"):
                yield DocxParagraph(child, doc)
            elif child.tag == qn("w:tbl"):
                yield DocxTable(child, doc)
