from __future__ import annotations

from datetime import datetime

from api.features.prd_generation.prd_api_contracts import Database, DeploymentStyle, Framework, FrontendFramework, TechStackConfig


# ============================================================================
# Source-of-truth render helpers (verification report §3.8)
#
# These surface the analyzer-grounded chain — Rule.statement / Example GWT /
# Open Decisions / UserStory index — into the spec markdown so Cursor/Claude
# receive code-grounded acceptance criteria rather than abstract descriptions.
# Each helper returns "" when the input is empty so the section is silently
# skipped from the spec instead of leaving an empty heading.
# ============================================================================

def render_source_rules_table(source_rules: list[dict]) -> str:
    """Per-US Source Business Rules — analyzer Rule.statement + source_function.

    Surfaces the *real source* of meaning (verification §3.8, source 1). The
    function tag is back-tickable so Cursor can jump to the file.
    """
    rules = [r for r in (source_rules or []) if r and r.get("statement")]
    if not rules:
        return ""
    out = "\n  - **Source Business Rules** (analyzer-grounded):\n\n"
    out += "    | seq | statement | host fn |\n"
    out += "    |---|---|---|\n"
    for r in rules:
        seq = (r.get("local_id") or "—").strip() or "—"
        stmt = (r.get("statement") or "").replace("|", "\\|")[:100]
        fn = (r.get("source_function") or "").strip()
        fn_md = f"`{fn}`" if fn else "—"
        out += f"    | {seq} | {stmt} | {fn_md} |\n"
    return out


def render_acceptance_tests(canonical_examples: list[dict]) -> str:
    """Per-US Acceptance Tests — Example.given/when_/then_ + AFFECTS_TABLE writes.

    Surfaces the schema-bound source (verification §3.8, source 2). Cursor/Claude
    use these as BDD-style acceptance criteria when writing tests.
    """
    exs = [e for e in (canonical_examples or []) if e and e.get("example_id")]
    if not exs:
        return ""
    out = "\n  - **Acceptance Tests** (from analyzer Examples):\n\n"
    for ex in exs[:5]:  # cap at 5 to keep spec readable; full list lives in Inspector
        eid = (ex.get("example_id") or "")[-40:]  # tail of long example_id
        boundary = " (boundary)" if ex.get("boundary") else ""
        given = (ex.get("given") or "").replace("\n", " ")[:120]
        when_ = (ex.get("when_") or "").replace("\n", " ")[:120]
        then_ = (ex.get("then_") or "").replace("\n", " ")[:120]
        write_hint = ""
        if ex.get("table") and ex.get("op"):
            write_hint = f" — *{ex['op']} on `{ex['table']}`*"
        out += f"    - **{eid}**{boundary}{write_hint}\n"
        if given:
            out += f"      - **Given**: {given}\n"
        if when_:
            out += f"      - **When**: {when_}\n"
        if then_:
            out += f"      - **Then**: {then_}\n"
    if len(exs) > 5:
        out += f"    - *(+{len(exs) - 5} more — see Inspector)*\n"
    return out


def render_open_decisions(questions: list[dict]) -> str:
    """BC-level Open Decisions — analyzer Question nodes ATTACHED_TO this BC.

    Each Question represents a policy/correctness decision the analyzer flagged
    as ambiguous in the source code. Cursor/Claude should not silently resolve
    these — they need user confirmation.
    """
    qs = [q for q in (questions or []) if q and q.get("text")]
    if not qs:
        return ""
    out = "\n## Open Decisions (정책 검토 필요)\n\n"
    out += "> ⚠️ The analyzer flagged these as ambiguous in the source code. **Confirm with the user before resolving in implementation.**\n\n"
    for q in qs:
        text = (q.get("text") or "").strip()
        reason = (q.get("reason") or "").strip()
        host_fn = (q.get("host_function") or "").strip()
        host_md = f" (host fn: `{host_fn}`)" if host_fn else ""
        out += f"- **Q**{host_md}: {text}\n"
        if reason:
            out += f"  - *Reason*: {reason}\n"
    return out


def render_node_source_rules(source_rules: list[dict], indent: str = "  ") -> str:
    """Per-ES-node Source Business Rules — Aggregate / Command / Event level.

    Same shape as render_source_rules_table but adds a `via_us` column so
    Cursor/Claude can see which UserStory's grounding produced this rule
    (multiple US's may IMPLEMENT the same Aggregate/Command).
    """
    rules = [r for r in (source_rules or []) if r and r.get("statement")]
    if not rules:
        return ""
    out = f"\n{indent}- **Source Business Rules** ({len(rules)} via grounded US):\n\n"
    out += f"{indent}  | seq | statement | host fn | via US |\n"
    out += f"{indent}  |---|---|---|---|\n"
    for r in rules:
        seq = (r.get("local_id") or "—").strip() or "—"
        stmt = (r.get("statement") or "").replace("|", "\\|").replace("\n", " ")[:90]
        fn = (r.get("source_function") or "").strip()
        fn_md = f"`{fn}`" if fn else "—"
        via = (r.get("via_us") or "—")
        out += f"{indent}  | {seq} | {stmt} | {fn_md} | {via} |\n"
    return out


def render_node_source_examples(source_examples: list[dict], indent: str = "    ") -> str:
    """Per-Event Acceptance Tests from Example nodes (boundary cases included).

    Cap at 3 to keep the per-Event subsection scannable; the full list lives
    in the per-US section earlier in the spec.
    """
    exs = [e for e in (source_examples or []) if e and e.get("example_id")]
    if not exs:
        return ""
    out = f"\n{indent}- **Acceptance source** (from Example):\n"
    for ex in exs[:3]:
        eid = (ex.get("example_id") or "")[-30:]
        boundary = " (boundary)" if ex.get("boundary") else ""
        write = ""
        if ex.get("table") and ex.get("op"):
            write = f" — *{ex['op']} on `{ex['table']}`*"
        given = (ex.get("given") or "").replace("\n", " ")[:90]
        when_ = (ex.get("when_") or "").replace("\n", " ")[:90]
        then_ = (ex.get("then_") or "").replace("\n", " ")[:90]
        out += f"{indent}  - **{eid}**{boundary}{write}\n"
        if given: out += f"{indent}    - **Given**: {given}\n"
        if when_: out += f"{indent}    - **When**: {when_}\n"
        if then_: out += f"{indent}    - **Then**: {then_}\n"
    if len(exs) > 3:
        out += f"{indent}  - *(+{len(exs) - 3} more)*\n"
    return out


def render_user_story_index(user_stories: list[dict]) -> str:
    """BC-level UserStory index with grounding indicator.

    For each US, signals whether it has analyzer code-grounding (sourceRules > 0)
    or is description-only (0-rule task — see verification §3.8). Cursor/Claude
    treat the latter as "needs new implementation" rather than "translate
    existing code intent".
    """
    uss = [u for u in (user_stories or []) if u and u.get("id")]
    if not uss:
        return ""
    out = "\n## User Stories — code-grounding map\n\n"
    out += "| US id | role | action | source rules | grounding |\n"
    out += "|---|---|---|---|---|\n"
    for us in uss:
        sid = us.get("id", "")
        role = (us.get("role") or "").strip() or "—"
        action = (us.get("action") or "").replace("|", "\\|").replace("\n", " ")[:80]
        rule_count = len(us.get("sourceRules") or [])
        if rule_count > 0:
            grounding = f"**{rule_count} rules** ✅"
        else:
            grounding = "0 — *description-only*"
        out += f"| {sid} | {role} | {action} | {rule_count} | {grounding} |\n"
    return out


def generate_main_prd(bcs: list[dict], config: TechStackConfig) -> str:
    """PRD.md — project composition (FR-022, research D9).

    Holds only compositional content: project name, technology-stack
    table, Bounded Contexts inventory, project-file index, deployment
    view, and pointers to the engineering constitution that lives in
    ``CLAUDE.md`` (when ``ai_assistant=claude``) or ``.cursorrules``
    (when ``ai_assistant=cursor``). Prescriptive prose (read-order, DDD
    principles, EARS rules, GWT obligation, "🚨 CRITICAL"-style imperative
    blocks) does NOT belong here — the
    :func:`api.features.prd_generation.prd_split_lint.lint_disjoint` lint
    aborts the zip build with ``prd_split_lint_failed`` if it leaks back in.
    """
    has_frontend = bool(config.include_frontend and config.frontend_framework)
    using_claude = config.ai_assistant.value == "claude"
    spec_uses_ddd = config.spec_format.value == "ddd"

    parts: list[str] = []
    parts.append(f"# {config.project_name}\n")
    parts.append("")
    parts.append("> Project composition. The engineering rules live in")
    parts.append(
        "> `CLAUDE.md`" if using_claude else "> `.cursorrules`"
    )
    parts.append("> — read that before writing code.")
    parts.append("")

    # Technology Stack table.
    parts.append("## Technology Stack")
    parts.append("")
    parts.append("| Component | Choice |")
    parts.append("|-----------|--------|")
    parts.append(f"| Language | {config.language.value} |")
    parts.append(f"| Framework | {config.framework.value} |")
    parts.append(f"| Messaging | {config.messaging.value} |")
    parts.append(f"| Database | {config.database.value} |")
    parts.append(f"| Deployment | {config.deployment.value} |")
    if has_frontend:
        parts.append(f"| Frontend framework | {config.frontend_framework.value} |")
    parts.append("")

    # Bounded Contexts inventory table.
    parts.append("## Bounded Contexts")
    parts.append("")
    parts.append("| BC Name | Aggregates | Commands | Events | ReadModels | Policies | UIs |")
    parts.append("|---------|------------|----------|--------|------------|----------|-----|")
    for bc in bcs:
        aggs = bc.get("aggregates", []) or []
        cmds = sum(len(a.get("commands", []) or []) for a in aggs)
        evts = sum(len(a.get("events", []) or []) for a in aggs)
        rms = len(bc.get("readmodels", []) or [])
        pols = len(bc.get("policies", []) or [])
        uis = len(bc.get("uis", []) or [])
        parts.append(
            f"| {bc.get('name', 'Unknown')} | {len(aggs)} | {cmds} | {evts} | {rms} | {pols} | {uis} |"
        )
    parts.append("")

    # Project file index — pure listing, no imperatives.
    parts.append("## Project Files")
    parts.append("")
    if using_claude:
        parts.append("- `CLAUDE.md` — engineering constitution for AI assistants")
    else:
        parts.append("- `.cursorrules` — engineering constitution for the Cursor IDE")
    parts.append("- `README.md` — project overview")
    if spec_uses_ddd:
        parts.append("- `specs/context-map.md` — system-level Context Map")
        parts.append("- `specs/bounded-contexts/<bc-slug>/` — per-BC DDD artifacts (domain-terms, bc-canvas, aggregate specs, requirements + wireframes)")
        if has_frontend:
            parts.append("- `specs/frontend/framework.md` — declared frontend framework + conventions")
            parts.append("- `specs/frontend/menu-structure.md` — navigation tree grouped by BC")
            parts.append("- `specs/frontend/ui-flow.md` — causal ordering of UI screens across the event-modeling flow")
    else:
        for bc in bcs:
            bc_name = bc.get("name", "Unknown")
            bc_name_slug = bc_name.lower().replace(" ", "_")
            parts.append(f"- `specs/{bc_name_slug}_spec.md` — {bc_name} specification")
    if using_claude:
        parts.append("- `.claude/skills/` — reference skills (DDD principles, Event Storming mapping, GWT tests, tech stack)")
        if spec_uses_ddd:
            parts.append("- `.claude/agents/ddd-specialist.md` — role-based agent for backend / domain work")
            if has_frontend:
                parts.append("- `.claude/agents/frontend-engineer.md` — role-based agent for frontend work")
            parts.append("- `.claude/commands/implement-ddd-bc.md` — slash command for one BC's full implementation")
            parts.append("- `.claude/commands/implement-ddd-wireframe.md` — slash command for a single wireframe")
            if has_frontend:
                parts.append("- `.claude/commands/generate-frontend.md` — slash command for the whole frontend")
    else:
        parts.append("- `.cursor/rules/` — Cursor rule files (DDD, Event Storming, GWT, tech stack)")
    if config.include_docker:
        parts.append("- `docker-compose.yml`, `Dockerfile` — local container setup")
    parts.append("")

    # Deployment view — descriptive (no imperatives).
    parts.append("## Deployment View")
    parts.append("")
    parts.append(f"- Deployment style: {config.deployment.value}")
    parts.append(f"- Messaging platform: {config.messaging.value}")
    parts.append(f"- Database: {config.database.value}")
    parts.append(f"- Container packaging: {'included (docker-compose + Dockerfile)' if config.include_docker else 'not included'}")
    parts.append(f"- Kubernetes manifests: {'included' if config.include_kubernetes else 'not included'}")
    parts.append("")

    # Cross-references — pointer lines only.
    parts.append("## Cross-References")
    parts.append("")
    if using_claude:
        parts.append("- Read `CLAUDE.md` for the engineering constitution and read-order before writing code.")
    else:
        parts.append("- Read `.cursorrules` for the engineering constitution and read-order before writing code.")
    if spec_uses_ddd:
        parts.append("- Read `specs/bounded-contexts/<bc-slug>/` for each BC's domain model.")
        parts.append("- Read `specs/context-map.md` for cross-BC relationships.")
        if has_frontend:
            parts.append("- Read `specs/frontend/{framework,menu-structure,ui-flow}.md` for the frontend perspective.")
    else:
        parts.append("- Read each `specs/<bc_name>_spec.md` for that BC's details.")
    parts.append("")
    return "\n".join(parts)


