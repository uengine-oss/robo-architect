# Reference: Strategic Diff

Use this reference only for `SIMPLIFIED_STRATEGIC` and `DETAILED_STRATEGIC_FROM_DDD`.

## BoundedContext = Epic
`strategicDiff.epics` represents Bounded Contexts. Do not create a separate Epic concept.

Each epic:

```json
{ "op": "CREATE", "entityType": "BoundedContext", "entityId": null, "tempId": "EP-order", "entityTitle": "주문", "fields": { "description": {"after": "..."}, "classification": {"after": "core"} } }
```

Classification:

- `core`: business differentiation.
- `supporting`: helps core capabilities.
- `generic`: commodity capability, often buyable.

## Feature and UserStory
- Each Feature belongs to one BC via `epicId`.
- Each UserStory belongs to one Feature and one BC via `featureId` and `boundedContextId`.
- UserStory requires `role`, `action`, `benefit`.
- `entityTitle` should read like `<role>: <action>`.
- Acceptance criteria can be GWT-style summaries.

## Process and Journey
Use `processes` for major end-to-end domain flows discovered in the prompt or DDD artifacts.

Use top-level `journeys` only when the user flow is clear:

```json
{
  "tempId": "JNY-order",
  "boundedContextId": "EP-order",
  "name": "주문 여정",
  "steps": [
    { "tempId": "ST-cart", "name": "장바구니", "kind": "screen", "next": ["ST-order"] }
  ]
}
```

## Detailed DDD Input
For `DETAILED_STRATEGIC_FROM_DDD`, ground the diff in:

- Discover events, pivotal events, hotspots, actors, external systems.
- Decompose subdomains, responsibilities, adjacency, coupling notes.
- Strategize classifications, build-vs-buy, differentiation.

Do not merely copy stage artifact names. Convert them into the canonical Strategic Diff hierarchy and fill missing parent refs.

## Clarification
Only `SIMPLIFIED_STRATEGIC` may return `action: "clarify"`, and only when generating a useful Strategic Diff would be unsafe without user input. Ask at most five choice-based questions.
