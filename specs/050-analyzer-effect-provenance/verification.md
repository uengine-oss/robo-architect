# Verification: Analyzer Effect Provenance Consumer

## Automated evidence

- `PYTHONUTF8=1 python -m pytest api/features/ingestion/hybrid -q`
  - 25 passed.
- `PYTHONUTF8=1 python -m pytest api tests -q -k
  "not test_no_direct_system_message_construction"`
  - 934 passed, 2 skipped, 458 deselected.
- `npm.cmd --prefix frontend run build`
  - production build passed; 5,268 modules transformed.

## Broad-suite baseline finding

`PYTHONUTF8=1 python -m pytest api tests -q` reached 1,385 passing tests and failed six
parameterizations of the pre-existing language chokepoint. The failures are direct
`SystemMessage(...)` calls in these unrelated, untouched files:

- `api/features/ai_design/router.py`
- `api/features/ingestion/workflow/post_coverage.py`
- `api/features/requirements/ddd_wizard/engine.py`
- `api/features/requirements/routes/child_story_generation.py`
- `api/features/requirements/routes/ddd_validation.py`
- `api/features/requirements/routes/epic_feature_propose.py`

An unscoped repository-root pytest invocation also collects bundled
`desktop/resources/runtime/**/win32comext/taskscheduler/test` and crashes in native Windows code;
application test roots must be explicit.

## Contract audit

- Framework and DBMS projections preserve `table`, `access`, `op`, and `op_source`.
- READ effects are excluded from write consumers; WRITE/READ_WRITE with UNKNOWN remains valid
  Aggregate grounding.
- Legacy `{table, op}` entries remain additive with `op_source=LEGACY`.
- SCANNER is authoritative, LLM_INFERRED is a weak hint, and UNRESOLVED cannot carry an exact
  event verb.
- Traceability, PRD projections, BPM prompt context, event naming guidance, and InspectorPanel
  preserve the same distinction.
