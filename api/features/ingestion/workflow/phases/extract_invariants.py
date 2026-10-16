"""Extract Invariants Phase (spec 027 — aggregate-invariants).

Runs right after GWT generation. For each Aggregate, asks the LLM to state the
business invariants the aggregate must always uphold, then persists each as a
first-class `Invariant` node (`source='ingested'`) and links it to the
Commands whose acceptance criteria verify it via `VERIFIED_BY`.

Idempotent: `Invariant` is `MERGE`d on its natural key, so re-ingesting the
same requirement updates rather than duplicates (spec FR-022).
"""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage
from api.platform.llm_messages import build_system_message
from pydantic import BaseModel, Field

from api.features.ingestion.ingestion_contracts import IngestionPhase, ProgressEvent
from api.features.ingestion.workflow.ingestion_workflow_context import IngestionWorkflowContext
from api.platform.observability.smart_logger import SmartLogger

PHASE_START = 88
PHASE_END = 91

_SYSTEM_PROMPT = (
    "You are a domain-driven design expert extracting the invariants a DDD "
    "Aggregate must ALWAYS uphold, regardless of which command runs.\n"
    "\n"
    "**Work from the evidence given, not from what a typical aggregate of this "
    "name would need.** The evidence is the source material this aggregate was "
    "built from: statements from the requirement documents and rules proven by "
    "reading the legacy code.\n"
    "\n"
    "Priority order:\n"
    "1. **Prohibitions stated in the source** - anything the source says must "
    "not or cannot happen, or may happen only under a condition. These are the "
    "invariants that matter; they are what a reader would be held to.\n"
    "2. Other consistency rules the source states explicitly.\n"
    "3. Nothing else. If the evidence states no constraint, return an empty "
    "list - an empty answer is correct and useful. Do NOT fill the list with "
    "generic rules (\"must have a valid X\", \"must always be consistent\") "
    "that the source never states.\n"
    "\n"
    "Each invariant is one declarative sentence. When a listed command keeps it "
    "true, name that command as a verifier. At most 8."
)


class _ExtractedInvariant(BaseModel):
    declaration: str = Field(description="One declarative sentence stating the rule")
    verifying_command_names: list[str] = Field(
        default_factory=list,
        description="Names of listed commands whose behavior verifies this invariant",
    )


class _ExtractedInvariantSet(BaseModel):
    invariants: list[_ExtractedInvariant] = Field(default_factory=list)


# 근거 예산. 구절 원문은 길다(한 건 1~2천 자). 어그리거트 하나당 이만큼까지 싣고,
# 몇 개를 싣고 몇 개를 두고 왔는지는 **로그로 남긴다** — 조용히 버리지 않는다.
_EVIDENCE_PASSAGE_BUDGET = 6000
_EVIDENCE_RULE_LIMIT = 40

# 제약을 말하는 한국어·영어 표현. 이 표식이 있는 구절을 **앞으로 보낸다**(버리지 않는다).
# 예산을 넘겨 잘릴 때 금지 문장이 먼저 살아남게 하는 것이 목적이다.
_CONSTRAINT_MARKERS = (
    "할 수 없", "하지 못하", "되돌리지 않", "금지", "불가", "허용하지 않",
    "없도록", "없게 한다", "제외한다", "만 할 수 있", "먼저", "이내",
    "must not", "cannot", "only if", "only when", "never",
)


def _constraint_score(text: str) -> int:
    """구절이 제약을 몇 번 말하는가. 정렬에만 쓴다."""
    low = text or ""
    return sum(low.count(marker) for marker in _CONSTRAINT_MARKERS)