def generate_bc_spec(bc: dict, config: TechStackConfig) -> str:
    name = bc.get("name", "Unknown")
    spec = f"""# {name} Bounded Context Specification

> **Note**: This is a detailed specification for the {name} Bounded Context.  
> For overall architecture and principles, refer to **`PRD.md`** (main PRD document).  
> For implementation guidance, refer to the AI assistant configuration files (use @mention in Cursor):
> - Cursor: `@.cursorrules` + `@{{framework}}` (e.g., `@spring-boot`) + `@ddd-principles`, `@eventstorming-implementation`, `@gwt-test-generation`
> - Claude: `.claude/agents/{{bc_name}}_agent.md`

## Overview
- **BC ID**: {bc.get("id", "")}
- **Description**: {bc.get("description", "No description")}
- **Display name (UI)**: {bc.get('displayName') or name}
- **Main PRD**: See `PRD.md` for architecture principles and guidelines

**UI text**: Use `displayName` for all UI labels, button text, and form field labels in this BC (see each node and property below).
"""

    # Open Decisions + UserStory index — surface analyzer-grounded source-of-truth
    # at BC top so Cursor/Claude see grounding map before implementation guidance.
    spec += render_open_decisions(bc.get("questions", []))
    spec += render_user_story_index(bc.get("userStories", []))

    # Per-US Source Rules + Acceptance Tests — verification §3.8 source 1+2
    user_stories = bc.get("userStories", []) or []
    grounded_us = [u for u in user_stories if u.get("sourceRules")]
    if grounded_us:
        spec += "\n## User Stories — analyzer-grounded detail\n"
        spec += "\n> Each US below has **code-grounded source rules** (Rule.statement) and **acceptance tests** (Example GWT). Treat these as the implementation contract — the action text is narrative, the rules + examples are the source-of-truth.\n"
        for us in grounded_us:
            sid = us.get("id", "")
            role = (us.get("role") or "").strip()
            action = (us.get("action") or "").strip()
            benefit = (us.get("benefit") or "").strip()
            spec += f"\n### {sid}\n"
            if role or action or benefit:
                spec += "- **Story**:"
                if role: spec += f" *as a* `{role}`"
                if action: spec += f", *I want to* {action}"
                if benefit: spec += f", *so that* {benefit}"
                spec += "\n"
            spec += render_source_rules_table(us.get("sourceRules", []))
            spec += render_acceptance_tests(us.get("canonicalExamples", []))

    spec += """
## Aggregates
"""
    for agg in bc.get("aggregates", []) or []:
        agg_display = agg.get("displayName") or agg.get("name", "Unknown")
        spec += f"\n### {agg.get('name', 'Unknown')} (UI: {agg_display})\n"
        if agg.get("rootEntity"):
            spec += f"- Root Entity: `{agg['rootEntity']}`\n"
        
        # Aggregate Invariants
        if agg.get("invariants"):
            invariants = agg["invariants"]
            if isinstance(invariants, list) and len(invariants) > 0:
                spec += "- Invariants:\n"
                for inv in invariants:
                    spec += f"  - {inv}\n"
        
        # Aggregate Enumerations
        if agg.get("enumerations"):
            enums = agg["enumerations"]
            if isinstance(enums, list) and len(enums) > 0:
                spec += "- Enumerations:\n"
                for enum in enums:
                    if isinstance(enum, dict):
                        enum_name = enum.get("name", "Unknown")
                        enum_values = enum.get("values", [])
                        spec += f"  - `{enum_name}`: {', '.join(enum_values) if enum_values else 'N/A'}\n"
        
        # Aggregate Value Objects
        if agg.get("valueObjects"):
            vos = agg["valueObjects"]
            if isinstance(vos, list) and len(vos) > 0:
                spec += "- Value Objects:\n"
                for vo in vos:
                    if isinstance(vo, dict):
                        vo_name = vo.get("name", "Unknown")
                        spec += f"  - `{vo_name}`\n"
        
        # Aggregate Properties
        if agg.get("properties"):
            spec += "- Properties (use displayName for form labels):\n"
            for prop in agg["properties"]:
                if prop.get("id"):
                    prop_type = prop.get("type", "String")
                    is_key = " (Key)" if prop.get("isKey") else ""
                    is_fk = f" (FK -> {prop.get('fkTargetHint', '')})" if prop.get("isForeignKey") else ""
                    prop_display = prop.get("displayName") or prop.get("name", "")
                    spec += f"  - `{prop.get('name', '')}` (UI label: {prop_display}): {prop_type}{is_key}{is_fk}\n"
                    if prop.get("description"):
                        spec += f"    - {prop.get('description')}\n"

        # Aggregate-level Source Business Rules — verification §3.8 source 1
        # rolled up from grounded US's that IMPLEMENTS this Aggregate.
        spec += render_node_source_rules(agg.get("sourceRules", []), indent="")

        # Commands with Properties
        if agg.get("commands"):
            spec += "- Commands (use displayName for button/form title):\n"
            for cmd in agg["commands"]:
                if cmd.get("id"):
                    cmd_name = cmd.get("name", "")
                    cmd_display = cmd.get("displayName") or cmd_name
                    cmd_actor = cmd.get("actor", "")
                    cmd_category = cmd.get("category", "")
                    cmd_desc = cmd.get("description", "")
                    spec += f"  - `{cmd_name}` (UI label: {cmd_display})"
                    if cmd_actor:
                        spec += f" (actor: {cmd_actor})"
                    if cmd_category:
                        spec += f" [category: {cmd_category}]"
                    spec += "\n"
                    if cmd_desc:
                        spec += f"    - Description: {cmd_desc}\n"
                    if cmd.get("inputSchema"):
                        spec += f"    - Input Schema: {cmd['inputSchema']}\n"
                    if cmd.get("properties"):
                        spec += "    - Properties (use displayName for form field labels):\n"
                        for prop in cmd["properties"]:
                            if prop.get("id"):
                                prop_type = prop.get("type", "String")
                                is_required = " (required)" if prop.get("isRequired") else ""
                                prop_display = prop.get("displayName") or prop.get("name", "")
                                spec += f"      - `{prop.get('name', '')}` (UI: {prop_display}): {prop_type}{is_required}\n"
                    # Per-Command Source Rules (= preconditions in DDD)
                    spec += render_node_source_rules(cmd.get("sourceRules", []), indent="    ")

        # Events with Properties
        if agg.get("events"):
            spec += "- Events:\n"
            for evt in agg["events"]:
                if evt.get("id"):
                    evt_name = evt.get("name", "")
                    evt_display = evt.get("displayName") or evt_name
                    evt_version = evt.get("version", "1")
                    evt_desc = evt.get("description", "")
                    spec += f"  - `{evt_name}` (UI: {evt_display}, v{evt_version})\n"
                    if evt_desc:
                        spec += f"    - Description: {evt_desc}\n"
                    if evt.get("schema"):
                        spec += f"    - Schema: {evt['schema']}\n"
                    if evt.get("properties"):
                        spec += "    - Properties (use displayName for UI labels):\n"
                        for prop in evt["properties"]:
                            if prop.get("id"):
                                prop_type = prop.get("type", "String")
                                prop_display = prop.get("displayName") or prop.get("name", "")
                                spec += f"      - `{prop.get('name', '')}` (UI: {prop_display}): {prop_type}\n"
                    # Per-Event Source Rules (reached via emitting Command's US)
                    spec += render_node_source_rules(evt.get("sourceRules", []), indent="    ")
                    # Per-Event Acceptance source — Example given/when_/then_ + write op
                    spec += render_node_source_examples(evt.get("sourceExamples", []), indent="    ")

    # ReadModels
    if bc.get("readmodels"):
        spec += "\n## ReadModels (use displayName for page title/list headers)\n"
        for rm in bc["readmodels"]:
            if rm.get("id"):
                rm_display = rm.get("displayName") or rm.get("name", "Unknown")
                spec += f"\n### {rm.get('name', 'Unknown')} (UI: {rm_display})\n"
                if rm.get("description"):
                    spec += f"- Description: {rm.get('description')}\n"
                if rm.get("provisioningType"):
                    spec += f"- Provisioning Type: {rm.get('provisioningType')}\n"
                if rm.get("actor"):
                    spec += f"- Actor: {rm.get('actor')}\n"
                if rm.get("isMultipleResult"):
                    spec += f"- Result Type: {rm.get('isMultipleResult')}\n"
                if rm.get("properties"):
                    spec += "- Properties (use displayName for column/field labels):\n"
                    for prop in rm["properties"]:
                        if prop.get("id"):
                            prop_type = prop.get("type", "String")
                            prop_display = prop.get("displayName") or prop.get("name", "")
                            spec += f"  - `{prop.get('name', '')}` (UI: {prop_display}): {prop_type}\n"

    # Policies
    if bc.get("policies"):
        spec += "\n## Policies\n"
        for pol in bc["policies"]:
            if pol.get("id"):
                pol_display = pol.get("displayName") or pol.get("name", "")
                spec += f"- `{pol.get('name','')}` (UI: {pol_display})\n"
                if pol.get("description"):
                    spec += f"  - Description: {pol.get('description')}\n"
                trigger_evt_name = pol.get('triggerEventName', 'N/A')
                trigger_evt_bc = pol.get('triggerEventBCName', '')
                if trigger_evt_bc and trigger_evt_bc != bc.get('name', ''):
                    spec += f"  - Triggers: `{trigger_evt_name}` (from BC: {trigger_evt_bc})\n"
                else:
                    spec += f"  - Triggers: `{trigger_evt_name}`\n"
                invoke_cmd_name = pol.get('invokeCommandName', 'N/A')
                invoke_cmd_bc = pol.get('invokeCommandBCName', '')
                if invoke_cmd_bc and invoke_cmd_bc != bc.get('name', ''):
                    spec += f"  - Invokes: `{invoke_cmd_name}` (in BC: {invoke_cmd_bc})\n"
                else:
                    spec += f"  - Invokes: `{invoke_cmd_name}`\n"

    # UI Wireframes
    if bc.get("uis"):
        spec += "\n## UI Wireframes\n"
        for ui in bc["uis"]:
            if ui.get("id"):
                spec += f"- `{ui.get('name', 'Unknown')}`\n"
                if ui.get("description"):
                    spec += f"  - Description: {ui.get('description')}\n"
                if ui.get("attachedToType") and ui.get("attachedToName"):
                    spec += f"  - Attached to: {ui.get('attachedToType')} `{ui.get('attachedToName')}`\n"
                if ui.get("template"):
                    template = ui.get("template", "").strip()
                    if template:
                        spec += f"  - Wireframe Template:\n"
                        spec += f"    ```html\n"
                        # Template을 들여쓰기하여 표시 (각 줄 앞에 4칸 공백 추가)
                        for line in template.split('\n'):
                            spec += f"    {line}\n"
                        spec += f"    ```\n"

    # GWT Test Cases
    if bc.get("gwts"):
        spec += "\n## GWT Test Cases\n"
        for gwt in bc["gwts"]:
            if gwt.get("id"):
                parent_type = gwt.get("parentType", "Unknown")
                spec += f"\n### GWT for {parent_type} `{gwt.get('parentId', '')}`\n"
                if gwt.get("givenRef"):
                    given = gwt["givenRef"]
                    if isinstance(given, dict):
                        spec += f"- **Given**: {given.get('name', 'N/A')}\n"
                        if given.get("description"):
                            spec += f"  - {given.get('description')}\n"
                if gwt.get("whenRef"):
                    when = gwt["whenRef"]
                    if isinstance(when, dict):
                        spec += f"- **When**: {when.get('name', 'N/A')}\n"
                        if when.get("description"):
                            spec += f"  - {when.get('description')}\n"
                if gwt.get("thenRef"):
                    then = gwt["thenRef"]
                    if isinstance(then, dict):
                        spec += f"- **Then**: {then.get('name', 'N/A')}\n"
                        if then.get("description"):
                            spec += f"  - {then.get('description')}\n"
                if gwt.get("testCases"):
                    test_cases = gwt["testCases"]
                    if isinstance(test_cases, list) and len(test_cases) > 0:
                        spec += f"\n#### Test Scenarios ({len(test_cases)} cases)\n"
                        for idx, tc in enumerate(test_cases, 1):
                            if isinstance(tc, dict):
                                spec += f"\n**Scenario {idx}**: {tc.get('scenarioDescription', 'N/A')}\n"
                                if tc.get("givenFieldValues"):
                                    spec += "- Given values:\n"
                                    for k, v in tc.get("givenFieldValues", {}).items():
                                        spec += f"  - `{k}`: {v}\n"
                                if tc.get("whenFieldValues"):
                                    spec += "- When values:\n"
                                    for k, v in tc.get("whenFieldValues", {}).items():
                                        spec += f"  - `{k}`: {v}\n"
                                if tc.get("thenFieldValues"):
                                    spec += "- Then values:\n"
                                    for k, v in tc.get("thenFieldValues", {}).items():
                                        spec += f"  - `{k}`: {v}\n"

    spec += "\n## Implementation Notes\n"
    spec += f"- Framework: `{config.framework.value}`\n- Messaging: `{config.messaging.value}`\n"
    spec += f"\n## Related Files\n"
    spec += f"- **Main PRD**: `PRD.md` - Overall architecture, principles, and development guidelines\n"
    bc_name_slug = name.lower().replace(" ", "_")
    if config.ai_assistant.value == "cursor":
        spec += f"\n### Cursor Rules (Implementation Guidelines)\n"
        spec += f"- **Global Rules**: `.cursorrules` - General DDD principles and coding standards\n"
        spec += f"- **DDD Principles**: `.cursor/rules/ddd-principles.mdc` - DDD patterns (always applied)\n"
        spec += f"- **Event Storming Implementation**: `.cursor/rules/eventstorming-implementation.mdc` - Sticker-to-code mapping (Command, Event, Aggregate, ReadModel, Policy, UI)\n"
        spec += f"- **GWT Test Generation**: `.cursor/rules/gwt-test-generation.mdc` - GWT (Given/When/Then) test patterns\n"
        spec += f"- **Tech Stack Rules**: `.cursor/rules/{config.framework.value}.mdc` - {config.framework.value} implementation guidelines\n"
        if config.include_frontend and config.frontend_framework:
            spec += f"- **Frontend Rules**: `.cursor/rules/{config.frontend_framework.value}.mdc` - Frontend framework implementation guidelines\n"
        if config.deployment == DeploymentStyle.MICROSERVICES:
            spec += f"- **API Gateway**: `.cursor/rules/api-gateway.mdc` - Gateway routing, CORS, and service discovery\n"
    else:
        spec += f"\n### Claude Skills (Implementation Guidelines)\n"
        spec += f"- **DDD Principles**: `.claude/skills/ddd-principles.md` - DDD patterns (always reference)\n"
        spec += f"- **Event Storming Implementation**: `.claude/skills/eventstorming-implementation.md` - Sticker-to-code mapping (Command, Event, Aggregate, ReadModel, Policy, UI)\n"
        spec += f"- **GWT Test Generation**: `.claude/skills/gwt-test-generation.md` - GWT (Given/When/Then) test patterns\n"
        spec += f"- **Tech Stack Skills**: `.claude/skills/{config.framework.value}.md` - {config.framework.value} implementation guidelines\n"
        if config.include_frontend and config.frontend_framework:
            spec += f"- **Frontend Skills**: `.claude/skills/{config.frontend_framework.value}.md` - Frontend framework implementation guidelines\n"
        if config.deployment == DeploymentStyle.MICROSERVICES:
            spec += f"- **API Gateway**: `.claude/skills/api-gateway.md` - Gateway routing, CORS, and service discovery\n"
        spec += f"- **BC Agent**: `.claude/agents/{bc_name_slug}_agent.md` - BC-specific agent configuration\n"
    spec += f"- **Project Context**: `CLAUDE.md` - Project overview for AI assistants\n"
    return spec


def generate_claude_md(bcs: list[dict], config: TechStackConfig) -> str:
    """CLAUDE.md — the engineering constitution (FR-022, research D9).

    Holds the prescriptive content the PRD.md used to carry: read-order,
    DDD principles, EARS-translation rules, GWT-test obligation,
    "do-not-invent-domain-concepts" rule, and skills references. Does NOT
    restate the technology-stack table or the Bounded Contexts inventory
    — those live in ``PRD.md`` and this file references them by pointer.
    The
    :func:`api.features.prd_generation.prd_split_lint.lint_disjoint` lint
    aborts the zip build with ``prd_split_lint_failed`` if either rule is
    violated.
    """
    spec_uses_ddd = config.spec_format.value == "ddd"
    has_frontend = bool(config.include_frontend and config.frontend_framework)
    fw = config.framework.value
    front_fw = config.frontend_framework.value if has_frontend else None
    in_microservices = config.deployment == DeploymentStyle.MICROSERVICES

    parts: list[str] = []
    parts.append("# CLAUDE.md — Engineering Constitution")
    parts.append("")
    parts.append("> The rules every coding pass MUST honour. See `PRD.md` for the")
    parts.append("> project composition (stack, BC inventory, file index, deployment view).")
    parts.append("")

    # --- Read-order (read this first) ------------------------------------
    parts.append("## Read Order")
    parts.append("")
    parts.append("Before writing any code, load these in order:")
    parts.append("")
    parts.append("1. This file (`CLAUDE.md`) — the constitution.")
    if spec_uses_ddd:
        parts.append("2. `specs/context-map.md` — system-level Context Map. Inferred patterns carry `(inferred — confirm)`; pause and consult the user before treating them as authoritative.")
        parts.append("3. For each Bounded Context you touch: `specs/bounded-contexts/<bc-slug>/`")
        parts.append("   - `bc-<bc-slug>.md` (Bounded Context Canvas) → module docstring / README + cross-BC contract direction.")
        parts.append("   - `domain-terms.md` (Ubiquitous Language) → every name in code MUST appear verbatim in this file. Entries under \"Aliases to AVOID\" are forbidden names.")
        parts.append("   - `aggregates/aggregate-<slug>.md` → translate the nine sections directly onto code (root entity, member entities/VOs, properties + mutability, EARS invariants, corrective policies, commands table, events emitted, repository interface).")
        parts.append("   - `requirements.md` → user stories grouped by aggregate; each story's acceptance criteria appears in EARS form.")
        parts.append("   - `acl-<system>.md` (when present) → adapter translation maps; no external type leaks into core.")
        parts.append("4. `.claude/skills/ddd-spec-implementation.md` — implementation order + verification checklist (binding).")
        parts.append("5. `.claude/skills/ddd-principles.md`, `eventstorming-implementation.md`, `gwt-test-generation.md` — pattern references.")
        parts.append(f"6. `.claude/skills/{fw}.md` — {fw} implementation patterns.")
        if has_frontend:
            parts.append("7. `specs/frontend/framework.md` / `menu-structure.md` / `ui-flow.md` — read all three before writing frontend code.")
            parts.append(f"8. `.claude/skills/{front_fw}.md` — {front_fw}-specific frontend patterns.")
    else:
        parts.append("2. For each Bounded Context you touch: `specs/<bc_name>_spec.md` — contains aggregates, commands, events, ReadModels, policies, UI wireframes, GWT tests.")
        parts.append("3. `.claude/skills/ddd-principles.md`, `eventstorming-implementation.md`, `gwt-test-generation.md` — pattern references.")
        parts.append(f"4. `.claude/skills/{fw}.md` — {fw} implementation patterns.")
        if has_frontend:
            parts.append(f"5. `.claude/skills/{front_fw}.md` — frontend-specific patterns.")
    parts.append("")
    parts.append("Skip this read-order at your peril: every spec file is the binding contract for the slice of code you are about to write.")
    parts.append("")

    # --- DDD principles -------------------------------------------------
    parts.append("## DDD Principles")
    parts.append("")
    parts.append("- **Names are sacred.** Aggregate / Command / Event / ReadModel / Policy names in code MUST match the spec verbatim. No `Confirm` → `Approve` synonym drift. Entries under domain-terms.md's \"Aliases to AVOID\" are forbidden names.")
    parts.append("- **Aggregate is the consistency boundary.** State changes happen only through commands on the aggregate root; cross-aggregate updates ride events.")
    parts.append("- **Commands are imperative** (`CreateOrder`, `CancelOrder`); **Events are past tense** (`OrderCreated`, `OrderCancelled`).")
    parts.append("- **No direct cross-BC calls.** BCs communicate via events through the messaging platform. A Policy in one BC subscribes to events from another and invokes its own commands.")
    parts.append("- **Do not invent domain concepts.** If a needed concept is not in the spec, pause and ask. The graph is the source of truth; the artifacts are its projection.")
    parts.append("- **Mutability hints in the Properties table are binding.** \"Immutable after creation\" → no setter. \"Mutable through commands only\" → state changes only via aggregate command methods, never via direct field assignment.")
    parts.append("")

    # --- EARS translation rules ----------------------------------------
    parts.append("## EARS Translation Rules")
    parts.append("")
    parts.append("Each numbered line in `Enforced Invariants` / `Acceptance Criteria` is in EARS form. Translate as follows:")
    parts.append("")
    parts.append("- `THE <Aggregate> SHALL <C>` → unconditional invariant. Assert in the constructor AND every state-changing method. The aggregate is never legally in a state that violates it.")
    parts.append("- `WHEN <trigger> THEN system SHALL <obligation>` → command method `<trigger>` MUST produce `<obligation>` (state change + event emission) when called.")
    parts.append("- `WHEN <trigger> IF <state> THEN system SHALL <obligation>` → command method `<trigger>` has precondition `<state>` (guard clause that rejects when false) and postcondition `<obligation>`. Use the `.claude/skills/gwt-test-generation.md` patterns for the matching tests.")
    parts.append("- Multiple `Given` clauses are joined with `AND`; multiple `Then` lines each become a separate `SHALL` line under the same `WHEN/IF`.")
    parts.append("")

    # --- GWT obligation ------------------------------------------------
    parts.append("## GWT-Test Obligation")
    parts.append("")
    parts.append("Every numbered EARS line in an aggregate spec MUST have a corresponding test that fails if the invariant is broken. Use Given/When/Then style following `.claude/skills/gwt-test-generation.md`. Cross-BC scenarios in `requirements.md` MUST have integration tests that exercise the event flow.")
    parts.append("")

    # --- Skills references --------------------------------------------
    parts.append("## Skills")
    parts.append("")
    parts.append("Reference these by relative path; they are not restated here:")
    parts.append("")
    parts.append("- `.claude/skills/ddd-principles.md` — DDD patterns and aggregate rules (always).")
    parts.append("- `.claude/skills/eventstorming-implementation.md` — sticker-to-code mapping (Command → API, Event → message, ReadModel → query API, UI → component).")
    parts.append("- `.claude/skills/gwt-test-generation.md` — Given/When/Then patterns for tests of EARS invariants.")
    parts.append(f"- `.claude/skills/{fw}.md` — {fw} implementation patterns.")
    if spec_uses_ddd:
        parts.append("- `.claude/skills/ddd-spec-implementation.md` — order to read the DDD artifact set + verification checklist (binding).")
    if in_microservices:
        parts.append("- `.claude/skills/api-gateway.md` — gateway routing, CORS, service discovery for microservice deployments.")
    if has_frontend:
        parts.append(f"- `.claude/skills/{front_fw}.md` — {front_fw}-specific frontend patterns.")
    parts.append("")

    # --- Role-based agents --------------------------------------------
    if spec_uses_ddd:
        parts.append("## Agents")
        parts.append("")
        parts.append("Role-based agents (one per project; no per-BC agents):")
        parts.append("")
        parts.append("- `.claude/agents/ddd-specialist.md` — backend / domain implementation. Invoked by `/implement-ddd-bc` and `/implement-ddd-wireframe`.")
        if has_frontend:
            parts.append("- `.claude/agents/frontend-engineer.md` — frontend implementation. Invoked by `/generate-frontend`.")
        parts.append("")

    # --- Compositional pointers ----------------------------------------
    parts.append("## See Also")
    parts.append("")
    parts.append("- `PRD.md` — project composition: stack, BC inventory, file index, deployment view.")
    if spec_uses_ddd:
        parts.append("- `specs/context-map.md` — Bounded Context relationships.")
        parts.append("- `specs/bounded-contexts/<bc>/` — per-BC artifact folders.")
        if has_frontend:
            parts.append("- `specs/frontend/` — frontend perspective (framework, menu hints, ui-flow). Read these for IA/structure; name your components from `specs/bounded-contexts/<bc>/domain-terms.md`.")
    parts.append("")
    return "\n".join(parts)



def generate_cursor_rules(config: TechStackConfig) -> str:
    # Get database-specific guidelines
    db_guidelines = _get_database_specific_guidelines(config.database.value)
    
    return f"""# Cursor Rules for {config.project_name}

> **Global Rules**: These apply to the entire project. For BC-specific implementation guides, see `.cursor/rules/{{bc_name}}.mdc` files.
> Use mention feature (`@.cursorrules`) to reference these global standards.

## Domain-Driven Design (DDD) Principles

### Naming Conventions
- **Commands**: Use imperative verbs (CreateOrder, CancelOrder, ProcessPayment)
- **Events**: Use past tense (OrderCreated, PaymentProcessed, UserRegistered)
- **Aggregates**: Use domain nouns (Order, Payment, User)
- **ReadModels**: Use query intent (OrderList, OrderDetail, UserProfile)

### Bounded Context Boundaries
- **Strict Isolation**: Never directly access another BC's database or internal APIs
- **Event Communication**: All cross-BC communication must go through {config.messaging.value} events
- **Independent Deployment**: Each BC should be independently deployable
- **Own Data Model**: Each BC has its own database schema

### Aggregate Rules
- **Transaction Boundary**: Keep transactions within a single aggregate
- **Invariant Enforcement**: Always enforce all business invariants
- **Root Entity**: Access entities only through the aggregate root
- **Consistency**: Maintain consistency within aggregate boundaries only

### Command-Event Pattern
- **Command Validation**: Validate all inputs before execution
- **Event Emission**: Emit events after successful command execution
- **Idempotency**: Consider idempotency for retryable commands
- **Actor Authorization**: Check actor permissions for all commands

### CQRS Pattern
- **Read-Write Separation**: Separate read models from write models
- **Event Projections**: Update ReadModels via event projections
- **Eventual Consistency**: Accept eventual consistency for read models
- **Query Optimization**: Denormalize data for query performance

## Technology Stack Standards

### Language: {config.language.value}
- Follow {config.language.value} best practices and conventions
- Use appropriate type system features
- Maintain code readability and maintainability

### Framework: {config.framework.value}
- Follow {config.framework.value} patterns and conventions
- Use framework-provided features for dependency injection, validation, etc.
- Maintain consistency with framework idioms

### Messaging: {config.messaging.value}
- Use {config.messaging.value} for all event publishing and consumption
- Implement proper error handling and retry logic
- Use dead-letter queues for failed messages
- Maintain event schema versioning

### Database: {config.database.value}
- **BC Isolation**: Each BC has its own database schema/database
- **Transactions**: Use transactions only within aggregate boundaries
- **Indexing**: Implement proper indexing for queries (especially for ReadModels)
- **Connection Pooling**: Configure appropriate connection pool settings
- **Migration**: Use database migration tools for schema changes
- **Never share database between BCs**: Each BC must have independent database access
{db_guidelines}

### Deployment: {config.deployment.value}
- Follow {config.deployment.value} deployment patterns
- Ensure each BC is independently deployable
- Implement proper health checks and monitoring

## Code Quality Standards

### Testing
- Write GWT (Given/When/Then) tests for all commands
- Test aggregate invariants
- Test event publishing and consumption
- Test cross-BC policies (if applicable)
- Maintain high test coverage

### Error Handling
- Validate all inputs
- Handle aggregate invariant violations gracefully
- Implement retry logic for external calls
- Log errors with sufficient context
- Use appropriate error response codes

### Documentation
- Document aggregate invariants
- Document command and event schemas
- Document cross-BC event contracts
- Keep README files up to date

## File Organization

- Keep BC boundaries clear in directory structure
- Separate domain, infrastructure, and API layers
- Group related functionality together
- Follow framework conventions for project structure

## Important Reminders

1. **BC Isolation**: Never break BC boundaries
2. **Event Contracts**: Maintain backward compatibility for events
3. **Aggregate Invariants**: Always enforce invariants
4. **Actor Authorization**: Check permissions for all commands
5. **Event Sourcing**: Events are immutable facts - never modify them
"""


