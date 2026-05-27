#!/usr/bin/env bash
#
# check_robo_spec_install.sh — feature 029 T019
#
# Verifies that a workspace's .claude/skills/ subtree is a byte-identical
# copy of <repo>/robo-spec/.claude/skills/ (FR-012 / SC-006), and that no
# Jinja template markers leaked into the source. Used in CI and by smoke
# scenario quickstart S1.
#
# Usage:
#   ./scripts/check_robo_spec_install.sh <target-workspace>
#
# Exits 0 on success; non-zero with a diagnostic on any check failure.

set -euo pipefail

if [[ "${1:-}" == "" ]]; then
    cat >&2 <<'EOF'
usage: check_robo_spec_install.sh <target-workspace>

Validates that <target-workspace>/.claude/skills/ matches
<repo>/robo-spec/.claude/skills/ byte-for-byte, and that the source tree
contains no Jinja markers (FR-012 / SC-006).
EOF
    exit 2
fi

target="$1"
if [[ ! -d "$target" ]]; then
    echo "error: target workspace does not exist: $target" >&2
    exit 1
fi

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
src_skills="${repo_root}/robo-spec/.claude/skills"
target_skills="${target}/.claude/skills"

if [[ ! -d "$src_skills" ]]; then
    echo "error: source not found: $src_skills" >&2
    exit 1
fi
if [[ ! -d "$target_skills" ]]; then
    echo "error: target skills not installed: $target_skills" >&2
    echo "       run setup-project against this workspace first." >&2
    exit 1
fi

# (1) Byte-identical install — verbatim copy guarantee.
echo "[check 1/3] diff -r $src_skills $target_skills"
if ! diff -r "$src_skills" "$target_skills" >/dev/null; then
    echo "FAIL: installed skills/ differs from source. Re-run setup-project." >&2
    diff -r "$src_skills" "$target_skills" >&2 || true
    exit 1
fi
echo "  ok — installed tree is byte-identical to source"

# (2) No Jinja markers in the source (would break FR-012's verbatim guarantee).
echo "[check 2/3] grep for Jinja markers under $src_skills"
if grep -rIlE '\{\{|\{%' "$src_skills" >&2; then
    echo "FAIL: Jinja control tokens found in robo-spec/ source. " \
         "FR-012 requires verbatim copy with no template substitution." >&2
    exit 1
fi
echo "  ok — no Jinja markers in source"

# (3) No marker comments in any developer source the workspace already
# scaffolded (research R7 — /robo-implement must never write `@robo`
# comments into source). Scoped to common source directories to avoid
# false positives in docs or vendored content.
echo "[check 3/3] grep '@robo:' in workspace source (R7 enforcement)"
hits=0
for src_dir in "${target}/src" "${target}/api" "${target}/app" "${target}/lib"; do
    if [[ -d "$src_dir" ]]; then
        if grep -rIn '@robo:' "$src_dir" 2>/dev/null; then
            hits=$((hits + 1))
        fi
    fi
done
if [[ $hits -gt 0 ]]; then
    echo "FAIL: found @robo: markers in workspace source. Research R7 forbids " \
         "marker comments in developer code; /robo-sync uses full AST extraction." >&2
    exit 1
fi
echo "  ok — no @robo: markers in workspace source"

echo
echo "PASS: robo-spec install at $target is byte-identical and marker-free."
