"""013-report-mcda / 014-report-design — 결정론 보고서 렌더러 (순수 파이썬 포맷터).

`render_report(phase, artifact)` 가 저장 artifact 를 **요약 테이블 + 응집 카드** 중심의
마크다운으로 렌더한다. 설계 정본: `p_local/evidences/014-report-design/target-designs/`.

핵심 원칙(design-principles.md):
  - **정보 완전성(A2)**: 저장 계약의 모든 핵심 필드 표현(다치 properties·gwt·캔버스 전 필드).
  - **피라미드(A1/A4)**: 집계 헤더 + 요약 테이블 → 상세(카드/소표).
  - **밀도 규칙(B2)**: 다치 엔티티(전술 노드·US·BC/Aggregate 캔버스)=카드, 플랫 엔티티=좁은 표.
  - **트리 계층(B3)**: 요약표 첫 열 D1 전각 공백 들여쓰기(`　└`), 그래프는 컬럼/엣지.
  - **라벨 정본 + 아이콘 보조(C1)**: 아이콘 전부 제거해도 온전.
  - **완전성 가드**: top-level 식별자 + 리스트 원소 하위 필드까지 미표시 검출→강제 append.
  - **결정론(E3)**: 입력 동일 → 출력 바이트 동일(정렬·안정 순회).

신규 Neo4j 스키마 없음. 표시 계층 전용.
"""

from __future__ import annotations

from typing import Any

from api.features.proposal_lifecycle.services import report_contract_data as rc

DASH = rc.DASH
# 전각 공백(U+3000) 트리 들여쓰기(D1). depth 0/1/2 커넥터.
_INDENT = ["", "　└ ", "　　└ ", "　　　└ "]
_CIRCLED = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩",
            "⑪", "⑫", "⑬", "⑭", "⑮", "⑯", "⑰", "⑱", "⑲", "⑳"]


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


def _table(headers: list[str], rows: list[list[Any]], *, aligns: list[str] | None = None) -> str:
    head = "| " + " | ".join(headers) + " |"
    if aligns:
        sep = "| " + " | ".join(aligns) + " |"
    else:
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


def _code(value: Any) -> str:
    """백틱 코드 인라인(빈 값은 `—`)."""
    if value is None or value == "":
        return DASH
    return f"`{_cell(value)}`"


def _val(value: Any) -> str:
    """스칼라 값 표시(빈 값은 `—`, B6)."""
    if value is None or value == "":
        return DASH
    return _cell(value)


def _join_list(items: Any, *, sep: str = " · ") -> str:
    """다치 리스트를 인라인 압축(`a · b`). 빈 값은 `—`."""
    if not items:
        return DASH
    if isinstance(items, (list, tuple)):
        parts = [_cell(v) for v in items if v not in (None, "")]
        return sep.join(parts) if parts else DASH
    return _cell(items)


def _obj_inline(obj: Any) -> str:
    """객체를 `{ k: v, ... }` 인라인으로. 빈 값은 `—`."""
    if not isinstance(obj, dict) or not obj:
        return DASH
    return "{ " + ", ".join(f"{k}: {_cell(v)}" for k, v in obj.items()) + " }"


def _list(work: dict, key: str) -> list:
    val = work.get(key)
    return val if isinstance(val, list) else []


def _circled(idx: int) -> str:
    return _CIRCLED[idx] if idx < len(_CIRCLED) else f"({idx + 1})"


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
        for k, v in work.items():
            if k != "action":
                merged.setdefault(k, v)
        return merged
    # SCOPE 스테이지 플랜 봉투({stagePlan:{...}}) 언랩(015 scope-design).
    if phase == "SCOPE" and isinstance(work.get("stagePlan"), dict):
        return dict(work["stagePlan"])
    stage_key = rc.STAGE_ARTIFACT_KEYS.get(phase)
    if stage_key and isinstance(work.get(stage_key), dict):
        return dict(work[stage_key])
    return work


# --- 전략 Diff (target-01) ---------------------------------------------------


def _op_display(op: Any) -> str:
    if not op:
        return DASH
    icon = rc.OP_ICON.get(str(op).upper(), "")
    return f"{icon} {op}".strip()


def _strategic_first_col(depth: int, type_label: str, title: Any) -> str:
    icon = rc.STRATEGIC_TYPE_ICON.get(type_label, "")
    return f"{_INDENT[depth]}{icon} {type_label} · {_val(title)}".rstrip()


