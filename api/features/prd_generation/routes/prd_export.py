from __future__ import annotations

import io
import time
import zipfile
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field
from starlette.requests import Request

from api.features.prd_generation.prd_api_contracts import PRDGenerationRequest
from api.features.prd_generation.prd_api_contracts import AIAssistant, DeploymentStyle, SpecFormat
from api.features.prd_generation.prd_artifact_generation import (
    generate_api_gateway_rule,
    generate_bc_spec_files,
    generate_claude_command_generate_frontend,
    generate_claude_command_implement_ddd_bc,
    generate_claude_command_implement_ddd_wireframe,
    generate_claude_md,
    generate_claude_skill_api_gateway,
    generate_claude_skill_ddd_principles,
    generate_claude_skill_ddd_spec_implementation,
    generate_claude_skill_eventstorming_implementation,
    generate_claude_skill_frontend,
    generate_claude_skill_gwt_test_generation,
    generate_claude_skill_tech_stack,
    generate_cursor_tech_stack_rule,
    generate_cursor_rules,
    generate_docker_compose,
    generate_dockerfile,
    generate_ddd_principles_rule,
    generate_eventstorming_implementation_rule,
    generate_frontend_prd,
    generate_gwt_test_generation_rule,
    generate_frontend_cursor_rule,
    generate_main_prd,
    generate_readme,
    generate_role_agent_ddd_specialist,
    generate_role_agent_frontend_engineer,
)
from api.features.prd_generation.prd_model_data import get_bcs_from_nodes
from api.platform.observability.request_logging import http_context, sha256_bytes, summarize_for_log
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


def _require_frontend_framework(config) -> None:
    """Enforce FR-020: when include_frontend=true, frontend_framework MUST be set."""
    if config.include_frontend and config.frontend_framework is None:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "frontend_framework_required",
                "message": "Select a frontend framework before generation (vue / react / svelte / …).",
            },
        )


