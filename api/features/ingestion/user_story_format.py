"""포스코 User Story 문서 — 감지와 구조 파싱.

## 왜 LLM 을 안 쓰나

이 문서는 **이미 구조화돼 있다.** ID·이름·인수조건·태스크·에픽이 전부 문법으로
표시돼 있어서 읽기만 하면 된다. LLM 에 넣으면 셋을 잃는다.

```
ID       프롬프트가 "US-001, US-002 형식으로 순차 부여하세요"라고 지시한다
         → 문서의 US-FR-001 이 버려진다
잘림     출력 토큰 한계에 걸리면 뒤쪽 스토리가 통째로 사라진다 (ENT-AI-001)
재현성   같은 문서를 두 번 넣으면 다른 결과가 나온다
```

그래서 **이 모양이면 이 길로, 아니면 지금까지의 길로** 간다. 기존 입력 형식은
한 줄도 안 바뀐다.

## 정규식은 MSAez 정본을 따른다

`local-msaez/platform` 의 `DocumentTemplate.vue` · `TextChunker.js` ·
`es_trace_util.py` 가 같은 규칙을 쓴다. 하나라도 어긋나면 **섹션 0개가 되고,
그건 빈 문서와 구별되지 않는다.** 실제로 상류에서 두 번 그 결함을 고쳤다.

```
e731fb30   접두사 있는 ID 를 못 읽었다        PROJ-US-FR-001
d07a93b6   H5 만 받아 H4/H6 문서가 통째 미매핑
```

## 인용문 한 줄에서 역할·행위·효익을 가른다

```
> * 인사업무담당자,··시뮬레이션을 활용해 … 비교하고 싶다··조직, … 결정할 수 있다.*
     역할,          행위                      효익
```

**구분자는 공백 둘 이상이다.** 원본 서식(이탤릭)만 남고 연결어가 비어 있어서
이렇게 됐다. 못 가르면 **셋을 비우고 원문 전체를 설명으로 남긴다** — 억지로
채우면 추적성이 조용히 어긋난다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

# 접두사는 있어도 되고 없어도 된다 (`PROJ-US-FR-001`).
_US_ID = r"(?:[A-Za-z][\w-]*-)?US-(?:FR|NFR)-\d+"

# 헤더 — H4~H6 과 줄 앞 공백을 받는다. 좁히면 조용히 0개가 된다.
US_HEADER_RE = re.compile(rf"^\s*#{{4,6}}\s+\[({_US_ID})\]\s+(.+?)\s*$")
US_ID_RE = re.compile(rf"\[?({_US_ID})\]?")

# 에픽 머리 — `#### 2.1.1. [EP-001] 이름`
EPIC_HEADER_RE = re.compile(r"^\s*#{2,6}\s*[\d.]*\s*\[(EP-\d+)\]\s+(.+?)\s*$")

# 태스크 — `- [US-FR-001-TASK-001] 이름`
TASK_RE = re.compile(rf"^\s*[-*]\s*\[({_US_ID}-TASK-\d+)\]\s+(.+?)\s*$")

# 목록 표의 한 줄. 에픽 칸은 첫 줄에만 차 있고 이어지는 줄은 비어 있다.
_TABLE_ROW_RE = re.compile(
    rf"^\s*\|(?P<epic>[^|]*)\|(?P<name>[^|]*)\|\s*(?P<id>{_US_ID})\s*\|(?P<pri>[^|]*)\|"
)
_EPIC_IN_CELL_RE = re.compile(r"^(.*?)\s*\((EP-\d+)\)\s*$")

# 스토리 구분선.
_HR_RE = re.compile(r"^\s*-{3,}\s*$")

# 인용문 한 줄. 앞뒤 `*` 는 이탤릭 표시라 벗긴다.
_QUOTE_RE = re.compile(r"^\s*>\s*(.*?)\s*$")

# 인수조건 묶음의 첫 줄. 이어지는 When/Then 은 들여쓴 줄로 온다.
_AC_START_RE = re.compile(r"^\s*[-*]\s+(Given\b.*)$", re.IGNORECASE)
_AC_CONT_RE = re.compile(r"^\s{2,}((?:When|Then|And)\b.*)$", re.IGNORECASE)


def bare_id(story_id: str) -> str:
    """접두사를 벗긴 ID. `PROJ-US-FR-020` → `US-FR-020`.

    목록 표는 접두사 없이 적고 명세는 접두사를 붙이는 문서가 있다. 둘을 같은
    것으로 보지 않으면 **전부 "목록에 없는 스토리"가 된다.**
    """
    i = story_id.find("US-")
    return story_id[i:] if i >= 0 else story_id


def kind_of(story_id: str) -> str:
    """`FR` 또는 `NFR`."""
    return "NFR" if "-NFR-" in story_id else "FR"


@dataclass
class ParsedUserStory:
    id: str
    name: str
    kind: str
    epic_id: Optional[str] = None
    epic_name: Optional[str] = None
    priority: Optional[str] = None
    role: str = ""
    action: str = ""
    benefit: str = ""
    description: str = ""
    acceptance_criteria: list[str] = field(default_factory=list)
    tasks: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "epicId": self.epic_id,
            "epicName": self.epic_name,
            "priority": self.priority,
            "role": self.role,
            "action": self.action,
            "benefit": self.benefit,
            "description": self.description,
            "acceptance_criteria": list(self.acceptance_criteria),
            "tasks": [dict(t) for t in self.tasks],
        }


@dataclass
class ParsedDocument:
    stories: list[ParsedUserStory] = field(default_factory=list)
    #: 목록 표에는 있는데 명세가 없는 ID. **조용히 지나가면 안 된다.**
    listed_without_spec: list[str] = field(default_factory=list)
    #: 명세는 있는데 목록 표에 없는 ID.
    spec_without_listing: list[str] = field(default_factory=list)


def looks_like_user_story_document(text: str) -> bool:
    """이 텍스트가 US 명세 문서인가.

    **헤더가 하나라도 있으면** 그렇게 본다. 목록 표만 있고 명세가 없는 문서는
    이 길로 보내지 않는다 — 파싱할 본문이 없다.
    """
    if not text:
        return False
    for line in text.splitlines():
        if US_HEADER_RE.match(line):
            return True
    return False


def _split_role_action_benefit(quote: str) -> tuple[str, str, str]:
    """인용문 한 줄 → (역할, 행위, 효익). 못 가르면 전부 빈 문자열.

    구분자는 **공백 둘 이상**이다. 못 가른 것을 억지로 채우지 않는다.
    """
    body = quote.strip()
    # 이탤릭 표시를 벗긴다. 양쪽 어느 한쪽만 있어도 벗긴다.
    body = re.sub(r"^\*+\s*", "", body)
    body = re.sub(r"\s*\*+$", "", body)
    parts = [p.strip() for p in re.split(r"\s{2,}", body) if p.strip()]
    if len(parts) != 3:
        return "", "", ""
    role, action, benefit = parts
    return role.rstrip(",， "), action, benefit


def _parse_listing_tables(lines: list[str]) -> dict[str, dict[str, str]]:
    """목록 표에서 ID → {우선순위, 에픽}. 표가 없으면 빈 dict.

    에픽 칸은 그 묶음의 **첫 줄에만** 차 있다. 빈 칸이면 직전 값을 잇는다.
    """
    out: dict[str, dict[str, str]] = {}
    current_epic: tuple[str, str] | None = None
    for line in lines:
        m = _TABLE_ROW_RE.match(line)
        if not m:
            continue
        cell = m.group("epic").strip()
        if cell:
            em = _EPIC_IN_CELL_RE.match(cell)
            current_epic = (em.group(2), em.group(1).strip()) if em else None
        entry: dict[str, str] = {"priority": m.group("pri").strip()}
        if current_epic:
            entry["epicId"], entry["epicName"] = current_epic
        out[bare_id(m.group("id"))] = entry
    return out


def parse_user_story_document(text: str) -> ParsedDocument:
    """US 명세 문서를 읽는다. **LLM 을 부르지 않는다.**"""
    lines = (text or "").splitlines()
    listing = _parse_listing_tables(lines)

    doc = ParsedDocument()
    epic: tuple[str, str] | None = None
    story: ParsedUserStory | None = None
    pending_ac: list[str] = []

    def flush() -> None:
        nonlocal story, pending_ac
        if story is None:
            return
        if pending_ac:
            story.acceptance_criteria.append(" ".join(pending_ac))
            pending_ac = []
        doc.stories.append(story)
        story = None

    for raw in lines:
        header = US_HEADER_RE.match(raw)
        if header:
            flush()
            sid, name = header.group(1), header.group(2).strip()
            meta = listing.get(bare_id(sid), {})
            story = ParsedUserStory(
                id=sid,
                name=name,
                kind=kind_of(sid),
                # 에픽은 목록 표가 우선이다. 표가 없으면 바로 위 에픽 머리를 쓴다.
                epic_id=meta.get("epicId") or (epic[0] if epic else None),
                epic_name=meta.get("epicName") or (epic[1] if epic else None),
                priority=meta.get("priority") or None,
            )
            continue

        # 에픽 머리는 US 헤더가 아닌 것만. `[EP-001]` 과 `[US-FR-001]` 은 모양이
        # 비슷해서 순서를 바꾸면 US 헤더가 에픽으로 먹힌다.
        ep = EPIC_HEADER_RE.match(raw)
        if ep:
            flush()
            epic = (ep.group(1), ep.group(2).strip())
            continue

        if story is None:
            continue

        if _HR_RE.match(raw):
            flush()
            continue

        task = TASK_RE.match(raw)
        if task:
            if pending_ac:
                story.acceptance_criteria.append(" ".join(pending_ac))
                pending_ac = []
            story.tasks.append({"id": task.group(1), "name": task.group(2).strip()})
            continue

        ac = _AC_START_RE.match(raw)
        if ac:
            if pending_ac:
                story.acceptance_criteria.append(" ".join(pending_ac))
            pending_ac = [ac.group(1).strip()]
            continue

        cont = _AC_CONT_RE.match(raw)
        if cont and pending_ac:
            pending_ac.append(cont.group(1).strip())
            continue

        quote = _QUOTE_RE.match(raw)
        if quote and not story.description and quote.group(1).strip():
            story.description = quote.group(1).strip().strip("*").strip()
            story.role, story.action, story.benefit = _split_role_action_benefit(
                quote.group(1)
            )
            continue

    flush()

    # 목록과 명세를 맞춰 본다. 어긋나면 **말해 준다** — 조용히 빠지면 그 스토리는
    # 아무 데도 안 나타나고, 사람은 문서가 잘 들어갔다고 믿는다.
    spec_ids = {bare_id(s.id) for s in doc.stories}
    doc.listed_without_spec = sorted(set(listing) - spec_ids)
    doc.spec_without_listing = sorted(spec_ids - set(listing)) if listing else []
    return doc


def to_generated_user_stories(doc: ParsedDocument) -> list[Any]:
    """파싱 결과를 인제스천이 쓰는 모양(`GeneratedUserStory`)으로.

    **ID 를 다시 매기지 않는다.** 문서가 정한 것이 정본이다 — 여기서 새로 매기면
    이 기능의 이유가 통째로 사라진다.

    `ui_description` 은 비워 둔다. 이 문서에는 화면 서술이 없다. 지어내면 그
    문장으로 UI 스티커가 만들어져 **없던 화면이 생긴다.**
    """
    from api.features.ingestion.ingestion_contracts import GeneratedUserStory

    out: list[Any] = []
    for i, s in enumerate(doc.stories, start=1):
        out.append(
            GeneratedUserStory(
                id=s.id,
                role=s.role,
                action=s.action or s.name,
                benefit=s.benefit,
                priority=(s.priority or "medium").strip().lower() or "medium",
                sequence=i,
                ui_description="",
                displayName=s.name,
                acceptance_criteria=list(s.acceptance_criteria),
                epic_id=s.epic_id,
                epic_name=s.epic_name,
                tasks=[dict(t) for t in s.tasks],
            )
        )
    return out
