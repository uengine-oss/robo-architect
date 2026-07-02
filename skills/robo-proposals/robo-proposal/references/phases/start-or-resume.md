# Start Or Resume

When no Proposal ID is provided, call `proposal_list` and show create/resume choices. When a Proposal ID is provided, call `proposal_get`, `proposal_resume`, and `proposal_next_step`.

Return a concise next-step recommendation. If there is a pending question or draft, show only that pending decision and do not generate a new artifact.