def build_prd_zip(zip_file: zipfile.ZipFile, bcs: list, config) -> None:
    """Shared zip-build for both ``/api/prd/download`` and
    ``/api/claude-code/setup-project``.

    Pre-renders the PRD/CLAUDE/.cursorrules texts, runs the PRD↔
    constitution disjointness lint (raises :class:`PrdSplitLintError`
    on failure so the caller can map to its own error response),
    then writes every file the new contract requires into ``zip_file``:

    - ``PRD.md`` (composition only)
    - ``CLAUDE.md`` or ``.cursorrules`` (the constitution, depending on
      ``ai_assistant``)
    - ``.claude/skills/*`` + ``.claude/commands/*`` (Claude path)
    - ``.cursor/rules/*`` (Cursor path)
    - ``specs/bounded-contexts/<bc>/...`` + ``specs/context-map.md``
      via :func:`api.features.ddd_spec.inproc.pack_ddd_artifacts_to_zip`
      (when ``spec_format=ddd``)
    - ``specs/frontend/{framework,menu-structure,ui-flow}.md`` via
      :func:`api.features.ddd_spec.inproc.render_frontend_spec_to_zip`
      (when ``include_frontend=true`` AND ``spec_format=ddd``)
    - ``.claude/agents/ddd-specialist.md`` (always, Claude path,
      ``spec_format=ddd``) and ``.claude/agents/frontend-engineer.md``
      + ``.claude/commands/generate-frontend.md`` (when also
      ``include_frontend=true``)
    - ``Dockerfile`` + ``docker-compose.yml`` (when ``include_docker``)
    - ``README.md``

    Per-BC ``<bc_name>_agent.md`` files are **never** written (FR-023);
    ``Frontend-PRD.md`` is **never** written (2026-05-12 amendment);
    scene-graph JSON sidecars are **never** written (2026-05-12
    amendment).
    """
    from api.features.prd_generation.prd_split_lint import lint_disjoint

    prd_text = generate_main_prd(bcs, config)
    cursor_rules_text = generate_cursor_rules(config)
    claude_md_text = (
        generate_claude_md(bcs, config)
        if config.ai_assistant == AIAssistant.CLAUDE
        else None
    )
    if config.ai_assistant == AIAssistant.CLAUDE:
        lint_disjoint(prd_text, claude_md_text, constitution_filename="CLAUDE.md")
    else:
        lint_disjoint(prd_text, cursor_rules_text, constitution_filename=".cursorrules")

    if config.ai_assistant == AIAssistant.CLAUDE:
        zip_file.writestr("CLAUDE.md", claude_md_text)
        zip_file.writestr(".claude/skills/ddd-principles.md", generate_claude_skill_ddd_principles(config))
        zip_file.writestr(".claude/skills/eventstorming-implementation.md", generate_claude_skill_eventstorming_implementation(config))
        zip_file.writestr(".claude/skills/gwt-test-generation.md", generate_claude_skill_gwt_test_generation(config))
        zip_file.writestr(f".claude/skills/{config.framework.value}.md", generate_claude_skill_tech_stack(config))
        if config.include_frontend and config.frontend_framework:
            frontend_skill = generate_claude_skill_frontend(config)
            if frontend_skill:
                zip_file.writestr(f".claude/skills/{config.frontend_framework.value}.md", frontend_skill)
        if config.deployment == DeploymentStyle.MICROSERVICES:
            zip_file.writestr(".claude/skills/api-gateway.md", generate_claude_skill_api_gateway(config, bcs))
        if config.spec_format == SpecFormat.DDD:
            zip_file.writestr(".claude/skills/ddd-spec-implementation.md", generate_claude_skill_ddd_spec_implementation(config))
            zip_file.writestr(".claude/commands/implement-ddd-bc.md", generate_claude_command_implement_ddd_bc(config))
            zip_file.writestr(".claude/commands/implement-ddd-wireframe.md", generate_claude_command_implement_ddd_wireframe(config))

    zip_file.writestr("PRD.md", prd_text)
    zip_file.writestr(".cursorrules", cursor_rules_text)

    if config.ai_assistant == AIAssistant.CURSOR:
        zip_file.writestr(".cursor/rules/ddd-principles.mdc", generate_ddd_principles_rule(config))
        zip_file.writestr(".cursor/rules/eventstorming-implementation.mdc", generate_eventstorming_implementation_rule(config))
        zip_file.writestr(".cursor/rules/gwt-test-generation.mdc", generate_gwt_test_generation_rule(config))
        zip_file.writestr(f".cursor/rules/{config.framework.value}.mdc", generate_cursor_tech_stack_rule(config))
        if config.include_frontend and config.frontend_framework:
            frontend_rule = generate_frontend_cursor_rule(config)
            if frontend_rule:
                zip_file.writestr(f".cursor/rules/{config.frontend_framework.value}.mdc", frontend_rule)
        if config.deployment == DeploymentStyle.MICROSERVICES:
            zip_file.writestr(".cursor/rules/api-gateway.mdc", generate_api_gateway_rule(config, bcs))

    if config.spec_format == SpecFormat.DDD:
        from api.features.ddd_spec.inproc import pack_ddd_artifacts_to_zip

        pack_ddd_artifacts_to_zip(zip_file)
        if config.include_frontend and config.frontend_framework is not None:
            from api.features.ddd_spec.inproc import render_frontend_spec_to_zip
            from api.features.prd_generation.prd_tech_stack_catalog import (
                get_framework_conventions,
            )

            render_frontend_spec_to_zip(
                zip_file,
                config.frontend_framework.value,
                get_framework_conventions(config.frontend_framework),
            )
        if config.ai_assistant == AIAssistant.CLAUDE:
            zip_file.writestr(
                ".claude/agents/ddd-specialist.md",
                generate_role_agent_ddd_specialist(config),
            )
            if config.include_frontend and config.frontend_framework is not None:
                zip_file.writestr(
                    ".claude/agents/frontend-engineer.md",
                    generate_role_agent_frontend_engineer(config),
                )
                zip_file.writestr(
                    ".claude/commands/generate-frontend.md",
                    generate_claude_command_generate_frontend(config),
                )
    else:
        for bc in bcs:
            for path, content in generate_bc_spec_files(bc, config).items():
                zip_file.writestr(path, content)
        # Frontend-PRD.md carries UI flow / wireframe inventory / API
        # endpoint contract for the PRD layout. The 2026-05-12 amendment
        # removed it from the DDD path (where `specs/frontend/*.md` +
        # `specs/bounded-contexts/<bc>/domain-terms.md` cover the same
        # ground) but the PRD path has no such replacement.
        if config.include_frontend and config.frontend_framework is not None:
            zip_file.writestr("Frontend-PRD.md", generate_frontend_prd(bcs, config))

    if config.include_docker:
        zip_file.writestr("docker-compose.yml", generate_docker_compose(config))
        zip_file.writestr("Dockerfile", generate_dockerfile(config))

    zip_file.writestr("README.md", generate_readme(bcs, config))

    # Feature 023 — HTML policy-document extension. Pure add-on; degrades
    # to deterministic fallbacks when no LLM provider is configured.
    if getattr(config, "include_html_policy", False):
        try:
            from api.features.prd_generation.html_templates.orchestrator import (
                render_policy_doc_from_neo4j,
            )
            from api.features.prd_generation.html_templates.registry import (
                TemplateNotFoundError,
            )

            html_text = render_policy_doc_from_neo4j(
                config.html_template_id,
                project_name=getattr(config, "project_name", "") or "",
            )
            zip_file.writestr("PRD.html", html_text)
        except TemplateNotFoundError as exc:
            # Template missing isn't fatal for the existing zip path —
            # surface a marker file the user can inspect.
            zip_file.writestr(
                "PRD.html.error.txt",
                f"HTML policy template '{config.html_template_id}' not found: {exc}",
            )


