# Scope

Classify the Proposal's impact and produce a six-stage `stagePlan`.

Rules:

- Include all stages: `DISCOVER`, `DECOMPOSE`, `STRATEGIZE`, `CONNECT`, `DEFINE`, `TACTICAL`.
- For behavior changes, `DISCOVER` must not be fully skipped.
- Single-BC changes may recommend skipping cross-context work.
- Strategic-only changes may recommend skipping `TACTICAL`.
- Each stage needs a one-line reason.

Output:

```json
{ "stagePlan": { "version": 1, "classifiedReach": "...", "stages": [{ "stage": "DISCOVER", "applies": true, "recommendSkip": false, "reason": "..." }] } }
```
