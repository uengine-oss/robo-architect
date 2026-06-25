#!/usr/bin/env bash
# 041 Constitution-driven Plan — 매뉴얼 스크린샷 재생성 (백엔드 모킹, 프론트만 필요)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
cd "$ROOT/frontend"
# Vite dev 서버가 5173에 떠 있어야 함 (없으면 기동)
if ! curl -sf http://localhost:5173 -o /dev/null; then
  (npm run dev >/tmp/vite-041.log 2>&1 &) ; until curl -sf http://localhost:5173 -o /dev/null; do sleep 1; done
fi
npx playwright test tests/manual-041-capture.spec.ts --reporter=line --workers=1
echo "screenshots → specs/041-constitution-driven-plan/manual/screenshots/"