def _render_strategic(work: dict) -> str:
    epics = _list(work, "epics")
    features = _list(work, "features")
    stories = _list(work, "userStories")
    processes = _list(work, "processes")
    journeys = _list(work, "journeys")
    version = work.get("version")

    total = len(epics) + len(features) + len(stories) + len(processes) + len(journeys)
    op_counts: dict[str, int] = {}
    for item in (*epics, *features, *stories, *processes):
        if isinstance(item, dict) and item.get("op"):
            key = str(item["op"]).upper()
            op_counts[key] = op_counts.get(key, 0) + 1
    op_summary = " · ".join(f"{rc.OP_ICON.get(k, '')} {k} {v}".strip() for k, v in sorted(op_counts.items())) or DASH
    ver_txt = f" · 버전 v{version}" if version is not None else ""
    summary = (
        f"**요약** — Epic {len(epics)} · Feature {len(features)} · UserStory {len(stories)}"
        f" · Process {len(processes)} · Journey {len(journeys)} (총 {total}개, {op_summary}){ver_txt}"
    )

    # 요약 테이블(트리 계층: Epic→Feature→UserStory).
    rows: list[list[Any]] = []
    used_feat: set[int] = set()
    used_story: set[int] = set()

    def feat_parent(f: dict) -> str:
        return f"Epic {_code(f.get('epicId'))}" if f.get("epicId") else DASH

    def story_parent(s: dict, *, estimated: bool = False) -> str:
        bc = f"BC {_code(s.get('boundedContextId'))}" if s.get("boundedContextId") else DASH
        return f"{bc} ~추정" if estimated else bc

    for e in epics:
        if not isinstance(e, dict):
            continue
        rows.append([_strategic_first_col(0, "Epic", e.get("entityTitle")),
                     _code(e.get("tempId")), DASH, _op_display(e.get("op"))])
        for fi, f in enumerate(features):
            if not isinstance(f, dict) or fi in used_feat or f.get("epicId") != e.get("tempId"):
                continue
            used_feat.add(fi)
            rows.append([_strategic_first_col(1, "Feature", f.get("entityTitle")),
                         _code(f.get("tempId")), feat_parent(f), _op_display(f.get("op"))])
            for si, s in enumerate(stories):
                if not isinstance(s, dict) or si in used_story or s.get("featureId") != f.get("tempId"):
                    continue
                used_story.add(si)
                rows.append([_strategic_first_col(2, "UserStory", s.get("entityTitle")),
                             _code(s.get("tempId")), story_parent(s), _op_display(s.get("op"))])
    # 부모 없는 Feature(고아).
    for fi, f in enumerate(features):
        if not isinstance(f, dict) or fi in used_feat:
            continue
        used_feat.add(fi)
        rows.append([_strategic_first_col(0, "Feature", f.get("entityTitle")),
                     _code(f.get("tempId")), feat_parent(f), _op_display(f.get("op"))])
        for si, s in enumerate(stories):
            if not isinstance(s, dict) or si in used_story or s.get("featureId") != f.get("tempId"):
                continue
            used_story.add(si)
            rows.append([_strategic_first_col(1, "UserStory", s.get("entityTitle")),
                         _code(s.get("tempId")), story_parent(s), _op_display(s.get("op"))])
    # 링크 없는 UserStory(고아) — 배치 추정(E1).
    for si, s in enumerate(stories):
        if not isinstance(s, dict) or si in used_story:
            continue
        used_story.add(si)
        rows.append([_strategic_first_col(0, "UserStory", s.get("entityTitle")),
                     _code(s.get("tempId")), story_parent(s, estimated=True), _op_display(s.get("op"))])
    for p in processes:
        if isinstance(p, dict):
            rows.append([_strategic_first_col(0, "Process", p.get("entityTitle")),
                         _code(p.get("tempId")), DASH, _op_display(p.get("op"))])
    for j in journeys:
        if isinstance(j, dict):
            rows.append([_strategic_first_col(0, "Journey", j.get("entityTitle")),
                         _code(j.get("tempId")), DASH, _op_display(j.get("op"))])

    parts = [summary]
    if rows:
        parts.append(_table(["계층 · 항목", "tempId", "상위/BC", "op"], rows))
        parts.append("> 첫 열 전각 공백 들여쓰기(`　└`)로 Epic→Feature→UserStory 계층을 드러냅니다. "
                     "전각 공백이 트리밍되면 비공백 커넥터(`└─`)로 무손실 폴백. "
                     "UserStory→Feature 링크가 없으면 배치는 `~추정`.")

    # UserStory 상세 카드(다치 엔티티만 카드 — B2).
    if stories:
        cards = ["### UserStory 상세"]
        for s in stories:
            if not isinstance(s, dict):
                continue
            title = _val(s.get("entityTitle"))
            cards.append(
                f"**{title} — {_code(s.get('tempId'))}**\n"
                f"- **역할(role)**: {_val(s.get('role'))}\n"
                f"- **행동(action)**: {_val(s.get('action'))}\n"
                f"- **가치(benefit)**: {_val(s.get('benefit'))}\n"
                f"- **컨텍스트(boundedContextId)**: {_code(s.get('boundedContextId'))}"
                f" · **op**: {_val(s.get('op'))} · **version**: {_val(version)}\n\n"
                f"> {_val(s.get('role'))}(으)로서, {_val(s.get('action'))}, {_val(s.get('benefit'))}"
            )
        parts.append("\n\n".join(cards))

    return "\n\n".join(parts) if parts else "_전략 Diff 항목 없음_"


# --- 전술 Diff (target-02) ---------------------------------------------------


def _impact_display(level: Any) -> str:
    if not level:
        return DASH
    icon = rc.IMPACT_ICON.get(str(level).upper(), "")
    return f"{icon} {level}".strip()


def _node_label_display(label: Any) -> str:
    icon = rc.TACTICAL_LABEL_ICON.get(str(label), "")
    return f"{icon} {label}".strip() if label else DASH


def _node_refs(node: dict) -> list[str]:
    parts: list[str] = []
    for field in ("boundedContextId", "aggregateId", "commandId", "triggerEventId", "invokeCommandId"):
        if node.get(field):
            parts.append(f"{field} = {_code(node[field])}")
    refs = node.get("userStoryRefs")
    if isinstance(refs, list) and refs:
        parts.append("userStoryRefs = [" + ", ".join(_code(r) for r in refs) + "]")
    return parts


def _refs_summary_cell(node: dict) -> str:
    short: list[str] = []
    if node.get("boundedContextId"):
        short.append(f"bc {_code(node['boundedContextId'])}")
    if node.get("aggregateId"):
        short.append(f"agg {_code(node['aggregateId'])}")
    if node.get("commandId"):
        short.append(f"cmd {_code(node['commandId'])}")
    if node.get("triggerEventId"):
        short.append(f"evt {_code(node['triggerEventId'])}")
    if node.get("invokeCommandId"):
        short.append(f"→cmd {_code(node['invokeCommandId'])}")
    refs = node.get("userStoryRefs")
    if isinstance(refs, list) and refs:
        short.append("US " + " ".join(_code(r) for r in refs))
    return " · ".join(short) if short else DASH


def _tactical_order(nodes: list[dict]) -> list[dict]:
    """트리 순회 순서(Aggregate→Command→Event), 나머지는 저장 순서."""
    by_id = {n.get("nodeId"): n for n in nodes if isinstance(n, dict)}
    commands_by_agg: dict[Any, list[dict]] = {}
    events_by_cmd: dict[Any, list[dict]] = {}
    for n in nodes:
        if not isinstance(n, dict):
            continue
        if n.get("nodeLabel") == "Command" and n.get("aggregateId"):
            commands_by_agg.setdefault(n["aggregateId"], []).append(n)
        elif n.get("nodeLabel") == "Event" and n.get("commandId"):
            events_by_cmd.setdefault(n["commandId"], []).append(n)
    ordered: list[dict] = []
    seen: set[int] = set()

    def emit(node: dict, depth: int) -> None:
        seen.add(id(node))
        node["_depth"] = depth
        ordered.append(node)

    for n in nodes:
        if not isinstance(n, dict) or id(n) in seen:
            continue
        if n.get("nodeLabel") == "Aggregate":
            emit(n, 0)
            for cmd in commands_by_agg.get(n.get("nodeId"), []):
                if id(cmd) in seen:
                    continue
                emit(cmd, 1)
                for evt in events_by_cmd.get(cmd.get("nodeId"), []):
                    if id(evt) not in seen:
                        emit(evt, 2)
    # 트리에 안 걸린 노드(ReadModel/Policy/UI/Invariant/고아).
    for n in nodes:
        if isinstance(n, dict) and id(n) not in seen:
            emit(n, 0)
    return ordered


