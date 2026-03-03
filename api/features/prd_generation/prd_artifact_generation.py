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

    prd += "\n| BC Name | Aggregates | Commands | Events | ReadModels | Policies | UIs |\n"
    prd += "|---------|------------|----------|--------|------------|----------|-----|\n"
    for bc in bcs:
        aggs = bc.get("aggregates", []) or []
        cmds = sum(len(a.get("commands", []) or []) for a in aggs)
        evts = sum(len(a.get("events", []) or []) for a in aggs)
        rms = len(bc.get("readmodels", []) or [])
        pols = len(bc.get("policies", []) or [])
        uis = len(bc.get("uis", []) or [])
        prd += f"| {bc.get('name', 'Unknown')} | {len(aggs)} | {cmds} | {evts} | {rms} | {pols} | {uis} |\n"

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
        
        # Aggregate Properties
        if agg.get("properties"):
            spec += "- Properties:\n"
            for prop in agg["properties"]:
                if prop.get("id"):
                    prop_type = prop.get("type", "String")
                    is_key = " (Key)" if prop.get("isKey") else ""
                    is_fk = f" (FK -> {prop.get('fkTargetHint', '')})" if prop.get("isForeignKey") else ""
                    spec += f"  - `{prop.get('name', '')}`: {prop_type}{is_key}{is_fk}\n"
                    if prop.get("description"):
                        spec += f"    - {prop.get('description')}\n"
        
        # Commands with Properties
        if agg.get("commands"):
            spec += "- Commands:\n"
            for cmd in agg["commands"]:
                if cmd.get("id"):
                    spec += f"  - `{cmd.get('name','')}` (actor: {cmd.get('actor','')})\n"
                    if cmd.get("properties"):
                        spec += "    - Properties:\n"
                        for prop in cmd["properties"]:
                            if prop.get("id"):
                                prop_type = prop.get("type", "String")
                                is_required = " (required)" if prop.get("isRequired") else ""
                                spec += f"      - `{prop.get('name', '')}`: {prop_type}{is_required}\n"
        
        # Events with Properties
        if agg.get("events"):
            spec += "- Events:\n"
            for evt in agg["events"]:
                if evt.get("id"):
                    spec += f"  - `{evt.get('name','')}` (v{evt.get('version','1')})\n"
                    if evt.get("properties"):
                        spec += "    - Properties:\n"
                        for prop in evt["properties"]:
                            if prop.get("id"):
                                prop_type = prop.get("type", "String")
                                spec += f"      - `{prop.get('name', '')}`: {prop_type}\n"

    # ReadModels
    if bc.get("readmodels"):
        spec += "\n## ReadModels\n"
        for rm in bc["readmodels"]:
            if rm.get("id"):
                spec += f"\n### {rm.get('name', 'Unknown')}\n"
                if rm.get("description"):
                    spec += f"- Description: {rm.get('description')}\n"
                if rm.get("provisioningType"):
                    spec += f"- Provisioning Type: {rm.get('provisioningType')}\n"
                if rm.get("properties"):
                    spec += "- Properties:\n"
                    for prop in rm["properties"]:
                        if prop.get("id"):
                            prop_type = prop.get("type", "String")
                            spec += f"  - `{prop.get('name', '')}`: {prop_type}\n"

    # Policies
    if bc.get("policies"):
        spec += "\n## Policies\n"
        for pol in bc["policies"]:
            if pol.get("id"):
                spec += f"- `{pol.get('name','')}`\n"
                if pol.get("description"):
                    spec += f"  - Description: {pol.get('description')}\n"
                spec += f"  - Triggers: `{pol.get('triggerEventName', 'N/A')}`\n"
                spec += f"  - Invokes: `{pol.get('invokeCommandName', 'N/A')}`\n"

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

    # GWT Test Cases
    if bc.get("gwts"):
        spec += "\n## GWT Test Cases\n"
        for gwt in bc["gwts"]:
            if gwt.get("id"):
                parent_type = gwt.get("parentType", "Unknown")
                spec += f"- GWT for {parent_type} `{gwt.get('parentId', '')}`\n"
                if gwt.get("givenRef"):
                    given = gwt["givenRef"]
                    if isinstance(given, dict):
                        spec += f"  - Given: {given.get('name', 'N/A')}\n"
                if gwt.get("whenRef"):
                    when = gwt["whenRef"]
                    if isinstance(when, dict):
                        spec += f"  - When: {when.get('name', 'N/A')}\n"
                if gwt.get("thenRef"):
                    then = gwt["thenRef"]
                    if isinstance(then, dict):
                        spec += f"  - Then: {then.get('name', 'N/A')}\n"
                if gwt.get("testCases"):
                    test_cases = gwt["testCases"]
                    if isinstance(test_cases, list) and len(test_cases) > 0:
                        spec += f"  - Test Cases: {len(test_cases)} scenarios\n"

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


