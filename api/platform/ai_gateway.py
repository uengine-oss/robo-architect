"""P-GPT — 사내 AI 게이트웨이 설정 묶음.

## 왜 필요한가

AI 를 부르는 자리가 **여섯 갈래**인데, 갈래마다 설정 이름이 달랐다. 그래서
"P-GPT 로 돌렸다"고 말할 수 있는 자리가 없었다 — 어떤 갈래는 옮겨졌고 어떤
갈래는 여전히 밖으로 나가는데, **화면에도 로그에도 그 구분이 안 보였다.**

여기가 그 한 자리다. 키 하나로 옮겨지는 갈래는 옮기고, **옮겨지지 않는
갈래는 이름을 불러 준다**(`describe()`). 조용히 초록인 것이 이 기능의 유일한
실패 방식이다.

    PGPT_BASE_URL        게이트웨이 endpoint (이것이 있으면 P-GPT 모드)
    PGPT_API_KEY         게이트웨이 키
    PGPT_CHAT_MODEL      채팅 모델 slug (없으면 LLM_MODEL / 기본값)
    PGPT_EMBEDDING_BASE_URL  임베딩 endpoint — **따로 준다**
    PGPT_EMBEDDING_API_KEY   임베딩 키
    PGPT_EMBEDDING_MODEL     임베딩 모델

## 임베딩이 따라가지 않는다

사내 게이트웨이는 OpenAI 호환이지만 **임베딩을 제공하지 않는 경우가 있다**
(`platform/embeddings.py`). 그래서 `PGPT_BASE_URL` 하나로는 임베딩이 움직이지
않는다. 임베딩까지 게이트웨이로 보내려면 `PGPT_EMBEDDING_*` 를 **명시**해야
한다. 채팅만 옮기고 임베딩을 잊으면 런타임에 404 로 깨지던 것이, 이제 켜는
순간 진단에 뜬다.

## OPENAI_* 보다 P-GPT 가 이긴다

`PGPT_BASE_URL` 이 있으면 `OPENAI_BASE_URL` 을 덮는다. 반대로 했다면, 이미
`OPENAI_BASE_URL` 이 있는 배포에서 P-GPT 를 켜도 **아무 일도 안 일어나면서
켜진 것처럼 보인다.** 덮었다는 사실은 `describe()` 의 ``overrides`` 에 남는다.

## 옮겨지지 않는 갈래

세 갈래는 이 키로 안 움직인다. 설정이 아니라 **납품 항목**이다.

    pdf2bpmn facade    외부 SaaS (pdf2bpmn.process-gpt.io) — 문서 업로드가 여기를 지난다
    Claude Code PTY    `claude` CLI 가 Anthropic 에 직결
    open-pencil AIChat 브라우저가 직접 부르고 키가 localStorage 에 있다

분석기 스택은 코드가 아니라 **설정 파일**로 옮긴다 —
`robo-data-analyzer/llm_configs/<name>.yaml` 의 `api_base` 와 `ROBO_LLM_CONFIG`.
여기서는 그 사실만 보고한다(우리 프로세스가 아니라 남의 프로세스다).
"""

from __future__ import annotations

from typing import Any

from api.platform.env import env_first, env_str

# 진단 문구에서 쓰는 이름. 갈래 이름을 문서와 화면에서 같게 유지한다.
PATH_ARCHITECT = "architect-backend"
PATH_EMBEDDINGS = "embeddings"
PATH_ANALYZER = "analyzer-stack"
PATH_PDF2BPMN = "pdf2bpmn-facade"
PATH_CLAUDE_PTY = "claude-code-pty"
PATH_OPEN_PENCIL = "open-pencil-aichat"


def base_url() -> str | None:
    """게이트웨이 endpoint. 이 값이 P-GPT 모드의 스위치다."""
    return env_str("PGPT_BASE_URL", default=None)


def enabled() -> bool:
    return bool(base_url())


def api_key() -> str | None:
    return env_str("PGPT_API_KEY", default=None)


def chat_model() -> str | None:
    return env_str("PGPT_CHAT_MODEL", default=None)


def chat_overrides() -> dict[str, Any]:
    """`llm.py` 가 `ChatOpenAI` 에 얹을 인자. P-GPT 모드가 아니면 빈 dict.

    호출부는 이것을 **먼저** 깔고 그 위에 자기 인자를 얹는다 — 호출 시점에
    명시한 값이 설정보다 세다.
    """
    url = base_url()
    if not url:
        return {}
    out: dict[str, Any] = {"base_url": url}
    key = api_key()
    if key:
        out["api_key"] = key
    return out


