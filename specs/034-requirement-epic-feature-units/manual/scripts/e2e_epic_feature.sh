#!/usr/bin/env bash
# E2E smoke + evidence capture for 034 (Epic/Feature 등록·뷰·편집·radar).
# Reuses an already-running backend (8000, --reload, has the new endpoints)
# and Neo4j (7687). Starts a FRESH Vite on 5199 to guarantee current frontend
# code, runs Playwright (UI screenshots), captures backend text evidence,
# then cleans up the demo nodes it created.
#
# Idempotent: re-runnable. Epic/Feature MERGE on natural keys → no duplicates.
set -uo pipefail

REPO="/Users/uengine/main-robo-arch/robo-architect"
MANUAL="$REPO/specs/034-requirement-epic-feature-units/manual"
SHOTS="$MANUAL/screenshots"
ART="$MANUAL/artifacts"
BACK="http://localhost:8000"
FRONT_PORT="${E2E_FRONT_PORT:-5199}"
APP="http://localhost:${FRONT_PORT}"
VITE_PID=""

mkdir -p "$SHOTS" "$ART"

cleanup() {
  echo "── teardown ──"
  # Kill the vite we started (npm spawns a child — kill the whole group via port).
  lsof -nP -iTCP:"$FRONT_PORT" -sTCP:LISTEN -t 2>/dev/null | xargs -r kill 2>/dev/null && echo "killed vite on :$FRONT_PORT"
  # Remove demo FEATURES via the public DELETE endpoint (works with the running
  # backend's own DB connection — no separate credentials needed).
  for fid in $(curl -sf -m 5 "$BACK/api/requirements/tree" \
      | jq -r '.epics[] | select(.name|test("E2E")) | .features[].id' 2>/dev/null); do
    curl -s -m 8 -o /dev/null -X DELETE "$BACK/api/requirements/feature" \
      -H 'Content-Type: application/json' -d "{\"featureId\":\"$fid\",\"userStoryDisposition\":\"delete\"}"
  done
  echo "demo features deleted via API"
  # NOTE: demo Epics (BoundedContext 'E2E*') cannot be removed here — there is
  # no BC-delete endpoint, and direct Neo4j access needs the backend's own
  # credentials. Remove them via Neo4j Browser if desired:
  #   MATCH (bc:BoundedContext) WHERE bc.name CONTAINS 'E2E' DETACH DELETE bc
}
trap cleanup EXIT

echo "── pre-flight ──"
curl -sf -m 5 "$BACK/api/requirements/tree" -o /dev/null && echo "backend 8000: OK" || { echo "backend 8000 not responding — start it first"; exit 1; }
curl -sf -m 5 "$BACK/openapi.json" | jq -e '.paths["/api/requirements/bounded-context"].post and .paths["/api/requirements/feature"].patch' >/dev/null \
  && echo "new endpoints present: OK" || { echo "running backend lacks new endpoints"; exit 1; }
curl -sf -m 5 "$BACK/openapi.json" -o "$ART/openapi.json" && echo "saved openapi.json"

echo "── boot fresh frontend on :$FRONT_PORT ──"
( cd "$REPO/frontend" && npm run dev -- --port "$FRONT_PORT" --strictPort >"$ART/vite.log" 2>&1 ) &
VITE_PID=$!
for i in $(seq 1 60); do curl -sf -m 2 "$APP" -o /dev/null && break; sleep 1; done
curl -sf -m 3 "$APP" -o /dev/null && echo "frontend $APP: OK" || { echo "vite failed; see $ART/vite.log"; exit 1; }

echo "── Playwright UI capture ──"
( cd "$REPO/frontend" && APP_URL="$APP" NODE_PATH="$REPO/frontend/node_modules" \
    npx playwright test --config "$ART/playwright.config.ts" ) \
  && echo "playwright: PASS" || echo "playwright: completed with failures (see output)"

echo "── backend text evidence (curl) ──"
# 16 — Create Epic via API
EPIC_JSON=$(curl -sf -m 8 -X POST "$BACK/api/requirements/bounded-context" \
  -H 'Content-Type: application/json' -d '{"name":"E2E-API 검증 Epic","description":"API 검증용"}')
{ echo "# POST /api/requirements/bounded-context"; echo "$EPIC_JSON" | jq .; } > "$SHOTS/16_api_create_epic.txt"
BC_ID=$(echo "$EPIC_JSON" | jq -r '.boundedContext.id')

# Create a feature under it (reused endpoint), then PATCH it
FEAT_JSON=$(curl -sf -m 8 -X POST "$BACK/api/requirements/feature" \
  -H 'Content-Type: application/json' -d "{\"boundedContextId\":\"$BC_ID\",\"name\":\"E2E 검증 Feature\"}")
FID=$(echo "$FEAT_JSON" | jq -r '.feature.id')
{ echo "# PATCH /api/requirements/feature  (rename → 200)";
  curl -s -m 8 -o /dev/null -w "HTTP %{http_code}\n" -X PATCH "$BACK/api/requirements/feature" \
    -H 'Content-Type: application/json' -d "{\"featureId\":\"$FID\",\"name\":\"E2E 검증 Feature (수정됨)\"}";
  echo; echo "# PATCH 결과 본문:";
  curl -s -m 8 -X PATCH "$BACK/api/requirements/feature" -H 'Content-Type: application/json' \
    -d "{\"featureId\":\"$FID\",\"description\":\"설명 추가\"}" | jq .;
} > "$SHOTS/17_api_patch_feature_ok.txt"

# 18 — validation: blank name → 422, missing id → 404
{ echo "# PATCH /feature  빈 이름 → 422";
  curl -s -m 8 -o /dev/null -w "HTTP %{http_code}\n" -X PATCH "$BACK/api/requirements/feature" \
    -H 'Content-Type: application/json' -d "{\"featureId\":\"$FID\",\"name\":\"   \"}";
  echo "# PATCH /feature  없는 id → 404";
  curl -s -m 8 -o /dev/null -w "HTTP %{http_code}\n" -X PATCH "$BACK/api/requirements/feature" \
    -H 'Content-Type: application/json' -d '{"featureId":"does-not-exist","name":"x"}';
  echo "# PATCH /bounded-context  빈 이름 → 422";
  curl -s -m 8 -o /dev/null -w "HTTP %{http_code}\n" -X PATCH "$BACK/api/requirements/bounded-context" \
    -H 'Content-Type: application/json' -d "{\"boundedContextId\":\"$BC_ID\",\"name\":\"\"}";
} > "$SHOTS/18_api_validation.txt"

# 19 — tree summary
curl -sf -m 8 "$BACK/api/requirements/tree" | jq '{epics:[.epics[].name], featureCount:[.epics[].features|length]|add}' > "$SHOTS/19_api_tree.txt"

# 20 — local tooling (US5 claude-ide engine install check)
{ echo "# GET /api/requirements/local-tooling/status (Claude IDE 엔진 설치 점검)";
  curl -sf -m 8 "$BACK/api/requirements/local-tooling/status" | jq .; } > "$SHOTS/20_api_local_tooling.txt"

# 21 — pending-design (US7 미반영 설계 식별)
{ echo "# GET /api/requirements/user-stories/pending-design (설계 미반영 US)";
  curl -sf -m 8 "$BACK/api/requirements/user-stories/pending-design" \
    | jq '{pendingCount:(.pending|length), sample:[.pending[0:3][]|.action]}'; } > "$SHOTS/21_api_pending_design.txt"

echo "── done. screenshots: $SHOTS ──"
ls -1 "$SHOTS"
