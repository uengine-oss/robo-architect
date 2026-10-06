# -*- coding: utf-8 -*-
"""Policy 가 **자기 설명과 다른 Command 를 부르는가** (2026-10-06).

기준 그래프에서 실제로 하나 나왔다 — 설명은 `then GrantAnnualLeave` 인데 엣지는
`DeductAnnualLeaveBalance` 를 가리켰다(done6 §135 ①). 업무로 맞는지 틀린지 이전에
**자기 설명과 다르다**, 그래서 기계가 잡는다.

```
① 적어 둔 이름을 읽는다      "… then GrantAnnualLeave in LeaveEntitlement" → GrantAnnualLeave
② 안 적혀 있으면 **센 적 없는 것**으로 둔다 (산문 설명이 대부분이다)
③ 다르면 고른다 — 다만 **막지 않는다**. 세기만 한다
```
"""

from __future__ import annotations

import pytest

from api.features.ingestion.hybrid.policy_consistency import (
    check_policy_targets,
    declared_command,
    duplicate_commands,
)


# ── ① 적어 둔 이름 ────────────────────────────────────────────────────────

@pytest.mark.parametrize("text,expected", [
    ("When 연차 부여됨 in ApprovalWorkflow then GrantAnnualLeave in LeaveEntitlement 한다",
     "GrantAnnualLeave"),
    ("then ApplyLeaveRequest", "ApplyLeaveRequest"),
    ("THEN DeductAnnualLeaveBalance 를 부른다", "DeductAnnualLeaveBalance"),
])
def test_설명이_적어_둔_Command_를_읽는다(text, expected):
    assert declared_command(text) == expected


@pytest.mark.parametrize("text", [
    None, "", "결재선 생성에 실패하면 휴가 신청을 자동으로 취소합니다.",
    "then 한글만 적힌 경우",
])
def test_안_적혀_있으면_비교하지_않는다(text):
    """`None` 은 '틀렸다' 가 아니라 **'비교할 근거가 없다'** 다."""
    assert declared_command(text) is None


# ── ③ 고르기 ──────────────────────────────────────────────────────────────

def test_설명과_엣지가_다르면_고른다():
    rows = [{
        "policy": "RecalculateLeaveBalanceOnAnnualLeaveGranted",
        "description": "When 연차 부여됨 then GrantAnnualLeave in LeaveEntitlement",
        "command": "DeductAnnualLeaveBalance",
    }]
    out = check_policy_targets(rows)
    assert out["checked"] == 1 and out["mismatched"] == 1
    assert out["samples"][0]["declared"] == "GrantAnnualLeave"
    assert out["samples"][0]["actual"] == "DeductAnnualLeaveBalance"


def test_같으면_안_고른다_대소문자는_무시한다():
    rows = [{"policy": "P", "description": "then applyLeaveRequest", "command": "ApplyLeaveRequest"}]
    out = check_policy_targets(rows)
    assert out == {"checked": 1, "mismatched": 0, "samples": []}


def test_산문_설명은_세지_않는다():
    """비교 못 하는 것을 불일치로 세면 **거의 전부가 불일치**가 된다."""
    rows = [{"policy": "P", "description": "결재선 생성 실패 시 취소합니다", "command": "CancelLeaveRequest"}]
    assert check_policy_targets(rows)["checked"] == 0


def test_엣지가_아예_없으면_세지_않는다():
    """Command 를 안 부르는 Policy 는 이 검사의 대상이 아니다."""
    rows = [{"policy": "P", "description": "then GrantAnnualLeave", "command": None}]
    out = check_policy_targets(rows)
    assert out["checked"] == 1 and out["mismatched"] == 0


def test_표본은_다섯까지만_든다():
    rows = [{"policy": f"P{i}", "description": "then A", "command": "B"} for i in range(9)]
    out = check_policy_targets(rows)
    assert out["checked"] == 9 and len(out["samples"]) == 5


# ── 중복 Command (PROMO-1) ────────────────────────────────────────────────

def test_중복_Command_를_센다():
    """기준 그래프의 실제 값 — 17개 중 고유 15개, 두 이름이 두 벌씩."""
    names = ["ApplyLeaveRequest", "ApproveApprovalStep", "ApproveApprovalStep",
             "RejectApprovalStep", "RejectApprovalStep", "CancelLeaveRequest"]
    out = duplicate_commands(names)
    assert out["total"] == 6 and out["unique"] == 4 and out["extra"] == 2
    assert out["duplicated"] == ["ApproveApprovalStep", "RejectApprovalStep"]


def test_중복이_없으면_빈_목록이다():
    out = duplicate_commands(["A", "B", "C"])
    assert out["duplicated"] == [] and out["extra"] == 0
