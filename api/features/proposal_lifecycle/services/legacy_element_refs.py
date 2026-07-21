"""요소별 레거시 근거(legacyRefs) 검증 — evlink.

계약: 설계 요소(strategicDiff/tacticalDiff 의 각 항목)의 ``legacyRefs`` 는 이 Proposal 의
provenance(``p.legacyReferences`` 에 기록된 실제 검색·검토 노드)의 부분집합이어야 한다.

- 관찰집합 밖·형식 불량 nodeId → 제거하고 경고(할루시네이션 차단)
- ``legacyRefs`` 누락/비배열 → ``[]`` 로 정규화하고 경고(신규 폴백 — 조용한 실패 금지)
- 빈 배열 → 그대로 보존(정직한 "근거 없음")
- 중복 nodeId → 첫 항목만 유지

검증은 결정론 코드만 사용한다. 경고는 diff 의 ``_legacyRefWarnings`` 로 노출되어
UI/감사가 스킬 계약 위반을 볼 수 있다.
"""
from __future__ import annotations

import json
from typing import Any

_EVIDENCE_MAX = 200
_STATEMENT_MAX = 300
_ROLE_VALUES = {"derived-from", "refines", "reads", "writes", "rule", "example"}


def allowed_ref_ids(legacy_references: Any) -> set[str]:
    """provenance(v1 ``nodes``/v2 ``searchedNodes``+``inspections``)에서 관찰된 nodeId 집합.

    상세 조회가 실패(``ok: false``)한 inspection 은 관찰로 치지 않는다 — 검색에도 없던
    id 라면 스킬이 지어낸 id 일 수 있기 때문이다(검색에 있었다면 searchedNodes 로 허용됨).
    """
    if isinstance(legacy_references, str):
        try:
            legacy_references = json.loads(legacy_references)
        except ValueError:
            return set()
    allowed: set[str] = set()
    for stage in legacy_references or []:
        if not isinstance(stage, dict):
            continue
        for retrieve in stage.get("retrieves") or []:
            if not isinstance(retrieve, dict):
                continue
            nodes = retrieve.get("searchedNodes")
            if not isinstance(nodes, list):
                nodes = retrieve.get("nodes") if isinstance(retrieve.get("nodes"), list) else []
            for node in nodes:
                node_id = (node or {}).get("id") if isinstance(node, dict) else None
                if isinstance(node_id, str) and node_id:
                    allowed.add(node_id)
            for inspection in retrieve.get("inspections") or []:
                if not isinstance(inspection, dict) or inspection.get("ok") is not True:
                    continue
                node_id = inspection.get("nodeId")
                if isinstance(node_id, str) and node_id:
                    allowed.add(node_id)
    return allowed


def _normalize_one(ref: Any) -> dict | None:
    """ref 하나를 {nodeId, role?, evidence?, field?} 로 정규화. 불량이면 None."""
    if isinstance(ref, str):
        ref = {"nodeId": ref}
    if not isinstance(ref, dict):
        return None
    node_id = ref.get("nodeId") or ref.get("node_id") or ref.get("id")
    if not isinstance(node_id, str) or not node_id.strip():
        return None
    out: dict = {"nodeId": node_id.strip()}
    role = ref.get("role")
    if isinstance(role, str) and role.strip() in _ROLE_VALUES:
        out["role"] = role.strip()
    evidence = ref.get("evidence")
    if isinstance(evidence, str) and evidence.strip():
        out["evidence"] = evidence.strip()[:_EVIDENCE_MAX]
    field = ref.get("field")
    if isinstance(field, str) and field.strip():
        out["field"] = field.strip()
    # 내용 인용(content reference): LLM 은 응답에서 본 내용만 안다(내장 rule/example/table 은
    # id 가 응답에 없음). resolve_content_refs 가 그래프에서 노드 id 로 결정론 승격한다.
    rule = ref.get("rule")
    if isinstance(rule, str) and rule.strip():
        out["rule"] = rule.strip()[:_STATEMENT_MAX]
    example = ref.get("example")
    if isinstance(example, str) and example.strip():
        out["example"] = example.strip()[:_STATEMENT_MAX]
    elif isinstance(example, dict):
        out["example"] = {k: str(example.get(k) or "")[:_STATEMENT_MAX]
                          for k in ("given", "when", "then") if example.get(k)}
    table = ref.get("table")
    if isinstance(table, str) and table.strip():
        out["table"] = table.strip()[:120]
    # 이미 해석된 ref 왕복 보존(수동 편집 재저장 등): parentId 가 있으면 유지한다.
    parent = ref.get("parentId")
    if isinstance(parent, str) and parent.strip():
        out["parentId"] = parent.strip()
    statement = ref.get("statement")
    if isinstance(statement, str) and statement.strip():
        out["statement"] = statement.strip()[:_STATEMENT_MAX]
    examples = ref.get("examples")
    if isinstance(examples, list):
        out["examples"] = examples[:3]
    return out


