#!/usr/bin/env bash
# init-env.sh — .env 를 처음 만든다. **다시 돌려도 안전하다** — 이미 채운 값은 안 건드린다.
#
#   bash init-env.sh
#   (Windows PowerShell 이면)  & "C:\Program Files\Git\bin\bash.exe" init-env.sh
#
# 하는 일
#   1. .env 가 없으면 .env.example 을 복사한다 (있으면 그대로 둔다)
#   2. 아직 CHANGE_ME 인 비밀 넷만 난수(16진수 48자)로 채운다
#   3. 사람이 채울 이름만 알려 준다 — 값은 찍지 않는다
#
# ⚠ 비밀 넷 중 ROBO_GRAPH_PASSWORD · AUTH_ROLE_SECRET 은 한 번 정하면 바꾸지 않는다.
#   이 스크립트는 CHANGE_ME 인 것만 채우므로 두 번 돌려도 바뀌지 않는다.
set -euo pipefail
cd "$(dirname "$0")"

if [[ -f .env ]]; then
  echo ".env 있음 — 그대로 두고 빈 비밀만 채운다"
else
  cp .env.example .env
  chmod 600 .env 2>/dev/null || true
  echo ".env 를 만들었다 (.env.example 복사)"
fi

for n in ROBO_GRAPH_PASSWORD ROBO_AUTHORITY_DB_PASSWORD AUTH_JWT_SECRET AUTH_ROLE_SECRET; do
  if grep -q "^$n=CHANGE_ME" .env; then
    v=$(openssl rand -hex 24 2>/dev/null || head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n')
    sed -i "s/^$n=CHANGE_ME.*/$n=$v/" .env
    echo "  채움  $n (${#v}자)"
  else
    echo "  둠    $n"
  fi
done

left=$(grep -E '^[A-Z0-9_]+=.*CHANGE_ME' .env | cut -d= -f1 || true)
if [[ -n $left ]]; then
  echo
  echo "사람이 채울 것 — .env 를 열어 적는다:"
  for n in $left; do
    case $n in
      ROBO_DB_SERVER_IP) echo "  $n   (AP·DB 분할 배포일 때만 — 통합 서버면 그대로 둔다)";;
      *) echo "  $n";;
    esac
  done
  echo "다 채우면:  bash check.sh"
else
  echo
  echo "CHANGE_ME 가 남지 않았다 — bash check.sh"
fi
