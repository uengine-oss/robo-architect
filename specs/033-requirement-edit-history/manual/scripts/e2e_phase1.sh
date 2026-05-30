#!/usr/bin/env bash
# 033-requirement-edit-history — E2E Validation Script (Phase 1)
# Tests: PATCH /user-story/{id}, GET /user-story/{id}/history, identity headers
# Idempotent: kills prior listeners, regenerates artifacts, traps on exit.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../../.." && pwd)"
SPEC_DIR="$REPO_ROOT/specs/033-requirement-edit-history"
MANUAL_DIR="$SPEC_DIR/manual"
SHOTS_DIR="$MANUAL_DIR/screenshots"
ARTIFACTS_DIR="$MANUAL_DIR/artifacts"
PORT="${E2E_PORT:-8765}"
VENV="$REPO_ROOT/.venv"
PYTHON="$VENV/bin/python"
UVICORN="$VENV/bin/uvicorn"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

cleanup() {
  if [[ -n "${UVICORN_PID:-}" ]]; then
    kill "$UVICORN_PID" 2>/dev/null || true
    wait "$UVICORN_PID" 2>/dev/null || true
  fi
  lsof -ti:"$PORT" 2>/dev/null | xargs kill -9 2>/dev/null || true
}
trap cleanup EXIT

# ── 0. Pre-flight ────────────────────────────────────────────────────────────
echo "[0] Pre-flight checks..."
command -v curl >/dev/null || { echo "ERROR: curl missing"; exit 1; }
command -v jq   >/dev/null || { echo "ERROR: jq missing"; exit 1; }
[[ -x "$PYTHON" ]]        || { echo "ERROR: venv not found at $VENV"; exit 1; }

# Kill anything already on the port
lsof -ti:"$PORT" 2>/dev/null | xargs kill -9 2>/dev/null || true
sleep 0.5

# ── 1. Boot backend ──────────────────────────────────────────────────────────
echo "[1] Starting backend on port $PORT..."
cd "$REPO_ROOT"
PYTHONPATH="$REPO_ROOT" \
  "$UVICORN" api.main:app \
  --host 127.0.0.1 --port "$PORT" \
  --log-level warning \
  > "$ARTIFACTS_DIR/uvicorn.log" 2>&1 &
UVICORN_PID=$!

# Wait for readiness (poll /openapi.json)
for i in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:$PORT/openapi.json" -o /dev/null 2>/dev/null; then
    echo "  Backend ready (attempt $i)"
    break
  fi
  sleep 1
done
curl -sf "http://127.0.0.1:$PORT/openapi.json" -o /dev/null || { echo "ERROR: backend failed to start"; cat "$ARTIFACTS_DIR/uvicorn.log"; exit 1; }

# ── 2. Check A — OpenAPI route registration ───────────────────────────────────
echo "[2] Check A: OpenAPI route registration for /user-story/{id} routes..."
curl -s "http://127.0.0.1:$PORT/openapi.json" | \
  jq '[.paths | to_entries[] | select(.key | test("/requirements/user-story/")) | .key]' \
  > "$SHOTS_DIR/01_openapi_routes.txt"
cat "$SHOTS_DIR/01_openapi_routes.txt"

# ── 3. Check B — PATCH endpoint exists ───────────────────────────────────────
echo "[3] Check B: PATCH /api/requirements/user-story/{id} returns 404 for unknown ID (not 405)..."
HTTP_CODE=$(curl -s -o "$SHOTS_DIR/02_patch_unknown.txt" -w "%{http_code}" \
  -X PATCH "http://127.0.0.1:$PORT/api/requirements/user-story/nonexistent-id-000" \
  -H "Content-Type: application/json" \
  -H "X-User-Name: Test%20User" \
  -H "X-User-Email: test@example.com" \
  -d '{"action": "test action"}')
echo "  HTTP status: $HTTP_CODE"
echo "HTTP $HTTP_CODE" >> "$SHOTS_DIR/02_patch_unknown.txt"

# ── 4. Check C — History endpoint exists ─────────────────────────────────────
echo "[4] Check C: GET /api/requirements/user-story/{id}/history returns 200 with items array..."
curl -s "http://127.0.0.1:$PORT/api/requirements/user-story/nonexistent-id-000/history" \
  > "$SHOTS_DIR/03_history_endpoint.txt"
cat "$SHOTS_DIR/03_history_endpoint.txt"

# ── 5. Check D — Swagger UI screenshot ───────────────────────────────────────
echo "[5] Check D: Swagger UI screenshot..."
"$CHROME" \
  --headless --disable-gpu --no-sandbox --hide-scrollbars \
  --window-size=1400,3000 \
  --screenshot="$SHOTS_DIR/04_swagger_ui.png" \
  "http://127.0.0.1:$PORT/docs#/requirements" \
  2>/dev/null || echo "  WARNING: Chrome screenshot failed (non-fatal)"

# ── 6. Check E — Real edit + history (if Neo4j available) ────────────────────
echo "[6] Check E: Attempt real PATCH + history with identity headers..."
# Try to get first user story from tree
TREE_RESP=$(curl -s "http://127.0.0.1:$PORT/api/requirements/tree")
US_ID=$(echo "$TREE_RESP" | jq -r '
  (.epics[]?.features[]?.userStories[]?.id,
   .epics[]?.unassignedFeature?.userStories[]?.id,
   .unassigned[]?.id)
  | select(. != null)
  ' | head -1)

if [[ -n "$US_ID" && "$US_ID" != "null" ]]; then
  echo "  Found UserStory id: $US_ID"
  # PATCH with identity headers
  PATCH_RESP=$(curl -s -X PATCH \
    "http://127.0.0.1:$PORT/api/requirements/user-story/$US_ID" \
    -H "Content-Type: application/json" \
    -H "X-User-Name: E2E%20Test%20User" \
    -H "X-User-Email: e2e@test.com" \
    -d '{"action":"E2E 테스트 편집"}')
  echo "$PATCH_RESP" | jq . > "$SHOTS_DIR/05_patch_real.txt" 2>/dev/null || echo "$PATCH_RESP" > "$SHOTS_DIR/05_patch_real.txt"

  # GET history
  HISTORY_RESP=$(curl -s \
    "http://127.0.0.1:$PORT/api/requirements/user-story/$US_ID/history")
  echo "$HISTORY_RESP" | jq . > "$SHOTS_DIR/06_history_real.txt" 2>/dev/null || echo "$HISTORY_RESP" > "$SHOTS_DIR/06_history_real.txt"
  echo "  PATCH + history captured"
else
  echo "  No UserStory found (Neo4j empty) — skipping live edit test"
  echo "SKIPPED: no UserStory data in Neo4j" > "$SHOTS_DIR/05_patch_real.txt"
  echo "SKIPPED: no UserStory data in Neo4j" > "$SHOTS_DIR/06_history_real.txt"
fi

# ── 7. Save OpenAPI JSON ─────────────────────────────────────────────────────
curl -s "http://127.0.0.1:$PORT/openapi.json" > "$ARTIFACTS_DIR/openapi.json"

echo ""
echo "✓ All checks complete. Artifacts in: $MANUAL_DIR"