@router.post("/generate")
async def generate_prd(request: PRDGenerationRequest, http_request: Request):
    t0 = time.perf_counter()
    # Always generate PRD for all BCs regardless of selected nodes
    # PRD should always include all Bounded Contexts in the system

    _require_frontend_framework(request.tech_stack)

    SmartLogger.log(
        "INFO",
        "PRD: generation plan requested.",
        category="api.prd.generate.request",
        params={
            **http_context(http_request),
            "inputs": {
                "node_ids": "all (always)",
                "session_id": request.session_id,
                "tech_stack": request.tech_stack.model_dump(),
            },
        },
    )

    bcs = get_bcs_from_nodes(None, session_id=request.session_id)  # Always get all BCs (optionally scoped by session_id)
    if not bcs:
        raise HTTPException(status_code=404, detail="No Bounded Contexts found for the given nodes")

    config = request.tech_stack

    files_to_generate = ["PRD.md", ".cursorrules", "README.md"]
    # Add CLAUDE.md only for Claude assistant
    if config.ai_assistant == AIAssistant.CLAUDE:
        files_to_generate.append("CLAUDE.md")
        # Add Claude skills
        files_to_generate.append(".claude/skills/ddd-principles.md")
        files_to_generate.append(".claude/skills/eventstorming-implementation.md")
        files_to_generate.append(".claude/skills/gwt-test-generation.md")
        files_to_generate.append(f".claude/skills/{config.framework.value}.md")
        if config.include_frontend and config.frontend_framework:
            files_to_generate.append(f".claude/skills/{config.frontend_framework.value}.md")
            # Frontend-PRD.md is NOT emitted (2026-05-12 amendment):
            # the agent reads `specs/frontend/*.md` for IA/structure and
            # `specs/bounded-contexts/<bc>/domain-terms.md` for naming.
            # A separate Frontend-PRD.md tends to leak BC-centric thinking
            # back into the workflow.
        if config.deployment == DeploymentStyle.MICROSERVICES:
            files_to_generate.append(".claude/skills/api-gateway.md")
        # Feature 022 — DDD-for-SDD implementation guide + slash commands.
        if config.spec_format == SpecFormat.DDD:
            files_to_generate.append(".claude/skills/ddd-spec-implementation.md")
            files_to_generate.append(".claude/commands/implement-ddd-bc.md")
            files_to_generate.append(".claude/commands/implement-ddd-wireframe.md")
    # Add tech stack specific rule (not BC-specific)
    if config.ai_assistant == AIAssistant.CURSOR:
        # Event Storming 기반 세분화된 rules 추가
        files_to_generate.append(".cursor/rules/ddd-principles.mdc")
        files_to_generate.append(".cursor/rules/eventstorming-implementation.mdc")
        files_to_generate.append(".cursor/rules/gwt-test-generation.mdc")
        # Tech stack specific rule
        tech_stack_rule_name = f"{config.framework.value}.mdc"
        files_to_generate.append(f".cursor/rules/{tech_stack_rule_name}")
        # Add frontend rule if frontend is included (Cursor only). The
        # legacy Frontend-PRD.md is NOT emitted — see Claude branch.
        if config.include_frontend and config.frontend_framework:
            frontend_rule_name = f"{config.frontend_framework.value}.mdc"
            files_to_generate.append(f".cursor/rules/{frontend_rule_name}")
        if config.deployment == DeploymentStyle.MICROSERVICES:
            files_to_generate.append(".cursor/rules/api-gateway.mdc")

    if config.spec_format == SpecFormat.DDD:
        # Feature 022 — DDD-for-SDD artifact set replaces the flat per-BC
        # spec files. Source the planned paths from the same code that
        # actually renders the artifacts to keep the preview honest.
        from api.features.ddd_spec.inproc import planned_paths_for_preview

        files_to_generate.extend(
            planned_paths_for_preview(
                include_frontend=bool(
                    config.include_frontend and config.frontend_framework is not None
                )
            )
        )
        # FR-023 (US7) — per-BC `<bc_name>_agent.md` files are NOT
        # planned anymore. Role-based agents take their place.
        if config.ai_assistant == AIAssistant.CLAUDE:
            files_to_generate.append(".claude/agents/ddd-specialist.md")
            if config.include_frontend and config.frontend_framework is not None:
                files_to_generate.append(".claude/agents/frontend-engineer.md")
                files_to_generate.append(".claude/commands/generate-frontend.md")
    else:
        for bc in bcs:
            # Same builder the zip-packager uses so the preview matches
            # the actual emitted files (auto-split when oversized).
            files_to_generate.extend(generate_bc_spec_files(bc, config).keys())
        if config.include_frontend and config.frontend_framework is not None:
            files_to_generate.append("Frontend-PRD.md")
        # Non-DDD path also drops per-BC agents — agent set is consistent
        # across spec_format choices (FR-023).

    if config.include_docker:
        files_to_generate.append("docker-compose.yml")
        files_to_generate.append("Dockerfile")

    # Feature 023 — HTML policy document is an opt-in add-on (default off).
    if getattr(config, "include_html_policy", False):
        files_to_generate.append("PRD.html")

    # FR-023 / US7 — surface previously-emitted per-BC `<bc_name>_agent.md`
    # paths as "deprecated" so the user knows to delete their local
    # copies after pulling a new package. We never scan their filesystem;
    # we only describe what the *old* pipeline would have produced.
    deprecated_per_bc_agents: list[dict[str, str]] = []
    if config.ai_assistant == AIAssistant.CLAUDE:
        for bc in bcs:
            bc_name = (bc.get("name", "unknown") or "unknown").lower().replace(" ", "_")
            deprecated_per_bc_agents.append(
                {
                    "kind": "artifact_file",
                    "existing_path": f".claude/agents/{bc_name}_agent.md",
                    "reason": "deprecated_per_bc_agent",
                    "message": (
                        "Per-BC agent files are deprecated; delete your local copy. "
                        "Useful content was migrated to .claude/skills/* and "
                        ".claude/commands/*."
                    ),
                }
            )

    payload = {
        "success": True,
        "bounded_contexts": [{"id": bc.get("id"), "name": bc.get("name")} for bc in bcs],
        "tech_stack": config.model_dump(),
        "files_to_generate": files_to_generate,
        "deprecated_per_bc_agents": deprecated_per_bc_agents,
        "download_url": "/api/prd/download",
    }
    SmartLogger.log(
        "INFO",
        "PRD: generation plan created.",
        category="api.prd.generate.done",
        params={
            **http_context(http_request),
            "duration_ms": int((time.perf_counter() - t0) * 1000),
            "summary": {"bcs": len(bcs), "files_to_generate": len(files_to_generate)},
        },
    )
    return payload


