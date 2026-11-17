"""Proposal provenance -> bounded, deduplicated LLM evidence packet.

The packet only transports evidence that an earlier stage actually inspected.  It does
not infer ownership or business meaning.  Later semantic stages may use it instead of
repeating identical MCP detail calls, while the original ``legacyReferences`` remains
the audit log of every real tool call.
"""
from __future__ import annotations

import json
import re
from typing import Any

from api.platform.neo4j import get_session


def _parse_refs(raw: Any) -> list[dict]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return []
    return [stage for stage in (raw or []) if isinstance(stage, dict)]


def _inspection_score(item: dict) -> tuple[int, int, int, int]:
    frame = item.get("semanticFrame") if isinstance(item.get("semanticFrame"), dict) else {}
    profile = frame.get("profile") if isinstance(frame.get("profile"), dict) else {}
    linked = item.get("linkedContext") if isinstance(item.get("linkedContext"), dict) else {}
    return (
        len(frame.get("slots") or {}),
        len(profile.get("evidence") or {}),
        len(linked.get("callees") or []),
        len(linked.get("data_objects") or []),
    )


def _is_valid_semantic_frame(frame: object, expected_target_id: str) -> bool:
    """Validate one closed frame and every internal evidence reference."""
    if not isinstance(frame, dict) or frame.get("schema") != "semantic-frame/v1":
        return False
    target = frame.get("target")
    profile = frame.get("profile")
    slots = frame.get("slots")
    if not isinstance(target, dict) or target.get("id") != expected_target_id:
        return False
    if not isinstance(profile, dict) or profile.get("schema") != "structural-profile/v1":
        return False
    if profile.get("target") != target or not isinstance(slots, dict):
        return False
    evidence = profile.get("evidence")
    if not isinstance(evidence, dict) or not evidence:
        return False
    for evidence_id, fact in evidence.items():
        if not isinstance(fact, dict) or fact.get("id") != evidence_id:
            return False
    for slot_id, slot in slots.items():
        if not isinstance(slot, dict) or slot.get("slot_id") != slot_id:
            return False
        refs = slot.get("evidence_refs")
        if slot.get("target_ref") not in evidence or not isinstance(refs, list):
            return False
        if any(ref not in evidence for ref in refs):
            return False
        status = slot.get("status")
        meaning = slot.get("meaning")
        missing = slot.get("missing_context")
        if status not in {"sufficient", "partial", "insufficient"} or not isinstance(missing, list):
            return False
        if status == "sufficient" and (not meaning or missing):
            return False
        if status == "partial" and (not meaning or not missing):
            return False
        if status == "insufficient" and (meaning != "" or not missing):
            return False
    return True


def _is_valid_semantic_frame_packet(item: dict) -> bool:
    """Accept only closed, internally referential semantic-frame packets."""
    if item.get("schemaVersion") != "semantic-frame-packet/v1":
        return False
    if not _is_valid_semantic_frame(item.get("semanticFrame"), str(item.get("nodeId") or "")):
        return False
    linked = item.get("linkedContext")
    if not isinstance(linked, dict):
        return False
    for key in ("callees", "symbols", "data_objects"):
        values = linked.get(key)
        if not isinstance(values, list):
            return False
        ids = [str(value.get("id") or value.get("evidence_id") or "") for value in values if isinstance(value, dict)]
        if len(ids) != len(set(ids)):
            return False
    for table in linked.get("data_objects") or []:
        if not isinstance(table, dict):
            return False
        table_frame = table.get("semantic_frame")
        if table_frame is not None and not _is_valid_semantic_frame(
            table_frame, str(table.get("id") or ""),
        ):
            return False
        for column in table.get("columns") or []:
            if not isinstance(column, dict):
                return False
            column_frame = column.get("semantic_frame")
            if column_frame is not None and not _is_valid_semantic_frame(
                column_frame, str(column.get("id") or ""),
            ):
                return False
    return True


def build_evidence_packet(legacy_references: Any) -> list[dict]:
    """Select the richest successful semantic-frame inspection per exact node id.

    Repeated stages often inspect the same function.  Choosing an already persisted
    response is deterministic deduplication; arrays and source text remain unchanged.
    """
    selected: dict[str, dict] = {}
    order: list[str] = []
    for stage in _parse_refs(legacy_references):
        for retrieve in stage.get("retrieves") or []:
            if not isinstance(retrieve, dict):
                continue
            for inspection in retrieve.get("inspections") or []:
                if not isinstance(inspection, dict) or not inspection.get("ok"):
                    continue
                node_id = str(inspection.get("nodeId") or "").strip()
                if (not node_id or inspection.get("view") != "frame"
                        or not _is_valid_semantic_frame_packet(inspection)):
                    continue
                if node_id not in selected:
                    order.append(node_id)
                    selected[node_id] = inspection
                elif _inspection_score(inspection) > _inspection_score(selected[node_id]):
                    selected[node_id] = inspection
    return [selected[node_id] for node_id in order]


