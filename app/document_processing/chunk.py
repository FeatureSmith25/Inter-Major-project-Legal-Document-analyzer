import re
from uuid import uuid4

from app.document_processing.models import Chunk, DocumentText

CLAUSE_RE = re.compile(r"(?im)^\s*((?:section\s+)?\d+(?:\.\d+)*[.)]?)\s+(.{3,100})$")


def chunk_document(document_id: str, document: DocumentText, max_chars: int = 1200) -> list[Chunk]:
    chunks: list[Chunk] = []
    for page in document.pages:
        paragraphs = [p.strip() for p in page.text.splitlines() if p.strip()]
        current: list[str] = []
        section = clause = None
        size = 0
        for paragraph in paragraphs:
            match = CLAUSE_RE.match(paragraph)
            if match:
                section, clause = match.group(2).strip(), match.group(1).strip()
            if current and size + len(paragraph) + 1 > max_chars:
                chunks.append(Chunk(document_id, document.name, page.page, section, clause, "\n".join(current)))
                current, size = [], 0
            current.append(paragraph)
            size += len(paragraph) + 1
        if current:
            chunks.append(Chunk(document_id, document.name, page.page, section, clause, "\n".join(current)))
    return chunks or [Chunk(document_id, document.name, 1, None, None, "")]
