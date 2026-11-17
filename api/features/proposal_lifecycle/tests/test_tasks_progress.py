"""구현 진행률(PROPOSAL_<id>_TASKS.md 체크박스) 파싱 · 갱신 시각 단위 테스트.

구현 탭은 /progress 를 폴링해 percent·sections 를 그리고, secondsSinceUpdate 로
"멈췄는지"를 판단한다(임계값은 프런트엔드). 파일 시스템은 tmp_path 만 쓴다.
"""

from __future__ import annotations

import os
import time

import pytest

from api.features.proposal_lifecycle.services import tasks_progress as tp
from api.features.proposal_lifecycle.services.tasks_runner import render_tasks_markdown

PID = "PRO-004"

SAMPLE = """\
# Tasks: 부분 환불 (PRO-004)

이 체크리스트는 Proposal 구현 진행 추적용입니다. 각 작업을 완료하면
해당 항목을 `- [x]`로 바꾸고 워크트리에서 git commit 하세요.

## Phase 1: Setup
- [x] T001 결제 도메인 디렉터리 구조 생성 (src/payment/)
- [ ] T002 [P] Kafka 개발환경 docker-compose 추가

## Phase 2: Domain
- [X] T003 [P] PartialRefundAmount VO 추가 <!-- @robo kind=ValueObject id=vo-refund-amount -->
- [ ] T004 Refund Aggregate 에 부분 환불 불변식 추가
      환불 금액은 결제 금액 이하여야 한다 (여러 줄로 이어지는 작업 설명)
      - 이 줄은 체크박스가 아니므로 세지 않는다
  - [x] T004a 불변식 단위 테스트
* [ ] T005 RefundRequested 이벤트 발행

## Phase 3: API
- [ ] T006 부분 환불 Command 핸들러 구현
"""


def test_tasks_filename():
    assert tp.tasks_filename(PID) == "PROPOSAL_PRO-004_TASKS.md"


def test_counts_checkboxes_by_phase():
    r = tp.parse_tasks_markdown(SAMPLE)
    assert r["exists"] is True
    assert r["total"] == 7 and r["done"] == 3
    assert r["percent"] == 43  # round(3/7*100)
    assert r["sections"] == [
        {"title": "Phase 1: Setup", "total": 2, "done": 1},
        {"title": "Phase 2: Domain", "total": 4, "done": 2},
        {"title": "Phase 3: API", "total": 1, "done": 0},
    ]


def test_items_keep_text_section_and_state():
    items = tp.parse_tasks_markdown(SAMPLE)["items"]
    assert [i["text"].split()[0] for i in items] == ["T001", "T002", "T003", "T004", "T004a", "T005", "T006"]
    assert [i["done"] for i in items] == [True, False, True, False, True, False, False]
    # @robo 마커는 표시 텍스트에서 빠진다
    assert items[2]["text"] == "T003 [P] PartialRefundAmount VO 추가"
    # 여러 줄 작업은 첫 줄만 항목 텍스트가 되고 이어지는 줄은 세지 않는다
    assert items[3]["text"] == "T004 Refund Aggregate 에 부분 환불 불변식 추가"
    assert items[4]["section"] == "Phase 2: Domain"  # 들여쓴 하위 항목도 같은 phase


def test_items_before_any_heading_fall_into_default_bucket():
    r = tp.parse_tasks_markdown("- [x] T001 머리말 없는 작업\n- [ ] T002 두 번째\n")
    assert r["items"][0]["section"] is None
    assert r["sections"] == [{"title": "기타", "total": 2, "done": 1}]
    assert r["percent"] == 50


@pytest.mark.parametrize("line, counted, done", [
    ("- [ ] T001 기본", True, False),
    ("- [x] T001 완료", True, True),
    ("- [X] T001 대문자 완료", True, True),
    ("* [x] T001 별표 목록", True, True),
    ("    - [ ] T001 깊게 들여쓴 항목", True, False),
    ("-[x]T001 공백 없이", True, True),
    ("- [ ]", False, None),           # 본문 없는 체크박스
    ("- [] T001 빈 대괄호", False, None),
    ("- [~] T001 진행 중 표기", False, None),
    ("1. [ ] T001 번호 목록", False, None),
    ("- T001 체크박스 없음", False, None),
    ("해당 항목을 `- [x]`로 바꾸세요", False, None),
])
def test_checkbox_forms(line, counted, done):
    r = tp.parse_tasks_markdown(f"## Phase 1: Setup\n{line}\n")
    assert r["total"] == (1 if counted else 0)
    if counted:
        assert r["items"][0]["done"] is done


