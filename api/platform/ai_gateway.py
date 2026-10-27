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

## 옮겨지지 않는 갈래 — **2026-10-27 기준 0개**

셋이라고 적혀 있던 것을 그날 하나씩 재 보니 **셋 다 틀렸다.**

    pdf2bpmn facade    예전엔 외부 SaaS(pdf2bpmn.process-gpt.io). 지금은 **이 PC 안
                       컨테이너**가 돌고(자체 호스팅 완료) compose 가 PGPT_* 를
                       넘긴다 → `facade.py` 가 값이 있을 때만 바꾼다
    open-pencil AIChat 브라우저가 직접 부르지 **않는다**. `aiDesign/bootstrap.js` 가
                       open-pencil 을 **우리 프록시**(`/api/ai-design/v1`)로 맞춰
                       두었고, 그 프록시가 `platform/llm.py` → 여기를 지난다.
                       브라우저에 가는 키는 자리표시자 `"proxy"` 뿐이다
    Claude Code PTY    **이 배포에 없다.** 2026-09-29 에 Code · Proposals 탭을
                       뺐다(`TopBar.vue`) — 사내망에 `claude` CLI 가 없다

⚠ 그러니 **문구를 고치지 않으면 점검표가 거짓말을 한다.** 세 줄 다 "별도 작업이
필요하다" 고 말하고 있었는데, 하나는 이미 한 일이었고 하나는 처음부터 아니었고
하나는 쓰지도 않는 기능이었다.
⚠ 다만 pdf2bpmn 은 **이 프로세스가 컨테이너 안의 값을 직접 읽지 못한다** —
같은 호스트 환경을 compose 가 넘긴다는 사실로 말하는 것이다.

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
        default      P-GPT 가 꺼져 있다 — 기존 OPENAI_* 로 간다
        config-only  우리 코드가 아니라 그쪽 설정 파일로 옮긴다
        not-shipped  **이 배포에 그 기능이 없다** — 옮길 것도 없다
        unroutable   이 키로는 안 움직인다 — 납품 항목

    ⚠ `blocked` 는 `unroutable` 만 센다. "안 쓰는 기능" 을 막힌 것으로 세면
      납품 점검에서 **고칠 수 없는 항목이 영영 남아 있는 것처럼** 보인다.
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
            # 2026-10-27: **자체 호스팅은 끝났다** — 이 PC 안 컨테이너가 돈다.
            # 그 안의 추출기도 이제 같은 손잡이를 따라간다(compose 가 PGPT_* 를
            # 넘기고 `facade.py` 가 값이 있을 때만 바꾼다).
            "status": "routed" if on else "default",
            "target": env_str("PDF2BPMN_FACADE_URL", default=None),
            "note": (
                # 이 프로세스는 컨테이너 안의 값을 **직접 읽지 못한다.** 같은 호스트
                # 환경을 compose 가 넘긴다는 사실로 말하는 것이라고 밝혀 둔다.
                "이 PC 안 컨테이너가 돈다. 그 안의 추출기도 같은 호스트의 "
                "PGPT_BASE_URL 을 따라간다(compose 가 넘긴다) — 컨테이너 안의 값을 "
                "여기서 직접 읽지는 못한다."
                if on
                else "이 PC 안 컨테이너가 돈다. 다만 그 안의 추출기는 지금 "
                     "OpenAI 로 직접 나간다 — PGPT_BASE_URL · PGPT_API_KEY 를 "
                     "지정하면 함께 옮겨진다."
            ),
        },
        {
            "id": PATH_CLAUDE_PTY,
            "label": "Claude Code PTY",
            # 2026-09-29 에 **탭에서 뺐다**(`TopBar.vue` 의 `tabs`). 사내망에는
            # `claude` CLI 가 없어서 열어 두면 눌러도 아무 일이 안 난다.
            # 쓰지 않는 갈래를 "못 옮김" 으로 세면 점검표가 영영 안 닫힌다.
            "status": "not-shipped",
            "target": "anthropic",
            "note": ("이 배포는 Code · Proposals 탭을 뺐다 — 쓰지 않는 갈래다. "
                     "되살리면 `claude` CLI 가 Anthropic 에 직결하므로 OpenAI "
                     "호환 게이트웨이로는 못 보낸다."),
        },
        {
            "id": PATH_OPEN_PENCIL,
            "label": "open-pencil AIChat",
            # 2026-10-27 정정: **밖으로 직접 나가지 않는다.**
            # `frontend/src/features/aiDesign/bootstrap.js` 가 open-pencil 의
            # localStorage 설정을 **우리 프록시**(`/api/ai-design/v1`)로 맞추고,
            # 그 프록시가 `platform/llm.py` 를 거치므로 ai_gateway 를 따라간다.
            # 브라우저에 들어가는 키는 자리표시자 `"proxy"` 뿐이다.
            "status": "routed" if on else "default",
            "target": "/api/ai-design/v1 → Architect 백엔드",
            "note": ("브라우저가 아니라 **Architect 백엔드 프록시**를 지난다 — "
                     "모델 키는 브라우저에 가지 않는다(자리표시자만 둔다). "
                     "그래서 Architect 백엔드와 같이 움직인다."),
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