def _get_file_extensions_for_language(language: str, framework: str) -> str:
    """Get file extension globs based on language and framework."""
    if language == "java":
        return "*.java"
    elif language == "kotlin":
        return "*.kt"
    elif language == "typescript":
        if framework in ["nestjs", "express"]:
            return "*.ts,*.tsx"
        return "*.ts"
    elif language == "python":
        return "*.py"
    elif language == "go":
        return "*.go"
    else:
        return "*"


def _get_code_structure_guide(config: TechStackConfig, bc_name: str) -> str:
    """Generate code structure guide based on technology stack."""
    package_name = config.package_name
    bc_name_upper = bc_name.replace("_", "").title()
    
    if config.language == "java" and config.framework == "spring-boot":
        return f"""
**Backend Structure** (Spring Boot):
```
{bc_name}/
├── src/main/java/{package_name.replace('.', '/')}/{bc_name}/
│   ├── domain/
│   │   ├── aggregate/          # Aggregate root entities
│   │   │   └── {{AggregateName}}.java
│   │   ├── command/            # Command classes and handlers
│   │   │   ├── {{CommandName}}.java
│   │   │   └── {{CommandName}}Handler.java
│   │   ├── event/               # Event classes
│   │   │   └── {{EventName}}.java
│   │   ├── readmodel/           # ReadModel classes
│   │   │   └── {{ReadModelName}}.java
│   │   ├── policy/             # Policy implementations
│   │   │   └── {{PolicyName}}.java
│   │   └── valueobject/         # Value objects
│   │       └── {{ValueObjectName}}.java
│   ├── infrastructure/
│   │   ├── messaging/            # {config.messaging.value} integration
│   │   └── persistence/          # {config.database.value} integration
│   ├── api/
│   │   └── controller/          # REST endpoints
│   │       ├── {{CommandName}}Controller.java
│   │       └── {{ReadModelName}}Controller.java
│   └── application/
│       └── {bc_name_upper}Application.java
├── src/main/resources/
│   └── application.yml
└── src/test/java/{package_name.replace('.', '/')}/{bc_name}/
    └── gwt/                  # GWT test cases
```
"""
    elif config.language == "python" and config.framework == "fastapi":
        return f"""
**Backend Structure** (FastAPI):
```
{bc_name}/
├── domain/
│   ├── aggregate/          # Aggregate root entities
│   │   └── {{aggregate_name}}.py
│   ├── command/            # Command classes and handlers
│   │   ├── {{command_name}}.py
│   │   └── {{command_name}}_handler.py
│   ├── event/               # Event classes
│   │   └── {{event_name}}.py
│   ├── readmodel/           # ReadModel classes
│   │   └── {{readmodel_name}}.py
│   ├── policy/             # Policy implementations
│   │   └── {{policy_name}}.py
│   └── valueobject/         # Value objects
│       └── {{value_object_name}}.py
├── infrastructure/
│   ├── messaging/            # {config.messaging.value} integration
│   └── persistence/          # {config.database.value} integration
├── api/
│   └── controllers/          # REST endpoints
│       ├── {{command_name}}_controller.py
│       └── {{readmodel_name}}_controller.py
└── tests/
    └── gwt/                  # GWT test cases
```
"""
    elif config.language == "typescript" and config.framework == "nestjs":
        return f"""
**Backend Structure** (NestJS):
```
{bc_name}/
├── domain/
│   ├── aggregate/          # Aggregate root entities
│   │   └── {{aggregate-name}}.entity.ts
│   ├── command/            # Command classes and handlers
│   │   ├── {{command-name}}.ts
│   │   └── {{command-name}}.handler.ts
│   ├── event/               # Event classes
│   │   └── {{event-name}}.ts
│   ├── readmodel/           # ReadModel classes
│   │   └── {{readmodel-name}}.entity.ts
│   ├── policy/             # Policy implementations
│   │   └── {{policy-name}}.ts
│   └── valueobject/         # Value objects
│       └── {{value-object-name}}.ts
├── infrastructure/
│   ├── messaging/            # {config.messaging.value} integration
│   └── persistence/          # {config.database.value} integration
├── api/
│   └── controllers/          # REST endpoints
│       ├── {{command-name}}.controller.ts
│       └── {{readmodel-name}}.controller.ts
└── tests/
    └── gwt/                  # GWT test cases
```
"""
    elif config.language == "go":
        return f"""
**Backend Structure** (Go):
```
{bc_name}/
├── domain/
│   ├── aggregate/          # Aggregate root entities
│   │   └── {{aggregate_name}}.go
│   ├── command/            # Command classes and handlers
│   │   ├── {{command_name}}.go
│   │   └── {{command_name}}_handler.go
│   ├── event/               # Event classes
│   │   └── {{event_name}}.go
│   ├── readmodel/           # ReadModel classes
│   │   └── {{readmodel_name}}.go
│   ├── policy/             # Policy implementations
│   │   └── {{policy_name}}.go
│   └── valueobject/         # Value objects
│       └── {{value_object_name}}.go
├── infrastructure/
│   ├── messaging/            # {config.messaging.value} integration
│   └── persistence/          # {config.database.value} integration
├── api/
│   └── controllers/          # REST endpoints
│       ├── {{command_name}}_controller.go
│       └── {{readmodel_name}}_controller.go
└── tests/
    └── gwt/                  # GWT test cases
```
"""
    else:
        return f"""
**Backend Structure** ({config.framework.value}):
```
{bc_name}/
├── domain/
│   ├── aggregates/          # Aggregate root entities
│   ├── commands/            # Command classes and handlers
│   ├── events/               # Event classes
│   ├── readmodels/           # ReadModel classes
│   ├── policies/             # Policy implementations
│   └── valueobjects/         # Value objects
├── infrastructure/
│   ├── messaging/            # {config.messaging.value} integration
│   └── persistence/          # {config.database.value} integration
├── api/
│   └── controllers/          # REST endpoints
└── tests/
    └── gwt/                  # GWT test cases
```
"""


def generate_cursor_tech_stack_rule(config: TechStackConfig) -> str:
    """Generate Cursor rule file (.mdc format) for tech stack (not BC-specific)."""
    # Get file extensions based on language and framework
    file_extensions = _get_file_extensions_for_language(config.language.value, config.framework.value)
    # Build globs pattern for tech stack files
    if "," in file_extensions:
        # Multiple extensions (e.g., *.ts,*.tsx)
        exts = [ext.strip() for ext in file_extensions.split(",")]
        globs_pattern = ",".join([f"**/{ext}" for ext in exts])
    else:
        globs_pattern = f"**/{file_extensions}"
    
    # Get code structure guide (use placeholder BC name)
    code_structure = _get_code_structure_guide(config, "{bc_name}")
    
    # Generate tech stack specific implementation guidelines
    tech_stack_guidelines = _get_tech_stack_implementation_guidelines(config)
    
    return f"""---
alwaysApply: false
description: {config.framework.value} ({config.language.value}) implementation guidelines for DDD aggregates commands events readmodels policies
globs: {globs_pattern}
---

# {config.framework.value} ({config.language.value}) Implementation Guidelines

> **Tech Stack Rule**: This rule applies when implementing code using {config.framework.value} with {config.language.value}.
> Reference BC-specific specs in `specs/{{bc_name}}_spec.md` for detailed requirements.
> Use mention feature (`@{config.framework.value}`) to reference these tech stack standards.

## Technology Stack
- **Language**: {config.language.value}
- **Framework**: {config.framework.value}
- **Messaging**: {config.messaging.value}
- **Database**: {config.database.value}
- **Deployment**: {config.deployment.value}
- **Package Name**: {config.package_name if config.language.value in ['java', 'kotlin'] else 'N/A'}

## Code Structure
{code_structure}

## Implementation Guidelines

{tech_stack_guidelines}

## Reference Files

When implementing a specific BC:
1. **Read BC Spec**: `specs/{{bc_name}}_spec.md` - Complete BC requirements (aggregates, commands, events, properties, GWT tests)
2. **Follow Tech Stack Rules**: This file (mention: `@{config.framework.value}`) - {config.framework.value} specific implementation patterns
3. **Check DDD Principles**: `@ddd-principles` - DDD patterns (always applied)
4. **Check Event Storming Rules**: `@eventstorming-implementation` - Sticker-to-code mapping
5. **Check GWT Test Rules**: `@gwt-test-generation` - GWT test patterns
6. **Check Global Rules**: `@.cursorrules` - DDD principles and general coding standards

## Complete Implementation Checklist

### For Each Bounded Context:

#### 1. Read BC Spec First (MANDATORY)
- [ ] **Read BC Spec** (`specs/{{bc_name}}_spec.md`) - Contains ALL requirements
- [ ] **Count ALL elements** - Aggregates, Commands, Events, ReadModels, Policies, UI Wireframes
- [ ] **Verify completeness** - Ensure spec has all required information

#### 2. Database Setup (MANDATORY)
- [ ] **Configure {config.database.value} connection** - Set up connection in application config
- [ ] **Create schema** - Create tables/collections for ALL aggregates
- [ ] **Create indexes** - Index foreign keys and frequently queried columns
- [ ] **Test connection** - Verify database connection works

#### 3. Implement ALL Commands (100% Coverage)
For EACH Command in BC spec:
- [ ] **Command Handler** - Implement handler with validation
- [ ] **REST API Endpoint** - `POST /api/{{bc_name}}/{{command-name}}` (MANDATORY)
- [ ] **Input Validation** - Validate all inputs from inputSchema
- [ ] **Actor Authorization** - Check actor permissions
- [ ] **Event Emission** - Emit events after execution
- [ ] **Error Handling** - Proper error responses (400, 403, etc.)

#### 4. Implement ALL Events (100% Coverage)
For EACH Event in BC spec:
- [ ] **Event Class** - With all properties from spec
- [ ] **Event Publishing** - Publish to {config.messaging.value}
- [ ] **Version Handling** - Include version in message
- [ ] **Error Handling** - Retry logic, dead-letter queue

#### 5. Implement ALL ReadModels (100% Coverage)
For EACH ReadModel in BC spec:
- [ ] **ReadModel Class** - With all properties from spec
- [ ] **Query API Endpoint** - `GET /api/{{bc_name}}/{{readmodel-name}}` (MANDATORY)
- [ ] **Projection Handler** - Update from events
- [ ] **Pagination** - If isMultipleResult: 'list', support pagination

#### 6. Messaging Setup (MANDATORY)
- [ ] **Configure {config.messaging.value}** - Set up connection
- [ ] **Event Publishers** - Publisher service for all events
- [ ] **Event Consumers** - Consumer service for policies
- [ ] **Test messaging** - Verify events can be published/consumed

#### 7. Frontend (If included)
- [ ] **All Commands have UI** - Every Command has a UI button/form
- [ ] **All ReadModels have Pages** - Every ReadModel has a display page
- [ ] **All APIs Connected** - All UI elements call backend APIs

## Getting Started

1. **Choose a BC**: Select a Bounded Context from `specs/` directory
2. **Read BC Spec**: Review `specs/{{bc_name}}_spec.md` for complete requirements
3. **Follow Tech Stack**: Use mention `@{config.framework.value}` for {config.framework.value} implementation patterns
4. **Reference Other Rules**: Use `@ddd-principles`, `@eventstorming-implementation`, `@gwt-test-generation` as needed
5. **Follow Checklist**: Use the checklist above to ensure 100% implementation coverage

**Remember**: 
- **100% Coverage Required** - Every Command, Event, ReadModel, Policy MUST be implemented
- **No Partial Implementation** - Don't skip any element from BC spec
- **Complete API Endpoints** - Every Command and ReadModel MUST have a REST API endpoint
- This rule provides **tech stack specific** guidance. BC-specific requirements are in `specs/{{bc_name}}_spec.md`.
"""


def _get_tech_stack_implementation_guidelines(config: TechStackConfig) -> str:
    """Generate tech stack specific implementation guidelines."""
    # Get database-specific guidelines
    db_guidelines = _get_database_specific_guidelines(config.database.value)
    
    if config.language == "java" and config.framework == "spring-boot":
        return f"""### Spring Boot Specific Guidelines

#### Commands
- Use `@Service` or `@Component` for command handlers
- Use `@Valid` and `@RequestBody` for request validation
- Use `@Transactional` for aggregate operations (keep transactions within aggregate boundaries)
- Use Spring Data JPA repositories for persistence
- Use `ApplicationEventPublisher` for in-memory events or `KafkaTemplate`/`RabbitTemplate` for messaging

#### Database & Persistence
- Use Spring Data JPA with {config.database.value}
- Configure `application.properties` or `application.yml` for database connection
- Use `@Entity` for aggregate root entities
- Use `@Repository` for data access layer
- Use `@Transactional(readOnly = true)` for ReadModel queries
- Implement proper connection pooling (HikariCP is default in Spring Boot)
{db_guidelines}

#### Events
- Use `@Value` (Lombok) or immutable classes for events
- Use `@Async` for asynchronous event publishing
- Use `@KafkaListener` for Kafka or `@RabbitListener` for RabbitMQ
- Include event version in message headers

#### ReadModels
- Use Spring Data JPA repositories for queries
- Use `@Query` annotations for custom queries
- Support pagination with `Pageable`
- Use `@Entity` and JPA annotations

#### REST Controllers
- Use `@RestController` and `@RequestMapping`
- Use `@PostMapping` for commands, `@GetMapping` for queries
- Use `ResponseEntity` for response codes
- Use `@ExceptionHandler` for error handling

#### Testing
- Use `@SpringBootTest` for integration tests
- Use `@MockBean` for mocking dependencies
- Use `TestRestTemplate` or `MockMvc` for API testing"""
    
    elif config.language == "python" and config.framework == "fastapi":
        return f"""### FastAPI Specific Guidelines

#### Commands
- Use Pydantic models for command DTOs
- Use `@app.post()` decorators for command endpoints
- Use dependency injection for handlers
- Use SQLAlchemy for persistence
- Use async/await for async operations

#### Database & Persistence
- Use SQLAlchemy ORM with {config.database.value}
- Use async SQLAlchemy (`asyncpg` for PostgreSQL, `aiomysql` for MySQL)
- Configure database connection in settings/environment variables
- Use `SessionLocal` for database sessions
- Use `@db.transaction` or `async with session.begin()` for transactions
- Keep transactions within aggregate boundaries
- Use connection pooling (SQLAlchemy connection pool)
{db_guidelines}

#### Events
- Use Pydantic models for events
- Use async message brokers (aiokafka, aio-pika)
- Use background tasks for event publishing
- Include event version in message metadata

#### ReadModels
- Use SQLAlchemy models for ReadModels
- Use async database sessions
- Support pagination with limit/offset
- Use query builders for filtering

#### REST Controllers
- Use FastAPI route decorators
- Use Pydantic for request/response models
- Use `HTTPException` for error handling
- Use dependency injection for services

#### Testing
- Use `TestClient` for API testing
- Use pytest fixtures for test setup
- Mock async dependencies"""
    
    elif config.language == "typescript" and config.framework == "nestjs":
        return f"""### NestJS Specific Guidelines

#### Commands
- Use `@Injectable()` for command handlers
- Use `@Post()` decorators for command endpoints
- Use DTOs with `class-validator` for validation
- Use TypeORM or Prisma for persistence
- Use dependency injection

#### Database & Persistence
- Use TypeORM or Prisma with {config.database.value}
- Configure database connection in `TypeOrmModule` or Prisma schema
- Use `@Entity()` decorators for aggregate root entities (TypeORM)
- Use `@Transaction()` for aggregate operations
- Use repositories for data access
- Keep transactions within aggregate boundaries
- Use connection pooling (TypeORM/Prisma connection pool)
{db_guidelines}

#### Events
- Use classes or interfaces for events
- Use `@EventPattern()` for event listeners
- Use `@CqrsModule` for CQRS patterns
- Use message brokers (Kafka, RabbitMQ) via NestJS microservices

#### ReadModels
- Use TypeORM entities or Prisma models
- Use repositories for queries
- Support pagination with `PaginationDto`
- Use query builders

#### REST Controllers
- Use `@Controller()` and `@Post()`/`@Get()` decorators
- Use DTOs for request/response
- Use `HttpException` for error handling
- Use guards for authorization

#### Testing
- Use `@nestjs/testing` for unit tests
- Use `supertest` for e2e tests
- Mock providers with `Test.createTestingModule()`"""
    
    elif config.language == "go":
        return f"""### Go Specific Guidelines

#### Commands
- Use structs for command DTOs
- Use interfaces for handlers
- Use dependency injection manually or with wire
- Use GORM or sqlx for persistence
- Use context.Context for cancellation

#### Database & Persistence
- Use GORM or sqlx with {config.database.value}
- Configure database connection (DSN) in environment variables or config
- Use GORM models for aggregate root entities
- Use `db.Begin()` for transactions (keep within aggregate boundaries)
- Use connection pooling (database/sql connection pool or GORM)
- Use prepared statements for security
{db_guidelines}

#### Events
- Use structs for events
- Use message brokers (sarama for Kafka, amqp for RabbitMQ)
- Use goroutines for async operations
- Include event version in message headers

#### ReadModels
- Use GORM models or structs
- Use query builders
- Support pagination
- Use database/sql or GORM

#### REST Controllers
- Use gorilla/mux or gin/fiber routers
- Use JSON encoding/decoding
- Use http.Error for error handling
- Use middleware for authorization

#### Testing
- Use testing package for unit tests
- Use httptest for API testing
- Mock dependencies with interfaces"""
    
    else:
        return f"""### {config.framework.value} Specific Guidelines

#### Commands
- Implement command handlers following {config.framework.value} patterns
- Validate inputs using framework validation
- Use dependency injection
- Persist using {config.database.value}

#### Events
- Create immutable event classes
- Publish to {config.messaging.value}
- Handle async operations appropriately

#### ReadModels
- Implement query models
- Support pagination and filtering
- Use {config.database.value} for persistence

#### REST Controllers
- Follow {config.framework.value} routing patterns
- Use framework-specific error handling
- Implement proper HTTP status codes"""


# ============================================================================
# Claude Code Skills 생성 함수들 (Cursor rules 기반)
# ============================================================================

def generate_claude_skill_ddd_principles(config: TechStackConfig) -> str:
    """Generate DDD principles skill for Claude Code."""
    return f"""# DDD Principles and Patterns

> **Always Reference**: These DDD principles apply to all code in this project.
> Reference Event Storming model and BC specs for domain-specific requirements.
> Reference this skill file (`.claude/skills/ddd-principles.md`) when implementing any BC.

## Naming Conventions

- **Commands**: Use imperative verbs (CreateOrder, CancelOrder, ProcessPayment)
- **Events**: Use past tense (OrderCreated, PaymentProcessed, UserRegistered)
- **Aggregates**: Use domain nouns (Order, Payment, User)
- **ReadModels**: Use query intent (OrderList, OrderDetail, UserProfile)

## Bounded Context Boundaries

- **Strict Isolation**: Never directly access another BC's database or internal APIs
- **Event Communication**: All cross-BC communication must go through {config.messaging.value} events
- **Independent Deployment**: Each BC should be independently deployable
- **Own Data Model**: Each BC has its own database schema

## Aggregate Rules

- **Transaction Boundary**: Keep transactions within a single aggregate
- **Invariant Enforcement**: Always enforce all business invariants
- **Root Entity**: Access entities only through the aggregate root
- **Consistency**: Maintain consistency within aggregate boundaries only

## Command-Event Pattern

- **Command Validation**: Validate all inputs before execution
- **Event Emission**: Emit events after successful command execution
- **Idempotency**: Consider idempotency for retryable commands
- **Actor Authorization**: Check actor permissions for all commands

## CQRS Pattern

- **Read-Write Separation**: Separate read models from write models
- **Event Projections**: Update ReadModels via event projections
- **Eventual Consistency**: Accept eventual consistency for read models
- **Query Optimization**: Denormalize data for query performance

## Important Reminders

1. **BC Isolation**: Never break BC boundaries
2. **Event Contracts**: Maintain backward compatibility for events
3. **Aggregate Invariants**: Always enforce invariants
4. **Actor Authorization**: Check permissions for all commands
5. **Event Immutability**: Events are immutable facts - never modify them

## Related Skills

- **Event Storming Implementation**: `.claude/skills/eventstorming-implementation.md` - Sticker-to-code mapping patterns
- **GWT Test Generation**: `.claude/skills/gwt-test-generation.md` - GWT test patterns
- **Tech Stack Skills**: `.claude/skills/{config.framework.value}.md` - Framework-specific implementation guidelines
"""