def embedding_overrides() -> dict[str, Any]:
    """임베딩 쪽. **`PGPT_EMBEDDING_*` 를 따로 줘야 움직인다.**

    채팅용 `PGPT_BASE_URL` 만으로는 임베딩을 옮기지 않는다 — 게이트웨이가
    임베딩을 제공하지 않으면 그대로 깨지기 때문이다.
    """
    url = env_str("PGPT_EMBEDDING_BASE_URL", default=None)
    key = env_str("PGPT_EMBEDDING_API_KEY", default=None)
    if not url and not key:
        return {}
    out: dict[str, Any] = {}
    if url:
        out["base_url"] = url
    if key:
        out["api_key"] = key
    return out


def embedding_model() -> str | None:
    return env_str("PGPT_EMBEDDING_MODEL", default=None)


def _overridden_keys() -> list[str]:
    """P-GPT 가 덮은 기존 설정. 덮은 줄 모르면 원인을 못 찾는다."""
    if not enabled():
        return []
    names = []
    if env_first(["OPENAI_BASE_URL", "OPENAI_API_BASE"], default=None):
        names.append("OPENAI_BASE_URL")
    if api_key() and env_str("OPENAI_API_KEY", default=None):
        names.append("OPENAI_API_KEY")
    return names


def describe() -> dict[str, Any]:
    """여섯 갈래가 지금 어디를 보는가. **비밀값은 담지 않는다.**

    ``status`` 는 셋뿐이다.

        routed       이 설정으로 게이트웨이를 본다
        config-only  우리 코드가 아니라 그쪽 설정 파일로 옮긴다
        unroutable   이 키로는 안 움직인다 — 납품 항목
    """
    from api.platform import embeddings as _emb

    on = enabled()
    emb_over = embedding_overrides()
    emb_state = _emb.describe()

    paths = [
        {
            "id": PATH_ARCHITECT,
            "label": "Architect 백엔드",
            "status": "routed" if on else "default",
            "target": base_url() or emb_state["chatBaseUrl"] or "openai",
            "note": None if on else "PGPT_BASE_URL 미설정 — 기존 OPENAI_* 를 그대로 쓴다",
        },
        {
            "id": PATH_EMBEDDINGS,
            "label": "임베딩",
            "status": "routed" if emb_over else "default",
            "target": emb_state["baseUrl"],
            # 채팅만 옮기고 임베딩을 잊은 상태. 게이트웨이가 임베딩을 안 주면
            # 런타임에 깨진다 — 켜는 순간 여기서 보여야 한다.
            "note": (
                "채팅만 게이트웨이로 갔다. 게이트웨이가 임베딩을 제공하지 않으면 "
                "PGPT_EMBEDDING_BASE_URL / PGPT_EMBEDDING_API_KEY 를 지정하세요."
                if on and not emb_over
                else None
            ),
        },
        {
            "id": PATH_ANALYZER,
            "label": "분석기 스택",
            "status": "config-only",
            "target": None,
            "note": (
                "별개 프로세스다. llm_configs/<name>.yaml 의 api_base 를 게이트웨이로 "
                "두고 ROBO_LLM_CONFIG · ROBO_LLM_API_KEY 로 고른다."
            ),
        },
        {
            "id": PATH_PDF2BPMN,
            "label": "pdf2bpmn facade",
            "status": "unroutable",
            "target": env_str("PDF2BPMN_FACADE_URL", default=None),
            "note": "외부 SaaS. 사내망에서 문서 업로드가 막힌다 — 자체 호스팅이 필요하다.",
        },
        {
            "id": PATH_CLAUDE_PTY,
            "label": "Claude Code PTY",
            "status": "unroutable",
            "target": "anthropic",
            "note": "`claude` CLI 가 직결한다. OpenAI 호환 게이트웨이로 못 보낸다.",
        },
        {
            "id": PATH_OPEN_PENCIL,
            "label": "open-pencil AIChat",
            "status": "unroutable",
            "target": "browser",
            "note": "브라우저가 직접 부르고 키가 localStorage 에 있다. 서버 설정이 안 닿는다.",
        },
    ]

    return {
        "enabled": on,
        "baseUrl": base_url(),
        "chatModel": chat_model(),
        "keyConfigured": bool(api_key()),
        "embeddingKeyConfigured": bool(env_str("PGPT_EMBEDDING_API_KEY", default=None)),
        # 덮은 것을 숨기면 "왜 안 바뀌지"를 못 푼다.
        "overrides": _overridden_keys(),
        "paths": paths,
        "blocked": [p["id"] for p in paths if p["status"] == "unroutable"],
    }
