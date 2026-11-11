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
#   4. yml 의 모델 설정·AI 주소가 .env 와 짝인가 (박힌 값 **과 빠진 값** 모두)
#   5. compose 가 그 .env 로 파일을 읽어 내는가(config)
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
  [[ $(val ROBO_APPROVAL_REQUIRED) =~ ^(true|false)$ ]] || bad "ROBO_APPROVAL_REQUIRED 는 true|false"
  # AI 주소와 analyzer 설정은 짝이다 — 한쪽만 바꾸면 분석만 다른 곳으로 간다.
  case "$(val ROBO_ANALYZER_LLM_CONFIG):$(val ROBO_AI_BASE_URL)" in
    openai_gpt41:https://api.openai.com/*) ok "AI: OpenAI 직결 (analyzer openai_gpt41)";;
    openai_gpt41:*) bad "ROBO_ANALYZER_LLM_CONFIG=openai_gpt41 인데 ROBO_AI_BASE_URL 이 OpenAI 가 아니다";;
    pgpt:https://api.openai.com/*) bad "ROBO_AI_BASE_URL 이 OpenAI 인데 ROBO_ANALYZER_LLM_CONFIG=pgpt — 분석만 P-GPT 로 간다 (openai_gpt41 로)";;
    pgpt:*) ok "AI: P-GPT (analyzer pgpt)";;
    *) bad "ROBO_ANALYZER_LLM_CONFIG 는 pgpt | openai_gpt41";;
  esac
  # yml 에 **박힌** 모델 설정 이름. `.env` 를 거치는 것은 위에서 이미 봤다.
  # 2026-11-11: ROBO_SEARCH_LLM_CONFIG 가 `gpt54_mini_openai`(api_base = api.openai.com)로
  # 박혀 있었다 — 위의 짝 검사는 ROBO_ANALYZER_LLM_CONFIG 만 보아 이 자리를 놓쳤다.
  seen=0; pinned=0
  while read -r name value; do
    seen=$((seen+1))
    case $value in '${'*) continue;; esac
    pinned=$((pinned+1))
    case "$value:$(val ROBO_AI_BASE_URL)" in
      openai_gpt41:https://api.openai.com/*) ok "yml $name=$value (OpenAI 직결과 짝)";;
      pgpt:https://api.openai.com/*) bad "yml 의 $name=pgpt 인데 ROBO_AI_BASE_URL 이 OpenAI 다";;
      pgpt:*) ok "yml $name=$value (P-GPT 와 짝)";;
      openai_gpt41:*) bad "yml 의 $name=openai_gpt41 인데 ROBO_AI_BASE_URL 이 OpenAI 가 아니다";;
      *) bad "yml 에 AI 주소와 짝이 아닌 모델 설정이 박혀 있다: $name=$value";;
    esac
  done < <(sed -n 's/^ *\([A-Z0-9_]*LLM_CONFIG\): *\(.*\)/\1 \2/p' "$FILE")
  if (( seen == 0 )); then ok "모델 설정 이름이 이 파일에 없다 (DB 서버 몫)"
  elif (( pinned == 0 )); then ok "모델 설정 $seen 곳 모두 .env 가 정한다 (박힌 값 없음)"; fi

  # AI 주소가 **전부 .env 에서 나오는가.** 2026-11-11 에 여기가 뚫렸다 — architect-api 에
  # EMBEDDING_API_KEY 만 주고 주소를 안 줬더니, 코드가 그것을 "전용 endpoint" 로 보고
  # **OpenAI 본점**으로 보냈다(embeddings.py: dedicated_key → OPENAI_DEFAULT_BASE_URL).
  # 띄운 컨테이너에서 baseUrl=https://api.openai.com/v1 로 쟀다. 박힌 값을 보는 검사로는
  # **없는 값**을 못 잡으므로 셋을 같이 본다.
  # 주석은 뺀다 — 이 yml 의 주석이 그 주소를 **설명**한다(2026-11-11 에 자기 주석에 걸렸다).
  if grep -vE '^ *#' "$FILE" | grep -qE 'api[.]openai[.]com'; then
    bad "yml 에 api.openai.com 이 박혀 있다 — 주소는 .env 로만 정한다"
  else
    ok "yml 에 박힌 외부 AI 주소 없음"
  fi
  n_ai=0
  while read -r line; do
    n_ai=$((n_ai+1))
    [[ $line == *ROBO_AI_BASE_URL* ]] || bad "AI 주소가 .env 를 안 가리킨다: ${line%%:*}"
  done < <(grep -E '^ +(OPENAI|EMBEDDING|LLM|ROBO_EMBED)[A-Z0-9_]*(BASE_URL|API_BASE): ' "$FILE" | sed 's/^ *//')
  if (( n_ai == 0 )); then ok "AI 주소 칸이 이 파일에 없다 (DB 서버 몫)"
  else ok "AI 주소 칸 $n_ai 곳이 .env(ROBO_AI_BASE_URL)를 가리킨다"; fi
  if grep -qE '^ +EMBEDDING_API_KEY: ' "$FILE"; then
    if grep -qE '^ +EMBEDDING_BASE_URL: ' "$FILE"; then
      ok "EMBEDDING 키와 주소가 짝이다"
    else
      bad "EMBEDDING_API_KEY 만 있고 EMBEDDING_BASE_URL 이 없다 — 임베딩이 OpenAI 본점으로 간다"
    fi
  else
    ok "전용 임베딩 키를 안 쓴다 (OPENAI_BASE_URL 을 물려받는다)"
  fi

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
