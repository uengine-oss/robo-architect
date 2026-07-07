"""013-report-mcda — 결정론 보고서 렌더러 (순수 파이썬 포맷터).

`render_report(phase, artifact)` 가 저장 artifact 를 **표 중심 마크다운**으로 렌더한다.
설계(spec §6 / plan Step 2):
  - 순수 파이썬 f-string/문자열 빌드 (Jinja2 미채택 — 조용한 누락 회피).
  - **완전성 가드**: `report_contract_data.REPORT_CONTRACT` 기준으로 미표시 top-level 키·
    리스트 원소를 런타임 검출→강제 append(누락 0 을 코드로 보장, FR-1/AC-1).
  - **결정론**: 입력 동일 → 출력 바이트 동일(정렬·안정 순회, AC-5).
  - **다형**(plan Q3): phase ∈ {QUESTION, VIOLATIONS} 는 전용 렌더(clarify/validation).

신규 Neo4j 스키마 없음. 표시 계층 전용.
"""

from __future__ import annotations

from typing import Any

from api.features.proposal_lifecycle.services import report_contract_data as rc

# --- 스칼라/표 유틸 ----------------------------------------------------------


def _cell(value: Any) -> str:
    """마크다운 표 셀용 안전 문자열(파이프/개행 이스케이프)."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "예" if value else "아니오"
    if isinstance(value, (list, tuple)):
        return ", ".join(_cell(v) for v in value)
    if isinstance(value, dict):
        return ", ".join(f"{k}={_cell(v)}" for k, v in value.items())
    text = str(value)
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    head = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(_cell(c) for c in r) + " |" for r in rows]
    return "\n".join([head, sep, *body])


def _kv_table(data: dict[str, Any], *, title: str | None = None) -> str:
    rows = [[k, v] for k, v in data.items()]
    out = _table(["키", "값"], rows)
    if title:
        return f"**{title}**\n\n{out}"
    return out


def _section(title: str, body: str) -> str:
    return f"### {title}\n\n{body}"


# --- artifact 정규화 ---------------------------------------------------------


def _normalize_artifact(phase: str, artifact: dict) -> dict:
    """렌더/가드 대상 dict 로 평탄화.

    - 전략 봉투 {action, strategicDiff:{...}, journeys} → strategicDiff 내부를 top-level 로 병합.
    - 스테이지 봉투 {DiscoverArtifact:{...}} → 내부 dict 로 언랩.
    """
    if not isinstance(artifact, dict):
        return {"value": artifact}
    work = dict(artifact)
    if phase == "STRATEGIC_DIFF" and isinstance(work.get("strategicDiff"), dict):
        inner = work.pop("strategicDiff")
        merged = dict(inner)
        # 봉투의 잔여 키(journeys 등)는 보존.
        for k, v in work.items():
            if k != "action":
                merged.setdefault(k, v)
        return merged
    stage_key = rc.STAGE_ARTIFACT_KEYS.get(phase)
    if stage_key and isinstance(work.get(stage_key), dict):
        return dict(work[stage_key])
    return work


# --- phase 별 렌더 함수 ------------------------------------------------------


def _render_diff_items(items: list[dict], *, title: str, cols: list[tuple[str, str]]) -> str:
    """제네릭 diff 리스트(전략 엔티티/전술 노드) 고정 컬럼 표."""
    headers = [label for label, _ in cols]
    rows = [[item.get(key) for _, key in cols] for item in items if isinstance(item, dict)]
    return _section(title, _table(headers, rows))


def _render_strategic(work: dict) -> str:
    parts: list[str] = []
    collections = [
        ("epics", "Epic", [("작업", "op"), ("제목", "entityTitle"), ("ID", "tempId")]),
        ("features", "Feature", [("작업", "op"), ("제목", "entityTitle"), ("Epic", "epicId"), ("ID", "tempId")]),
        ("userStories", "User Story", [("작업", "op"), ("제목", "entityTitle"), ("역할", "role"), ("행동", "action"), ("가치", "benefit"), ("BC", "boundedContextId")]),
        ("processes", "Process", [("작업", "op"), ("제목", "entityTitle"), ("ID", "tempId")]),
        ("journeys", "Journey", [("제목", "entityTitle"), ("ID", "tempId")]),
    ]
    for key, title, cols in collections:
        val = work.get(key)
        # 선언된 컬렉션은 비어 있어도 항상 노출(top-level 키 완전성, G2).
        if isinstance(val, list) and val:
            parts.append(_render_diff_items(val, title=f"{title} ({len(val)}건)", cols=cols))
        elif key in work:
            parts.append(_section(f"{title} (0건)", "_항목 없음_"))
    if work.get("version") is not None:
        parts.append(f"_스키마 버전({{version}}): {work.get('version')}_")
    return "\n\n".join(parts) if parts else "_전략 Diff 항목 없음_"


def _render_tactical(work: dict) -> str:
    parts: list[str] = []
    td = work.get("tacticalDiff")
    if isinstance(td, list) and td:
        cols = [("노드ID", "nodeId"), ("라벨", "nodeLabel"), ("제목", "nodeTitle"),
                ("변경", "changeType"), ("임팩트", "impactLevel")]
        parts.append(_render_diff_items(td, title=f"전술 노드 ({len(td)}건)", cols=cols))
    plan = work.get("implementationPlan")
    if isinstance(plan, dict):
        parts.append(_render_impl_plan(plan))
    return "\n\n".join(parts) if parts else "_전술 Diff 항목 없음_"


def _render_impl_plan(plan: dict) -> str:
    parts = ["### 구현 계획"]
    ad = plan.get("architectureDecisions")
    if isinstance(ad, list) and ad:
        rows = [[d.get("aspect"), d.get("decision") or d.get("choice"), d.get("rationale")]
                for d in ad if isinstance(d, dict)]
        parts.append(_table(["관점", "결정", "근거"], rows))
    gaps = plan.get("constitutionGaps")
    if isinstance(gaps, list) and gaps:
        rows = [[_cell(g)] for g in gaps]
        parts.append("**Constitution 갭**\n\n" + _table(["항목"], rows))
    if plan.get("version") is not None:
        parts.append(f"_계획 버전: {plan.get('version')}_")
    return "\n\n".join(parts)


def _render_list_of_dicts(items: list, id_field: str | None, extra_fields: list[str]) -> str:
    headers = [id_field or "값"] + extra_fields
    rows = []
    for it in items:
        if isinstance(it, dict):
            rows.append([it.get(id_field) if id_field else it] + [it.get(f) for f in extra_fields])
        else:
            rows.append([it] + ["" for _ in extra_fields])
    return _table(headers, rows)


def _render_stage(phase: str, work: dict) -> str:
    """DDD 스테이지: 각 top-level 키를 표로. 식별필드는 계약에서."""
    parts: list[str] = []
    field_hints: dict[str, list[str]] = {
        "events": ["actor", "external"],
        "hotspots": ["disposition"],
        "subDomains": ["responsibility"],
        "adjacency": ["to"],
        "classifications": ["kind", "rationale"],
        "interactions": ["from", "to", "kind", "sync"],
        "contexts": ["purpose", "classification"],
        "aggregates": ["description", "boundaryRationale"],
    }
    for key, value in work.items():
        id_field = rc.identity_field(phase, key)
        if isinstance(value, list):
            if not value:
                parts.append(_section(f"{key} (0건)", "_항목 없음_"))
            elif all(not isinstance(v, dict) for v in value):
                parts.append(_section(f"{key} ({len(value)}건)", _table(["값"], [[v] for v in value])))
            else:
                body = _render_list_of_dicts(value, id_field, field_hints.get(key, []))
                parts.append(_section(f"{key} ({len(value)}건)", body))
        elif isinstance(value, dict):
            parts.append(_section(key, _kv_table(value) if value else "_없음_"))
        else:
            parts.append(f"**{key}**: {_cell(value)}")
    return "\n\n".join(parts) if parts else "_스테이지 아티팩트 항목 없음_"


def _render_tasks(work: dict) -> str:
    tasks = work.get("tasks")
    if isinstance(tasks, list) and tasks:
        cols = [("ID", "id"), ("단계", "phase"), ("내용", "text"), ("병렬", "parallel")]
        rows = [[t.get(k) for _, k in cols] for t in tasks if isinstance(t, dict)]
        return _section(f"구현 태스크 ({len(tasks)}건)", _table([c for c, _ in cols], rows))
    return "_태스크 없음_"


def _render_test(work: dict) -> str:
    # 스칼라 top-level 키를 raw 키명으로 노출(완전성·가드 미발동).
    scalar_rows = [[k, v] for k, v in work.items() if not isinstance(v, (list, dict))]
    parts = ["**테스트 요약**\n\n" + _table(["키", "값"], scalar_rows)] if scalar_rows else []
    items = work.get("items")
    if isinstance(items, list) and items:
        cols = [("시나리오", "scenarioId"), ("분류", "category"), ("스토리", "storyTitle"),
                ("결과", "result"), ("사유", "reason")]
        rows = [[i.get(k) for _, k in cols] for i in items if isinstance(i, dict)]
        parts.append(_section(f"시나리오 ({len(items)}건)", _table([c for c, _ in cols], rows)))
    return "\n\n".join(parts)


def _render_question(payload: dict) -> str:
    text = payload.get("question") or payload.get("text") or ""
    parts = [f"{rc.EMOJI_WARN} **질문**\n\n{text}"]
    options = payload.get("options") or []
    if options:
        rows = [[idx, _cell(opt)] for idx, opt in enumerate(options)]
        parts.append(_table(["번호", "선택지"], rows))
    return "\n\n".join(parts)


def _render_violations(payload: dict) -> str:
    summary = payload.get("violationSummary") or payload.get("reason") or "검증 실패"
    parts = [f"{rc.EMOJI_WARN} **검증 오류**: {_cell(summary)}"]
    violations = payload.get("violations") or []
    if violations:
        rows = []
        for v in violations:
            if isinstance(v, dict):
                rows.append([v.get("path") or v.get("loc") or v.get("field"),
                             v.get("message") or v.get("msg") or v.get("reason")])
            else:
                rows.append(["", _cell(v)])
        parts.append(_table(["위치", "메시지"], rows))
    return "\n\n".join(parts)


_ARTIFACT_RENDERERS = {
    "STRATEGIC_DIFF": _render_strategic,
    "TACTICAL_DIFF": _render_tactical,
    "CONSTITUTION": _render_tactical,
    "TASKS": _render_tasks,
    "TEST": _render_test,
}


# --- 완전성 가드(AC-1 핵심) --------------------------------------------------


def _completeness_guard(phase: str, work: dict, rendered: str) -> str:
    """미표시 top-level 키 / 리스트 원소를 검출→강제 append(누락 0)."""
    contract = rc.REPORT_CONTRACT.get(phase.upper(), {})
    identity = contract.get("identity", {})
    missing_rows: list[list[str]] = []
    for key, value in work.items():
        if isinstance(value, list):
            # AC-1 기준: 입력 원소 개수 N == 출력 반영 개수 N. 빈 리스트(N=0)는 누락 아님.
            id_field = identity.get(key, rc.identity_field(phase, key))
            for elem in value:
                token = rc.identity_token(elem, id_field)
                if token and token not in rendered:
                    missing_rows.append([key, token])
        elif isinstance(value, dict):
            # dict 값은 구조 컨테이너 — 렌더 함수가 내용을 표로 전개하므로 키 자체는 누락 판정 제외.
            continue
        else:
            token = _cell(value)
            if key not in rendered and token not in rendered:
                missing_rows.append([key, token])
    if missing_rows:
        guard = _section(
            f"{rc.EMOJI_WARN} 누락 보정(자동 강제)",
            _table(["키", "식별값"], missing_rows),
        )
        return rendered + "\n\n" + guard
    return rendered


# --- 공개 API ----------------------------------------------------------------


def render_report(phase: str, artifact: Any, *, progress_header: str | None = None) -> str:
    """저장 artifact → 표 중심 마크다운(결정론). phase 로 렌더 함수 선택.

    phase ∈ {QUESTION, VIOLATIONS} 는 다형 렌더(clarify/validation).
    그 외는 artifact 렌더 + 완전성 가드.
    """
    norm_phase = (phase or "").upper()
    if norm_phase == "QUESTION":
        body = _render_question(artifact if isinstance(artifact, dict) else {})
    elif norm_phase == "VIOLATIONS":
        body = _render_violations(artifact if isinstance(artifact, dict) else {})
    else:
        work = _normalize_artifact(norm_phase, artifact if isinstance(artifact, dict) else {"value": artifact})
        renderer = _ARTIFACT_RENDERERS.get(norm_phase)
        if renderer is not None:
            body = renderer(work)
        elif norm_phase in rc.STAGE_ARTIFACT_KEYS:
            body = _render_stage(norm_phase, work)
        else:
            # 미등록 phase → 안전 폴백(모든 키 표 나열).
            body = _fallback_body(work)
        body = _completeness_guard(norm_phase, work, body)

    if norm_phase in rc.STAGE_ARTIFACT_KEYS:
        title = rc.stage_label(norm_phase)
    else:
        title = rc.phase_label(norm_phase)
    header = f"## 📄 {title} 보고서"
    segments = [header]
    if progress_header:
        segments.append(progress_header)
    segments.append(body)
    return "\n\n".join(segments)


def _fallback_body(work: dict) -> str:
    """미등록/비어있는 artifact 의 키 기계 나열(경량 폴백과 동형)."""
    if not work:
        return "_표시할 내용이 없습니다_"
    rows = [[k, _cell(v)] for k, v in work.items()]
    return _table(["키", "값"], rows)


def render_fallback(phase: str, artifact: Any, *, progress_header: str | None = None) -> str:
    """스킬측 경량 폴백과 동형인 서버 참조 구현(FR-5/AC-6).

    `reportMarkdown` 부재 시 스킬이 따라야 할 '모든 top-level 키를 표로 나열 + 헤더'
    규칙의 정본. 누락 0 만 보장하고 서식 품질은 포기.
    """
    work = artifact if isinstance(artifact, dict) else {"value": artifact}
    title = rc.phase_label((phase or "").upper())
    segments = [f"## 📄 {title} 보고서(폴백)"]
    if progress_header:
        segments.append(progress_header)
    segments.append(_fallback_body(work))
    return "\n\n".join(segments)
