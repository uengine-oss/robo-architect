import asyncio

import pytest

from api.platform.skill_execution_strategy import (
    OpenAICompatibleSettings,
    OpenAICompatibleSkillStrategy,
    skill_runner_provider,
)


def test_provider_alias_and_default(monkeypatch):
    monkeypatch.delenv("SKILL_RUNNER_PROVIDER", raising=False)
    assert skill_runner_provider() == "claude_cli"

    monkeypatch.setenv("SKILL_RUNNER_PROVIDER", "frentis")
    assert skill_runner_provider() == "openai_compatible"


def test_openai_settings_require_all_values(monkeypatch):
    monkeypatch.setenv("SKILL_RUNNER_API_KEY", "")
    monkeypatch.setenv("SKILL_RUNNER_BASE_URL", "http://internal/v1")
    monkeypatch.setenv("SKILL_RUNNER_MODEL", "internal-model")

    with pytest.raises(RuntimeError, match="SKILL_RUNNER_API_KEY"):
        OpenAICompatibleSettings.from_env()


def test_file_tools_are_limited_to_allowed_roots(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_RUNNER_API_KEY", "test")
    monkeypatch.setenv("SKILL_RUNNER_BASE_URL", "http://internal/v1")
    monkeypatch.setenv("SKILL_RUNNER_MODEL", "internal-model")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source = workspace / "Sample.java"
    source.write_text("class Sample {}\n", encoding="utf-8")

    strategy = OpenAICompatibleSkillStrategy(
        project_root=workspace,
        cwd=workspace,
    )
    assert asyncio.run(strategy._tool("Read", {"file_path": str(source)})) == "class Sample {}\n"
    assert "Sample.java" in asyncio.run(strategy._tool("Glob", {"pattern": "*.java"}))

    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    with pytest.raises(ValueError, match="작업공간 밖"):
        asyncio.run(strategy._tool("Read", {"file_path": str(outside)}))
