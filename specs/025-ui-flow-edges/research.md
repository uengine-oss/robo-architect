# Phase 0 Research: UI Sticker Flow Edges with Conditional Gateways

**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-05-15

This document captures the decisions made before design. No `[NEEDS CLARIFICATION]` markers remain in the spec; every open question below is resolved here.

---

## D1 — Metamodel naming (`NEXT_UI` vs alternatives)

**Decision**: Relationship type `NEXT_UI`. Node label `Gateway`. Containment edge `HAS_GATEWAY`.

**Rationale**:
- The existing graph already uses snake-cased uppercase relationship names with short, semantic prefixes (`HAS_AGGREGATE`, `HAS_COMMAND`, `HAS_POLICY`, `HAS_UI`, `EMITS`, `IMPLEMENTS`, `ATTACHED_TO`). `NEXT_UI` reads naturally as "next UI in the flow."
- `Gateway` (single word, capitalized) matches `UserStory`, `BoundedContext`, `ReadModel` etc. Avoids the verbosity of `FlowGateway` / `DecisionNode`.
- `HAS_GATEWAY` mirrors `HAS_AGGREGATE` / `HAS_POLICY` for BC ownership.

**Alternatives considered**:
- `FLOWS_TO` / `LEADS_TO` — too generic; a future data-flow relationship might want the same name.
- `NEXT_SCREEN` — accurate but mixes terminology (canvas calls them "UI" / "stickers"); diverges from `HAS_UI`.
- `:FlowEdge` materialized node — would force every transition through a node, complicating queries and rendering. Only branching points need to be nodes (Gateway).

---

## D2 — Idempotent keys (so re-ingest doesn't duplicate)

**Decision**:
- `Gateway.key = "<bc.key>.gateway.<slug(label)>"` (BC-scoped, label-derived).
- `NEXT_UI.id = uuid5(NAMESPACE_OID, f"{source.key}->{target.key}#{condition_slug}")` — deterministic per (source UI/Gateway, target UI/Gateway, condition).

**Rationale**:
- The existing event-storming graph relies on natural-key `key` properties for all idempotent upserts (see `ui.key = ui_key(...)`, `agg.key`, `cmd.key`). Following that pattern means our MERGE statements look identical to the existing `_UI_BULK_CYPHER`.
- LLM output may rephrase the same edge across runs ("after submit" vs "when user clicks submit"). Including `condition_slug` in the edge id prevents accidental collapse of distinct branches, while a stable `slugify` on the condition makes wording drift idempotent within a normalization budget.
- `uuid5` with the OID namespace is already used elsewhere; gives 128-bit collision-free ids without a Neo4j round-trip.

**Alternatives considered**:
- Pure surrogate UUIDs (random) — would duplicate on every re-ingest. Rejected.
- Hash of (source, target) only — would collapse legitimate multi-branch gateways into one edge. Rejected.
- Store edges in a Cypher MERGE by `(source, target)` without an id — works but loses the ability to address an edge from the Inspector for edit/delete; rejected for FR-011/019.

---

## D3 — LLM phase placement in the ingestion pipeline

**Decision**: A new phase `generate_ui_flow_edges_phase` runs **after** `generate_ui_wireframes_phase` (currently phase 11 — last) and **before** the run-summary step. Phase tag: `12_ui_flow_edges`. It is gated by the same `IS_SKIP_UI_PHASE` flag as `ui_wireframes` (if UI phase is skipped, this phase is skipped too, since it has no UIs to reference).

**Rationale**:
- The phase MUST reference existing UI node ids (FR-007), so it has to run after UIs are written to Neo4j and `ctx.uis_by_id` is populated.
- Running it after UI wireframes keeps the dependency direction unambiguous: this phase only reads from already-emitted nodes; it never edits Commands/Events/ReadModels.
- Phase tag follows the existing `NN_<name>` naming used in `workflow/utils/phase_logger.py:171`.
- Skip-flag gating is consistent: if `IS_SKIP_UI_PHASE=true`, there are no UIs, so deriving UI flow would produce zero edges and noise.

