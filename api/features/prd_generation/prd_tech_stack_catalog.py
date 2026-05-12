from __future__ import annotations

from typing import Optional

from api.features.ddd_spec.projection import FrameworkConventions
from api.features.prd_generation.prd_api_contracts import Database, DeploymentStyle, Framework, FrontendFramework, Language, MessagingPlatform


# Frontend convention catalog (feature 022 P5 / research D7).
#
# Looked up by :func:`get_framework_conventions`. An unknown framework
# returns ``None``; the frontend renderer then emits
# ``frontend_framework_unsupported`` and renders the "(no curated
# conventions — confirm)" marker in ``specs/frontend/framework.md``.
FRAMEWORK_CONVENTIONS: dict[FrontendFramework, FrameworkConventions] = {
    FrontendFramework.VUE: FrameworkConventions(
        framework="vue",
        component_file_shape="single-file `.vue` component (template / script setup / style scoped)",
        state_default="Pinia store under `src/stores/`",
        routing_default="Vue Router 4 with `<router-view>`",
        styling_default="scoped CSS in the SFC",
    ),
    FrontendFramework.REACT: FrameworkConventions(
        framework="react",
        component_file_shape="function component in `.tsx`",
        state_default="Zustand store under `src/stores/`",
        routing_default="React Router 6 with `<Outlet>`",
        styling_default="CSS Modules per component",
    ),
    FrontendFramework.SVELTE: FrameworkConventions(
        framework="svelte",
        component_file_shape="`.svelte` single-file component (script / template / style)",
        state_default="Svelte writable store in `$lib/stores/`",
        routing_default="SvelteKit file-based routing under `src/routes/`",
        styling_default="scoped CSS in the `.svelte` file",
    ),
}


def get_framework_conventions(framework: FrontendFramework | None) -> Optional[FrameworkConventions]:
    """Return curated conventions for ``framework`` or ``None`` if unknown."""
    if framework is None:
        return None
    return FRAMEWORK_CONVENTIONS.get(framework)


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
        "frontend_frameworks": [
            {"value": f.value, "label": f.value.replace("-", " ").title()}
            for f in FrontendFramework
        ],
    }


