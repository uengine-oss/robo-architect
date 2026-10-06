"""템플릿 한 장이 **구조적으로 성립하는가** — 쓰는 자리에서 보는 검사 (TPL-2).

화면에도 같은 검사가 있다(`templateSyntax.js`). 그쪽은 Handlebars 를 실제로
컴파일하니 **문법의 권위는 그쪽**이다. 그런데 화면만 막으면 **API 를 직접 부르면
깨진 템플릿이 그대로 들어간다** — 그리고 템플릿 저장은 한 PC 의 일이 아니다.
중앙 DB 에 들어간 그 한 장이 **모든 PC 의 코드 생성을 깨뜨린다**. 고친 사람은
이미 자기 화면을 떠난 뒤고, 다른 PC 의 사용자는 자기가 하지 않은 일로 멈춘다.

그래서 **쓰는 자리에도** 둔다. 파이썬에는 Handlebars 도 JavaScript 파서도 없으니
여기서 잡는 것은 사람이 실제로 내는 **구조적 파손**이다 —

    닫히지 않은 `{{` · `{{` 를 `}}}` 로 닫은 것 · `{{#if}}` 짝이 안 맞는 것 ·
    `<function>` 태그가 안 닫힌 것 · `<function>` 안의 괄호가 안 맞는 것

문법의 전부가 아니다. **문을 두는 것이지 체를 두는 것이 아니다** — 화면이 이미
한 번 컴파일해서 보내고, 이쪽은 그 화면을 거치지 않은 쓰기를 막는다.

거짓 양성이 없어야 한다 — 출고 템플릿을 막으면 코드 생성 자체가 멈춘다. 그래서
가늠이 안 서는 자리에서는 **검사를 포기한다**(JS 의 정규식 리터럴 등).
`test_template_syntax.py` 가 출고 템플릿 전부를 넣어 **거절 0장**을 지킨다.
"""

from __future__ import annotations

import re

_FUNCTION_OPEN = "<function>"
_FUNCTION_CLOSE = "</function>"
_FUNCTION_BLOCK = re.compile(r"<function>(.*?)</function>", re.DOTALL)

# `{{else}}` 처럼 짝의 바깥에 서는 것들. 열지도 닫지도 않는다.
_NEUTRAL = ("else", "^")

_PAIRS = {")": "(", "]": "[", "}": "{"}


def _line_of(text: str, pos: int) -> int:
    """1-based 줄 번호. 본문 기준이다 — front matter 를 뗀 뒤를 센다."""
    return text.count("\n", 0, pos) + 1


def body_of(text: str) -> str:
    """front matter 를 뗀 나머지.

    쪼개는 규칙은 `repository.parse_template` 과 같아야 한다. 다만 그쪽은 front
    matter 가 아닌 머리글을 보면 **통째로 본문으로 되돌린다** — 여기도 같다.
    """
    from api.features.code_templates.repository import parse_template

    parsed = parse_template(text or "", "<check>")
    # `parse_template` 은 `<function>` 을 떼어 낸 본문을 준다. 검사는 **떼기 전**을
    # 봐야 하므로(태그 짝이 그 안에 있다) 구분자만 같은 규칙으로 다시 자른다.
    raw = text or ""
    head, sep, rest = raw.partition("\n---\n")
    if not sep:
        head, sep, rest = raw.partition("\n---")
    if not sep:
        return raw
    if parsed.for_each is None and parsed.out_path is None and parsed.out_file_name is None:
        # front matter 로 읽히지 않았다 — 통째로 본문이다.
        if head.strip():
            return raw
    return rest.lstrip("\n")


def _mustache_error(body: str) -> str | None:
    """`{{...}}` 를 훑어 **닫기와 짝**을 본다."""
    stack: list[tuple[str, int]] = []
    i = 0
    while True:
        i = body.find("{{", i)
        if i < 0:
            break
        triple = body.startswith("{{{", i)
        open_len = 3 if triple else 2
        close = body.find("}}", i + open_len)
        if close < 0:
            return f"{_line_of(body, i)}줄의 `{{{{` 가 닫히지 않았습니다."
        inner = body[i + open_len:close]
        if "{{" in inner:
            return f"{_line_of(body, i)}줄의 `{{{{` 가 닫히기 전에 다시 열렸습니다."
        if triple:
            if not body.startswith("}}}", close):
                return (
                    f"{_line_of(body, i)}줄: `{{{{{{` 는 `}}}}}}` 로 닫아야 합니다."
                )
            close_len = 3
        elif body.startswith("}}}", close):
            # 사람이 실제로 내는 오류다 — 자바의 `}` 하나가 템플릿 닫기에 붙는다.
            # Handlebars 는 이것을 `Expecting 'CLOSE' … got 'CLOSE_UNESCAPED'` 로 낸다.
            return (
                f"{_line_of(body, i)}줄: `{{{{` 로 열고 `}}}}}}` 로 닫았습니다 — "
                "닫기가 한 글자 많습니다."
            )
        else:
            close_len = 2
        token = inner.strip().strip("~").strip()
        if token.startswith("#") or token.startswith("^"):
            # `{{^if …}}` 도 블록을 연다(뒤집힌 절) — 닫기는 `{{/if}}` 다.
            # 다만 `{{^}}` 혼자는 절 안의 else 자리이고, 여는 것이 아니다.
            name = token.lstrip("#^>").strip().split()[0:1]
            if name:
                stack.append((name[0], i))
        elif token.startswith("/"):
            name = token.lstrip("/").strip()
            if not stack:
                return f"{_line_of(body, i)}줄의 `{{{{/{name}}}}}` 에 맞는 열기가 없습니다."
            opened, at = stack.pop()
            if name and name != opened:
                return (
                    f"{_line_of(body, i)}줄: `{{{{#{opened}}}}}`({_line_of(body, at)}줄)를 "
                    f"`{{{{/{name}}}}}` 로 닫았습니다."
                )
        i = close + close_len
    if stack:
        opened, at = stack[-1]
        return f"{_line_of(body, at)}줄의 `{{{{#{opened}}}}}` 가 닫히지 않았습니다."
    return None


