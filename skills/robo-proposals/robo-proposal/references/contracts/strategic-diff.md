# Strategic Diff Contract

Authoritative validator: `api/features/proposal_lifecycle/services/proposal_ai_validation.py`
(`validate_strategic_output`). Mirror it here. **You do not need to read the backend source
to pass validation; the required shape is below.**

Output:

```json
{ "action": "done", "strategicDiff": { "version": 1, "epics": [], "features": [], "userStories": [], "processes": [] }, "journeys": [] }
```

`strategicDiff` must contain at least one design-intent item across
`epics` / `features` / `userStories` / `processes`.

## Required fields per entity type

Every item (any collection) requires these **top-level** fields:

- `op`: `CREATE`, `MODIFY`, or `DELETE`.
- `entityType`.
- `entityTitle`.
- On `CREATE`: `tempId` (or `entityId`).

Per collection, additional **top-level** requirements:

| Collection | Additional required top-level fields |
|---|---|
| `epics` | (common only) |
| `features` | `epicId` |
| `userStories` | `featureId`, `boundedContextId`, `role`, `action`, `benefit` |
| `processes` | (common only) |

> **Critical for User Stories:** `role` / `action` / `benefit` / `boundedContextId` /
> `featureId` are **top-level fields on the item — NOT inside `fields`**. Putting the
> As-a/I-want/So-that narrative under `fields` (e.g. `fields.asA`) fails validation with
> `role/action/benefit = required`. `fields` is optional and only for extra detail.

## Epic ≡ BoundedContext — `boundedContextId` must resolve

There is **no separate BoundedContext entity to invent**: in this model an **Epic is the
BoundedContext** (the requirements tree is BoundedContext(Epic) → Feature → UserStory, and
Aggregates hang off it). So `userStories[].boundedContextId` — and later every
`boundedContextId` in the tacticalDiff — must be **an Epic `tempId` declared in this same
strategicDiff** (or the id of a BoundedContext that already exists in the graph).

Writing `boundedContextId: "BC-order"` while the Epic is `EPIC-order` is rejected with
`unresolved_bounded_context`: that id matches nothing, so on Accept the story and its
Aggregates would be written outside every BoundedContext and vanish from the live views.

## Valid User Story example

```json
{
  "op": "CREATE",
  "entityType": "UserStory",
  "tempId": "US-add-to-cart",
  "entityTitle": "장바구니에 상품 담기",
  "featureId": "FEA-cart",
  "boundedContextId": "EPIC-order",
  "role": "고객",
  "action": "상품을 장바구니에 담는다",
  "benefit": "원하는 상품을 모아 한 번에 주문할 수 있다"
}
```

Feature example (note `epicId`):

```json
{ "op": "CREATE", "entityType": "Feature", "tempId": "FEA-cart", "entityTitle": "장바구니", "epicId": "EPIC-order" }
```

For clarify:

```json
{ "action": "clarify", "questions": [{ "index": 0, "text": "...", "options": ["...", "..."] }] }
```
