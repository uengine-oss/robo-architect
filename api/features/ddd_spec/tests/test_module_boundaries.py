"""Static guard: Constitution VI + Feature-modular architecture (T037).

- No direct ``openai`` / ``anthropic`` / ``google.*`` imports inside
  ``api/features/ddd_spec/`` — LLM access must go through
  ``api/features/ingestion/ingestion_llm_runtime`` per Constitution VI.
- No sibling-feature imports except ``api/platform/*`` and the documented
  pass-through to ``ingestion_llm_runtime``.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

MODULE_ROOT = Path(__file__).resolve().parent.parent


def _python_files():
    for p in MODULE_ROOT.rglob("*.py"):
        if p.name.startswith("test_"):
            continue
        if "tests" in p.parts:
            continue
        yield p


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                out.append(node.module)
    return out


FORBIDDEN_PROVIDERS = ("openai", "anthropic", "google.")


def test_no_direct_llm_provider_imports():
    bad: list[str] = []
    for path in _python_files():
        for imp in _imports(path):
            if any(imp == fp or imp.startswith(fp) for fp in FORBIDDEN_PROVIDERS):
                bad.append(f"{path.relative_to(MODULE_ROOT)} imports {imp}")
    assert not bad, "Forbidden LLM-provider imports (Constitution VI):\n" + "\n".join(bad)


ALLOWED_FEATURE_IMPORTS = {
    # The one pass-through to a sibling feature documented in plan.md /
    # Constitution Check is the LLM runtime façade. Everything else must
    # come from api/platform/* or stay inside ddd_spec.
    "api.features.ingestion.ingestion_llm_runtime",
}


def test_no_unauthorized_sibling_feature_imports():
    bad: list[str] = []
    for path in _python_files():
        for imp in _imports(path):
            if imp.startswith("api.features.") and not imp.startswith("api.features.ddd_spec"):
                if imp not in ALLOWED_FEATURE_IMPORTS:
                    bad.append(f"{path.relative_to(MODULE_ROOT)} imports {imp}")
    assert not bad, "Cross-feature imports must go through api/platform/* (Principle V):\n" + "\n".join(bad)
