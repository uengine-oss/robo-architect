"""구조화 출력(LLM → JSON → 스키마)이 **어디서 왜** 깨졌는지 한 줄로 가르는 진단.

## 왜 여기인가

인제스천의 LLM 구조화 호출은 스무 곳 남짓이지만, OpenAI 갈래는 **모두**
`platform/llm.py` 의 ``FunctionCallingChatOpenAI.with_structured_output`` 을
지난다(method 기본값 ``function_calling`` — 모델이 tool 을 부르고 그 arguments
문자열을 JSON 으로 읽어 Pydantic 으로 검증한다). 그래서 진단을 호출부마다 심지
않고 **그 한 자리**에 건다. 단계가 늘어도 따라다닐 필요가 없다.

## 무엇을 가르는가 (2026-11 P-GPT 현장 대비)

    가  request_rejected / tool_ignored   프록시가 tools·response_format 을 400 으로
                                          거절하거나, 버려서 모델이 본문으로만 답함
    나  fenced                            ```json 펜스·앞뒤 설명이 붙음
    다  truncated                         출력이 잘림 (finish_reason=length)
    라  schema_mismatch                   JSON 은 맞는데 필드 이름·형이 스키마와 다름

로그는 전부 ``llm.structured_output.*`` category 로 남긴다. **ERROR** 수준인 이유:
SmartLogger 의 기본 최소 수준이 ERROR 라 그 아래는 콘솔에도 파일에도 안 남는다.

    docker compose logs architect-api | grep 'llm.structured_output'

## 동작은 바꾸지 않는다 — 한 가지만 예외

실패는 예전과 **같은 예외**로 올리고, tool 호출이 없으면 예전과 같이 ``None`` 을
돌려준다. 예외 하나: tool 호출 없이 **본문에 JSON 을 적었고**(펜스·앞뒤 설명
포함), 그 JSON 이 **스키마 검증을 통과**하며, 잘리지 않았을 때(finish_reason≠length)
그 값을 돌려준다. 예전 코드는 이때 ``None`` 을 받아 다음 줄에서
``AttributeError`` 로 죽었다. 살린 경우도 ``recovered`` 로 남긴다 — 조용히 살리면
프록시가 tools 를 버린다는 사실이 안 보인다.

응답 앞뒤 200자는 남기되 키·이메일·전화번호·긴 숫자열은 가린다(``redact``).
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable
from urllib.parse import urlparse

from api.platform.observability.smart_logger import SmartLogger

CATEGORY_PREFIX = "llm.structured_output"
SNIPPET_CHARS = 200

# ---------------------------------------------------------------------------
# 호출 맥락 (예: 인제스천의 현재 단계) — platform 이 feature 를 import 하지 않도록
# feature 쪽이 함수를 등록한다.
# ---------------------------------------------------------------------------
_context_providers: list[Callable[[], dict]] = []


def register_context_provider(fn: Callable[[], dict]) -> None:
    """진단 로그에 붙일 맥락(단계 이름·세션 id 등)을 돌려주는 함수를 등록한다."""
    if fn not in _context_providers:
        _context_providers.append(fn)


def _context() -> dict:
    out: dict = {}
    for fn in _context_providers:
        try:
            got = fn() or {}
            if isinstance(got, dict):
                out.update({k: v for k, v in got.items() if v is not None})
        except Exception:  # noqa: BLE001 — 진단이 본업을 막지 않는다
            pass
    return out


# ---------------------------------------------------------------------------
# 가리기 · 자르기
# ---------------------------------------------------------------------------
_REDACTIONS = [
    (re.compile(r"sk-[A-Za-z0-9_\-]{8,}"), "sk-***"),
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{8,}"), "Bearer ***"),
    (re.compile(r"(?i)(api[_-]?key|token|password|secret)(\"?\s*[:=]\s*\"?)[^\s\"',}]{4,}"), r"\1\2***"),
    (re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"), "***@***"),
    (re.compile(r"01[016789][- .]?\d{3,4}[- .]?\d{4}"), "010-****-****"),
    (re.compile(r"\d{6}[- ]?[1-4]\d{6}"), "******-*******"),
    (re.compile(r"\d{9,}"), "#########"),
]


def redact(text: str) -> str:
    s = text or ""
    for pat, rep in _REDACTIONS:
        s = pat.sub(rep, s)
    return s


def head_tail(text: Any, n: int = SNIPPET_CHARS) -> dict:
    """길이와 앞뒤 n자(가린 뒤). 짧으면 head 하나만."""
    s = text if isinstance(text, str) else ("" if text is None else str(text))
    out: dict = {"len": len(s)}
    if not s:
        return out
    if len(s) <= n * 2:
        out["head"] = redact(s)
    else:
        out["head"] = redact(s[:n])
        out["tail"] = redact(s[-n:])
    return out


# ---------------------------------------------------------------------------
# 관용 JSON 파싱 (갈래 나)
# ---------------------------------------------------------------------------
_FENCE_RE = re.compile(r"```[A-Za-z0-9_-]*[ \t]*\r?\n?(.*?)```", re.DOTALL)


def strip_code_fence(text: str) -> str:
    """처음 나오는 ``` 펜스 안쪽만. 펜스가 없거나 닫히지 않았으면 여는 펜스만 벗긴다."""
    t = (text or "").strip()
    m = _FENCE_RE.search(t)
    if m:
        return m.group(1).strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t[3:]
    return t.strip()


def parse_llm_json(text: str) -> Any:
    """모델이 낸 문자열을 JSON 으로. 펜스·앞뒤 설명을 견딘다.

    순서: 그대로 → 펜스 안쪽 → 본문에서 실제로 파싱되는 가장 큰 객체/배열
    (`skill_runner.extract_json` — raw_decode 스캔, 같은 문제를 이미 푼 함수).
    아무것도 안 되면 **처음 시도의** ``json.JSONDecodeError`` 를 그대로 올린다.

    ⚠ 잘린 JSON 은 살리지 않는다. 다만 잘린 바깥 객체 **안의** 온전한 조각이
    "가장 큰 객체" 로 뽑힐 수는 있다 — 스키마를 아는 호출자는 키를 확인한다
    (``_recover_from_text``).
    """
    raw = text or ""
    try:
        return json.loads(raw)
    except json.JSONDecodeError as first:
        err = first
    try:
        return json.loads(strip_code_fence(raw))
    except json.JSONDecodeError:
        pass
    from api.platform.skill_runner import extract_json  # 지연 import — 무거운 모듈

    found = extract_json(raw)
    if found is None:
        raise err
    return found


def looks_fenced_or_wrapped(text: str) -> bool:
    t = (text or "").strip()
    return "```" in t or (bool(t) and t[0] not in "{[")


# ---------------------------------------------------------------------------
# 응답 뜯어보기
# ---------------------------------------------------------------------------
def _finish_reason(raw: Any) -> str | None:
    meta = getattr(raw, "response_metadata", None) or {}
    fr = meta.get("finish_reason") if isinstance(meta, dict) else None
    return str(fr) if fr is not None else None


def describe_message(raw: Any) -> dict:
    """AIMessage 에서 갈래를 가르는 데 필요한 것만."""
    if raw is None:
        return {"raw": None}
    meta = getattr(raw, "response_metadata", None) or {}
    usage = getattr(raw, "usage_metadata", None) or {}
    content = getattr(raw, "content", None)
    if isinstance(content, list):  # 블록형 content
        content = "".join(
            b.get("text", "") if isinstance(b, dict) else str(b) for b in content
        )
    tool_calls = list(getattr(raw, "tool_calls", None) or [])
    invalid = list(getattr(raw, "invalid_tool_calls", None) or [])
    out: dict = {
        "finish_reason": _finish_reason(raw),
        "model_name": meta.get("model_name") if isinstance(meta, dict) else None,
        "output_tokens": usage.get("output_tokens") if isinstance(usage, dict) else None,
        "content": head_tail(content),
        "tool_calls": len(tool_calls),
        "tool_names": [tc.get("name") for tc in tool_calls if isinstance(tc, dict)],
        "invalid_tool_calls": len(invalid),
    }
    if invalid:
        first = invalid[0] if isinstance(invalid[0], dict) else {}
        out["invalid_tool_name"] = first.get("name")
        out["invalid_args"] = head_tail(first.get("args"))
        out["invalid_error"] = redact(str(first.get("error") or ""))[:300]
    return out


def _status_code(e: BaseException) -> int | None:
    st = getattr(e, "status_code", None)
    if st is None:
        st = getattr(getattr(e, "response", None), "status_code", None)
    return st if isinstance(st, int) else None


def _validation_errors(e: BaseException) -> list[dict] | None:
    """pydantic ValidationError(직접이든 OutputParserException 안이든)의 위치·종류만.

    입력값(input)은 넣지 않는다 — 고객 문서 내용이 실린다.
    """
    cur: BaseException | None = e
    for _ in range(4):
        if cur is None:
            break
        errs = getattr(cur, "errors", None)
        if callable(errs):
            try:
                items = errs()
                return [
                    {"loc": ".".join(str(p) for p in (it.get("loc") or ())),
                     "type": it.get("type"), "msg": str(it.get("msg"))[:120]}
                    for it in items[:10]
                ]
            except Exception:  # noqa: BLE001
                return None
        cur = cur.__cause__ or cur.__context__
    return None


def classify(
    *, raw: Any, parsing_error: BaseException | None, request_error: BaseException | None
) -> tuple[str, str]:
    """(갈래, kind). 금요일 로그에서 이 두 값으로 원인이 갈린다."""
    if request_error is not None:
        msg = str(request_error).lower()
        st = _status_code(request_error)
        if st in (400, 404, 415, 422) and any(
            k in msg for k in ("tool", "function", "response_format", "json_schema", "max_tokens", "max_completion")
        ):
            return "가", "request_rejected"
        return "?", "request_error"
    fr = _finish_reason(raw)
    if fr == "length":
        return "다", "truncated"
    tool_calls = list(getattr(raw, "tool_calls", None) or [])
    invalid = list(getattr(raw, "invalid_tool_calls", None) or [])
    if invalid:
        args = invalid[0].get("args") if isinstance(invalid[0], dict) else ""
        if looks_fenced_or_wrapped(args or ""):
            return "나", "fenced_tool_args"
        return "다", "invalid_tool_args"
    if not tool_calls:
        return "가", "tool_ignored"
    if parsing_error is not None and _validation_errors(parsing_error):
        return "라", "schema_mismatch"
    return "?", "parse_error"


# ---------------------------------------------------------------------------
# 기록
# ---------------------------------------------------------------------------
def _schema_name(schema: Any) -> str:
    if isinstance(schema, dict):
        return str(schema.get("title") or schema.get("name") or "dict")
    return getattr(schema, "__name__", type(schema).__name__)


def _base_host(llm: Any) -> str | None:
    base = getattr(llm, "openai_api_base", None) or getattr(llm, "base_url", None)
    if not base:
        return None
    try:
        return urlparse(str(base)).netloc or str(base)[:80]
    except Exception:  # noqa: BLE001
        return None


def log_structured_event(
    event: str,
    *,
    schema: Any,
    method: str,
    llm: Any = None,
    raw: Any = None,
    parsing_error: BaseException | None = None,
    request_error: BaseException | None = None,
    extra: dict | None = None,
) -> None:
    try:
        branch, kind = classify(raw=raw, parsing_error=parsing_error, request_error=request_error)
        err = request_error or parsing_error
        params: dict = {
            "stage": _schema_name(schema),
            "method": method,
            "branch": branch,
            "kind": kind,
            **_context(),
        }
        if llm is not None:
            params["model"] = getattr(llm, "model_name", None)
            params["max_tokens"] = getattr(llm, "max_tokens", None)
            params["base_host"] = _base_host(llm)
        if raw is not None:
            params["response"] = describe_message(raw)
        if err is not None:
            params["error_type"] = type(err).__name__
            params["error"] = redact(str(err))[:400]
            st = _status_code(err)
            if st is not None:
                params["status_code"] = st
            v = _validation_errors(err)
            if v:
                params["validation_errors"] = v
        if extra:
            params.update(extra)
        SmartLogger.log(
            "ERROR",
            f"structured output {event}: {params['stage']} [{branch}:{kind}]",
            category=f"{CATEGORY_PREFIX}.{event}",
            params=params,
        )
    except Exception:  # noqa: BLE001 — 관측 수단이 관측 대상을 망가뜨리면 안 된다
        pass


def log_text_parse_failure(stage: str, raw_text: Any, error: BaseException, **extra: Any) -> None:
    """tool 을 안 쓰고 본문 문자열을 직접 파싱하는 자리(sequencing · gwt 등)용."""
    try:
        text = raw_text if isinstance(raw_text, str) else getattr(raw_text, "content", raw_text)
        params: dict = {
            "stage": stage,
            "method": "text+json.loads",
            "branch": "나" if looks_fenced_or_wrapped(text if isinstance(text, str) else "") else "?",
            "kind": "text_parse_failed",
            **_context(),
            "response": {
                "finish_reason": _finish_reason(raw_text),
                "content": head_tail(text),
            },
            "error_type": type(error).__name__,
            "error": redact(str(error))[:400],
        }
        if params["response"]["finish_reason"] == "length":
            params["branch"], params["kind"] = "다", "truncated"
        params.update(extra)
        SmartLogger.log(
            "ERROR",
            f"text JSON parse failed: {stage} [{params['branch']}:{params['kind']}]",
            category=f"{CATEGORY_PREFIX}.text_parse_failed",
            params=params,
        )
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# 감싸기
# ---------------------------------------------------------------------------
def _pydantic_model(schema: Any):
    try:
        from pydantic import BaseModel

        if isinstance(schema, type) and issubclass(schema, BaseModel):
            return schema
    except Exception:  # noqa: BLE001
        pass
    return None


def _recover_from_text(schema: Any, raw: Any) -> Any | None:
    """tool 호출 없이 본문에 쓴 JSON 을 스키마로 살린다. 못 살리면 None.

    조건: Pydantic 스키마 · 잘리지 않음 · tool 호출도 잘못된 tool 호출도 없음 ·
    최상위 키 중 하나 이상이 스키마 필드 · 검증 통과.
    """
    model = _pydantic_model(schema)
    if model is None or raw is None:
        return None
    if _finish_reason(raw) == "length":
        return None
    if getattr(raw, "tool_calls", None) or getattr(raw, "invalid_tool_calls", None):
        return None
    content = getattr(raw, "content", None)
    if not isinstance(content, str) or not content.strip():
        return None
    try:
        obj = parse_llm_json(content)
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(obj, dict):
        return None
    fields = set(getattr(model, "model_fields", {}) or {})
    aliases = {
        f.alias for f in (getattr(model, "model_fields", {}) or {}).values() if getattr(f, "alias", None)
    }
    if not (set(obj) & (fields | aliases)):
        return None
    try:
        return model.model_validate(obj)
    except Exception:  # noqa: BLE001
        return None


def wrap_structured(runnable_with_raw: Any, *, schema: Any, method: str, llm: Any = None):
    """``include_raw=True`` 로 만든 runnable 을, ``include_raw=False`` 와 같은 결과를
    내는 runnable 로 감싼다 — 실패만 기록한다(모듈 docstring 참고)."""
    from langchain_core.runnables import RunnableLambda

    def _finish(result: Any) -> Any:
        if not isinstance(result, dict) or "raw" not in result:
            return result  # 모양이 다르면 손대지 않는다
        raw = result.get("raw")
        parsed = result.get("parsed")
        perr = result.get("parsing_error")
        if perr is None and parsed is not None:
            return parsed
        recovered = _recover_from_text(schema, raw) if perr is None else None
        if recovered is not None:
            log_structured_event("recovered", schema=schema, method=method, llm=llm, raw=raw)
            return recovered
        log_structured_event(
            "parse_failed", schema=schema, method=method, llm=llm, raw=raw, parsing_error=perr
        )
        if perr is not None:
            raise perr
        return parsed  # None — 예전과 같다

    def _invoke(input: Any, config: Any = None) -> Any:
        try:
            result = runnable_with_raw.invoke(input, config)
        except Exception as e:
            log_structured_event("request_error", schema=schema, method=method, llm=llm, request_error=e)
            raise
        return _finish(result)

    async def _ainvoke(input: Any, config: Any = None) -> Any:
        try:
            result = await runnable_with_raw.ainvoke(input, config)
        except Exception as e:
            log_structured_event("request_error", schema=schema, method=method, llm=llm, request_error=e)
            raise
        return _finish(result)

    return RunnableLambda(_invoke, afunc=_ainvoke, name=f"structured[{_schema_name(schema)}]")