def _render_evidence(agg: dict) -> tuple[str, dict]:
    """근거 블록과 **실었는지 세는 값**을 돌려준다."""
    rules = [r for r in (agg.get("rules") or []) if r]
    passages = [p for p in (agg.get("passages") or []) if p]
    stats = {
        "rules_available": len(rules),
        "passages_available": len(passages),
        "rules_included": 0,
        "passages_included": 0,
        "passage_chars": 0,
        "constraint_markers": 0,
    }
    if not rules and not passages:
        return "", stats

    lines: list[str] = ["", "=== EVIDENCE ==="]

    if passages:
        ordered = sorted(passages, key=_constraint_score, reverse=True)
        lines += ["", "Statements from the requirement documents:"]
        used = 0
        for text in ordered:
            flat = " ".join((text or "").split())
            if not flat:
                continue
            if used + len(flat) > _EVIDENCE_PASSAGE_BUDGET and stats["passages_included"]:
                break
            lines.append(f"  - {flat[:_EVIDENCE_PASSAGE_BUDGET]}")
            used += len(flat)
            stats["passages_included"] += 1
            stats["constraint_markers"] += _constraint_score(flat)
        stats["passage_chars"] = used

    if rules:
        shown = rules[:_EVIDENCE_RULE_LIMIT]
        stats["rules_included"] = len(shown)
        lines += ["", "Rules proven by reading the legacy code:"]
        lines += [f"  - {' '.join((r or '').split())}" for r in shown]

    lines += ["", "=== END EVIDENCE ==="]
    return "\n".join(lines), stats


def _build_prompt(agg: dict) -> str:
    lines = [
        f'Aggregate: "{agg.get("aggName") or ""}"',
        f'Root entity: {agg.get("rootEntity") or "(unspecified)"}',
        "",
        "Commands handled by this aggregate:",
    ]
    commands = agg.get("commands") or []
    if commands:
        for c in commands:
            lines.append(f'  - {c.get("name") or ""}')
    else:
        lines.append("  (none)")
    events = [e for e in (agg.get("events") or []) if e]
    if events:
        lines += ["", "Events it emits:"]
        lines += [f"  - {e}" for e in events]
    evidence, _stats = _render_evidence(agg)
    if evidence:
        lines.append(evidence)
        lines += [
            "",
            "From the EVIDENCE above, state the invariants this aggregate must "
            "always uphold. **Start with every prohibition the evidence states** "
            "(what must not happen, or may happen only under a condition) and "
            "write each as one declarative sentence naming the same subject the "
            "source names. Do not add constraints the evidence does not state. "
            "For each, set verifying_command_names to the subset of the commands "
            "above that keep it true (exact names; leave empty if none apply).",
        ]
    else:
        # 근거가 하나도 안 붙은 어그리거트다. 이름만으로 만들어내게 하지 않는다.
        lines += [
            "",
            "No source evidence is attached to this aggregate. Return an empty "
            "list unless a constraint is implied by the command names themselves "
            "beyond all doubt. Do not invent generic invariants.",
        ]
    return "\n".join(lines)