@router.post("/download")
async def download_prd_zip(request: PRDGenerationRequest, http_request: Request):
    t0 = time.perf_counter()
    # Always generate PRD for all BCs regardless of selected nodes
    # PRD should always include all Bounded Contexts in the system

    _require_frontend_framework(request.tech_stack)

    SmartLogger.log(
        "INFO",
        "PRD: zip download requested.",
        category="api.prd.download.request",
        params={
            **http_context(http_request),
            "inputs": {
                "node_ids": "all (always)",
                "session_id": request.session_id,
                "tech_stack": request.tech_stack.model_dump(),
            },
        },
    )

    bcs = get_bcs_from_nodes(None, session_id=request.session_id)  # Always get all BCs (optionally scoped by session_id)
    if not bcs:
        raise HTTPException(status_code=404, detail="No Bounded Contexts found for the given nodes")

    config = request.tech_stack
    zip_buffer = io.BytesIO()

    from api.features.prd_generation.prd_split_lint import PrdSplitLintError

    t_zip0 = time.perf_counter()
    try:
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            build_prd_zip(zip_file, bcs, config)
    except PrdSplitLintError as e:
        raise HTTPException(
            status_code=500,
            detail={
                "code": e.code,
                "file": e.offending_file,
                "substring": e.offending_substring,
                "offset": e.offset,
                "message": str(e),
            },
        )

    zip_buffer.seek(0)
    zip_bytes = zip_buffer.getvalue()
    zip_size = len(zip_bytes)
    zip_sha = sha256_bytes(zip_bytes)
    filename = f"{config.project_name}_prd_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"

    SmartLogger.log(
        "INFO",
        "PRD: zip built and streaming response returned.",
        category="api.prd.download.done",
        params={
            **http_context(http_request),
            "duration_ms": int((time.perf_counter() - t0) * 1000),
            "zip_build_ms": int((time.perf_counter() - t_zip0) * 1000),
            "summary": {"bcs": len(bcs), "zip_bytes": zip_size, "zip_sha256": zip_sha, "filename": filename},
        },
    )

    zip_buffer = io.BytesIO(zip_bytes)
    zip_buffer.seek(0)
    return StreamingResponse(zip_buffer, media_type="application/zip", headers={"Content-Disposition": f"attachment; filename={filename}"})