def load_evidence_packet(proposal_id: str) -> list[dict]:
    with get_session() as session:
        row = session.run(
            "MATCH (p:Proposal {id:$id}) RETURN p.legacyReferences AS refs",
            id=proposal_id,
        ).single()
    return build_evidence_packet((row or {}).get("refs"))


def evidence_prompt_block(packet: list[dict]) -> str:
    if not packet:
        return "(이전 단계에서 성공한 semantic-frame 상세 검토 없음 — 필요한 근거만 MCP로 조회)"
    return json.dumps({
        "contract": "semantic-frame-packet/v1",
        "authorityOrder": [
            "semanticFrame.profile.evidence structural facts and coordinates",
            "semanticFrame.slots with status and evidence_refs",
            "ruleExamples derived from accepted RULE condition/effects",
            "linkedContext deduplicated callee/symbol/data-object frames",
        ],
        "usage": (
            "Do not request or reconstruct source in the normal generation path. "
            "RULE meaning is its exact profile.evidence condition/effects plus ruleExamples; "
            "do not expect or invent a RULE narrative slot. "
            "Cite exact slot_id or evidence fact IDs in each GWT scenario.evidenceRefs; "
            "surface partial/insufficient missing_context instead of inventing facts."
        ),
        "targets": packet,
    }, ensure_ascii=False, separators=(",", ":"))


def has_grounded_legacy_evidence(packet: object) -> bool:
    """One policy boundary: Analyzer evidence enriches Architect but never starts it."""
    return isinstance(packet, list) and bool(packet)


def optional_legacy_evidence_instruction(packet: object) -> str:
    """Return the shared Plan/Tactical instruction for the current optional mode."""
    if has_grounded_legacy_evidence(packet):
        return (
            "Analyzer evidence packet이 있으므로 각 GWT scenario.evidenceRefs에는 실제 사용한 "
            "packet evidence_id를 넣고 RULE evidence_id를 최소 1개 포함한다. legacyRefs에도 "
            "실제로 확인한 근거만 보존한다."
        )
    return (
        "Analyzer/legacy evidence는 선택 도구이며 현재 packet이 없다. Architect의 기본 GWT "
        "생성을 계속하고 각 scenario.evidenceRefs와 legacyRefs는 빈 배열로 둔다. 존재하지 "
        "않는 evidence_id를 만들거나 추가 조회 결과를 필수 입력처럼 취급하지 않는다."
    )


def optional_legacy_refs_instruction(packet: object) -> str:
    """Keep Command legacyRefs rules consistent with the optional packet policy."""
    if has_grounded_legacy_evidence(packet):
        return (
            "각 Command.legacyRefs에 근거 함수 nodeId, 그 함수의 실제 RULE "
            "evidenceId와 condition/effects 구조 표시 1개 이상, linkedContext.data_objects의 "
            "직접 TABLE id 전부를 "
            "access에 맞는 reads/writes role로 붙인다. TABLE 이름을 바꾸지 않는다."
        )
    return (
        "현재 packet이 없으므로 각 Command.legacyRefs는 빈 배열로 둔다. Analyzer 조회나 "
        "레거시 근거를 완료 조건으로 만들지 않고, 존재하지 않는 nodeId·RULE·TABLE을 만들지 않는다."
    )


def _index_frame(index: dict[str, dict], frame: dict, node_id: str) -> None:
    """Add a validated code/table/column frame without changing its exact IDs."""
    profile = frame.get("profile") or {}
    for evidence_id, evidence in (profile.get("evidence") or {}).items():
        if evidence_id not in index and isinstance(evidence, dict):
            index[evidence_id] = {
                "nodeId": node_id,
                "kind": evidence.get("kind") or "",
                "evidence": evidence,
            }
    for slot_id, slot in (frame.get("slots") or {}).items():
        if slot_id not in index and isinstance(slot, dict):
            index[slot_id] = {
                "nodeId": node_id,
                "kind": f"SLOT:{slot.get('family') or ''}",
                "evidence": slot,
            }


