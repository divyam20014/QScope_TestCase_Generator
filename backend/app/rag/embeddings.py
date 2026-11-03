from __future__ import annotations

from functools import lru_cache

import numpy as np

from app.core.config import get_settings


@lru_cache(maxsize=1)
def _get_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(get_settings().embedding_model)


def embed_texts(texts: list[str]) -> np.ndarray:
    """Return L2-normalized embeddings, shape (len(texts), dim), float32.

    Normalizing lets inner-product FAISS search double as cosine similarity.
    """
    if not texts:
        return np.zeros((0, embedding_dim()), dtype="float32")
    model = _get_model()
    vectors = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
    return vectors.astype("float32")


def embed_query(query: str) -> np.ndarray:
    return embed_texts([query])[0]


@lru_cache(maxsize=1)
def embedding_dim() -> int:
    model = _get_model()
    return model.get_sentence_embedding_dimension()
