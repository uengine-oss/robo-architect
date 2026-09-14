"""구조화된 US 명세 문서를 읽는가.

**이 파서가 틀리면 조용하다.** 정규식이 한 칸 좁으면 섹션 0개가 되고, 그건 빈
문서와 구별되지 않는다. 상류(MSAez)에서 그 결함을 두 번 고쳤다.

    e731fb30   접두사 있는 ID 를 못 읽었다        PROJ-US-FR-001
    d07a93b6   H5 만 받아 H4/H6 문서가 통째 미매핑

그래서 여기서 재는 것은 "파싱이 되나"가 아니라 **어떤 모양까지 받나** 다.
픽스처에 H4·H6·줄 앞 공백·접두사·빈 태스크를 일부러 섞어 뒀다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from api.features.ingestion.user_story_format import (
    bare_id,
    kind_of,
    looks_like_user_story_document,
    parse_user_story_document,
    to_generated_user_stories,
)

FIXTURE = Path(__file__).parent / "fixtures" / "posco_user_stories.md"


@pytest.fixture(scope="module")
def doc():
    return parse_user_story_document(FIXTURE.read_text(encoding="utf-8"))


def test_이_모양이면_구조화_문서로_본다():
    assert looks_like_user_story_document(FIXTURE.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "text",
    [
        "",
        "그냥 요구사항 문서입니다. 회원이 로그인한다.",
        # 목록 표만 있고 명세가 없다 — 파싱할 본문이 없다.
        "| 인사 (EP-001) | 이름 | US-FR-001 | High |",
        # 본문에 ID 만 언급 — 헤더가 아니다.
        "US-FR-001 을 참고하세요",
    ],
)
def test_아니면_기존_경로로_보낸다(text):
    """**이쪽이 더 중요하다.** 잘못 감지하면 일반 요구사항 문서가 LLM 을 안 거치고
    빈 결과가 된다."""
    assert not looks_like_user_story_document(text)


def test_스토리를_빠짐없이_읽는다(doc):
    ids = [s.id for s in doc.stories]
    assert ids == [
        "US-FR-001", "US-FR-002", "US-FR-012", "US-FR-013",
        "PROJ-US-FR-020",
        "US-NFR-001", "US-NFR-002", "US-NFR-007",
    ]


def test_H4_H6_와_줄앞공백을_받는다(doc):
    """픽스처의 US-FR-013 은 H6, PROJ-US-FR-020 은 H4 + 앞공백이다.
    H5 만 받으면 이 둘이 조용히 사라진다."""
    ids = {s.id for s in doc.stories}
    assert "US-FR-013" in ids, "H6 헤더를 놓쳤다"
    assert "PROJ-US-FR-020" in ids, "H4 + 줄 앞 공백을 놓쳤다"


def test_접두사가_붙어도_목록과_이어진다(doc):
    """명세는 `PROJ-US-FR-020`, 목록 표는 `US-FR-020` 이다. 둘을 같게 보지
    않으면 전부 '목록에 없는 스토리'가 된다."""
    s = next(s for s in doc.stories if s.id == "PROJ-US-FR-020")
    assert bare_id(s.id) == "US-FR-020"
    assert (s.epic_id, s.priority) == ("EP-006", "High")


def test_역할_행위_효익을_가른다(doc):
    s = doc.stories[0]
    assert s.role == "인사업무담당자"
    assert s.action.endswith("싶다")
    assert "인력 운영안을 신속하게 결정할 수 있다" in s.benefit
    # 원문도 남긴다 — 가른 것이 틀렸을 때 돌아갈 곳이 있어야 한다.
    assert s.role in s.description and s.benefit[:10] in s.description


@pytest.mark.parametrize(
    "quote",
    [
        "> * 역할만 있고 구분자가 없다 *",
        "> * 역할, 행위만 있다 *",
        "> ",
    ],
)
def test_못_가르면_비워_둔다(quote):
    """**억지로 채우지 않는다.** 틀리게 채우면 추적성이 조용히 어긋난다."""
    text = f"##### [US-FR-099] 이름\n\n{quote}\n\n---\n"
    s = parse_user_story_document(text).stories[0]
    assert (s.role, s.action, s.benefit) == ("", "", "")


def test_인수조건은_Given_When_Then_을_한_덩어리로(doc):
    s = doc.stories[0]
    assert len(s.acceptance_criteria) == 2
    first = s.acceptance_criteria[0]
    assert first.startswith("Given ")
    assert " When " in first and " Then " in first


def test_태스크를_읽는다(doc):
    s = doc.stories[0]
    assert [t["id"] for t in s.tasks] == [
        "US-FR-001-TASK-001", "US-FR-001-TASK-002", "US-FR-001-TASK-003",
    ]
    assert s.tasks[0]["name"] == "인력계획 시나리오 등록"


def test_비기능은_태스크_0개가_정상이다(doc):
    """**있어야 유효하다고 보면 NFR 이 통째로 사라진다.**"""
    nfr = [s for s in doc.stories if s.kind == "NFR"]
    assert len(nfr) == 3
    assert all(s.tasks == [] for s in nfr)
    # 그래도 인수조건은 있어야 한다 — 비어 있으면 파싱이 끊긴 것이다.
    assert all(s.acceptance_criteria for s in nfr)


def test_에픽과_우선순위는_목록_표에서_온다(doc):
    by = {s.id: s for s in doc.stories}
    assert (by["US-FR-001"].epic_id, by["US-FR-001"].epic_name) == (
        "EP-001", "인사 의사결정 및 평가 지원 자동화")
    # 에픽 칸이 빈 줄은 직전 값을 잇는다.
    assert by["US-FR-002"].epic_id == "EP-001"
    assert by["US-FR-013"].priority == "Medium"
    assert by["US-NFR-007"].epic_id == "EP-011"


def test_목록과_명세가_어긋나면_말해_준다():
    """조용히 빠지면 그 스토리는 아무 데도 안 나타나는데 사람은 다 들어갔다고 믿는다."""
    text = (
        "| 인사 (EP-001) | 있는 것 | US-FR-001 | High |\n"
        "|  | 명세가 없는 것 | US-FR-777 | High |\n"
        "\n##### [US-FR-001] 있는 것\n\n> * 역할,  행위 싶다  효익이다.*\n\n---\n"
        "\n##### [US-FR-888] 목록에 없는 것\n\n> * 역할,  행위 싶다  효익이다.*\n\n---\n"
    )
    d = parse_user_story_document(text)
    assert d.listed_without_spec == ["US-FR-777"]
    assert d.spec_without_listing == ["US-FR-888"]


def test_ID_를_다시_매기지_않는다(doc):
    """**이 검사가 이 기능의 이유다.** 기존 경로는 US-001 을 새로 부여한다."""
    gs = to_generated_user_stories(doc)
    assert [g.id for g in gs][:3] == ["US-FR-001", "US-FR-002", "US-FR-012"]
    assert not any(g.id.startswith("US-00") for g in gs)


def test_화면_서술을_지어내지_않는다(doc):
    """`ui_description` 으로 UI 스티커가 만들어진다. 채우면 **없던 화면이 생긴다.**"""
    assert all(g.ui_description == "" for g in to_generated_user_stories(doc))


def test_변환된_모양이_인제스천_계약을_지킨다(doc):
    gs = to_generated_user_stories(doc)
    g = gs[0]
    assert g.displayName == "시뮬레이션 기반 인력계획 수립"
    assert g.priority == "high"          # 표의 "High" 를 계약 값으로
    assert g.sequence == 1
    assert len(g.tasks) == 3 and g.epic_id == "EP-001"


def test_FR_과_NFR_을_가른다():
    assert kind_of("US-FR-001") == "FR"
    assert kind_of("PROJ-US-NFR-007") == "NFR"


# ── 기존 입력 형식이 영향을 안 받는가 ──────────────────────────────────
#
# **이쪽이 더 중요하다.** 새 길이 안 도는 것은 눈에 띄지만, 기존 문서가 새 길로
#잘못 새면 LLM 을 안 거쳐 **빈 결과**가 되고 그건 조용하다.

@pytest.mark.parametrize(
    "text",
    [
        # 보통의 요구사항 문서 (PDF/DOCX 에서 추출된 텍스트)
        "# 요구사항\n\n## 1. 회원\n회원은 이름과 이메일로 가입한다.\n- 이메일 형식을 검증한다\n",
        # 코드 분석에서 이어지는 입력 (BL 목록)
        "BL[1] 자동납부 신청 요청 수신 시 실시간 인증을 수행한다\nBL[2] 인증 결과를 적재한다\n",
        # 마크다운 표만 있는 문서
        "| 항목 | 값 |\n|---|---|\n| 가 | 나 |\n",
        # US 라는 글자가 있지만 헤더가 아닌 경우
        "## User Story 목록\n- 회원 가입 (US-001)\n- 로그인 (US-002)\n",
        # 헤더는 있는데 FR/NFR 이 아닌 옛 ID 체계
        "##### [US-001] 회원 가입\n\n> * 회원,  가입하고 싶다  서비스를 쓸 수 있다.*\n",
        # 헤더 수준이 H1~H3 — 명세 헤더가 아니다
        "### [US-FR-001] 제목처럼 보이지만 절 제목이다\n",
    ],
)
def test_기존_입력은_새_길로_새지_않는다(text):
    assert not looks_like_user_story_document(text)


def test_옛_ID_체계는_건드리지_않는다():
    """`US-001` / `US-1-3` / `US-A1B2C3D4` 는 기존 경로가 만든 것이다.
    이관하지 않기로 했으므로 이 파서가 손대면 안 된다."""
    for old in ("US-001", "US-1-3", "US-A1B2C3D4"):
        assert not looks_like_user_story_document(f"##### [{old}] 이름\n")
