# Specifications — Robo Architect (MSAez)

> **Backfilled** on 2026-05-06 by reverse-engineering the existing codebase using the [GitHub spec-kit](https://github.com/github/spec-kit) format. Each `spec.md` was derived from the actual implementation (routers, agents, Vue components, Cypher queries) — not from a prior design doc. Endpoint paths, Neo4j labels, and UI behaviors are grounded in code as of the `figma-integration` branch.

## How to use these specs

- **Onboarding**: read in numbered order to understand what the system does, feature by feature, in business-oriented language.
- **Change planning**: when modifying a feature, update its `spec.md` first; the spec is the contract, the code is the implementation.
- **New features**: use `/speckit-specify` to create `specs/NNN-<short-name>/spec.md` before writing code. The constitution at `.specify/memory/constitution.md` describes the principles new specs must comply with.
- **Validation**: each spec follows the spec-kit template (User Scenarios, Functional Requirements, Key Entities, Success Criteria, Assumptions). When code drifts from a spec, either update the spec to reflect the new reality or reconcile the code.

## Constitution

- [`.specify/memory/constitution.md`](../.specify/memory/constitution.md) — 7 principles that the codebase already embodies (graph-as-source-of-truth, Event Storming vocabulary, streaming-first UX, human-in-the-loop on mutations, feature-modular architecture, provider-agnostic LLM, observable by default).

## Feature index

### Ingestion & input
| # | Spec | One-liner |
|---|------|-----------|
| 001 | [Requirements Ingestion (SSE)](001-requirements-ingestion-sse/spec.md) | Upload requirement docs/text and stream LLM-driven Event Storming extraction into Neo4j |
| 009 | [Figma Sync (bidirectional)](009-figma-sync-bidirectional/spec.md) | Pull Figma frames into the canvas, push wireframes back; live plugin bridge over WebSocket |
| 013 | [Confluence Page Ingestion](013-confluence-ingest/spec.md) | Pull Confluence pages as a requirements source for the ingestion pipeline |

### Exploration & navigation
| # | Spec | One-liner |
|---|------|-----------|
| 002 | [Canvas Graph Explorer](002-canvas-graph-explorer/spec.md) | Interactive Vue Flow canvas with lazy node expansion and event-trigger traversal |
| 003 | [Contexts Tree Navigator](003-contexts-tree-navigator/spec.md) | Left-side panel tree of Bounded Contexts → Aggregates → Commands → Events; drag-to-canvas |
| 010 | [GWT Event Modeling](010-event-modeling-gwt/spec.md) | Given/When/Then scenario editor attached to Command nodes |
| 011 | [BPMN Process Export](011-bpmn-process-export/spec.md) | Generate BPMN-XML process flows from command/event chains |
| 012 | [Timeline & Traceability](012-timeline-traceability/spec.md) | Big-picture cross-BC event timeline plus per-element upstream/downstream traceability |

### Editing & change management
| # | Spec | One-liner |
|---|------|-----------|
| 004 | [Change Impact & Planning](004-change-impact-planning/spec.md) | LLM-assisted impact analysis → change plan → human-approved apply pipeline |
| 005 | [Model Modifier Chat](005-model-modifier-chat/spec.md) | Streaming ReAct chat to modify a node, with screenshot-to-wireframe inference |
| 006 | [ReadModel / CQRS Config](006-readmodel-cqrs-config/spec.md) | Define ReadModel projections, CQRS operations, mappings and WHERE filters |
| 008 | [User Story Authoring (Planning Agent)](008-user-story-planning-agent/spec.md) | LangGraph agent that scopes a new GWT story and proposes graph changes |

### Output & integration
| # | Spec | One-liner |
|---|------|-----------|
| 007 | [PRD / Agent Context Export](007-prd-generation-export/spec.md) | Generate PRD + Cursor/Claude agent context bundles as a downloadable ZIP |
| 014 | [Document Export with Templates](014-document-export-template/spec.md) | Frontend-driven `.docx`/`.pptx`/PDF export of selected design artifacts |
| 015 | [Claude Code Terminal](015-claude-code-terminal/spec.md) | Embedded WebSocket PTY bridge plus project setup helper for Claude Code / Cursor |

## Backfill methodology

This is a **reverse-engineered** spec set. Each spec was produced by:

1. Identifying a coherent unit of user-visible capability (e.g., "ingestion", "change planning") rather than splitting by file.
2. Reading the relevant routers, services, agent code, and Vue components for that feature.
3. Writing the spec in WHAT/WHY language: user stories with priorities, observable functional requirements, real Neo4j entities, measurable (technology-agnostic) success criteria, and the assumptions baked into the implementation.
4. Calling out edge cases that the code clearly handles or fails on (e.g., "DELETE /api/ingest/clear-all wipes the entire database" → flagged as a destructive intent edge).

Where the original feature inventory had endpoint paths or argument shapes wrong, the per-spec agent **corrected them against the code** rather than carrying the inaccuracy forward (notably for `/api/graph/timeline`, BPMN routes, and a few PRD generator endpoints).

Specs are intentionally short (~100-130 lines each) — they describe the contract, not the code.

## Next steps

- `/speckit-clarify` — run on any spec where you want a structured Q&A pass to de-risk ambiguity.
- `/speckit-checklist` — generate quality checklists per spec before treating them as authoritative.
- `/speckit-analyze` — cross-spec consistency review (recommended once a few new specs exist alongside backfilled ones).
- `/speckit-plan` then `/speckit-tasks` — for any new feature, after `/speckit-specify`.