def generate_claude_skill_eventstorming_implementation(config: TechStackConfig) -> str:
    """Generate Event Storming implementation skill for Claude Code."""
    messaging_platform = config.messaging.value
    
    return f"""# Event Storming Implementation Patterns

> **Event Storming Skill**: This skill maps Event Storming stickers to code implementation patterns.
> Reference BC specs (`specs/{{bc_name}}_spec.md`) for complete sticker details from Event Storming model.
> Reference this skill file (`.claude/skills/eventstorming-implementation.md`) when implementing Commands, Events, Aggregates, ReadModels, Policies, and UI.

## Command Implementation

### Command Handler
- **Naming**: Use imperative verbs (CreateOrder, CancelOrder, ProcessPayment)
- **Validation**: Validate all invariants before executing commands
- **Input Schema**: Use the provided `inputSchema` to define command DTOs
- **Actor Authorization**: Check actor permissions before command execution
- **Execution**: Execute through aggregate root
- **Event Emission**: Emit events after successful command execution
- **Idempotency**: Consider idempotency for commands that may be retried

### REST API Endpoints
- **HTTP Method**: POST (all commands change state)
- **Endpoint Pattern**: `POST /api/{{bc_name}}/{{command-name}}`
- **Request Mapping**: Map request body to command DTO using `inputSchema`
- **Response Codes**:
  - `201 Created` for Create commands
  - `200 OK` for Update/Process commands
  - `204 No Content` for Delete commands
  - `400 Bad Request` for validation errors
  - `403 Forbidden` for authorization failures

## Event Implementation

### Event Class
- **Naming**: Use past tense (OrderCreated, PaymentProcessed, UserRegistered)
- **Schema**: Use the provided `schema` to define event classes
- **Properties**: Map all properties from spec to event fields
- **Immutability**: Events are immutable once emitted
- **Versioning**: Use semantic versioning for event schema evolution
- **Metadata**: Include eventId, timestamp, version, etc.

### Event Publishing
- **Publisher**: Use event publisher service in `infrastructure/messaging/`
- **Platform**: Publish to {messaging_platform} after successful command execution
- **Async**: Publish asynchronously to avoid blocking command execution
- **Versioning**: Include event version in message headers/topic
- **Error Handling**: Handle publishing failures (retry, dead-letter queue)
- **Event Schema**: Use semantic versioning for event schema evolution
- **Metadata**: Include eventId, timestamp, version, etc.

### Event Consumption (Policies)
- **Subscription**: Subscribe to events via {messaging_platform} consumer
- **Cross-BC Events**: Handle events from other BCs (deserialize using other BC event schemas)
- **Idempotency**: Implement idempotency checks for duplicate events
- **Error Handling**: Handle consumption failures gracefully
- **Event Contracts**: Maintain backward compatibility for events

## Aggregate Implementation

- **Root Entity**: Use the `rootEntity` as the aggregate root class
- **Invariants**: Enforce all listed invariants in aggregate methods
- **Properties**: Map all properties with correct types (use `isKey` for primary keys, `isForeignKey` for references)
- **Enumerations**: Use provided enumerations for state management
- **Value Objects**: Implement value objects for complex domain concepts

## ReadModel Implementation

### ReadModel Projection
- **CQRS Pattern**: ReadModels are updated via event projections
- **Projection Handler**: Implement event projection handlers in `domain/readmodels/`
- **Actor Support**: Filter/authorize based on `actor` field
- **Denormalization**: Denormalize data for query performance
- **Eventual Consistency**: Accept eventual consistency (ReadModels may be slightly stale)

### Query API Endpoints
- **HTTP Method**: GET (queries don't change state)
- **Endpoint Patterns**:
  - Single result: `GET /api/{{bc_name}}/{{readmodel-name}}/{{id}}`
  - List: `GET /api/{{bc_name}}/{{readmodel-name}}?filter=value&page=1&size=10`
  - Collection: `GET /api/{{bc_name}}/{{readmodel-name}}`
- **Return Types** (based on `isMultipleResult`):
  - `list`: Return ordered arrays
  - `collection`: Return unordered collections
  - `single result`: Return single objects
- **Features**: Support filtering, pagination, and sorting for list/collection types

## Policy Implementation

### Event Listener
- **Subscription**: Subscribe to trigger events via {config.messaging.value} consumer
- **Cross-BC Events**: Handle events from other BCs (deserialize using other BC event schemas)
- **Idempotency**: Implement idempotency checks to handle duplicate events

### Command Invocation
- **Async Invocation**: Invoke target commands asynchronously via {messaging_platform}
- **Cross-BC Commands**: Handle command invocation in different BCs
- **Data Mapping**: Map event data to command input using event/command schemas
- **Retry Logic**: Implement retry logic for failed invocations

### Service Independence & Dependencies
- **No Direct Service Calls**: Policy BC does NOT call target BC service directly
- **Event Contract Dependency**: Policy BC depends ONLY on event contract (schema), not service implementation
- **Independent Deployment**: Policy BC can be deployed/updated independently
- **Target BC Availability**: Policy BC can handle events even if target BC is temporarily unavailable (events queued in messaging platform)
- **Error Handling**:
  - Schema Mismatch: Send to dead-letter queue (DLQ)
  - Version Mismatch: Support multiple versions or reject unsupported versions
  - Transient vs Permanent Failures: Retry transient failures, send permanent failures to DLQ

## UI Wireframe Implementation

### UI Components
- **Attached to Command**: Create form components for command execution
- **Attached to ReadModel**: Create display/list components for query results
- **Wireframe Description**: Follow wireframe descriptions from BC specs
- **API Integration**: Connect UI to backend APIs (Command POST, ReadModel GET)
- **State Management**: Use framework-specific state management (Pinia, Redux, etc.)
- **Error Handling**: Display user-friendly error messages
- **Loading States**: Show loading indicators during API calls

### Complete UI Implementation Checklist

**For EACH Command in BC spec:**
- [ ] **Create UI Button/Form** - Every Command MUST have a UI element
- [ ] **Create API Service** - Service method for `POST /api/{{bc_name}}/{{command-name}}`
- [ ] **Connect UI to API** - Button/form MUST call API service
- [ ] **Handle Response** - Show success/error, update UI state
- [ ] **Validate Input** - Client-side validation
- [ ] **Loading State** - Show loading during API call

**For EACH ReadModel in BC spec:**
- [ ] **Create Display/List Page** - Every ReadModel MUST have a page
- [ ] **Create API Service** - Service method for `GET /api/{{bc_name}}/{{readmodel-name}}`
- [ ] **Connect Page to API** - Page load MUST call API service
- [ ] **Display Data** - Show ReadModel data in UI
- [ ] **Pagination** - If isMultipleResult: 'list', implement pagination

**For EACH UI Wireframe in BC spec:**
- [ ] **Read Template** - HTML template from BC spec
- [ ] **Create Component** - Implement as Vue/React component
- [ ] **Match Structure** - Follow wireframe template structure
- [ ] **Connect to Command/ReadModel** - Wireframe attached to Command → form, ReadModel → display

**CRITICAL**: 100% Coverage Required - Every Command, ReadModel, and UI Wireframe MUST be implemented.

## Related Skills

- **DDD Principles**: `.claude/skills/ddd-principles.md` - DDD patterns and BC boundaries
- **GWT Test Generation**: `.claude/skills/gwt-test-generation.md` - Test patterns for implementations
- **Tech Stack Skills**: `.claude/skills/{config.framework.value}.md` - Framework-specific implementation patterns
"""


def generate_claude_skill_gwt_test_generation(config: TechStackConfig) -> str:
    """Generate GWT test generation skill for Claude Code."""
    return f"""# GWT Test Generation Guidelines

> **GWT Test Skill**: This skill provides guidelines for writing GWT (Given/When/Then) tests based on Event Storming model.
> Reference BC specs (`specs/{{bc_name}}_spec.md`) for GWT test cases from Event Storming.
> Reference this skill file (`.claude/skills/gwt-test-generation.md`) when writing tests.

## GWT (Given/When/Then) Test Pattern

### Test Structure
- **Given**: Set up preconditions (aggregate state, events)
- **When**: Execute the command or trigger the event
- **Then**: Verify outcomes (events emitted, state changes, invariants)

### Test Coverage
- **Commands**: Write GWT tests for all commands
- **Aggregates**: Test aggregate invariants
- **Events**: Test event publishing and consumption
- **Policies**: Test cross-BC policies (if applicable)
- **ReadModels**: Test query results and projections

## Test Implementation

### Framework-Specific Patterns
- **Spring Boot**: Use `@SpringBootTest`, `@MockBean`, `@Test` (JUnit)
- **FastAPI**: Use `pytest`, `TestClient`
- **NestJS**: Use `@nestjs/testing`, `Test.createTestingModule()`
- **Go**: Use `testing` package, table-driven tests

### Best Practices
- **Isolation**: Each test should be independent
- **Mocking**: Mock external dependencies (messaging, database)
- **Assertions**: Verify all expected outcomes
- **Coverage**: Maintain high test coverage

## Test Data

- **Fixtures**: Use test fixtures for common test data
- **Builders**: Use builder pattern for test object creation
- **Factories**: Use factory methods for aggregate creation
- **Cleanup**: Clean up test data after each test

## Related Skills

- **DDD Principles**: `.claude/skills/ddd-principles.md` - DDD patterns and aggregate rules
- **Event Storming Implementation**: `.claude/skills/eventstorming-implementation.md` - Command, Event, Aggregate implementation patterns
- **Tech Stack Skills**: `.claude/skills/{config.framework.value}.md` - Framework-specific testing patterns
"""


def generate_claude_skill_tech_stack(config: TechStackConfig) -> str:
    """Generate tech stack specific skill for Claude Code."""
    # Get file extensions based on language and framework
    file_extensions = _get_file_extensions_for_language(config.language.value, config.framework.value)
    # Get code structure guide (use placeholder BC name)
    code_structure = _get_code_structure_guide(config, "{bc_name}")
    # Generate tech stack specific implementation guidelines
    tech_stack_guidelines = _get_tech_stack_implementation_guidelines(config)
    # Get database-specific guidelines
    db_guidelines = _get_database_specific_guidelines(config.database.value)
    
    return f"""# {config.framework.value} ({config.language.value}) Implementation Guidelines

> **Tech Stack Skill**: This skill provides {config.framework.value} with {config.language.value} implementation guidelines.
> Reference BC-specific specs in `specs/{{bc_name}}_spec.md` for detailed requirements.
> Reference this skill file (`.claude/skills/{config.framework.value}.md`) when implementing code.

## Technology Stack
- **Language**: {config.language.value}
- **Framework**: {config.framework.value}
- **Messaging**: {config.messaging.value}
- **Database**: {config.database.value}
- **Deployment**: {config.deployment.value}
- **Package Name**: {config.package_name if config.language.value in ['java', 'kotlin'] else 'N/A'}

## Code Structure
{code_structure}

## Implementation Guidelines

{tech_stack_guidelines}

## Database & Persistence

### Database Configuration
- **BC Isolation**: Each BC has its own database schema/database
- **Transactions**: Use transactions only within aggregate boundaries
- **Indexing**: Implement proper indexing for queries (especially for ReadModels)
- **Connection Pooling**: Configure appropriate connection pool settings
- **Migration**: Use database migration tools for schema changes
- **Never share database between BCs**: Each BC must have independent database access

{db_guidelines}

## Reference Files

When implementing a specific BC:
1. **Read BC Spec**: `specs/{{bc_name}}_spec.md` - Complete BC requirements (aggregates, commands, events, properties, GWT tests)
2. **Follow Tech Stack Skills**: This file (`.claude/skills/{config.framework.value}.md`) - {config.framework.value} specific implementation patterns
3. **Check DDD Principles**: `.claude/skills/ddd-principles.md` - DDD patterns (always reference)
4. **Check Event Storming Skills**: `.claude/skills/eventstorming-implementation.md` - Sticker-to-code mapping
5. **Check GWT Test Skills**: `.claude/skills/gwt-test-generation.md` - GWT test patterns
6. **Check BC Agent**: `.claude/agents/{{bc_name}}_agent.md` - BC-specific implementation guidance

## Complete Implementation Checklist

### For Each Bounded Context:

#### 1. Read BC Spec First (MANDATORY)
- [ ] **Read BC Spec** (`specs/{{bc_name}}_spec.md`) - Contains ALL requirements
- [ ] **Count ALL elements** - Aggregates, Commands, Events, ReadModels, Policies, UI Wireframes
- [ ] **Verify completeness** - Ensure spec has all required information

#### 2. Database Setup (MANDATORY)
- [ ] **Configure {config.database.value} connection** - Set up connection in application config
- [ ] **Create schema** - Create tables/collections for ALL aggregates
- [ ] **Create indexes** - Index foreign keys and frequently queried columns
- [ ] **Test connection** - Verify database connection works

#### 3. Implement ALL Commands (100% Coverage)
For EACH Command in BC spec:
- [ ] **Command Handler** - Implement handler with validation
- [ ] **REST API Endpoint** - `POST /api/{{bc_name}}/{{command-name}}` (MANDATORY)
- [ ] **Input Validation** - Validate all inputs from inputSchema
- [ ] **Actor Authorization** - Check actor permissions
- [ ] **Event Emission** - Emit events after execution
- [ ] **Error Handling** - Proper error responses (400, 403, etc.)

#### 4. Implement ALL Events (100% Coverage)
For EACH Event in BC spec:
- [ ] **Event Class** - With all properties from spec
- [ ] **Event Publishing** - Publish to {config.messaging.value}
- [ ] **Version Handling** - Include version in message
- [ ] **Error Handling** - Retry logic, dead-letter queue

#### 5. Implement ALL ReadModels (100% Coverage)
For EACH ReadModel in BC spec:
- [ ] **ReadModel Class** - With all properties from spec
- [ ] **Query API Endpoint** - `GET /api/{{bc_name}}/{{readmodel-name}}` (MANDATORY)
- [ ] **Projection Handler** - Update from events
- [ ] **Pagination** - If isMultipleResult: 'list', support pagination

#### 6. Messaging Setup (MANDATORY)
- [ ] **Configure {config.messaging.value}** - Set up connection
- [ ] **Event Publishers** - Publisher service for all events
- [ ] **Event Consumers** - Consumer service for policies
- [ ] **Test messaging** - Verify events can be published/consumed

#### 7. Frontend (If included)
- [ ] **All Commands have UI** - Every Command has a UI button/form
- [ ] **All ReadModels have Pages** - Every ReadModel has a display page
- [ ] **All APIs Connected** - All UI elements call backend APIs

## Getting Started

1. **Choose a BC**: Select a Bounded Context from `specs/` directory
2. **Read BC Spec**: Review `specs/{{bc_name}}_spec.md` for complete requirements
3. **Follow Tech Stack Skills**: Reference `.claude/skills/{config.framework.value}.md` for {config.framework.value} implementation patterns
4. **Reference Other Skills**: Use `.claude/skills/ddd-principles.md`, `.claude/skills/eventstorming-implementation.md`, `.claude/skills/gwt-test-generation.md` as needed
5. **Follow Checklist**: Use the checklist above to ensure 100% implementation coverage

**Remember**: 
- **100% Coverage Required** - Every Command, Event, ReadModel, Policy MUST be implemented
- **No Partial Implementation** - Don't skip any element from BC spec
- **Complete API Endpoints** - Every Command and ReadModel MUST have a REST API endpoint
- This skill provides **tech stack specific** guidance. BC-specific requirements are in `specs/{{bc_name}}_spec.md`.

## Related Skills

- **DDD Principles**: `.claude/skills/ddd-principles.md` - DDD patterns and BC boundaries
- **Event Storming Implementation**: `.claude/skills/eventstorming-implementation.md` - Sticker-to-code mapping
- **GWT Test Generation**: `.claude/skills/gwt-test-generation.md` - GWT test patterns
"""


def generate_claude_skill_frontend(config: TechStackConfig) -> str:
    """Generate frontend framework skill for Claude Code - Technical implementation patterns only."""
    if not config.include_frontend or not config.frontend_framework:
        return ""
    
    frontend_guidelines = _get_frontend_implementation_guidelines(config)
    
    return f"""# {config.frontend_framework.value} Frontend Implementation Guidelines

> **Frontend Skill**: This skill provides {config.frontend_framework.value} **technical implementation patterns** (HOW to implement).
> For frontend architecture and strategy (WHAT/WHY), refer to `Frontend-PRD.md`.
> Reference BC specs (`specs/{{bc_name}}_spec.md`) for UI wireframes and attached Commands/ReadModels.
> Reference this skill file (`.claude/skills/{config.frontend_framework.value}.md`) when writing frontend code.

## Frontend Framework
- **Framework**: {config.frontend_framework.value}
- **Backend API**: {config.framework.value} REST APIs
- **State Management**: Framework-specific state management

## Code Structure

**Frontend Structure** ({config.frontend_framework.value}):
```
frontend/
├── src/
│   ├── features/              # Feature-based organization (BC-based)
│   │   └── {{bc_name}}/
│   │       ├── components/    # UI components
│   │       ├── views/         # Page views
│   │       ├── stores/        # State management
│   │       └── services/      # API services
│   ├── shared/                # Shared components
│   └── router/                # Routing configuration
└── package.json
```

## Implementation Guidelines

{frontend_guidelines}

## Reference Files

When implementing frontend code:
1. **Read Frontend PRD**: `Frontend-PRD.md` - Frontend architecture, strategy, and UI overview (read this first)
2. **Read Backend PRD**: `PRD.md` - Backend architecture and API endpoints
3. **Read BC Specs**: `specs/{{bc_name}}_spec.md` - UI wireframes and API contracts
4. **Follow Frontend Skills**: This file - {config.frontend_framework.value} technical implementation patterns
5. **Check Backend Skills**: `.claude/skills/{config.framework.value}.md` - Backend API patterns

## Complete Implementation Checklist

### For EACH Command in BC spec:
- [ ] **Create UI Button/Form** - Every Command MUST have a UI element
- [ ] **Create API Service** - Service method for `POST /api/{{bc_name}}/{{command-name}}`
- [ ] **Connect UI to API** - Button/form MUST call API service
- [ ] **Handle Response** - Show success/error, update UI state
- [ ] **Validate Input** - Client-side validation
- [ ] **Loading State** - Show loading during API call

### For EACH ReadModel in BC spec:
- [ ] **Create Display/List Page** - Every ReadModel MUST have a page
- [ ] **Create API Service** - Service method for `GET /api/{{bc_name}}/{{readmodel-name}}`
- [ ] **Connect Page to API** - Page load MUST call API service
- [ ] **Display Data** - Show ReadModel data in UI
- [ ] **Pagination** - If isMultipleResult: 'list', implement pagination

### For EACH UI Wireframe in BC spec:
- [ ] **Read Template** - HTML template from BC spec
- [ ] **Create Component** - Implement as {config.frontend_framework.value} component
- [ ] **Match Structure** - Follow wireframe template structure
- [ ] **Connect to Command/ReadModel** - Wireframe attached to Command → form, ReadModel → display

**CRITICAL**: 100% Coverage Required - Every Command, ReadModel, and UI Wireframe MUST be implemented.

## Related Skills

- **Event Storming Implementation**: `.claude/skills/eventstorming-implementation.md` - UI wireframe implementation patterns
- **Tech Stack Skills**: `.claude/skills/{config.framework.value}.md` - Backend API patterns
- **DDD Principles**: `.claude/skills/ddd-principles.md` - DDD patterns
"""


