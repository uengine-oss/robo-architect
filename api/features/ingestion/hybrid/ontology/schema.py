"""Neo4j labels & relationship types for the hybrid ingestion ontology.

Kept disjoint from existing event_storming labels so the new pipeline can coexist
with the legacy BPMN synthesis route.
"""

from __future__ import annotations

# Nodes
L_BPM_PROCESS = "BpmProcess"  # top-level process identity (§2.A of 개선&재구조화.md)
L_BPM_TASK = "BpmTask"
L_BPM_SEQUENCE = "BpmSequence"
L_BPM_ACTOR = "BpmActor"  # separate from existing Actor to avoid polluting analyzer graph
L_RULE = "Rule"
L_ACTIVITY_MAPPING = "ActivityMapping"
L_GLOSSARY_TERM = "GlossaryTerm"
L_EXTERNAL_TABLE = "ExternalTable"  # shadow of analyzer Table (hybrid DB side)
L_DOCUMENT_PASSAGE = "DocumentPassage"
L_HYBRID_SESSION = "HybridSession"  # session marker — bpmn_xml + metadata

# pdf2bpmn extractor 가 기본 DB에 남기는 노드들 — 충돌 회피 위해 hybrid 쪽에서 `Bpmn*` 로 relabel.
# 각 라벨은 pdf2bpmn 만의 고유 프로퍼티로 식별 가능 (event_type/gateway_type/proc_id).
L_BPMN_EVENT = "BpmnEvent"       # was :Event  (pdf2bpmn start/end/intermediate events)
L_BPMN_GATEWAY = "BpmnGateway"   # was :Gateway
L_BPMN_PROCESS = "BpmnProcess"   # was :Process (BPMN process 정의)

# Relationships
R_PERFORMS = "PERFORMS"  # (BpmActor)-[:PERFORMS]->(BpmTask)
R_NEXT = "NEXT"  # (BpmTask)-[:NEXT]->(BpmTask)
R_CONTAINS = "CONTAINS"  # (BpmSequence)-[:CONTAINS]->(BpmTask)
R_REALIZED_BY = "REALIZED_BY"  # (BpmTask)-[:REALIZED_BY {confidence}]->(Rule)
R_USES = "USES"  # (BpmTask)-[:USES]->(FUNCTION)  — bridge to analyzer graph
R_EVALUATES = "EVALUATES"  # (Rule)-[:EVALUATES]->(Column|Table)
R_PROMOTED_TO = "PROMOTED_TO"  # (BpmTask)-[:PROMOTED_TO]->(Command|Event|Policy|Aggregate)
R_SOURCED_FROM = "SOURCED_FROM"  # (BpmTask)-[:SOURCED_FROM {score, rank}]->(DocumentPassage)
R_HAS_TASK = "HAS_TASK"  # (BpmProcess)-[:HAS_TASK]->(BpmTask)
R_HAS_ACTOR = "HAS_ACTOR"  # (BpmProcess)-[:HAS_ACTOR]->(BpmActor)
R_IMPLEMENTED_BY = "IMPLEMENTED_BY"  # (BpmProcess)-[:IMPLEMENTED_BY {confidence, method}]->(MODULE)

ALL_HYBRID_LABELS = [
    L_BPM_PROCESS,
    L_BPM_TASK,
    L_BPM_SEQUENCE,
    L_BPM_ACTOR,
    L_RULE,
    L_ACTIVITY_MAPPING,
    L_GLOSSARY_TERM,
    L_EXTERNAL_TABLE,
    L_DOCUMENT_PASSAGE,
    L_HYBRID_SESSION,
    L_BPMN_EVENT,
    L_BPMN_GATEWAY,
    L_BPMN_PROCESS,
]
