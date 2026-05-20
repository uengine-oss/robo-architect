# Phase 0 Research: DDD Artifact Generation from Event Storming

Six decisions (D1–D6) from v1 (2026-05-11). Four new decisions (D7–D10) added in the 2026-05-12 amendment to cover stories P5–P7 (frontend perspective, PRD↔CLAUDE split, role-based agents). One additional decision (D11) added in the 2026-05-13 amendment to cover viewport-intent classification and the agent prompt that gates IA generation on the user's mobile/tablet/desktop direction. D1 records the pivot away from the earlier SpecKit-rendering / Figma-token approach; D2–D6 nail down the v1 design before contracts can be drawn; D7 fixes the frontend artifact folder layout + framework declaration; D8 fixes the UI-flow causal-ordering algorithm; D9 fixes the PRD↔CLAUDE content split rule; D10 fixes role-based agents + per-BC agent migration; D11 fixes viewport classification + dominant-viewport agent prompt.

---

## D1 — Artifact format and the pivot away from SpecKit + Figma token

**Decision**: Generate the **"DDD for SDD" artifact set** (Jarosław Wasowski, May 2026 — `docs/DDD for SDD - …Medium.pdf`), not SpecKit `spec.md`/`plan.md`. The artifacts are: `domain-terms.md` (Ubiquitous Language, per BC), `bc-<slug>.md` (Bounded Context Canvas, per BC), `context-map.md` (Context Map, one per system), `aggregate-<slug>.md` (Aggregate Design Spec, per Aggregate), `acl-<system>.md` (Anti-Corruption Layer Spec, per external integration), `requirements.md` (User Stories + EARS, per BC). `constitution.md` is **not** generated — the project's existing `.specify/memory/constitution.md` plays that role and is referenced by relative path. Output layout follows the article: `specs/bounded-contexts/<bc-slug>/...` plus `specs/context-map.md`. **No Figma API and no Figma credential** are introduced — UI wireframes are rendered from the open-pencil scene graph already stored in Neo4j (`UI.sceneGraph`).

**Rationale**:

- The user redirected: SpecKit integration is out; the DDD artifact format from the attached article is in. The article's thesis — AI coding agents need these five DDD artifacts as a deterministic semantic contract — fits our situation, with one twist in our favour: the article warns "LLMs are poor at *generating* tactical DDD; they're excellent at *consuming* it" and says the Aggregate Design Spec should be "written by a human from scratch." We are not generating tactical DDD with an LLM — we are **transcribing** a structured, human-authored event-storming graph (Aggregates, attributes, invariants/GWT, Commands, Events, Policies) into the article's artifact format. That sidesteps the failure mode the article cautions about; the human authoring already happened, in the event-storming UI.
- The Figma personal-access-token plan (earlier draft's D1) is dropped: the Figma plugin already syncs the wireframe scene graph into Neo4j as `UI.sceneGraph` (`docs/cypher/schema/03_node_types.cypher:258` — "open-pencil SerializedSceneGraph"). Pulling the same picture back over the Figma REST API would (a) need a credential we don't have, (b) couple a graph projection to a remote service, (c) duplicate data that's already local. Rendering from the stored scene graph is strictly better on all three.
- `constitution.md` is not regenerated because we already have one and it is the authoritative source; duplicating it into `specs/constitution.md` would create two copies that can drift. Generated artifacts reference `../../.specify/memory/constitution.md` (relative from a BC folder) instead.

**Alternatives considered**:

- **Keep generating SpecKit `spec.md`/`plan.md`** (earlier plan). Rejected by user direction.
- **Generate the DDD artifacts *and* SpecKit folders**. Rejected as scope bloat with no asked-for value; the SpecKit folders for real features are still authored via the SpecKit workflow as before.
- **Re-fetch wireframes from Figma REST API for higher-fidelity PNGs**. Rejected — we have the scene graph locally; see Rationale.

---

## D2 — Output folder layout and coexistence with existing `specs/NNN-*/`

**Decision**: Write DDD artifacts under `specs/bounded-contexts/<bc-slug>/` (one folder per BC) and the system-level Context Map at `specs/context-map.md`. Per-BC folder contents:

```text
specs/bounded-contexts/<bc-slug>/
├── domain-terms.md
├── bc-<bc-slug>.md
├── aggregates/
│   ├── aggregate-<agg-slug>.md
│   └── …
├── acl-<external-slug>.md            # 0..N — only if external integrations are modeled
├── requirements.md
└── requirements.assets/
    ├── <userStoryId>-<ui-slug>.scene.json
    └── <userStoryId>-<ui-slug>.svg    # only when the wireframe service rendered one
```

The existing `specs/NNN-*/` SpecKit feature folders (001–022) are never read or written by this feature. The two trees coexist under `specs/`.

**Rationale**:

- The article's reference layout is `/specs/{constitution.md, context-map.md, /bounded-contexts/<bc>/{bc-canvas, domain-terms, /aggregates, /api, acl, requirements}.md}`. Matching it keeps generated output recognizable to anyone who's read the article, and keeps the door open for the `/api/*.yaml` (OpenAPI / event schemas) artifacts as a future extension.
- Putting the DDD tree under `specs/bounded-contexts/` rather than a sibling top-level dir (`ddd/`, `domain/`) keeps everything spec-related in one place and matches the article verbatim. The `NNN-` numeric prefix convention of the SpecKit folders and the BC-slug naming of the DDD folders don't collide (a BC slug never starts with three digits followed by a hyphen unless someone names a BC "123-foo", in which case the slug rule still keeps it unique within `bounded-contexts/`).
- `requirements.assets/` (not `assets/`) so the wireframe sidecars don't get confused with any future per-BC asset conventions and so it's obvious they belong to `requirements.md`.

**Alternatives considered**:

- **Top-level `ddd/` directory**. Rejected — deviates from the article and fragments "where do specs live?".
- **One folder per Aggregate (mirroring the earlier `specs/NNN-<bc>-<agg>/` plan)**. Rejected — the article's unit is the Bounded Context (the BC Canvas, `domain-terms.md`, and `requirements.md` are BC-scoped; only the Aggregate Spec is Aggregate-scoped, and it lives in the BC folder's `aggregates/` subdir). BC-folder layout is faithful to the source.
- **Configurable output root**. Deferred — a `output_root` request field could be added later; for v1 the article's path is hard-wired to keep the contract small.

