---
name: robo-proposal-strategic-ddd
description: Unified Detailed DDD strategic stage skill for Discover, Decompose, and Strategize.
---

# Skill: robo-proposal-strategic-ddd

## Purpose
Run the first three Detailed DDD stages for a Proposal:

- `DISCOVER`: event storming and hotspots.
- `DECOMPOSE`: subdomain map and coupling notes.
- `STRATEGIZE`: Core/Supporting/Generic classification.

The runner passes a `stage:` line. Read only the reference for that stage.

## Reference Selection
- `stage: DISCOVER` -> `references/discover.md`
- `stage: DECOMPOSE` -> `references/decompose.md`
- `stage: STRATEGIZE` -> `references/strategize.md`

Do not read legacy individual strategic DDD stage skills.

## Output
Narrate briefly in Korean with stage-specific tags, then output one JSON object.

The top-level artifact key must match the stage:

- `DiscoverArtifact`
- `DecomposeArtifact`
- `StrategizeArtifact`

## Common Rules
1. Focus on this Proposal's change, not the whole domain.
2. Use domain language, not technical layer names.
3. Preserve existing strategic memory when the prompt provides it.
4. If backend validator feedback is present, fix the listed contract issue before anything else.
5. Do not produce Strategic Diff or Tactical Diff here. Stage artifacts are consolidated later by `robo-proposal-diff`.
