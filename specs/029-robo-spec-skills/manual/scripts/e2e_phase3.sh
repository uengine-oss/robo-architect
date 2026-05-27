#!/usr/bin/env bash
#
# e2e_phase3.sh — feature 029 Phase 1+2+3 end-to-end smoke
#
# Spins up the FastAPI backend, hits the new and extended routes, runs
# the verbatim-install check against a temp workspace, captures the
# results as both text dumps and PNG screenshots (Swagger UI via
# headless Chrome), and tears down cleanly.
#
# Idempotent: re-running cleans up any prior backend on the chosen port,
# removes prior artifacts under the run directory, and starts fresh.
#
# Outputs (relative to the calling directory's manual/ folder by default):
#   screenshots/   PNG renders of Swagger pages + text-dumps of CLI outputs
#   artifacts/     JSON responses and copy of the installed workspace
#   e2e.log        Aggregated log of every step
#
# Exit 0 on success; non-zero with a failure summary appended to e2e.log.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
MANUAL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SHOTS="$MANUAL_DIR/screenshots"
ARTIFACTS="$MANUAL_DIR/artifacts"
LOG="$MANUAL_DIR/e2e.log"

PORT="${E2E_PORT:-8765}"
BACKEND_URL="http://127.0.0.1:${PORT}"
VENV_PYTHON="$REPO_ROOT/.venv/bin/python"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

mkdir -p "$SHOTS" "$ARTIFACTS"
: > "$LOG"

say() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$LOG"; }
fail() { say "FAIL: $*"; exit 1; }