---

## D3 — GWT → EARS notation transform

**Decision**: Deterministic string transform, applied identically wherever criteria appear (Aggregate Spec "Enforced Invariants" and `requirements.md` "Acceptance Criteria"):

- `Given X, When Y, Then Z` → `WHEN Y IF X THEN system SHALL Z`
- `When Y, Then Z` (no Given) → `WHEN Y THEN system SHALL Z`
- Aggregate-level unconditional invariant `C` (from the Aggregate's own `invariants` array, no trigger) → `THE <AggregateName> SHALL <C>`
- Multiple `Given` clauses joined with `AND`; multiple `Then` clauses become multiple `SHALL` lines under the same `WHEN/IF`.

Invariants are numbered (`1.`, `2.`, …) per the article's Aggregate Spec example. An optional LLM pass (`llm_assist.smooth_ears`) fixes grammar/agreement in the produced sentences; it is OFF-able and never changes the logical structure (numbers, WHEN/IF/THEN/SHALL keywords, referenced names are preserved verbatim — the smoother only adjusts connective prose).

**Rationale**:

- EARS (Easy Approach to Requirements Syntax — Mavin, 2009) as used in the article combines Event-Driven (`WHEN <trigger>`) and Conditional (`IF <state>`) patterns with the `SHALL` obligation keyword. GWT maps onto it cleanly and mechanically: When→trigger, Given→state, Then→obligation. No LLM is needed for the *structure*.
- Doing the transform deterministically is required by SC-005 (byte-stable output): if an LLM rephrased criteria freely, two runs would differ. The smoother is constrained to leave the load-bearing tokens untouched, so even with smoothing on, the output is stable enough for review (and `smooth_ears=false` gives full determinism).
- Numbering invariants matches the article's `aggregate-order.md` example and lets the BC Canvas / Context Map reference "invariant 3 of aggregate Order".

**Alternatives considered**:

- **Keep GWT verbatim, don't translate to EARS**. Rejected — the article's Aggregate Spec and `requirements.md` both use EARS; emitting GWT would be off-format.
- **Let the LLM do the whole GWT→EARS translation**. Rejected on determinism (SC-005) and because the mapping is trivially mechanical — LLM adds risk, not value, for the structural part.

---

## D4 — UI wireframe rendering from the stored scene graph

**Decision**: For each User Story bound to a `UI` node, render the wireframe from `UI.sceneGraph` (open-pencil `SerializedSceneGraph` JSON) with **two always-produced outputs** and **one best-effort output**:

1. **Always** — a textual element tree embedded in `requirements.md`: walk the scene graph and emit a nested bullet list of meaningful elements (frames/containers with their layout role; text nodes with their content; interactive elements — buttons, inputs, links — with their labels/placeholders). This is what an AI coding agent actually consumes (it can't see images).
2. **Always** — the raw `sceneGraph` JSON written to `requirements.assets/<userStoryId>-<ui-slug>.scene.json`, linked from `requirements.md`, for full fidelity / re-rendering by other tools.
3. **Best-effort** — an SVG at `requirements.assets/<userStoryId>-<ui-slug>.svg`, embedded in `requirements.md` when produced. The SVG is obtained by calling the existing open-pencil wireframe service (`api/platform/open_pencil_client`, base URL `WIREFRAME_SERVICE_URL`); if that service does not expose a scene-graph→SVG render endpoint, or is unavailable, or times out, the SVG is skipped, a warning is reported, and the textual tree + JSON still go in. **No Figma API, no Figma credential** is involved in any of this.

The element-tree extractor is a small deterministic walker over the open-pencil node shape (it does not need the open-pencil runtime — just the JSON structure: `type`, `name`, `characters`/`text`, `children`, and the component-instance kind for buttons/inputs).

**Rationale**:

- The user explicitly removed the Figma token: "우리는 어차피 자체 neo4j 에 scenegraph 가 있으므로 토큰이 필요없어" — render from the scene graph we already have.
- The textual element tree is the highest-value output for the article's purpose ("specs the AI consumes"): a coding agent generating a Vue/React screen needs the structure and labels, not a bitmap. Making it the *always* output, with the image as a *nice-to-have*, means generation never depends on the wireframe service being up (SC-007).
- Attaching the raw scene-graph JSON costs nothing and preserves perfect fidelity for any downstream tool (including re-rendering the SVG later).
- Reusing `api/platform/open_pencil_client` for the SVG (rather than re-implementing an open-pencil renderer in Python) keeps us out of the rendering business; the client already exists and `WIREFRAME_SERVICE_URL` is already configured. If the service lacks an SVG endpoint today, the feature still ships fully on outputs (1) and (2), and the SVG step is a clean future add.

**Open implementation question (resolved by fallback, not blocking)**: whether the open-pencil Bun service currently exposes a `scene-graph → SVG/PNG` endpoint. The documented surface in `open_pencil_client.py` shows `/render` (component-instances → scene graph), `/components`, `/health` — not a scene-graph→image route. Implementation will check; if absent, output (3) is simply not produced and a one-line warning explains why. The contract and the spec already treat the SVG as best-effort, so this is not a gating unknown.

**Alternatives considered**:

- **Headless-browser render of the open-pencil frontend renderer** (canvaskit-wasm / yoga-layout) to PNG. Rejected — heavyweight (ship a headless Chromium), slow, and unnecessary given the textual tree is the consumable artifact.
- **Skip wireframes entirely**. Rejected — the user wants the UI captured in the artifacts; the textual tree + JSON does that without images.
- **Only attach the JSON, no textual tree**. Rejected — raw open-pencil JSON is verbose and not pleasant for a human reviewer; the textual tree is the readable form.

---

## D5 — Slug derivation, output-path resolution, and atomic create

**Decision**:

- **Slug**: `python-slugify` with `lowercase=True, separator="-", max_length=40, word_boundary=True`; non-ASCII (Korean) transliterated. A composed file slug (e.g. `bc-<bc-slug>.md`, `aggregate-<agg-slug>.md`) is checked for emptiness/collision within its target directory; on collision or empty result, a 6-char hex hash of the source node id is appended. BC folder name = `<bc-slug>` (with the same fallback).
- **Path safety**: every write path is `os.path.realpath`-resolved and asserted to be under `realpath(specs/)` before any handle is opened; anything else is a hard error (`path_escape`).
- **Atomic create / overwrite**: for a BC folder, render everything to a temp staging directory, then for each file either (a) refuse if the destination exists and `overwrite=false`, reporting it as skipped, or (b) `os.replace` the staged file over the destination when `overwrite=true` or the destination is absent. A process-level `fcntl.flock` on `specs/bounded-contexts/.ddd-spec.lock` is held across the scan+create critical section so concurrent generations against the same area can't interleave.
- **Stale-asset detection**: on overwrite, any file under `requirements.assets/` not referenced by the freshly-rendered `requirements.md` is reported as a `stale_asset` warning (not deleted).

**Rationale**:

- Korean BC/Aggregate names need transliteration; `python-slugify` (pulls `text-unidecode`) does it correctly and is tiny. The hash-suffix fallback guarantees uniqueness without a registry.
- `realpath` sandboxing is the same pattern feature 021 uses for the Claude Code workspace; cheap and removes any path-traversal risk from slug/name inputs.
- Staging + `os.replace` gives per-file atomicity: a reader never sees a half-written artifact. The single flock is sufficient for this single-tenant deployment — no need for a distributed lock.
- Reporting (not deleting) stale assets is conservative: a human decides whether the old SVG/JSON is garbage.

**Alternatives considered**:

- **Number DDD folders like SpecKit (`NNN-...`)**. Rejected — the article's unit is named BCs, not numbered features; numbering would be a foreign convention here.
- **Delete stale assets automatically**. Rejected — too aggressive; a stale-but-still-wanted SVG could be lost. Warn instead.
- **No lock (optimistic create-then-detect)**. Rejected — under concurrent triggers this risks interleaved partial folders; a single flock is simpler and correct.

---

## D6 — Context-Map relationship-pattern inference

**Decision**: Build `context-map.md` from the BCs and the cross-BC flows the graph *does* record (an upstream BC's `Event` consumed by a downstream BC's `Policy`, or any modeled BC→BC relationship). For each edge, assign a DDD relationship pattern:

- If the graph records an explicit pattern on the relationship, use it.
- Else infer a heuristic default: a BC that consumes another's events via a Policy → **Customer-Supplier** (consumer is the customer) — and if the consuming BC has its own translation layer modeled, **Conformist + ACL** instead; a BC whose events are consumed by ≥ 3 downstream BCs → mark the upstream side **Open Host Service + Published Language**; an edge to a node flagged external → **ACL (mandatory)**.
- Whatever is inferred (i.e. not read directly from the graph) is rendered with a trailing "(inferred — confirm)" and the operation reports a `relationship_pattern_inferred` warning naming the edge.

The Mermaid diagram is `graph LR` with one node per BC and one labeled edge per relationship, in the article's style. The Relationships section has one `### <Upstream> → <Downstream>` block per edge with **Pattern**, **Direction**, **Translation** (or **Reason**), and a **Spec file** pointer (to the relevant `acl-*.md` when the pattern involves an ACL, otherwise to the downstream BC's `bc-<slug>.md`).

**Rationale**:

- The graph doesn't model DDD relationship patterns today, and the article itself treats Context-Map patterns as human-reviewed-and-corrected ("relationship patterns in the Context Map — reviewed and corrected manually"). So the honest behaviour is: emit a best-guess scaffold, label every guess, and tell the human to confirm — exactly what FR-010 specifies.
- Heuristics that lean on what *is* in the graph (event→policy consumption, fan-out count, external flags) give a useful starting point without pretending to authority.
- Pointing the **Spec file** field at a concrete file (the ACL spec or the downstream BC canvas) matches the article's example, where each relationship names "the specific spec file that enforces it."

**Alternatives considered**:

- **Refuse to emit `context-map.md` until patterns are modeled**. Rejected — blocks a useful artifact indefinitely; a confirmed-later scaffold is better than nothing.
- **Emit patterns without the "(inferred)" marker**. Rejected — would mislead reviewers into trusting a guess.
- **Ask the LLM to choose the pattern from prose descriptions of each BC**. Available as an optional `llm_assist.infer_relationship_pattern` enhancement on top of the heuristic, but not the default and never authoritative — the marker and warning stay regardless of whether a heuristic or the LLM produced the guess.

---

## D7 — Frontend artifact folder layout and framework declaration

**Decision**: When `include_frontend=true` AND `spec_format=ddd` AND a frontend framework is declared (FR-020), write a sibling folder `specs/frontend/` (never nested inside any BC folder) containing exactly three markdown files:

```text
specs/frontend/
├── framework.md         # The declared framework + the conventions it implies
├── menu-structure.md    # Hierarchical menu / route tree grouped by BC; each leaf names a route, a BC, a User Story
└── ui-flow.md           # Narrative ordering of UI screens following the cross-BC event-modeling causal chain; each entry links back to a per-BC requirements.assets/<story>-<ui>.scene.json + .svg
```

The supported framework set is whatever the PRD-generation framework catalog (`api/features/prd_generation/prd_api_contracts.py::FrontendFramework`) enumerates. The 2026-05-12 amendment extends this enum to **Vue, React, Svelte** at minimum (the user named all three by example); the catalog is the source of truth and future additions are a downstream task, not a spec change.

`framework.md` carries:
- `Framework: <declared name>` as the first non-heading line (machine-readable preamble).
- A "Conventions" section sourced from the static catalog: component file shape (SFC for Vue, function components in `.tsx` for React, `.svelte` for Svelte), default state-management (Pinia / Zustand / Svelte stores), default routing library (Vue Router / React Router / SvelteKit routing), default styling approach (CSS-scoped / CSS-modules / Svelte scoped styles).
- A "Project Structure" pointer paragraph telling the coding agent that components live next to the route they back, and that wireframe assets are at `specs/bounded-contexts/<bc>/requirements.assets/<story>-<ui>.{scene.json,svg}` — not duplicated under `specs/frontend/`.
- When the catalog does not (yet) carry curated conventions for the declared framework, the Conventions section is rendered with a single line "(no curated conventions for this framework — confirm)" and a warning `frontend_framework_unsupported` is emitted; generation does not abort.

`menu-structure.md` carries a hierarchical bullet list, top level grouped by Bounded Context (BC display name), each leaf naming a route path, the User Story id, and the wireframe slug. The grouping order is the BC insertion order from the graph; within a BC the order is the User Story priority order (P1 first), falling back to insertion order when priority is absent. This file is the **navigation table of contents**, not the user-journey narrative — that's `ui-flow.md`.

`ui-flow.md` is the **causal narrative** (see D8 for the ordering algorithm). Each entry is a numbered section like:

```markdown
### 3. Confirm payment (Payments / US-9)

Triggered by: `OrderConfirmed` (from Order Management).
Wireframe assets:
- Element tree: see `../bounded-contexts/payments/requirements.md` § "Wireframe: Confirm payment"
- Scene graph: `../bounded-contexts/payments/requirements.assets/US-9-confirm-payment.scene.json`
- SVG (if rendered): `../bounded-contexts/payments/requirements.assets/US-9-confirm-payment.svg`
```

The relative `../bounded-contexts/...` paths preserve the canonical asset location; the frontend folder never duplicates assets (SC-010 requires each link reach a real file).

**Rationale**:

- A sibling folder rather than a nested one matches the user's explicit instruction: "Bounded Context에 Context 폴더 및 이하에 들어가는 게 아니라 스펙 밑에 프론트엔드라고 하는 폴더에 만들어지는 게 맞겠지." Frontend cuts across BCs by definition — slicing it under one BC would mis-shape the artifact.
- Three files (framework / menu / ui-flow) match the three questions a frontend engineer asks: "What am I building with?" (framework), "What's the IA?" (menu), "What order do users hit screens in?" (ui-flow). A single merged file would interleave these and lose the per-question readability.
- Relative links back to per-BC `requirements.assets/` make the frontend folder a *router* of attention; duplicating assets would create drift and bloat the zip.
- Hard-wiring three files (vs. a configurable set) keeps the contract small for v1; if a downstream need emerges (e.g. a separate `design-tokens.md`), it can be added as a new template later without breaking existing consumers.

**Alternatives considered**:

- **Generate inside `specs/bounded-contexts/_frontend/` to reuse the existing tree**. Rejected — leaks "frontend" into the bounded-contexts namespace and would confuse readers expecting that folder to hold BCs.
- **Single `Frontend-SPEC.md` rather than three files**. Rejected — couples three concerns; harder to update one (e.g. swap framework) without touching the others; harder for the `/generate-frontend` slash command to point at narrow sections.
- **Embed framework declaration in `PRD.md` instead of a dedicated file**. Rejected — `framework.md`'s first-line machine-readable preamble is the contract the `/generate-frontend` command parses; PRD.md's job (post-P6) is composition, not contracts.

---

## D8 — UI-flow causal ordering algorithm

**Decision**: Compute the ordering in `specs/frontend/ui-flow.md` by a deterministic topological sort over a DAG of (BC, UserStory, UI) triples connected by cross-BC Policy→Event chains, with a fallback to per-BC insertion order for unconnected islands.

Algorithm:

1. **Collect nodes**. For every Bounded Context, for every User Story with at least one bound UI, emit one DAG node keyed by `(bc_id, user_story_id, ui_id)`. Stories with multiple UIs emit one node per UI in the story's wireframe order. Stories without a bound UI are excluded (they are not "screens").
2. **Add intra-story edges**. Within one User Story, if it has UIs `[u1, u2, u3]` in wireframe order, add edges `(bc, us, u1) → (bc, us, u2) → (bc, us, u3)` — the story's internal screen sequence is preserved.
3. **Add intra-BC edges**. For two User Stories `us_a`, `us_b` in the same BC where `us_a`'s last UI's bound Command produces an Event that `us_b`'s first UI's bound Command consumes (via a Policy), add an edge from `us_a`'s last node to `us_b`'s first node.
4. **Add cross-BC edges**. For an upstream BC's Aggregate's Event consumed by a downstream BC's Policy that triggers a Command bound (via a User Story) to a UI, add an edge from the upstream UI node to the downstream UI node. This is the **causal cross-BC arrow** the spec's P5 acceptance scenario 3 demands.
5. **Topologically sort**. Standard Kahn's algorithm: at each step, take the node with no incoming edges and the smallest tiebreaker key `(bc_insertion_index, user_story_priority, user_story_insertion_index, ui_order_in_story)`. This makes the sort deterministic for SC-005/SC-010 byte-stability.
6. **Cycle handling**. If a cycle exists (rare — would require a Policy→Event→Policy→... loop), break it by removing the back-edge with the largest tiebreaker key, record a `ui_flow_cycle_broken` warning naming the removed edge, and continue. Generation does not abort.
7. **Islands**. Nodes with no in-or-out edges in the DAG (a UI that is not reached from any other UI's flow) are appended at the tail in insertion order with the label "(unreferenced flow — review)" per the edge case in the spec.
8. **Empty-cross-BC fallback**. If the cross-BC edge set is empty (single BC, or BCs that don't talk to each other), step 4 contributes nothing, the sort degenerates to "intra-BC, in BC insertion order", and a warning `ui_flow_no_cross_bc_edges` is emitted with the explanation per FR-021 fallback clause.

**Rationale**:

- A topological sort is the standard answer for "render in causal order"; the inputs (Policy/Event chains across BCs) are exactly the edges the Context Map already loads. Reusing that loader (`api/features/ddd_spec/repository.py`'s cross-BC flow query) keeps one source of truth for "what crosses BCs."
- Tiebreaker keys force determinism: SC-010 requires that two runs against the same graph produce the same ordering, which a topological sort *with a stable tiebreaker* guarantees.
- Handling cycles with a warning rather than an abort matches the v1 philosophy (FR-014: graceful degradation, never abort on partial data).
- Marking islands rather than dropping them ensures no UI silently disappears — the spec's edge case requires they appear "at the tail" with a review note so the human notices.

**Alternatives considered**:

- **Order by `User Story priority` only, ignoring cross-BC flow**. Rejected — collapses to the same shape as `requirements.md`, defeats the purpose of the new artifact.
- **Have the LLM narrate the ordering**. Rejected on determinism (SC-010) and because the structural problem (DAG → linearisation) has a known correct answer.
- **Manual sequencing via a graph property**. Rejected — adds a Neo4j schema change for a problem the existing flow edges already encode.

---

## D9 — PRD.md / CLAUDE.md content-split rule

**Decision**: Partition the currently-mixed prose in `generate_main_prd` (PRD.md) into two disjoint buckets and rebuild PRD.md and CLAUDE.md (or `.cursorrules`) from them. The partition is **declarative**: the bucket is decided by content shape, not by which existing section it came from.

| Bucket | Goes to | Recognisable by |
|--------|---------|-----------------|
| **Composition** | `PRD.md` | Tables / lists describing *what the project is*: project name + version, Technology Stack table, Bounded Contexts inventory table, project-file index (the "this lives in folder X" listing), deployment view (Docker / K8s / profile selections), pointers ("see `CLAUDE.md`", "see per-BC artifact folders") — *no imperative voice*. |
| **Prescription** | `CLAUDE.md` (when `ai_assistant=claude`) / `.cursorrules` (when `ai_assistant=cursor`) | Imperatives addressed to the coding agent or engineer: "you MUST read…", "Before starting implementation…", DDD naming rules, EARS-translation rules, GWT-test obligations, "always reference X by @-mention", "do not invent domain concepts". |

Boundary heuristic for the lint (implements SC-011):
- `PRD.md` rejected if any of these regex hits in non-quoted body: `(?i)\b(MUST|SHALL|MUST NOT|SHALL NOT|REQUIRED|Before starting|🚨|CRITICAL)\b`. The only allowed imperatives are inside markdown table cells or fenced code blocks (where they describe a downstream contract — e.g. an EARS line example).
- `CLAUDE.md` / `.cursorrules` rejected if it contains the Technology Stack table or the Bounded Contexts inventory table (it may reference them; it may not restate them).
- The lint runs at generation time (in `prd_artifact_generation.py` after each file is built) and emits `prd_split_lint_failed` with the offending substring + file name if it fails; the build aborts because this is a packaging contract, not a partial-data degrade.

Both files keep a one-line pointer to the other ("See PRD.md for the BC inventory and stack table" / "See CLAUDE.md for the engineering constitution") — this is *navigation*, not duplication.

**Rationale**:

- The user's framing is "PRD.md is constitution-like; that should move." The split is therefore content-shape based, not section-name based, because section names will drift over time but the *shape* (table vs imperative paragraph) is stable.
- The lint is a hard gate (abort on failure) rather than a warning because the contract's value comes from being *enforced*: a `PRD.md` that drifts back into prescriptive prose silently nullifies P6. The build aborting forces the issue to be fixed, not patched over.
- Allowing imperatives inside fenced code blocks lets us put example EARS lines in PRD.md without tripping the lint (e.g. when the Technology Stack section illustrates a constraint with a code-block sample), while still catching ambient "you MUST" prose.

**Alternatives considered**:

- **Soft warning instead of abort on lint failure**. Rejected — degrades silently; the user explicitly said this content "should" move, which we read as a contract not a preference.
- **Split by section name (allowlist)**. Rejected — fragile; section names are renamed routinely.
- **Move *all* prose out of PRD.md, leaving only tables**. Rejected — PRD.md still needs a brief project-purpose paragraph and pointers; the rule is "no imperatives", not "no prose".

---

## D10 — Role-based agents and migration of per-BC agent content

**Decision**: Remove `generate_agent_config` (the per-BC agent emitter) from the PRD-generation pipeline. Replace with two role-based agent generators emitted **exactly once per project** (not once per BC):

- `.claude/agents/frontend-engineer.md` — adopted by sessions implementing the frontend. Body shape:
  - **Role** paragraph: "You are the frontend engineer for this project. You read `specs/frontend/{framework,menu-structure,ui-flow}.md` and produce components in the declared framework."
  - **Skills you reference (do not restate)**: `@.claude/skills/ddd-principles.md` (DDD boundaries), `@.claude/skills/eventstorming-implementation.md` (sticker→component mapping for UI nodes), `@.claude/skills/gwt-test-generation.md` (frontend component tests from GWT criteria when applicable), and (when present) `@.claude/skills/<frontend-framework>.md`.
  - **When invoked**: list the slash commands that may invoke this agent — `/generate-frontend` (FR-024); future commands may join the list.
- `.claude/agents/ddd-specialist.md` — adopted by sessions implementing a Bounded Context. Body shape mirrors the above, referencing `@.claude/skills/ddd-spec-implementation.md`, `@.claude/skills/eventstorming-implementation.md`, `@.claude/skills/gwt-test-generation.md`, and the chosen tech-stack skill. **When invoked**: `/implement-ddd-bc`, `/implement-ddd-wireframe`.

**Migration of per-BC agent content**: the previous `generate_agent_config` produced four reusable kinds of prose: (a) the skills-reference list, (b) the scope/boundary statement, (c) the key-component recap (Aggregates / Commands / Events / ReadModels counts), (d) the responsibilities checklist. After this amendment:

- (a) Skills-reference list → migrated **upward** into the two role-based agents (one copy each, not per-BC).
- (b) Scope/boundary statement → migrated **downward** into the slash commands (`/implement-ddd-bc` already takes a `<bc-slug>` arg and now states "modify only files within the BC's module"). The per-BC nuance lives in the spec folder it points at, not in an agent file.
- (c) Key-component recap → already in `specs/bounded-contexts/<bc>/bc-<slug>.md` (the BC Canvas's Strategic Classification + Inbound/Outbound Communication tables); the agent file's recap was a restatement and is dropped.
- (d) Responsibilities checklist → migrated into `.claude/skills/ddd-spec-implementation.md`'s "verification checklist" section, which is already the contract `/implement-ddd-bc`'s "Done criteria" points at.

**Stale per-BC agent files in the user's working copy**: the generator never deletes consumer-side files (preserves FR-013 stance). When PRD generation runs after this amendment and sees pre-existing `.claude/agents/<bc_name>_agent.md` files in the target zip, it doesn't include them in the output zip (so they're not refreshed); the response includes a `skipped` entry per stale file with `reason: "deprecated_per_bc_agent"` so the user knows to delete their local copy. This matches the v1 pattern for stale assets (warn, don't delete).

**Rationale**:

- The user explicitly said per-BC agents are unnecessary and that role-based agents (Frontend Engineer, DDD Specialist) "make sense." Migrating the four kinds of useful content into skills/commands matches the user's "그 에이전트에 선언된 것 중에 쓸만한 게 있다면 그 내용을 스킬과 커맨드로 옮기면 될 것 같고" — nothing of value is lost, just relocated to its right home.
- Two role-based agents (not one) because a frontend engineer and a backend/domain engineer have meaningfully different read-orders and skill sets; collapsing them would force every session to load both skill bundles even when only one is relevant.
- Reporting (not deleting) deprecated per-BC agent files matches v1's conservative stance and lets the user see what is being deprecated rather than silently disappearing.

**Alternatives considered**:

- **Keep per-BC agents and add role-based agents alongside**. Rejected per user direction; also duplicates the skills-reference list N times.
- **One single "engineer" role-based agent**. Rejected — frontend and DDD reads diverge enough (UI scene-graph parsing vs. EARS-to-precondition translation) that one merged agent's body would either over-include or under-include for any given session.
- **Auto-delete stale per-BC agent files**. Rejected — too aggressive; the user might have hand-edited one. Warn instead.

---

## D11 — Viewport classification and the dominant-viewport agent prompt (2026-05-13 amendment)

**Decision**: Classify every bound wireframe's primary frame into one of `{mobile, tablet, desktop, unknown}` using the frame's **width** alone, with thresholds:

| Class | Rule |
|-------|------|
| `mobile` | `0 < width ≤ 480` |
| `tablet` | `480 < width ≤ 1024` |
| `desktop` | `width > 1024` |
| `unknown` | Scene graph missing, malformed, or primary frame has no positive width/height |

Aggregate counts per class across the whole project on `FrontendCompositionProjection.viewport_summary`. The single class covering ≥ **70%** of the *known-viewport* total (mobile + tablet + desktop, **excluding** unknown) becomes `dominant_viewport`; otherwise `None`. The threshold is the static module-level constant `api.features.ddd_spec.repository.DOMINANT_VIEWPORT_THRESHOLD = 0.70`; not a request field.

`specs/frontend/framework.md` renders the summary + `Dominant: <name>` (or `Dominant: mixed — ask the user`). The `frontend-engineer` agent body and `/generate-frontend` command body both carry a "Viewport intent check" step that runs BEFORE IA generation and asks the user verbatim:

> "Wireframes are predominantly `<dominant>` ({counts}). Should I design the whole menu IA, routing, breakpoints, and component chrome `<dominant>`-first?"

When the summary is `mixed`, the agent asks "Which viewport class should drive the IA?" instead. The answer is recorded at the top of the generated project's `README.md` and governs every downstream decision (breakpoints, container max-widths, navigation chrome — bottom-tab vs. sidebar — touch vs. pointer affordances). The agent's Stop conditions include (a) unanswered `mixed` state and (b) any `[viewport: <class>]` tag on a `ui-flow.md` entry that conflicts with the confirmed intent.

**Rationale**:

- **Width, not `max(w,h)` or `min(w,h)`**: the open-pencil flow in this repo always draws wireframes with frame width = device natural-orientation width. iPhone wireframes are 375×812 (mobile) or 390×844 (mobile); iPad wireframes are 768×1024 (tablet portrait) or 1024×768 (tablet landscape); desktop wireframes are 1440×900+. `max(w,h)` misfires on iPhone portrait (812 reads as tablet); `min(w,h)` misfires on 1440×900 (900 reads as tablet). Width tracks designer intent directly. Verified against 12 device cases in `test_viewport_classification.py`.
- **70% threshold**: tolerates 2–3 companion screens (admin panels, print views) on a project of ~10 wireframes without flipping the dominant to mixed, but catches the genuinely-mixed case where the project is split between two device targets. Picked once in code (not a knob) because a runtime override would invite users to "just bump it to 60%" rather than confront a real mixed-direction project, defeating the prompt's purpose.
- **Excluding `unknown` from the dominant calculation**: an `unknown` wireframe gave us no signal; bucketing it as a guess (e.g. "assume mobile") would shift the dominant percentage in invisible ways. Better to surface the `Unknown` row in `framework.md` so the user can see how much signal was lost.
- **Agent asks at run-time, NOT during PRD build**: the PRD build is non-interactive (zip export); the right moment to ask is when the user runs `/generate-frontend` in their Claude Code session, with the user present. The `framework.md` block + agent prompt body is the carrier.
- **Stop condition on tag conflict**: a single 1440-wide screen in an otherwise 375-wide project is a real design decision (admin desktop view, full-screen dashboard) — silently rendering it desktop-style under a mobile-first IA breaks the user's mental model. Forcing the agent to ask "companion / redirect / responsive breakpoint?" forces the design intent to surface.

**Alternatives considered**:

- **Skip classification, let the agent eyeball SVGs**. Rejected — defeats determinism (SC-005 + SC-014 require byte-stable framework.md across runs). Also offloads the decision to the agent, which gets it wrong silently.
- **Ask the user during PRD build (HTTP form field)**. Rejected — PRD build is one-shot and stateless; the user might generate a PRD for a graph they haven't seen yet. The agent's session at `/generate-frontend` is the right context (the wireframes are in front of them).
- **Make the 70% threshold a request body field**. Rejected — see "70% threshold" rationale; runtime knob defeats the prompt.
- **Five buckets (xs/sm/md/lg/xl)**. Rejected — more granularity than `mobile/tablet/desktop` adds without changing the IA question. Frontend agents need to know "phone or computer or in-between"; `xs` vs. `sm` is a CSS breakpoint detail.
