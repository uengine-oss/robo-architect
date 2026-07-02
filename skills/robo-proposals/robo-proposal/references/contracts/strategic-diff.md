# Strategic Diff Contract

Output:

```json
{ "action": "done", "strategicDiff": { "version": 1, "epics": [], "features": [], "userStories": [], "processes": [] }, "journeys": [] }
```

Each entry should include:

- `op`: `CREATE`, `MODIFY`, or `DELETE`
- `entityType`
- `entityId` or `tempId`
- `entityTitle`
- `fields` when useful
- parent refs such as `epicId`, `featureId`, or `boundedContextId`

For clarify:

```json
{ "action": "clarify", "questions": [{ "index": 0, "text": "...", "options": ["...", "..."] }] }
```