def generate_readme(bcs: list[dict], config: TechStackConfig) -> str:
    return f"""# {config.project_name}

Generated from Event Storming model.

## Bounded Contexts
{chr(10).join([f"- {bc.get('name','Unknown')}: {bc.get('description','')}" for bc in bcs])}
"""


def generate_frontend_prd(bcs: list[dict], config: TechStackConfig) -> str:
    """Generate Frontend PRD based on UI wireframes and ReadModels."""
    if not config.include_frontend or not config.frontend_framework:
        return ""
    
    frontend_fw = config.frontend_framework.value
    
    # Collect all UIs and their attached commands/readmodels
    all_uis = []
    for bc in bcs:
        uis = bc.get("uis", []) or []
        for ui in uis:
            if ui.get("id"):
                all_uis.append({
                    "bc_name": bc.get("name", "Unknown"),
                    "ui": ui
                })
    
    # Collect ReadModels for query screens
    all_readmodels = []
    for bc in bcs:
        rms = bc.get("readmodels", []) or []
        for rm in rms:
            if rm.get("id"):
                all_readmodels.append({
                    "bc_name": bc.get("name", "Unknown"),
                    "readmodel": rm
                })
    
    prd = f"""# {config.project_name} - Frontend Product Requirements Document

Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## ⚠️ Important: Read All Reference Files

**This Frontend PRD provides frontend architecture, strategy, and UI overview (WHAT/WHY). For technical implementation patterns (HOW), refer to:**
1. **Frontend Tech Stack Rules/Skills**: `.cursor/rules/{frontend_fw}.mdc` (Cursor) or `.claude/skills/{frontend_fw}.md` (Claude) - Technical implementation patterns
2. **Backend PRD** (`PRD.md`) - Backend architecture and API endpoints
3. **BC Specifications** (`specs/{{bc_name}}_spec.md`) - Complete backend requirements including UI wireframes
4. **Backend Tech Stack Rules/Skills**: `.cursor/rules/{config.framework.value}.mdc` (Cursor) or `.claude/skills/{config.framework.value}.md` (Claude) - Backend API patterns

## Technology Stack

| Component | Choice |
|-----------|--------|
| **Frontend Framework** | {frontend_fw} |
| **Backend API** | {config.framework.value} ({config.language.value}) |
| **Deployment** | {config.deployment.value} |

## UI Wireframes Overview

Total UI Screens: {len(all_uis)}
Total Query Screens (ReadModels): {len(all_readmodels)}

### UI Screens by Bounded Context
"""
    
    for bc in bcs:
        uis = bc.get("uis", []) or []
        if uis:
            bc_name = bc.get("name", "Unknown")
            bc_name_slug = bc_name.lower().replace(" ", "_")
            prd += f"\n#### {bc_name} ({len(uis)} screens)\n"
            prd += f"**Reference**: See `specs/{bc_name_slug}_spec.md` for detailed UI wireframes with templates.\n\n"
            for ui in uis:
                if ui.get("id"):
                    ui_name = ui.get("name", "Unknown")
                    attached_to = ui.get("attachedToName", "")
                    attached_type = ui.get("attachedToType", "")
                    description = ui.get("description", "")
                    prd += f"- **{ui_name}**"
                    if attached_to:
                        prd += f" (attached to {attached_type}: `{attached_to}`)"
                    prd += "\n"
                    if description:
                        prd += f"  - Description: {description}\n"
                    prd += f"  - **Wireframe Template**: See `specs/{bc_name_slug}_spec.md` for complete HTML template\n"
    
    # API Endpoint Contract per BC
    prd += "\n## API Endpoint Contract (Frontend ↔ Backend)\n\n"
    prd += "Use these endpoints when implementing API integration in the frontend.\n"
    prd += "For detailed property schemas, refer to each BC spec (`specs/{bc_name}_spec.md`).\n\n"

    for bc in bcs:
        bc_name = bc.get("name", "Unknown")
        bc_slug = bc_name.lower().replace(" ", "_")
        aggs = bc.get("aggregates", []) or []
        rms = bc.get("readmodels", []) or []
        has_endpoints = False

        for agg in aggs:
            if agg.get("commands"):
                for cmd in agg["commands"]:
                    if cmd.get("id"):
                        has_endpoints = True
                        break
            if has_endpoints:
                break
        if not has_endpoints and rms:
            for rm in rms:
                if rm.get("id"):
                    has_endpoints = True
                    break

        if not has_endpoints:
            continue

        prd += f"### {bc_name} API Endpoints\n\n"
        prd += "| Method | Endpoint | Description | Request Body | Response |\n"
        prd += "|--------|----------|-------------|--------------|----------|\n"

        for agg in aggs:
            agg_slug = (agg.get("name", "unknown") or "unknown").lower().replace(" ", "_")
            for cmd in agg.get("commands", []) or []:
                if not cmd.get("id"):
                    continue
                cmd_name = cmd.get("name", "")
                cmd_slug = cmd_name.lower().replace(" ", "_") if cmd_name else "unknown"
                cmd_display = cmd.get("displayName") or cmd_name

                # Determine HTTP method from command name pattern
                name_lower = cmd_name.lower()
                if any(kw in name_lower for kw in ["delete", "remove", "cancel"]):
                    method = "DELETE"
                    endpoint = f"/api/{bc_slug}/{agg_slug}/{{{agg_slug}Id}}"
                elif any(kw in name_lower for kw in ["update", "modify", "change", "edit"]):
                    method = "PUT"
                    endpoint = f"/api/{bc_slug}/{agg_slug}/{{{agg_slug}Id}}"
                else:
                    method = "POST"
                    endpoint = f"/api/{bc_slug}/{agg_slug}"

                # Build request body summary from command properties
                props = cmd.get("properties", []) or []
                if props:
                    prop_parts = []
                    for p in props:
                        if p.get("id"):
                            p_name = p.get("name", "")
                            p_type = p.get("type", "String")
                            req = "*" if p.get("isRequired") else ""
                            prop_parts.append(f"{p_name}: {p_type}{req}")
                    req_body = "`{ " + ", ".join(prop_parts) + " }`" if prop_parts else "-"
                else:
                    req_body = "-"

                prd += f"| `{method}` | `{endpoint}` | {cmd_display} | {req_body} | Success/Error |\n"

        for rm in rms:
            if not rm.get("id"):
                continue
            rm_name = rm.get("name", "Unknown")
            rm_slug = rm_name.lower().replace(" ", "_")
            rm_display = rm.get("displayName") or rm_name
            is_multi = rm.get("isMultipleResult", "")

            # Build response summary from readmodel properties
            props = rm.get("properties", []) or []
            if props:
                prop_parts = []
                for p in props:
                    if p.get("id"):
                        prop_parts.append(f"{p.get('name', '')}: {p.get('type', 'String')}")
                resp = "`{ " + ", ".join(prop_parts) + " }`"
                if is_multi and "true" in str(is_multi).lower():
                    resp = f"Array of {resp}"
            else:
                resp = "See spec"

            prd += f"| `GET` | `/api/{bc_slug}/{rm_slug}` | {rm_display} | - | {resp} |\n"

        prd += "\n"

    prd += f"""
### Query Screens (ReadModels)

"""
    for item in all_readmodels:
        bc_name = item["bc_name"]
        rm = item["readmodel"]
        rm_name = rm.get("name", "Unknown")
        actor = rm.get("actor", "")
        is_multiple = rm.get("isMultipleResult", "")
        prd += f"- **{rm_name}** (BC: {bc_name})"
        if actor:
            prd += f" - Actor: {actor}"
        if is_multiple:
            prd += f" - Result Type: {is_multiple}"
        prd += "\n"
    
    prd += f"""
## Frontend Implementation Strategy

### Progressive BC Integration: Main Page First, Then BC Features

**This is the recommended implementation order for frontend development:**

1. **Phase 1: Main Landing Page** (Start Here)
   - Create main landing/home page (`HomeView.vue` or `HomePage.tsx`)
   - Implement navigation structure (menu, sidebar, header)
   - Add routing foundation
   - Set up shared layout components
   - Configure state management infrastructure

2. **Phase 2: Add BC Features One by One**
   - For each Bounded Context, add its domain features incrementally:
     - Create BC feature directory: `features/{{bc_name}}/`
     - Implement BC-specific components, views, stores, services
     - Add routes for BC pages
     - Integrate BC features into main navigation
   - **Order**: Start with core BCs (e.g., User/Auth BC), then add business BCs

3. **Phase 3: Integration & Polish**
   - Connect BC features to main navigation
   - Implement cross-BC navigation flows
   - Add shared components and utilities
   - Optimize and refactor

**Implementation Order Example**:
```
1. Main Page (Home/Landing) → Navigation structure
2. BC 1 (e.g., User/Auth) → Login, Profile pages
3. BC 2 (e.g., Order) → Order list, Order detail pages
4. BC 3 (e.g., Payment) → Payment pages
5. ... (continue for each BC)
```

## UI/UX Requirements

- **Responsive Design**: Support mobile, tablet, desktop
- **Accessibility**: Follow WCAG guidelines
- **Error Messages**: Display user-friendly error messages
- **Validation**: Client-side validation before API calls
- **Loading States**: Show loading indicators
- **Success Feedback**: Confirm successful operations

## Wireframe Implementation Overview

For each UI wireframe:
1. **Read BC spec** (`specs/{{bc_name}}_spec.md`) - Contains complete wireframe templates and descriptions
2. **Identify attached Command/ReadModel** from BC spec
3. **Create view component** for the screen based on wireframe template
4. **Implement form/display** based on Command/ReadModel properties from BC spec—**use each node's and property's `displayName` for all UI text** (button labels, form field labels, page titles, column headers). The displayName was set at requirements upload (Korean or English).
   - **CRITICAL**: **Do NOT translate or paraphrase** UI text. Use the `displayName` string **verbatim** as the user-facing label.
   - If `displayName` is missing, fall back to `name` (technical identifier). Do not invent new labels.
5. **Connect to API** using service layer (see Frontend Tech Stack Rules/Skills for technical patterns)
6. **Handle responses** and update UI accordingly

**Important**: 
- Wireframe templates (HTML) are stored in BC specs, not in this Frontend-PRD. Always refer to `specs/{{bc_name}}_spec.md` for detailed wireframe templates.
- For technical implementation patterns (API integration, state management, component structure), refer to Frontend Tech Stack Rules/Skills.

## Reference Files

- **Backend PRD**: `PRD.md` - Backend architecture and API endpoints
- **BC Specs**: `specs/{{bc_name}}_spec.md` - Complete backend requirements including UI wireframes
- **Frontend Tech Stack Rules/Skills**: 
  - Cursor: `@{frontend_fw}` - {frontend_fw} technical implementation patterns (use @mention)
  - Claude: `.claude/skills/{frontend_fw}.md` - {frontend_fw} technical implementation patterns
- **Backend Tech Stack Rules/Skills**: 
  - Cursor: `@{config.framework.value}` - Backend API patterns (use @mention)
  - Claude: `.claude/skills/{config.framework.value}.md` - Backend API patterns
- **Event Storming Rules/Skills**: 
  - Cursor: `@eventstorming-implementation` - UI wireframe implementation patterns
  - Claude: `.claude/skills/eventstorming-implementation.md` - UI wireframe implementation patterns

## Getting Started

### Implementation Workflow: Main Page First, Then BC Features

**When asked to "진행해" (proceed) for frontend implementation:**

1. **Read Both PRDs Together** (Architecture & Strategy):
   - ✅ **Backend PRD** (`PRD.md`) - Understand API endpoints and data contracts
   - ✅ **Frontend PRD** (`Frontend-PRD.md`) - This file for frontend architecture, strategy, and UI overview
   - ✅ **BC Specs** (`specs/{{bc_name}}_spec.md`) - Check UI wireframes with templates and attached Commands/ReadModels

2. **Start with Main Landing Page** (Follow strategy from this PRD):
   - Create main/home page first (navigation foundation)
   - Set up routing structure
   - Implement shared layout components (header, sidebar, footer)
   - Configure state management infrastructure

3. **Add BC Features Incrementally** (Follow strategy from this PRD):
   - For each BC, read its spec (`specs/{{bc_name}}_spec.md`)
   - Create BC feature directory: `features/{{bc_name}}/`
   - Implement BC pages/components based on wireframes from BC spec
   - Add BC routes to main navigation
   - Connect to backend APIs (from Backend PRD)

4. **Follow Technical Implementation Patterns** (Refer to Frontend Tech Stack Rules/Skills):
   - **Frontend Tech Stack Rules/Skills**: For {frontend_fw} technical patterns (component structure, API integration, state management)
   - **Backend Tech Stack Rules/Skills**: For API patterns
   - **Event Storming Rules/Skills**: For UI wireframe implementation patterns

5. **For Each BC Feature**:
   - Read wireframe template from BC spec (`specs/{{bc_name}}_spec.md`)
   - Create components based on wireframe template
   - Use attached Command/ReadModel properties from BC spec
   - Connect to APIs using service layer (see Frontend Tech Stack Rules/Skills for technical details)
   - Test integration and error handling

**Remember**: 
- **This Frontend-PRD provides architecture and strategy** (WHAT/WHY) - Read this first for overall approach
- **Frontend Tech Stack Rules/Skills provide technical patterns** (HOW) - Refer to them when writing code
- **Always start with main page** - It provides the foundation for all BC features
- **Add BC features one by one** - Don't try to implement all BCs at once
- **Wireframe templates are in BC specs**, not in this Frontend-PRD
"""
    
    return prd


def generate_frontend_cursor_rule(config: TechStackConfig) -> str:
    """Generate Cursor rule file for frontend framework - Technical implementation patterns only."""
    if not config.include_frontend or not config.frontend_framework:
        return ""
    
    frontend_fw = config.frontend_framework.value
    
    # Get file extensions based on frontend framework
    if frontend_fw == "vue":
        file_extensions = "*.vue,*.ts,*.js"
    elif frontend_fw == "react":
        file_extensions = "*.tsx,*.ts,*.jsx,*.js"
    else:
        file_extensions = "*.ts,*.js,*.vue,*.tsx,*.jsx"
    
    # Get frontend-specific guidelines
    frontend_guidelines = _get_frontend_implementation_guidelines(config)
    
    return f"""---
alwaysApply: false
description: {frontend_fw} frontend implementation guidelines for UI components views stores services
globs: frontend/**/{file_extensions},src/**/{file_extensions}
---

# {frontend_fw} Frontend Implementation Guidelines

> **Frontend Tech Stack Rule**: This rule provides {frontend_fw} **technical implementation patterns** (HOW to implement).
> For frontend architecture and strategy (WHAT/WHY), refer to `Frontend-PRD.md`.
> Reference backend PRD (`PRD.md`) and BC specs (`specs/{{bc_name}}_spec.md`) for API contracts.
> Use mention feature (`@{frontend_fw}`) to reference these frontend standards.

## Technology Stack
- **Frontend Framework**: {frontend_fw}
- **Backend API**: {config.framework.value} ({config.language.value})
- **Deployment**: {config.deployment.value}

## Code Structure

**Frontend Structure** ({frontend_fw}):
```
frontend/
├── src/
│   ├── features/              # Feature-based organization (BC-based)
│   │   └── {{bc_name}}/
│   │       ├── components/    # UI components
│   │       │   └── {{ComponentName}}.vue (or .tsx)
│   │       ├── views/         # Page views
│   │       │   └── {{ViewName}}.vue (or .tsx)
│   │       ├── stores/        # State management
│   │       │   └── {{StoreName}}.ts (or .js)
│   │       └── services/      # API services
│   │           └── {{ServiceName}}.ts (or .js)
│   ├── shared/                # Shared components
│   │   ├── components/
│   │   └── utils/
│   └── router/                # Routing configuration
└── package.json
```

## Implementation Guidelines

{frontend_guidelines}

## Reference Files

When implementing frontend code:
1. **Read Frontend PRD**: `Frontend-PRD.md` - Frontend architecture, strategy, and UI overview (read this first)
2. **Read Backend PRD**: `PRD.md` - Backend architecture and API endpoints
3. **Read BC Specs**: `specs/{{bc_name}}_spec.md` - UI wireframes and API contracts
4. **Follow Frontend Rules**: This file (mention: `@{frontend_fw}`) - {frontend_fw} technical implementation patterns
5. **Check Backend Rules**: `.cursor/rules/{config.framework.value}.mdc` (mention: `@{config.framework.value}`) - Backend API patterns

## Complete Implementation Checklist

### For Each Bounded Context:

#### 1. Read BC Spec First
- [ ] **Read BC Spec** (`specs/{{bc_name}}_spec.md`) - Contains ALL UI wireframes, Commands, ReadModels
- [ ] **Identify all Commands** in the BC spec - Each Command MUST have a UI button/form
- [ ] **Identify all ReadModels** in the BC spec - Each ReadModel MUST have a display/list page
- [ ] **Check UI Wireframes** - Each wireframe template shows the UI structure

#### 2. Implement ALL Commands (100% Coverage Required)
For EACH Command in BC spec:
- [ ] **Create UI Button/Form** - Every Command MUST have a UI element (button, form, etc.)
- [ ] **Create API Service Method** - Service method to call `POST /api/{{bc_name}}/{{command-name}}`
- [ ] **Connect Button to API** - Button click/form submit MUST call the API service
- [ ] **Handle Response** - Show success/error messages, update UI state
- [ ] **Validate Input** - Client-side validation before API call
- [ ] **Loading State** - Show loading indicator during API call

**CRITICAL**: If a Command exists in BC spec, it MUST have:
1. A UI button/form element
2. An API service method
3. Connection between UI and API
4. Error handling

#### 3. Implement ALL ReadModels (100% Coverage Required)
For EACH ReadModel in BC spec:
- [ ] **Create Display/List Page** - Every ReadModel MUST have a page/component
- [ ] **Create API Service Method** - Service method to call `GET /api/{{bc_name}}/{{readmodel-name}}`
- [ ] **Connect Page to API** - Page load MUST call the API service
- [ ] **Display Data** - Show ReadModel data in UI (list, detail, etc.)
- [ ] **Handle Pagination** - If `isMultipleResult: 'list'`, implement pagination
- [ ] **Error Handling** - Handle API errors gracefully

**CRITICAL**: If a ReadModel exists in BC spec, it MUST have:
1. A display/list page/component
2. An API service method
3. Connection between page and API
4. Data display logic

#### 4. Implement ALL UI Wireframes (100% Coverage Required)
For EACH UI Wireframe in BC spec:
- [ ] **Read Wireframe Template** - HTML template from BC spec
- [ ] **Create Component/Page** - Implement wireframe as Vue/React component
- [ ] **Connect to Attached Command/ReadModel** - Wireframe attached to Command → form, ReadModel → display
- [ ] **Match Template Structure** - Follow wireframe template HTML structure
- [ ] **Add Styling** - Apply appropriate styling (framework-specific)

#### 5. Complete Integration
- [ ] **All Commands have UI** - Verify every Command has a UI button/form
- [ ] **All ReadModels have Pages** - Verify every ReadModel has a display page
- [ ] **All APIs are Connected** - Verify all UI elements call backend APIs
- [ ] **Error Handling** - All API calls have error handling
- [ ] **Loading States** - All API calls show loading indicators
- [ ] **Navigation** - Add routes for all BC pages to main navigation

## Getting Started

1. **Choose a BC**: Select a Bounded Context from `specs/` directory
2. **Read BC Spec**: Review `specs/{{bc_name}}_spec.md` for UI wireframes and API contracts
3. **Follow Frontend Tech Stack**: Use this rule for {frontend_fw} implementation patterns
4. **Check Backend PRD**: Reference `PRD.md` for API endpoint details
5. **Implement ALL Commands and ReadModels** - Use the checklist above

**Remember**: 
- **100% Coverage Required** - Every Command and ReadModel in BC spec MUST be implemented
- **No Partial Implementation** - Don't skip any Command or ReadModel
- **Complete UI-API Connection** - Every UI element MUST be connected to backend API
"""


# ============================================================================
# 세분화된 Cursor Rules 생성 함수들
# ============================================================================