def _render_tactical_nodes(nodes: list[dict], *, version: Any = None) -> str:
    ordered = _tactical_order(nodes)
    label_counts: dict[str, int] = {}
    change_counts: dict[str, int] = {}
    impact_counts: dict[str, int] = {}
    for n in ordered:
        lbl = str(n.get("nodeLabel") or "")
        label_counts[lbl] = label_counts.get(lbl, 0) + 1
        if n.get("changeType"):
            ct = str(n["changeType"]).upper()
            change_counts[ct] = change_counts.get(ct, 0) + 1
        if n.get("impactLevel"):
            il = str(n["impactLevel"]).upper()
            impact_counts[il] = impact_counts.get(il, 0) + 1

    label_order = ["Aggregate", "Command", "Event", "ReadModel", "Policy", "UI", "Invariant"]
    agg_bits = []
    for lbl in label_order:
        if label_counts.get(lbl):
            agg_bits.append(f"{rc.TACTICAL_LABEL_ICON.get(lbl, '')} {lbl} {label_counts[lbl]}".strip())
    for k in sorted(change_counts):
        agg_bits.append(f"{rc.OP_ICON.get(k, '')} {k} {change_counts[k]}".strip())
    for k in ("HIGH", "MEDIUM", "LOW", "NONE"):
        if impact_counts.get(k):
            agg_bits.append(f"{rc.IMPACT_ICON.get(k, '')} {k} {impact_counts[k]}".strip())

    ver_txt = f" (버전 {version})" if version is not None else ""
    parts = [f"**전술 Diff — {len(ordered)}개 노드{ver_txt}**", "집계: " + " · ".join(agg_bits)]

    # 요약 테이블(D1 트리 계층).
    rows: list[list[Any]] = []
    for n in ordered:
        depth = n.get("_depth", 0)
        first = f"{_INDENT[depth]}{_node_label_display(n.get('nodeLabel'))} · {_val(n.get('nodeTitle'))} {_code(n.get('nodeId'))}"
        change_impact = f"{_op_display(n.get('changeType'))} · {_impact_display(n.get('impactLevel'))}"
        rows.append([first.rstrip(), change_impact, _refs_summary_cell(n)])
    parts.append(_table(["계층 · 노드", "변경 · 임팩트", "참조(ref)"], rows))
    parts.append("> 첫 열 전각 공백 들여쓰기(`　└`)로 Aggregate→Command→Event 트리를 드러냅니다. "
                 "전각 공백 트리밍 시 비공백 커넥터(`└─`)로 무손실 폴백. ReadModel 은 BC 직속 최상위.")

    # 상세 카드.
    parts.append("**상세 카드**")
    cards: list[str] = []
    for idx, n in enumerate(ordered, start=1):
        lines = [
            f"**{idx}. {_node_label_display(n.get('nodeLabel'))} · {_val(n.get('nodeTitle'))} {_code(n.get('nodeId'))}**",
            f"- 변경/임팩트: {_op_display(n.get('changeType'))} · {_impact_display(n.get('impactLevel'))}",
        ]
        refs = _node_refs(n)
        if refs:
            lines.append(f"- 참조: {' · '.join(refs)}")
        fields = n.get("fields")
        label = n.get("nodeLabel")
        if isinstance(fields, dict) and fields:
            if label == "Aggregate" and "rootEntity" in fields:
                lines.append(f"- fields: rootEntity = {_code(fields.get('rootEntity'))}")
            elif label == "Command" and "inputSchema" in fields:
                lines.append(f"- fields.inputSchema: {_obj_inline(fields.get('inputSchema'))}")
            elif label == "Event" and "payload" in fields:
                lines.append(f"- fields.payload: {_obj_inline(fields.get('payload'))}")
            else:
                lines.append(f"- fields: {_obj_inline(fields)}")
        props = n.get("properties")
        card = "\n".join(lines)
        if isinstance(props, list) and props:
            prop_rows = [[_val(p.get("name")), _val(p.get("type"))] for p in props if isinstance(p, dict)]
            card += "\n- properties\n\n  " + _table(["name", "type"], prop_rows).replace("\n", "\n  ")
        gwt = n.get("gwt")
        if isinstance(gwt, list) and gwt:
            gwt_rows = []
            for gi, sc in enumerate(gwt):
                if not isinstance(sc, dict):
                    continue
                given = _fieldvalues(sc.get("given"))
                when = _fieldvalues(sc.get("when"))
                then = _fieldvalues(sc.get("then"))
                gwt_rows.append([_circled(gi), given, when, then])
            card += (f"\n\n- GWT 시나리오 ({len(gwt_rows)}건)\n\n  "
                     + _table(["시나리오", "given.fieldValues", "when.fieldValues", "then.fieldValues"], gwt_rows).replace("\n", "\n  "))
        cards.append(card)
    parts.append("\n\n".join(cards))
    return "\n\n".join(parts)


def _fieldvalues(clause: Any) -> str:
    """GWT given/when/then 절의 fieldValues 를 `key = \\`value\\`` 로 압축."""
    if not isinstance(clause, dict):
        return DASH
    fv = clause.get("fieldValues")
    if not isinstance(fv, dict) or not fv:
        return DASH
    return " · ".join(f"{k} = {_code(v)}" for k, v in fv.items())


def _render_tactical(work: dict) -> str:
    parts: list[str] = []
    td = work.get("tacticalDiff")
    plan = work.get("implementationPlan")
    version = plan.get("version") if isinstance(plan, dict) else None
    if isinstance(td, list) and td:
        parts.append(_render_tactical_nodes(td, version=version))
    if isinstance(plan, dict) and plan:
        parts.append(_render_impl_plan_table(plan))
    return "\n\n".join(parts) if parts else "_전술 Diff 항목 없음_"


# --- 구현 계획 (target-02 압축표 / target-03 관점 섹션) ------------------------


def _render_impl_plan_table(plan: dict) -> str:
    """전술 Diff 봉투 내 implementationPlan — 압축 표(target-02)."""
    version = plan.get("version")
    ver_txt = f" · 버전 {version}" if version is not None else ""
    parts = [f"**구현 계획 (implementationPlan{ver_txt})**"]
    ad = plan.get("architectureDecisions")
    if isinstance(ad, list) and ad:
        rows = [[_val(d.get("aspect")), _val(d.get("decision") or d.get("choice")), _val(d.get("rationale"))]
                for d in ad if isinstance(d, dict)]
        parts.append(_table(["aspect", "decision", "rationale"], rows))
    gaps = plan.get("constitutionGaps")
    if isinstance(gaps, list) and gaps:
        parts.append(f"{rc.EMOJI_WARN} **Constitution Gaps**: " + " · ".join(_cell(g) for g in gaps))
    return "\n\n".join(parts)


def _render_constitution(work: dict) -> str:
    """CONSTITUTION 단계 — 관점(aspect) 그룹 섹션 + 미결 별도 섹션(target-03)."""
    parts: list[str] = []
    td = work.get("tacticalDiff")
    if isinstance(td, list) and td:
        parts.append(_render_tactical_nodes(td))
    plan = work.get("implementationPlan")
    if isinstance(plan, dict):
        parts.append(_render_impl_plan_sections(plan))
    elif isinstance(work.get("architectureDecisions"), list):
        parts.append(_render_impl_plan_sections(work))
    return "\n\n".join(parts) if parts else "_구현 계획 항목 없음_"