**Alternatives considered**:
- Make it a sub-step inside `ui_wireframes` phase — couples two LLM concerns into one phase, hurts streaming UX (the canvas can't show wireframes-ready before flow-ready).
- Run it at the very end after GWT — works but adds latency to the user-visible "wireframes available" moment.
- Run it on-demand from the canvas (not during ingestion) — violates "graph as SOT after ingestion" expectation and forces the user to manually trigger a step that should be automatic.

---

## D4 — Manual-edit preservation across re-ingest

**Decision**: Each `NEXT_UI` edge and `Gateway` node carries `source: 'llm' | 'manual'`. The ingestion phase MUST honor a *non-clobber* rule: it MAY create new edges, but it MUST NOT delete or modify any node/edge whose `source = 'manual'`. Mechanism:
- The phase reads the current graph snapshot before its own MERGEs.
- For each LLM-proposed edge, if the (source, target, condition) tuple matches an existing `manual` edge, skip the upsert entirely (the manual version wins).
- For each existing `llm` edge that is no longer in the new LLM output, the phase deletes it (LLM is authoritative for `llm`-tagged state).
- Manual edges are never deleted by the phase.

**Rationale**:
- This is the standard "user-corrections-as-pins" pattern. The same idea applies to `criteriaUserEdited` in `UserStory` (spec 019). The pattern is known to work and is consistent with Principle IV (human-in-the-loop).
- Tagging via property rather than separate label keeps Cypher queries simple (`MATCH (a)-[r:NEXT_UI {source:'manual'}]->(b)`).

**Alternatives considered**:
- Separate relationship type `MANUAL_NEXT_UI` — doubles the query surface for canvas reads. Rejected.
- Last-write-wins (always overwrite from LLM) — violates SC-004 (manual edits must survive 100%). Rejected.
- Track edits in a sidecar table outside Neo4j — violates Constitution I (single source of truth). Rejected.

---

## D5 — Canvas rendering of new edges and gateways

**Decision**:
- `NEXT_UI` edges: render as **dashed arrows** with stroke color `#9c36b5` (a purple distinct from existing data-flow stroke colors `#5c7cfa` / `#fd7e14` / `#40c057` seen in `EventModelingPanel.vue:936-948`).
- `Gateway` nodes: render as an **SVG `<polygon>` diamond** (rhombus) with `fill="#fff8db"` and `stroke="#f08c00"` (warm yellow — visually distinct from existing rectangular stickers). Default size 88×56 px; label centered.
- Condition labels on edges out of a Gateway: rendered with the existing edge-label pattern (small floating `<text>` near the midpoint of the path), max 24 chars before ellipsis.
- Layout: `NEXT_UI` edges live in the **UI swimlane** (the top row already used by UI stickers). A Gateway is laid out inline at the swimlane height. The renderer must not pull a Gateway into a non-UI swimlane.

**Rationale**:
- The component already has the SVG primitives for arrows and labels (see polygon arrowheads in `EventModelingPanel.vue:936-948`); adding a dashed variant + a diamond is a small extension, not a rewrite.
- Color and stroke-dasharray together give a visual contract that is colorblind-friendlier than color alone.
- Keeping Gateways in the UI swimlane preserves the "UI-layer flow" mental model — the flow is between screens, the Gateway is a decision *between screens*, not a backend artifact.

**Alternatives considered**:
- Render Gateways as a separate node component (Vue Flow custom node) — heavier; the canvas is currently SVG-native. Rejected for v1 to keep the change scoped.
- Render all flow on a parallel canvas — duplicates the canvas; rejected.

---

## D6 — Gateway kind handling (LLM may emit parallel/inclusive)

**Decision**: V1 supports only `kind='exclusive'`. If the LLM output describes a parallel/inclusive gateway, the phase downgrades it to exclusive: each path is materialized as its own outgoing edge from a single exclusive gateway. The downgrade emits a `GenerationWarning {code: 'gateway_kind_downgrade', original_kind: ..., gateway_key: ...}`.

**Rationale**:
- BPMN purists would want all gateway kinds; pragmatically, the user explicitly said "복잡한 게이트웨이까지는 필요가 없어 — 그냥 마름모 형태로" ("no need for complex gateways — just a diamond"). Exclusive is the simplest and covers the dominant case in product flows.
- Reserving the `kind` property now (FR-002) means a future spec can add `parallel`/`inclusive` without schema migration.
- A warning rather than a silent collapse keeps the modeler informed.

**Alternatives considered**:
- Drop the LLM's parallel hint silently — invisible loss of intent. Rejected.
- Implement all BPMN kinds now — scope creep; rejected for v1.

---

## Resolved open items

All `[NEEDS CLARIFICATION]` markers from the spec template are resolved by D1–D6 above. No further research is required before Phase 1.
