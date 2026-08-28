from __future__ import annotations

import pytest

from api.platform import embeddings as emb

_KEYS = (
    "EMBEDDING_API_KEY", "OPENAI_EMBEDDING_API_KEY", "EMBEDDING_BASE_URL",
    "EMBEDDING_MODEL", "HYBRID_EMBEDDING_MODEL", "OPENAI_BASE_URL", "OPENAI_API_BASE",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in _KEYS:
        monkeypatch.delenv(key, raising=False)


def test_default_routes_to_openai(monkeypatch):
    state = emb.describe()

    assert state["baseUrl"] == emb.OPENAI_DEFAULT_BASE_URL
    assert state["keySource"] == "inherited"
    assert state["sharesChatEndpoint"] is False
    assert state["warning"] is None


def test_gateway_without_dedicated_key_is_flagged(monkeypatch):
    """P-GPT 처럼 임베딩 미지원 게이트웨이로 Chat 을 돌리면 임베딩이 따라간다."""
    monkeypatch.setenv("OPENAI_BASE_URL", "http://aigpt.posco.net/gpgpta01-gpt/v1")
    state = emb.describe()

    assert state["sharesChatEndpoint"] is True
    assert state["baseUrl"] == "http://aigpt.posco.net/gpgpta01-gpt/v1"
    assert "EMBEDDING_API_KEY" in state["warning"]


def test_dedicated_key_pins_embeddings_to_openai(monkeypatch):
    """전용 키가 있으면 Chat 이 게이트웨이를 봐도 임베딩은 본점으로 간다."""
    monkeypatch.setenv("OPENAI_BASE_URL", "http://aigpt.posco.net/gpgpta01-gpt/v1")
    monkeypatch.setenv("EMBEDDING_API_KEY", "sk-real-openai")
    state = emb.describe()

    assert state["keySource"] == "dedicated"
    assert state["baseUrl"] == emb.OPENAI_DEFAULT_BASE_URL
    assert state["sharesChatEndpoint"] is False
    assert state["warning"] is None


def test_msaez_key_name_is_accepted(monkeypatch):
    """기준 구현의 키 이름(OPENAI_EMBEDDING_API_KEY)도 인정한다."""
    monkeypatch.setenv("OPENAI_BASE_URL", "http://aigpt.posco.net/gpgpta01-gpt/v1")
    monkeypatch.setenv("OPENAI_EMBEDDING_API_KEY", "sk-real-openai")

    assert emb.describe()["keySource"] == "dedicated"


def test_explicit_embedding_base_url_wins(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://aigpt.posco.net/gpgpta01-gpt/v1")
    monkeypatch.setenv("EMBEDDING_BASE_URL", "http://embed.internal/v1")
    state = emb.describe()

    assert state["baseUrl"] == "http://embed.internal/v1"
    assert state["sharesChatEndpoint"] is False


def test_model_resolution_and_legacy_key(monkeypatch):
    assert emb.embedding_model() == emb.DEFAULT_EMBEDDING_MODEL

    monkeypatch.setenv("HYBRID_EMBEDDING_MODEL", "text-embedding-3-large")
    assert emb.embedding_model() == "text-embedding-3-large"

    # 새 키가 우선한다.
    monkeypatch.setenv("EMBEDDING_MODEL", "bge-m3")
    assert emb.embedding_model() == "bge-m3"


def test_describe_never_exposes_key(monkeypatch):
    monkeypatch.setenv("EMBEDDING_API_KEY", "sk-secret-value")
    state = emb.describe()

    assert "sk-secret-value" not in str(state)
