# Contract: Proposal legacy provenance v2

## Marker events

- Search request/result and detail request/result are typed separately.
- Pairing uses tool_use_id; arrival order must not rely on one global pending query.
- File fallback is resolved before JSON decoding.

## Stage lifecycle

- Collector begins at stage run start.
- Completed entries may stream to UI immediately.
- Stage save occurs on success, clarify return, and explicit stage completion; cancellation must not fabricate a complete result.
- Empty collectors do not write noise records.

## UI projection

- `referenceCount = unique(searched ids ∪ inspected ids)`.
- `connected = normalized generated text contains node name, physical table name, logical table name, or inspected column name`.
- Search-only nodes remain visible but faded and have no line.

