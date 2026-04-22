"""Phase 2: legacy analyzer graph → GWT business Rules.

The analyzer stage already produces `(FUNCTION)-[:HAS_BUSINESS_LOGIC]->(BusinessLogic)`
with `given` / `when` / `then` properties. Phase 2 simply reads those, drops
infrastructure/boilerplate, and maps each surviving BusinessLogic entry to a
`RuleDTO` for downstream mapping (Phase 3) and promotion (Phase 5).

No LLM is required here — the semantic lift happened upstream.
"""

from __future__ import annotations

import hashlib
from typing import Any

from api.features.ingestion.hybrid.code_to_rules.rule_filters import (
    is_infra,
    is_meaningful_gwt,
)
from api.features.ingestion.hybrid.contracts import RuleDTO
from api.platform.neo4j import ANALYZER_NEO4J_DATABASE, get_session
from api.platform.observability.smart_logger import SmartLogger

_QUERY = """
MATCH (f)-[:HAS_BUSINESS_LOGIC]->(bl:BusinessLogic)
WITH f, bl
ORDER BY coalesce(f.procedure_name, f.name), bl.sequence
RETURN
    coalesce(f.function_id, f.procedure_name, f.name) AS function_id,
    coalesce(f.procedure_name, f.name)                AS function_name,
    f.procedure_name                                  AS procedure_name,
    f.summary                                         AS function_summary,
    bl.title                                          AS title,
    bl.sequence                                       AS sequence,
    bl.coupled_domain                                 AS domain,
    bl.given                                          AS given,
    bl.`when`                                         AS `when`,
    bl.`then`                                         AS `then`
"""


def _rule_id(function_id: str, sequence: Any, title: str) -> str:
    raw = f"{function_id}|{sequence}|{title or ''}"
    return "rule_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def _module_of(function_id: str | None, function_name: str | None) -> str | None:
    fid = function_id or ""
    if "." in fid:
        return fid.rsplit(".", 1)[0]
    if "::" in fid:
        return fid.rsplit("::", 1)[0]
    return None


async def extract_rules_from_analyzer_graph(
    analyzer_graph_ref: str | None = None,
) -> list[RuleDTO]:
    """Pull every meaningful BusinessLogic entry from the analyzer DB as a RuleDTO.

    `analyzer_graph_ref` is currently informational — the analyzer DB is a single
    global graph. The parameter is kept on the interface so a future per-snapshot
    tagging scheme can filter without breaking callers.
    """
    rules: list[RuleDTO] = []
    seen: set[str] = set()

    try:
        with get_session(database=ANALYZER_NEO4J_DATABASE) as s:
            records = list(s.run(_QUERY))
    except Exception as e:
        SmartLogger.log(
            "WARN", "Phase 2 query failed; returning empty rule list",
            category="ingestion.hybrid.code_rules",
            params={"error": str(e), "analyzer_graph_ref": analyzer_graph_ref},
        )
        return []

    for rec in records:
        title = rec.get("title")
        fn_name = rec.get("function_name")
        if is_infra(title, fn_name):
            continue

        given = rec.get("given")
        when = rec.get("when")
        then = rec.get("then")
        if not is_meaningful_gwt(given, when, then):
            continue

        fid = rec.get("function_id") or fn_name or "unknown"
        rid = _rule_id(fid, rec.get("sequence"), title or "")
        if rid in seen:
            continue
        seen.add(rid)

        rules.append(
            RuleDTO(
                id=rid,
                given=(given or "").strip(),
                when=(when or "").strip(),
                then=(then or "").strip(),
                source_function=fn_name,
                source_module=_module_of(fid, fn_name) or rec.get("domain"),
                confidence=1.0,
                title=(title or None),
            )
        )

    SmartLogger.log(
        "INFO", "Phase 2 rule extraction complete",
        category="ingestion.hybrid.code_rules",
        params={"rule_count": len(rules), "raw_records": len(records)},
    )
    return rules