def _evidence_index(packet: list[dict]) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for item in packet:
        node_id = str(item.get("nodeId") or "")
        frame = item.get("semanticFrame") or {}
        _index_frame(index, frame, node_id)
        linked = item.get("linkedContext") or {}
        for collection, kind in (("callees", "CALL"), ("symbols", "SYMBOL"),
                                 ("data_objects", "TABLE")):
            for evidence in linked.get(collection) or []:
                if not isinstance(evidence, dict):
                    continue
                evidence_id = str(evidence.get("evidence_id") or "").strip()
                if evidence_id and evidence_id not in index:
                    index[evidence_id] = {"nodeId": node_id, "kind": kind, "evidence": evidence}
                if collection == "data_objects":
                    table_id = str(evidence.get("id") or "")
                    table_frame = evidence.get("semantic_frame")
                    if isinstance(table_frame, dict):
                        _index_frame(index, table_frame, table_id)
                    for column in evidence.get("columns") or []:
                        if not isinstance(column, dict):
                            continue
                        column_frame = column.get("semantic_frame")
                        if isinstance(column_frame, dict):
                            _index_frame(
                                index, column_frame, str(column.get("id") or ""),
                            )
    return index


def _scalar_is_grounded(value: object, corpus: str) -> bool:
    if value in (None, ""):
        return True
    if isinstance(value, bool):
        token = "true" if value else "false"
        return re.search(rf"(?<![A-Za-z]){token}(?![A-Za-z])", corpus, re.IGNORECASE) is not None
    token = str(value).strip()
    if not token:
        return True
    if re.fullmatch(r"-?\d+(?:\.\d+)?", token):
        plain = re.escape(token)
        if re.search(rf"(?<![\d.]){plain}(?![\d.])", corpus):
            return True
        try:
            number = float(token)
            if number.is_integer():
                formatted = f"{int(number):,}"
                return formatted in corpus
        except ValueError:
            pass
        return False
    return token in corpus


def ungrounded_gwt_values(
    tactical: list[dict], evidence_packet: list[dict], additional_context: object = None,
) -> list[str]:
    """Report scalar fieldValues absent from authoritative inputs.

    This is a validation gate, not a semantic generator: it does not decide which value
    is correct or repair anything.  It only rejects a value the model could not have read
    from the persisted GWT detail or the approved strategic input.
    """
    if not has_grounded_legacy_evidence(evidence_packet):
        return []
    evidence_by_id = _evidence_index(evidence_packet)
    errors: list[str] = []
    for command in tactical:
        if command.get("nodeLabel") != "Command":
            continue
        title = command.get("nodeTitle") or "<unnamed>"
        for scenario_index, scenario in enumerate(command.get("gwt") or []):
            if not isinstance(scenario, dict):
                continue
            cited = [
                evidence_by_id[evidence_id]
                for evidence_id in scenario.get("evidenceRefs") or []
                if isinstance(evidence_id, str) and evidence_id in evidence_by_id
            ]
            corpus = json.dumps(
                {"citedEvidence": cited, "context": additional_context},
                ensure_ascii=False, separators=(",", ":"),
            )
            for phase in ("given", "when", "then"):
                values = scenario.get(phase, {}).get("fieldValues", {})
                if not isinstance(values, dict):
                    continue
                for field, value in values.items():
                    if not _scalar_is_grounded(value, corpus):
                        errors.append(
                            f"Command {title} gwt[{scenario_index}].{phase}.fieldValues."
                            f"{field}={value!r} is absent from inspected evidence and strategic input"
                        )
    return errors


