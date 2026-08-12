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
    source = item.get("source") if isinstance(item.get("source"), dict) else {}
    return (
        len(source.get("code_text") or ""),
        len(item.get("rules") or []),
        len(item.get("calls") or []),
        len(item.get("tables") or []),
    )


def build_evidence_packet(legacy_references: Any) -> list[dict]:
    """Select the richest successful GWT inspection per exact node id.

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
                if not node_id or inspection.get("view") != "gwt":
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
        return "(이전 단계에서 성공한 GWT 상세 검토 없음 — 필요한 근거만 MCP로 조회)"
    return json.dumps(packet, ensure_ascii=False, separators=(",", ":"))


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
    if not evidence_packet:
        return []
    by_id = {item.get("nodeId"): item for item in evidence_packet if item.get("nodeId")}
    errors: list[str] = []
    for command in tactical:
        if command.get("nodeLabel") != "Command":
            continue
        title = command.get("nodeTitle") or "<unnamed>"
        refs = [ref for ref in command.get("legacyRefs") or [] if isinstance(ref, dict)]
        primary_ids = {
            ref.get("nodeId")
            for ref in refs
            if ref.get("nodeId") in by_id
            and ref.get("rule") in {
                rule.get("text")
                for rule in by_id[ref.get("nodeId")].get("rules") or []
                if isinstance(rule, dict) and rule.get("text")
            }
        }
        command_evidence = [
            by_id[node_id] for node_id in primary_ids
        ] if primary_ids else evidence_packet
        corpus = json.dumps(
            {"evidence": command_evidence, "context": additional_context},
            ensure_ascii=False, separators=(",", ":"),
        )
        for scenario_index, scenario in enumerate(command.get("gwt") or []):
            if not isinstance(scenario, dict):
                continue
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


def tactical_evidence_ref_errors(
    tactical: list[dict], evidence_packet: list[dict],
) -> list[str]:
    """Require each grounded Command to expose exact RULE and direct TABLE refs."""
    by_id = {item.get("nodeId"): item for item in evidence_packet if item.get("nodeId")}
    errors: list[str] = []
    for command in tactical:
        if command.get("nodeLabel") != "Command":
            continue
        title = command.get("nodeTitle") or "<unnamed>"
        refs = [ref for ref in command.get("legacyRefs") or [] if isinstance(ref, dict)]
        source_ids = [ref.get("nodeId") for ref in refs if ref.get("nodeId") in by_id]
        if not source_ids:
            errors.append(f"Command {title} has no inspected function legacyRef")
            continue
        rules_by_id = {
            node_id: {
                rule.get("text")
                for rule in by_id[node_id].get("rules") or []
                if isinstance(rule, dict) and rule.get("text")
            }
            for node_id in source_ids
        }
        exact_rules = set().union(*rules_by_id.values()) if rules_by_id else set()
        primary_ids = {
            ref.get("nodeId")
            for ref in refs
            if ref.get("nodeId") in rules_by_id and ref.get("rule") in rules_by_id[ref.get("nodeId")]
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
            for table in by_id[node_id].get("tables") or []
            if isinstance(table, dict) and table.get("id")
        }
        actual_ids = {ref.get("nodeId") for ref in refs}
        for table_id in sorted(expected_tables - actual_ids):
            errors.append(f"Command {title} missing direct TABLE ref {table_id}")
    return errors


__all__ = [
    "build_evidence_packet", "load_evidence_packet", "evidence_prompt_block",
    "ungrounded_gwt_values", "tactical_evidence_ref_errors",
]
