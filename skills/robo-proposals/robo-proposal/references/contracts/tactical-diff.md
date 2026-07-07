# Tactical Diff Contract

Authoritative validator: `api/features/proposal_lifecycle/services/tactical_contract.py`
(`validate_tactical_diff_contract`). This document mirrors that source — keep them in
sync when the validator changes. **You do not need to read the backend source to pass
validation; the full shape is below.**

Output envelope:

```json
{ "tacticalDiff": [], "implementationPlan": { "version": 1, "architectureDecisions": [], "constitutionGaps": [] } }
```

`tacticalDiff` must be a **non-empty list** of node items.

## Common item fields

| Field | Required | Shape / enum |
|---|---|---|
| `nodeId` | yes | Unique string id. Other items reference it by this value. |
| `nodeLabel` | yes | One of `Aggregate`, `Command`, `Event`, `ReadModel`, `Policy`, `UI`, `Invariant`. **`ValueObject` and `BoundedContext` are NOT valid tactical labels.** |
| `nodeTitle` | yes | Human-readable title (non-empty). |
| `changeType` | recommended | `CREATE`, `MODIFY`, or `DELETE`. |
| `impactLevel` | recommended | `HIGH`, `MEDIUM`, `LOW`, or `NONE`. |
| `properties` | see table | **Non-empty list** of `{ "name": <camelCase>, "type": <string> }`. Required for `Aggregate`, `Command`, `Event`, `ReadModel`. |
| `fields` | see table | Object; required sub-keys depend on label (below). |
| ref fields | see table | `boundedContextId`, `aggregateId`, `commandId`, `triggerEventId`, `invokeCommandId`, `userStoryRefs`. |

**Forbidden legacy aliases** (use the canonical ref instead): `aggregate`→`aggregateId`,
`boundedContext`→`boundedContextId`, `emittedBy`→`commandId`, `trigger`→`triggerEventId`,
`invokes`→`invokeCommandId`, `traces`→`userStoryRefs`.

All property names and all schema/`fieldValues` **keys must be English camelCase**
(`^[a-z][A-Za-z0-9]*$`).

## Per-label requirements

| Label | Required ref(s) | Required `fields` | `properties` | Other |
|---|---|---|---|---|
| **Aggregate** | `boundedContextId` (may be external — any string) | `fields.rootEntity` (non-empty string) | non-empty list | — |
| **Command** | `aggregateId` (**must equal another item's `nodeId`**) | `fields.inputSchema` = non-empty object, keys camelCase | non-empty list | `userStoryRefs` = non-empty list; `gwt` required (see below) |
| **Event** | `commandId` (**must equal another item's `nodeId`**) | `fields.payload` = non-empty object, keys camelCase | non-empty list | — |
| **ReadModel** | `boundedContextId` (may be external) | — | non-empty list | `userStoryRefs` = non-empty list |
| **Policy** | `boundedContextId` (external ok), `triggerEventId` + `invokeCommandId` (**must equal other items' `nodeId`**) | — | — | — |
| **UI** | `boundedContextId` (may be external) | — | — | — |
| **Invariant** | — | — | — | — |

"must equal another item's `nodeId`" = the referenced node must also appear in the same
`tacticalDiff` list (unresolved refs are rejected as `unresolved_ref`). `boundedContextId`
is allowed to be external (it is not required to resolve to another item).

## GWT (Command only) — the most common failure

`gwt` on a Command is a **non-empty list of scenarios**. Each scenario is an **object**
with three keys `given` / `when` / `then`, and **each of those is an object holding a
`fieldValues` object** (NOT a string, NOT an array of strings):

```json
"gwt": [
  {
    "given": { "fieldValues": { "cartId": "cart-1" } },
    "when":  { "fieldValues": { "productId": "prod-1", "quantity": 2 } },
    "then":  { "fieldValues": { "productId": "prod-1", "quantity": 2 } }
  }
]
```

`fieldValues` **keys must match related property names**, and matching is only enforced
when the related node has properties:

- `given.fieldValues` keys ⊆ the **Aggregate** (`aggregateId`) `properties[].name`.
- `when.fieldValues` keys ⊆ this **Command**'s own `properties[].name`.
- `then.fieldValues` keys ⊆ the **Event(s) emitted by this command**'s `properties[].name`
  (an Event whose `commandId` equals this Command's `nodeId`).

## Minimal valid example (copy and adapt)

```json
{
  "tacticalDiff": [
    { "nodeId": "AGG-cart", "nodeLabel": "Aggregate", "nodeTitle": "장바구니",
      "changeType": "CREATE", "impactLevel": "HIGH",
      "boundedContextId": "BC-order",
      "properties": [ { "name": "cartId", "type": "UUID" }, { "name": "items", "type": "List" } ],
      "fields": { "rootEntity": "Cart" } },

    { "nodeId": "CMD-addToCart", "nodeLabel": "Command", "nodeTitle": "장바구니에 담기",
      "changeType": "CREATE", "impactLevel": "HIGH",
      "aggregateId": "AGG-cart",
      "userStoryRefs": ["US-add-to-cart"],
      "properties": [ { "name": "productId", "type": "UUID" }, { "name": "quantity", "type": "Integer" } ],
      "fields": { "inputSchema": { "productId": "UUID", "quantity": "Integer" } },
      "gwt": [ {
        "given": { "fieldValues": { "cartId": "cart-1" } },
        "when":  { "fieldValues": { "productId": "prod-1", "quantity": 2 } },
        "then":  { "fieldValues": { "productId": "prod-1", "quantity": 2 } }
      } ] },

    { "nodeId": "EVT-itemAdded", "nodeLabel": "Event", "nodeTitle": "상품 담김",
      "changeType": "CREATE", "impactLevel": "MEDIUM",
      "commandId": "CMD-addToCart",
      "properties": [ { "name": "productId", "type": "UUID" }, { "name": "quantity", "type": "Integer" } ],
      "fields": { "payload": { "productId": "UUID", "quantity": "Integer" } } }
  ],
  "implementationPlan": { "version": 1, "architectureDecisions": [], "constitutionGaps": [] }
}
```
