#!/usr/bin/env bash
# check.sh — 띄우기 **전에** 본다. 아무것도 바꾸지 않는다. 비밀 값은 찍지 않는다(이름과 길이만).
#
#   bash check.sh                      # 통합 서버
#   bash check.sh split.ap | split.db  # 분할 배포의 각 서버
#
# 보는 것
#   1. 분할 파일이 통합 파일에서 만든 그대로인가(make-split.py --check)
#   2. 이미지가 **전부 고정 태그**인가 — latest·태그 없음이면 멈춘다
#   3. .env 가 있고, CHANGE_ME 가 남지 않았고, 비밀이 규칙에 맞는가
#   4. compose 가 그 .env 로 파일을 읽어 내는가(config)
#
# podman 이면  COMPOSE="podman compose" bash check.sh
set -euo pipefail
cd "$(dirname "$0")"

COMPOSE=${COMPOSE:-docker compose}
case "${1:-}" in
  "")       FILE=docker-compose.yml ;;
  split.ap) FILE=docker-compose.split.ap.yml ;;
  split.db) FILE=docker-compose.split.db.yml ;;
  *) echo "usage: bash check.sh [split.ap|split.db]" >&2; exit 2 ;;
esac

fail=0
ok()   { printf '  v %s\n' "$*"; }
bad()  { printf '  x %s\n' "$*"; fail=1; }

echo "[1] 분할 파일"
PY=
for c in python3 python; do
  # Windows 의 python3 는 스토어 안내만 찍는 가짜일 수 있다 — 실제로 돌아 보는 것으로 고른다.
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys' >/dev/null 2>&1; then PY=$c; break; fi
done
if [[ -z $PY ]]; then
  echo "  - python 이 없어 건너뛴다(빌드한 쪽 CI 가 이미 본다)"
elif "$PY" -I make-split.py --check >/dev/null; then ok "통합 파일과 일치"
else bad "분할 파일이 통합 파일과 다르다 — python make-split.py"; fi

echo "[2] 이미지 태그 ($FILE)"
while read -r img; do
  ref=${img##*/}
  if [[ $ref != *:* ]]; then bad "태그 없음: $img"
  elif [[ ${ref##*:} == latest ]]; then bad "latest: $img"
  else ok "$img"; fi
done < <(sed -n 's/^    image: *//p' "$FILE")

echo "[3] .env"
if [[ ! -f .env ]]; then
  bad ".env 가 없다 — cp .env.example .env"
else
  perm=$(stat -c %a .env 2>/dev/null || echo "?")
  case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*) ok "권한 검사 건너뜀(Windows 파일시스템)";;
    *) [[ $perm == 600 ]] && ok "권한 $perm" || bad "권한 $perm — chmod 600 .env";;
  esac
  val() { sed -n "s/^$1=//p" .env | tail -1; }
  while read -r name; do
    # 통합 서버는 DB 서버 주소를 쓰지 않는다.
    [[ $FILE != *split* && $name == ROBO_DB_* ]] && continue
    v=$(val "$name")
    if [[ -z $v ]]; then
      case $name in SWP_SSO_*) ok "$name (비움 → 코드 기본값)";; *) bad "$name 비었다";; esac
    elif [[ $v == *CHANGE_ME* ]]; then bad "$name 를 아직 안 채웠다"
    else ok "$name (${#v}자)"; fi
  done < <(grep -oE '^[A-Z0-9_]+' .env.example | sort -u)
  for n in AUTH_JWT_SECRET AUTH_ROLE_SECRET; do
    v=$(val $n); (( ${#v} >= 32 )) || bad "$n 는 32자 이상"
  done
  [[ $(val AUTH_JWT_SECRET) != "$(val AUTH_ROLE_SECRET)" ]] || bad "AUTH_JWT_SECRET 와 AUTH_ROLE_SECRET 가 같다"
  for n in ROBO_GRAPH_PASSWORD ROBO_AUTHORITY_DB_PASSWORD; do
    [[ $(val $n) =~ ^[A-Za-z0-9]+$ ]] || bad "$n 는 영문·숫자만(DSN 에 들어간다)"
  done
  [[ $(val ROBO_GRAPH_DESIGN) != "$(val ROBO_GRAPH_ANALYSIS)" ]] ||
    bad "설계·분석 graph 이름이 같다 — 분석이 설계를 지운다"
  url=$(val ROBO_PUBLIC_URL)
  [[ $url =~ ^https?://[^/]+$ ]] || bad "ROBO_PUBLIC_URL 은 scheme://host:port (경로 없이)"
  if [[ $FILE == *split* ]]; then
    ip=$(val ROBO_DB_SERVER_IP)
    [[ $ip != 0.0.0.0 ]] || bad "ROBO_DB_SERVER_IP 에 0.0.0.0 금지 — 사내망 IP 를 쓴다(Bolt 는 평문 인증)"
  fi
fi

echo "[4] compose config"
if [[ -f .env ]] && $COMPOSE --env-file .env -f "$FILE" config --quiet 2>/tmp/robo-check.$$; then
  ok "$FILE 를 읽었다 · 서비스 $($COMPOSE --env-file .env -f "$FILE" config --services | wc -l)개"
else
  bad "$FILE 를 못 읽었다: $(head -3 /tmp/robo-check.$$ 2>/dev/null)"
fi
rm -f /tmp/robo-check.$$

echo
if (( fail )); then echo "막혔다 — 위 x 를 고친다"; exit 1; fi
echo "통과 — $COMPOSE -f $FILE up -d --wait"
