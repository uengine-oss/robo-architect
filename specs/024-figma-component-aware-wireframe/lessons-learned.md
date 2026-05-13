# Spec 024 — Lessons Learned

Trial-and-error log from implementing figma-component-aware wireframe generation. Each entry follows: **Symptom → Diagnosis → Fix → Constitution principle codified**.

Most of these are summarised as Constitution Principles VIII and IX (see `.specify/memory/constitution.md` § VIII–IX); this file is the long-form story.

---

## L1. Plugin reports "nodesCreated: 2, nodesFailed: 0" but Figma frame is empty

- **Symptom** — the plugin's `CREATE_FRAME_IN_PAGE_RESULT` ack returned `ok: true, nodesCreated: 2, nodesFailed: 0`, yet opening the created frame in Figma showed an empty rectangle.
- **Diagnosis** — the sceneGraph had structure `root (type=FRAME) → INSTANCE leaves`. The plugin's `renderJsxSceneGraphIntoFrame` walker looks for `root → CANVAS → FRAME → leaves`; when it can't find a CANVAS child, it falls back to "any FRAME with children that is NOT rootId" — but since our root IS the FRAME, that fallback also missed. Plugin returned `failed: 1` (the "no wireframe FRAME found" miss) — which is **not** the same as zero failures. Later, the actual node walk happened against `wireframeNode.childIds` which was empty, so `nodesFailed` accumulated to 0 too. Net effect: plugin appeared to succeed; nothing rendered.
- **Fix** — wrap the flat INSTANCE list in `root(DOCUMENT) → page(CANVAS) → wireframe(FRAME) → leaves`. See `retype_instance_markers` doc + `_generate_figma_components_scene_graph` in `api/features/ingestion/workflow/phases/ui_wireframes.py`.
- **Constitution** — VIII §1 (structure walker).

## L2. INSTANCE nodes silently dropped as "Unsupported node type"

- **Symptom** — after fixing L1, `nodesFailed: 2` for two INSTANCE children. The plugin produced no instances.
- **Diagnosis** — the renderer used `renderJsxSceneGraphIntoFrame` (handles primitives), NOT the older `buildFrameFromSceneGraph` (which had INSTANCE logic). `renderSceneNode` covered `FRAME / TEXT / RECTANGLE / ELLIPSE / LINE` and fell into `else { ctx.failed++; ctx.errors.push('Unsupported node type: INSTANCE') }`. The `renderErrors` field that would have told us this was NOT in the Pydantic ack body (silently dropped).
- **Fix** — added an `INSTANCE` branch to `renderSceneNode` in `figma-plugin/src/plugin.ts` that does the componentCache lookup (exact + substring fallback) and applies text overrides. Also added `renderErrors: list[str] | None` to `CreateFrameInPageAckBody` in `plugin_messages.py` so future failures are visible.
- **Constitution** — IX §plugin-ack-structure.

## L3. Hand-rolled sceneGraph produces "all on top of each other" layout

- **Symptom** — when the dev endpoint generated a mixed-mode wireframe, the Figma frame showed elements stacked / overlapping at the top with the bottom 80% empty. See the screenshot in commit history for the spec.
- **Diagnosis** — the dev endpoint emitted autolayout fields with the **wrong field names**. It set `primaryAxisSizingMode: "AUTO"`, but the plugin's `applyAutoLayout` reads `sn.primaryAxisSizing === "HUG"` (SerializedSceneGraph convention) — not the Figma API names. So the autolayout-sizing call silently no-op'd, the outer FRAME stayed at its default `frame.resize(375, 812)`, child INSTANCEs got placed by autolayout VERTICAL into a tiny region, and natives (TEXT/RECT) without explicit width fell to natural-content size.
- **Fix** — switched the dev endpoint to call `run_render_agent` (open-pencil JSX → Yoga layout) instead of hand-rolling sceneGraph. Production `_generate_figma_components_scene_graph` switched too — both now share `build_jsx_agent_extra_context` + `retype_instance_markers`.
- **Constitution** — VIII (whole principle).

## L4. open-pencil's `<Component>` / `<Instance>` JSX elements are broken

- **Symptom** — sending `<Component name="..." />` JSX to `/render` returned `{"error": "Component resolution depth exceeded"}`. `<Instance ...>` returned `"Instance is not defined"`.
- **Diagnosis** — `open-pencil/packages/core/src/design-jsx/components.ts` exports `export const Component = Frame` and `Instance = Frame`, but the runtime substitution in `render.ts:buildComponent` only registers a fixed list of intrinsic names (Frame/Text/Rectangle/Ellipse/Line/Star/Polygon/Vector/Group/Section/View/Rect/Icon). `Component` and `Instance` are not in that list — Sucrase compiles `<Component>` as a JSX **custom component**, which `resolveToTree` treats as a recursive function call → "depth exceeded".
- **Fix** — adopted a marker convention `<Frame name="$INSTANCE:<exact name>|<k>=<v>|…" w={N} h={N} />`. The marker is a regular Frame to open-pencil (no runtime patching needed); the backend's `retype_instance_markers` post-processor converts the FRAME to INSTANCE with `componentId` resolved and overrides parsed before sending to the plugin.
- **Constitution** — VIII §marker-convention (last paragraph).

## L5. ngrok-free silently dies at the monthly request limit

