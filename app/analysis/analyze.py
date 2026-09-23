import re
from collections import defaultdict

from app.document_processing.models import Chunk

CLAUSES = {
    "Payment": r"payment|\bpay\b|invoice|fee|price|compensation",
    "Termination": r"terminat|end this agreement|cancel",
    "Renewal": r"renew|automatic renewal|evergreen",
    "Confidentiality": r"confidential|non-disclosure",
    "Liability": r"liabilit|limitation of damages|consequential damages",
    "Indemnification": r"indemnif|hold harmless",
    "Intellectual Property": r"intellectual property|work product|ownership of (?:all )?right",
    "Dispute Resolution": r"arbitrat|dispute resolution|mediat",
    "Governing Law": r"governed by|governing law|laws of the state",
    "Force Majeure": r"force majeure|acts of god|beyond (?:its|their) reasonable control",
    "Data Protection": r"personal data|data protection|privacy|security incident",
}
DATE_RE = re.compile(r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+\d{4})\b", re.I)


def analyze_chunks(chunks: list[Chunk]) -> dict:
    clauses: dict[str, list[dict]] = defaultdict(list)
    dates, attention, obligations, key_terms = [], [], [], []
    seen_dates: set[tuple[str, int]] = set()
    parties: list[str] = []
    party_evidence: dict | None = None
    summary_sentences: list[str] = []
    summary_sources: list[dict] = []
    seen_obligations: set[str] = set()
    seen_terms: set[str] = set()
    for chunk in chunks:
        text = chunk.text
        if len(summary_sentences) < 3:
            additions = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()][:3 - len(summary_sentences)]
            if additions:
                summary_sentences.extend(additions)
                summary_sources.append(_evidence(chunk))
        if not parties:
            party_match = re.search(r"\bbetween\s+(.{2,100}?)\s+and\s+(.{2,100}?)(?:,|\.|\s+(?:dated|effective|whose))", text, re.I)
            if party_match:
                parties = [party_match.group(1).strip(" ,;"), party_match.group(2).strip(" ,;")]
                party_evidence = _evidence(chunk)
        for kind, pattern in CLAUSES.items():
            if re.search(pattern, text, re.I):
                clauses[kind].append(_evidence(chunk))
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            normalized = sentence.strip()
            key = normalized.casefold()
            if re.search(r"\b(?:shall|must|required to|agrees to|will)\b", normalized, re.I) and key not in seen_obligations:
                obligations.append({"text": normalized[:500], **_evidence(chunk)})
                seen_obligations.add(key)
        for match in re.finditer(r"[\"“]([^\"”]{2,60})[\"”]\s*(?:means|refers to|,?\s+hereinafter)", text, re.I):
            term = match.group(1).strip()
            if term.casefold() not in seen_terms:
                key_terms.append({"term": term, **_evidence(chunk)})
                seen_terms.add(term.casefold())
        for match in DATE_RE.finditer(text):
            key = (match.group(), chunk.page)
            if key not in seen_dates:
                dates.append({"date": match.group(), **_evidence(chunk)})
                seen_dates.add(key)
        checks = [
            (r"automatically renew|automatic renewal|renewal term", "Automatic renewal language appears in the document."),
            (r"penalt(?:y|ies)|liquidated damages", "Penalty or liquidated damages language appears in the document."),
            (r"sole discretion|unlimited liability|any and all damages", "Broad or potentially open-ended language appears in the document."),
            (r"within \d+ days(?:'|’)? notice|\d+ days(?:'|’)? prior notice", "A notice period is specified and may merit review in context."),
            (r"\b(?:[A-Z][a-z]+\s+\d{1,2},?\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b", "A date appears; check consistency with other dates and effective terms."),
        ]
        for pattern, message in checks:
            if re.search(pattern, text, re.I):
                attention.append({"label": "Review Recommended", "finding": message, **_evidence(chunk)})
    if len(dates) > 1:
        attention.append({"label": "Review Recommended", "finding": "Multiple distinct dates appear in the document; check that they are consistent with the relevant terms.", **{k: dates[0][k] for k in ("document", "page", "section", "clause", "text")}})
    full_text = " ".join(chunk.text for chunk in chunks[:4]).lower()
    doc_type = "Non-disclosure agreement" if re.search(r"non.?disclosure|confidentiality agreement", full_text) else "Service agreement" if re.search(r"services agreement|service agreement", full_text) else "Employment agreement" if "employment agreement" in full_text else "Agreement" if "agreement" in full_text else "Document"
    return {
        "summary": " ".join(summary_sentences),
        "summary_sources": summary_sources,
        "document_type_purpose": f"This document appears to be a {doc_type.lower()}, based on its text. Confirm the document purpose from the full context.",
        "parties": parties, "party_evidence": party_evidence, "important_dates": dates, "obligations": obligations, "key_terms": key_terms,
        "clauses": dict(clauses), "attention_areas": attention,
        "notice": "Automated document assistance only; findings are not legal advice.",
    }


def _evidence(chunk: Chunk) -> dict:
    return {"document": chunk.document, "page": chunk.page, "section": chunk.section, "clause": chunk.clause, "text": chunk.text[:1200]}
