---
name: robo-proposal-tactical-ddd
description: Unified Detailed DDD tactical stage skill for Connect, Define, and Tactical.
---

# Skill: robo-proposal-tactical-ddd

## Purpose
Run the last three Detailed DDD stages for a Proposal:

- `CONNECT`: domain message flow and coupling decisions.
- `DEFINE`: Bounded Context Canvas.
- `TACTICAL`: Aggregate Design Canvas.

The runner passes a `stage:` line. Read only the reference for that stage.

## Reference Selection
- `stage: CONNECT` -> `references/connect.md`
- `stage: DEFINE` -> `references/define.md`
- `stage: TACTICAL` -> `references/tactical.md`

Do not read legacy individual tactical DDD stage skills.

## Output
Narrate briefly in Korean with stage-specific tags, then output one JSON object.

The top-level artifact key must match the stage:

- `ConnectArtifact`
- `DefineArtifact`
- `TacticalArtifact`

## Common Rules
1. Keep coupling loose and expose coupling risks as warnings in the artifact.
2. Reuse provided strategic memory and previous stage artifacts.
3. Use domain language and avoid technical layer names unless the stage explicitly asks for messaging channel.
4. If backend validator feedback is present, fix the listed contract issue before anything else.
5. Do not output final Tactical Diff here. The final diff is generated later by `robo-proposal-diff` from these artifacts.
