"""extract_json — 스킬 stdout 에서 최종 JSON 을 뽑아내는 파서.

배경(실측): PRO-002 Plan 이 `PLAN_PARSE_FAILED` 로 실패했다. 기존 구현은 정규식으로
중첩 구조를 다루려 해서 세 가지 방식으로 깨졌다.
  (a) ```json 펜스 정규식이 **비탐욕**이라, 모델이 JSON 문자열 값 안에 또 코드펜스를
      넣으면(PRO-001 실측) 안쪽에서 끊겨 조각을 파싱하려다 실패
  (b) 폴백 `(\\{[^`]*\\})` 는 본문에 백틱이 하나라도 있으면 전체를 못 잡음
  (c) 그 결과 **내부 조각**이 파싱에 성공하면 그걸 정답으로 반환 — 조용히 틀림
"""
import json

from api.platform.skill_runner import extract_json


def test_plain_json_object():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_fenced_json_block():
    assert extract_json('설명\n```json\n{"a": 1}\n```\n꼬리말') == {"a": 1}


def test_narration_braces_do_not_win_over_the_real_payload():
    """narration 의 작은 {} 보다 실제 산출물(가장 큰 블록)을 고른다."""
    raw = '진행 {상태} 표시\n{"note": "x"}\n```json\n{"tacticalDiff": [1, 2, 3], "plan": {"k": "v"}}\n```'
    assert extract_json(raw) == {"tacticalDiff": [1, 2, 3], "plan": {"k": "v"}}


def test_nested_code_fence_inside_a_string_value():
    """(a) — 값 안에 ```json 이 들어가도 구조가 깨지지 않는다."""
    payload = {"decision": "compose 예시:\n```json\n{\"svc\": \"order\"}\n```", "ok": True}
    raw = "narration\n```json\n" + json.dumps(payload, ensure_ascii=False) + "\n```"
    assert extract_json(raw) == payload


def test_backtick_inside_a_string_value():
    """(b) — 본문에 백틱이 있어도 전체가 잡힌다."""
    payload = {"description": "식별자는 `orderId` 이다", "n": 1}
    raw = "```json\n" + json.dumps(payload, ensure_ascii=False) + "\n```"
    assert extract_json(raw) == payload


def test_inner_fragment_is_not_returned_as_the_answer():
    """(c) — 조각이 파싱되더라도 더 큰 정답을 우선한다."""
    raw = '```json\n{"outer": {"inner": {"leaf": 1}}, "more": [1,2,3]}\n```'
    out = extract_json(raw)
    assert "outer" in out and "more" in out


def test_braces_inside_strings_do_not_unbalance():
    payload = {"tpl": "{{ handlebars }} 와 } 단독 중괄호"}
    assert extract_json(json.dumps(payload, ensure_ascii=False)) == payload


def test_escaped_quote_inside_string():
    payload = {"q": 'he said \\"hi\\" then left'}
    raw = json.dumps(payload, ensure_ascii=False)
    assert extract_json(raw) == payload


def test_array_payload_is_supported():
    assert extract_json('앞말\n```json\n[{"a": 1}, {"b": 2}]\n```') == [{"a": 1}, {"b": 2}]


def test_truncated_json_returns_none():
    """출력이 잘리면 균형이 안 맞으므로 조용히 조각을 주지 않고 None."""
    assert extract_json('```json\n{"tacticalDiff": [{"nodeLabel": "Command"') is None


def test_no_json_at_all():
    assert extract_json("그냥 설명만 있고 JSON 은 없다") is None
    assert extract_json("") is None
    assert extract_json("{}") is None  # 빈 dict 는 산출물로 보지 않는다


def test_multiple_fenced_blocks_picks_the_largest():
    raw = ('```json\n{"a": 1}\n```\n중간 설명\n'
           '```json\n{"tacticalDiff": [1,2,3,4,5], "implementationPlan": {"x": 1}}\n```')
    out = extract_json(raw)
    assert "tacticalDiff" in out


# ── 실측 회귀: narration 의 따옴표가 홀수일 때 ──────────────────────────

def test_odd_quote_in_narration_before_json():
    """PRO-002 실패 재현.

    직접 만든 균형 스캐너는 문서 전체를 `"` 로 토글하며 훑어, JSON 앞
    narration 의 따옴표가 홀수면 JSON 시작을 "문자열 내부"로 오인해
    후보를 하나도 못 찾았다(raw 145,844자, 정상 종료했음에도 PARSE_FAILED).
    """
    payload = {"tacticalDiff": [{"nodeLabel": "Command"}], "implementationPlan": {"v": 1}}
    raw = (
        '[전술] Command: search 계열은 커맨드 없이 ReadModel 로 충족\n'
        '[전술] 인용부호가 하나만 있는 narration: "미완결 인용\n'
        '```json\n' + json.dumps(payload, ensure_ascii=False) + '\n```\n'
        '**요약**: `tacticalDiff` = Command 93 + Event 92\n'
    )
    assert raw.count('"') % 2 == 1 or True  # narration 따옴표가 균형을 깨는 상황
    assert extract_json(raw) == payload


def test_trailing_summary_with_backticks_after_json():
    """JSON 뒤에 백틱 섞인 요약 문단이 붙어도 산출물을 고른다(실측 rawTail 형태)."""
    payload = {"tacticalDiff": [1, 2], "implementationPlan": {"messagingChannel": "Kafka"}}
    raw = ('```json\n' + json.dumps(payload) + '\n```\n'
           '**요약**: `tacticalDiff` = Aggregate 1 + Command 93, `implementationPlan` = 갭 0.')
    assert extract_json(raw) == payload


def test_narration_with_unmatched_brace():
    """narration 에 짝 없는 중괄호가 있어도 무관하다."""
    payload = {"ok": True, "n": 123}
    raw = '진행 상태 { 미완결 중괄호\n' + json.dumps(payload) + '\n'
    assert extract_json(raw) == payload


def test_multiple_valid_json_values_picks_largest():
    small = {"a": 1}
    big = {"tacticalDiff": list(range(50)), "implementationPlan": {"x": "y"}}
    raw = json.dumps(small) + "\n설명\n" + json.dumps(big)
    assert extract_json(raw) == big


def test_json_inside_a_string_value_is_not_picked_separately():
    """값 안에 JSON 문자열이 들어 있어도 바깥 객체가 이긴다."""
    payload = {"note": '{"inner": "이건 문자열이다"}', "real": [1, 2, 3]}
    assert extract_json(json.dumps(payload, ensure_ascii=False)) == payload
