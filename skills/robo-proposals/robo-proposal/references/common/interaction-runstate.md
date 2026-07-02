# Interaction RunState

For a user decision:

1. Produce one question only.
2. Call `proposal_record_question`.
3. Return an `action:"clarify"` envelope and stop.
4. On answer, use `proposal_answer_question`, then `proposal_resume`.

For a draft:

1. Generate the artifact in canonical shape.
2. Call `proposal_save_draft`.
3. Return an `action:"draft"` envelope with `draftRef`.
4. Promote only after `proposal_confirm_draft`.

Resume context should include the Proposal summary, pending interaction, recent interaction window, and confirmed artifact summary. Do not replay the full history unless the user asks.
