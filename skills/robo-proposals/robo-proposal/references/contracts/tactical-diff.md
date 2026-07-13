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
| `nodeLabel` | yes | One of `Aggregate`, `ValueObject`, `Enumeration`, `Command`, `Event`, `ReadModel`, `Policy`, `UI`, `Invariant`. **`BoundedContext` is NOT a valid tactical label** (it comes from the strategic Epic). |
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
| **Aggregate** | `boundedContextId` (**must be a known BoundedContext** — see below) | `fields.rootEntity` (non-empty string) | non-empty list | — |
| **ValueObject** | `aggregateId` (**must equal another item's `nodeId`**) | `fields.typeName` = English **PascalCase** type name | non-empty list (the VO's fields) | — |
| **Enumeration** | `aggregateId` (**must equal another item's `nodeId`**) | `fields.typeName` (PascalCase) + `fields.items` = non-empty list of literals | — | — |
| **Command** | `aggregateId` (**must equal another item's `nodeId`**) | `fields.inputSchema` = non-empty object, keys camelCase | non-empty list | `userStoryRefs` = non-empty list; `gwt` required (see below) |
| **Event** | `commandId` (**must equal another item's `nodeId`**) | `fields.payload` = non-empty object, keys camelCase | non-empty list | — |
| **ReadModel** | `boundedContextId` (known BC) | — | non-empty list | `userStoryRefs` = non-empty list |
| **Policy** | `boundedContextId` (known BC), `triggerEventId` + `invokeCommandId` (**must equal other items' `nodeId`**) | — | — | — |
| **UI** | `boundedContextId` (known BC) | — | — | optional `commandId` / `readModelId` to attach the screen |
| **Invariant** | `aggregateId` (**must equal another item's `nodeId`**) | — | — | — |

"must equal another item's `nodeId`" = the referenced node must also appear in the same
`tacticalDiff` list (unresolved refs are rejected as `unresolved_ref`).

## `boundedContextId` — Epic ≡ BoundedContext (do not invent ids)

`boundedContextId` must be an **Epic `tempId` from this Proposal's approved strategicDiff**
(an Epic *is* the BoundedContext container in this model) or the id of a BoundedContext that
already exists in the graph. Inventing a fresh id like `BC-order` when the strategic Epic is
`EPIC-order` is rejected as `unresolved_bounded_context` — on Accept it would leave the
Aggregate dangling outside every BoundedContext, so nothing would show up in the live graph.

## ValueObject / Enumeration — required, and they must be used

When the diff contains any Aggregate, it **must** also contain at least one `ValueObject`
and at least one `Enumeration` node (`required`). Every `fields.typeName` you declare must be
**used as a property type** by some Aggregate/Command/Event/ReadModel — either directly
(`"type": "Money"`) or inside a container (`"type": "List<Money>"`). An unused declaration is
rejected as `unused_type`. This is what makes VO/Enum real model elements instead of decoration.

```json
{ "nodeId": "VO-money", "nodeLabel": "ValueObject", "nodeTitle": "금액",
  "changeType": "CREATE", "impactLevel": "LOW", "aggregateId": "AGG-order",
  "fields": { "typeName": "Money" },
  "properties": [ { "name": "amount", "type": "BigDecimal" }, { "name": "currency", "type": "String" } ] },

{ "nodeId": "ENUM-order-status", "nodeLabel": "Enumeration", "nodeTitle": "주문 상태",
  "changeType": "CREATE", "impactLevel": "LOW", "aggregateId": "AGG-order",
  "fields": { "typeName": "OrderStatus", "items": ["PLACED", "PAID", "CANCELLED"] } }
```

…and the Aggregate that uses them:

```json
"properties": [ { "name": "orderId", "type": "UUID" },
                { "name": "totalAmount", "type": "Money" },
                { "name": "status", "type": "OrderStatus" } ]
```

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

`EPIC-order` below is the Epic `tempId` from the approved strategicDiff — not a made-up id.

```json
{
  "tacticalDiff": [
    { "nodeId": "AGG-cart", "nodeLabel": "Aggregate", "nodeTitle": "장바구니",
      "changeType": "CREATE", "impactLevel": "HIGH",
      "boundedContextId": "EPIC-order",
      "properties": [ { "name": "cartId", "type": "UUID" },
                      { "name": "items", "type": "List<CartItem>" },
                      { "name": "status", "type": "CartStatus" } ],
      "fields": { "rootEntity": "Cart" } },

    { "nodeId": "VO-cartItem", "nodeLabel": "ValueObject", "nodeTitle": "장바구니 항목",
      "changeType": "CREATE", "impactLevel": "LOW", "aggregateId": "AGG-cart",
      "fields": { "typeName": "CartItem" },
      "properties": [ { "name": "productId", "type": "UUID" }, { "name": "quantity", "type": "Integer" } ] },

    { "nodeId": "ENUM-cartStatus", "nodeLabel": "Enumeration", "nodeTitle": "장바구니 상태",
      "changeType": "CREATE", "impactLevel": "LOW", "aggregateId": "AGG-cart",
      "fields": { "typeName": "CartStatus", "items": ["ACTIVE", "ORDERED", "ABANDONED"] } },

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
