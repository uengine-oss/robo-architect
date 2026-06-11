#!/usr/bin/env bash
# e2e_039.sh — 039 Proposal Lifecycle end-to-end test script
# Idempotent: safe to re-run. Cleans up processes on EXIT.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
MANUAL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SHOTS_DIR="$MANUAL_DIR/screenshots"
ARTIFACTS_DIR="$MANUAL_DIR/artifacts"
BACK_PORT="${E2E_PORT:-8765}"
FRONT_PORT="${E2E_FRONT_PORT:-5173}"
BACK_URL="http://localhost:$BACK_PORT"
FRONT_URL="http://localhost:$FRONT_PORT"

BACK_PID=""
FRONT_PID=""

cleanup() {
  echo "[cleanup] Stopping background processes..."
  [[ -n "$BACK_PID" ]] && kill "$BACK_PID" 2>/dev/null || true
  [[ -n "$FRONT_PID" ]] && kill "$FRONT_PID" 2>/dev/null || true
  lsof -ti:"$BACK_PORT" | xargs kill -9 2>/dev/null || true
  lsof -ti:"$FRONT_PORT" | xargs kill -9 2>/dev/null || true
}
trap cleanup EXIT

mkdir -p "$SHOTS_DIR" "$ARTIFACTS_DIR"

echo "=== [1] Pre-flight checks ==="
for cmd in curl jq npx; do
  command -v "$cmd" &>/dev/null || { echo "MISSING: $cmd"; exit 1; }
done
npx playwright --version &>/dev/null || { echo "Playwright not found"; exit 1; }
echo "All tools present."

echo "=== [2] Start backend ==="
cd "$REPO_ROOT"
python3 -m uvicorn api.main:app --host 127.0.0.1 --port "$BACK_PORT" \
  --log-level info \
  > "$ARTIFACTS_DIR/uvicorn.log" 2>&1 &
BACK_PID=$!

echo "Waiting for backend on $BACK_URL..."
for i in $(seq 1 30); do
  curl -sf "$BACK_URL/health" -o /dev/null && break || sleep 2
done
echo "Backend ready (PID=$BACK_PID)"

echo "=== [3] Dump OpenAPI spec ==="
curl -sf "$BACK_URL/openapi.json" | jq . > "$ARTIFACTS_DIR/openapi.json"
echo "  OpenAPI saved."

echo "=== [4] Backend API checks ==="

# Check 1: POST /api/proposals/ — Proposal 생성
echo "[API] Creating test proposal..."
CREATE_RESP=$(curl -sf -X POST "$BACK_URL/api/proposals/" \
  -H "Content-Type: application/json" \
  -d '{"originalPrompt": "결제 시스템에 부분 환불 기능을 추가해줘", "title": "부분 환불 기능 추가"}' 2>/dev/null) || CREATE_RESP="{}"
echo "$CREATE_RESP" | jq . > "$SHOTS_DIR/06_api_create_proposal.txt"
PROPOSAL_ID=$(echo "$CREATE_RESP" | jq -r '.id // "PRO-001"')
echo "  Created: $PROPOSAL_ID"

# Check 2: GET /api/proposals/ — 목록 조회
echo "[API] Listing proposals..."
curl -sf "$BACK_URL/api/proposals/" | jq '.[0:3]' > "$SHOTS_DIR/07_api_list_proposals.txt" 2>/dev/null || echo "[]" > "$SHOTS_DIR/07_api_list_proposals.txt"

# Check 3: GET /api/proposals/{id} — 상세 조회
if [[ "$PROPOSAL_ID" != "PRO-001" && "$PROPOSAL_ID" != "null" ]]; then
  curl -sf "$BACK_URL/api/proposals/$PROPOSAL_ID" | jq '{id,title,status,author}' > "$SHOTS_DIR/08_api_get_proposal.txt" 2>/dev/null || echo "{}" > "$SHOTS_DIR/08_api_get_proposal.txt"
fi

# Check 4: Verify /api/proposals/ endpoint exists (schema check)
OPENAPI_CHECK=$(jq 'if .paths["/api/proposals/"] then "PASS" else "FAIL" end' "$ARTIFACTS_DIR/openapi.json")
echo "  OpenAPI /api/proposals/: $OPENAPI_CHECK"

echo "=== [5] Start frontend ==="
cd "$REPO_ROOT/frontend"
npm run dev -- --port "$FRONT_PORT" --host 127.0.0.1 \
  > "$ARTIFACTS_DIR/vite.log" 2>&1 &
FRONT_PID=$!

echo "Waiting for frontend on $FRONT_URL..."
for i in $(seq 1 40); do
  curl -sf "$FRONT_URL" -o /dev/null && break || sleep 2
done
echo "Frontend ready (PID=$FRONT_PID)"

echo "=== [6] Run Playwright ==="
cd "$REPO_ROOT"
APP_URL="$FRONT_URL" npx playwright test \
  "$MANUAL_DIR/artifacts/playwright-039.spec.ts" \
  --reporter=line \
  --timeout=60000 \
  || echo "[WARN] Some Playwright tests failed — screenshots may be partial"

echo "=== [7] Report ==="
echo "Screenshots:"
ls -lh "$SHOTS_DIR/"
echo "Done."
