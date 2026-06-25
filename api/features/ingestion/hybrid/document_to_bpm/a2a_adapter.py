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
import re
import time
import uuid
import xml.etree.ElementTree as ET
from typing import Any, Optional

from api.features.ingestion.hybrid.contracts import (
    BpmActor,
    BpmFlowDTO,
    BpmGatewayDTO,
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
            for g in process_skel.gateways:
                g.process_id = pid
            for fl in process_skel.flows:
                fl.process_id = pid
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


def merge_process_bundles(bundles: list[ProcessBundle]) -> ProcessBundle:
    """Stack `ProcessBundle`s from separate A2A runs (e.g. one PDF per run).

    Combined ``bpmn_xml`` is for canvas preview only; per-process XML lives on
    each ``BpmSkeleton`` (same rules as ``_merge_bpmn_definitions`` for id clashes).
    """
    if not bundles:
        return ProcessBundle(processes=[], bpmn_xml=None)
    processes: list[BpmSkeleton] = []
    xmls: list[str] = []
    for b in bundles:
        processes.extend(b.processes)
        bx = b.bpmn_xml
        if bx and str(bx).strip():
            xmls.append(str(bx))
    combined: Optional[str] = None
    if xmls:
        combined = xmls[0] if len(xmls) == 1 else (_merge_bpmn_definitions(xmls) or xmls[0])
    return ProcessBundle(processes=processes, bpmn_xml=combined)


_TASK_TAGS = {
    "task", "userTask", "serviceTask", "manualTask", "scriptTask",
    "businessRuleTask", "sendTask", "receiveTask", "callActivity", "subProcess",
}


def _is_task_tag(tag: str) -> bool:
    return tag.endswith("Task") or tag in _TASK_TAGS


def _gateway_type_from_tag(tag: str) -> str:
    """`exclusiveGateway` → `exclusive`, `parallelGateway` → `parallel`, …"""
    if tag.endswith("Gateway"):
        base = tag[: -len("Gateway")].strip()
        return base.lower() or "exclusive"
    return "exclusive"


def _rewrite_ids_in_xml(xml_str: str, id_remap: dict[str, str]) -> str:
    """Rewrite flow-node ids in a BPMN XML string to robo ids, preserving the
    original formatting/namespaces/DI verbatim (string-level, no ET round-trip).

    Ids appear (a) quoted in attributes (`id="…"`, `sourceRef="…"`,
    `targetRef="…"`, `bpmnElement="…"`) and (b) as element text
    (`<incoming>…</incoming>`, `<flowNodeRef>…</flowNodeRef>`). Both forms are
    full-token, so quoted/boundary replacement is collision-safe. Longest ids
    first so a shorter id can't clobber a longer one it's a prefix of.
    """
    for old, new in sorted(id_remap.items(), key=lambda kv: -len(kv[0])):
        xml_str = xml_str.replace(f'"{old}"', f'"{new}"')
        xml_str = re.sub(rf">\s*{re.escape(old)}\s*<", f">{new}<", xml_str)
    return xml_str


def parse_bpmn_xml_per_process(bpmn_xml: str) -> list[BpmSkeleton]:
    """Split a BPMN XML doc with N `<bpmn:process>` elements into N skeletons.

    Each returned skeleton carries this process's Actor/Task/**Gateway** graph
    plus the full sequenceFlow topology (`flows`), so the extractor's branch
    structure survives intact instead of being flattened to a linear chain.
    `.process` is a *preliminary* BpmProcess (id="") that the caller stamps with
    session/pdf context.

    `.bpmn_xml` preserves the extractor's ORIGINAL per-process XML verbatim (its
    own diagram/DI + gateways) for faithful canvas rendering. Flow-node ids are
    rewritten to robo ids (`Task_<taskId>` / `Gateway_<gwId>`) so the canvas
    element id resolves back to the persisted node (dblclick → inspector), and
    so `flows`/nodes share one id space.
    """
    root = ET.fromstring(bpmn_xml)
    process_els: list[ET.Element] = list(root.findall("bpmn:process", _NS))
    if not process_els:
        for child in root.iter():
            if _strip_ns(child.tag) == "process":
                process_els.append(child)
    if not process_els:
        return []

    single_process_doc = len(process_els) == 1

    # Collect all lanes once so cross-process actor names can dedupe (two
    # processes both referring to "담당자" should share one BpmActor).
    actor_by_name: dict[str, BpmActor] = {}

    out: list[BpmSkeleton] = []
    for process_el in process_els:
        proc_name = (process_el.get("name") or process_el.get("id") or "").strip()
        task_el_by_id: dict[str, ET.Element] = {}
        task_order: list[str] = []
        gw_el_by_id: dict[str, ET.Element] = {}
        seq_flows: list[dict] = []  # {id, src, tgt, name, condition}
        next_map: dict[str, list[str]] = {}
        has_incoming: set[str] = set()
        for child in process_el.iter():
            tag = _strip_ns(child.tag)
            if _is_task_tag(tag):
                tid = child.get("id")
                if not tid or tid in task_el_by_id:
                    continue
                task_el_by_id[tid] = child
                task_order.append(tid)
            elif tag.endswith("Gateway"):
                gid = child.get("id")
                if gid and gid not in gw_el_by_id:
                    gw_el_by_id[gid] = child
            elif tag == "sequenceFlow":
                src = child.get("sourceRef")
                tgt = child.get("targetRef")
                if src and tgt:
                    next_map.setdefault(src, []).append(tgt)
                    has_incoming.add(tgt)
                    cond = None
                    for sub in child:
                        if _strip_ns(sub.tag) == "conditionExpression":
                            cond = (sub.text or "").strip() or None
                    seq_flows.append({
                        "id": child.get("id") or _new_id("flow"),
                        "src": src, "tgt": tgt,
                        "name": (child.get("name") or "").strip(),
                        "condition": cond,
                    })

        ordered_task_ids = _topological_task_order(task_order, next_map, has_incoming)

        # Lanes for THIS process only — a flowNodeRef may point at a task OR a gateway.
        node_to_actor: dict[str, str] = {}
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
                    node_to_actor[ref] = actor.id

        if not local_actors:
            default_actor = actor_by_name.get("System") or BpmActor(id=_new_id("actor"), name="System")
            actor_by_name.setdefault("System", default_actor)
            local_actors.append(default_actor)
            default_actor_id = default_actor.id
        else:
            default_actor_id = local_actors[0].id

        # robo ids per flow node + XML-id rewrite map (Task_/Gateway_ prefixed so
        # the canvas element id still resolves to the persisted node).
        xmlid_to_roboid: dict[str, str] = {}
        xml_rewrite: dict[str, str] = {}

        tasks: list[BpmTaskDTO] = []
        for idx, tid in enumerate(ordered_task_ids):
            el = task_el_by_id[tid]
            name = (el.get("name") or tid).strip()
            actor_id = node_to_actor.get(tid, default_actor_id)
            robo_id = _new_id("task")
            xmlid_to_roboid[tid] = robo_id
            xml_rewrite[tid] = f"Task_{robo_id}"
            tasks.append(BpmTaskDTO(
                id=robo_id,
                name=name,
                sequence_index=idx,
                actor_ids=[actor_id] if actor_id else [],
            ))

        gateways: list[BpmGatewayDTO] = []
        for gid, el in gw_el_by_id.items():
            robo_id = _new_id("gw")
            xmlid_to_roboid[gid] = robo_id
            xml_rewrite[gid] = f"Gateway_{robo_id}"
            actor_id = node_to_actor.get(gid)
            gateways.append(BpmGatewayDTO(
                id=robo_id,
                name=(el.get("name") or "").strip(),
                gateway_type=_gateway_type_from_tag(_strip_ns(el.tag)),
                actor_ids=[actor_id] if actor_id else [],
            ))

        # Flows over the full topology. Endpoints that aren't persisted flow
        # nodes (start/end/intermediate events) become `__boundary__*` so the
        # persistence MATCH skips them rather than dangling.
        flows: list[BpmFlowDTO] = []
        for f in seq_flows:
            src = xmlid_to_roboid.get(f["src"], f"__boundary__{f['src']}")
            tgt = xmlid_to_roboid.get(f["tgt"], f"__boundary__{f['tgt']}")
            flows.append(BpmFlowDTO(
                id=f["id"], source_id=src, target_id=tgt,
                name=f["name"], condition=f["condition"],
            ))

        # Preserve the extractor's faithful XML (diagram + gateways), with
        # flow-node ids rewritten to robo ids.
        if single_process_doc:
            per_xml = _rewrite_ids_in_xml(bpmn_xml, xml_rewrite)
        else:
            per_xml = _rewrite_ids_in_xml(ET.tostring(process_el, encoding="unicode"), xml_rewrite)

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
            gateways=gateways,
            flows=flows,
            bpmn_xml=per_xml,
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
    from api.features.ingestion.hybrid.ontology.schema import L_BPMN_PROCESS

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
            # proc_ids actually harvested into this bundle. We relabel them to
            # :BpmnProcess + stamp session_id below so a *subsequent* per-PDF
            # harvest (this fn runs once per uploaded PDF, all sharing one
            # default DB) does not re-match these still-`:Process` nodes via
            # `session_id IS NULL` and re-stamp them with the wrong PDF's
            # source_pdf_name. Without this, every process collapses to the
            # last PDF's source_pdf_name.
            harvested_proc_ids: list[str] = []

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
                harvested_proc_ids.append(proc_id)

            # Isolate this PDF's harvest: relabel the consumed :Process nodes so
            # the next PDF's harvest cannot re-pick them (see note above). Same
            # operation the end-of-phase relabel_pdf2bpmn_nodes performs, scoped
            # to exactly the proc_ids we just consumed.
            if harvested_proc_ids:
                s.run(
                    f"MATCH (p:Process) "
                    f"WHERE p.proc_id IN $pids AND p.session_id IS NULL "
                    f"SET p:{L_BPMN_PROCESS}, p.session_id = $sid "
                    f"REMOVE p:Process",
                    pids=harvested_proc_ids, sid=session_id,
                )
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