def _element_key(element: dict, category: str, index: int) -> str:
    ident = element.get("entityId") or element.get("tempId") or element.get("nodeId") or \
        element.get("id") or element.get("entityTitle") or element.get("nodeTitle") or str(index)
    return f"{category}[{ident}]"


def _validate_element(element: dict, allowed: set[str], key: str, warnings: list[dict]) -> None:
    raw = element.get("legacyRefs")
    if raw is None or not isinstance(raw, list):
        code = "REFS_MISSING" if raw is None else "REFS_NOT_A_LIST"
        warnings.append({"element": key, "code": code})
        element["legacyRefs"] = []
        return
    cleaned: list[dict] = []
    seen: set[str] = set()
    for ref in raw:
        normalized = _normalize_one(ref)
        if normalized is None:
            warnings.append({"element": key, "code": "REF_MALFORMED",
                             "detail": json.dumps(ref, ensure_ascii=False, default=str)[:120]})
            continue
        node_id = normalized["nodeId"]
        if node_id in seen:
            continue
        # 해석된 내용 ref(rule/example/table)는 nodeId 가 내장 노드 id — 부모가 관찰집합에
        # 있으면 통과시키고, 소속 진위는 resolve_content_refs 가 그래프로 재검증한다.
        is_resolved_content = normalized.get("parentId") in allowed
        if node_id not in allowed and not is_resolved_content:
            warnings.append({"element": key, "code": "REF_NOT_OBSERVED", "nodeId": node_id})
            continue
        seen.add(node_id)
        cleaned.append(normalized)
    element["legacyRefs"] = cleaned


def validate_strategic_refs(strategic_diff: dict, allowed: set[str]) -> list[dict]:
    """strategicDiff 의 모든 카테고리 요소를 제자리 검증한다. 경고 목록을 반환."""
    warnings: list[dict] = []
    if not isinstance(strategic_diff, dict):
        return warnings
    for category, entries in strategic_diff.items():
        if category.startswith("_") or not isinstance(entries, list):
            continue
        for i, element in enumerate(entries):
            if isinstance(element, dict):
                _validate_element(element, allowed, _element_key(element, category, i), warnings)
    _attach_warnings(strategic_diff, warnings)
    return warnings


def validate_tactical_refs(tactical_diff: list, allowed: set[str]) -> list[dict]:
    """tacticalDiff(배열) 요소를 제자리 검증한다. 경고 목록을 반환.

    tacticalDiff 는 배열이라 경고를 자신에게 붙일 자리가 없다 — 호출자가 SmartLogger 와
    함께 strategicDiff 또는 별도 저장으로 표면화한다.
    """
    warnings: list[dict] = []
    if not isinstance(tactical_diff, list):
        return warnings
    for i, element in enumerate(tactical_diff):
        if isinstance(element, dict):
            _validate_element(element, allowed, _element_key(element, "tactical", i), warnings)
    return warnings


def _norm_statement(text: str) -> str:
    """규칙 문장 비교용 정규화 — 공백·따옴표 차이를 무시한다(내용은 보존)."""
    import re as _re
    return _re.sub(r"\s+", "", str(text or "")).strip("\"'“”.,")


def _iter_elements(strategic_diff: Any, tactical_diff: Any):
    if isinstance(strategic_diff, dict):
        for category, entries in strategic_diff.items():
            if category.startswith("_") or not isinstance(entries, list):
                continue
            for i, element in enumerate(entries):
                if isinstance(element, dict):
                    yield _element_key(element, category, i), element
    if isinstance(tactical_diff, list):
        for i, element in enumerate(tactical_diff):
            if isinstance(element, dict):
                yield _element_key(element, "tactical", i), element


def _match_rule(rules: list[dict], text: str) -> dict | None:
    wanted = _norm_statement(text)
    if not wanted:
        return None
    return next(
        (r for r in rules
         if _norm_statement(r.get("statement")) == wanted
         or (len(wanted) >= 8 and wanted in _norm_statement(r.get("statement")))),
        None,
    )


def _match_example(rules: list[dict], req: Any) -> tuple[dict, dict] | None:
    """req(문자열 또는 {given,when,then})와 일치하는 (rule, example)을 찾는다."""
    if isinstance(req, dict):
        wanted = _norm_statement("".join(str(req.get(k) or "") for k in ("given", "when", "then")))
    else:
        wanted = _norm_statement(req)
    if not wanted:
        return None
    for rule in rules:
        for example in rule.get("examples") or []:
            joined = _norm_statement("".join(
                str(example.get(k) or "") for k in ("given", "when", "then")))
            if joined == wanted or (len(wanted) >= 8 and wanted in joined):
                return rule, example
    return None


