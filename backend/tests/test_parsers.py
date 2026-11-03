from __future__ import annotations

import fitz
import openpyxl
import pytest
from docx import Document as DocxDocument
from pptx import Presentation

from app.parsers.base import ParseError
from app.parsers.docx_parser import DocxParser
from app.parsers.models import BlockType
from app.parsers.pdf_parser import PdfParser
from app.parsers.pptx_parser import PptxParser
from app.parsers.registry import get_parser
from app.parsers.text_parser import CsvParser, MarkdownParser, PlainTextParser
from app.parsers.xlsx_parser import XlsxParser


def test_registry_resolves_all_supported_extensions():
    for ext in [".pdf", ".docx", ".xlsx", ".pptx", ".txt", ".csv", ".md"]:
        assert get_parser(ext) is not None
    assert get_parser(".exe") is None


def test_pdf_parser_extracts_heading_and_paragraph(tmp_path):
    path = tmp_path / "sample.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Requirement Specification", fontsize=24)
    page.insert_text((72, 120), "The system shall allow user login.", fontsize=11)
    doc.save(str(path))
    doc.close()

    result = PdfParser().parse(str(path))
    assert result.page_count == 1
    texts = [b.text for b in result.blocks]
    assert "Requirement Specification" in texts
    assert any("shall allow user login" in t for t in texts)
    heading = next(b for b in result.blocks if b.text == "Requirement Specification")
    assert heading.type == BlockType.HEADING
    assert heading.page == 1


def test_pdf_parser_flags_scanned_page_for_ocr(tmp_path):
    path = tmp_path / "scanned.pdf"
    doc = fitz.open()
    page = doc.new_page()
    # A blank image with no text layer simulates a scanned page.
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 100, 100))
    pix.set_rect(pix.irect, (255, 255, 255))
    page.insert_image(fitz.Rect(0, 0, 200, 200), pixmap=pix)
    doc.save(str(path))
    doc.close()

    result = PdfParser().parse(str(path))
    assert result.requires_ocr is True
    assert any("OCR is required" in w.message for w in result.warnings)


def test_pdf_parser_raises_parse_error_on_corrupt_file(tmp_path):
    path = tmp_path / "corrupt.pdf"
    path.write_bytes(b"not a real pdf")
    with pytest.raises(ParseError):
        PdfParser().parse(str(path))


def test_docx_parser_extracts_heading_table_and_paragraph(tmp_path):
    path = tmp_path / "sample.docx"
    doc = DocxDocument()
    doc.add_heading("Functional Requirements", level=1)
    doc.add_paragraph("FR-1: The system shall validate email format.")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Field"
    table.cell(0, 1).text = "Rule"
    table.cell(1, 0).text = "Email"
    table.cell(1, 1).text = "Must be valid format"
    doc.save(str(path))

    result = DocxParser().parse(str(path))
    types = [b.type for b in result.blocks]
    assert BlockType.HEADING in types
    assert BlockType.PARAGRAPH in types
    assert BlockType.TABLE in types
    table_block = next(b for b in result.blocks if b.type == BlockType.TABLE)
    assert table_block.table_data[0] == ["Field", "Rule"]
    assert table_block.section == "Functional Requirements"


def test_docx_parser_raises_on_corrupt_file(tmp_path):
    path = tmp_path / "corrupt.docx"
    path.write_bytes(b"not a docx")
    with pytest.raises(ParseError):
        DocxParser().parse(str(path))


def test_xlsx_parser_extracts_sheet_and_rows(tmp_path):
    path = tmp_path / "sample.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Requirements"
    ws.append(["ID", "Description"])
    ws.append(["REQ-1", "User can reset password"])
    wb.save(str(path))

    result = XlsxParser().parse(str(path))
    table_block = next(b for b in result.blocks if b.type == BlockType.TABLE)
    assert table_block.sheet == "Requirements"
    assert table_block.table_data[0] == ["ID", "Description"]
    assert table_block.table_data[1] == ["REQ-1", "User can reset password"]


def test_xlsx_parser_warns_on_empty_sheet(tmp_path):
    path = tmp_path / "empty.xlsx"
    wb = openpyxl.Workbook()
    wb.active.title = "Empty"
    wb.save(str(path))

    result = XlsxParser().parse(str(path))
    assert any("empty" in w.message.lower() for w in result.warnings)


def test_pptx_parser_extracts_title_and_body(tmp_path):
    path = tmp_path / "sample.pptx"
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = "Business Rules"
    body = slide.placeholders[1]
    body.text_frame.text = "Approval requires manager sign-off."
    prs.save(str(path))

    result = PptxParser().parse(str(path))
    texts = [b.text for b in result.blocks]
    assert "Business Rules" in texts
    assert any("manager sign-off" in t for t in texts)
    assert result.page_count == 1


def test_plain_text_parser(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("Line one\n\nLine two\n", encoding="utf-8")
    result = PlainTextParser().parse(str(path))
    assert [b.text for b in result.blocks] == ["Line one", "Line two"]


def test_markdown_parser_headings_and_lists(tmp_path):
    path = tmp_path / "spec.md"
    path.write_text("# Title\n\n## Section A\n- item one\n- item two\n\nParagraph text.\n", encoding="utf-8")
    result = MarkdownParser().parse(str(path))
    heading = next(b for b in result.blocks if b.text == "Title")
    assert heading.level == 1
    section = next(b for b in result.blocks if b.text == "Section A")
    assert section.level == 2
    list_items = [b for b in result.blocks if b.type == BlockType.LIST_ITEM]
    assert len(list_items) == 2
    assert list_items[0].section == "Section A"


def test_csv_parser_extracts_table(tmp_path):
    path = tmp_path / "data.csv"
    path.write_text("ID,Name\n1,Alpha\n2,Beta\n", encoding="utf-8")
    result = CsvParser().parse(str(path))
    table_block = result.blocks[0]
    assert table_block.table_data[0] == ["ID", "Name"]
    assert len(table_block.table_data) == 3


def test_csv_parser_warns_on_empty_file(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("", encoding="utf-8")
    result = CsvParser().parse(str(path))
    assert result.blocks == []
    assert any("empty" in w.message.lower() for w in result.warnings)
