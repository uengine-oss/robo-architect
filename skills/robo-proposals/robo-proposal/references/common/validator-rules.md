# Validator Rules

Backend validation is authoritative.

- Fix validator feedback before adding new analysis.
- Use canonical tactical fields only: `aggregateId`, `boundedContextId`, `commandId`, `triggerEventId`, `invokeCommandId`, `userStoryRefs`.
- Do not use legacy aliases such as `aggregate`, `boundedContext`, `emittedBy`, `trigger`, `invokes`, or `traces`.
- Every final artifact must be valid JSON.
- Invalid transition means stop with an error envelope or one confirmation question.
