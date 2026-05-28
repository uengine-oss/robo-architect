"""
Regression test enforcing the single-chokepoint contract for feature 031.

No file under `api/features/` may directly construct a
`langchain_core.messages.SystemMessage`. All system-message construction
MUST go through `api.platform.llm_messages.build_system_message`, which
appends the per-request generation-language directive.

This test fails the build if any `api/features/` file regresses, and the
failure message points the offending developer at the chokepoint helper.

The escape hatch `_skip_language_directive=True` is allowed in test code
(under `api/tests/`) but forbidden in production feature code.

See:
  - specs/031-generation-language-policy/spec.md FR-008 / FR-015
  - specs/031-generation-language-policy/contracts/language-policy-contract.md C2
  - specs/031-generation-language-policy/research.md D5
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# Resolve to <repo>/api/features regardless of where pytest is invoked from.
_HERE = Path(__file__).resolve()
_API_ROOT = _HERE.parents[2]  # api/tests/regression/ -> api/
_FEATURES_ROOT = _API_ROOT / "features"
_CHOKEPOINT_MODULE = _API_ROOT / "platform" / "llm_messages.py"


def _python_files_under_features() -> list[Path]:
    """All .py files under api/features/, excluding __pycache__."""
    return [
        p
        for p in _FEATURES_ROOT.rglob("*.py")
        if "__pycache__" not in p.parts
    ]


def _find_offending_calls(tree: ast.AST) -> list[tuple[int, str]]:
    """Locate every direct construction of langchain SystemMessage in the tree.

    Recognizes:
      - `SystemMessage(...)` after `from langchain_core.messages import SystemMessage`
      - `SystemMessage(...)` after `from langchain_core.messages import SystemMessage as X` (X(...) detected by alias)
      - `langchain_core.messages.SystemMessage(...)` fully-qualified
      - `messages.SystemMessage(...)` after `from langchain_core import messages`

    Returns (line_number, source_excerpt) tuples; empty list means clean.
    """
    offenses: list[tuple[int, str]] = []

    # Collect every name that resolves to langchain_core's SystemMessage in
    # this file's import-time namespace.
    system_message_aliases: set[str] = set()
    # And every module alias that, when followed by `.SystemMessage`, would
    # resolve to the same class (e.g. `import langchain_core.messages as m`).
    module_aliases: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == "langchain_core.messages":
                for alias in node.names:
                    if alias.name == "SystemMessage":
                        system_message_aliases.add(alias.asname or alias.name)
            elif node.module == "langchain_core":
                for alias in node.names:
                    if alias.name == "messages":
                        module_aliases.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "langchain_core.messages":
                    module_aliases.add(alias.asname or "langchain_core.messages")

    if not system_message_aliases and not module_aliases:
        return []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # Bare name: SystemMessage(...) or its alias
        if isinstance(func, ast.Name) and func.id in system_message_aliases:
            offenses.append((node.lineno, f"{func.id}(...)"))
        # Attribute: foo.SystemMessage(...) where foo is a module alias
        elif isinstance(func, ast.Attribute) and func.attr == "SystemMessage":
            base = _attribute_base_name(func.value)
            if base and (base in module_aliases or base == "langchain_core.messages"):
                offenses.append((node.lineno, f"{base}.SystemMessage(...)"))
    return offenses


def _attribute_base_name(node: ast.expr) -> str | None:
    """Return the dotted-name root for an attribute chain, or None."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return None


def _find_forbidden_skip_kwarg(tree: ast.AST) -> list[tuple[int, str]]:
    """Find calls to build_system_message that pass _skip_language_directive=True.

    Allowed in test code (api/tests/) but forbidden in api/features/.
    """
    offenses: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = None
        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr
        if name != "build_system_message":
            continue
        for kw in node.keywords:
            if kw.arg == "_skip_language_directive":
                # Even passing False would be suspicious; flag any usage so
                # the test is the single audit point. Tests that need this
                # live under api/tests/, which this scan excludes.
                offenses.append((node.lineno, f"build_system_message(..., _skip_language_directive=...)"))
    return offenses


@pytest.mark.parametrize("path", _python_files_under_features(), ids=lambda p: str(p.relative_to(_API_ROOT)))
def test_no_direct_system_message_construction(path: Path):
    """Per-file gate: zero direct SystemMessage construction in api/features/."""
    source = path.read_text()
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as e:
        pytest.fail(f"{path.relative_to(_API_ROOT)}: failed to parse — {e}")
        return

    offenses = _find_offending_calls(tree)
    if offenses:
        rel = path.relative_to(_API_ROOT)
        msg = "\n".join(f"  {rel}:{lineno} — {excerpt}" for lineno, excerpt in offenses)
        pytest.fail(
            f"Feature 031 chokepoint violated: direct SystemMessage construction in api/features/:\n"
            f"{msg}\n\n"
            f"Use `from api.platform.llm_messages import build_system_message` and call "
            f"`build_system_message(content)` instead. The shared builder appends the "
            f"per-request output-language directive set by the language middleware.\n\n"
            f"See specs/031-generation-language-policy/contracts/language-policy-contract.md §C2."
        )


@pytest.mark.parametrize("path", _python_files_under_features(), ids=lambda p: str(p.relative_to(_API_ROOT)))
def test_no_forbidden_skip_kwarg(path: Path):
    """The _skip_language_directive escape hatch is forbidden in api/features/."""
    source = path.read_text()
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        pytest.skip(f"{path}: unparseable (covered by sibling test)")
        return
    offenses = _find_forbidden_skip_kwarg(tree)
    if offenses:
        rel = path.relative_to(_API_ROOT)
        msg = "\n".join(f"  {rel}:{lineno} — {excerpt}" for lineno, excerpt in offenses)
        pytest.fail(
            f"Feature 031: _skip_language_directive=True is a test-only escape and is "
            f"forbidden in api/features/ production code:\n{msg}"
        )


def test_chokepoint_module_exists_and_exposes_build_system_message():
    """Sanity check that the canonical chokepoint module hasn't been deleted/renamed."""
    assert _CHOKEPOINT_MODULE.exists(), (
        f"Expected chokepoint module at {_CHOKEPOINT_MODULE}, but it is missing. "
        f"If you renamed the module, update both this test and the chokepoint "
        f"contract document (specs/031-generation-language-policy/contracts/)."
    )
    from api.platform.llm_messages import build_system_message  # noqa: F401


def test_meta_detector_flags_a_synthetic_violation(tmp_path):
    """Meta-test: the AST detector itself works on a synthetic violation.

    Without this we cannot tell whether the two parametrised tests above are
    passing because the codebase is clean or because the detector is broken.
    """
    synthetic = tmp_path / "deliberately_bad.py"
    synthetic.write_text(
        "from langchain_core.messages import SystemMessage\n"
        "\n"
        "msg = SystemMessage(content='this should be flagged')\n"
    )
    tree = ast.parse(synthetic.read_text())
    offenses = _find_offending_calls(tree)
    assert offenses, "Detector failed to flag a deliberate violation — the gate is broken"
    assert offenses[0][0] == 3  # line number of the offending call