def _render_impl_plan_sections(plan: dict) -> str:
    version = plan.get("version")
    ad = plan.get("architectureDecisions") if isinstance(plan.get("architectureDecisions"), list) else []
    gaps = plan.get("constitutionGaps") if isinstance(plan.get("constitutionGaps"), list) else []
    n_dec = len(ad)
    n_gap = len(gaps)
    ver_txt = f"v{version}" if version is not None else "v-"
    gap_txt = f"{rc.EMOJI_WARN} **미결 {n_gap}건**" if n_gap else "**미결 없음**"

    tail = " 확정 전 확인이 필요한 미결 사항은 문서 하단에 있습니다." if n_gap else ""
    parts = [f"**📐 구현계획 (Constitution) · {ver_txt}**",
             f"총 **결정 {n_dec}건** · {gap_txt} · 버전 {ver_txt} — "
             "승인된 전술 설계를 구현하기 위한 아키텍처 결정을 관점별로 정리했습니다." + tail]

    for d in ad:
        if not isinstance(d, dict):
            continue
        aspect = d.get("aspect")
        icon = rc.aspect_icon(aspect)
        head = f"**{icon} {_val(aspect)}**" if icon else f"**{_val(aspect)}**"
        parts.append(
            f"{head}\n"
            f"- **결정**: {_val(d.get('decision') or d.get('choice'))}\n"
            f"- **근거**: {_val(d.get('rationale'))}"
        )

    if n_gap:
        gap_lines = [f"**{rc.EMOJI_WARN} 미결 사항 (constitutionGaps · {n_gap}건)**",
                     "승인 전 결정이 필요한 항목입니다. 미해결 상태로 승인 시 이후 태스크·구현 단계에 리스크로 전달됩니다."]
        gap_lines.extend(f"- {_cell(g)}" for g in gaps)
        parts.append("\n".join([gap_lines[0], "", gap_lines[1], "", *gap_lines[2:]]))
    else:
        parts.append(f"**미결 사항 (constitutionGaps)**\n\n미결 없음")
    return "\n\n".join(parts)


# --- 태스크 (target-04) ------------------------------------------------------


def _render_tasks(work: dict) -> str:
    tasks = work.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        return "_태스크 없음_"
    # phase 를 첫 등장 순서로 그룹(태스크는 이미 의존 순서로 정렬됨).
    phase_order: list[str] = []
    groups: dict[str, list[dict]] = {}
    parallel_total = 0
    for t in tasks:
        if not isinstance(t, dict):
            continue
        ph = str(t.get("phase") or "(단계 미지정)")
        if ph not in groups:
            groups[ph] = []
            phase_order.append(ph)
        groups[ph].append(t)
        if t.get("parallel"):
            parallel_total += 1

    counts = " · ".join(f"{ph} {len(groups[ph])}" for ph in phase_order)
    header = (f"**🛠️ 구현 태스크 · 총 {len(tasks)}건 · {counts} · ⚡ 병렬 {parallel_total}**")
    order_line = "실행 순서: **" + " → ".join(phase_order) + "**"

    rows: list[list[str]] = []
    for ph in phase_order:
        has_parallel = any(t.get("parallel") for t in groups[ph])
        group_label = f"**{ph}**" + (" ⚡" if has_parallel else "")
        rows.append([group_label, DASH, DASH])
        for t in groups[ph]:
            par = "⚡ 병렬" if t.get("parallel") else "순차"
            rows.append([f"{_INDENT[1]}{_code(t.get('id'))}", par, _val(t.get("text"))])

    table = _table(["계층 · id", "병렬", "태스크(text)"], rows, aligns=["---", ":---:", "---"])
    note = ("> ⚡ 병렬 = 같은 단계 내 다른 태스크와 병렬 실행 가능 · 순차 = 단독 진행\n"
            "> 들여쓰기 전각 공백(`　└`)이 트리밍되면 비공백 커넥터(`└─`)로 무손실 폴백")
    return "\n\n".join([header, order_line, table, note])


# --- 테스트/리뷰 (target-05) -------------------------------------------------


def _result_display(result: Any) -> str:
    key = str(result or "").upper()
    icon = rc.TEST_RESULT_ICON.get(key, "")
    if key in ("FAIL", "SKIP"):
        return f"{icon} **{key}**".strip()
    return f"{icon} {key}".strip() if key else DASH


def _render_test(work: dict) -> str:
    total = work.get("totalScenarios")
    passed = work.get("passed")
    failed = work.get("failed")
    skipped = work.get("skipped")
    items = work.get("items") if isinstance(work.get("items"), list) else []
    if total is None:
        total = len(items)

    header = (f"**🧪 테스트 결과 · 총 {_val(total)} · ✅ PASS {_val(passed)}"
              f" · ❌ FAIL {_val(failed)} · ⏭️ SKIP {_val(skipped)}**")

    order_key = {"FAIL": 0, "SKIP": 1, "PASS": 2}
    indexed = list(enumerate(i for i in items if isinstance(i, dict)))
    ordered = sorted(indexed, key=lambda pair: (order_key.get(str(pair[1].get("result") or "").upper(), 3), pair[0]))

    rows = []
    for _, it in ordered:
        rows.append([
            _result_display(it.get("result")),
            _code(it.get("scenarioId")),
            _val(it.get("category")),
            _val(it.get("storyTitle")),
            _val(it.get("reason")),
        ])
    parts = [header]
    if rows:
        parts.append(_table(["결과", "시나리오(scenarioId)", "분류", "스토리(storyTitle)", "사유(reason)"], rows))
        parts.append("> 실패/스킵을 상단에 정렬(주의 필요 결론 먼저). FAIL/SKIP 은 볼드, PASS 는 일반체.")
    return "\n\n".join(parts)


# --- SCOPE 스테이지 플랜 (015 scope-design, 스타일 B: 전략/전술 2단 트리) --------

# 파이프라인 2단 그룹(전략 DDD 3 / 전술 DDD 3) + 그룹 설명. 실행 순서 고정.
_SCOPE_GROUPS = [
    ("전략 DDD", ["DISCOVER", "DECOMPOSE", "STRATEGIZE"], "도메인 발견·분해·전략 분류"),
    ("전술 DDD", ["CONNECT", "DEFINE", "TACTICAL"], "연동·컨텍스트·애그리거트 설계"),
]
# 스테이지 보조 아이콘(C1 — 라벨 정본, 아이콘 보조).
_STAGE_ICON = {
    "DISCOVER": "📣", "DECOMPOSE": "🧩", "STRATEGIZE": "⭐",
    "CONNECT": "🔗", "DEFINE": "📦", "TACTICAL": "🧱",
}


