from __future__ import annotations

import fitz  # PyMuPDF

from app.parsers.base import BlockIdFactory, DocumentParser, ParseError
from app.parsers.models import BlockType, ExtractedBlock, ExtractionResult, ExtractionWarning

MIN_CHARS_FOR_TEXT_PAGE = 10


class PdfParser(DocumentParser):
    def parse(self, file_path: str) -> ExtractionResult:
        try:
            doc = fitz.open(file_path)
        except Exception as exc:  # pragma: no cover - fitz raises various internal errors
            raise ParseError(f"Could not open PDF: {exc}") from exc

        ids = BlockIdFactory()
        blocks: list[ExtractedBlock] = []
        warnings: list[ExtractionWarning] = []
        current_section: str | None = None
        any_scanned_page = False

        try:
            body_size = self._estimate_body_font_size(doc)

            for page_index in range(doc.page_count):
                page = doc[page_index]
                page_number = page_index + 1
                page_dict = page.get_text("dict")
                page_text_len = len(page.get_text("text").strip())

                if page_text_len < MIN_CHARS_FOR_TEXT_PAGE:
                    images = page.get_images()
                    if images:
                        any_scanned_page = True
                        warnings.append(
                            ExtractionWarning(
                                message=(
                                    "Page appears to be a scanned image with no extractable "
                                    "text; OCR is required to analyse this page."
                                ),
                                page=page_number,
                            )
                        )
                        continue

                for block in page_dict.get("blocks", []):
                    if block.get("type") != 0:  # 0 = text block
                        continue
                    for line in block.get("lines", []):
                        line_text = "".join(span.get("text", "") for span in line.get("spans", []))
                        line_text = line_text.strip()
                        if not line_text:
                            continue
                        max_span_size = max(
                            (span.get("size", 0) for span in line.get("spans", [])), default=0
                        )
                        is_heading = body_size > 0 and max_span_size >= body_size * 1.15
                        if is_heading:
                            current_section = line_text
                            level = 1 if max_span_size >= body_size * 1.4 else 2
                            blocks.append(
                                ExtractedBlock(
                                    block_id=ids.next(),
                                    type=BlockType.HEADING,
                                    text=line_text,
                                    level=level,
                                    page=page_number,
                                    section=current_section,
                                )
                            )
                        else:
                            blocks.append(
                                ExtractedBlock(
                                    block_id=ids.next(),
                                    type=BlockType.PARAGRAPH,
                                    text=line_text,
                                    page=page_number,
                                    section=current_section,
                                )
                            )

                try:
                    tables = page.find_tables()
                    for table in tables.tables:
                        extracted = table.extract()
                        if extracted:
                            blocks.append(
                                ExtractedBlock(
                                    block_id=ids.next(),
                                    type=BlockType.TABLE,
                                    text=f"Table ({len(extracted)} rows)",
                                    page=page_number,
                                    section=current_section,
                                    table_data=[[str(cell) if cell is not None else "" for cell in row] for row in extracted],
                                )
                            )
                except Exception:  # noqa: BLE001 - table detection is best-effort
                    warnings.append(
                        ExtractionWarning(message="Table detection failed on this page", page=page_number)
                    )

            if not blocks and not any_scanned_page:
                warnings.append(ExtractionWarning(message="No extractable text found in this PDF"))

            return ExtractionResult(
                blocks=blocks,
                warnings=warnings,
                page_count=doc.page_count,
                requires_ocr=any_scanned_page,
            )
        finally:
            doc.close()

    @staticmethod
    def _estimate_body_font_size(doc: fitz.Document) -> float:
        """Body text size = the font size covering the most characters,
        since body paragraphs normally contain far more text than headings."""
        char_count_by_size: dict[float, int] = {}
        for page_index in range(min(doc.page_count, 5)):
            page_dict = doc[page_index].get_text("dict")
            for block in page_dict.get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "")
                        if text.strip():
                            size = span.get("size", 0)
                            char_count_by_size[size] = char_count_by_size.get(size, 0) + len(text)
        if not char_count_by_size:
            return 0.0
        return max(char_count_by_size, key=char_count_by_size.get)