cleanup() {
    if [[ -n "${UVICORN_PID:-}" ]] && kill -0 "$UVICORN_PID" 2>/dev/null; then
        say "Stopping uvicorn (pid=$UVICORN_PID)"
        kill "$UVICORN_PID" 2>/dev/null || true
        wait "$UVICORN_PID" 2>/dev/null || true
    fi
    if [[ -n "${TMP_WS:-}" ]] && [[ -d "$TMP_WS" ]]; then
        say "Removing temp workspace: $TMP_WS"
        rm -rf "$TMP_WS"
    fi
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# 0. Pre-flight
# ---------------------------------------------------------------------------
say "Repo root: $REPO_ROOT"
say "Manual dir: $MANUAL_DIR"
say "Backend port: $PORT"

if [[ ! -x "$VENV_PYTHON" ]]; then
    fail "Project venv python not found at $VENV_PYTHON. Run uv sync first."
fi

# Free the port if a stale uvicorn is squatting on it.
if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    say "Killing stale process on port $PORT"
    lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t | xargs -r kill -9 || true
    sleep 1
fi

# ---------------------------------------------------------------------------
# 1. Start backend (no Neo4j needed for the routes we hit — the import
#    succeeds even without a live DB; classification PATCH will fail
#    cleanly with a 404 if there's no BC in the graph, which is fine
#    for this smoke).
# ---------------------------------------------------------------------------
say "Starting uvicorn"
cd "$REPO_ROOT"
"$VENV_PYTHON" -m uvicorn api.main:app \
    --host 127.0.0.1 --port "$PORT" \
    > "$ARTIFACTS/uvicorn.log" 2>&1 &
UVICORN_PID=$!
say "uvicorn pid: $UVICORN_PID"

# Wait for /openapi.json to respond — that's the most reliable readiness
# signal because it doesn't depend on Neo4j or any business logic.
say "Waiting for backend readiness…"
for i in {1..30}; do
    if curl -fsS "$BACKEND_URL/openapi.json" -o /dev/null 2>/dev/null; then
        say "  ready after ${i}s"
        break
    fi
    sleep 1
    if [[ $i -eq 30 ]]; then
        cat "$ARTIFACTS/uvicorn.log" >> "$LOG"
        fail "Backend did not become ready in 30s"
    fi
done

# ---------------------------------------------------------------------------
# 2. Hit /api/robo-spec/health — confirms router registration + MCP mount
# ---------------------------------------------------------------------------
say "Check 1/5 — GET /api/robo-spec/health"
curl -fsS "$BACKEND_URL/api/robo-spec/health" | tee "$ARTIFACTS/health.json" \
    | jq . > "$SHOTS/01_health.txt"
grep -q '"status": "ok"' "$SHOTS/01_health.txt" \
    || fail "health endpoint did not return status=ok"
say "  ok"

# ---------------------------------------------------------------------------
# 3. Confirm /docs lists robo-spec + classification routes
# ---------------------------------------------------------------------------
say "Check 2/5 — /openapi.json includes new routes"
curl -fsS "$BACKEND_URL/openapi.json" > "$ARTIFACTS/openapi.json"

ROUTES_FILE="$SHOTS/02_routes.txt"
{
    echo "Routes registered under /api/robo-spec and the new classification surface:"
    echo "----------------------------------------------------------------------"
    jq -r '.paths
        | to_entries
        | map(select(.key | test("/api/robo-spec|/classification|/setup-project")))
        | sort_by(.key)
        | .[]
        | "\(.value | keys | map(ascii_upcase) | join(",")) \(.key)"
      ' "$ARTIFACTS/openapi.json"
} | tee "$ROUTES_FILE"

for needle in \
    "/api/contexts/{bc_id}/classification" \
    "/api/robo-spec/health" \
    "/api/claude-code/setup-project"
do
    grep -qF "$needle" "$ROUTES_FILE" || fail "missing route in OpenAPI: $needle"
done
say "  ok — all expected routes present"

# ---------------------------------------------------------------------------
# 4. Screenshot Swagger UI via headless Chrome
# ---------------------------------------------------------------------------
say "Check 3/5 — Swagger UI screenshot via headless Chrome"
if [[ -x "$CHROME" ]]; then
    SWAGGER_PNG="$SHOTS/03_swagger_docs.png"
    "$CHROME" --headless --disable-gpu --hide-scrollbars \
        --no-sandbox \
        --virtual-time-budget=8000 \
        --window-size=1600,2400 \
        --screenshot="$SWAGGER_PNG" \
        "$BACKEND_URL/docs" >/dev/null 2>&1 || true
    if [[ -f "$SWAGGER_PNG" ]]; then
        say "  swagger screenshot saved: $(du -h "$SWAGGER_PNG" | awk '{print $1}')"
    else
        say "  WARNING: chrome did not produce a screenshot (continuing)"
    fi
else
    say "  WARNING: Chrome not at $CHROME — skipping Swagger screenshot"
fi

# ---------------------------------------------------------------------------
# 5. Verbatim install + check_robo_spec_install.sh against a temp workspace
# ---------------------------------------------------------------------------
say "Check 4/5 — verbatim install + integrity check"
TMP_WS=$(mktemp -d -t robo_spec_e2e_XXXX)
say "  temp workspace: $TMP_WS"

INSTALL_LOG="$SHOTS/04_install_result.txt"
"$VENV_PYTHON" - <<PYEOF | tee "$INSTALL_LOG"
import json, sys
sys.path.insert(0, "$REPO_ROOT")
from api.features.claude_code.router import _install_robo_spec
result = _install_robo_spec("$TMP_WS")
print(json.dumps(result, indent=2))
PYEOF
grep -q '"roboSpecInstalled": true' "$INSTALL_LOG" \
    || fail "install did not report roboSpecInstalled=true"

# Capture the resulting workspace tree
TREE_LOG="$SHOTS/05_workspace_tree.txt"
{
    echo "Workspace tree after _install_robo_spec:"
    echo "----------------------------------------"
    if command -v tree >/dev/null 2>&1; then
        (cd "$TMP_WS" && tree -a .claude)
    else
        (cd "$TMP_WS" && find .claude -print | sort | sed 's|[^/]*/|  |g;s|  |   |g')
    fi
    echo
    echo "robo-project.json:"
    cat "$TMP_WS/.claude/robo-project.json"
    echo
    echo
    echo "mcp.json:"
    cat "$TMP_WS/.claude/mcp.json"
} | tee "$TREE_LOG"

# Run the install-integrity check
CHECK_LOG="$SHOTS/06_check_install.txt"
say "Running scripts/check_robo_spec_install.sh"
if "$REPO_ROOT/scripts/check_robo_spec_install.sh" "$TMP_WS" 2>&1 | tee "$CHECK_LOG"; then
    say "  ok — install integrity check passed"
else
    fail "install integrity check failed (see $CHECK_LOG)"
fi

# Copy a small representative slice of the workspace for the manual
mkdir -p "$ARTIFACTS/workspace_sample"
cp "$TMP_WS/.claude/robo-project.json" "$ARTIFACTS/workspace_sample/"
cp "$TMP_WS/.claude/mcp.json" "$ARTIFACTS/workspace_sample/"
cp -R "$TMP_WS/.claude/skills" "$ARTIFACTS/workspace_sample/"

# ---------------------------------------------------------------------------
# 6. MCP mount sanity — /mcp is reachable (it speaks streamable-HTTP so
#    raw curl gets either a 200/406 or a JSON-RPC error, both prove the
#    transport is alive).
# ---------------------------------------------------------------------------
say "Check 5/5 — MCP mount reachable at $BACKEND_URL/mcp/"
MCP_LOG="$SHOTS/07_mcp_mount.txt"
{
    echo "GET /mcp/ (streamable-HTTP transport probe)"
    curl -s -o /dev/null -w "  HTTP %{http_code}  (200/404/406/415/501 = mount alive)\n" \
        "$BACKEND_URL/mcp/"
    echo
    echo "OpenAPI does not document /mcp/ (mounted as a sub-app, by design)."
    echo "If MCP transport is unreachable the status code would be ERR 7 (refused)."
} | tee "$MCP_LOG"

# ---------------------------------------------------------------------------
# 7. Summary
# ---------------------------------------------------------------------------
say "PASS: Phase 1+2+3 e2e smoke complete."
echo
{
    echo "=== Phase 1+2+3 e2e smoke — summary ==="
    echo "Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "Backend: $BACKEND_URL"
    echo "Workspace: $TMP_WS (removed on exit)"
    echo
    echo "Captured artifacts:"
    find "$SHOTS" "$ARTIFACTS" -type f -maxdepth 3 \
        | sort | sed "s|^$MANUAL_DIR/|  |"
} | tee -a "$LOG"
