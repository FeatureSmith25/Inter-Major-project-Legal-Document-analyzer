from types import SimpleNamespace

from app.analysis.analyze import analyze_chunks
from app.analysis.compare import compare_chunks
from app.document_processing.models import Chunk
from app.rag.answer import NOT_FOUND, answer_question


def test_unanswerable_question_returns_required_fallback():
    result = answer_question("What is the weather?", [Chunk("1", "contract", 1, None, None, "The contract starts on January 2, 2025.")])
    assert result["answer"] == NOT_FOUND
    assert not result["citations"]


def test_answer_returns_only_retrieved_document_evidence_with_citation(monkeypatch):
    monkeypatch.setattr("app.rag.answer.get_settings", lambda: SimpleNamespace(llm_base_url="", llm_model=""))
    chunk = Chunk("1", "contract.pdf", 4, "Fees", "2.1", "Customer shall pay $500 within thirty days.")
    result = answer_question("What must the customer pay?", [chunk])
    assert result["grounded"]
    assert "Customer shall pay $500" in result["answer"]
    assert result["citations"][0]["page"] == 4
    assert result["mode"] == "extractive"


def test_model_call_carries_context_and_hides_reasoning(monkeypatch):
    from app.rag import answer as answer_module

    chunk = Chunk("1", "contract.pdf", 4, "Fees", "2.1", "Customer shall pay $500 within thirty days.")
    monkeypatch.setattr(answer_module, "retrieve", lambda *_args: [(chunk, 0.9)])
    monkeypatch.setattr(answer_module, "get_settings", lambda: SimpleNamespace(
        llm_base_url="https://model.example/v1/", llm_model="test-model", llm_api_key="test-key"
    ))
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "<think>private reasoning</think>The customer pays $500 (contract.pdf, page 4)."}}]}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs["json"])
        return Response()

    monkeypatch.setattr(answer_module.httpx, "post", fake_post)
    result = answer_question("What about that?", [chunk], [
        {"role": "user", "content": "What does the payment clause require?"},
        {"role": "assistant", "content": "It describes a payment obligation."},
    ])
    assert result["mode"] == "llm"
    assert "private reasoning" not in result["answer"]
    assert captured["url"] == "https://model.example/v1/chat/completions"
    assert captured["messages"][1]["content"] == "What does the payment clause require?"
    assert captured["messages"][-1]["content"].startswith("Question: What about that?")


def test_provider_failure_is_not_misrepresented_as_a_model_answer(monkeypatch):
    from app.rag import answer as answer_module
    import httpx

    chunk = Chunk("1", "contract.pdf", 4, "Fees", "2.1", "Customer shall pay $500 within thirty days.")
    monkeypatch.setattr(answer_module, "retrieve", lambda *_args: [(chunk, 0.9)])
    monkeypatch.setattr(answer_module, "get_settings", lambda: SimpleNamespace(
        llm_base_url="https://model.example/v1", llm_model="test-model", llm_api_key="test-key"
    ))
    monkeypatch.setattr(answer_module.httpx, "post", lambda *_args, **_kwargs: (_ for _ in ()).throw(httpx.ConnectError("offline")))
    result = answer_question("What must the customer pay?", [chunk])
    assert result["mode"] == "extractive"
    assert "model could not respond" in result["notice"].lower()
    assert "Customer shall pay $500" in result["answer"]


def test_analysis_and_comparison_keep_source_evidence():
    old = [Chunk("1", "old.pdf", 2, "Fees", "3.1", "Customer shall pay $500 within thirty days. This Agreement automatically renews.")]
    new = [Chunk("2", "new.pdf", 2, "Fees", "3.1", "Customer shall pay $700 within thirty days. This Agreement automatically renews.")]
    analysis = analyze_chunks(old)
    assert "Payment" in analysis["clauses"]
    assert analysis["attention_areas"][0]["page"] == 2
    changes = compare_chunks(old, new)
    assert changes
    assert changes[0]["source"]
