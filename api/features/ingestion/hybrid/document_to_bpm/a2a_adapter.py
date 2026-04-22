"""Adapt external pdf2bpmn A2A service output into a `ProcessBundle`.

The A2A service returns a result dict of shape::

    {
        "bpmn_xml": "<bpmn:definitions>...</bpmn:definitions>",
        "process_count": <int>,
        "processes": [ { "id": ..., "name": ..., "bpmn_xml": ... }, ... ]
    }

Each `<bpmn:process>` in each XML payload represents ONE business process.
We parse them *independently* — one BpmSkeleton per process — so downstream
retrieval can disambiguate "어느 프로세스의 입력값 검증" via process identity
(see docs/legacy-ingestion/개선&재구조화.md §A.0).

Previously this module flattened all processes into a single skeleton via
`_merge_bpmn_definitions`; that collapse is the root cause of Phase 3's
cross-process contamination. The combined XML is still produced for canvas
rendering, but it is no longer the parsing input.
"""

from __future__ import annotations

import hashlib
import json as _json
import os
import time
import uuid
import xml.etree.ElementTree as ET
from typing import Any, Optional

from api.features.ingestion.hybrid.contracts import (
    BpmActor,
    BpmProcess,
    BpmSequenceDTO,
    BpmSkeleton,
    BpmTaskDTO,
    ProcessBundle,
)
from api.platform.observability.smart_logger import SmartLogger


