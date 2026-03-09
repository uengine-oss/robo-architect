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
    VUE = "vue"
    REACT = "react"


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
    # Frontend options
    frontend_framework: FrontendFramework | None = Field(default=None, description="Frontend framework (Vue, React, Angular, etc.)")
    include_frontend: bool = Field(default=False, description="Include frontend PRD and rules")


class PRDGenerationRequest(BaseModel):
    node_ids: list[str] | None = Field(default=None, description="List of node IDs from canvas. Note: PRD generation always includes all Bounded Contexts regardless of this parameter.")
    tech_stack: TechStackConfig = Field(default_factory=TechStackConfig)


