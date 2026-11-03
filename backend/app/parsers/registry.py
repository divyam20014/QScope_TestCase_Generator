from __future__ import annotations

from app.parsers.base import DocumentParser
from app.parsers.docx_parser import DocxParser
from app.parsers.pdf_parser import PdfParser
from app.parsers.pptx_parser import PptxParser
from app.parsers.text_parser import CsvParser, MarkdownParser, PlainTextParser
from app.parsers.xlsx_parser import XlsxParser

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".pptx", ".txt", ".csv", ".md"}

_PARSERS: dict[str, DocumentParser] = {
    ".pdf": PdfParser(),
    ".docx": DocxParser(),
    ".xlsx": XlsxParser(),
    ".pptx": PptxParser(),
    ".txt": PlainTextParser(),
    ".md": MarkdownParser(),
    ".csv": CsvParser(),
}


def get_parser(extension: str) -> DocumentParser | None:
    return _PARSERS.get(extension.lower())
