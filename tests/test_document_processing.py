import pytest

from app.document_processing.chunk import chunk_document
from app.document_processing.extract import extract_document, validate_upload


def test_rejects_unsupported_and_invalid_files():
    with pytest.raises(ValueError):
        validate_upload("contract.txt", b"text")
    with pytest.raises(ValueError):
        validate_upload("contract.pdf", b"not a pdf")


def test_extracts_docx_and_chunks_with_page_metadata():
    from docx import Document
    import io
    doc = Document()
    doc.add_paragraph("Section 1 Payment")
    doc.add_paragraph("Customer shall pay fees within thirty days.")
    buf = io.BytesIO()
    doc.save(buf)
    extracted = extract_document("contract.docx", buf.getvalue())
    chunks = chunk_document("doc-1", extracted, max_chars=32)
    assert chunks
    assert all(chunk.document_id == "doc-1" and chunk.page == 1 for chunk in chunks)


def test_empty_document_text_fails_validation():
    with pytest.raises(ValueError):
        extract_document("empty.docx", b"PKinvalid")