def _match_table(tables: list[dict], name: str) -> dict | None:
    wanted = str(name or "").strip().lower()
    if not wanted:
        return None
    short = wanted.split(".")[-1]
    return next(
        (t for t in tables
         if str(t.get("name") or "").lower() in (wanted, short)
         or str(t.get("id") or "").lower().endswith("." + short)),
        None,
    )


def resolve_content_refs(strategic_diff: Any, tactical_diff: Any, fetch_children) -> list[dict]:
    """내용 인용(rule 문장·example G/W/T·table 이름)을 실제 노드 꼬리표로 결정론 승격한다.

    LLM 은 검색/상세 응답에 내장된 rule/example/table 의 "내용"만 본다(id 없음). 여기서
    부모(관찰된 함수/노드)의 실제 자식들을 그래프에서 조회(fetch_children)해 내용을 대조하고,
    - 일치 → ref 를 해당 노드 id 로 승격(role=rule|example, table 은 db: id + 기존 role 유지)
    - 불일치(그 부모에 없는 내용) → 인용 필드 제거 + *_NOT_MATCHED 경고(부모 근거는 유지)
    - 기해석 ref 재저장(왕복) → 소속 재검증, 어긋나면 ref 제거 + *_NOT_OBSERVED
    LLM 주장이 아니라 서버의 그래프 관찰이므로 정직성 계약(N1)을 유지한다.
    """
    warnings: list[dict] = []
    for key, element in _iter_elements(strategic_diff, tactical_diff):
        refs = element.get("legacyRefs")
        if not isinstance(refs, list) or not refs:
            continue
        kept: list[dict] = []
        seen: set[str] = set()
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            rule_text = ref.pop("rule", None)
            example_req = ref.pop("example", None)
            table_name = ref.pop("table", None)
            parent_id = ref.get("parentId") or ref.get("nodeId", "")

            if rule_text or example_req:
                children = fetch_children(parent_id) or {}
                rules = children.get("rules") or []
                if example_req:
                    found = _match_example(rules, example_req)
                    if found is None:
                        warnings.append({"element": key, "code": "EXAMPLE_NOT_MATCHED",
                                         "nodeId": parent_id,
                                         "detail": json.dumps(example_req, ensure_ascii=False)[:80]})
                    else:
                        rule, example = found
                        ref.update({
                            "parentId": parent_id, "nodeId": example["id"], "role": "example",
                            "statement": str(rule.get("statement") or "")[:_STATEMENT_MAX],
                            "examples": [{k: example.get(k) for k in ("given", "when", "then")}],
                        })
                        if not ref.get("evidence"):
                            ref["evidence"] = str(example.get("when") or example.get("given") or "")[:_EVIDENCE_MAX]
                elif rule_text:
                    matched = _match_rule(rules, rule_text)
                    if matched is None:
                        warnings.append({"element": key, "code": "RULE_NOT_MATCHED",
                                         "nodeId": parent_id, "detail": str(rule_text)[:80]})
                    else:
                        statement = str(matched.get("statement") or "")
                        ref.update({
                            "parentId": parent_id, "nodeId": matched["id"], "role": "rule",
                            "statement": statement[:_STATEMENT_MAX],
                        })
                        if not ref.get("evidence"):
                            ref["evidence"] = statement[:_EVIDENCE_MAX]
                        if matched.get("examples"):
                            ref["examples"] = [
                                {k: e.get(k) for k in ("given", "when", "then")}
                                for e in matched["examples"][:3]
                            ]
            elif table_name:
                # LLM 이 테이블을 이미 직접 id 로 인용하며 table 필드를 중복 첨부하는
                # 경우(자기 자신) — 승격 불필요, 필드만 걷어내고 통과.
                self_ref = ref.get("nodeId", "")
                if _match_table([{"id": self_ref, "name": self_ref.split(".")[-1]}], table_name):
                    pass
                else:
                    children = fetch_children(parent_id) or {}
                    matched = _match_table(children.get("tables") or [], table_name)
                    if matched is None:
                        warnings.append({"element": key, "code": "TABLE_NOT_MATCHED",
                                         "nodeId": parent_id, "detail": str(table_name)[:80]})
                    else:
                        ref["parentId"] = parent_id
                        ref["nodeId"] = matched["id"]
            elif ref.get("parentId"):
                # 왕복 재검증 — 소속이 그래프에서 여전히 확인되는가
                children = fetch_children(ref["parentId"]) or {}
                child_ids = {r.get("id") for r in children.get("rules") or []}
                child_ids |= {e.get("id") for r in children.get("rules") or []
                              for e in r.get("examples") or []}
                child_ids |= {t.get("id") for t in children.get("tables") or []}
                if ref.get("nodeId") not in child_ids:
                    warnings.append({"element": key, "code": "CONTENT_NOT_OBSERVED",
                                     "nodeId": ref.get("nodeId", "")})
                    continue

            node_id = ref.get("nodeId")
            if node_id in seen:
                continue
            seen.add(node_id)
            kept.append(ref)
        element["legacyRefs"] = kept
    return warnings


