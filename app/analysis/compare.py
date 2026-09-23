from difflib import SequenceMatcher
import re

from app.document_processing.models import Chunk


def compare_chunks(old: list[Chunk], new: list[Chunk]) -> list[dict]:
    def lines(chunks: list[Chunk]) -> list[Chunk]:
        return [c for c in chunks if c.text.strip()]
    left, right = lines(old), lines(new)
    used: set[int] = set()
    changes: list[dict] = []
    for before in left:
        best_i, score = max(((i, SequenceMatcher(None, _norm(before.text), _norm(after.text)).ratio()) for i, after in enumerate(right) if i not in used), default=(-1, 0))
        if score < 0.28:
            changes.append(_change("Removed clause", before, None, "Content in Document A has no close match in Document B."))
        elif score < 0.9999:
            after = right[best_i]
            used.add(best_i)
            changes.append(_change(_category(before.text + " " + after.text), before, after, "Text differs between the documents."))
        else:
            used.add(best_i)
    for i, after in enumerate(right):
        if i not in used:
            changes.append(_change("Added clause", None, after, "Content appears in Document B without a close match in Document A."))
    return changes


def _norm(text: str) -> str:
    return re.sub(r"\W+", " ", text.lower()).strip()


def _category(text: str) -> str:
    for label, pattern in [("Payment", r"payment|fee|price"), ("Termination", r"terminat|cancel"), ("Dates", r"date|effective|\d{1,2}[/-]\d"), ("Liability", r"liabilit|damages"), ("Obligations", r"shall|must|will"), ("Renewal", r"renew")]:
        if re.search(pattern, text, re.I):
            return label
    return "Clause"


def _change(category: str, old: Chunk | None, new: Chunk | None, message: str) -> dict:
    def cite(chunk: Chunk) -> dict:
        return {"document": chunk.document, "page": chunk.page, "section": chunk.section, "clause": chunk.clause, "text": chunk.text[:1200]}
    return {"category": category, "old": old.text[:1200] if old else None, "new": new.text[:1200] if new else None,
            "change": message, "source": [cite(c) for c in (old, new) if c]}