def _dump_a2a_raw(session_id: str, result: Any) -> None:
    """Write the raw A2A response to /tmp for offline inspection.

    The adapter has been quietly falling back to the native extractor when
    it couldn't find an XML payload inside the A2A response; dumping the
    raw JSON lets us see exactly what shape the server returned so we can
    teach `_collect_bpmn_xmls` about it.

    Controlled by `HYBRID_A2A_DUMP_DIR` env var (default `/tmp/hybrid_a2a_raw`).
    """
    try:
        out_dir = os.getenv("HYBRID_A2A_DUMP_DIR", "/tmp/hybrid_a2a_raw")
        os.makedirs(out_dir, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        fn = os.path.join(out_dir, f"{session_id}_{stamp}.json")
        with open(fn, "w", encoding="utf-8") as fp:
            _json.dump(result, fp, ensure_ascii=False, indent=2, default=str)
        SmartLogger.log(
            "INFO", "A2A raw response dumped",
            category="ingestion.hybrid.a2a_adapter",
            params={"session_id": session_id, "file": fn, "top_keys": list(result.keys()) if isinstance(result, dict) else type(result).__name__},
        )
    except Exception as e:
        SmartLogger.log(
            "WARN", "Failed to dump A2A raw response",
            category="ingestion.hybrid.a2a_adapter",
            params={"error": str(e)},
        )

# BPMN 2.0 namespace
_BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
_NS = {"bpmn": _BPMN_NS}


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _process_id(pdf_name: str, session_id: str, process_name: str) -> str:
    """Stable id for a process within a session — `proc_{sha1(pdf+sid+name)[:12]}`.

    Includes `process_name` so a single PDF with N processes yields N distinct ids.
    """
    raw = f"{pdf_name}|{session_id}|{process_name}".encode("utf-8")
    return f"proc_{hashlib.sha1(raw).hexdigest()[:12]}"


def adapt_a2a_result_to_skeleton(
    result: dict[str, Any],
    *,
    session_id: str = "",
    source_pdf_name: Optional[str] = None,
) -> ProcessBundle:
    """Convert an A2A result (TaskResult or inner result dict) into a `ProcessBundle`.

    The pdf2bpmn A2A server returns a ``TaskResult`` whose BPMN XML lives inside
    ``artifacts[].artifact.parts[].text`` (nested JSON/dict), not at top level.
    We walk the full structure collecting every ``bpmn_xml``. Each payload can
    itself contain multiple ``<bpmn:process>`` elements; each process becomes
    one `BpmSkeleton` in the bundle.

    `session_id` / `source_pdf_name` are stamped onto the per-process
    `BpmProcess.id` hash. Callers that cannot supply them yet (rare) may pass
    empty strings — a downstream Phase 1 step can re-hash with richer inputs.
    """
    _dump_a2a_raw(session_id or "unknown", result)
    xmls = _collect_bpmn_xmls(result)
    # Diagnostic: record what we extracted so we can spot when A2A returned
    # successfully but we still ended up parsing 0 XMLs.
    SmartLogger.log(
        "INFO", "A2A adapter XML collection",
        category="ingestion.hybrid.a2a_adapter",
        params={
            "session_id": session_id,
            "xml_count": len(xmls),
            "xml_lengths": [len(x) for x in xmls],
            "result_top_keys": (
                list(result.keys()) if isinstance(result, dict) else type(result).__name__
            ),
        },
    )
    if not xmls:
        # This pdf2bpmn flavour returns only {status, message} in the A2A
        # response; the real output is written straight to Neo4j as
        # (:Process)-[:HAS_TASK]->(:Task)-[:PERFORMED_BY]->(:Role) plus
        # gateways/events, none of which carry a session_id yet.
        # Harvest those freshly-written side-effect nodes into a bundle.
        neo4j_bundle = _harvest_bundle_from_pdf2bpmn_neo4j(
            session_id=session_id, source_pdf_name=source_pdf_name,
        )
        if neo4j_bundle.processes:
            SmartLogger.log(
                "INFO", "A2A adapter harvested from Neo4j side-effects",
                category="ingestion.hybrid.a2a_adapter",
                params={
                    "session_id": session_id,
                    "process_count": len(neo4j_bundle.processes),
                    "task_total": sum(len(p.tasks) for p in neo4j_bundle.processes),
                },
            )
            return neo4j_bundle
        return ProcessBundle(processes=[])

    skeletons: list[BpmSkeleton] = []
    xml_index = 0
    for xml in xmls:
        try:
            per_xml = parse_bpmn_xml_per_process(xml)
        except ET.ParseError:
            continue
        for process_skel in per_xml:
            xml_index += 1
            raw_name = process_skel.process.name if process_skel.process else ""
            name = raw_name or f"Process {xml_index}"
            pid = _process_id(source_pdf_name or "", session_id, name)
            process_dto = BpmProcess(
                id=pid,
                name=name,
                domain_keywords=[],
                source_pdf_name=source_pdf_name,
                session_id=session_id,
                actor_ids=[a.id for a in process_skel.actors],
                task_ids=[t.id for t in process_skel.tasks],
            )
            process_skel.process = process_dto
            for a in process_skel.actors:
                a.process_id = pid
            for t in process_skel.tasks:
                t.process_id = pid
            for s in process_skel.sequences:
                s.process_id = pid
            skeletons.append(process_skel)

    # Produce a merged combined XML for single-canvas rendering backward compat.
    combined = xmls[0] if len(xmls) == 1 else (_merge_bpmn_definitions(xmls) or xmls[0])
    # Also stamp combined onto the bundle; per-process XML lives on each skeleton.
    return ProcessBundle(processes=skeletons, bpmn_xml=combined)


def _collect_bpmn_xmls(node: Any) -> list[str]:
    """Recursively harvest every ``bpmn_xml`` string found inside ``node``."""
    out: list[str] = []

    def visit(v: Any) -> None:
        if isinstance(v, dict):
            for k, vv in v.items():
                if k == "bpmn_xml" and isinstance(vv, str) and vv.strip().startswith("<"):
                    out.append(vv)
                else:
                    visit(vv)
        elif isinstance(v, list):
            for item in v:
                visit(item)
        elif isinstance(v, str):
            # Some A2A artifact "text" parts hold a stringified JSON payload.
            s = v.strip()
            if s.startswith("{") or s.startswith("["):
                try:
                    import json as _json
                    visit(_json.loads(s))
                except Exception:
                    pass
            elif s.startswith("<") and "bpmn" in s[:200].lower():
                out.append(s)

    visit(node)
    # Deduplicate while preserving order.
    seen: set[str] = set()
    uniq: list[str] = []
    for x in out:
        key = x[:200]  # cheap dedupe key
        if key in seen:
            continue
        seen.add(key)
        uniq.append(x)
    return uniq


def _merge_bpmn_definitions(xmls: list[str]) -> Optional[str]:
    """Merge multiple BPMN documents into one for CANVAS rendering only.

    Used to produce the `ProcessBundle.bpmn_xml` that the frontend canvas shows
    as a unified diagram. Never used as the parsing input — that happens per
    `<bpmn:process>` via `parse_bpmn_xml_per_process`.
    """
    try:
        ET.register_namespace("bpmn", _BPMN_NS)
        base_root = ET.fromstring(xmls[0])
        base_processes = {
            (p.get("id") or f"idx{i}"): p
            for i, p in enumerate(base_root.findall("bpmn:process", _NS))
        }
        for extra in xmls[1:]:
            try:
                extra_root = ET.fromstring(extra)
            except ET.ParseError:
                continue
            for p in extra_root.findall("bpmn:process", _NS):
                pid = p.get("id") or ""
                if pid and pid in base_processes:
                    continue
                base_root.append(p)
                if pid:
                    base_processes[pid] = p
        return ET.tostring(base_root, encoding="unicode")
    except ET.ParseError:
        return None


def parse_bpmn_xml_per_process(bpmn_xml: str) -> list[BpmSkeleton]:
    """Split a BPMN XML doc with N `<bpmn:process>` elements into N skeletons.

    Each returned skeleton has its own Actor/Task/Sequence scoped to ONE
    process. `.process` is set to a *preliminary* BpmProcess (id=empty,
    name = the XML-level process name or id) — the caller stamps final ids
    with session/pdf context. `.bpmn_xml` is set to a minimal per-process
    wrapper so that canvas overlays can target one process independently.
    """
    root = ET.fromstring(bpmn_xml)
    process_els: list[ET.Element] = list(root.findall("bpmn:process", _NS))
    if not process_els:
        for child in root.iter():
            if _strip_ns(child.tag) == "process":
                process_els.append(child)
    if not process_els:
        return []

    # Collect all lanes once so cross-process actor names can dedupe (two
    # processes both referring to "담당자" should share one BpmActor).
    actor_by_name: dict[str, BpmActor] = {}

    out: list[BpmSkeleton] = []
    for process_el in process_els:
        proc_name = (process_el.get("name") or process_el.get("id") or "").strip()
        task_el_by_id: dict[str, ET.Element] = {}
        task_order: list[str] = []
        next_map: dict[str, list[str]] = {}
        has_incoming: set[str] = set()
        for child in process_el.iter():
            tag = _strip_ns(child.tag)
            if tag.endswith("Task") or tag in {
                "task", "userTask", "serviceTask", "manualTask", "scriptTask",
                "businessRuleTask", "sendTask", "receiveTask", "callActivity", "subProcess",
            }:
                tid = child.get("id")
                if not tid or tid in task_el_by_id:
                    continue
                task_el_by_id[tid] = child
                task_order.append(tid)
            elif tag == "sequenceFlow":
                src = child.get("sourceRef")
                tgt = child.get("targetRef")
                if src and tgt:
                    next_map.setdefault(src, []).append(tgt)
                    has_incoming.add(tgt)

        ordered_task_ids = _topological_task_order(task_order, next_map, has_incoming)

        # Lanes for THIS process only
        task_to_actor: dict[str, str] = {}
        local_actors: list[BpmActor] = []
        for lane in process_el.iter():
            if _strip_ns(lane.tag) != "lane":
                continue
            lane_name = (lane.get("name") or lane.get("id") or "").strip() or "System"
            actor = actor_by_name.get(lane_name)
            if not actor:
                actor = BpmActor(id=_new_id("actor"), name=lane_name)
                actor_by_name[lane_name] = actor
            if actor not in local_actors:
                local_actors.append(actor)
            for fr in lane.iter():
                if _strip_ns(fr.tag) != "flowNodeRef":
                    continue
                ref = (fr.text or "").strip()
                if ref:
                    task_to_actor[ref] = actor.id

        if not local_actors:
            default_actor = actor_by_name.get("System") or BpmActor(id=_new_id("actor"), name="System")
            actor_by_name.setdefault("System", default_actor)
            local_actors.append(default_actor)
            default_actor_id = default_actor.id
        else:
            default_actor_id = local_actors[0].id

        tasks: list[BpmTaskDTO] = []
        for idx, tid in enumerate(ordered_task_ids):
            el = task_el_by_id[tid]
            name = (el.get("name") or tid).strip()
            actor_id = task_to_actor.get(tid, default_actor_id)
            tasks.append(BpmTaskDTO(
                id=_new_id("task"),
                name=name,
                sequence_index=idx,
                actor_ids=[actor_id] if actor_id else [],
            ))
        sequence = BpmSequenceDTO(
            id=_new_id("seq"),
            name=proc_name or "Main",
            task_ids=[t.id for t in tasks],
        )
        preliminary = BpmProcess(
            id="",
            name=proc_name,
            session_id="",
            actor_ids=[a.id for a in local_actors],
            task_ids=[t.id for t in tasks],
        )
        skeleton = BpmSkeleton(
            actors=list(local_actors),
            tasks=tasks,
            sequences=[sequence],
            bpmn_xml=None,
            process=preliminary,
        )
        out.append(skeleton)
    return out


async def _backfill_domain_keywords(name: str, description: str) -> list[str]:
    """Ask the LLM to extract 3~8 domain keywords from a process name + description.

    pdf2bpmn's Neo4j output carries rich description/purpose fields but no
    keyword list. We need keywords because Phase 3 Agent uses them as the
    query text for MODULE retrieval. Empty keywords = weaker retrieval.
    """
    if not name and not description:
        return []
    try:
        from api.features.ingestion.hybrid.document_to_bpm.entity_extractor import (
            extract_process_identity,
        )
        # `extract_process_identity` accepts (pdf_name, text); feed the
        # process's description so it can pull keywords.
        ident = await extract_process_identity(
            pdf_name=name,
            first_pages_text=f"프로세스: {name}\n\n{description}",
        )
        return list(ident.domain_keywords or [])
    except Exception as e:
        SmartLogger.log(
            "WARN", "domain_keywords backfill failed",
            category="ingestion.hybrid.a2a_adapter",
            params={"process_name": name, "error": str(e)},
        )
        return []


def _harvest_bundle_from_pdf2bpmn_neo4j(
    *,
    session_id: str = "",
    source_pdf_name: Optional[str] = None,
) -> ProcessBundle:
    """Build a `ProcessBundle` from pdf2bpmn's Neo4j side-effect nodes.

    pdf2bpmn A2A writes its output directly to Neo4j (labels `Process`,
    `Task`, `Role`, `Event`, `Gateway`) instead of returning it in the A2A
    response payload. This helper harvests the freshly-written structure
    (session_id IS NULL — not yet stamped by `relabel_pdf2bpmn_nodes`) and
    converts it to our internal `BpmSkeleton` shape.

    After this runs, `relabel_pdf2bpmn_nodes` should be called to stamp
    session_id + relabel `:Process` → `:BpmnProcess` etc. so the raw
    labels stay free for the next A2A call.
    """
    from api.platform.neo4j import get_session

    try:
        with get_session() as s:
            proc_rows = list(s.run(
                """
                MATCH (p:Process)
                WHERE p.session_id IS NULL AND p.proc_id IS NOT NULL
                RETURN p.proc_id AS proc_id, p.name AS name,
                       p.description AS description, p.purpose AS purpose
                """,
            ))
            if not proc_rows:
                return ProcessBundle(processes=[])

            skeletons: list[BpmSkeleton] = []
            actor_by_name: dict[str, BpmActor] = {}

            for prow in proc_rows:
                proc_id = prow["proc_id"]
                proc_name = prow["name"] or prow.get("description") or "Process"
                proc_description = prow.get("description") or prow.get("purpose") or ""

                task_rows = list(s.run(
                    """
                    MATCH (p:Process {proc_id: $pid})-[:HAS_TASK]->(t:Task)
                    OPTIONAL MATCH (t)-[:PERFORMED_BY]->(r:Role)
                    RETURN t.task_id AS task_id, t.name AS name,
                           t.description AS description, t.instruction AS instruction,
                           t.order AS order_, t.task_type AS task_type,
                           r.role_id AS role_id, r.name AS role_name,
                           r.persona_hint AS role_hint
                    ORDER BY toInteger(coalesce(t.order, '0')), t.task_id
                    """,
                    pid=proc_id,
                ))
                if not task_rows:
                    continue

                local_actors: list[BpmActor] = []
                tasks: list[BpmTaskDTO] = []
                for idx, trow in enumerate(task_rows):
                    role_name = (trow["role_name"] or "System").strip()
                    actor = actor_by_name.get(role_name)
                    if not actor:
                        actor = BpmActor(
                            id=_new_id("actor"), name=role_name,
                            description=trow["role_hint"],
                        )
                        actor_by_name[role_name] = actor
                    if actor not in local_actors:
                        local_actors.append(actor)

                    description = trow["description"] or trow["instruction"]
                    tasks.append(BpmTaskDTO(
                        id=_new_id("task"),
                        name=(trow["name"] or "").strip(),
                        description=(description or "").strip() or None,
                        sequence_index=idx,
                        actor_ids=[actor.id],
                    ))

                pid_hash = _process_id(source_pdf_name or "", session_id, proc_name)
                process_dto = BpmProcess(
                    id=pid_hash,
                    name=proc_name,
                    description=proc_description or None,
                    domain_keywords=[],
                    source_pdf_name=source_pdf_name,
                    session_id=session_id,
                    actor_ids=[a.id for a in local_actors],
                    task_ids=[t.id for t in tasks],
                )
                # Stamp process_id on children for downstream save.
                for a in local_actors:
                    a.process_id = pid_hash
                for t in tasks:
                    t.process_id = pid_hash

                sequence = BpmSequenceDTO(
                    id=_new_id("seq"),
                    name=proc_name or "Main",
                    task_ids=[t.id for t in tasks],
                    process_id=pid_hash,
                )
                skeletons.append(BpmSkeleton(
                    actors=list(local_actors),
                    tasks=tasks,
                    sequences=[sequence],
                    bpmn_xml=None,  # runner will generate via build_bpmn_xml
                    process=process_dto,
                ))
        return ProcessBundle(processes=skeletons)
    except Exception as e:
        SmartLogger.log(
            "WARN", "Failed to harvest pdf2bpmn Neo4j side-effects",
            category="ingestion.hybrid.a2a_adapter",
            params={"error": str(e)},
        )
        return ProcessBundle(processes=[])


def _topological_task_order(
    task_order: list[str],
    next_map: dict[str, list[str]],
    has_incoming: set[str],
) -> list[str]:
    """Order tasks along sequence flows; fall back to document order on cycles."""
    if not task_order:
        return []
    task_set = set(task_order)
    starts = [t for t in task_order if t not in has_incoming]
    if not starts:
        starts = [task_order[0]]

    seen: set[str] = set()
    ordered: list[str] = []
    stack = list(reversed(starts))
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        if cur in task_set:
            ordered.append(cur)
        for nxt in next_map.get(cur, []):
            if nxt not in seen:
                stack.append(nxt)

    for t in task_order:
        if t not in seen:
            ordered.append(t)
    return ordered