- **Symptom** — `ngrok http 8000` reported "tunnel started", the agent's local `/api/tunnels` returned the public URL, but every public request returned HTTP 403 with content type text/html.
- **Diagnosis** — body contained `<noscript>This ngrok account has reached its HTTP requests limit for the month. (ERR_NGROK_727)</noscript>`. Free-tier monthly request quota; the agent is healthy but ngrok-edge refuses traffic.
- **Fix** — switched to Cloudflare's quick tunnel (`cloudflared tunnel --url http://localhost:8000`). No account, no rate limit, no `ngrok-skip-browser-warning` header needed.
- **Constitution** — IX §external-tunnels.

## L6. New routes 404 even after editing files

- **Symptom** — added `/api/figma-binding/components/scan`, reloaded vite, hit the endpoint via curl → 404.
- **Diagnosis** — uvicorn was launched WITHOUT `--reload`. Process command was `uvicorn api.main:app --host 127.0.0.1 --port 8000 --log-level warning` started at 21:21; my edits happened at 23:30. uvicorn doesn't auto-reload without the flag — confusing because we had vite auto-reload working in the same dev loop.
- **Fix** — restart uvicorn with `--reload`. From now on, the dev runbook is `uvicorn api.main:app --reload --host 127.0.0.1 --port 8000`.
- **Constitution** — IX §uvicorn-reload-flag.

## L7. Plugin tries to connect to a dead tunnel after reload

- **Symptom** — after rebuilding the plugin, user reopened it; Figma showed "연결됨" but no requests arrived at the backend. Backend's `/api/figma-plugin/status?file_key=...` showed `connected: []` and `pending_files: []`.
- **Diagnosis** — the plugin auto-loads `localStorage.robo_sync_url` and silently retries against it. The saved URL was the old ngrok one (long dead), so the plugin's `/poll` requests failed in the iframe network layer with no visible feedback. The visible "연결됨" indicator was set after the initial `/status` probe — which happened to return 200 because the user briefly switched the URL field but didn't realize localStorage was overriding it.
- **Fix** — instructed the user to overwrite the URL field with the live cloudflared URL and click 연결 (which calls `localStorage.setItem('robo_sync_url', ...)` again).
- **Constitution** — IX §plugin-url-cache.

## L8. Plugin bundle stale after `bun build.js`

- **Symptom** — after editing `figma-plugin/src/plugin.ts` (added INSTANCE handler) and running `bun build.js` (success, `Built dist/plugin.js (60.5 KB)`), the next Playwright run still returned `nodesFailed: 2` with "Unsupported node type" semantics.
- **Diagnosis** — Figma only reads `dist/plugin.js` when the plugin window is **launched fresh**. The currently-open plugin instance was running the pre-edit bundle.
- **Fix** — instructed the user to close + relaunch the plugin window before re-running. Plugin file_key + URL are cached in `figma.clientStorage` so reconnect is one click.
- **Constitution** — IX §plugin-bundle-reload.

## L9. New page in Figma exists but viewport sits at (0, 0)

- **Symptom** — Playwright run reported `nodesCreated: 14, failed: 0`. User opened the named page in Figma sidebar and saw an empty canvas. Confused for ~15 minutes — was it a render failure?
- **Diagnosis** — the plugin's `handleCreateFrameInPage` placed the new frame at `(0, 0)` of the new page, then ack'd. Figma does NOT auto-scroll the viewport when a plugin creates a node off-screen. The user's viewport last centered on a different page coordinate, so the new frame was visually outside.
- **Fix** — call `figma.viewport.scrollAndZoomIntoView([frame])` before ack'ing. One line, but explains 100% of "page exists but content invisible" symptoms.
- **Constitution** — IX §viewport-centring.

## L10. `/api/figma-plugin/status` is a misleading liveness probe for polling clients

- **Symptom** — used `GET /api/figma-plugin/status` to check whether the plugin was online before triggering an action. It returned `connected: []` (no WebSocket). Triggered the action anyway "to see what happens" — and it worked.
- **Diagnosis** — the endpoint reports only `_connections` (WebSocket dict) and `_pending_updates`. Plugin polling-mode clients announce themselves via `_plugin_metadata`, which the `is_polling_active(file_key)` helper reads. `/status` doesn't surface metadata; for polling clients, the only ground-truth liveness signal is "does an ack arrive within timeout".
- **Fix** — when writing pre-flight checks, trust `is_polling_active` (or actually attempt the operation), not the status snapshot. Mentioned the trap in the Playwright test's pre-flight checklist.
- **Constitution** — IX §plugin-liveness-probe.

---

## Open follow-ups (not blocking)

- `applyContainerProps` no-ops the `node.resize(w, h)` call when either dimension is missing. Easy to miss; future helper should warn. The plugin code is at `figma-plugin/src/plugin.ts:589`.
- The plugin's `INSTANCE` lookup is by lowercased name with substring fallback; if two components share a substring (e.g. "btn-primary" and "btn-primary-disabled"), the first found wins. Document for future when catalog grows.
- We do NOT currently parse open-pencil's full set of node types when post-processing — only TEXT / RECTANGLE / FRAME / INSTANCE / etc. If open-pencil adds new primitive kinds (e.g. `path`, `image`), the plugin's `renderSceneNode` else branch will silently fail again. Add a structural test that fuzzes new node types into the post-processor.
