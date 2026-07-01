# Reference: Tactical Diff and Architecture Plan

Use this reference only for `SIMPLIFIED_TACTICAL` and `DETAILED_TACTICAL_FROM_DDD`.

## Tactical Items
Allowed `nodeLabel` values:

- `Aggregate`
- `Command`
- `Event`
- `ReadModel`
- `Policy`
- `Invariant`
- `UI`

Required refs and structures:

| nodeLabel | Required refs | Required data |
| --- | --- | --- |
| Aggregate | `boundedContextId` | `fields.rootEntity`, `properties`, `semanticDiff.ops`, `invariants` |
| Command | `aggregateId` | `fields.inputSchema`, `properties`, `userStoryRefs`, `gwt` |
| Event | `commandId` | `fields.payload`, `properties`, `fields.version` |
| ReadModel | `boundedContextId` | `properties`, `userStoryRefs`, `ui` |
| Policy | `boundedContextId`, `triggerEventId`, `invokeCommandId` | `fields.description`, `fields.condition` |

## Properties
Properties are concrete schema entries:

```json
{ "name": "orderId", "type": "UUID", "isKey": true, "isRequired": true, "description": "주문 식별자" }
```

Rules:

- Aggregate root has a key property.
- Command properties match `fields.inputSchema`.
- Event properties match `fields.payload`.
- Complex values should be ValueObjects in Aggregate `semanticDiff.ops`.
- Foreign keys use `isForeignKey: true` and `fkTargetHint`.

## GWT
Every user-facing Command needs at least one GWT scenario:

```json
{
  "scenario": "정상 주문 생성",
  "given": { "name": "Aggregate: Order", "fieldValues": { "status": "NONE" } },
  "when": { "name": "Command: PlaceOrder", "fieldValues": { "customerId": "customer-1" } },
  "then": { "name": "Event: OrderPlaced", "fieldValues": { "status": "PLACED" } }
}
```

`fieldValues` keys must match the related Aggregate, Command, or Event properties.

## ReadModel, Policy, Invariant, UI
- ReadModel is for query/status/list UserStories.
- Policy connects an Event to a follow-up Command.
- Aggregate invariants should name the rule and list verifying commands.
- UI belongs on user-facing Command and ReadModel items.

## Architecture Plan
For `SIMPLIFIED_TACTICAL`, also output `implementationPlan`.

Required architecture aspects:

- `DEPLOYMENT_ENV`
- `INGRESS`
- `SERVICE_MESH_FRAMEWORK`
- `FRONTEND`
- `REPO_MAPPING`

Each aspect must appear in `architectureDecisions` or `constitutionGaps`.

For microservices with multiple Bounded Contexts, also decide:

- `interContextIntegrations[]`: `{fromContext,toContext,message,kind: EVENT|COMMAND|QUERY,sync,rationale}`
- `messagingChannel`: default Kafka unless Constitution says otherwise.
- `serviceDevEnvironments[]`: per-service runtime, dependencies, compose services, and scope note.

For monolith, do not invent service mesh or per-service infra. Use explicit `N/A (monolith)` decisions where appropriate.

## Detailed DDD Tactical Input
For `DETAILED_TACTICAL_FROM_DDD`, use:

- Connect interactions and coupling warnings.
- Define contexts, inbound/outbound messages, ubiquitous language, business decisions.
- Tactical aggregates, invariants, handled commands, created events, state transitions.

The stage artifacts may not contain every property or schema. Infer concrete Aggregate properties, Command input schemas, Event payloads, ReadModels, Policies, Invariants, and UI from the artifact evidence.
