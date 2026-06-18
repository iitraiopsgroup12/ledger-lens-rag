from abc import ABC, abstractmethod
import csv
import io
from pathlib import Path

from app.exceptions import EmptyFileError, FileParseError, UnsupportedFileTypeError


class BaseParser(ABC):
    @abstractmethod
    def parse(self, data: bytes, filename: str) -> str: ...


class TextParser(BaseParser):
    def parse(self, data: bytes, filename: str) -> str:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("latin-1")
        result = text.strip()
        if not result:
            raise EmptyFileError(filename)
        return result


class PDFParser(BaseParser):
    def parse(self, data: bytes, filename: str) -> str:
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(data))
            pages = []
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    pages.append(extracted)
            result = "\n\n".join(pages).strip()
        except Exception as exc:
            raise FileParseError(filename, str(exc)) from exc
        if not result:
            raise EmptyFileError(filename)
        return result


class DocxParser(BaseParser):
    def parse(self, data: bytes, filename: str) -> str:
        try:
            from docx import Document

            doc = Document(io.BytesIO(data))
            parts: list[str] = []
            for para in doc.paragraphs:
                if para.text.strip():
                    parts.append(para.text)
            for table in doc.tables:
                for row in table.rows:
                    row_text = "\t".join(cell.text.strip() for cell in row.cells)
                    if row_text.strip():
                        parts.append(row_text)
            result = "\n".join(parts).strip()
        except Exception as exc:
            raise FileParseError(filename, str(exc)) from exc
        if not result:
            raise EmptyFileError(filename)
        return result


class ExcelParser(BaseParser):
    def parse(self, data: bytes, filename: str) -> str:
        ext = Path(filename).suffix.lower()
        try:
            if ext == ".xlsx":
                result = self._parse_xlsx(data)
            else:
                result = self._parse_xls(data)
        except (EmptyFileError, FileParseError):
            raise
        except Exception as exc:
            raise FileParseError(filename, str(exc)) from exc
        if not result.strip():
            raise EmptyFileError(filename)
        return result

    def _parse_xlsx(self, data: bytes) -> str:
        import openpyxl

        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        sections: list[str] = []
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows: list[str] = []
            for row in ws.iter_rows(values_only=True):
                cells = [str(c) if c is not None else "" for c in row]
                if any(c.strip() for c in cells):
                    rows.append("\t".join(cells))
            if rows:
                sections.append(f"## Sheet: {sheet_name}\n" + "\n".join(rows))
        return "\n\n".join(sections)

    def _parse_xls(self, data: bytes) -> str:
        import xlrd

        wb = xlrd.open_workbook(file_contents=data)
        sections: list[str] = []
        for sheet in wb.sheets():
            rows: list[str] = []
            for rx in range(sheet.nrows):
                cells = [str(sheet.cell_value(rx, cx)) for cx in range(sheet.ncols)]
                if any(c.strip() for c in cells):
                    rows.append("\t".join(cells))
            if rows:
                sections.append(f"## Sheet: {sheet.name}\n" + "\n".join(rows))
        return "\n\n".join(sections)


class CsvParser(BaseParser):
    def parse(self, data: bytes, filename: str) -> str:
        try:
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                text = data.decode("latin-1")
            reader = csv.reader(io.StringIO(text))
            rows = ["\t".join(row) for row in reader if any(cell.strip() for cell in row)]
            result = "\n".join(rows).strip()
        except Exception as exc:
            raise FileParseError(filename, str(exc)) from exc
        if not result:
            raise EmptyFileError(filename)
        return result


class XmlParser(BaseParser):
    def parse(self, data: bytes, filename: str) -> str:
        try:
            import xml.etree.ElementTree as ET

            root = ET.fromstring(data)
            lines: list[str] = []

            def _walk(element) -> None:
                text = (element.text or "").strip()
                if text:
                    lines.append(f"{element.tag}: {text}")
                for child in element:
                    _walk(child)

            _walk(root)
            result = "\n".join(lines).strip()
        except Exception as exc:
            raise FileParseError(filename, str(exc)) from exc
        if not result:
            raise EmptyFileError(filename)
        return result


_REGISTRY: dict[str, BaseParser] = {
    ".pdf": PDFParser(),
    ".docx": DocxParser(),
    ".xlsx": ExcelParser(),
    ".xls": ExcelParser(),
    ".txt": TextParser(),
    ".csv": CsvParser(),
    ".md": TextParser(),
    ".xml": XmlParser(),
}


def get_parser(filename: str) -> BaseParser:
    ext = Path(filename).suffix.lower()
    if ext not in _REGISTRY:
        raise UnsupportedFileTypeError(ext)
    return _REGISTRY[ext]


def supported_extensions() -> list[str]:
    return list(_REGISTRY.keys())
