import re
from pathlib import Path

import httpx

from app.config import get_settings
from app.document_processing.models import Chunk
from app.rag.retrieval import retrieve

NOT_FOUND = "I could not find sufficient information in the uploaded document."


def answer_question(question: str, chunks: list[Chunk], history: list[dict] | None = None) -> dict:
    history = (history or [])[-8:]
    # A short follow-up can depend on the user's earlier wording (for example, "what about renewal?").
    prior_user_text = " ".join(turn["content"] for turn in history if turn.get("role") == "user")
    retrieval_query = f"{prior_user_text} {question}".strip()
    hits = retrieve(retrieval_query, chunks)
    if not hits:
        return {"answer": NOT_FOUND, "citations": [], "grounded": False, "mode": "not_found", "notice": "No sufficiently relevant passage was found for this question."}
    citations = [{"document": c.document, "page": c.page, "section": c.section, "clause": c.clause, "text": c.text[:1200]} for c, _ in hits]
    settings = get_settings()
    if settings.llm_base_url and settings.llm_model:
        prompt = Path(__file__).parents[1].joinpath("prompts", "answer.txt").read_text(encoding="utf-8")
        evidence = "\n\n".join(f"[{c['document']} p.{c['page']} {c['section'] or ''} {c['clause'] or ''}]\n{c['text']}" for c in citations)
        try:
            messages = [{"role": "system", "content": prompt}]
            messages.extend({"role": turn["role"], "content": turn["content"]} for turn in history)
            messages.append({"role": "user", "content": f"Question: {question}\n\nEvidence for this answer (use only this evidence for factual claims):\n{evidence}"})
            response = httpx.post(
                _chat_completions_url(settings.llm_base_url),
                headers={"Authorization": f"Bearer {settings.llm_api_key}"} if settings.llm_api_key else {},
                json={"model": settings.llm_model, "temperature": 0.1, "max_tokens": 700, "stream": False, "messages": messages}, timeout=60,
            )
            response.raise_for_status()
            text = _response_text(response.json()).strip()
            text = re.sub(r"<(?:think|analysis)>.*?</(?:think|analysis)>", "", text, flags=re.I | re.S).strip()
            if text and NOT_FOUND.lower() not in text.lower():
                return {"answer": text, "citations": citations, "grounded": True, "mode": "llm", "notice": ""}
            if NOT_FOUND.lower() in text.lower():
                return {"answer": NOT_FOUND, "citations": citations, "grounded": False, "mode": "not_found", "notice": "The retrieved text did not support an answer."}
            raise ValueError("The model returned an empty response.")
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
            # Avoid presenting an API failure as a model-generated answer.
            return _evidence_fallback(hits, citations, "The model could not respond. Showing source passages instead.")
    return _evidence_fallback(hits, citations, "No chat model is configured. Showing source passages instead.")


def _evidence_fallback(hits: list[tuple[Chunk, float]], citations: list[dict], notice: str) -> dict:
    """Return retrieved text without implying that an LLM generated a synthesis."""
    excerpts = "\n\n".join(f"{c.document}, page {c.page}" + (f", section {c.section}" if c.section else "") + f": {c.text[:700]}" for c, _ in hits[:3])
    return {"answer": f"Relevant document evidence:\n\n{excerpts}", "citations": citations, "grounded": True, "mode": "extractive", "notice": notice}


def _chat_completions_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    return base if base.endswith("/chat/completions") else f"{base}/chat/completions"


def _response_text(payload: dict) -> str:
    """Read standard OpenAI-compatible text content without exposing reasoning fields."""
    content = payload["choices"][0]["message"].get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(part["text"] for part in content if isinstance(part, dict) and isinstance(part.get("text"), str))
    return ""
