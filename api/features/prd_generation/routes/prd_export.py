from __future__ import annotations

import io
import time
import zipfile
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from starlette.requests import Request

from api.features.prd_generation.prd_api_contracts import PRDGenerationRequest
from api.features.prd_generation.prd_artifact_generation import (
    generate_agent_config,
    generate_bc_spec,
    generate_claude_md,
    generate_cursor_rules,
    generate_docker_compose,
    generate_dockerfile,
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
    if not request.node_ids:
        raise HTTPException(status_code=400, detail="node_ids cannot be empty")

    SmartLogger.log(
        "INFO",
        "PRD: generation plan requested.",
        category="api.prd.generate.request",
        params={
            **http_context(http_request),
            "inputs": {"node_ids": summarize_for_log(request.node_ids), "tech_stack": request.tech_stack.model_dump()},
        },
    )

    bcs = get_bcs_from_nodes(request.node_ids)
    if not bcs:
        raise HTTPException(status_code=404, detail="No Bounded Contexts found for the given nodes")

    config = request.tech_stack

    files_to_generate = ["CLAUDE.md", "PRD.md", ".cursorrules"]
    for bc in bcs:
        bc_name = (bc.get("name", "unknown") or "unknown").lower().replace(" ", "_")
        files_to_generate.append(f".claude/agents/{bc_name}_agent.md")
        files_to_generate.append(f"specs/{bc_name}_spec.md")

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
    if not request.node_ids:
        raise HTTPException(status_code=400, detail="node_ids cannot be empty")

    SmartLogger.log(
        "INFO",
        "PRD: zip download requested.",
        category="api.prd.download.request",
        params={
            **http_context(http_request),
            "inputs": {"node_ids": summarize_for_log(request.node_ids), "tech_stack": request.tech_stack.model_dump()},
        },
    )

    bcs = get_bcs_from_nodes(request.node_ids)
    if not bcs:
        raise HTTPException(status_code=404, detail="No Bounded Contexts found for the given nodes")

    config = request.tech_stack
    zip_buffer = io.BytesIO()

    t_zip0 = time.perf_counter()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("CLAUDE.md", generate_claude_md(bcs, config))
        zip_file.writestr("PRD.md", generate_main_prd(bcs, config))
        zip_file.writestr(".cursorrules", generate_cursor_rules(config))

        for bc in bcs:
            bc_name = (bc.get("name", "unknown") or "unknown").lower().replace(" ", "_")
            zip_file.writestr(f"specs/{bc_name}_spec.md", generate_bc_spec(bc, config))
            zip_file.writestr(f".claude/agents/{bc_name}_agent.md", generate_agent_config(bc))

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


