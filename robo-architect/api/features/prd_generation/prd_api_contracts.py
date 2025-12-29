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


class PRDGenerationRequest(BaseModel):
    node_ids: list[str] = Field(..., description="List of node IDs from canvas")
    tech_stack: TechStackConfig = Field(default_factory=TechStackConfig)


