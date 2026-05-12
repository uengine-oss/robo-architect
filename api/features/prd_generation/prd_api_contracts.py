from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Language(str, Enum):
    JAVA = "java"
    KOTLIN = "kotlin"
    TYPESCRIPT = "typescript"
    PYTHON = "python"
    GO = "go"


class Framework(str, Enum):
    SPRING_BOOT = "spring-boot"
    SPRING_WEBFLUX = "spring-webflux"
    NESTJS = "nestjs"
    EXPRESS = "express"
    FASTAPI = "fastapi"
    GIN = "gin"
    FIBER = "fiber"


class FrontendFramework(str, Enum):
    """Frontend frameworks supported by the PRD-generation flow.

    v1 ships ``vue`` and ``react``; the 2026-05-12 amendment (feature 022 P5)
    adds ``svelte``. Adding a new framework requires registering its
    conventions in
    :data:`api.features.prd_generation.prd_tech_stack_catalog.FRAMEWORK_CONVENTIONS`
    so ``specs/frontend/framework.md`` can render its conventions block.
    """

    VUE = "vue"
    REACT = "react"
    SVELTE = "svelte"


class MessagingPlatform(str, Enum):
    KAFKA = "kafka"
    RABBITMQ = "rabbitmq"
    REDIS_STREAMS = "redis-streams"
    PULSAR = "pulsar"
    IN_MEMORY = "in-memory"


class DeploymentStyle(str, Enum):
    MICROSERVICES = "microservices"
    MODULAR_MONOLITH = "modular-monolith"


class Database(str, Enum):
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    MONGODB = "mongodb"
    H2 = "h2"


class AIAssistant(str, Enum):
    CURSOR = "cursor"
    CLAUDE = "claude"


class SpecFormat(str, Enum):
    """How per-BC spec markdown is laid out inside the generated package.

    - ``prd``: legacy flat layout — one ``specs/<bc_name>_spec.md`` per BC.
    - ``ddd``: the "DDD for SDD" artifact set from feature 022 —
      ``specs/bounded-contexts/<bc-slug>/{domain-terms,bc-<slug>,aggregates/aggregate-*,acl-*,requirements}.md``
      plus ``specs/context-map.md``. Generated via ``api.features.ddd_spec``.
    """

    PRD = "prd"
    DDD = "ddd"


class TechStackConfig(BaseModel):
    language: Language = Language.JAVA
    framework: Framework = Framework.SPRING_BOOT
    messaging: MessagingPlatform = MessagingPlatform.KAFKA
    deployment: DeploymentStyle = DeploymentStyle.MICROSERVICES
    database: Database = Database.POSTGRESQL
    project_name: str = Field(default="my-project", description="Project name for the generated code")
    package_name: str = Field(default="com.example", description="Base package name (for Java/Kotlin)")
    include_docker: bool = True
    include_kubernetes: bool = False
    include_tests: bool = True
    ai_assistant: AIAssistant = Field(default=AIAssistant.CURSOR, description="AI assistant to use: cursor or claude")
    # Spec layout — choose between legacy flat per-BC specs and the
    # "DDD for SDD" artifact set produced by feature 022.
    spec_format: SpecFormat = Field(
        default=SpecFormat.PRD,
        description="Per-BC spec layout: 'prd' (legacy flat) or 'ddd' (DDD-for-SDD artifact set; feature 022)",
    )
    # Frontend options
    frontend_framework: FrontendFramework | None = Field(default=None, description="Frontend framework (Vue, React, Angular, etc.)")
    include_frontend: bool = Field(default=False, description="Include frontend PRD and rules")


class PRDGenerationRequest(BaseModel):
    node_ids: list[str] | None = Field(default=None, description="List of node IDs from canvas. Note: PRD generation always includes all Bounded Contexts regardless of this parameter.")
    tech_stack: TechStackConfig = Field(default_factory=TechStackConfig)