def _js_balance_error(src: str) -> str | None:
    """`<function>` 안의 괄호 짝. **가늠이 안 서면 포기한다.**

    파이썬으로 JavaScript 를 파싱할 수는 없다. 그래서 문자열·주석·정규식을
    건너뛰며 `(){}[]` 만 센다 — 사람이 편집기에서 내는 사고의 대부분은 **잘린
    괄호**다. 정규식 리터럴의 시작을 가릴 수 없는 자리를 만나면 **이 블록의
    검사를 버린다**(거짓 양성보다 못 잡는 쪽이 낫다).
    """
    stack: list[tuple[str, int]] = []
    # 템플릿 문자열 안의 `${…}` 깊이. 백틱이 닫히는 자리를 가리려고 둔다.
    i = 0
    n = len(src)
    prev = ""  # 바로 앞의 뜻 있는 글자 — `/` 가 나눗셈인지 정규식인지 가린다
    while i < n:
        c = src[i]
        if c in "'\"":
            quote = c
            i += 1
            while i < n and src[i] != quote:
                if src[i] == "\\":
                    i += 1
                elif src[i] == "\n":
                    return None  # 줄을 넘는 따옴표 — 우리가 가릴 자리가 아니다
                i += 1
            if i >= n:
                return None
            i += 1
            prev = quote
            continue
        if c == "`":
            i += 1
            depth = 0
            while i < n:
                if src[i] == "\\":
                    i += 2
                    continue
                if src[i] == "$" and src.startswith("${", i):
                    depth += 1
                    i += 2
                    continue
                if src[i] == "}" and depth:
                    depth -= 1
                    i += 1
                    continue
                if src[i] == "`" and not depth:
                    break
                i += 1
            if i >= n:
                return None
            i += 1
            prev = "`"
            continue
        if c == "/" and src.startswith("//", i):
            nl = src.find("\n", i)
            i = n if nl < 0 else nl
            continue
        if c == "/" and src.startswith("/*", i):
            end = src.find("*/", i + 2)
            if end < 0:
                return None
            i = end + 2
            continue
        if c == "/":
            # 앞이 값이면 나눗셈, 아니면 정규식이다. 정규식이면 **포기한다** —
            # `/[}{]/` 처럼 괄호를 품을 수 있어 세면 틀린다.
            if prev not in (")", "]", "`", "'", '"') and not (prev.isalnum() or prev == "_"):
                return None
            i += 1
            prev = "/"
            continue
        if c in "([{":
            stack.append((c, i))
        elif c in ")]}":
            if not stack:
                return f"여는 짝이 없는 `{c}` 가 있습니다({_line_of(src, i)}줄)."
            opened, at = stack.pop()
            if opened != _PAIRS[c]:
                return (
                    f"{_line_of(src, at)}줄의 `{opened}` 를 `{c}` 로 닫았습니다"
                    f"({_line_of(src, i)}줄)."
                )
        if not c.isspace():
            prev = c
        i += 1
    if stack:
        opened, at = stack[-1]
        return f"{_line_of(src, at)}줄의 `{opened}` 가 닫히지 않았습니다."
    return None


def syntax_error(text: str) -> str | None:
    """성립하면 `None`, 아니면 **사람에게 보일 한 줄**.

    문구 앞에 **무엇이 깨졌는지**를 붙인다 — 템플릿 문법인지 `<function>` 안의
    JavaScript 인지 가려 주지 않으면, 받는 사람은 자기 자바 코드를 의심한다.
    """
    body = body_of(text or "")
    opens = body.count(_FUNCTION_OPEN)
    closes = body.count(_FUNCTION_CLOSE)
    if opens != closes:
        return (
            f"`<function>` 태그의 짝이 맞지 않습니다 — 여는 것 {opens}개, "
            f"닫는 것 {closes}개."
        )
    blocks = [m.group(1) for m in _FUNCTION_BLOCK.finditer(body)]
    handlebars = _FUNCTION_BLOCK.sub("", body) if blocks else body
    bad = _mustache_error(handlebars)
    if bad:
        return f"템플릿 문법: {bad}"
    for src in blocks:
        bad = _js_balance_error(src)
        if bad:
            return f"`<function>` 블록의 JavaScript: {bad}"
    return None
