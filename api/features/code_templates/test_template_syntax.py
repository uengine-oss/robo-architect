# -*- coding: utf-8 -*-
"""저장하는 자리에서 **깨진 템플릿을 받지 않는다** (TPL-2).

## 왜 이 검사가 있나

TPL-1 로 템플릿을 고칠 수 있게 되자 문법 오류가 **흔한 일**이 됐다. 화면은
저장 전에 Handlebars 를 한 번 컴파일해 막는다(`templateSyntax.js`). 그런데
**API 를 직접 부르면 그 문을 지나지 않는다** — 그리고 저장은 한 PC 의 일이
아니다. 중앙 DB 에 들어간 한 장이 **모든 PC 의 코드 생성을 깨뜨린다.**

그래서 쓰는 자리에도 문을 둔다. 지키는 것은 둘이다 —

```
① 깨진 것을 **받지 않는다**   사람이 실제로 내는 파손: 닫기 · 짝 · 괄호
② 멀쩡한 것을 **막지 않는다**  출고 템플릿을 거절하면 생성 자체가 멈춘다.
                            그래서 산출물 전부를 넣어 **거절 0장**을 못으로 박는다
```

②가 ①보다 무섭다 — 못 잡은 것은 사람이 고치면 되지만, 멀쩡한 것을 막으면
**아무도 손을 못 댄다**. 그래서 검사기는 가늠이 안 서는 자리에서 포기한다.
"""

from __future__ import annotations

import io
from pathlib import Path

from api.features.code_templates.syntax import body_of, syntax_error

TEMPLATES = Path(__file__).resolve().parents[3] / "templates"

FRONT = "forEach: Command\npath: a\nfileName: b.java\n---\n"


# ── ① 깨진 것 ──────────────────────────────────────────────────────────────

def test_닫기가_한_글자_많으면_거절한다():
    """사용자가 실제로 본 오류다 — 자바의 `}` 가 템플릿 닫기에 붙는다.

    Handlebars 는 이것을 `Expecting 'CLOSE' … got 'CLOSE_UNESCAPED'` 로 낸다.
    사람이 그 문구만 보면 자기 자바 코드를 의심하므로, 우리는 **무엇이 많은지**
    를 말한다.
    """
    err = syntax_error(FRONT + "package a.{{nameCamelCase}}};\n")
    assert err and "닫기" in err
    assert err.startswith("템플릿 문법:")


def test_안_닫힌_중괄호를_거절한다():
    err = syntax_error(FRONT + "class {{namePascalCase {\n}\n")
    assert err and "닫히지 않았" in err


def test_블록의_짝이_다르면_말해_준다():
    err = syntax_error(FRONT + "{{#fieldDescriptors}}x{{/queryParameters}}\n")
    assert err and "/queryParameters" in err


def test_안_닫힌_블록을_거절한다():
    err = syntax_error(FRONT + "{{#fieldDescriptors}}x\n")
    assert err and "닫히지 않았" in err


def test_여는_것이_없는_닫기를_거절한다():
    err = syntax_error(FRONT + "x{{/if}}\n")
    assert err and "맞는 열기가 없" in err


def test_function_태그가_안_닫히면_거절한다():
    """짝이 안 맞으면 정규식이 **그 블록을 못 본다** — JS 가 본문으로 새어
    출력 파일에 그대로 찍힌다. 조용히 지나가는 모양이라 먼저 센다."""
    err = syntax_error(FRONT + "<function>\nfunction a() { return 1 }\n")
    assert err and "<function>" in err and "짝" in err


def test_function_안의_괄호가_안_맞으면_거절한다():
    err = syntax_error(
        FRONT + "<function>\nfunction a(x) { if (x) { return 1 }\n</function>\n")
    assert err and "JavaScript" in err


def test_오류_줄_번호는_본문_기준이다():
    """front matter 를 뗀 뒤를 센다 — 화면의 편집기가 보여 주는 것과 같은 자.

    `templateSyntax.js` 도 같은 자를 쓴다(done6 §139).
    """
    err = syntax_error(FRONT + "a\nb\n{{#if x}}\n")
    assert err and "3줄" in err


# ── ② 멀쩡한 것 ────────────────────────────────────────────────────────────

def test_출고_템플릿_전부를_받는다():
    """**거짓 양성 0.** 산출물에 실려 온 템플릿을 하나라도 막으면 생성이 멈춘다."""
    if not TEMPLATES.is_dir():
        # 템플릿은 굽기가 받아 오는 것이다(`fetch-templates.sh`). 없으면 셀 것이 없다.
        return
    rejected = []
    checked = 0
    for p in sorted(TEMPLATES.rglob("*")):
        if not p.is_file() or ".git" in p.parts:
            continue
        try:
            text = io.open(p, encoding="utf-8").read()
        except UnicodeDecodeError:
            continue  # 텍스트가 아닌 것은 템플릿도 아니다
        checked += 1
        err = syntax_error(text)
        if err:
            rejected.append(f"{p.relative_to(TEMPLATES)} | {err}")
    assert checked > 30, f"읽은 템플릿이 너무 적다({checked}장) — 경로를 확인한다"
    assert not rejected, "출고 템플릿을 거절했다:\n" + "\n".join(rejected)


def test_뒤집힌_절도_블록이다():
    """`{{^if …}}` 는 `{{/if}}` 로 닫힌다 — 출고 템플릿 넷이 이 모양이고,
    `^` 를 중립으로 보면 그 넷이 전부 거절된다(한 번 그렇게 틀렸다)."""
    assert syntax_error(
        FRONT + "{{#fieldDescriptors}}{{^if (isPrimitive className)}}"
        "import a;{{/if}}{{/fieldDescriptors}}\n") is None


def test_else_는_짝을_건드리지_않는다():
    assert syntax_error(FRONT + "{{#if x}}a{{else}}b{{/if}}\n") is None


def test_세겹_중괄호를_받는다():
    assert syntax_error(FRONT + "{{{rawValue}}}\n") is None


def test_주석과_부분과_헬퍼를_받는다():
    assert syntax_error(
        FRONT + "{{! 설명 }}{{> partial}}{{helper a b c=1}}\n") is None


def test_정규식_리터럴이_있으면_괄호를_세지_않는다():
    """`/[{}]/` 처럼 괄호를 품은 정규식은 세면 틀린다. **포기하는 쪽**이 맞다 —
    여기서 거짓 양성을 내면 관리자가 멀쩡한 템플릿을 저장할 수 없다."""
    assert syntax_error(
        FRONT + "<function>\nfunction a(s) { return s.replace(/[{}]/g, '') }\n"
        "</function>\n") is None


def test_문자열_속_괄호를_세지_않는다():
    assert syntax_error(
        FRONT + "<function>\nfunction a() { return '{' + \"}\" + `${1}` }\n"
        "</function>\n") is None


def test_front_matter_가_없으면_통째로_본문이다():
    text = "package a;\n{{name}}\n"
    assert body_of(text) == text
    assert syntax_error(text) is None
