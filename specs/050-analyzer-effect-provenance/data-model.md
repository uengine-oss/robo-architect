# Data Model: Architect Table Effects

`ExampleDTO.writes` retains its historical name but entries now have:

```json
{
  "table": "ORDER_HISTORY",
  "access": "WRITE",
  "op": "UNKNOWN",
  "op_source": "UNRESOLVED"
}
```

Normalization rules:

- exclude READ-only effects from `writes`;
- preserve WRITE and READ_WRITE even with UNKNOWN;
- legacy missing access derives READ for op READ, otherwise WRITE;
- legacy missing provenance is marked LEGACY for display/compatibility only;
- deduplication key includes table, access, op, and provenance.

