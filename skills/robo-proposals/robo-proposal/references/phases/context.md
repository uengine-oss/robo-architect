# Context Impact

Build an impact map from Tactical Diff and graph domain nodes.

Return a JSON array of:

```json
{ "nodeId": "US-001", "nodeLabel": "UserStory", "nodeTitle": "...", "conflictLevel": "HIGH", "reason": "..." }
```

Conflict levels:

- `HIGH`: same Aggregate/Command direct modification.
- `MEDIUM`: related UserStory or Feature flow needs branching.
- `LOW`: boundary-level impact.
- `NONE`: no connected domain node.