def generate_ddd_principles_rule(config: TechStackConfig) -> str:
    """Generate DDD principles rule file."""
    return f"""---
alwaysApply: true
description: Domain-Driven Design (DDD) principles and patterns for Event Storming model
---

# DDD Principles and Patterns

> **Always Applied**: These DDD principles apply to all code in this project.
> Reference Event Storming model and BC specs for domain-specific requirements.
> Use mention feature (`@ddd-principles`) to reference these DDD patterns.

## Naming Conventions

- **Commands**: Use imperative verbs (CreateOrder, CancelOrder, ProcessPayment)
- **Events**: Use past tense (OrderCreated, PaymentProcessed, UserRegistered)
- **Aggregates**: Use domain nouns (Order, Payment, User)
- **ReadModels**: Use query intent (OrderList, OrderDetail, UserProfile)

## Bounded Context Boundaries

- **Strict Isolation**: Never directly access another BC's database or internal APIs
- **Event Communication**: All cross-BC communication must go through {config.messaging.value} events
- **Independent Deployment**: Each BC should be independently deployable
- **Own Data Model**: Each BC has its own database schema

## Aggregate Rules

- **Transaction Boundary**: Keep transactions within a single aggregate
- **Invariant Enforcement**: Always enforce all business invariants
- **Root Entity**: Access entities only through the aggregate root
- **Consistency**: Maintain consistency within aggregate boundaries only

## Command-Event Pattern

- **Command Validation**: Validate all inputs before execution
- **Event Emission**: Emit events after successful command execution
- **Idempotency**: Consider idempotency for retryable commands
- **Actor Authorization**: Check actor permissions for all commands

## CQRS Pattern

- **Read-Write Separation**: Separate read models from write models
- **Event Projections**: Update ReadModels via event projections
- **Eventual Consistency**: Accept eventual consistency for read models
- **Query Optimization**: Denormalize data for query performance

## Important Reminders

1. **BC Isolation**: Never break BC boundaries
2. **Event Contracts**: Maintain backward compatibility for events
3. **Aggregate Invariants**: Always enforce invariants
4. **Actor Authorization**: Check permissions for all commands
5. **Event Immutability**: Events are immutable facts - never modify them

## Related Rules

- **Event Storming Implementation**: `@eventstorming-implementation` - Sticker-to-code mapping patterns
- **GWT Test Generation**: `@gwt-test-generation` - GWT test patterns
- **Tech Stack Rules**: `@{config.framework.value}` - Framework-specific implementation guidelines
"""






def generate_gwt_test_generation_rule(config: TechStackConfig) -> str:
    """Generate GWT test generation rules."""
    return f"""---
alwaysApply: false
description: GWT (Given/When/Then) test generation guidelines based on Event Storming GWT test cases
globs: **/*Test*.java,**/*Test*.kt,**/*test*.py,**/*test*.ts,**/*test*.go,**/*spec*.ts
---

# GWT Test Generation Rules

> **GWT Test Rule**: This rule applies when writing GWT (Given/When/Then) tests based on Event Storming model.
> Reference BC specs (`specs/{{bc_name}}_spec.md`) for GWT test cases from Event Storming.
> Use mention feature (`@gwt-test-generation`) to reference these testing patterns.

## GWT (Given/When/Then) Test Pattern

### Test Structure
- **Given**: Set up preconditions (aggregate state, events)
- **When**: Execute the command or trigger the event
- **Then**: Verify outcomes (events emitted, state changes, invariants)

### Test Coverage
- **Commands**: Write GWT tests for all commands
- **Aggregates**: Test aggregate invariants
- **Events**: Test event publishing and consumption
- **Policies**: Test cross-BC policies (if applicable)
- **ReadModels**: Test query results and projections

## Test Implementation

### Framework-Specific Patterns
- **Spring Boot**: Use `@SpringBootTest`, `@MockBean`, `@Test` (JUnit)
- **FastAPI**: Use `pytest`, `TestClient`
- **NestJS**: Use `@nestjs/testing`, `Test.createTestingModule()`
- **Go**: Use `testing` package, table-driven tests

### Best Practices
- **Isolation**: Each test should be independent
- **Mocking**: Mock external dependencies (messaging, database)
- **Assertions**: Verify all expected outcomes
- **Coverage**: Maintain high test coverage

## Test Data

- **Fixtures**: Use test fixtures for common test data
- **Builders**: Use builder pattern for test object creation
- **Factories**: Use factory methods for aggregate creation
- **Cleanup**: Clean up test data after each test

## Related Rules

- **DDD Principles**: `@ddd-principles` - DDD patterns and aggregate rules
- **Event Storming Implementation**: `@eventstorming-implementation` - Command, Event, Aggregate implementation patterns
- **Tech Stack Rules**: `@{config.framework.value}` - Framework-specific testing patterns
"""


def generate_eventstorming_implementation_rule(config: TechStackConfig) -> str:
    """Generate Event Storming sticker-to-code implementation rules."""
    messaging_platform = config.messaging.value
    
    return f"""---
alwaysApply: false
description: Event Storming sticker-to-code implementation patterns (Command, Event, Aggregate, ReadModel, Policy, UI)
globs: **/*
---

# Event Storming Implementation Rules

> **Event Storming Rule**: This rule maps Event Storming stickers to code implementation patterns.
> Reference BC specs (`specs/{{bc_name}}_spec.md`) for complete sticker details from Event Storming model.
> Use mention feature (`@eventstorming-implementation`) to reference these patterns.

## Command Implementation

### Command Handler
- **Naming**: Use imperative verbs (CreateOrder, CancelOrder, ProcessPayment)
- **Validation**: Validate all invariants before executing commands
- **Input Schema**: Use the provided `inputSchema` to define command DTOs
- **Actor Authorization**: Check actor permissions before command execution
- **Execution**: Execute through aggregate root
- **Event Emission**: Emit events after successful command execution
- **Idempotency**: Consider idempotency for commands that may be retried

### REST API Endpoints
- **HTTP Method**: POST (all commands change state)
- **Endpoint Pattern**: `POST /api/{{bc_name}}/{{command-name}}`
- **Request Mapping**: Map request body to command DTO using `inputSchema`
- **Response Codes**:
  - `201 Created` for Create commands
  - `200 OK` for Update/Process commands
  - `204 No Content` for Delete commands
  - `400 Bad Request` for validation errors
  - `403 Forbidden` for authorization failures

## Event Implementation

### Event Class
- **Naming**: Use past tense (OrderCreated, PaymentProcessed, UserRegistered)
- **Schema**: Use the provided `schema` to define event classes
- **Properties**: Map all properties from spec to event fields
- **Immutability**: Events are immutable once emitted
- **Versioning**: Use semantic versioning for event schema evolution
- **Metadata**: Include eventId, timestamp, version, etc.

### Event Publishing
- **Publisher**: Use event publisher service in `infrastructure/messaging/`
- **Platform**: Publish to {messaging_platform} after successful command execution
- **Async**: Publish asynchronously to avoid blocking command execution
- **Versioning**: Include event version in message headers/topic
- **Error Handling**: Handle publishing failures (retry, dead-letter queue)
- **Event Schema**: Use semantic versioning for event schema evolution
- **Metadata**: Include eventId, timestamp, version, etc.

### Event Consumption (Policies)
- **Subscription**: Subscribe to events via {messaging_platform} consumer
- **Cross-BC Events**: Handle events from other BCs (deserialize using other BC event schemas)
- **Idempotency**: Implement idempotency checks for duplicate events
- **Error Handling**: Handle consumption failures gracefully
- **Event Contracts**: Maintain backward compatibility for events

## Aggregate Implementation

- **Root Entity**: Use the `rootEntity` as the aggregate root class
- **Invariants**: Enforce all listed invariants in aggregate methods
- **Properties**: Map all properties with correct types (use `isKey` for primary keys, `isForeignKey` for references)
- **Enumerations**: Use provided enumerations for state management
- **Value Objects**: Implement value objects for complex domain concepts

## ReadModel Implementation

### ReadModel Projection
- **CQRS Pattern**: ReadModels are updated via event projections
- **Projection Handler**: Implement event projection handlers in `domain/readmodels/`
- **Actor Support**: Filter/authorize based on `actor` field
- **Denormalization**: Denormalize data for query performance
- **Eventual Consistency**: Accept eventual consistency (ReadModels may be slightly stale)

### Query API Endpoints
- **HTTP Method**: GET (queries don't change state)
- **Endpoint Patterns**:
  - Single result: `GET /api/{{bc_name}}/{{readmodel-name}}/{{id}}`
  - List: `GET /api/{{bc_name}}/{{readmodel-name}}?filter=value&page=1&size=10`
  - Collection: `GET /api/{{bc_name}}/{{readmodel-name}}`
- **Return Types** (based on `isMultipleResult`):
  - `list`: Return ordered arrays
  - `collection`: Return unordered collections
  - `single result`: Return single objects
- **Features**: Support filtering, pagination, and sorting for list/collection types

## Policy Implementation

### Event Listener
- **Subscription**: Subscribe to trigger events via {config.messaging.value} consumer
- **Cross-BC Events**: Handle events from other BCs (deserialize using other BC event schemas)
- **Idempotency**: Implement idempotency checks to handle duplicate events

### Command Invocation
- **Async Invocation**: Invoke target commands asynchronously via {messaging_platform}
- **Cross-BC Commands**: Handle command invocation in different BCs
- **Data Mapping**: Map event data to command input using event/command schemas
- **Retry Logic**: Implement retry logic for failed invocations

## UI Wireframe Implementation

### UI Components
- **Attached to Command**: Create form components for command execution
- **Attached to ReadModel**: Create display/list components for query results
- **Wireframe Description**: Follow wireframe descriptions from BC specs
- **API Integration**: Connect UI to backend APIs (Command POST, ReadModel GET)
- **State Management**: Use framework-specific state management (Pinia, Redux, etc.)
- **Error Handling**: Display user-friendly error messages
- **Loading States**: Show loading indicators during API calls

### Complete UI Implementation Checklist

**For EACH Command in BC spec:**
- [ ] **Create UI Button/Form** - Every Command MUST have a UI element
- [ ] **Create API Service** - Service method for `POST /api/{{bc_name}}/{{command-name}}`
- [ ] **Connect UI to API** - Button/form MUST call API service
- [ ] **Handle Response** - Show success/error, update UI state
- [ ] **Validate Input** - Client-side validation
- [ ] **Loading State** - Show loading during API call

**For EACH ReadModel in BC spec:**
- [ ] **Create Display/List Page** - Every ReadModel MUST have a page
- [ ] **Create API Service** - Service method for `GET /api/{{bc_name}}/{{readmodel-name}}`
- [ ] **Connect Page to API** - Page load MUST call API service
- [ ] **Display Data** - Show ReadModel data in UI
- [ ] **Pagination** - If isMultipleResult: 'list', implement pagination

**For EACH UI Wireframe in BC spec:**
- [ ] **Read Template** - HTML template from BC spec
- [ ] **Create Component** - Implement as Vue/React component
- [ ] **Match Structure** - Follow wireframe template structure
- [ ] **Connect to Command/ReadModel** - Wireframe attached to Command → form, ReadModel → display

**CRITICAL**: 100% Coverage Required - Every Command, ReadModel, and UI Wireframe MUST be implemented.

## Related Rules

- **DDD Principles**: `@ddd-principles` - DDD patterns and BC boundaries
- **GWT Test Generation**: `@gwt-test-generation` - Test patterns for implementations
- **Tech Stack Rules**: `@{config.framework.value}` - Framework-specific implementation patterns
"""


def _get_database_specific_guidelines(database: str) -> str:
    """Generate database-specific implementation guidelines."""
    if database == "postgresql":
        return """
- **PostgreSQL Specific**:
  - Use `SERIAL` or `BIGSERIAL` for auto-increment IDs, or `UUID` for distributed systems
  - Use `JSONB` for flexible schema (if needed for event storage or denormalized data)
  - Use `VARCHAR` with appropriate length limits
  - Use `TIMESTAMP WITH TIME ZONE` for timestamps
  - Create indexes on foreign keys and frequently queried columns
  - Use `EXPLAIN ANALYZE` to optimize queries
  - Consider using `PARTITION BY` for large tables (if applicable)
  - Use connection pooling (HikariCP for Java, asyncpg for Python, etc.)"""
    
    elif database == "mysql":
        return """
- **MySQL Specific**:
  - Use `InnoDB` storage engine (supports transactions and foreign keys)
  - Use `AUTO_INCREMENT` for primary keys, or `CHAR(36)` for UUIDs
  - Use `VARCHAR` with appropriate length limits
  - Use `DATETIME` or `TIMESTAMP` for timestamps
  - Create indexes on foreign keys and frequently queried columns
  - Use `utf8mb4` character set for full Unicode support
  - Use connection pooling (HikariCP for Java, SQLAlchemy for Python, etc.)
  - Consider using `EXPLAIN` to optimize queries"""
    
    elif database == "mongodb":
        return """
- **MongoDB Specific**:
  - Use `ObjectId` for document IDs (or UUIDs if needed)
  - Design document structure to match query patterns (denormalize for reads)
  - Create indexes on frequently queried fields
  - Use compound indexes for multi-field queries
  - Use `$lookup` sparingly (prefer denormalization for performance)
  - Use transactions for multi-document operations (MongoDB 4.0+)
  - Use connection pooling (MongoDB driver connection pool)
  - Consider using `explain()` to optimize queries"""
    
    elif database == "h2":
        return """
- **H2 Specific**:
  - Use `BIGINT AUTO_INCREMENT` for primary keys, or `CHAR(36)` for UUIDs
  - Use `VARCHAR` with appropriate length limits
  - Use `TIMESTAMP` for timestamps
  - Create indexes on foreign keys and frequently queried columns
  - Use in-memory mode (`jdbc:h2:mem:`) for testing
  - Use file-based mode (`jdbc:h2:file:`) for development
  - H2 is typically used for development/testing, not production"""
    
    else:
        return f"""
- **{database} Specific**:
  - Follow {database} best practices for your use case
  - Implement proper indexing strategy
  - Use appropriate data types for your domain
  - Configure connection pooling appropriately"""


def _get_frontend_implementation_guidelines(config: TechStackConfig) -> str:
    """Generate frontend framework specific implementation guidelines."""
    frontend_fw = config.frontend_framework.value if config.frontend_framework else ""
    
    if frontend_fw == "vue":
        return """### Vue.js 3 Specific Guidelines

#### Components
- Use `<script setup>` syntax for Composition API
- Use `defineProps` and `defineEmits` for component interface
- Use `ref` and `reactive` for reactive state
- Use `computed` for derived state
- Use `watch` for side effects

#### Views/Pages
- Use Vue Router for navigation
- Use route params and query for data fetching
- Implement loading states with `v-if` and loading indicators
- Handle errors with try-catch and error components

#### State Management (Pinia)
- Create stores in `stores/` directory
- Use `defineStore` for store definition
- Separate stores by feature/BC
- Use `getters` for computed state
- Use `actions` for async operations (API calls)

#### API Services
- Create service files in `services/` directory
- Use `fetch` or `axios` for HTTP requests
- Handle errors and return typed responses
- Use async/await for async operations

#### Forms
- Use `v-model` for two-way binding
- Validate with `vuelidate` or custom validators
- Show validation errors inline
- Disable submit button during submission

#### Testing
- Use Vitest for unit tests
- Use Vue Test Utils for component testing
- Mock API calls in tests"""
    
    elif frontend_fw == "react":
        return """### React Specific Guidelines

#### Components
- Use functional components with hooks
- Use `useState` for local state
- Use `useEffect` for side effects
- Use `useMemo` and `useCallback` for optimization
- Use TypeScript for type safety

#### Views/Pages
- Use React Router for navigation
- Use route params and search params
- Implement loading states with conditional rendering
- Handle errors with Error Boundaries

#### State Management
- Use Context API for global state (small apps)
- Use Redux Toolkit or Zustand for complex state
- Separate stores by feature/BC
- Use selectors for computed state
- Use thunks/sagas for async operations

#### API Services
- Create service files in `services/` directory
- Use `fetch` or `axios` for HTTP requests
- Use custom hooks (e.g., `useApi`) for data fetching
- Handle errors and return typed responses

#### Forms
- Use controlled components with `value` and `onChange`
- Use `react-hook-form` for form management
- Validate with `zod` or `yup`
- Show validation errors inline

#### Testing
- Use Jest and React Testing Library
- Mock API calls with MSW (Mock Service Worker)
- Test user interactions, not implementation"""
    
    else:
        return f"""### {frontend_fw} Specific Guidelines

#### Components
- Follow {frontend_fw} component patterns
- Use framework-specific state management
- Implement proper lifecycle hooks

#### API Integration
- Create service layer for API calls
- Handle errors and loading states
- Use framework-specific HTTP client

#### Forms
- Use framework-specific form handling
- Validate inputs
- Show validation errors

#### Testing
- Use framework-specific testing tools
- Test components and integration"""


def generate_dockerfile(config: TechStackConfig) -> str:
    if config.framework == Framework.FASTAPI:
        return """FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
"""
    if config.framework in [Framework.NESTJS, Framework.EXPRESS]:
        return """FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
CMD ["npm","run","start"]
"""
    return """# Dockerfile template (customize per service)
"""


def generate_docker_compose(config: TechStackConfig) -> str:
    # Database service
    if config.database == Database.POSTGRESQL:
        db_service = """  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: ${DB_NAME:-app}
      POSTGRES_USER: ${DB_USER:-postgres}
      POSTGRES_PASSWORD: ${DB_PASSWORD:-postgres}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5
"""
    elif config.database == Database.MONGODB:
        db_service = """  mongodb:
    image: mongo:6
    ports:
      - "27017:27017"
    volumes:
      - mongodb_data:/data/db
    healthcheck:
      test: ["CMD", "mongosh", "--eval", "db.adminCommand('ping')"]
      interval: 10s
      timeout: 5s
      retries: 5
"""
    elif config.database == Database.MYSQL:
        db_service = """  mysql:
    image: mysql:8
    environment:
      MYSQL_DATABASE: ${DB_NAME:-app}
      MYSQL_USER: ${DB_USER:-mysql}
      MYSQL_PASSWORD: ${DB_PASSWORD:-mysql}
      MYSQL_ROOT_PASSWORD: ${DB_ROOT_PASSWORD:-root}
    ports:
      - "3306:3306"
    volumes:
      - mysql_data:/var/lib/mysql
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      timeout: 5s
      retries: 5
"""
    else:
        db_service = ""

    # Messaging service
    if config.messaging.value == "kafka":
        messaging_service = """  kafka:
    image: confluentinc/cp-kafka:latest
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_LISTENERS: PLAINTEXT://:9092,CONTROLLER://:9093
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka:9093
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_AUTO_CREATE_TOPICS_ENABLE: "true"
      CLUSTER_ID: MkU3OEVBNTcwNTJENDM2Qk
    ports:
      - "9092:9092"
    healthcheck:
      test: ["CMD-SHELL", "kafka-broker-api-versions --bootstrap-server localhost:9092"]
      interval: 10s
      timeout: 5s
      retries: 5
"""
    elif config.messaging.value == "rabbitmq":
        messaging_service = """  rabbitmq:
    image: rabbitmq:3-management
    environment:
      RABBITMQ_DEFAULT_USER: ${RABBITMQ_USER:-guest}
      RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD:-guest}
    ports:
      - "5672:5672"   # AMQP port
      - "15672:15672" # Management UI
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
"""
    elif config.messaging.value == "redis-streams":
        messaging_service = """  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
"""
    else:
        messaging_service = ""

    volumes = ""
    if config.database in [Database.POSTGRESQL, Database.MONGODB, Database.MYSQL]:
        volumes += "\nvolumes:"
        if config.database == Database.POSTGRESQL:
            volumes += "\n  postgres_data:"
        elif config.database == Database.MONGODB:
            volumes += "\n  mongodb_data:"
        elif config.database == Database.MYSQL:
            volumes += "\n  mysql_data:"
    if config.messaging.value == "rabbitmq":
        if not volumes:
            volumes = "\nvolumes:"
        volumes += "\n  rabbitmq_data:"
    if config.messaging.value == "redis-streams":
        if not volumes:
            volumes = "\nvolumes:"
        volumes += "\n  redis_data:"

    # API Gateway for microservices deployment
    gateway_service = ""
    if config.deployment == DeploymentStyle.MICROSERVICES:
        gateway_service = """  api-gateway:
    image: nginx:alpine
    ports:
      - "8080:80"
    volumes:
      - ./gateway/nginx.conf:/etc/nginx/nginx.conf:ro
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:80/health"]
      interval: 10s
      timeout: 5s
      retries: 5
"""

    # Modern Docker Compose V2 format (no version field needed)
    return f"""services:
{db_service}{messaging_service}{gateway_service}{volumes}
"""


