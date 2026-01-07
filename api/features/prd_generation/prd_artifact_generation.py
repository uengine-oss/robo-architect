from __future__ import annotations

from datetime import datetime

from api.features.prd_generation.prd_api_contracts import Database, Framework, TechStackConfig


def generate_main_prd(bcs: list[dict], config: TechStackConfig) -> str:
    prd = f"""# {config.project_name} - Product Requirements Document

Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Technology Stack

| Component | Choice |
|-----------|--------|
| **Language** | {config.language.value} |
| **Framework** | {config.framework.value} |
| **Messaging** | {config.messaging.value} |
| **Database** | {config.database.value} |
| **Deployment** | {config.deployment.value} |

## Bounded Contexts
"""

    prd += "\n| BC Name | Aggregates | Commands | Events | Policies |\n"
    prd += "|---------|------------|----------|--------|----------|\n"
    for bc in bcs:
        aggs = bc.get("aggregates", []) or []
        cmds = sum(len(a.get("commands", []) or []) for a in aggs)
        evts = sum(len(a.get("events", []) or []) for a in aggs)
        pols = len(bc.get("policies", []) or [])
        prd += f"| {bc.get('name', 'Unknown')} | {len(aggs)} | {cmds} | {evts} | {pols} |\n"

    prd += "\n## Notes\n- This PRD was generated from the Event Storming model stored in Neo4j.\n"
    return prd


def generate_bc_spec(bc: dict, config: TechStackConfig) -> str:
    name = bc.get("name", "Unknown")
    spec = f"""# {name} Bounded Context Specification

## Overview
- **BC ID**: {bc.get("id", "")}
- **Description**: {bc.get("description", "No description")}

## Aggregates
"""
    for agg in bc.get("aggregates", []) or []:
        spec += f"\n### {agg.get('name', 'Unknown')}\n"
        if agg.get("rootEntity"):
            spec += f"- Root Entity: `{agg['rootEntity']}`\n"
        if agg.get("commands"):
            spec += "- Commands:\n"
            for cmd in agg["commands"]:
                if cmd.get("id"):
                    spec += f"  - `{cmd.get('name','')}` (actor: {cmd.get('actor','')})\n"
        if agg.get("events"):
            spec += "- Events:\n"
            for evt in agg["events"]:
                if evt.get("id"):
                    spec += f"  - `{evt.get('name','')}` (v{evt.get('version','1')})\n"

    if bc.get("policies"):
        spec += "\n## Policies\n"
        for pol in bc["policies"]:
            if pol.get("id"):
                spec += f"- `{pol.get('name','')}`: triggers `{pol.get('triggerEventId')}` -> invokes `{pol.get('invokeCommandId')}`\n"

    spec += "\n## Implementation Notes\n"
    spec += f"- Framework: `{config.framework.value}`\n- Messaging: `{config.messaging.value}`\n"
    return spec


def generate_claude_md(bcs: list[dict], config: TechStackConfig) -> str:
    return f"""# CLAUDE.md - AI Assistant Context

## Project
- Name: {config.project_name}
- Deployment: {config.deployment.value}
- Stack: {config.language.value} / {config.framework.value}
- Messaging: {config.messaging.value}
- Database: {config.database.value}

## Bounded Contexts
{chr(10).join([f"- {bc.get('name','Unknown')} ({bc.get('id','')})" for bc in bcs])}
"""


def generate_cursor_rules(config: TechStackConfig) -> str:
    return f"""# Cursor Rules for {config.project_name}

- Follow DDD naming: Commands are verbs, Events are past tense
- Keep BC boundaries clear
- Prefer explicit schemas for events and commands
"""


def generate_agent_config(bc: dict) -> str:
    bc_name = (bc.get("name", "unknown") or "unknown").lower().replace(" ", "_")
    return f"""# Agent Configuration: {bc.get('name','Unknown')}

## Scope
- Only modify files within `{bc_name}/`
- Respect event contracts defined in `specs/{bc_name}_spec.md`
"""


def generate_readme(bcs: list[dict], config: TechStackConfig) -> str:
    return f"""# {config.project_name}

Generated from Event Storming model.

## Bounded Contexts
{chr(10).join([f"- {bc.get('name','Unknown')}: {bc.get('description','')}" for bc in bcs])}
"""


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
    if config.database == Database.POSTGRESQL:
        db_service = """  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: ${DB_NAME:-app}
      POSTGRES_USER: ${DB_USER:-postgres}
      POSTGRES_PASSWORD: ${DB_PASSWORD:-postgres}
    ports:
      - "5432:5432"
"""
    elif config.database == Database.MONGODB:
        db_service = """  mongodb:
    image: mongo:6
    ports:
      - "27017:27017"
"""
    else:
        db_service = ""

    return f"""version: "3.8"
services:
{db_service}
"""


