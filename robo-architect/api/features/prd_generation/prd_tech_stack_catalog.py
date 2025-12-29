from __future__ import annotations

from api.features.prd_generation.prd_api_contracts import Database, DeploymentStyle, Framework, Language, MessagingPlatform


def _get_framework_languages(framework: Framework) -> list[str]:
    mapping = {
        Framework.SPRING_BOOT: ["java", "kotlin"],
        Framework.SPRING_WEBFLUX: ["java", "kotlin"],
        Framework.NESTJS: ["typescript"],
        Framework.EXPRESS: ["typescript", "javascript"],
        Framework.FASTAPI: ["python"],
        Framework.GIN: ["go"],
        Framework.FIBER: ["go"],
    }
    return mapping.get(framework, [])


def _get_messaging_description(messaging: MessagingPlatform) -> str:
    descriptions = {
        MessagingPlatform.KAFKA: "Distributed event streaming, best for microservices",
        MessagingPlatform.RABBITMQ: "Message broker with flexible routing",
        MessagingPlatform.REDIS_STREAMS: "Lightweight, good for simpler use cases",
        MessagingPlatform.PULSAR: "Multi-tenant, geo-replication support",
        MessagingPlatform.IN_MEMORY: "For modular monolith, uses internal event bus",
    }
    return descriptions.get(messaging, "")


def build_tech_stack_options() -> dict:
    return {
        "languages": [{"value": l.value, "label": l.name.title()} for l in Language],
        "frameworks": [
            {"value": f.value, "label": f.value.replace("-", " ").title(), "languages": _get_framework_languages(f)}
            for f in Framework
        ],
        "messaging": [
            {"value": m.value, "label": m.value.replace("-", " ").title(), "description": _get_messaging_description(m)}
            for m in MessagingPlatform
        ],
        "deployments": [{"value": d.value, "label": d.value.replace("-", " ").title()} for d in DeploymentStyle],
        "databases": [{"value": d.value, "label": d.value.title()} for d in Database],
    }


