from __future__ import annotations

import openpyxl

from app.parsers.base import BlockIdFactory, DocumentParser, ParseError
from app.parsers.models import BlockType, ExtractedBlock, ExtractionResult, ExtractionWarning


class XlsxParser(DocumentParser):
    def parse(self, file_path: str) -> ExtractionResult:
        try:
            workbook = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
        except Exception as exc:
            raise ParseError(f"Could not open XLSX: {exc}") from exc

        ids = BlockIdFactory()
        blocks: list[ExtractedBlock] = []
        warnings: list[ExtractionWarning] = []

        for sheet_name in workbook.sheetnames:
            sheet = workbook[sheet_name]
            rows: list[list[str]] = []
            try:
                for row in sheet.iter_rows(values_only=True):
                    if row is None or all(cell is None for cell in row):
                        continue
                    rows.append(["" if cell is None else str(cell) for cell in row])
            except Exception:  # noqa: BLE001
                warnings.append(ExtractionWarning(message="Failed to read sheet contents", sheet=sheet_name))
                continue

            if not rows:
                warnings.append(ExtractionWarning(message="Sheet is empty", sheet=sheet_name))
                continue

            blocks.append(
                ExtractedBlock(
                    block_id=ids.next(),
                    type=BlockType.HEADING,
                    text=sheet_name,
                    level=1,
                    sheet=sheet_name,
                    section=sheet_name,
                )
            )
            blocks.append(
                ExtractedBlock(
                    block_id=ids.next(),
                    type=BlockType.TABLE,
                    text=f"Table ({len(rows)} rows)",
                    sheet=sheet_name,
                    section=sheet_name,
                    table_data=rows,
                )
            )

        workbook.close()

        if not blocks:
            warnings.append(ExtractionWarning(message="No data found in this workbook"))

        return ExtractionResult(blocks=blocks, warnings=warnings)
