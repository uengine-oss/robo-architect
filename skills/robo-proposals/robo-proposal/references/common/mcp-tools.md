# MCP Tools

Use the `robo-proposal` MCP server for lifecycle state:

- `proposal_create`, `proposal_get`, `proposal_list`, `proposal_next_step`
- `proposal_save_stage_plan`, `proposal_skip_stage`, `proposal_save_stage_artifact`
- `proposal_save_draft`, `proposal_confirm_draft`, `proposal_reject_draft`
- `proposal_save_diff`
- `proposal_record_question`, `proposal_answer_question`, `proposal_resume`
- `proposal_generate_tasks`, `proposal_update_implementation_status`, `proposal_save_test_result`
- `proposal_submit`, `proposal_accept`

Rules:

1. Neo4j is the source of truth.
2. Do not use workspace files to remember lifecycle state.
3. If a tool returns validator or transition failure, stop and report that failure.
4. Store user-facing waits as interactions: questions as `QUESTION`, drafts as `DRAFT`.