def _attach_warnings(diff: dict, warnings: list[dict]) -> None:
    # 재검증 시 이전 경고를 갱신한다(누적 금지). 경고 0이면 키 자체를 제거해 잡음을 없앤다.
    if warnings:
        diff["_legacyRefWarnings"] = warnings
    else:
        diff.pop("_legacyRefWarnings", None)


def enforce_proposal_refs(
    proposal_id: str,
    strategic_diff: Any = None,
    tactical_diff: Any = None,
) -> list[dict]:
    """저장 직전 단일 진입점 — proposal 의 provenance 로 요소 legacyRefs 를 검증·정규화한다.

    LLM 생성·사용자 수동 편집 모두 이 관문을 지나야 한다(N1 완전 차단).
    diff 는 제자리(in-place) 수정되며, 떨어진 근거는 경고로 반환·로그된다.
    """
    from api.platform.neo4j import get_session
    from api.platform.observability.smart_logger import SmartLogger

    rule_cache: dict[str, list[dict]] = {}
    with get_session() as session:
        row = session.run(
            "MATCH (p:Proposal {id: $id}) RETURN p.legacyReferences AS refs",
            id=proposal_id,
        ).single()
        allowed = allowed_ref_ids((row or {}).get("refs"))

        def fetch_children(parent_id: str) -> dict:
            if parent_id not in rule_cache:
                rules = [dict(r) for r in session.run(
                    "MATCH (x {id: $id})-[:HAS_RULE]->(r:RULE) "
                    "OPTIONAL MATCH (r)-[:HAS_EXAMPLE]->(e:EXAMPLE) "
                    "WITH r, collect(CASE WHEN e IS NULL THEN NULL "
                    "  ELSE {id: e.id, given: e.given, when: e.when_, then: e.then_} END) AS exs "
                    "RETURN r.id AS id, r.statement AS statement, "
                    "  [x IN exs WHERE x IS NOT NULL] AS examples",
                    id=parent_id,
                )]
                # 부모가 직접 참조하는 TABLE + 규칙 사례가 영향(AFFECTS_TABLE)하는 TABLE
                tables = [dict(r) for r in session.run(
                    "MATCH (x {id: $id}) "
                    "OPTIONAL MATCH (x)-[]->(t1:TABLE) "
                    "OPTIONAL MATCH (x)-[:HAS_RULE]->()-[:HAS_EXAMPLE]->()-[:AFFECTS_TABLE]->(t2:TABLE) "
                    "WITH collect(DISTINCT t1) + collect(DISTINCT t2) AS ts "
                    "UNWIND ts AS t WITH DISTINCT t WHERE t IS NOT NULL "
                    "RETURN t.id AS id, t.name AS name",
                    id=parent_id,
                )]
                rule_cache[parent_id] = {"rules": rules, "tables": tables}
            return rule_cache[parent_id]

        warnings: list[dict] = []
        if isinstance(strategic_diff, dict):
            warnings += validate_strategic_refs(strategic_diff, allowed)
        if isinstance(tactical_diff, list):
            warnings += validate_tactical_refs(tactical_diff, allowed)
        content_warnings = resolve_content_refs(strategic_diff, tactical_diff, fetch_children)
        if content_warnings:
            warnings += content_warnings
            if isinstance(strategic_diff, dict):
                strategic_diff.setdefault("_legacyRefWarnings", []).extend(content_warnings)
    if warnings:
        SmartLogger.log(
            "WARN", f"legacy refs dropped/normalized: {proposal_id}",
            category="proposal_lifecycle.legacy_refs.enforced",
            params={"proposalId": proposal_id, "warnings": warnings[:20],
                    "warningCount": len(warnings), "allowedCount": len(allowed)},
        )
    return warnings


__all__ = [
    "allowed_ref_ids",
    "enforce_proposal_refs",
    "resolve_content_refs",
    "validate_strategic_refs",
    "validate_tactical_refs",
]