def _scope_status(stage: dict) -> str:
    """스테이지 상태 라벨(정본) — 확정 생략 > 미적용 > 적용."""
    if stage.get("skipped"):
        return "⛔ 생략확정"
    if stage.get("applies", True) is False:
        return "⏸ 미적용"
    return "▶ 적용"


def _render_scope(work: dict) -> str:
    """SCOPE 스테이지 플랜 — 전략/전술 2단 그룹 트리(D1 들여쓰기). scope-design.md 스타일 B."""
    version = work.get("version")
    reach = work.get("classifiedReach")
    stages = work.get("stages") if isinstance(work.get("stages"), list) else []
    by_stage: dict[str, dict] = {}
    for s in stages:
        if isinstance(s, dict) and s.get("stage"):
            by_stage[str(s["stage"]).upper()] = s

    n_apply = sum(1 for s in stages if isinstance(s, dict) and s.get("applies", True) and not s.get("skipped"))
    n_reco = sum(1 for s in stages if isinstance(s, dict) and s.get("recommendSkip"))
    n_skip = sum(1 for s in stages if isinstance(s, dict) and s.get("skipped"))
    ver_txt = f" · 버전 v{version}" if version is not None else ""
    header = (f"**🗺️ 스테이지 플랜 · {len(stages)} 스테이지 · ▶ 적용 {n_apply}"
              f" · ⏭️ 생략권장 {n_reco} · ⛔ 생략확정 {n_skip} · 전략 3 / 전술 3{ver_txt}**")
    parts = [header]
    if reach:
        parts.append(f"**스코프 분류(classifiedReach):** {_cell(reach)}")

    rows: list[list[str]] = []
    for group_label, group_stages, group_desc in _SCOPE_GROUPS:
        present = [st for st in group_stages if st in by_stage]
        rows.append([f"**{group_label}** ({len(present)})", DASH, DASH, group_desc])
        for st in group_stages:
            s = by_stage.get(st)
            if not s:
                continue
            icon = _STAGE_ICON.get(st, "")
            reco = "⏭️ 권장" if s.get("recommendSkip") else DASH
            rows.append([f"{_INDENT[1]}{icon} {rc.stage_label(st)}".rstrip(),
                         _scope_status(s), reco, _val(s.get("reason"))])
    # 계약 외 stage 방어(누락 0) — 최상위로 추가.
    known = {st for _, gs, _ in _SCOPE_GROUPS for st in gs}
    for st, s in by_stage.items():
        if st not in known:
            reco = "⏭️ 권장" if s.get("recommendSkip") else DASH
            rows.append([f"{_val(st)}", _scope_status(s), reco, _val(s.get("reason"))])

    parts.append(_table(["계층 · 스테이지", "상태", "생략 권장", "사유(reason)"], rows,
                        aligns=["---", "---", ":---:", "---"]))
    parts.append("> 첫 열 전각 공백 들여쓰기(`　└`)로 전략 DDD → 전술 DDD 2단 구조를 드러냅니다. "
                 "전각 공백 트리밍 시 비공백 커넥터(`└─`)로 무손실 폴백. 실행 순서는 고정(재정렬 없음). "
                 "⏭️ 생략 권장 = 스킬 제안(미확정) · ⛔ 생략확정 = 아키텍트 확정.")
    return "\n\n".join(parts)


# --- DDD Discover (target-06) ------------------------------------------------


def _render_discover(work: dict) -> str:
    events = _list(work, "events")
    pivotal = _list(work, "pivotalEvents")
    hotspots = _list(work, "hotspots")
    pivotal_names = {str(p) for p in pivotal}

    n_internal = sum(1 for e in events if isinstance(e, dict) and not e.get("external"))
    n_external = sum(1 for e in events if isinstance(e, dict) and e.get("external"))
    n_unresolved = sum(1 for h in hotspots if isinstance(h, dict) and str(h.get("disposition") or "").lower() == "question")

    header = ("**📣 DDD Discover — 도메인 이벤트 발견**\n\n"
              f"총 {len(events)}개 이벤트 · 🏠 내부 {n_internal} · 🌐 외부 {n_external}"
              f" · ⭐ 피벗 {len(pivotal)} · 🔥 핫스팟 {len(hotspots)}(미해결 {n_unresolved})")
    parts = [header, "**이벤트 스파인**"]

    rows = []
    for e in events:
        if not isinstance(e, dict):
            continue
        ext = "🌐 외부" if e.get("external") else "🏠 내부"
        pivot = "⭐ 피벗" if e.get("name") in pivotal_names else DASH
        rows.append([_val(e.get("name")), _val(e.get("actor")), ext, pivot])
    parts.append(_table(["📣 이벤트", "행위자(actor)", "내부/외부", "피벗"], rows))

    if pivotal:
        prows = [[_cell(p), "(미지정)"] for p in pivotal]
        parts.append("**⭐ 피벗 이벤트 (흐름의 축)**\n\n" + _table(["이벤트", "의미"], prows))

    if hotspots:
        hrows = []
        for h in hotspots:
            if not isinstance(h, dict):
                continue
            disp = h.get("disposition")
            disp_disp = f"❓ {disp}" if str(disp or "").lower() == "question" else _val(disp)
            hrows.append([_val(h.get("text")), disp_disp])
        parts.append("**🔥 핫스팟 (미해결 논점)**\n\n" + _table(["논점(text)", "처리(disposition)"], hrows))

    if n_external:
        parts.append("> 🌐 외부 이벤트는 다른 시스템이 발생시키므로 통합 계약·재시도 정책 설계가 필요합니다.")
    return "\n\n".join(parts)


# --- DDD Decompose (target-07) -----------------------------------------------


def _coupling_for_edge(frm: Any, to: Any, coupling_notes: list) -> tuple[str, str]:
    """엣지(from→to)에 대응하는 (sync 표시, 매칭 노트). couplingNotes 텍스트 스캔."""
    for note in coupling_notes:
        text = str(note)
        if to and str(to) in text and (not frm or str(frm) in text):
            low = text.lower()
            if any(k in text for k in ("비동기",)) or "async" in low or "이벤트" in text:
                return "📨 비동기", text
            if "동기" in text or "sync" in low:
                return "🔒 동기", text
            return "", text
    return "", ""


def _decompose_is_tree(nodes: list[str], edges: list[tuple[str, str]]) -> bool:
    """acyclic + 각 노드 in-degree ≤ 1 이면 트리(포레스트 허용)로 렌더."""
    indeg: dict[str, int] = {n: 0 for n in nodes}
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    for a, b in edges:
        if a in adj and b in indeg:
            adj[a].append(b)
            indeg[b] += 1
    if any(v > 1 for v in indeg.values()):
        return False
    # cycle 검출(DFS).
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in nodes}

    def has_cycle(u: str) -> bool:
        color[u] = GRAY
        for v in adj.get(u, []):
            if color.get(v) == GRAY:
                return True
            if color.get(v) == WHITE and has_cycle(v):
                return True
        color[u] = BLACK
        return False

    return not any(color[n] == WHITE and has_cycle(n) for n in nodes)


