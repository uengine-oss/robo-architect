# Stage Artifact Contracts

Authoritative validator: `api/features/proposal_lifecycle/services/proposal_ai_validation.py`
(`validate_stage_artifact`) plus each stage runner in
`api/features/proposal_lifecycle/services/stage_runners/*.py`. Mirror them here.
**You do not need to read the backend source; the required arrays, enums, and element
shapes are below.**

The stage is identified by the `proposal_save_stage_artifact` call; the artifact body
uses the stage's top-level key (e.g. `StrategizeArtifact`) shown below.

## Blocking rules (validation fails without these)

| Stage | Required non-empty array | Element enum / blocking rule |
|---|---|---|
| `DISCOVER` | `events` | — |
| `DECOMPOSE` | `subDomains` | — |
| `STRATEGIZE` | `classifications` | `classifications[].kind` ∈ `{ CORE, SUPPORTING, GENERIC }` (**blocking** — any other value, incl. "Core"/"핵심", is rejected) |
| `CONNECT` | `interactions` | — |
| `DEFINE` | `contexts` | — |
| `TACTICAL` | `aggregates` | — |

## Recommended rules (stage runner may re-request; treat as required)

- `DEFINE`: each `contexts[].ubiquitousLanguage` should have **≥ 5** terms.
- `TACTICAL`: each `aggregates[].invariants` should have **≥ 2** invariants.

(The save validator emits these as `warning`, but the stage runner's own quality gate
enforces them, so produce them to converge in one pass.)

## Element shapes (from the stage runner prompts)

```json
DiscoverArtifact: {
  "events": [ { "name": "...", "actor": "...", "external": false } ],
  "pivotalEvents": ["..."],
  "hotspots": [ { "text": "...", "disposition": "RESOLVE_NOW" } ]
}

DecomposeArtifact: {
  "subDomains": [ { "name": "...", "responsibility": "...", "eventRefs": ["..."] } ],
  "adjacency": [ { "from": "...", "to": "..." } ],
  "couplingNotes": ["..."]
}

StrategizeArtifact: {
  "classifications": [ { "subDomain": "...", "kind": "CORE", "rationale": "...", "buildVsBuy": null } ]
}

ConnectArtifact: {
  "interactions": [ { "from": "...", "to": "...", "message": "...", "kind": "EVENT", "sync": false, "rationale": "..." } ],
  "couplingWarnings": ["..."],
  "messagingChannel": "Kafka"
}

DefineArtifact: {
  "contexts": [ {
    "name": "...", "purpose": "...", "classification": "CORE",
    "businessModel": ["revenue"], "evolution": "custom_built", "domainRoles": ["execution"],
    "inbound":  [ { "collaborator": "...", "message": "...", "type": "Command" } ],
    "outbound": [ { "collaborator": "...", "message": "...", "type": "Event" } ],
    "ubiquitousLanguage": [ { "term": "...", "definition": "..." } ],   // >= 5 terms
    "businessDecisions": ["..."], "assumptions": ["..."],
    "verificationMetrics": ["..."], "openQuestions": ["..."], "languageClashes": ["..."]
  } ]
}

TacticalArtifact: {
  "aggregates": [ {
    "name": "...", "description": "...", "boundaryRationale": "...",
    "stateTransitions": [ { "from": "...", "to": "...", "trigger": "..." } ],
    "invariants": ["...", "..."],                                       // >= 2
    "correctivePolicies": ["..."], "handledCommands": ["..."], "createdEvents": ["..."],
    "throughput": { "commandHandlingRate": {"avg":"","max":""}, "totalClients": {"avg":"","max":""},
                    "concurrencyConflictChance": {"avg":"","max":""} },
    "size": { "eventGrowthRate": {"avg":"","max":""}, "lifetime": {"avg":"","max":""},
              "eventsPersisted": {"avg":"","max":""} }
  } ]
}
```

Do not output final Strategic or Tactical Diff from these stages — consolidation happens
in the diff phase. See `references/phases/detailed-ddd.md` for stage sequencing.
