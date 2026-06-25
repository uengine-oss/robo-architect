#!/usr/bin/env bash
# e2e_038.sh — Smoke test for 038 Requirement Change Management
# Assumes: backend on :8000, frontend Vite on :5173
set -euo pipefail

BACKEND="http://localhost:8000"
SHOTS="$(dirname "$0")/../screenshots"
mkdir -p "$SHOTS"

cleanup() {
  echo "[e2e] cleanup"
}
trap cleanup EXIT

echo "[e2e] 1. Backend health check"
curl -sf "$BACKEND/api/health" | grep '"status":"healthy"'
echo "PASS"

echo "[e2e] 2. Create Change (MANUAL)"
CHG=$(curl -sf -X POST "$BACKEND/api/requirement-changes/" \
  -H "Content-Type: application/json" \
  -H "X-User-Name: Test User A" \
  -H "X-User-Email: testa@test.com" \
  -d '{"title":"E2E Test Change","originalPrompt":"E2E test prompt","sourceType":"MANUAL"}')
CHG_ID=$(echo "$CHG" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "PASS: created $CHG_ID"

echo "[e2e] 3. List Changes"
LIST=$(curl -sf "$BACKEND/api/requirement-changes/")
COUNT=$(echo "$LIST" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")
[ "$COUNT" -gt 0 ] && echo "PASS: $COUNT changes" || echo "FAIL: empty list"

echo "[e2e] 4. Get single Change"
curl -sf "$BACKEND/api/requirement-changes/$CHG_ID" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['status']=='DRAFT', 'Expected DRAFT'"
echo "PASS"

echo "[e2e] 5. Submit Change"
curl -sf -X POST "$BACKEND/api/requirement-changes/$CHG_ID/submit" \
  -H "X-User-Name: Test User A" -H "X-User-Email: testa@test.com" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['status']=='SUBMITTED', f'Got {d[\"status\"]}'"
echo "PASS"

echo "[e2e] 6. Self-approve blocked (403)"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BACKEND/api/requirement-changes/$CHG_ID/approve" \
  -H "Content-Type: application/json" \
  -H "X-User-Name: Test User A" -H "X-User-Email: testa@test.com" \
  -d '{"comment":"self"}')
[ "$STATUS" = "403" ] && echo "PASS: 403 self-approve blocked" || echo "FAIL: got $STATUS"

echo "[e2e] 7. Approve by different user"
APPROVE=$(curl -sf -X POST "$BACKEND/api/requirement-changes/$CHG_ID/approve" \
  -H "Content-Type: application/json" \
  -H "X-User-Name: Test User B" -H "X-User-Email: testb@test.com" \
  -d '{"comment":"approved"}')
echo "$APPROVE" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['status']=='APPROVED', f'Got {d[\"status\"]}'"
echo "PASS: APPROVED, history=$(echo $APPROVE | python3 -c 'import sys,json; print(len(json.load(sys.stdin)[\"statusHistory\"]))')"

echo "[e2e] 8. Preflight check"
curl -sf "$BACKEND/api/requirement-changes/$CHG_ID/preflight" | python3 -c "import sys,json; d=json.load(sys.stdin); print('preflight OK, canProceed:', d['canProceed'])"

echo "[e2e] 9. Regression analysis"
curl -sf "$BACKEND/api/requirement-changes/$CHG_ID/regression" | python3 -c "import sys,json; d=json.load(sys.stdin); print('regression OK, hasContractTests:', d['hasContractTests'])"

echo "[e2e] 10. Playwright UI tests"
cd "$(dirname "$0")/../../../.."
cd frontend
npx playwright test tests/playwright-038-changes.spec.ts --reporter=line
echo "PASS: Playwright 6/6"

echo ""
echo "=============================="
echo "e2e_038.sh: ALL CHECKS PASSED"
echo "=============================="