@pytest.mark.parametrize("text", ["", "\n\n", "# 제목만 있음\n\n설명 문단\n"])
def test_no_checkboxes_is_zero_percent(text):
    r = tp.parse_tasks_markdown(text)
    assert (r["total"], r["done"], r["percent"], r["sections"]) == (0, 0, 0, [])


def test_percent_rounds_to_nearest():
    md = "## P\n- [x] a\n- [x] b\n- [ ] c\n"
    assert tp.parse_tasks_markdown(md)["percent"] == 67


def test_heading_level_does_not_matter_and_last_heading_wins():
    md = "# Tasks\n### Phase 1: Setup\n- [ ] a\n#### 세부\n- [x] b\n"
    r = tp.parse_tasks_markdown(md)
    assert [s["title"] for s in r["sections"]] == ["Phase 1: Setup", "세부"]


# ── 파일 읽기 · 정체 판단용 갱신 시각 ──────────────────────────────────────────

def test_read_progress_without_worktree_or_file(tmp_path):
    for wt in (None, "", str(tmp_path)):
        r = tp.read_progress(wt, PID)
        assert r["exists"] is False and r["total"] == 0
        assert r["updatedAt"] is None and r["secondsSinceUpdate"] is None
        assert r["file"] == "PROPOSAL_PRO-004_TASKS.md"


def test_read_progress_reports_mtime_for_stale_detection(tmp_path):
    f = tmp_path / tp.tasks_filename(PID)
    f.write_text(SAMPLE, encoding="utf-8")
    old = time.time() - 900  # 15분 전 마지막 갱신 → 프런트엔드가 정체로 표시할 수 있다
    os.utime(f, (old, old))
    r = tp.read_progress(str(tmp_path), PID)
    assert r["exists"] is True and r["total"] == 7 and r["done"] == 3
    assert r["updatedAt"] == pytest.approx(old, abs=1)
    assert 899 <= r["secondsSinceUpdate"] < 960


def test_read_progress_future_mtime_is_clamped_to_zero(tmp_path):
    f = tmp_path / tp.tasks_filename(PID)
    f.write_text(SAMPLE, encoding="utf-8")
    future = time.time() + 3600  # 시계가 어긋난 원격 파일시스템 등
    os.utime(f, (future, future))
    assert tp.read_progress(str(tmp_path), PID)["secondsSinceUpdate"] == 0.0


def test_ticking_a_box_updates_progress_and_freshness(tmp_path):
    tasks = [{"id": "T001", "phase": "Phase 1: Setup", "text": "디렉터리 생성", "files": [], "parallel": False},
             {"id": "T002", "phase": "Phase 2: Domain", "text": "VO 추가", "files": [], "parallel": True}]
    f = tmp_path / tp.tasks_filename(PID)
    f.write_text(render_tasks_markdown(PID, "부분 환불", tasks), encoding="utf-8")
    old = time.time() - 600
    os.utime(f, (old, old))
    before = tp.read_progress(str(tmp_path), PID)
    assert (before["done"], before["percent"]) == (0, 0)

    # 셀(claude)이 작업을 끝내고 체크한다
    f.write_text(f.read_text(encoding="utf-8").replace("- [ ] T001", "- [x] T001"), encoding="utf-8")
    after = tp.read_progress(str(tmp_path), PID)
    assert (after["done"], after["percent"]) == (1, 50)
    assert after["secondsSinceUpdate"] < before["secondsSinceUpdate"]


def test_read_progress_tolerates_invalid_utf8(tmp_path):
    f = tmp_path / tp.tasks_filename(PID)
    f.write_bytes("## Phase 1\n- [x] T001 정상\n".encode("utf-8") + b"- [ ] T002 \xff\xfe broken\n")
    r = tp.read_progress(str(tmp_path), PID)
    assert r["total"] == 2 and r["done"] == 1


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root 는 권한 없이도 읽는다")
def test_read_progress_unreadable_file_returns_empty(tmp_path):
    f = tmp_path / tp.tasks_filename(PID)
    f.write_text(SAMPLE, encoding="utf-8")
    f.chmod(0)
    try:
        assert tp.read_progress(str(tmp_path), PID)["exists"] is False
    finally:
        f.chmod(0o644)
