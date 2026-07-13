# Constitution

Two different steps share the word "Constitution". `proposal_next_step` tells you which one
you are in — never merge them, never skip the first.

| `nextStep.phase` | What it is | Where it is stored |
|---|---|---|
| `PROJECT_CONSTITUTION` | The **target project's Constitution** (architecture style, tech stack, repo strategy, design principles) | A **root `:Constitution` node in Neo4j** (project-wide singleton) |
| `CONSTITUTION` | The **implementation plan** for *this* Proposal, derived from that Constitution | `Proposal.implementationPlan` |

## 1. `PROJECT_CONSTITUTION` — interview first, then create the node

This step appears when the project has **no Constitution node yet** (confirm with
`proposal_get_constitution`). It is a hard gate: `TASKS` and everything after it stay blocked
until the Constitution node exists and the architect has approved it.

**You must actually interview the architect. Do not invent the answers.**

1. Ask the gating questions — **one at a time** — and record each with
   `proposal_record_question(proposalId, phase="PROJECT_CONSTITUTION", question=…, options=[…])`.
   Present the question, wait for the answer, then store it with `proposal_answer_question`.
   Seed every question with a recommended option inferred from the original prompt and the
   approved Diffs, so the architect only has to confirm or override.
   - architecture style: `MONOLITH` or `MICROSERVICES`
   - technology stack (language / framework / persistence)
   - repository strategy: `MONOREPO` or `REPO_PER_SERVICE`
   - design principles (the rules code review will enforce)
   - only if `MICROSERVICES` + `REPO_PER_SERVICE`: repo mode `SPLIT_GIT` or `REUSE_EXISTING`

   Dependency-aware minimum: for a monolith, skip ingress / mesh / per-service questions entirely.

2. Save the result with `proposal_save_draft(proposalId, phase="PROJECT_CONSTITUTION", artifact=…)`:

```json
{ "constitution": {
    "raw": "# Project Constitution\n\n## Architecture\n…the document body (markdown)…",
    "fields": {
      "designPrinciples": "…",
      "techStack": "…",
      "architectureStyle": "MONOLITH",
      "repoStrategy": "MONOREPO",
      "repoMode": null
    } } }
```

   The server rejects the draft with `interview_required` if no **answered**
   `PROJECT_CONSTITUTION` question exists, and with `invalid` if `architectureStyle` /
   `repoStrategy` / `techStack` / `designPrinciples` are missing. `raw` must be the real
   document body, not a stub.

3. Present the returned `reportMarkdown` and **wait for approval** (`requiresUserApproval: true`).
   On approval call `proposal_confirm_draft` — that is what **creates the `:Constitution` node
   in Neo4j**. Only then does `proposal_next_step` advance to `CONSTITUTION`.

## 2. `CONSTITUTION` — the implementation plan

The Constitution now exists; read it and produce the implementation plan for this Proposal:

```json
{ "implementationPlan": { "version": 1, "architectureDecisions": [], "constitutionGaps": [] } }
```

Every aspect in `DEPLOYMENT_ENV`, `INGRESS`, `SERVICE_MESH_FRAMEWORK`, `FRONTEND`,
`REPO_MAPPING` must have either a decision or an entry in `constitutionGaps`. Save with
`proposal_save_draft(phase="CONSTITUTION")`, present, wait for approval, then
`proposal_confirm_draft`.
