# Quickstart Verification

Run from `project/robo-architect`:

```powershell
.\.venv\Scripts\python.exe -m pytest api\features\ingestion\hybrid\tests\test_effect_provenance.py -q
.\.venv\Scripts\python.exe -m pytest api\features\canvas_graph\tests api\features\prd_generation\tests -q
```

If the repository virtual environment is absent, use its documented Python test command with
the same test paths.

Manual checks:

1. Active AFFECTS_TABLE projections include access/op/op_source.
2. READ-only effects are filtered before `writes`.
3. UNKNOWN renders as an unresolved WRITE, not an exact DML.
4. Event prompt instructions qualify LLM_INFERRED and ignore UNKNOWN for verb selection.

