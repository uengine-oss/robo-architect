# Tactical Diff Contract

Output:

```json
{ "tacticalDiff": [], "implementationPlan": { "version": 1, "architectureDecisions": [], "constitutionGaps": [] } }
```

Canonical tactical item fields:

- `nodeId`, `nodeLabel`, `nodeTitle`
- `changeType`: `CREATE`, `MODIFY`, `DELETE`
- `impactLevel`: `HIGH`, `MEDIUM`, `LOW`, `NONE`
- `boundedContextId`, `aggregateId`, `commandId`, `triggerEventId`, `invokeCommandId`, `userStoryRefs`
- `properties`, `fields`, `semanticDiff`

Forbidden aliases:

- `aggregate`, `boundedContext`, `emittedBy`, `trigger`, `invokes`, `traces`

Property/schema keys must be English camelCase.
