from pathlib import Path
import re
import io
import zipfile

import pymupdf as fitz
from docx import Document

from app.config import get_settings
from app.document_processing.models import DocumentText, PageText

SUPPORTED = {".pdf", ".docx"}


def validate_upload(name: str, content: bytes) -> None:
    suffix = Path(name).suffix.lower()
    if suffix not in SUPPORTED:
        raise ValueError("Only PDF and DOCX files are supported.")
    if not content:
        raise ValueError("The uploaded document is empty.")
    if suffix == ".pdf" and not content.startswith(b"%PDF"):
        raise ValueError("The file does not appear to be a valid PDF.")
    if suffix == ".docx" and not content.startswith(b"PK"):
        raise ValueError("The file does not appear to be a valid DOCX file.")
    if suffix == ".docx" and not zipfile.is_zipfile(io.BytesIO(content)):
        raise ValueError("The file does not appear to be a valid DOCX file.")


def _ocr_page(page: fitz.Page) -> str:
    settings = get_settings()
    try:
        import pytesseract
        from PIL import Image
        import io
    except ImportError as exc:
        raise RuntimeError("OCR is enabled, but pytesseract and Pillow are not installed.") from exc
    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
    return pytesseract.image_to_string(Image.open(io.BytesIO(pix.tobytes("png"))))


def extract_document(name: str, content: bytes) -> DocumentText:
    validate_upload(name, content)
    suffix = Path(name).suffix.lower()
    if suffix == ".pdf":
        pages: list[PageText] = []
        try:
            with fitz.open(stream=content, filetype="pdf") as pdf:
                for number, page in enumerate(pdf, start=1):
                    text = page.get_text("text").strip()
                    if len(text) < 30 and get_settings().ocr_enabled:
                        text = _ocr_page(page).strip()
                    pages.append(PageText(number, text))
                metadata = {str(k): str(v) for k, v in (pdf.metadata or {}).items() if v}
        except Exception as exc:
            raise ValueError("The PDF could not be read. Check that it is valid and not encrypted.") from exc
        if not any(page.text for page in pages):
            raise ValueError("No text could be extracted. Enable OCR for scanned PDFs and install Tesseract.")
        return DocumentText(name, pages, metadata)

    try:
        doc = Document(io.BytesIO(content))
    except Exception as exc:
        raise ValueError("The DOCX document could not be opened or is damaged.") from exc
    # DOCX has no stable page geometry; paragraph index is retained as the source locator.
    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    if not text.strip():
        raise ValueError("No text could be extracted from this DOCX document.")
    return DocumentText(name, [PageText(1, text)], {"title": doc.core_properties.title or ""})


def clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[\t\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return re.sub(r" {2,}", " ", text).strip()
