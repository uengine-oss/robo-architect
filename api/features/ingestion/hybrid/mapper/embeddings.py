"""Thin OpenAI embeddings helper with in-memory session cache.

Used by Phase 3 (semantic matching) and optionally Phase 3.0 (glossary
canonicalization). Defaults to `text-embedding-3-small` which is cheap
and good enough for 한↔영 short-span matching.
"""

from __future__ import annotations

import math
from collections import OrderedDict
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


# ── 세션 단위 공유 캐시 ──────────────────────────────────────────────────────
#
# **task 마다 코퍼스를 다시 임베딩하고 있었다.** `run_agentic_retrieval` 이
# `cache = cache or EmbeddingCache()` 로 받는데, `explore_task` 가 아무것도 넘기지
# 않아 task 하나가 끝나면 171개 루틴의 벡터가 통째로 버려졌다.
# `module_retriever.retrieve_top_modules` 의 docstring 이 이미 *"(re-embedding the
# whole corpus on every Task). Pass `cache` to share embeddings across tasks."* 라고
# 적어 두었는데 **넘기는 사람이 없었다.**
#
# 2026-09-30 실측: task 당 embeddings 호출 **8번** — 새로운 것은 질의 1개뿐이고
# 나머지 7개가 같은 코퍼스였다. 그 자체로도 낭비지만, 같은 날 회선이 흔들려
# 호출 세 번에 한 번이 5~20초씩 멈추자 **task 하나가 3분**이 됐다. 배수 8을
# 1로 줄인다.
#
# 세션으로 묶는 이유: 프로세스가 달라도 코퍼스는 같다(같은 분석 graph). 그리고
# 화면의 task 한 개 재탐색도 같은 캐시를 탄다.
_MAX_SESSIONS = 2
_by_session: "OrderedDict[str, EmbeddingCache]" = OrderedDict()


def session_embedding_cache(session_id: str | None) -> EmbeddingCache:
    """그 세션의 공유 캐시. 세션 id 가 없으면 매번 새로 만든다(격리).

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


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