def _render_decompose(work: dict) -> str:
    subs = _list(work, "subDomains")
    adjacency = _list(work, "adjacency")
    coupling_notes = _list(work, "couplingNotes")
    resp_by_name = {s.get("name"): s.get("responsibility") for s in subs if isinstance(s, dict)}
    names = [s.get("name") for s in subs if isinstance(s, dict)]
    edges = [(a.get("from"), a.get("to")) for a in adjacency if isinstance(a, dict)]

    n_sync = 0
    n_async = 0
    edge_coupling: dict[tuple, tuple[str, str]] = {}
    for frm, to in edges:
        sync_disp, note = _coupling_for_edge(frm, to, coupling_notes)
        edge_coupling[(frm, to)] = (sync_disp, note)
        if sync_disp.startswith("🔒"):
            n_sync += 1
        elif sync_disp.startswith("📨"):
            n_async += 1

    header = (f"**📍 DDD Decompose — 서브도메인 {len(subs)} · ➡️ 엣지 {len(edges)}"
              f" · 🔒 동기 {n_sync} · 📨 비동기 {n_async}**")

    if _decompose_is_tree(names, edges):
        parts = [header]
        parent: dict[Any, Any] = {}
        children: dict[Any, list[Any]] = {n: [] for n in names}
        for frm, to in edges:
            parent[to] = frm
            children.setdefault(frm, []).append(to)
        roots = [n for n in names if n not in parent]
        rows: list[list[str]] = []
        visited: set = set()

        def walk(node: Any, depth: int) -> None:
            if node in visited:
                return
            visited.add(node)
            if node in parent:
                sync_disp, note = edge_coupling.get((parent[node], node), ("", ""))
                flow = f"{parent[node]} → {node}"
                detail = f"{sync_disp} ({flow}{', ' + note if note else ''})".strip()
                coupling = detail if sync_disp or note else f"— ({flow})"
            else:
                coupling = "— (진입점)"
            rows.append([f"{_INDENT[depth]}🧱 {_val(node)}".rstrip(),
                         _val(resp_by_name.get(node)), coupling])
            for child in children.get(node, []):
                walk(child, depth + 1)

        for r in roots:
            walk(r, 0)
        for n in names:  # 고아(비연결) 방어.
            if n not in visited:
                walk(n, 0)
        parts.append(_table(["의존 흐름 · 서브도메인", "책임(responsibility)", "이 엣지의 결합"], rows))
        parts.append("> 첫 열 전각 공백 들여쓰기(`　└`)로 의존 흐름을 진입점부터 폅니다. "
                     "전각 공백 트리밍 시 비공백 커넥터(`└─`)로 무손실 폴백.")
        return "\n\n".join(parts)

    # 폴백: E3 엣지 리스트(순환·다부모).
    parts = [header, "**🧱 책임 요약**"]
    resp_rows = [[_val(s.get("name")), _val(s.get("responsibility"))] for s in subs if isinstance(s, dict)]
    parts.append(_table(["서브도메인", "책임(responsibility)"], resp_rows))
    parts.append("**➡️ 의존 엣지**")
    edge_rows = []
    for i, (frm, to) in enumerate(edges, start=1):
        sync_disp, note = edge_coupling.get((frm, to), ("", ""))
        edge_rows.append([str(i), f"🧱 {_val(frm)}", "➡️", f"🧱 {_val(to)}",
                          sync_disp or DASH, _val(note)])
    parts.append(_table(["#", "from", "→", "to", "결합", "노트"], edge_rows))
    parts.append("> 모든 엣지가 명시적 1급 행(유실 0·왜곡 0). 순환·다부모·다중 진입 그래프를 담습니다.")
    return "\n\n".join(parts)


# --- DDD Strategize (target-08) ----------------------------------------------


def _render_strategize(work: dict) -> str:
    classifications = _list(work, "classifications")
    order = {"CORE": 0, "SUPPORTING": 1, "GENERIC": 2}
    indexed = list(enumerate(c for c in classifications if isinstance(c, dict)))
    ordered = sorted(indexed, key=lambda pair: (order.get(str(pair[1].get("kind") or "").upper(), 3), pair[0]))

    counts: dict[str, int] = {}
    for c in classifications:
        if isinstance(c, dict):
            k = str(c.get("kind") or "").upper()
            counts[k] = counts.get(k, 0) + 1
    header = ("**📍 DDD Strategize — 서브도메인 전략 분류**\n\n"
              f"**분류 요약:** 총 {len(classifications)} · ⭐ Core {counts.get('CORE', 0)}"
              f" · 🧩 Supporting {counts.get('SUPPORTING', 0)} · ⚙️ Generic {counts.get('GENERIC', 0)}\n"
              "투자·구현 우선순위는 Core 부터 낮아집니다.")

    rows = []
    for _, c in ordered:
        key = str(c.get("kind") or "").upper()
        icon = rc.CLASSIFICATION_ICON.get(key, "")
        label = rc.CLASSIFICATION_LABEL.get(key, c.get("kind"))
        label_cell = f"{icon} **{label}**" if key == "CORE" else f"{icon} {label}".strip()
        rows.append([label_cell, _val(c.get("subDomain")), _val(c.get("rationale"))])
    parts = [header, _table(["분류", "서브도메인", "분류 근거"], rows),
             "> 첫 열이 분류 스파인입니다. 행 순서 = 투자 우선순위(Core → Supporting → Generic)."]
    return "\n\n".join(parts)


# --- DDD Connect (target-09) -------------------------------------------------


def _kind_display(kind: Any) -> str:
    key = str(kind or "").upper()
    icon = rc.KIND_ICON.get(key, "")
    label = "Command" if key == "COMMAND" else "Event" if key == "EVENT" else kind
    return f"{icon} {label}".strip() if label else DASH


