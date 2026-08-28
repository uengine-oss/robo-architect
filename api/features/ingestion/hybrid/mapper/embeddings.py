"""Thin OpenAI embeddings helper with in-memory session cache.

Used by Phase 3 (semantic matching) and optionally Phase 3.0 (glossary
canonicalization). Defaults to `text-embedding-3-small` which is cheap
and good enough for 한↔영 short-span matching.
"""

from __future__ import annotations

import math
from typing import Iterable

from api.platform.embeddings import get_embeddings


def _make_embedder():
    # 임베딩 endpoint/key 는 Chat 라우팅과 분리해서 해석한다 —
    # 사내 게이트웨이가 임베딩을 제공하지 않는 경우가 있다.
    # (모델명은 EMBEDDING_MODEL / HYBRID_EMBEDDING_MODEL 로 지정)
    return get_embeddings()


class EmbeddingCache:
    """Per-session embedding cache so retries / incremental calls don't re-embed."""

    def __init__(self) -> None:
        self._cache: dict[str, list[float]] = {}
        self._embedder = None

    def _ensure(self):
        if self._embedder is None:
            self._embedder = _make_embedder()
        return self._embedder

    def embed(self, text: str) -> list[float]:
        key = text.strip()
        if not key:
            return []
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        vec = self._ensure().embed_query(key)
        self._cache[key] = vec
        return vec

    def embed_many(self, texts: Iterable[str]) -> list[list[float]]:
        uniq = []
        order = []
        for t in texts:
            k = (t or "").strip()
            order.append(k)
            if k and k not in self._cache and k not in uniq:
                uniq.append(k)
        if uniq:
            vecs = self._ensure().embed_documents(uniq)
            for k, v in zip(uniq, vecs):
                self._cache[k] = v
        return [self._cache.get(k, []) for k in order]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
