from __future__ import annotations

from pptx import Presentation

from app.parsers.base import BlockIdFactory, DocumentParser, ParseError
from app.parsers.models import BlockType, ExtractedBlock, ExtractionResult, ExtractionWarning


class PptxParser(DocumentParser):
    def parse(self, file_path: str) -> ExtractionResult:
        try:
            presentation = Presentation(file_path)
        except Exception as exc:
            raise ParseError(f"Could not open PPTX: {exc}") from exc

        ids = BlockIdFactory()
        blocks: list[ExtractedBlock] = []
        warnings: list[ExtractionWarning] = []

        for slide_index, slide in enumerate(presentation.slides, start=1):
            current_section: str | None = None
            slide_had_text = False

            title_text = None
            if slide.shapes.title and slide.shapes.title.text.strip():
                title_text = slide.shapes.title.text.strip()

            if title_text:
                current_section = title_text
                slide_had_text = True
                blocks.append(
                    ExtractedBlock(
                        block_id=ids.next(),
                        type=BlockType.HEADING,
                        text=title_text,
                        level=1,
                        page=slide_index,
                        section=current_section,
                    )
                )

            for shape in slide.shapes:
                if shape == slide.shapes.title:
                    continue
                if shape.has_table:
                    table = shape.table
                    rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
                    if any(any(cell for cell in row) for row in rows):
                        slide_had_text = True
                        blocks.append(
                            ExtractedBlock(
                                block_id=ids.next(),
                                type=BlockType.TABLE,
                                text=f"Table ({len(rows)} rows)",
                                page=slide_index,
                                section=current_section,
                                table_data=rows,
                            )
                        )
                elif shape.has_text_frame:
                    for paragraph in shape.text_frame.paragraphs:
                        text = "".join(run.text for run in paragraph.runs).strip()
                        if not text:
                            continue
                        slide_had_text = True
                        blocks.append(
                            ExtractedBlock(
                                block_id=ids.next(),
                                type=BlockType.PARAGRAPH,
                                text=text,
                                page=slide_index,
                                section=current_section,
                            )
                        )

            if not slide_had_text:
                warnings.append(
                    ExtractionWarning(message="Slide has no extractable text", page=slide_index)
                )

        if not blocks:
            warnings.append(ExtractionWarning(message="No extractable text found in this presentation"))

        return ExtractionResult(blocks=blocks, warnings=warnings, page_count=len(presentation.slides))
