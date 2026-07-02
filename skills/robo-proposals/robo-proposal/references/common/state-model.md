# State Model

`Proposal` stores the current summary:

- `lifecycleStatus`: `ACTIVE`, `WAITING_USER`, `READY_FOR_CONFIRM`, `BLOCKED`, `DONE`, `REJECTED`
- `currentPhase`, `currentStage`
- canonical artifacts: `stagePlan`, `stageArtifacts`, `strategicDiff`, `tacticalDiff`, `implementationPlan`, `tasksJson`, `testResults`
- pending refs: `pendingQuestionId`, `pendingDraftId`, `resumeToken`

`ProposalInteraction` stores history:

- `QUESTION`, `ANSWER`, `DRAFT`, `APPROVAL`, `REJECTION`, `VALIDATOR_ERROR`, `SYSTEM_NOTE`
- `PENDING`, `RESOLVED`, `CONFIRMED`, `REJECTED`, `SUPERSEDED`

Drafts do not become final artifacts until confirmed. Confirmed artifacts are promoted to the canonical Proposal fields.
