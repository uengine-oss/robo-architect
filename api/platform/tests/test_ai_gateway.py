"""P-GPT 설정 묶음 — 여섯 갈래가 어디를 보는가.

여기서 재는 것은 "함수가 dict 를 돌려주나"가 아니라 **두 가지 조용한 실패**다.

    1  이미 OPENAI_BASE_URL 이 있는 배포에서 P-GPT 를 켰는데 아무 일도 안 난다
    2  채팅만 게이트웨이로 옮기고 임베딩을 잊어, 런타임에 404 로 깨진다

둘 다 오류가 안 나는 부류라 검사가 없으면 못 잡는다.
"""

from __future__ import annotations

import pytest

from api.platform import ai_gateway as gw
from api.platform import embeddings as emb

GATEWAY = "http://aigpt.posco.net/gpgpta01-gpt/v1"

_KEYS = (
    "PGPT_BASE_URL", "PGPT_API_KEY", "PGPT_CHAT_MODEL",
    "PGPT_EMBEDDING_BASE_URL", "PGPT_EMBEDDING_API_KEY", "PGPT_EMBEDDING_MODEL",
    "OPENAI_BASE_URL", "OPENAI_API_BASE", "OPENAI_API_KEY",
    "EMBEDDING_API_KEY", "OPENAI_EMBEDDING_API_KEY", "EMBEDDING_BASE_URL",
    "EMBEDDING_MODEL", "HYBRID_EMBEDDING_MODEL", "PDF2BPMN_FACADE_URL",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in _KEYS:
        monkeypatch.delenv(key, raising=False)


def test_꺼져_있으면_아무것도_안_바꾼다():
    """기존 배포의 동작이 바뀌면 안 된다."""
    assert gw.enabled() is False
    assert gw.chat_overrides() == {}
    assert gw.embedding_overrides() == {}


def test_게이트웨이가_기존_OPENAI_BASE_URL_을_덮는다(monkeypatch):
    """**이 검사가 이 파일의 이유다.** 반대로 두면, OPENAI_BASE_URL 이 이미 있는
    배포에서 P-GPT 를 켜도 아무 일이 안 일어나면서 켜진 것처럼 보인다."""
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("PGPT_BASE_URL", GATEWAY)

    assert gw.chat_overrides()["base_url"] == GATEWAY
    assert "OPENAI_BASE_URL" in gw.describe()["overrides"]


def test_덮은_것을_숨기지_않는다(monkeypatch):
    """덮은 줄 모르면 '왜 안 바뀌지'를 못 푼다."""
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-old")
    monkeypatch.setenv("PGPT_BASE_URL", GATEWAY)
    monkeypatch.setenv("PGPT_API_KEY", "pgpt-key")

    overrides = gw.describe()["overrides"]
    assert overrides == ["OPENAI_BASE_URL", "OPENAI_API_KEY"]


def test_비밀값은_진단에_안_담긴다(monkeypatch):
    monkeypatch.setenv("PGPT_BASE_URL", GATEWAY)
    monkeypatch.setenv("PGPT_API_KEY", "pgpt-secret-value")
    monkeypatch.setenv("PGPT_EMBEDDING_API_KEY", "embed-secret-value")

    blob = repr(gw.describe())
    assert "pgpt-secret-value" not in blob
    assert "embed-secret-value" not in blob
    assert gw.describe()["keyConfigured"] is True
    assert gw.describe()["embeddingKeyConfigured"] is True


def test_채팅만_옮기면_임베딩이_따라가지_않는다(monkeypatch):
    """게이트웨이가 임베딩을 제공하지 않는 경우가 있다. 따라가면 런타임에 깨진다."""
    monkeypatch.setenv("PGPT_BASE_URL", GATEWAY)

    assert gw.embedding_overrides() == {}
    assert emb.describe()["baseUrl"] == emb.OPENAI_DEFAULT_BASE_URL


def test_채팅만_옮긴_상태가_진단에_뜬다(monkeypatch):
    """조용히 초록이면 안 된다 — 켜는 순간 보여야 한다."""
    monkeypatch.setenv("PGPT_BASE_URL", GATEWAY)

    paths = {p["id"]: p for p in gw.describe()["paths"]}
    assert paths[gw.PATH_ARCHITECT]["status"] == "routed"
    assert paths[gw.PATH_EMBEDDINGS]["status"] == "default"
    assert "PGPT_EMBEDDING_BASE_URL" in paths[gw.PATH_EMBEDDINGS]["note"]


def test_임베딩을_명시하면_그때_따라간다(monkeypatch):
    monkeypatch.setenv("PGPT_BASE_URL", GATEWAY)
    monkeypatch.setenv("PGPT_EMBEDDING_BASE_URL", "http://embed.posco.net/v1")
    monkeypatch.setenv("PGPT_EMBEDDING_API_KEY", "embed-key")

    assert gw.embedding_overrides() == {
        "base_url": "http://embed.posco.net/v1",
        "api_key": "embed-key",
    }
    state = emb.describe()
    assert state["baseUrl"] == "http://embed.posco.net/v1"
    # 임베딩 자리가 잡혔으니 '따라갈 위험'은 사라져야 한다.
    assert state["sharesChatEndpoint"] is False
    paths = {p["id"]: p for p in gw.describe()["paths"]}
    assert paths[gw.PATH_EMBEDDINGS]["status"] == "routed"


def test_채팅이_게이트웨이인데_임베딩이_비면_위험으로_표시된다(monkeypatch):
    """`PGPT_BASE_URL` 도 채팅 endpoint 다. 여기를 안 세면 옮겨 놓고도
    '위험 없음'이라고 답한다."""
    monkeypatch.setenv("PGPT_BASE_URL", GATEWAY)
    state = emb.describe()

    assert state["chatBaseUrl"] == GATEWAY
    assert state["sharesChatEndpoint"] is True


def test_임베딩_모델도_묶음에서_고를_수_있다(monkeypatch):
    monkeypatch.setenv("PGPT_EMBEDDING_MODEL", "posco-embed-v1")
    assert emb.embedding_model() == "posco-embed-v1"


def test_옮겨지지_않는_갈래를_이름으로_부른다(monkeypatch):
    """설정이 아니라 납품 항목인 것들. 목록에서 빠지면 잊힌다."""
    monkeypatch.setenv("PGPT_BASE_URL", GATEWAY)
    monkeypatch.setenv("PDF2BPMN_FACADE_URL", "https://pdf2bpmn.process-gpt.io")

    state = gw.describe()
    assert set(state["blocked"]) == {
        gw.PATH_PDF2BPMN, gw.PATH_CLAUDE_PTY, gw.PATH_OPEN_PENCIL,
    }
    paths = {p["id"]: p for p in state["paths"]}
    # 사내망을 막는 그 주소가 진단에 그대로 보여야 한다.
    assert paths[gw.PATH_PDF2BPMN]["target"] == "https://pdf2bpmn.process-gpt.io"
    # 분석기는 우리 프로세스가 아니다 — 코드가 아니라 설정 파일로 옮긴다.
    assert paths[gw.PATH_ANALYZER]["status"] == "config-only"
    assert "ROBO_LLM_CONFIG" in paths[gw.PATH_ANALYZER]["note"]


def test_여섯_갈래가_전부_보고된다(monkeypatch):
    ids = [p["id"] for p in gw.describe()["paths"]]
    assert len(ids) == 6
    assert len(set(ids)) == 6


def test_채팅_모델을_묶음에서_고른다(monkeypatch):
    monkeypatch.setenv("PGPT_BASE_URL", GATEWAY)
    monkeypatch.setenv("PGPT_CHAT_MODEL", "posco-gpt-4o")
    assert gw.chat_model() == "posco-gpt-4o"
    assert gw.describe()["chatModel"] == "posco-gpt-4o"


def test_게이트웨이_주소가_실제_클라이언트까지_간다(monkeypatch):
    """설정을 읽는 검사만 두면 **배선이 끊겨도 통과한다.** 실제로 만들어진
    `ChatOpenAI` 가 어디를 보는지 잰다."""
    monkeypatch.setenv("PGPT_BASE_URL", GATEWAY)
    monkeypatch.setenv("PGPT_API_KEY", "pgpt-key")
    monkeypatch.setenv("PGPT_CHAT_MODEL", "posco-gpt-4o")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    from api.platform.llm import get_llm

    llm = get_llm()
    assert str(llm.openai_api_base).rstrip("/") == GATEWAY.rstrip("/")
    assert llm.model_name == "posco-gpt-4o"


def test_호출_시점_인자가_설정보다_세다(monkeypatch):
    """게이트웨이를 켠 뒤에도 한 기능만 다른 곳으로 보낼 수 있어야 한다."""
    monkeypatch.setenv("PGPT_BASE_URL", GATEWAY)
    monkeypatch.setenv("PGPT_API_KEY", "pgpt-key")

    from api.platform.llm import get_llm

    llm = get_llm(model="gpt-4.1", base_url="http://other.internal/v1")
    assert str(llm.openai_api_base).rstrip("/") == "http://other.internal/v1"
    assert llm.model_name == "gpt-4.1"