# ----- Feature 023: HTML policy document preview --------------------------


class HTMLPolicyRequest(BaseModel):
    template_id: str = Field(default="policy-doc-full")
    project_name: str = Field(default="")
    use_llm: bool = Field(default=True)


@router.post("/html-policy")
async def render_html_policy(request: HTMLPolicyRequest, http_request: Request):
    """Render a single self-contained HTML policy document from the current
    Neo4j event-storming graph. Useful for fast preview without rebuilding
    the full PRD zip."""
    t0 = time.perf_counter()
    SmartLogger.log(
        "INFO",
        "PRD: html-policy preview requested.",
        category="api.prd.html_policy.request",
        params={
            **http_context(http_request),
            "inputs": request.model_dump(),
        },
    )
    try:
        from api.features.prd_generation.html_templates.orchestrator import (
            render_policy_doc_from_neo4j,
        )
        from api.features.prd_generation.html_templates.registry import (
            TemplateNotFoundError,
        )
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "html_template_module_unavailable", "message": str(exc)},
        )

    try:
        html_text = render_policy_doc_from_neo4j(
            request.template_id,
            project_name=request.project_name,
            use_llm=request.use_llm,
        )
    except TemplateNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "html_template_not_found", "message": str(exc)},
        )
    except Exception as exc:  # neo4j connection, manifest errors, etc.
        # Distinguish Neo4j availability from other issues by message
        # heuristic; the underlying driver raises ServiceUnavailable.
        text = str(exc)
        if "ServiceUnavailable" in type(exc).__name__ or "neo4j" in text.lower():
            raise HTTPException(
                status_code=503,
                detail={"code": "neo4j_unavailable", "message": text},
            )
        raise HTTPException(
            status_code=500,
            detail={"code": "html_render_failed", "message": text},
        )

    SmartLogger.log(
        "INFO",
        "PRD: html-policy preview rendered.",
        category="api.prd.html_policy.done",
        params={
            **http_context(http_request),
            "duration_ms": int((time.perf_counter() - t0) * 1000),
            "summary": {"bytes": len(html_text)},
        },
    )
    return HTMLResponse(content=html_text, status_code=200)


