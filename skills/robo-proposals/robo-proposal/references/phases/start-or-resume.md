# Start Or Resume

When no Proposal ID is provided, call `proposal_list` and show create/resume choices. When a Proposal ID is provided, call `proposal_get`, `proposal_resume`, and `proposal_next_step`.

Before creating a **new** Proposal, apply the mode-selection gate in `references/phases/mode-selection.md`: if the user did not name a mode, ask which mode (SIMPLIFIED vs DETAILED DDD) and wait; if they named one, create with it immediately. Never call `proposal_create` until the mode is fixed.

Return a concise next-step recommendation. If there is a pending question or draft, show only that pending decision and do not generate a new artifact.
