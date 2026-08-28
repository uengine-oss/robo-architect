"""임베딩 클라이언트 팩토리 — Chat 라우팅과 독립적으로 설정한다.

## 왜 분리하는가

사내 LLM 게이트웨이(POSCO P-GPT 등)는 OpenAI 호환이지만 **임베딩을 제공하지
않는 경우가 있다.** 그런데 `OpenAIEmbeddings()` 는 `OPENAI_BASE_URL` /
`OPENAI_API_KEY` 를 그대로 읽으므로, Chat 을 게이트웨이로 돌리면 임베딩까지
따라가 런타임에 404/400 으로 깨진다.

그래서 임베딩은 **자기 자신의 endpoint/key 쌍**을 갖는다.

    EMBEDDING_API_KEY   설정됨  → 이 키로, EMBEDDING_BASE_URL(미설정 시 OpenAI 본점)
    EMBEDDING_API_KEY   미설정  → 기존과 동일하게 OPENAI_* 를 그대로 사용

즉 기본 동작은 바뀌지 않고, 게이트웨이를 쓰는 배포만 키를 하나 더 주면 된다.
"""

from __future__ import annotations

from typing import Any

from api.platform.env import env_first, env_str
from api.platform.observability.smart_logger import SmartLogger

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"

# OpenAI 본점. 임베딩 전용 키가 있는데 base_url 을 지정하지 않았다면, Chat 이
# 어디를 보든 임베딩은 본점으로 보낸다.
OPENAI_DEFAULT_BASE_URL = "https://api.openai.com/v1"


def embedding_model(default: str = DEFAULT_EMBEDDING_MODEL) -> str:
    # `HYBRID_EMBEDDING_MODEL` 은 기존 키 — 하위 호환으로 계속 인정한다.
    return env_first(["EMBEDDING_MODEL", "HYBRID_EMBEDDING_MODEL"], default=default) or default


def describe() -> dict[str, Any]:
    """진단용 현재 임베딩 라우팅 상태. 키 값은 담지 않는다."""
    dedicated_key = env_first(["EMBEDDING_API_KEY", "OPENAI_EMBEDDING_API_KEY"], default=None)
    chat_base_url = env_first(["OPENAI_BASE_URL", "OPENAI_API_BASE"], default=None)
    embed_base_url = env_str("EMBEDDING_BASE_URL", default=None)

    if dedicated_key:
        effective = embed_base_url or OPENAI_DEFAULT_BASE_URL
        source = "dedicated"
    else:
        effective = embed_base_url or chat_base_url or OPENAI_DEFAULT_BASE_URL
        source = "inherited"

    # Chat 이 게이트웨이로 가는데 임베딩 전용 설정이 없으면, 임베딩도 게이트웨이로
    # 따라간다. 임베딩 미지원 게이트웨이면 런타임에 깨진다.
    at_risk = bool(chat_base_url) and not dedicated_key and not embed_base_url

    return {
        "model": embedding_model(),
        "baseUrl": effective,
        "keySource": source,
        "chatBaseUrl": chat_base_url,
        "sharesChatEndpoint": at_risk,
        "warning": (
            "Chat 이 사내 게이트웨이로 라우팅되는데 임베딩 전용 설정이 없습니다. "
            "게이트웨이가 임베딩을 제공하지 않으면 EMBEDDING_API_KEY 를 지정하세요."
            if at_risk
            else None
        ),
    }


def get_embeddings(model: str | None = None, **kwargs: Any):
    """`OpenAIEmbeddings` 인스턴스를 만든다.

    임베딩 전용 키가 있으면 그 키와 endpoint 를, 없으면 기존처럼 `OPENAI_*` 를
    쓴다(하위 호환).
    """
    from langchain_openai import OpenAIEmbeddings

    resolved_model = model or embedding_model()
    dedicated_key = env_first(["EMBEDDING_API_KEY", "OPENAI_EMBEDDING_API_KEY"], default=None)
    embed_base_url = env_str("EMBEDDING_BASE_URL", default=None)

    if dedicated_key:
        kwargs.setdefault("api_key", dedicated_key)
        # 전용 키를 쓰면서 base_url 을 비워두면 langchain 이 OPENAI_BASE_URL 을
        # 주워 게이트웨이로 보내버린다. 명시적으로 본점을 박는다.
        kwargs.setdefault("base_url", embed_base_url or OPENAI_DEFAULT_BASE_URL)
    elif embed_base_url:
        kwargs.setdefault("base_url", embed_base_url)
    else:
        state = describe()
        if state["sharesChatEndpoint"]:
            SmartLogger.log(
                "WARN",
                "Embeddings inherit the chat gateway endpoint.",
                category="platform.embeddings.shared_endpoint",
                params={"base_url": state["baseUrl"], "model": resolved_model},
            )

    return OpenAIEmbeddings(model=resolved_model, **kwargs)
