# roboSpec — Frontend feature (spec 029)

Per-node progress badges + "open implementation file" affordance for the
Design tab.

Contents (skeleton; populated in subsequent /speckit-implement passes):

- `composables/useRoboProgressStream.ts` — subscribes to
  `GET /api/robo-spec/projects/{project_id}/progress/stream` (SSE).
- `composables/useOpenImplFile.ts` — calls
  `POST /api/robo-spec/projects/{project_id}/open-file` and surfaces the
  `opened | not-implemented | ambiguous | offline` variants to the UI.
- `components/ProgressBadge.vue` — renders one of
  `todo | in-progress | done | blocked | orphaned | offline`.

Cross-feature wiring is done in `eventModeling/ui/EventModelingPanel.vue`
(per-node badge + click handler) and stays on the composable boundary —
no direct imports from other feature folders (Principle V).