def generate_api_gateway_rule(config: TechStackConfig, bcs: list[dict]) -> str:
    """Generate API Gateway Cursor rule for microservices deployment."""
    bc_routes = ""
    for bc in bcs:
        bc_name = bc.get("name", "Unknown")
        bc_slug = bc_name.lower().replace(" ", "_")
        bc_routes += f"    - `/api/{bc_slug}/**` → `{bc_slug}-service`\n"

    # Framework-specific gateway recommendation
    if config.framework in [Framework.SPRING_BOOT, Framework.SPRING_WEBFLUX]:
        gateway_rec = "Spring Cloud Gateway (recommended for Spring ecosystem)"
        gateway_dep = "org.springframework.cloud:spring-cloud-starter-gateway"
        gateway_alt = "Alternatively: nginx, Kong, or Traefik"
    elif config.framework in [Framework.NESTJS, Framework.EXPRESS]:
        gateway_rec = "nginx or Kong (recommended for Node.js ecosystem)"
        gateway_dep = "npm: http-proxy-middleware (for custom Node.js gateway)"
        gateway_alt = "Alternatively: Traefik, or custom NestJS gateway module"
    elif config.framework == Framework.FASTAPI:
        gateway_rec = "nginx or Traefik (recommended for Python ecosystem)"
        gateway_dep = "pip: fastapi-gateway (for custom Python gateway)"
        gateway_alt = "Alternatively: Kong, or custom FastAPI reverse proxy"
    else:  # Go frameworks
        gateway_rec = "nginx or Traefik (recommended for Go ecosystem)"
        gateway_dep = "Go: net/http/httputil ReverseProxy (for custom gateway)"
        gateway_alt = "Alternatively: Kong, or custom Go reverse proxy"

    return f"""---
alwaysApply: true
description: API Gateway routing, CORS, and service discovery for microservices architecture
---

# API Gateway Configuration

> **Always Applied**: API Gateway is required for microservices deployment.
> All client requests (frontend, external) must go through the gateway — never call BC services directly.

## Gateway Technology

- **Recommended**: {gateway_rec}
- **Dependency**: `{gateway_dep}`
- {gateway_alt}

## Service Routing

All BC services are routed through the API gateway:

{bc_routes}

### Routing Rules

- Each Bounded Context runs as an independent service with its own port
- The gateway routes requests based on the URL path prefix (`/api/{{bc_name}}/`)
- **No direct service-to-service HTTP calls** — use {config.messaging.value} for inter-BC communication

## CORS Configuration

```
Allowed Origins: ${{CORS_ALLOWED_ORIGINS:-http://localhost:3000}}
Allowed Methods: GET, POST, PUT, DELETE, PATCH, OPTIONS
Allowed Headers: Content-Type, Authorization, X-Request-ID
Max Age: 3600
```

- Configure CORS at the gateway level only — individual BC services should NOT set CORS headers
- In development, allow `localhost:3000` (frontend dev server)
- In production, restrict to the actual frontend domain

## Rate Limiting

- **Global**: 1000 requests/minute per IP
- **Per-endpoint**: Configure based on business requirements
- Return `429 Too Many Requests` with `Retry-After` header

## Health Check Aggregation

The gateway should expose a unified health endpoint:

- **`GET /health`** — aggregated health of all BC services
- Check each downstream service health endpoint (`/actuator/health`, `/health`, etc.)
- Return `200 OK` only if all critical services are healthy
- Return `503 Service Unavailable` with details of unhealthy services

## Service Discovery

- **Docker Compose (dev)**: Use Docker DNS — service names resolve to container IPs (e.g., `http://{{bc_slug}}-service:8080`)
- **Kubernetes (prod)**: Use Kubernetes DNS — `{{bc_slug}}-service.{{namespace}}.svc.cluster.local`
- **Consul/Eureka**: Register each BC service at startup, gateway queries registry for routing

## Gateway Implementation Checklist

- [ ] Set up API Gateway service (nginx, Spring Cloud Gateway, etc.)
- [ ] Configure routing for all BC services
- [ ] Enable CORS for frontend origin
- [ ] Add health check aggregation endpoint
- [ ] Configure rate limiting
- [ ] Add request logging and tracing (X-Request-ID propagation)
- [ ] Set up SSL/TLS termination (production)
- [ ] Configure timeout and circuit breaker for downstream services

## nginx.conf Template (for nginx gateway)

```nginx
upstream {{bc_slug}}-service {{
    server {{bc_slug}}-service:8080;
}}

server {{
    listen 80;

    # Health check
    location /health {{
        access_log off;
        return 200 'OK';
    }}

    # BC routing
{chr(10).join(f'    location /api/{bc.get("name", "").lower().replace(" ", "_")}/ {{{chr(10)}        proxy_pass http://{bc.get("name", "").lower().replace(" ", "_")}-service;{chr(10)}    }}' for bc in bcs)}

    # CORS headers
    add_header Access-Control-Allow-Origin ${{CORS_ORIGIN}} always;
    add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, PATCH, OPTIONS" always;
    add_header Access-Control-Allow-Headers "Content-Type, Authorization, X-Request-ID" always;
}}
```

## Related Rules

- **DDD Principles**: `@ddd-principles` — BC isolation and boundaries
- **Event Storming Implementation**: `@eventstorming-implementation` — Cross-BC communication via events
- **Tech Stack Rules**: `@{config.framework.value}` — Framework-specific implementation guidelines
"""


def generate_claude_skill_api_gateway(config: TechStackConfig, bcs: list[dict]) -> str:
    """Generate API Gateway Claude skill for microservices deployment."""
    bc_routes = ""
    for bc in bcs:
        bc_name = bc.get("name", "Unknown")
        bc_slug = bc_name.lower().replace(" ", "_")
        bc_routes += f"    - `/api/{bc_slug}/**` → `{bc_slug}-service`\n"

    # Framework-specific gateway recommendation
    if config.framework in [Framework.SPRING_BOOT, Framework.SPRING_WEBFLUX]:
        gateway_rec = "Spring Cloud Gateway (recommended for Spring ecosystem)"
        gateway_dep = "org.springframework.cloud:spring-cloud-starter-gateway"
        gateway_alt = "Alternatively: nginx, Kong, or Traefik"
    elif config.framework in [Framework.NESTJS, Framework.EXPRESS]:
        gateway_rec = "nginx or Kong (recommended for Node.js ecosystem)"
        gateway_dep = "npm: http-proxy-middleware (for custom Node.js gateway)"
        gateway_alt = "Alternatively: Traefik, or custom NestJS gateway module"
    elif config.framework == Framework.FASTAPI:
        gateway_rec = "nginx or Traefik (recommended for Python ecosystem)"
        gateway_dep = "pip: fastapi-gateway (for custom Python gateway)"
        gateway_alt = "Alternatively: Kong, or custom FastAPI reverse proxy"
    else:  # Go frameworks
        gateway_rec = "nginx or Traefik (recommended for Go ecosystem)"
        gateway_dep = "Go: net/http/httputil ReverseProxy (for custom gateway)"
        gateway_alt = "Alternatively: Kong, or custom Go reverse proxy"

    return f"""# API Gateway Configuration

> **Always Reference**: API Gateway is required for microservices deployment.
> All client requests (frontend, external) must go through the gateway — never call BC services directly.
> Reference this skill file (`.claude/skills/api-gateway.md`) when implementing the gateway or service routing.

## Gateway Technology

- **Recommended**: {gateway_rec}
- **Dependency**: `{gateway_dep}`
- {gateway_alt}

## Service Routing

All BC services are routed through the API gateway:

{bc_routes}

### Routing Rules

- Each Bounded Context runs as an independent service with its own port
- The gateway routes requests based on the URL path prefix (`/api/{{bc_name}}/`)
- **No direct service-to-service HTTP calls** — use {config.messaging.value} for inter-BC communication

## CORS Configuration

```
Allowed Origins: ${{CORS_ALLOWED_ORIGINS:-http://localhost:3000}}
Allowed Methods: GET, POST, PUT, DELETE, PATCH, OPTIONS
Allowed Headers: Content-Type, Authorization, X-Request-ID
Max Age: 3600
```

- Configure CORS at the gateway level only — individual BC services should NOT set CORS headers
- In development, allow `localhost:3000` (frontend dev server)
- In production, restrict to the actual frontend domain

## Rate Limiting

- **Global**: 1000 requests/minute per IP
- **Per-endpoint**: Configure based on business requirements
- Return `429 Too Many Requests` with `Retry-After` header

## Health Check Aggregation

The gateway should expose a unified health endpoint:

- **`GET /health`** — aggregated health of all BC services
- Check each downstream service health endpoint (`/actuator/health`, `/health`, etc.)
- Return `200 OK` only if all critical services are healthy
- Return `503 Service Unavailable` with details of unhealthy services

## Service Discovery

- **Docker Compose (dev)**: Use Docker DNS — service names resolve to container IPs (e.g., `http://{{bc_slug}}-service:8080`)
- **Kubernetes (prod)**: Use Kubernetes DNS — `{{bc_slug}}-service.{{namespace}}.svc.cluster.local`
- **Consul/Eureka**: Register each BC service at startup, gateway queries registry for routing

## Gateway Implementation Checklist

- [ ] Set up API Gateway service (nginx, Spring Cloud Gateway, etc.)
- [ ] Configure routing for all BC services
- [ ] Enable CORS for frontend origin
- [ ] Add health check aggregation endpoint
- [ ] Configure rate limiting
- [ ] Add request logging and tracing (X-Request-ID propagation)
- [ ] Set up SSL/TLS termination (production)
- [ ] Configure timeout and circuit breaker for downstream services

## nginx.conf Template (for nginx gateway)

```nginx
upstream {{bc_slug}}-service {{
    server {{bc_slug}}-service:8080;
}}

server {{
    listen 80;

    # Health check
    location /health {{
        access_log off;
        return 200 'OK';
    }}

    # BC routing
{chr(10).join(f'    location /api/{bc.get("name", "").lower().replace(" ", "_")}/ {{{chr(10)}        proxy_pass http://{bc.get("name", "").lower().replace(" ", "_")}-service;{chr(10)}    }}' for bc in bcs)}

    # CORS headers
    add_header Access-Control-Allow-Origin ${{CORS_ORIGIN}} always;
    add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, PATCH, OPTIONS" always;
    add_header Access-Control-Allow-Headers "Content-Type, Authorization, X-Request-ID" always;
}}
```

## Related Skills

- **DDD Principles**: `.claude/skills/ddd-principles.md` — BC isolation and boundaries
- **Event Storming Implementation**: `.claude/skills/eventstorming-implementation.md` — Cross-BC communication via events
- **Tech Stack Skills**: `.claude/skills/{config.framework.value}.md` — Framework-specific implementation guidelines
"""


# ============================================================
# Feature 022 — DDD-for-SDD artifact-aware skills + commands
# ============================================================


def generate_claude_skill_ddd_spec_implementation(config: TechStackConfig) -> str:
    """Skill for translating the DDD-for-SDD artifact set into code.

    Generated when ``ai_assistant=claude`` AND ``spec_format=ddd``. Maps
    each artifact (``domain-terms.md`` / ``bc-<slug>.md`` / ``aggregate-<slug>.md`` /
    ``acl-<system>.md`` / ``requirements.md`` / ``context-map.md``) onto a
    concrete implementation step so Claude Code can read the spec folder
    and produce backend + frontend code that matches the original design.
    """
    framework = config.framework.value
    language = config.language.value
    frontend = config.frontend_framework.value if config.frontend_framework else None
    has_frontend = config.include_frontend and frontend is not None
    frontend_block = (
        f"- **`requirements.md` (per BC)** → user stories grouped by aggregate;\n"
        f"  acceptance criteria are in EARS form (``WHEN trigger IF state THEN system SHALL obligation``).\n"
        f"  Each story may list one or more **Wireframes** with two signals:\n"
        f"  1. a textual element tree (semantic / hierarchical, ideal for code structure),\n"
        f"  2. an embedded `<img src='./requirements.assets/<story>-<ui>.svg'>` (the visual reference).\n"
        f"  When you generate a `{frontend or 'frontend'}` component, **use both** —\n"
        f"  the element tree for component decomposition + accessibility names, the SVG to\n"
        f"  verify the result visually. Pull numeric values you need (sizes, padding, colors)\n"
        f"  from the SVG itself (`<rect>` / `<text>` attributes). The scene-graph JSON sidecar\n"
        f"  is no longer emitted (2026-05-12 amendment).\n"
        if has_frontend
        else
        f"- **`requirements.md` (per BC)** → user stories grouped by aggregate;\n"
        f"  acceptance criteria are in EARS form. Wireframe sections (element tree + SVG) "
        f"document the UI even when a frontend is not in this PR's scope.\n"
    )

    return f"""---
name: ddd-spec-implementation
description: |
  Translate the DDD-for-SDD artifact set (feature 022: domain-terms, bc-canvas,
  aggregate-spec, acl-spec, requirements + wireframes, context-map) into running
  {framework}/{language}{'+' + frontend if has_frontend else ''} code. Trigger
  whenever you encounter `specs/bounded-contexts/<bc-slug>/` or
  `specs/context-map.md` and need to write source files that match the design.
---

# DDD-for-SDD Implementation Skill

> Reference this skill (`.claude/skills/ddd-spec-implementation.md`) whenever you
> implement a bounded context whose specs live under `specs/bounded-contexts/<bc-slug>/`.

This skill closes the gap between the **graph-projected** DDD artifact set
(`specs/bounded-contexts/...`, generated by feature 022 of the Event Storming
Navigator) and your code. Treat each artifact as an authoritative semantic
contract — do **not** invent domain concepts that aren't in the spec, do **not**
rename them, and do **not** silently merge aggregates.

## Artifact map (read in this order)

1. **`specs/context-map.md`** (system level) → Strategic relationships between
   Bounded Contexts. Inferred patterns carry `(inferred — confirm)`; consult the
   user before treating them as authoritative.
2. **`specs/bounded-contexts/<bc-slug>/bc-<slug>.md`** → BC Canvas. Use **Purpose**
   for module-level docstrings/READMEs, **Strategic Classification** for
   architectural decisions (core vs supporting determines testing depth), and
   **Inbound/Outbound Communication** for inter-service contracts.
3. **`specs/bounded-contexts/<bc-slug>/domain-terms.md`** → Ubiquitous Language.
   Every Aggregate / Command / Event / ReadModel name **must** appear verbatim
   in code (no `Confirm` → `Approve` synonym drift). "Aliases to AVOID" entries
   are forbidden names; never use them.
4. **`specs/bounded-contexts/<bc-slug>/aggregates/aggregate-<slug>.md`** →
   Aggregate Design Spec. The nine sections map directly onto code:
   - **Aggregate Root** → primary class (e.g. `class Order` for `Order`)
   - **Member Entities & Value Objects** → owned types in the same module
   - **Properties** → fields with the listed `Type` + `Mutability` (immutable
     after creation → no setter; mutable through commands only → state changes
     only via method invocation, not field assignment)
   - **Enforced Invariants** → guard clauses inside command methods + property
     setters. Each numbered EARS line translates as follows:
     - `THE <Agg> SHALL <C>` → unconditional invariant; assert in constructor +
       every state change.
     - `WHEN <trigger> IF <state> THEN system SHALL <obligation>` → command
       method `<trigger>` precondition `<state>` + postcondition `<obligation>`.
       Use the `.claude/skills/gwt-test-generation.md` skill for the matching tests.
   - **Corrective Policies** → eventual-consistency reactions; implement as
     event handlers in the policy's BC, not inline in the aggregate.
   - **Commands** table → public methods on the aggregate (Preconditions →
     guard clauses; Postconditions → state mutations; Events emitted → domain
     events appended in the same transaction).
   - **Domain Events Emitted** → event classes (immutable records).
   - **Repository Interface** → exact contract; the stub is intentionally
     minimal — extend only with methods needed by Commands.
   - **Open Decisions** → blockers. Stop and ask the user before guessing.
5. **`specs/bounded-contexts/<bc-slug>/acl-<system>.md`** (when present) →
   external-system integrations. Implement the Translation Maps verbatim;
   forbidden concepts must NOT appear in the core domain types.
6. **`specs/bounded-contexts/<bc-slug>/requirements.md`** → User stories with
   EARS acceptance criteria + wireframes.

{frontend_block}
## Implementation order

For each Bounded Context, generate code in this order so dependencies resolve:

1. Identity Value Objects (e.g. `OrderId`) — from the Repository Interface stub.
2. Member Entities & Value Objects + property mutability rules.
3. Domain Events (immutable records named verbatim from "Domain Events Emitted").
4. Aggregate Root with Commands as methods + invariant guards.
5. Repository Interface + an in-memory implementation for tests.
6. Corrective Policies as event handlers — they live in the BC that owns them
   (look at the `bc-<slug>.md` "Inbound Communication" table to confirm
   ownership).
7. Application services / use-cases that orchestrate Command dispatch.
8. {('Frontend components mirroring the element-tree, styled from the SVG (read sizes / colors / fonts from `<rect>` / `<text>` attributes)' if has_frontend else 'API controllers / handlers, one per Command and one per ReadModel query')}.
9. Tests — see `.claude/skills/gwt-test-generation.md`. Generate one test per
   EARS acceptance criterion AND one per Enforced Invariant.

## Verification checklist (run before reporting done)

- [ ] Every name in `domain-terms.md` appears verbatim in code; no banned aliases.
- [ ] Every numbered EARS line in each `aggregate-<slug>.md` has a matching test.
- [ ] Each Command on the aggregate emits exactly the events listed under "Events emitted".
- [ ] No cross-BC type imports — communication is via events (see `context-map.md`).
- [ ] {('Wireframe components render at the documented frame size (read from the SVG root `viewBox` / `width`/`height`)' if has_frontend else 'Acceptance criteria from requirements.md are covered by integration tests')}.

## Related skills + commands

- **DDD Principles**: `.claude/skills/ddd-principles.md`
- **Event Storming Implementation**: `.claude/skills/eventstorming-implementation.md`
- **GWT Test Generation**: `.claude/skills/gwt-test-generation.md`
- **Tech Stack**: `.claude/skills/{framework}.md`
{('- **Frontend**: `.claude/skills/' + frontend + '.md`' + chr(10)) if has_frontend else ''}- **Slash commands**: `/implement-ddd-bc <bc-slug>` and `/implement-ddd-wireframe <bc-slug> <story-id> <ui-slug>`
"""


def generate_claude_command_implement_ddd_bc(config: TechStackConfig) -> str:
    """Slash command: read one BC's full spec folder and implement it."""
    framework = config.framework.value
    return f"""---
description: Implement an entire Bounded Context from its DDD-for-SDD artifact folder.
argument-hint: <bc-slug>
---

You are implementing the Bounded Context whose spec folder is
`specs/bounded-contexts/$1/` using the **{framework}** framework.

## Plan

1. Load the spec folder. **You must read every file before writing code**:
   - `specs/bounded-contexts/$1/bc-$1.md` (Canvas)
   - `specs/bounded-contexts/$1/domain-terms.md` (Ubiquitous Language)
   - All files under `specs/bounded-contexts/$1/aggregates/*.md`
   - All files under `specs/bounded-contexts/$1/acl-*.md` if present
   - `specs/bounded-contexts/$1/requirements.md`
   - `specs/context-map.md` — only the rows where `$1` is upstream or downstream
2. Skim `.claude/skills/ddd-spec-implementation.md` for the implementation order
   and verification checklist. Treat both as binding.
3. For each aggregate spec, in alphabetical order:
   1. Generate the Aggregate Root, its identity VO, member entities/VOs,
      and Domain Events. Use the exact names from `domain-terms.md`.
   2. Implement Commands as methods on the aggregate. Translate EARS lines
      into precondition guards (IF clauses), state mutations (THEN), and
      emitted events.
   3. Generate the Repository interface + an in-memory implementation.
   4. Generate GWT-style tests for every numbered EARS line (use the
      `.claude/skills/gwt-test-generation.md` patterns).
4. If `acl-<system>.md` files exist, implement the translation maps as
   adapter modules — no external type may leak into the core types.
5. From `requirements.md`, generate one application service / use case per
   user story. Wire them to the aggregates via the repository interface.
6. Run the verification checklist from
   `.claude/skills/ddd-spec-implementation.md`. Report any item you cannot
   tick off.

## Output expectations

- Produce one Pull Request worth of changes (commits grouped per aggregate).
- Do NOT touch other Bounded Contexts unless their `bc-<slug>.md` explicitly
  flags an inbound/outbound dependency you must satisfy.
- Keep imports inside the BC's module; cross-BC use only happens via the
  events listed in `context-map.md`.
- If any artifact has `(not modeled — confirm)`, `(inferred — confirm)`, or
  an item in "Open Decisions", **STOP and ask the user** before guessing.

## Done criteria

- All tests pass.
- Every name in `domain-terms.md` shows up as an identifier in the produced code.
- Every numbered EARS line in `aggregate-*.md` has a matching test that fails
  if the invariant is broken.
"""