def _render_connect(work: dict) -> str:
    interactions = _list(work, "interactions")
    warnings = _list(work, "couplingWarnings")
    channel = work.get("messagingChannel")

    n_sync = sum(1 for i in interactions if isinstance(i, dict) and i.get("sync"))
    n_async = sum(1 for i in interactions if isinstance(i, dict) and not i.get("sync"))
    froms: list[Any] = []
    for i in interactions:
        if isinstance(i, dict) and i.get("from") not in froms:
            froms.append(i.get("from"))

    header = (f"**🔗 DDD Connect — 상호작용 {len(interactions)} · 📦 from {len(froms)}"
              f" · 🔒 동기 {n_sync} · 📨 비동기 {n_async}**")

    def warned(i: dict) -> bool:
        frm, to = str(i.get("from") or ""), str(i.get("to") or "")
        msg = str(i.get("message") or "")
        is_sync = bool(i.get("sync"))
        for w in warnings:
            wt = str(w)
            if msg and msg in wt:
                return True
            if (frm and frm in wt) and (to and to in wt):
                # 경고가 동기/비동기를 명시하면 이 엣지의 sync 와 일치할 때만 표식
                # (같은 from→to 를 공유하는 반대 결합 엣지 오표식 방지).
                # '동기'⊂'비동기', 'sync'⊂'async' 부분문자열 겹침을 제거하고 판정.
                wl = wt.lower()
                mentions_async = ("비동기" in wt) or ("async" in wl)
                mentions_sync = ("동기" in wt.replace("비동기", "")) or ("sync" in wl.replace("async", ""))
                if mentions_async and not mentions_sync:
                    if not is_sync:
                        return True
                elif mentions_sync and not mentions_async:
                    if is_sync:
                        return True
                else:
                    return True
        return False

    rows: list[list[str]] = []
    for frm in froms:
        group = [i for i in interactions if isinstance(i, dict) and i.get("from") == frm]
        rows.append([f"📦 {_val(frm)} (from) · {len(group)}건", "", ""])
        for is_sync, sync_label in ((True, "🔒 동기 요청"), (False, "📨 비동기 요청")):
            sub = [i for i in group if bool(i.get("sync")) == is_sync]
            if not sub:
                continue
            rows.append([f"{_INDENT[1]}{sync_label} · {len(sub)}건", "", ""])
            for i in sub:
                msg = _val(i.get("message"))
                if warned(i):
                    msg = f"{msg} {rc.EMOJI_WARN}"
                rows.append([f"{_INDENT[2]}{msg}", _kind_display(i.get("kind")), f"→ 📦 {_val(i.get('to'))}"])

    parts = [header, _table(["from · 결합 · 메시지", "종류", "→ to"], rows),
             "> 첫 열 전각 공백 들여쓰기(`　└`)로 from→결합→메시지 2단 그룹을 폅니다. "
             "⚠️ 는 경고가 걸린 엣지에 인라인 표식."]
    if warnings:
        warn_lines = [f"**{rc.EMOJI_WARN} 결합 경고(couplingWarnings)**"]
        warn_lines.extend(f"- {_cell(w)}" for w in warnings)
        parts.append("\n".join([warn_lines[0], "", *warn_lines[1:]]))
    if channel:
        parts.append(f"> 메시징 채널(messagingChannel): {_cell(channel)}")
    return "\n\n".join(parts)


# --- DDD Define — Bounded Context Canvas (target-10) -------------------------


def _collab_table(context: dict, name: Any) -> str | None:
    inbound = context.get("inbound") if isinstance(context.get("inbound"), list) else []
    outbound = context.get("outbound") if isinstance(context.get("outbound"), list) else []
    if not inbound and not outbound:
        return None
    rows = []
    for c in inbound:
        if isinstance(c, dict):
            rows.append(["수신", f"{_val(c.get('collaborator'))} → **{_val(name)}**",
                         _val(c.get("message")), _val(c.get("type"))])
    for c in outbound:
        if isinstance(c, dict):
            rows.append(["발신", f"**{_val(name)}** → {_val(c.get('collaborator'))}",
                         _val(c.get("message")), _val(c.get("type"))])
    return "**🔗 협업**\n\n" + _table(["방향", "흐름", "메시지", "유형"], rows)


def _render_define(work: dict) -> str:
    contexts = _list(work, "contexts")
    order = {"CORE": 0, "SUPPORTING": 1, "GENERIC": 2}
    indexed = list(enumerate(c for c in contexts if isinstance(c, dict)))
    ordered = sorted(indexed, key=lambda pair: (order.get(str(pair[1].get("classification") or "").upper(), 3), pair[0]))

    counts: dict[str, int] = {}
    for c in contexts:
        if isinstance(c, dict):
            k = str(c.get("classification") or "").upper()
            counts[k] = counts.get(k, 0) + 1
    header = (f"**📦 DDD Define — Bounded Context {len(contexts)} · ⭐ CORE {counts.get('CORE', 0)}"
              f" · 🧩 SUPPORTING {counts.get('SUPPORTING', 0)} · ⚙️ GENERIC {counts.get('GENERIC', 0)}**")

    srows = []
    for _, c in ordered:
        inbound = c.get("inbound") if isinstance(c.get("inbound"), list) else []
        outbound = c.get("outbound") if isinstance(c.get("outbound"), list) else []
        ul = c.get("ubiquitousLanguage") if isinstance(c.get("ubiquitousLanguage"), list) else []
        srows.append([f"📦 {_val(c.get('name'))}", rc.classification_display(c.get("classification")),
                      _val(c.get("purpose")), f"{len(inbound)} / {len(outbound)}", str(len(ul))])
    parts = [header, _table(["Bounded Context", "분류", "목적", "협업(in/out)", "언어(용어)"], srows)]

    for _, c in ordered:
        name = c.get("name")
        parts.append(f"**📦 {_val(name)} — {rc.classification_display(c.get('classification'))}**")
        ident = [
            f"- **목적**: {_val(c.get('purpose'))}",
            f"- **분류/모델/진화/역할**: {_val(c.get('classification'))} · {_join_list(c.get('businessModel'))}"
            f" · {_val(c.get('evolution'))} · {_join_list(c.get('domainRoles'))}",
            f"- **의사결정**: {_join_list(c.get('businessDecisions'))}",
            f"- **가정**: {_join_list(c.get('assumptions'))}",
            f"- **검증 지표**: {_join_list(c.get('verificationMetrics'))}",
            f"- **미해결 질문**: {_join_list(c.get('openQuestions'))}",
            f"- **언어 충돌**: {_join_list(c.get('languageClashes'))}",
        ]
        parts.append("\n".join(ident))
        collab = _collab_table(c, name)
        if collab:
            parts.append(collab)
        else:
            parts.append("- **협업**: — (없음)")
        ul = c.get("ubiquitousLanguage") if isinstance(c.get("ubiquitousLanguage"), list) else []
        if ul:
            urows = [[_val(t.get("term")), _val(t.get("definition"))] for t in ul if isinstance(t, dict)]
            parts.append(f"**🗣️ 유비쿼터스 언어 ({len(ul)})**\n\n" + _table(["용어", "정의"], urows))
    return "\n\n".join(parts)


# --- DDD Tactical — Aggregate Design Canvas (target-11) ----------------------


