"""Thin OpenAI embeddings helper with in-memory session cache.

Used by Phase 3 (semantic matching) and optionally Phase 3.0 (glossary
canonicalization). Defaults to `text-embedding-3-small` which is cheap
and good enough for 한↔영 short-span matching.
"""

from __future__ import annotations

import math
from collections import OrderedDict
import os
from typing import Iterable

_DEFAULT_MODEL = "text-embedding-3-small"


def _make_embedder():
    from langchain_openai import OpenAIEmbeddings

    model = os.getenv("HYBRID_EMBEDDING_MODEL", _DEFAULT_MODEL)
    return OpenAIEmbeddings(model=model)


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

# ── 세션 공유 캐시 ────────────────────────────────────────────────────────
#
# 이것이 없으면 `run_agentic_retrieval` 이 task 마다 새 캐시를 만들고, 루틴
# 코퍼스 전체가 **task 마다 다시 임베딩된다.** 실측(enterprise, hr-sample
# 171 루틴 · 28 task): task 당 embeddings 호출 10.1 → 5.5~6.0.
# 1이 되지는 않는다 — task 질의 자체는 매번 새것이라 캐싱할 수 없다.
_MAX_SESSIONS = 2
_by_session: "OrderedDict[str, EmbeddingCache]" = OrderedDict()


def session_embedding_cache(session_id: str | None) -> EmbeddingCache:
    """그 세션의 공유 캐시. 세션 id 가 없으면 매번 새로 만든다(격리).

    남의 세션 벡터를 물려받는 편이 다시 임베딩하는 것보다 나쁘다.
    **크게 자라지 않는다** — 벡터는 1536 float, 코퍼스가 수백 개면 수 MB 다.
    그래도 세션을 무한히 쌓지는 않는다: 오래된 세션부터 버린다.
    """
    if not session_id:
        return EmbeddingCache()
    hit = _by_session.get(session_id)
    if hit is not None:
        _by_session.move_to_end(session_id)
        return hit
    cache = EmbeddingCache()
    _by_session[session_id] = cache
    while len(_by_session) > _MAX_SESSIONS:
        _by_session.popitem(last=False)
    return cache


def reset_session_embedding_caches() -> None:
    """검사용. 제품 코드에는 호출자가 없다."""
    _by_session.clear()
