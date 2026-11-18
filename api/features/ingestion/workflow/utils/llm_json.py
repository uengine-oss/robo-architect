"""LLM 이 돌려준 JSON 텍스트를 읽는다 — 문자열 **안**은 건드리지 않는다.

예전 정리는 정규식으로 ``//`` 뒤를 줄 끝까지 지웠다. 문자열 값 안의 ``//``(URL ·
``http://…`` · 경로 표기)까지 지워 닫는 따옴표가 사라졌고, json 은 다음 줄에서
"Expecting ',' delimiter" 로 멈췄다. 그 Command 의 GWT 가 통째로 저장되지 않았다
(2026-11-18 POSCO 로컬, ES 생성에서 7건).

순서:
  1. 손대지 않고 읽어 본다 — 대부분은 이미 올바른 JSON 이다.
  2. 문자열 밖에서만 주석(``//`` · ``/* */``)과 꼬리 쉼표를 지우고 다시 읽는다.
제어 문자 정리는 호출자가 하던 대로 둔다(문자열 안 줄바꿈은 ``strict=False`` 가 받는다).
"""
from __future__ import annotations

import json
from typing import Any


def strip_json_noise(text: str) -> str:
    """문자열 밖의 ``//`` 줄 주석, ``/* */`` 블록 주석, ``}``·``]`` 앞 꼬리 쉼표를 지운다."""
    out: list[str] = []
    i, n = 0, len(text)
    in_str = False
    while i < n:
        ch = text[i]
        if in_str:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        if ch == ",":
            k = i + 1
            while k < n and text[k] in " \t\r\n":
                k += 1
            if k < n and text[k] in "}]":
                i += 1
                continue
        out.append(ch)
        i += 1
    return "".join(out)


def loads_llm_json(text: str) -> Any:
    """그대로 → 문자열 밖 정리 순으로 읽는다. 둘 다 안 되면 **두 번째** 오류를 올린다."""
    try:
        return json.loads(text, strict=False)
    except json.JSONDecodeError:
        pass
    return json.loads(strip_json_noise(text), strict=False)