def _facet_rows(facet: Any, specs: list[tuple[str, str]]) -> list[list[str]]:
    rows = []
    if not isinstance(facet, dict):
        return rows
    for key, label in specs:
        entry = facet.get(key)
        if isinstance(entry, dict):
            rows.append([label, _val(entry.get("avg")), _val(entry.get("max"))])
        elif entry not in (None, ""):
            rows.append([label, _val(entry), DASH])
    return rows


def _render_tactical_stage(work: dict) -> str:
    aggs = _list(work, "aggregates")
    names = [a.get("name") for a in aggs if isinstance(a, dict)]
    names_txt = " · ".join(_cell(n) for n in names) if names else DASH
    header = f"**🧩 DDD Tactical — Aggregate {len(aggs)} ({names_txt})**"

    srows = []
    for a in aggs:
        if not isinstance(a, dict):
            continue
        hc = a.get("handledCommands") if isinstance(a.get("handledCommands"), list) else []
        ce = a.get("createdEvents") if isinstance(a.get("createdEvents"), list) else []
        inv = a.get("invariants") if isinstance(a.get("invariants"), list) else []
        srows.append([f"🧩 {_val(a.get('name'))}", _val(a.get("description")),
                      f"{len(hc)} / {len(ce)}", str(len(inv)), _val(a.get("boundaryRationale"))])
    parts = [header, _table(["애그리거트", "설명", "커맨드/이벤트", "불변식", "경계 근거"], srows)]

    for a in aggs:
        if not isinstance(a, dict):
            continue
        parts.append(f"**🧩 {_val(a.get('name'))}**")
        ident = [
            f"- **설명**: {_val(a.get('description'))}",
            f"- **경계 근거**: {_val(a.get('boundaryRationale'))}",
            f"- **⚙️ 처리 커맨드**: {_join_list(a.get('handledCommands'))}",
            f"- **⚙️ 생성 이벤트**: {_join_list(a.get('createdEvents'))}",
            f"- **🔒 불변식**: {_join_list(a.get('invariants'))}",
            f"- **🛡️ 보정 정책**: {_join_list(a.get('correctivePolicies'))}",
        ]
        parts.append("\n".join(ident))
        transitions = a.get("stateTransitions") if isinstance(a.get("stateTransitions"), list) else []
        if transitions:
            trows = [[_val(t.get("from")), _val(t.get("to")), _val(t.get("trigger"))]
                     for t in transitions if isinstance(t, dict)]
            parts.append("**🔄 상태 전이**\n\n" + _table(["from", "→ to", "trigger"], trows))
        char_rows = _facet_rows(a.get("throughput"), [
            ("commandHandlingRate", "커맨드 처리율(commandHandlingRate)"),
            ("totalClients", "총 클라이언트(totalClients)"),
            ("concurrencyConflictChance", "동시성 충돌(concurrencyConflictChance)"),
        ]) + _facet_rows(a.get("size"), [
            ("eventGrowthRate", "이벤트 증가율(eventGrowthRate)"),
            ("lifetime", "수명(lifetime)"),
            ("eventsPersisted", "누적 이벤트(eventsPersisted)"),
        ])
        if char_rows:
            parts.append("**📊 특성 (avg · max)**\n\n" + _table(["지표", "avg", "max"], char_rows))
    return "\n\n".join(parts)


# --- 다형 렌더(clarify / validation) ----------------------------------------


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
    "SCOPE": _render_scope,
    "STRATEGIC_DIFF": _render_strategic,
    "TACTICAL_DIFF": _render_tactical,
    "CONSTITUTION": _render_constitution,
    "TASKS": _render_tasks,
    "TEST": _render_test,
}

_STAGE_RENDERERS = {
    "DISCOVER": _render_discover,
    "DECOMPOSE": _render_decompose,
    "STRATEGIZE": _render_strategize,
    "CONNECT": _render_connect,
    "DEFINE": _render_define,
    "TACTICAL": _render_tactical_stage,
}


# --- 완전성 가드(AC-1 핵심) --------------------------------------------------


# 보고서 본문에 노출하지 않아도 되는 순수 식별/버전 메타 스칼라 키(가드 제외).
_GUARD_EXEMPT_SCALAR = {"proposalId", "id", "action", "schemaVersion", "skillVersion"}


def _completeness_guard(phase: str, work: dict, rendered: str) -> str:
    """미표시 top-level 키·리스트 원소·**하위 필드**를 검출→강제 append(누락 0)."""
    contract = rc.REPORT_CONTRACT.get(phase.upper(), {})
    identity = contract.get("identity", {})
    missing_rows: list[list[str]] = []
    for key, value in work.items():
        if isinstance(value, list):
            id_field = identity.get(key, rc.identity_field(phase, key))
            deep = rc.deep_fields(phase, key)
            for elem in value:
                token = rc.identity_token(elem, id_field)
                if token and token not in rendered:
                    missing_rows.append([key, token])
                # 하위 필드 유실 검출(014 심화).
                if deep and isinstance(elem, dict):
                    elem_id = rc.identity_token(elem, id_field) or "?"
                    for sub in deep:
                        for tok in rc.flatten_tokens(elem.get(sub)):
                            if tok not in rendered:
                                missing_rows.append([f"{key}.{sub}", f"{elem_id}: {tok}"])
        elif isinstance(value, dict):
            continue
        elif key in _GUARD_EXEMPT_SCALAR:
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
    """저장 artifact → 요약 테이블 + 카드 중심 마크다운(결정론). phase 로 렌더 함수 선택.

    phase ∈ {QUESTION, VIOLATIONS} 는 다형 렌더(clarify/validation).
    그 외는 artifact 렌더 + 완전성 가드.
    """
    norm_phase = (phase or "").upper()
    if norm_phase == "QUESTION":
        body = _render_question(artifact if isinstance(artifact, dict) else {})
    elif norm_phase == "VIOLATIONS":
        body = _render_violations(artifact if isinstance(artifact, dict) else {})
    else:
        # 015-report-issue: DDD 스테이지 초안이 상위 phase(STRATEGIC_DDD/TACTICAL_DDD)로
        # 들어오면 어느 렌더러에도 매칭되지 않아 폴백(키-값 테이블)으로 강등된다. artifact
        # 봉투 키(DiscoverArtifact→DISCOVER)로 유효 스테이지를 복원해 렌더러를 선택한다.
        if norm_phase not in _ARTIFACT_RENDERERS and norm_phase not in _STAGE_RENDERERS:
            inferred_stage = rc.stage_from_envelope(artifact)
            if inferred_stage:
                norm_phase = inferred_stage
        work = _normalize_artifact(norm_phase, artifact if isinstance(artifact, dict) else {"value": artifact})
        renderer = _ARTIFACT_RENDERERS.get(norm_phase) or _STAGE_RENDERERS.get(norm_phase)
        if renderer is not None:
            body = renderer(work)
        else:
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