async def extract_invariants_phase(
    ctx: IngestionWorkflowContext,
) -> AsyncGenerator[ProgressEvent, None]:
    """Extract candidate Invariants for every Aggregate and persist them."""
    client = ctx.client
    session_id = getattr(ctx.session, "id", None)

    yield ProgressEvent(
        phase=IngestionPhase.EXTRACTING_INVARIANTS,
        message="📐 어그리거트 인베리언트를 추출하는 중...",
        progress=PHASE_START,
    )

    # Housekeeping — re-ingestion wipes session-scoped Aggregates but Invariant
    # nodes are not session-tagged. If a prior run's aggregate was renamed, its
    # invariants are left orphaned. Drop them before re-extracting so the model
    # only carries invariants attached to current aggregates.
    try:
        pruned = client.prune_orphan_invariants()
        if pruned:
            SmartLogger.log(
                "INFO",
                f"Pruned {pruned} orphan invariant(s) before extraction",
                category="agent.invariants.extract.prune",
                params={"session_id": session_id, "pruned": pruned},
            )
    except Exception as exc:  # noqa: BLE001 — housekeeping is best-effort
        SmartLogger.log(
            "WARN",
            f"Orphan-invariant prune failed (non-fatal): {exc}",
            category="agent.invariants.extract.prune.error",
            params={"session_id": session_id, "error": str(exc)},
        )

    with client.session() as session:
        agg_rows = list(
            session.run(
                """
                MATCH (agg:Aggregate)
                OPTIONAL MATCH (agg)-[:HAS_COMMAND]->(cmd:Command)
                OPTIONAL MATCH (cmd)-[:EMITS]->(evt:Event)
                WITH agg, collect(DISTINCT cmd {.id, .name}) AS commands,
                     collect(DISTINCT evt.name) AS events
                // 근거는 **이 단계(progress 88~91)에 이미 있는 것**으로만 모은다.
                // 늦게 붙는 간선 둘을 쓰면 안 된다 —
                //   (Aggregate)-[:SOURCED_FROM]->(Rule)   traceability 부착 · **99**
                //   (BpmTask)-[:PROMOTED_TO]->(UserStory) 브리지 부착   · **97**
                // 2026-10-16 에 둘을 차례로 밟아 Invariant 가 0개가 됐다(done13 §255).
                // 그래서 **속성 조인**을 쓴다 — `UserStory.sourceUnitId == BpmTask.id`.
                // 그 값은 UserStory 생성 때 함께 들어가므로 여기서 이미 있다.
                // 숫자가 간선 꼴과 같은 것은 엔진에 직접 때려 확인했다.
                OPTIONAL MATCH (agg)<-[:IMPLEMENTS]-(us:UserStory)
                WITH agg, commands, events,
                     collect(DISTINCT us.sourceUnitId) AS unitIds
                OPTIONAL MATCH (t1:BpmTask)-[:REALIZED_BY]->(rule:Rule)
                  WHERE t1.id IN unitIds
                WITH agg, commands, events, unitIds,
                     collect(DISTINCT rule.title) AS rules
                OPTIONAL MATCH (t2:BpmTask)-[:SOURCED_FROM]->(doc:DocumentPassage)
                  WHERE t2.id IN unitIds
                WITH agg, commands, events, rules,
                     collect(DISTINCT doc.text) AS passages
                RETURN agg.id AS aggId, agg.key AS aggKey, agg.name AS aggName,
                       agg.rootEntity AS rootEntity, commands, events,
                       rules, passages
                ORDER BY agg.name
                """
            )
        )

    total = len(agg_rows)
    invariants_created = 0
    links_created = 0
    # 근거가 0인데 인베리언트도 0이면 "모델이 안 만들었다" 가 아니라
    # **우리가 줄 것을 안 줬다** 는 뜻이다. 둘을 구별할 수 있게 같이 싣는다.
    evidence_totals = {
        "rules": 0, "passages": 0, "markers": 0,
        "aggregates_without_evidence": 0,
    }

    SmartLogger.log(
        "INFO",
        f"Invariant extraction started: {total} aggregates",
        category="agent.invariants.extract.start",
        params={"session_id": session_id, "aggregate_count": total},
    )

    for idx, row in enumerate(agg_rows):
        agg = {
            "aggId": row["aggId"],
            "aggKey": row["aggKey"],
            "aggName": row["aggName"] or "",
            "rootEntity": row["rootEntity"],
            "commands": [dict(c) for c in (row["commands"] or []) if c and c.get("id")],
            "events": list(row["events"] or []),
            "rules": [r for r in (row["rules"] or []) if r],
            "passages": [p for p in (row["passages"] or []) if p],
        }

        # **재지 않으면 또 모른다.** 근거가 0인 어그리거트는 이름만으로 답하게 되는
        # 자리이므로 숫자로 남긴다. 분류에 skip/error 표식을 쓰지 않는다 —
        # 건너뛴 것이 아니라 상태 보고다.
        _evidence_text, _ev = _render_evidence(agg)
        SmartLogger.log(
            "WARN" if not _evidence_text else "INFO",
            ("Invariant evidence for '%s': rules %d/%d · passages %d/%d "
             "(%d chars · %d constraint markers)")
            % (agg["aggName"], _ev["rules_included"], _ev["rules_available"],
               _ev["passages_included"], _ev["passages_available"],
               _ev["passage_chars"], _ev["constraint_markers"]),
            category="agent.invariants.extract.evidence",
            params={"session_id": session_id, "aggregate": agg["aggName"], **_ev},
        )

        evidence_totals["rules"] += _ev["rules_included"]
        evidence_totals["passages"] += _ev["passages_included"]
        evidence_totals["markers"] += _ev["constraint_markers"]
        if not _evidence_text:
            evidence_totals["aggregates_without_evidence"] += 1

        progress = PHASE_START + int((PHASE_END - PHASE_START) * (idx / max(total, 1)))
        yield ProgressEvent(
            phase=IngestionPhase.EXTRACTING_INVARIANTS,
            message=(f"📐 '{agg['aggName']}' 인베리언트 추출 중... ({idx + 1}/{total})"
                     f" — 근거 규칙 {_ev['rules_included']} · 구절 {_ev['passages_included']}"),
            progress=progress,
            data={"aggregate": agg["aggName"], "evidence": _ev},
        )

        try:
            structured_llm = ctx.llm.with_structured_output(_ExtractedInvariantSet)
            result: _ExtractedInvariantSet = await asyncio.wait_for(
                asyncio.to_thread(
                    structured_llm.invoke,
                    [
                        build_system_message(_SYSTEM_PROMPT),
                        HumanMessage(content=_build_prompt(agg)),
                    ],
                ),
                timeout=180.0,
            )
            extracted = result.invariants or []
        except Exception as exc:  # noqa: BLE001 — skip this aggregate, keep going
            SmartLogger.log(
                "WARN",
                f"Invariant extraction LLM failed for aggregate '{agg['aggName']}': {exc}",
                category="agent.invariants.extract.error",
                params={"session_id": session_id, "aggregate_id": agg["aggId"], "error": str(exc)},
            )
            continue

        cmd_by_name = {(c.get("name") or "").strip().lower(): c["id"] for c in agg["commands"]}

        for seq, item in enumerate(extracted, start=1):
            declaration = (item.declaration or "").strip()
            if not declaration:
                continue
            invariant = client.upsert_invariant(
                aggregate_id=agg["aggId"],
                aggregate_key=agg["aggKey"],
                declaration=declaration,
                source="ingested",
                seq=seq,
                session_id=session_id,
            )
            if not invariant:
                continue
            invariants_created += 1
            for cmd_name in item.verifying_command_names or []:
                cmd_id = cmd_by_name.get((cmd_name or "").strip().lower())
                if cmd_id and client.link_invariant_verified_by(invariant["id"], cmd_id):
                    links_created += 1

    ctx.invariant_extraction_summary = {
        "invariants_created": invariants_created,
        "verified_by_links": links_created,
        "evidence": dict(evidence_totals),
    }
    SmartLogger.log(
        "INFO",
        f"Invariant extraction done: {invariants_created} invariants, {links_created} links",
        category="agent.invariants.extract.done",
        params={
            "session_id": session_id,
            "invariants_created": invariants_created,
            "verified_by_links": links_created,
        },
    )

    yield ProgressEvent(
        phase=IngestionPhase.EXTRACTING_INVARIANTS,
        message=(f"✅ 인베리언트 추출 완료 ({invariants_created}개)"
                 f" · 근거 규칙 {evidence_totals['rules']} · 구절 {evidence_totals['passages']}"
                 f" · 제약표현 {evidence_totals['markers']}"
                 + (f" · **근거 없는 어그리거트 {evidence_totals['aggregates_without_evidence']}개**"
                    if evidence_totals["aggregates_without_evidence"] else "")),
        progress=PHASE_END,
        data={"invariants_created": invariants_created,
              "verified_by_links": links_created,
              "evidence": dict(evidence_totals)},
    )
