#!/usr/bin/env bash
# e2e smoke test — 038 Change Management
# Usage: bash specs/038-change-management/manual/scripts/e2e_phase1.sh
# 재실행 가능 (idempotent). 기존 서버가 8000/5173에서 실행 중이면 그것을 사용.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../" && pwd)"
MANUAL_DIR="$REPO_ROOT/specs/038-change-management/manual"
SHOTS_DIR="$MANUAL_DIR/screenshots"
mkdir -p "$SHOTS_DIR"

BACK_URL="http://localhost:8000"
FRONT_URL="http://localhost:5173"

echo "=== Pre-flight ==="
curl -sf "$BACK_URL/api/requirement-changes/" -o /dev/null \
  && echo "Backend OK ($BACK_URL)" \
  || { echo "ERROR: Backend not running"; exit 1; }
curl -sf "$FRONT_URL" -o /dev/null \
  && echo "Frontend OK ($FRONT_URL)" \
  || { echo "ERROR: Frontend not running"; exit 1; }

echo ""
echo "=== Backend checks ==="

# 1. CHG 목록
curl -s "$BACK_URL/api/requirement-changes/" | \
  python3 -c "
import sys,json
d=json.load(sys.stdin)
items=d if isinstance(d,list) else []
print(f'총 RequirementChange: {len(items)}개')
for it in items[:5]:
    print(f\"  {it.get('id')} | {it.get('status')} | {it.get('title','')[:40]}\")
" | tee "$SHOTS_DIR/09_api_changes_list.txt"

# 2. CHG-012 상세
CHG_ID="CHG-012"
curl -s "$BACK_URL/api/requirement-changes/$CHG_ID" | \
  python3 -c "
import sys,json
d=json.load(sys.stdin)
print(f\"ID: {d.get('id')}, Status: {d.get('status')}\")
effects=d.get('effects',[]) or []
print(f'EFFECT 수: {len(effects)}')
" | tee "$SHOTS_DIR/10_api_chg012_detail.txt"

# 3. design-changes
curl -s "$BACK_URL/api/requirement-changes/$CHG_ID/design-changes" | \
  python3 -c "
import sys,json
d=json.load(sys.stdin)
print(f\"appliedCount={d.get('appliedCount')}, items={len(d.get('items',[]))}\")
" | tee "$SHOTS_DIR/11_api_design_changes.txt"

echo ""
echo "=== Playwright UI tests ==="
cd "$REPO_ROOT/frontend"
npx playwright test tests/playwright-038-changes.spec.ts --reporter=line

echo ""
echo "=== Done. Screenshots in $SHOTS_DIR ==="
ls "$SHOTS_DIR"/*.png | wc -l | xargs -I{} echo "{} PNG files captured"