def generate_claude_command_implement_ddd_wireframe(config: TechStackConfig) -> str:
    """Slash command: implement one wireframe → frontend component."""
    frontend = config.frontend_framework.value if config.frontend_framework else "vue"
    return f"""---
description: Generate one frontend component from a single wireframe (element tree + SVG).
argument-hint: <bc-slug> <story-id> <ui-slug>
---

You are generating a single **{frontend}** component for the wireframe
`specs/bounded-contexts/$1/requirements.assets/$2-$3.svg` and the
matching `requirements.md` section that describes it.

## Inputs (read both, in order)

1. **Element tree** — open `specs/bounded-contexts/$1/requirements.md` and find
   the `#### Wireframe: <name>` block whose linked SVG is `$2-$3.svg`. The
   nested bullet list is your component-decomposition hint:
   - `frame: <name> · layout: vertical|horizontal` → a flex container with the
     stated direction.
   - `rect: <name>` containing a `text: "..."` child → a button.
   - `text: "..."` → a heading / paragraph / label, depending on font size.
   - `icon: <name>` → an inline SVG (look it up by `name`; for `lucide:*` names
     use the `lucide-{frontend}` library if installed, otherwise inline the
     path from the SVG below).
2. **SVG** (`requirements.assets/$2-$3.svg`) — the visual reference and the
   only source of numeric values. Read positions, sizes, colors,
   typography directly from the SVG's `<rect>` / `<text>` / `<svg>`
   attributes:
   - position / size: `x`, `y`, `width`, `height` attributes on each element.
   - color: `fill` / `stroke` attributes (already in `rgba(...)` form).
   - corner radius: `rx` on `<rect>`.
   - typography: `font-size`, `font-family`, `font-weight`,
     `text-anchor` on `<text>`.
   After you write your component, open the SVG side-by-side with your
   rendered output and check the diff visually.

   The scene-graph JSON sidecar is no longer emitted (2026-05-12
   amendment); if you remember it from older specs, do not look for it.

## Output

- One **{frontend}** single-file component, named from the BC's
  `domain-terms.md` (Ubiquitous Language) — not from the wireframe slug
  if the names differ. Use PascalCase.
- Use CSS-in-template (scoped styles) with the **exact** numeric values
  from the SVG. Do not approximate — if `rx="12"`, write `border-radius: 12px`.
- Korean text content goes in verbatim — never translate.
- Accessibility: every interactive `<rect>` becomes a `<button>`, every
  `<text>` with `font-size >= 18` becomes an `<h*>` (heading level
  based on hierarchy), every container with a name becomes an
  `aria-label`-ed `<section>`.

## Verification

After writing the component, render it (the project has a dev server). Open the
original SVG in another browser tab and compare:

- Background color (the root SVG's outermost `<rect fill="...">`).
- Container dimensions (the SVG `viewBox` / root `<rect width/height>`).
- Typography (font sizes and weights match per `<text>`).
- Interactive elements (`<rect>` + child `<text>`) render as buttons
  in the expected positions with the expected colors.

If a wireframe's SVG is missing or its `_No scene graph modeled for this UI._`
marker appears in `requirements.md`, stop and report it — do not guess a layout.

## Related

- **DDD-for-SDD Implementation skill**: `.claude/skills/ddd-spec-implementation.md`
- **Frontend skill**: `.claude/skills/{frontend}.md`
"""


def generate_role_agent_ddd_specialist(config: TechStackConfig) -> str:
    """Role-based agent `.claude/agents/ddd-specialist.md` (US7, research D10).

    One per project (replaces the previous per-BC `<bc_name>_agent.md`
    files). Body references skills by relative path; does NOT restate
    skill content; lists the slash commands that may invoke it.
    """
    framework = config.framework.value
    in_microservices = config.deployment == DeploymentStyle.MICROSERVICES
    skill_refs = [
        "- `.claude/skills/ddd-spec-implementation.md` — order to read the DDD artifact set + verification checklist.",
        "- `.claude/skills/ddd-principles.md` — aggregate rules, transaction boundaries, naming conventions.",
        "- `.claude/skills/eventstorming-implementation.md` — sticker-to-code mapping (Command → API, Event → message, ReadModel → query API, Policy → event listener).",
        "- `.claude/skills/gwt-test-generation.md` — Given/When/Then patterns for testing EARS invariants.",
        f"- `.claude/skills/{framework}.md` — {framework} implementation patterns.",
    ]
    if in_microservices:
        skill_refs.append("- `.claude/skills/api-gateway.md` — gateway routing, CORS, service discovery for microservice deployments.")
    skills_block = "\n".join(skill_refs)
    return f"""---
name: ddd-specialist
description: Backend / domain implementation persona. Reads the DDD-for-SDD artifact folders under `specs/bounded-contexts/<bc>/` and produces aggregate + command + event + policy + repository code in the project's chosen tech stack.
---

# DDD Specialist

You implement Bounded Contexts from their DDD-for-SDD artifact folders.
You do **not** invent domain concepts — every name in code matches the
spec verbatim — and you do **not** silently merge aggregates.

## Skills you reference

Reference these by relative path. Their full content is in the file
itself; this agent file does not restate them.

{skills_block}

## When you are invoked

- `/implement-ddd-bc <bc-slug>` — implement one Bounded Context's full
  spec folder (aggregates, commands, events, policies, repository, tests).
- `/implement-ddd-wireframe <bc-slug> <story-id> <ui-slug>` — implement
  a single wireframe's backing code path (the Command or ReadModel API
  the wireframe is bound to).

## How you work

1. Load every file in the BC's spec folder before writing code (see the
   read-order in the `ddd-spec-implementation` skill).
2. For each aggregate, translate the nine sections of its spec onto
   code: root entity, member entities/VOs, properties with mutability,
   EARS invariants → guards + tests, corrective policies → event
   handlers, commands → public methods, events → emitted records,
   repository → interface stub.
3. Produce one Pull Request worth of changes per BC, grouped by
   aggregate. Do not touch other BCs unless `bc-<slug>.md` records an
   inbound/outbound dependency that requires it.
4. If any artifact carries `(not modeled — confirm)`, `(inferred — confirm)`,
   or an item in "Open Decisions", stop and ask the user before guessing.
"""


def generate_role_agent_frontend_engineer(config: TechStackConfig) -> str:
    """Role-based agent `.claude/agents/frontend-engineer.md` (US7, research D10).

    Emitted only when ``config.include_frontend`` is true AND
    ``config.frontend_framework`` is set. References the chosen frontend
    skill by relative path.
    """
    framework = config.framework.value
    front_fw = config.frontend_framework.value if config.frontend_framework else "vue"
    skill_refs = [
        "- `.claude/skills/ddd-principles.md` — DDD vocabulary the wireframes use (Aggregate / Command / ReadModel names).",
        "- `.claude/skills/eventstorming-implementation.md` — sticker-to-component mapping (Command → form, ReadModel → display).",
        "- `.claude/skills/gwt-test-generation.md` — component tests for the bound criteria.",
        f"- `.claude/skills/{framework}.md` — {framework} (backend) implementation patterns — needed for understanding the APIs the components call.",
        f"- `.claude/skills/{front_fw}.md` — {front_fw} component patterns.",
    ]
    skills_block = "\n".join(skill_refs)
    return f"""---
name: frontend-engineer
description: Frontend implementation persona. Reads `specs/frontend/*` for IA/structure, `specs/bounded-contexts/<bc>/domain-terms.md` for naming (Ubiquitous Language), and each wireframe's element tree + SVG for layout. Produces {front_fw} components that match the wireframes and serve the user's business task.
---

# Frontend Engineer

You implement the frontend by consuming **only** the frontend
perspective under `specs/frontend/` plus the canonical wireframe assets
and the Ubiquitous Language dictionary for each UI's owning BC. You do
not browse the rest of each BC's spec folder; that material is for the
DDD specialist, not for shaping the UI.

## Two-rule operating model

1. **Names come from Ubiquitous Language.** Every component, widget,
   store, type, route segment, and API path segment MUST use a name
   that appears verbatim in some BC's `domain-terms.md`. Synonyms,
   translations, and "friendlier" renames are forbidden — and so is
   anything listed under "Aliases to AVOID".
2. **Structure comes from the UI flow.** Menu IA, routing tree, module
   layout, folder grouping, and navigation order all derive from
   `specs/frontend/ui-flow.md` (the user's journey). BC boundaries do
   not shape the frontend's structure; BC fields in
   `menu-structure.md` are traceability metadata only.

Everything in the user's job is one of those two things — naming or
structure — and each has exactly one source.

## Skills you reference

Reference these by relative path. Their full content is in the file
itself; this agent file does not restate them.

{skills_block}

## When you are invoked

- `/generate-frontend` — generate the whole frontend from
  `specs/frontend/*` (structure) + each UI's BC `domain-terms.md`
  (naming).

## How you work

0. **Viewport intent check.** After loading `framework.md`, read its
   `Viewport summary` block. **Before designing any IA, routing, or
   breakpoint system, ask the user**: "The wireframes are predominantly
   `<dominant>` (see Viewport summary in `framework.md`). Should the
   whole menu, routing, and layout be designed `<dominant>`-first?" Wait
   for the user's confirmation before continuing. When the dominant
   reads `mixed — ask the user`, ask the user which viewport class
   should drive the IA instead of guessing. The answer governs
   breakpoint defaults, container max-widths, navigation chrome
   (bottom-tab vs. sidebar), and gesture vs. pointer affordances —
   apply it consistently across every component you generate next.
1. Load `specs/frontend/framework.md` first — its `Framework:` line +
   Conventions block decide component file shape, state management,
   routing library, styling.
2. Load `specs/frontend/ui-flow.md` — this is your **only** structural
   input. Each numbered entry's `Triggered by` line tells you the
   causal step that brings the user to that screen. Use the order to
   design the menu IA (entry-point UIs become top-level entries;
   consecutive UIs in the same flow nest as sub-routes). Each entry
   also carries a `[viewport: mobile|tablet|desktop]` tag — use it to
   sanity-check the user's viewport-intent answer above; flag any
   wireframe whose tag conflicts with the chosen direction.
3. Load `specs/frontend/menu-structure.md` for the flat inventory +
   per-UI traceability. Use it to map each UI to its owning BC for
   the *naming lookup* — not for grouping.
4. For each UI, in `ui-flow.md` order:
   a. Open the BC's `domain-terms.md` and pick the matching name
      (Aggregate / Command / ReadModel name for the bound entity).
      That name becomes the component name in PascalCase, the route
      segment in kebab-case, the store name, the type name, etc.
   b. Open the wireframe's element tree (in the BC's
      `requirements.md`) and its `.svg`. Use the element tree for
      decomposition + a11y; pull numeric values (sizes, padding,
      colors, typography) from the SVG's `<rect>` / `<text>` /
      `<svg>` attributes; the SVG itself is the visual verification
      reference. There is no scene-graph JSON sidecar.
   c. Bind to backend APIs using verbatim BC names: Commands → `POST
      /api/<bc-slug>/<command-name>`; ReadModels → `GET
      /api/<bc-slug>/<readmodel-name>`. Sub-component / prop / type
      names also come from `domain-terms.md` (Member Entity / Value
      Object / Property names).
5. For each numbered EARS line in the bound story's Acceptance
   Criteria, generate a component test per the
   `gwt-test-generation.md` patterns. Test descriptions cite the EARS
   line verbatim.

## Stop conditions

- A `ui-flow.md` entry is `(unreferenced — review)` → stop and ask
  the user.
- A wireframe's scene-graph reference says `_No scene graph modeled_`
  → stop, do not guess.
- A name you would use is missing from `domain-terms.md`, or appears
  under "Aliases to AVOID" → stop, do not invent or synonym.
- `framework.md` Conventions reads `(no curated conventions for this
  framework — confirm)` → stop and ask the user.
- `framework.md` Viewport summary reads `mixed — ask the user`, or
  you have not yet received the user's viewport-intent answer for the
  current run → stop and ask before generating components.
"""


def generate_claude_command_generate_frontend(config: TechStackConfig) -> str:
    """Slash command `.claude/commands/generate-frontend.md` (US7, FR-024).

    Emitted only when ``config.ai_assistant=claude`` AND
    ``config.spec_format=ddd`` AND ``config.include_frontend=true``.
    Its body limits the agent's inputs to ``specs/frontend/*`` plus the
    referenced wireframe assets, separates **naming** (Ubiquitous
    Language from each BC's ``domain-terms.md``) from **structure** (UI
    flow only — never BC slicing), and frames the work around the
    user's business task.
    """
    front_fw = config.frontend_framework.value if config.frontend_framework else "vue"
    return f"""---
description: Generate the whole frontend from `specs/frontend/`. BC artifacts are consulted ONLY for naming (Ubiquitous Language); IA / routing / module structure come from the UI flow alone.
argument-hint: (no arguments)
---

You are generating the project's frontend in **{front_fw}**. Adopt the
`@.claude/agents/frontend-engineer.md` agent persona for this session.

## Core principles (read these before anything else)

1. **Business purpose first.** Each screen exists to let a specific
   user complete a specific business task. Your job is to make those
   tasks easy and obvious. The DDD model is a *vocabulary*, not a UI
   blueprint.
2. **Naming from Ubiquitous Language, structure from UI flow.**
   - **Names** of components, widgets, stores, route paths, page
     titles, props, and types MUST come from
     `specs/bounded-contexts/<bc>/domain-terms.md` for the BC whose
     wireframe you are implementing. No synonyms, no translations, no
     "friendlier" renames. Entries under "Aliases to AVOID" are
     forbidden names — never use them.
   - **Everything else** — IA, routing tree, module layout, folder
     grouping, menu hierarchy, navigation order — is decided strictly
     from `specs/frontend/ui-flow.md` and the inventory in
     `specs/frontend/menu-structure.md`. BC boundaries do not shape
     the frontend structure.
3. **Do not read BC artifacts for IA.** The only BC files you load are
   `domain-terms.md` (naming) and the per-wireframe scene-graph /
   element-tree assets referenced from `ui-flow.md`. Do not browse
   `bc-<slug>.md`, `aggregate-<slug>.md`, or other BC files looking
   for module structure — that would re-introduce BC-centric thinking.

## Inputs (read in this exact order)

1. `specs/frontend/framework.md` — parse line `Framework: <name>`; use
   the Conventions block for component file shape, state management,
   routing library, styling. **Also parse the `Viewport summary`
   block** — it reports counts of mobile / tablet / desktop / unknown
   wireframes and a `Dominant:` line. The dominant value (or `mixed —
   ask the user` when no class crosses 70%) drives step 0 of the plan
   below.
2. `specs/frontend/ui-flow.md` — the **causal order** of UI screens
   across the user's whole journey. This is the only structural input.
3. `specs/frontend/menu-structure.md` — a flat **inventory** of bound
   UIs with entry-point / unreferenced markers and traceability fields
   (owning BC, story, actor, binding). Use this to design the menu IA
   yourself; do NOT take its BC labels as a grouping directive.
4. For each UI in the inventory, follow the relative links to its
   canonical wireframe assets (NOT into the rest of the BC folder):
   - the matching `Wireframe:` block in
     `../bounded-contexts/<bc>/requirements.md` (element tree).
   - `../bounded-contexts/<bc>/requirements.assets/<userStoryId>-<ui-slug>.svg`
     — the only visual asset. Read numeric values you need (positions,
     sizes, colors, typography) directly from its `<rect>` / `<text>` /
     `<svg>` attributes. There is no scene-graph JSON sidecar.
5. **Naming lookup only:**
   `../bounded-contexts/<bc>/domain-terms.md` for the BC of each UI —
   to pull Aggregate / Command / Event / ReadModel / Property names
   verbatim. Treat this file as a dictionary; do not read its
   "Business Context" prose looking for IA hints.

## Plan

0. **Confirm viewport intent with the user — BEFORE doing anything
   else.** Read the `Viewport summary` block in `framework.md`. Ask
   the user verbatim:
   > "Wireframes are predominantly `<dominant>` ({{counts}}). Should I
   > design the whole menu IA, routing, breakpoints, and component
   > chrome `<dominant>`-first?"
   When the summary reads `mixed — ask the user`, instead ask which
   viewport class should drive the IA (mobile / tablet / desktop) and
   why; don't pick one silently. Record the answer at the top of the
   generated project's README and use it consistently below.
1. Build the project skeleton per the framework's conventions
   (component shape, state library, routing library, styling). Apply
   the viewport-intent answer from step 0 to: default container
   max-widths, navigation chrome (bottom-tab vs. sidebar vs. top-nav),
   touch vs. pointer affordances, breakpoint thresholds.
2. **Design the menu IA from the user's workflow.** Read
   `ui-flow.md` end-to-end and decide:
   - Top-level entries from entry-point UIs (no upstream trigger) and
     workflow stages or user roles. **Not** from BC names.
   - Sub-flows grouped by consecutive UIs the same user traverses.
   - Where to place entries marked `(unreferenced — review)` — if you
     cannot justify a placement, stop and ask the user.
   The BC labels in the inventory are *traceability metadata*, not
   menu sections.
3. For each `ui-flow.md` entry in order, generate one component. Its
   name MUST come from the owning BC's `domain-terms.md` (Aggregate /
   Command / ReadModel name, in PascalCase). Wire it into the route
   you decided in step 2.
4. For each wireframe component:
   - Use the element tree for component decomposition + accessibility
     names. Sub-component names come from `domain-terms.md` of the
     same BC (Member Entity / Value Object / Property names) — never
     invented from English UI labels.
   - Read numeric values (positions, sizes, colors, typography) from
     the SVG's `<rect>` / `<text>` / `<svg>` attributes directly. The
     scene-graph JSON sidecar is no longer emitted.
   - Open the SVG side-by-side with your rendered output and check
     the visual diff (colors, positions, font sizes).
5. **Bind to backend APIs using Ubiquitous-Language names.**
   - A wireframe attached to a Command → POST to `/api/<bc-slug>/<command-name>`
     using the Command name from `domain-terms.md` verbatim. The
     request shape comes from the Command's properties (also in
     `domain-terms.md`).
   - A wireframe attached to a ReadModel → GET from `/api/<bc-slug>/<readmodel-name>`
     using the ReadModel name from `domain-terms.md` verbatim.
6. Stores / state modules carry the same names as the underlying
   Aggregate or ReadModel (e.g. a Pinia store for `Order` is
   `useOrderStore`, not `useOrderManagementStore`). Types/interfaces
   in TypeScript match Aggregate / Value Object names from
   `domain-terms.md`.
7. For each numbered EARS line in the bound story's Acceptance Criteria,
   generate a matching test using the `.claude/skills/gwt-test-generation.md`
   patterns. Test descriptions cite the EARS line verbatim.

## Stop conditions

- A `ui-flow.md` entry is `(unreferenced — review)` → stop and ask
  where to place it.
- A wireframe's scene-graph link returns `_No scene graph modeled_` →
  stop, do not guess a layout.
- `framework.md` Conventions reads `(no curated conventions for this
  framework — confirm)` → stop and ask the user.
- `framework.md` Viewport summary `Dominant:` reads `mixed — ask the
  user`, or you have not yet asked the user to confirm viewport
  intent for the current run → stop and ask before any code is
  generated.
- A `ui-flow.md` entry's `[viewport: ...]` tag conflicts with the
  user's confirmed viewport intent (e.g. a `desktop` wireframe in an
  otherwise mobile-first project) → stop and ask whether to render it
  as a companion screen, redirect to mobile, or treat as a separate
  responsive breakpoint.
- A name you would use in code is not present in the BC's
  `domain-terms.md`, or appears under "Aliases to AVOID" → stop, do
  not invent or synonym-substitute.

## Done criteria

- Every `ui-flow.md` entry has a component implementing the user task
  it documents.
- Every public identifier (component, store, type, route segment, API
  path segment) appears verbatim in some BC's `domain-terms.md`.
- Menu IA reflects user workflow (entry points → flows → sub-flows),
  not BC boundaries. A reviewer reading the navigation should see the
  *business journey*, not the *bounded-context inventory*.
- Every component's bound EARS criteria have matching tests.
- The frontend builds and the navigation renders end-to-end.
"""

