from dataclasses import asdict

from functools import lru_cache

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.document_processing.models import Chunk


@lru_cache(maxsize=2)
def _embedding_model(name: str):
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(name)


def retrieve(question: str, chunks: list[Chunk], limit: int = 5) -> list[tuple[Chunk, float]]:
    if not chunks or not question.strip():
        return []
    corpus = [chunk.text for chunk in chunks]
    # Load the configured Hugging Face encoder lazily; first use may download model weights.
    try:
        from app.config import get_settings
        model = _embedding_model(get_settings().embedding_model)
        vectors = model.encode([question, *corpus], normalize_embeddings=True)
        scores = vectors[1:] @ vectors[0]
        threshold = 0.22
    except Exception:
        # A TF-IDF fallback keeps the app usable offline and on CPU-only setups.
        try:
            matrix = TfidfVectorizer(ngram_range=(1, 2), stop_words="english").fit_transform([question, *corpus])
            scores = cosine_similarity(matrix[0:1], matrix[1:]).ravel()
        except ValueError:
            return []
        # Avoid a model answer for a passage that only shares a generic single word.
        threshold = 0.05
    ranked = sorted(enumerate(scores), key=lambda pair: float(pair[1]), reverse=True)
    return [(chunks[i], float(score)) for i, score in ranked[:limit] if score > threshold]
