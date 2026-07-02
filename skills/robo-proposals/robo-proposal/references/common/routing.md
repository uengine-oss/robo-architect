# Routing

Use explicit input first:

- `mode: SIMPLIFIED` routes to Strategic Diff, Plan, Tasks, Implement, Test.
- `mode: DETAILED_DDD` routes to Scope, DDD stages, Diff consolidation, Plan, Tasks, Implement, Test.
- `phase:` may be `START_OR_RESUME`, `SCOPE`, `STRATEGIC_DDD`, `STRATEGIC_DIFF`, `TACTICAL_DDD`, `TACTICAL_DIFF`, `CONSTITUTION`, `CONTEXT`, `TASKS`, `IMPLEMENT`, `TEST`, `SUBMIT`, or `ACCEPT`.
- `stage:` may be `DISCOVER`, `DECOMPOSE`, `STRATEGIZE`, `CONNECT`, `DEFINE`, or `TACTICAL`.
- `scenario:` may be `SIMPLIFIED_STRATEGIC`, `SIMPLIFIED_TACTICAL`, `DETAILED_STRATEGIC_FROM_DDD`, or `DETAILED_TACTICAL_FROM_DDD`.

When explicit routing is absent, call `proposal_list` or `proposal_get`, then `proposal_next_step`. If the returned step requires a pending question or draft decision, restore that context before generating anything new.
