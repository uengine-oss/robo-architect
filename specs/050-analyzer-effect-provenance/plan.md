# Implementation Plan: Consume Analyzer Table-Effect Provenance

**Branch**: `main` | **Date**: 2026-07-30 | **Spec**: [spec.md](spec.md)

## Summary

Project the v2 edge properties through active consumers, centralize effect normalization in the
hybrid code-to-rules owner, preserve unknown-write table grounding, and qualify exact operation
evidence in downstream LLM context.

## Technical Context

**Language/Version**: Python 3.11+, Vue 3/JavaScript

**Primary Dependencies**: FastAPI, Pydantic, Neo4j driver, Vue

**Storage**: shared Analyzer Neo4j graph plus Architect graph

**Testing**: pytest/unittest-compatible API tests and focused frontend tests

**Target Platform**: Architect web/Electron backend and frontend

**Constraints**: additive consumer compatibility; no Analyzer writes; no new LLM call

## Constitution Check

The repository does not define a separate current constitution file beyond its project
instructions. The plan follows the workspace principles: evidence-first contract tracing,
no silent precision upgrade, narrow ownership, cross-service contract documentation, and
focused plus regression verification.

## Project Structure

```text
api/features/ingestion/hybrid/contracts.py
api/features/ingestion/hybrid/code_to_rules/
api/features/ingestion/hybrid/bpm_context_builder.py
api/features/ingestion/workflow/phases/events_from_user_stories.py
api/features/canvas_graph/routes/traceability.py
api/features/prd_generation/prd_model_data.py
frontend/src/features/canvas/ui/InspectorPanel.vue
api/features/ingestion/hybrid/tests/
```

**Structure Decision**: normalization lives beside rule extraction because that is the first
active boundary converting Analyzer graph effects into Architect DTOs.

