# Diff

Use `scenario:` exactly.

- `SIMPLIFIED_STRATEGIC`: natural language requirement to Strategic Diff only.
- `SIMPLIFIED_TACTICAL`: approved Strategic Diff plus Constitution to Tactical Diff and `implementationPlan`.
- `DETAILED_STRATEGIC_FROM_DDD`: Discover/Decompose/Strategize artifacts to Strategic Diff.
- `DETAILED_TACTICAL_FROM_DDD`: Connect/Define/Tactical artifacts to Tactical Diff.

Strategic scenarios must not emit Tactical Diff. Tactical scenarios must use canonical tactical fields only.

If truly blocked in `SIMPLIFIED_STRATEGIC`, return one `clarify` question.
