#!/usr/bin/env bash
# E2E for 035 DDD discovery & canvases — boots worktree backend + vite, runs
# Playwright UI screenshots + backend curl evidence. Idempotent; cleans up.
set -uo pipefail

WT="/Users/uengine/main-robo-arch/robo-architect-035"
MANUAL="$WT/specs/035-ddd-discovery-canvases/manual"
BE_PORT="${E2E_PORT:-8770}"
FE_PORT="${E2E_FRONT_PORT:-5180}"
SHOTS="$MANUAL/screenshots"
ART="$MANUAL/artifacts"

mkdir -p "$SHOTS" "$ART"

BE_PID=""
FE_PID=""
PROXY_PATCHED=0

cleanup() {
  echo "── cleanup ──"
  [ -n "$FE_PID" ] && kill "$FE_PID" 2>/dev/null
  [ -n "$BE_PID" ] && kill "$BE_PID" 2>/dev/null
  pkill -f "uvicorn api.main:app.*$BE_PORT" 2>/dev/null
  pkill -f "vite.*$FE_PORT" 2>/dev/null
  # revert proxy patch
  if [ "$PROXY_PATCHED" = "1" ]; then
    sed -i '' "s#target: 'http://127.0.0.1:$BE_PORT'#target: 'http://127.0.0.1:8000'#" "$WT/frontend/vite.config.js"
  fi
}
trap cleanup EXIT

cd "$WT"

# kill prior listeners on our ports
pkill -f "uvicorn api.main:app.*$BE_PORT" 2>/dev/null
pkill -f "vite.*$FE_PORT" 2>/dev/null
sleep 1

echo "── boot backend on $BE_PORT ──"
uv run uvicorn api.main:app --host 127.0.0.1 --port "$BE_PORT" > "$ART/uvicorn.log" 2>&1 &
BE_PID=$!
until curl -sf "http://127.0.0.1:$BE_PORT/docs" -o /dev/null; do
  sleep 1
  kill -0 "$BE_PID" 2>/dev/null || { echo "backend died"; tail -20 "$ART/uvicorn.log"; exit 1; }
done
echo "backend up"
curl -s "http://127.0.0.1:$BE_PORT/openapi.json" -o "$ART/openapi.json"

echo "── patch vite proxy → $BE_PORT ──"
sed -i '' "s#target: 'http://127.0.0.1:8000'#target: 'http://127.0.0.1:$BE_PORT'#" "$WT/frontend/vite.config.js"
PROXY_PATCHED=1

echo "── boot vite on $FE_PORT ──"
cd "$WT/frontend"
npx vite --port "$FE_PORT" --strictPort > "$ART/vite.log" 2>&1 &
FE_PID=$!
until curl -sf "http://127.0.0.1:$FE_PORT" -o /dev/null; do
  sleep 1
  kill -0 "$FE_PID" 2>/dev/null || { echo "vite died"; tail -30 "$ART/vite.log"; exit 1; }
done
echo "vite up"
sleep 3

echo "── playwright ──"
cd "$ART"
APP_URL="http://localhost:$FE_PORT" npx playwright test playwright-ddd-canvases.spec.ts \
  --config playwright.config.ts --reporter=line 2>&1 | tee "$ART/playwright.out"

echo "── backend curl evidence ──"
B="http://127.0.0.1:$BE_PORT"
# 05 wizard start
curl -s -X POST "$B/api/requirements/ddd-wizard/start" -H 'Content-Type: application/json' \
  -d '{"scope":"greenfield","profile":{"projectType":"greenfield","dddExperience":"first_time","teamSize":"small","existingArtifacts":[]}}' \
  | jq '{sessionId, plan:[.recommendedPlan[].key], profileSummary}' > "$SHOTS/05_wizard_start.txt" 2>&1

# 06 classification generic + canvas (pick first BC if any)
BCID=$(curl -s "$B/api/requirements/tree" | jq -r '.epics[0].id // empty')
{
  echo "# 전략 분류(generic) + BC 캔버스 검증"
  if [ -n "$BCID" ]; then
    echo "## PATCH classification=generic"
    curl -s -X PATCH "$B/api/contexts/$BCID/classification" -H 'Content-Type: application/json' \
      -d '{"classification":"generic"}' | jq .
    echo "## GET bounded-context canvas"
    curl -s "$B/api/requirements/bounded-context/$BCID/canvas" | jq '{name, classification, version, ubiquitousLanguage}'
  else
    echo "(그래프에 BoundedContext가 없어 생략 — 마법사로 먼저 생성 필요)"
  fi
} > "$SHOTS/06_classification_canvas.txt" 2>&1

# 07 ddd-export
curl -s -X POST "$B/api/requirements/ddd-export" -H 'Content-Type: application/json' \
  -d '{"outputDir":"/tmp/ddd_export_manual"}' | jq '{written:(.writtenFiles|length), files:.writtenFiles[0:5]}' \
  > "$SHOTS/07_ddd_export.txt" 2>&1
rm -rf /tmp/ddd_export_manual

# 08 pivotal 404 (no event)
echo "# 없는 이벤트 토글 → 404 기대" > "$SHOTS/08_pivotal_404.txt"
curl -s -o /dev/null -w "HTTP %{http_code}\n" -X POST "$B/api/requirements/pivotal-events/toggle" \
  -H 'Content-Type: application/json' -d '{"eventId":"__nope__","pivotal":true}' >> "$SHOTS/08_pivotal_404.txt"

echo "── done ──"
ls -la "$SHOTS"
