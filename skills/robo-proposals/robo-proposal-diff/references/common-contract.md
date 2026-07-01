# Reference: Common Diff Contract

## JSON Envelope
Return one final JSON object after narration. The backend extracts the JSON block and validates it before saving.

Strategic outputs:

```json
{ "action": "done", "strategicDiff": { "version": 1, "epics": [], "features": [], "userStories": [], "processes": [] }, "journeys": [] }
```

Tactical outputs:

```json
{ "tacticalDiff": [], "implementationPlan": { "version": 1, "architectureDecisions": [], "constitutionGaps": [] } }
```

## Traceability
- Every CREATE item needs a stable batch-local id.
- Strategic ids use `tempId`; tactical ids use `nodeId`.
- Suggested prefixes: `EP-`, `FT-`, `US-`, `PROC-`, `AGG-`, `CMD-`, `EVT-`, `RM-`, `POL-`, `INV-`, `UI-`.
- Children reference parents by temp id or existing graph id.

Relationship refs:

| Item | Ref field |
| --- | --- |
| Feature | `epicId` |
| UserStory | `featureId`, `boundedContextId` |
| Aggregate | `boundedContextId` |
| Command | `aggregateId`, `userStoryRefs` |
| Event | `commandId` |
| ReadModel | `boundedContextId`, `userStoryRefs` |
| Policy | `boundedContextId`, `triggerEventId`, `invokeCommandId` |

## Canonical Naming
Use only canonical fields. These aliases are forbidden:

| Forbidden | Use |
| --- | --- |
| `aggregate` | `aggregateId` |
| `boundedContext` | `boundedContextId` |
| `emittedBy` | `commandId` |
| `trigger` | `triggerEventId` |
| `invokes` | `invokeCommandId` |
| `traces` | `userStoryRefs` |
| `fields.parameters` string | `fields.inputSchema` object + `properties` |
| `fields.payload` string | `fields.payload` object + `properties` |

Property and schema keys must be English camelCase.

## Self Check
- All Strategic items have `op`, `entityType`, `entityTitle`, and CREATE ids.
- Every UserStory has `role`, `action`, `benefit`, `featureId`, `boundedContextId`.
- Every tactical node has `nodeId`, `nodeLabel`, `nodeTitle`, `changeType`, `impactLevel`, and a reason.
- No Aggregate/Command/Event/ReadModel is name-only.
- Backend validator feedback, if present, has been fully addressed.