def gwt_evidence_ref_errors(tactical: list[dict], evidence_packet: list[dict]) -> list[str]:
    """Require every scenario to cite exact, source-owned evidence IDs."""
    if not has_grounded_legacy_evidence(evidence_packet):
        return []
    evidence_by_id = _evidence_index(evidence_packet)
    errors: list[str] = []
    for command in tactical:
        if command.get("nodeLabel") != "Command":
            continue
        title = command.get("nodeTitle") or "<unnamed>"
        legacy_node_ids: set[str] = set()
        for ref in command.get("legacyRefs") or []:
            if isinstance(ref, str) and ref:
                legacy_node_ids.add(ref)
            elif isinstance(ref, dict):
                # Content-ref resolution replaces nodeId with the Rule scenario
                # evidence id and preserves the inspected frame owner in parentId.
                # Either coordinate proves that the source frame is represented.
                for key in ("parentId", "nodeId"):
                    value = ref.get(key)
                    if isinstance(value, str) and value:
                        legacy_node_ids.add(value)
                evidence_id = ref.get("evidenceId")
                if evidence_id in evidence_by_id:
                    legacy_node_ids.add(evidence_by_id[evidence_id]["nodeId"])
        for index, scenario in enumerate(command.get("gwt") or []):
            if not isinstance(scenario, dict):
                continue
            refs = scenario.get("evidenceRefs")
            if not isinstance(refs, list) or not refs:
                errors.append(f"Command {title} gwt[{index}] requires non-empty evidenceRefs")
                continue
            string_refs = [ref for ref in refs if isinstance(ref, str)]
            if len(string_refs) != len(refs):
                errors.append(f"Command {title} gwt[{index}] evidenceRefs must contain strings")
            if len(string_refs) != len(set(string_refs)):
                errors.append(f"Command {title} gwt[{index}] evidenceRefs contains duplicates")
            records = []
            for evidence_id in refs:
                if not isinstance(evidence_id, str) or evidence_id not in evidence_by_id:
                    errors.append(
                        f"Command {title} gwt[{index}] cites unknown evidenceRef {evidence_id!r}"
                    )
                    continue
                records.append(evidence_by_id[evidence_id])
            if records and not any(record["kind"] == "RULE" for record in records):
                errors.append(f"Command {title} gwt[{index}] requires at least one RULE evidenceRef")
            for node_id in sorted({record["nodeId"] for record in records} - legacy_node_ids):
                errors.append(
                    f"Command {title} gwt[{index}] evidence source {node_id} is absent from legacyRefs"
                )
    return errors


def tactical_evidence_ref_errors(
    tactical: list[dict], evidence_packet: list[dict],
) -> list[str]:
    """Require each grounded Command to expose exact frame facts and direct tables."""
    if not has_grounded_legacy_evidence(evidence_packet):
        return []
    by_id = {item.get("nodeId"): item for item in evidence_packet if item.get("nodeId")}
    evidence_index = _evidence_index(evidence_packet)
    errors: list[str] = []
    for command in tactical:
        if command.get("nodeLabel") != "Command":
            continue
        title = command.get("nodeTitle") or "<unnamed>"
        refs = [ref for ref in command.get("legacyRefs") or [] if isinstance(ref, dict)]

        def source_id(ref: dict) -> str | None:
            evidence_id = ref.get("evidenceId")
            if evidence_id in evidence_index:
                return evidence_index[evidence_id]["nodeId"]
            # resolve_content_refs deliberately turns a RULE ref's nodeId into the
            # evidence coordinate.  parentId remains the inspected semantic-frame
            # target and therefore owns the RULE in the evidence packet.
            parent_id = ref.get("parentId")
            if parent_id in by_id:
                return parent_id
            node_id = ref.get("nodeId")
            return node_id if node_id in by_id else None

        source_ids = [resolved for ref in refs if (resolved := source_id(ref))]
        if not source_ids:
            errors.append(f"Command {title} has no inspected function legacyRef")
            continue
        rule_ids_by_node = {
            node_id: {
                evidence_id for evidence_id, record in evidence_index.items()
                if record["nodeId"] == node_id and record["kind"] == "RULE"
            }
            for node_id in source_ids
        }
        exact_rules = set().union(*rule_ids_by_node.values()) if rule_ids_by_node else set()
        primary_ids = {
            resolved
            for ref in refs
            if (resolved := source_id(ref)) in rule_ids_by_node
            and ref.get("evidenceId") in rule_ids_by_node[resolved]
        }
        if exact_rules and not primary_ids:
            errors.append(f"Command {title} requires at least one exact inspected RULE ref")
        # A CALL callee may have its own tables, but those are not the Command source
        # function's direct READ/WRITE.  Only the function whose exact RULE is cited as
        # primary evidence owns mandatory direct table refs.
        table_source_ids = primary_ids or set(source_ids)
        expected_tables = {
            table.get("id")
            for node_id in table_source_ids
            for table in (by_id[node_id].get("linkedContext") or {}).get("data_objects") or []
            if isinstance(table, dict) and table.get("id")
        }
        actual_ids = {ref.get("nodeId") for ref in refs}
        for table_id in sorted(expected_tables - actual_ids):
            errors.append(f"Command {title} missing direct TABLE ref {table_id}")
    return errors


__all__ = [
    "build_evidence_packet", "load_evidence_packet", "evidence_prompt_block",
    "has_grounded_legacy_evidence", "optional_legacy_evidence_instruction",
    "optional_legacy_refs_instruction",
    "gwt_evidence_ref_errors", "ungrounded_gwt_values", "tactical_evidence_ref_errors",
]
