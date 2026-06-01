"""설계 커버리지 검증·복구 (인제스천 사후 단계).

인제스천의 Command/ReadModel 단계는 LLM이 각 객체의 `user_story_ids`로 US를 지목하는데,
조회성 US는 ReadModel에 거의 매핑되지 않고(실측: ReadModel에 US 0건) 액션성 near-duplicate
US도 누락된다. 인제스천 후 이런 누락을 검증·복구하는 단계가 없었다.

이 모듈은 (1) 커버리지 리포트(어떤 behavioral 설계객체에도 IMPLEMENTS로 안 붙은 "고아 US"
집계 = 검증 체크리스트)와 (2) 복구(고아 US를 기존 Command(액션)/ReadModel(조회)에 LLM 매핑해
링크 — 새 객체를 만들지 않아 중복 회피; 적합 대상 없으면 unmapped로 남겨 리포트)를 제공한다.

ingestion 워크플로 마지막에 best-effort로 호출되고, `/api/requirements/design-coverage*`
엔드포인트도 동일 로직을 재사용한다.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from api.features.ingestion.event_storming.neo4j_client import get_neo4j_client
from api.features.ingestion.ingestion_llm_runtime import get_llm
from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger

# 어떤 behavioral 설계객체에도 IMPLEMENTS로 안 붙은 US = "고아"(설계 누락).
_ORPHAN_PRED = (
    "NOT (us)-[:IMPLEMENTS]->(:Command) "
    "AND NOT (us)-[:IMPLEMENTS]->(:ReadModel) "
    "AND NOT (us)-[:IMPLEMENTS]->(:Event) "
    "AND NOT (us)-[:IMPLEMENTS]->(:Policy)"
)


def _q(cy: str, **p: Any) -> list[dict]:
    with get_session() as session:
        return [dict(r) for r in session.run(cy, **p)]


def coverage_report() -> list[dict]:
    """BC별 {id,name,totalUS,orphanUS,sample} 리스트 (검증 체크리스트)."""
    return _q(
        f"""
        MATCH (bc:BoundedContext)
        OPTIONAL MATCH (us:UserStory)-[:IMPLEMENTS]->(bc)
        WITH bc, us,
          CASE WHEN us IS NOT NULL AND {_ORPHAN_PRED} THEN us ELSE NULL END AS orphan
        WITH bc, count(DISTINCT us) AS total,
             [o IN collect(DISTINCT orphan) WHERE o IS NOT NULL] AS orphans
        RETURN bc.id AS id, bc.name AS name, total AS totalUS,
               size(orphans) AS orphanUS, [u IN orphans[0..5] | u.action] AS sample
        ORDER BY orphanUS DESC
        """
    )


def _orphans(bc_id: str) -> list[dict]:
    return _q(
        f"MATCH (us:UserStory)-[:IMPLEMENTS]->(:BoundedContext {{id:$bc}}) WHERE {_ORPHAN_PRED} "
        "RETURN us.id AS id, us.role AS role, us.action AS action ORDER BY us.id",
        bc=bc_id,
    )


def _commands(bc_id: str) -> list[dict]:
    return _q(
        "MATCH (:BoundedContext {id:$bc})-[:HAS_AGGREGATE]->(:Aggregate)-[:HAS_COMMAND]->(c:Command) "
        "RETURN c.id AS id, coalesce(c.displayName,c.name) AS name, c.description AS description",
        bc=bc_id,
    )


def _readmodels(bc_id: str) -> list[dict]:
    return _q(
        "MATCH (:BoundedContext {id:$bc})-[:HAS_READMODEL]->(rm:ReadModel) "
        "RETURN rm.id AS id, coalesce(rm.displayName,rm.name) AS name, rm.description AS description",
        bc=bc_id,
    )


class _Mapping(BaseModel):
    userStoryId: str
    kind: str = "none"
    targetName: str = ""


class _MappingList(BaseModel):
    mappings: list[_Mapping] = Field(default_factory=list)


_SYSTEM = (
    "You map orphan user stories to the SINGLE best-matching EXISTING design object "
    "in the same Bounded Context. An action story (do/process/create/update/delete, "
    "register, cancel, change) maps to a Command. A query/read story (view, look up, "
    "check, confirm, list, be notified) maps to a ReadModel. Pick by closest meaning "
    "to the object's name/description. If NO existing object reasonably covers the "
    "story, return kind='none'. NEVER invent names — `targetName` MUST be copied "
    "character-for-character from the provided lists. Map EVERY listed story once."
)


def reconcile_bc(bc_id: str, name: str = "", *, dry_run: bool = False) -> dict:
    """고아 US를 기존 Command/ReadModel에 매핑·링크. 결과 dict 반환."""
    orphans = _orphans(bc_id)
    out = {
        "boundedContextId": bc_id, "name": name or "", "orphanBefore": len(orphans),
        "linkedToCommand": 0, "linkedToReadModel": 0, "unmapped": 0, "notes": [],
    }
    if not orphans:
        return out
    cmds, rms = _commands(bc_id), _readmodels(bc_id)
    cmd_by_name = {c["name"]: c["id"] for c in cmds}
    rm_by_name = {r["name"]: r["id"] for r in rms}
    if not cmds and not rms:
        out["unmapped"] = len(orphans)
        out["notes"].append("기존 Command/ReadModel이 없어 매핑 대상 없음")
        return out

    prompt = (
        "[Orphan User Stories]\n"
        + "\n".join(f"- {o['id']}: {o.get('role','')} / {o.get('action','')}" for o in orphans)
        + "\n\n[Existing Commands]\n"
        + ("\n".join(f"- {c['name']}: {c.get('description') or ''}" for c in cmds) or "(none)")
        + "\n\n[Existing ReadModels]\n"
        + ("\n".join(f"- {r['name']}: {r.get('description') or ''}" for r in rms) or "(none)")
        + "\n\n각 user story를 위 객체 중 하나(name 정확히)에 매핑하거나 kind='none'."
    )
    try:
        mappings = (
            get_llm().with_structured_output(_MappingList)
            .invoke([SystemMessage(content=_SYSTEM), HumanMessage(content=prompt)])
            .mappings
            or []
        )
    except Exception as exc:  # noqa: BLE001
        out["unmapped"] = len(orphans)
        out["notes"].append(f"LLM 매핑 실패: {exc}")
        return out

    client = get_neo4j_client()
    valid = {o["id"] for o in orphans}
    seen: set[str] = set()
    for m in mappings:
        if m.userStoryId not in valid or m.userStoryId in seen:
            continue
        seen.add(m.userStoryId)
        # kind는 PascalCase/혼동될 수 있으므로 무시하고 targetName을 실제 객체명에 매칭
        # (환각 이름은 자연히 unmapped). 동명이 양쪽이면 kind로 tiebreak.
        nm = (m.targetName or "").strip()
        kind = (m.kind or "").strip().lower()
        in_c, in_r = nm in cmd_by_name, nm in rm_by_name
        target = ("readmodel" if kind.startswith("read") else "command") if (in_c and in_r) else \
                 ("command" if in_c else ("readmodel" if in_r else None))
        if target == "command":
            if not dry_run:
                client.link_user_story_to_command(m.userStoryId, cmd_by_name[nm])
            out["linkedToCommand"] += 1
        elif target == "readmodel":
            if not dry_run:
                client.link_user_story_to_readmodel(m.userStoryId, rm_by_name[nm])
            out["linkedToReadModel"] += 1
        else:
            out["unmapped"] += 1
    out["unmapped"] += sum(1 for o in orphans if o["id"] not in seen)
    return out


def reconcile(bc_ids: list[str] | None = None, *, dry_run: bool = False) -> dict:
    """지정 BC(없으면 전체)의 고아 US를 복구. {results, totalLinked, totalUnmapped}."""
    if bc_ids:
        bcs = _q("MATCH (bc:BoundedContext) WHERE bc.id IN $ids RETURN bc.id AS id, bc.name AS name", ids=bc_ids)
    else:
        bcs = _q("MATCH (bc:BoundedContext) RETURN bc.id AS id, bc.name AS name ORDER BY bc.name")
    results = [reconcile_bc(b["id"], b["name"], dry_run=dry_run) for b in bcs]
    results = [r for r in results if r["orphanBefore"] > 0]
    linked = sum(r["linkedToCommand"] + r["linkedToReadModel"] for r in results)
    unmapped = sum(r["unmapped"] for r in results)
    return {"results": results, "totalLinked": linked, "totalUnmapped": unmapped}


def reconcile_best_effort(bc_ids: list[str] | None = None) -> dict | None:
    """인제스천 워크플로 마지막에서 호출 — 실패해도 워크플로를 깨지 않는다."""
    try:
        summary = reconcile(bc_ids)
        SmartLogger.log(
            "INFO",
            f"Post-ingestion coverage: linked {summary['totalLinked']}, "
            f"remaining gaps {summary['totalUnmapped']}.",
            category="ingestion.post_coverage",
            params={"linked": summary["totalLinked"], "unmapped": summary["totalUnmapped"]},
        )
        return summary
    except Exception as exc:  # noqa: BLE001 — best-effort, never break ingestion
        SmartLogger.log(
            "WARN", f"Post-ingestion coverage reconcile failed: {exc}",
            category="ingestion.post_coverage", params={"error": str(exc)},
        )
        return None
