# Feature Specification: Consume Analyzer Table-Effect Provenance

**Feature Branch**: `050-analyzer-effect-provenance`

**Created**: 2026-07-30

**Status**: In Progress

**Input**: Consume Analyzer spec 109 AFFECTS_TABLE v2 without treating unresolved or inferred
operations as scanner facts.

## User Scenarios & Testing

### User Story 1 - Safe architecture fallback (Priority: P1)

Architect users still receive Aggregate/table grounding when Analyzer knows a table is written
but cannot prove INSERT versus UPDATE versus DELETE. Event verbs are not fabricated from
UNKNOWN.

**Independent Test**: Feed scanner, inferred, unknown-write, and read-only effects through the
consumer normalizer and prompt renderer.

**Acceptance Scenarios**:

1. **Given** `WRITE/UNKNOWN/UNRESOLVED`, **When** Aggregate grounding is built, **Then** the table
   remains a write candidate and no exact event verb is implied.
2. **Given** `WRITE/UPDATE/SCANNER`, **When** Event context is built, **Then** UPDATE is presented
   as authoritative.
3. **Given** `WRITE/UPDATE/LLM_INFERRED`, **When** Event context is built, **Then** it is visibly
   marked inferred.
4. **Given** `READ/READ/SCANNER`, **When** a collection named writes is built, **Then** the effect
   is excluded.

## Requirements

- **FR-001**: All AFFECTS_TABLE query projections used by active ingestion, BPM context,
  traceability, and PRD model data MUST preserve `access`, `op`, and `op_source`.
- **FR-002**: Active `writes` collections MUST include only WRITE or READ_WRITE effects.
- **FR-003**: UNKNOWN writes MUST preserve table grounding.
- **FR-004**: Event-name instructions MUST distinguish authoritative, inferred, and unresolved op.
- **FR-005**: Legacy edges without new properties MUST receive read-only compatibility
  normalization without changing persisted Analyzer data.
- **FR-006**: Inspector table grounding MUST display WRITE for unknown exact operations rather
  than UNKNOWN as if it were a DML verb.

## Success Criteria

- **SC-001**: Consumer tests show zero READ-only entries in writes.
- **SC-002**: UNKNOWN write tables remain available to Aggregate grounding.
- **SC-003**: Rendered event context never maps UNKNOWN mechanically to a lifecycle verb.
- **SC-004**: Targeted Architect API and frontend tests pass.

## Assumptions

- Producer contract is Analyzer
  `specs/109-semantic-handoff-provenance/contracts/affects-table-v2.md`.
- Existing graph fixtures may omit v2 properties; compatibility is read-only.

