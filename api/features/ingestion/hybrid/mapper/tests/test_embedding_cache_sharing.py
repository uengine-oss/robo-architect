# -*- coding: utf-8 -*-
"""**코퍼스를 task 마다 다시 임베딩하지 않는다** (2026-09-30).

## 왜 고쳤나

`run_agentic_retrieval` 은 `cache = cache or EmbeddingCache()` 로 받는데,
`explore_task` 가 아무것도 넘기지 않았다. 그래서 task 하나가 끝나면 루틴 171개의
벡터가 통째로 버려지고 다음 task 가 처음부터 다시 임베딩했다.
`module_retriever.retrieve_top_modules` 의 docstring 이 이미 *"(re-embedding the
whole corpus on every Task). Pass `cache` to share embeddings across tasks."* 라고
적어 두었는데 **넘기는 사람이 없었다.**

실측: task 당 embeddings 호출 **8번** — 새로운 것은 질의 1개뿐. 그 자체로도 낭비지만,
같은 날 회선이 흔들려 호출 셋에 하나가 5~20초 멈추자 **task 하나가 3분**이 됐다.
(서버 처리 시간은 45~75ms, rate limit 여유 9999/10000 — 우리 쪽 배수가 문제였다.)

## 여기서 재는 것

  ① 같은 세션은 **같은 캐시**를 받는다 — 다른 세션·익명은 분리된다
  ② 캐시를 공유하면 **두 번째 task 는 임베딩을 다시 부르지 않는다**
  ③ `explore_task` 가 실제로 그 캐시를 넘긴다
  ④ 세션을 무한히 쌓지 않는다

②가 핵심이다. ①만 재면 캐시를 만들어 놓고 안 넘겨도 통과한다.
"""

from __future__ import annotations

import inspect

import pytest

from api.features.ingestion.hybrid import explore_service
from api.features.ingestion.hybrid.mapper import embeddings as emb


@pytest.fixture(autouse=True)
def _clean():
    emb.reset_session_embedding_caches()
    yield
    emb.reset_session_embedding_caches()


class _CountingEmbedder:
    """부른 횟수와 넘어온 텍스트 수를 센다."""

    def __init__(self) -> None:
        self.calls = 0
        self.texts = 0

    def embed_query(self, text: str) -> list[float]:
        self.calls += 1
        self.texts += 1
        return [1.0, 0.0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        self.texts += len(texts)
        return [[0.0, 1.0] for _ in texts]


def test_같은_세션은_같은_캐시를_받는다():
    a = emb.session_embedding_cache("sess_1")
    assert emb.session_embedding_cache("sess_1") is a
    assert emb.session_embedding_cache("sess_2") is not a
    # 세션 id 가 없으면 격리한다 — 남의 벡터를 물려받는 편이 더 나쁘다.
    assert emb.session_embedding_cache(None) is not emb.session_embedding_cache(None)


def test_두번째_task_는_코퍼스를_다시_부르지_않는다(monkeypatch: pytest.MonkeyPatch):
    counter = _CountingEmbedder()
    monkeypatch.setattr(emb, "_make_embedder", lambda: counter)

    corpus = [f"루틴 {i} 가 하는 일" for i in range(40)]

    # task 1
    c = emb.session_embedding_cache("sess_x")
    c.embed_many(corpus)
    c.embed("첫 task 질의")
    after_first = counter.calls
    assert counter.texts == 41

    # task 2 — 같은 세션, 같은 코퍼스, 질의만 다르다.
    c2 = emb.session_embedding_cache("sess_x")
    c2.embed_many(corpus)
    c2.embed("둘째 task 질의")

    assert counter.calls == after_first + 1, (
        "코퍼스를 다시 임베딩했다 — task 마다 배수가 붙는다"
    )
    assert counter.texts == 42, "질의 하나만 새로 임베딩해야 한다"


def test_explore_task_가_세션_캐시를_넘긴다():
    """안 넘기면 `run_agentic_retrieval` 이 task 마다 새 캐시를 만든다."""
    src = inspect.getsource(explore_service.explore_task)
    assert "cache=session_embedding_cache(session_id)" in src, (
        "explore_task 가 캐시를 넘기지 않는다 — 코퍼스가 task 마다 다시 임베딩된다"
    )


def test_세션을_무한히_쌓지_않는다():
    keep = emb._MAX_SESSIONS
    for i in range(keep + 3):
        emb.session_embedding_cache(f"s{i}")
    assert len(emb._by_session) == keep
    # 오래된 것부터 버린다.
    assert "s0" not in emb._by_session
    assert f"s{keep + 2}" in emb._by_session


def test_검사용_초기화는_제품_코드가_부르지_않는다():
    import pathlib

    root = pathlib.Path("api")
    callers = [
        str(p) for p in root.rglob("*.py")
        if "tests" not in p.parts
        and "reset_session_embedding_caches()" in p.read_text(encoding="utf-8")
        and p.name != "embeddings.py"
    ]
    assert callers == [], f"제품 코드가 캐시를 비운다: {callers}"
