from __future__ import annotations

import io
import time
import zipfile
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from starlette.requests import Request

from api.features.prd_generation.prd_api_contracts import PRDGenerationRequest
from api.features.prd_generation.prd_api_contracts import AIAssistant
from api.features.prd_generation.prd_artifact_generation import (
    generate_agent_config,
    generate_bc_spec,
    generate_claude_md,
    generate_claude_skill_ddd_principles,
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
    generate_gwt_test_generation_rule,
    generate_frontend_cursor_rule,
    generate_frontend_prd,
    generate_main_prd,
    generate_readme,
)
from api.features.prd_generation.prd_model_data import get_bcs_from_nodes
from api.platform.observability.request_logging import http_context, sha256_bytes, summarize_for_log
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


@router.post("/generate")
async def generate_prd(request: PRDGenerationRequest, http_request: Request):
    t0 = time.perf_counter()
    # Always generate PRD for all BCs regardless of selected nodes
    # PRD should always include all Bounded Contexts in the system

    SmartLogger.log(
        "INFO",
        "PRD: generation plan requested.",
        category="api.prd.generate.request",
        params={
            **http_context(http_request),
            "inputs": {"node_ids": "all (always)", "tech_stack": request.tech_stack.model_dump()},
        },
    )

    bcs = get_bcs_from_nodes(None)  # Always get all BCs
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
            files_to_generate.append("Frontend-PRD.md")
    # Add tech stack specific rule (not BC-specific)
    if config.ai_assistant == AIAssistant.CURSOR:
        # Event Storming 기반 세분화된 rules 추가
        files_to_generate.append(".cursor/rules/ddd-principles.mdc")
        files_to_generate.append(".cursor/rules/eventstorming-implementation.mdc")
        files_to_generate.append(".cursor/rules/gwt-test-generation.mdc")
        # Tech stack specific rule
        tech_stack_rule_name = f"{config.framework.value}.mdc"
        files_to_generate.append(f".cursor/rules/{tech_stack_rule_name}")
        # Add frontend rule and PRD if frontend is included (Cursor only)
        if config.include_frontend and config.frontend_framework:
            frontend_rule_name = f"{config.frontend_framework.value}.mdc"
            files_to_generate.append(f".cursor/rules/{frontend_rule_name}")
            files_to_generate.append("Frontend-PRD.md")
    
    for bc in bcs:
        bc_name = (bc.get("name", "unknown") or "unknown").lower().replace(" ", "_")
        files_to_generate.append(f"specs/{bc_name}_spec.md")
        if config.ai_assistant == AIAssistant.CLAUDE:
            files_to_generate.append(f".claude/agents/{bc_name}_agent.md")

    if config.include_docker:
        files_to_generate.append("docker-compose.yml")
        files_to_generate.append("Dockerfile")

    payload = {
        "success": True,
        "bounded_contexts": [{"id": bc.get("id"), "name": bc.get("name")} for bc in bcs],
        "tech_stack": config.model_dump(),
        "files_to_generate": files_to_generate,
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

    SmartLogger.log(
        "INFO",
        "PRD: zip download requested.",
        category="api.prd.download.request",
        params={
            **http_context(http_request),
            "inputs": {"node_ids": "all (always)", "tech_stack": request.tech_stack.model_dump()},
        },
    )

    bcs = get_bcs_from_nodes(None)  # Always get all BCs
    if not bcs:
        raise HTTPException(status_code=404, detail="No Bounded Contexts found for the given nodes")

    config = request.tech_stack
    zip_buffer = io.BytesIO()

    t_zip0 = time.perf_counter()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        # Generate CLAUDE.md only for Claude assistant
        if config.ai_assistant == AIAssistant.CLAUDE:
            zip_file.writestr("CLAUDE.md", generate_claude_md(bcs, config))
            # Generate Claude skills
            zip_file.writestr(".claude/skills/ddd-principles.md", generate_claude_skill_ddd_principles(config))
            zip_file.writestr(".claude/skills/eventstorming-implementation.md", generate_claude_skill_eventstorming_implementation(config))
            zip_file.writestr(".claude/skills/gwt-test-generation.md", generate_claude_skill_gwt_test_generation(config))
            zip_file.writestr(f".claude/skills/{config.framework.value}.md", generate_claude_skill_tech_stack(config))
            if config.include_frontend and config.frontend_framework:
                frontend_skill = generate_claude_skill_frontend(config)
                if frontend_skill:
                    zip_file.writestr(f".claude/skills/{config.frontend_framework.value}.md", frontend_skill)
                # Generate frontend PRD for Claude (same as Cursor)
                frontend_prd = generate_frontend_prd(bcs, config)
                if frontend_prd:
                    zip_file.writestr("Frontend-PRD.md", frontend_prd)
        zip_file.writestr("PRD.md", generate_main_prd(bcs, config))
        zip_file.writestr(".cursorrules", generate_cursor_rules(config))

        # Generate tech stack specific rule (not BC-specific)
        if config.ai_assistant == AIAssistant.CURSOR:
            # Event Storming 기반 세분화된 rules 생성
            zip_file.writestr(".cursor/rules/ddd-principles.mdc", generate_ddd_principles_rule(config))
            zip_file.writestr(".cursor/rules/eventstorming-implementation.mdc", generate_eventstorming_implementation_rule(config))
            zip_file.writestr(".cursor/rules/gwt-test-generation.mdc", generate_gwt_test_generation_rule(config))
            # Tech stack specific rule
            tech_stack_rule_name = f"{config.framework.value}.mdc"
            zip_file.writestr(f".cursor/rules/{tech_stack_rule_name}", generate_cursor_tech_stack_rule(config))
            # Generate frontend rule and PRD if frontend is included (Cursor only)
            if config.include_frontend and config.frontend_framework:
                frontend_rule = generate_frontend_cursor_rule(config)
                if frontend_rule:
                    frontend_rule_name = f"{config.frontend_framework.value}.mdc"
                    zip_file.writestr(f".cursor/rules/{frontend_rule_name}", frontend_rule)
                # Generate frontend PRD
                frontend_prd = generate_frontend_prd(bcs, config)
                if frontend_prd:
                    zip_file.writestr("Frontend-PRD.md", frontend_prd)
        
        for bc in bcs:
            bc_name = (bc.get("name", "unknown") or "unknown").lower().replace(" ", "_")
            zip_file.writestr(f"specs/{bc_name}_spec.md", generate_bc_spec(bc, config))
            if config.ai_assistant == AIAssistant.CLAUDE:
                zip_file.writestr(f".claude/agents/{bc_name}_agent.md", generate_agent_config(bc, config))

        if config.include_docker:
            zip_file.writestr("docker-compose.yml", generate_docker_compose(config))
            zip_file.writestr("Dockerfile", generate_dockerfile(config))

        zip_file.writestr("README.md", generate_readme(bcs, config))

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


