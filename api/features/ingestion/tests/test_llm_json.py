"""GWT 응답 JSON 정리가 문자열 안을 건드리지 않는다.

예전 정규식은 `//` 뒤를 줄 끝까지 지워 문자열 값 안의 URL 등에서 닫는 따옴표를 날렸다.
json 은 다음 키의 따옴표에서 "Expecting ',' delimiter: line N column 10" 으로 멈췄고
(8칸 들여쓰기), 그 Command 의 GWT 가 저장되지 않았다(2026-11-18 ES 생성 7건).
"""
from __future__ import annotations

import json
import re

import pytest

from api.features.ingestion.workflow.utils.llm_json import loads_llm_json, strip_json_noise

GWT = """[
  {
    "scenarioDescription": "결재선 생성",
    "given": {
      "name": "Aggregate: LeaveApplication",
      "description": "결재 화면에서 상신",
      "fieldValues": {
        "approvalUrl": "http://hr.posco.com/approve",
        "path": "a//b"
      }
    }
  }
]"""


def test_old_regex_reproduces_the_field_error():
    broken = re.sub(r'//.*?$', '', GWT, flags=re.MULTILINE)
    with pytest.raises(json.JSONDecodeError) as err:
        json.loads(broken, strict=False)
    assert "Expecting ',' delimiter" in str(err.value)
    assert err.value.colno == 10


def test_slashes_inside_strings_survive():
    data = loads_llm_json(GWT)
    fv = data[0]["given"]["fieldValues"]
    assert fv["approvalUrl"] == "http://hr.posco.com/approve"
    assert fv["path"] == "a//b"


def test_comments_and_trailing_commas_outside_strings_are_removed():
    text = """{
      // 주석
      "a": "x // not a comment", /* 블록 */
      "b": [1, 2,],
    }"""
    assert loads_llm_json(text) == {"a": "x // not a comment", "b": [1, 2]}


def test_escaped_quote_does_not_end_the_string():
    text = '{"a": "he said \\"//hi\\"", // c\n "b": 1,}'
    assert loads_llm_json(text) == {"a": 'he said "//hi"', "b": 1}


def test_raw_newline_inside_string_is_accepted():
    assert loads_llm_json('{"d": "줄1\n줄2"}') == {"d": "줄1\n줄2"}


def test_strip_keeps_comma_followed_by_value():
    assert strip_json_noise('[1, 2]') == '[1, 2]'
