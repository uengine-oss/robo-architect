#!/usr/bin/env bash
# =============================================================================
#  Robo Architect — 중앙 DB 환경값 **한 파일** (DB 서버 · 리눅스)
# =============================================================================
#
#  이 파일 하나로 서버 쪽 설정이 끝난다. 단계마다 셸을 붙여넣지 않는다.
#  PC 쪽의 `robo-env.ps1` 과 같은 자리이고, 같은 방식이다.
#
#  쓰는 법
#      1) 아래 [고치는 곳] 의 값만 채운다
#      2) sudo bash robo-central.sh            <- 처음 올릴 때
#      3) 화면 마지막이 가리키는 pc-central-setup.ps1 을 사용자 PC 에 전달한다
#
#  다시 돌려도 된다 — **이미 만든 비밀 다섯은 그대로 둔다.**
#  (다시 만들면 이미 초기화된 DB 와 어긋나 로그인이 전부 막힌다)
#
#      bash robo-central.sh check     값과 상태만 본다. 아무것도 바꾸지 않는다
#      bash robo-central.sh rebind    주소·포트만 바뀌었을 때
#      bash robo-central.sh migrate   새 릴리스로 올린 뒤 표 구조만 맞출 때
#      bash robo-central.sh down      내려놓는다 (볼륨은 **남긴다**)
#
#  ⚠ 비밀 값은 화면에 찍지 않는다 — 길이만 보여 준다.
#
# =============================================================================


# =============================================================================
#  [고치는 곳] — 여기만 채우면 된다
# =============================================================================

# --- 1. DB 를 공개할 사내망 IP ------------------------------------------------
#  이 서버의 **LAN IP** 를 적는다. `hostname -I` 로 확인한다.
#  ⚠ 고정 IP 여야 한다(정적 할당 또는 DHCP 예약). 주소가 바뀌면 컨테이너가
#     없는 IP 에 묶인 채 healthy 로 떠 있고, 사용자 PC 는 원인을 알기 어렵다.
#     바뀌었으면 `bash robo-central.sh rebind` 로 고친다.
#  ⚠ localhost · 127.* · 0.0.0.0 은 받지 않는다 — 같은 값이 각 PC 의 컨테이너
#     여덟에도 그대로 들어가기 때문이다.
SERVER_IP=''

# --- 2. 최초 관리자의 사번 ----------------------------------------------------
#  조직이 정한 실제 사번. 이 한 사람이 앱의 설정 화면에서 나머지를 승인한다.
#  시험이면 'DEV-ADMIN' — 그러면 앱에서 admin/admin 으로 들어갈 수 있다.
ADMIN_EMPNO=''

# --- 3. 로그인 방식 -----------------------------------------------------------
#  납품(POSCO)   'swp'    <- 아래 4번 SWP 칸을 함께 본다
#  사내 시험      'none'   사번만으로 들어온다(승인제는 그대로)
AUTH_PROVIDER='swp'

#  신규 사용자를 관리자가 승인해야 쓸 수 있게 하나. 납품은 'true'.
APPROVAL_REQUIRED='true'

# --- 4. SWP — AUTH_PROVIDER='swp' 일 때만 ------------------------------------
#  ⚠ 이 값들은 **만드는 것이 아니라 받아 적는 것**이다. 조직의 SWP 등록값이고,
#    같은 이름이 msa-ez platform 의 .env 에도 있다 — 거기 값을 그대로 옮긴다.
#  ⚠ 비워 두면 앱의 **코드 기본값**을 쓴다. msa-ez v1.0.30 과 대조해 두었고
#    아홉 값이 전부 같았으므로, 조직이 바꾸지 않았다면 **비워 두는 것이 맞다.**
SWP_SSO_LOGIN_URL=''
SWP_SSO_VALID_CHECK_URL=''
SWP_SSO_REDIRECT_URL=''

#  ⚠ 아래 다섯은 비밀이 아니라 "몇 번째 칸인가" 다. isValidSSO.jsp 가 돌려주는
#    CSV 의 열 위치(0부터)이고, 그중 EMPNO 가 **사람을 가리키는 사번**이 된다.
#    실제 칸 순서가 다르면 엉뚱한 칸을 사번으로 읽고도 **오류가 나지 않는다.**
#    첫 연동 때 SWP_SSO_LOG_RAW=1 로 한 번 찍어 눈으로 확인한다.
SWP_IDX_ID=''
SWP_IDX_EMPNO=''
SWP_IDX_DISPLAYNAME=''
SWP_IDX_MAIL=''
SWP_IDX_DEPT=''

SWP_EMAIL_FALLBACK_DOMAIN=''

#  콜백이 돌아올 수 있는 origin 들. 쉼표로 잇는다.
#  ⚠ 비우면 **loopback 만** 허용된다(localhost · 127.0.0.1 · ::1).
#  ⚠ 채우면 **그 loopback 자동허용이 사라진다** — 적은 origin 만 허용된다.
#    그러므로 채울 때는 현장 origin 을 **빠뜨리지 않고** 적는다.
AUTH_CALLBACK_ALLOWLIST=''

# --- 5. 포트 — 보통 비운다 ----------------------------------------------------
#  기본 5432(DB) · 7687(Bolt) 이다. **그 서버에서 msa-ez 가 5432 를 이미 쓰고
#  있을 때만** 옮긴다. 옮기면 각 PC 의 robo-env.ps1 에도 같은 값을 넣어야 한다.
PG_PORT=''
BOLT_PORT=''

# --- 6. 작업 폴더 — 보통 그대로 ------------------------------------------------
WORK_DIR='/opt/robo-central'


# =============================================================================
#  [아래는 손대지 않는다]
# =============================================================================
set -euo pipefail
umask 077

SCRIPT_PATH=$(readlink -f "${BASH_SOURCE[0]}")
SCRIPT_DIR=$(dirname "$SCRIPT_PATH")
CMD=${1:-up}

DIM=$'\033[2m'; OFF=$'\033[0m'
RED=$'\033[31m'; YEL=$'\033[33m'; GRN=$'\033[32m'
say()   { printf '%s\n' "$*"; }
head2() { printf '\n%s== %s ==%s\n' "$DIM" "$*" "$OFF"; }
ok()    { printf '%s  v%s %s\n' "$GRN" "$OFF" "$*"; }
warn()  { printf '%s  !%s %s\n' "$YEL" "$OFF" "$*"; }
die()   { printf '\n%s막혔다:%s %s\n' "$RED" "$OFF" "$*" >&2; exit 1; }

# ── 공통 점검 ────────────────────────────────────────────────────────────────
need_tool() { command -v "$1" >/dev/null 2>&1 || die "$1 가 없다. $2"; }

check_tools() {
  need_tool docker  '먼저 Docker Engine 을 깐다.'
  need_tool openssl 'openssl 을 깐다 — 비밀 다섯을 이것으로 만든다.'
  docker compose version >/dev/null 2>&1 ||
    die 'docker compose(v2) 가 없다. docker-compose(v1) 로는 이 compose 가 안 돈다.'
  docker info >/dev/null 2>&1 ||
    die "Docker 에 닿지 못한다. 권한이면 'sudo usermod -aG docker \$USER' 뒤 다시 로그인한다."
}

# ⚠ compose 는 **셸 환경변수를 .env 파일보다 먼저** 읽는다. 지난 설치가 남긴
#   ROBO_GRAPH_PASSWORD 가 있으면 DB 가 그 옛 비밀번호로 초기화되고, 뒷 단계가
#   엉뚱한 곳에서 실패한다(2026-10-14 에 실제로 그랬다). 눈으로 보는 대신 거절한다.
check_stale_env() {
  local leaked=() n
  for n in $(compgen -e | grep -E '^(ROBO_GRAPH|ROBO_AUTHORITY|ROBO_IMAGE)' || true); do
    [[ -n ${!n:-} ]] && leaked+=("$n")
  done
  if ((${#leaked[@]})); then
    say ''
    say "셸에 지난 설치의 환경변수가 남아 있다: ${leaked[*]}"
    say 'compose 는 이것을 .env 보다 먼저 읽으므로 **조용히 엉뚱한 값으로** 올라간다.'
    say '~/.bashrc · /etc/environment 에서 그 줄을 지우고 다시 로그인한 뒤 돌린다.'
    die '남은 환경변수 때문에 멈췄다.'
  fi
  ok '셸에 남은 환경변수 없음'
}

check_server_ip() {
  [[ -n $SERVER_IP ]] || die "[고치는 곳] 1번 SERVER_IP 가 비어 있다. 'hostname -I' 의 주소를 적는다."
  [[ $SERVER_IP =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] ||
    die "SERVER_IP='$SERVER_IP' 는 IPv4 주소가 아니다. 호스트 이름이 아니라 **IP** 로 적는다."
  case $SERVER_IP in
    127.*|0.0.0.0) die "SERVER_IP='$SERVER_IP' 로는 다른 PC 가 닿지 못한다. 사내망 IP 를 적는다." ;;
  esac
  if command -v ip >/dev/null 2>&1; then
    ip -4 -o addr show 2>/dev/null | grep -qw "$SERVER_IP" ||
      warn "SERVER_IP='$SERVER_IP' 가 이 서버의 인터페이스에 없다. 'hostname -I' 로 확인한다."
  fi
  ok "SERVER_IP = $SERVER_IP"
}

check_ports() {
  command -v ss >/dev/null 2>&1 || return 0
  local p
  for p in "${PG_PORT:-5432}" "${BOLT_PORT:-7687}"; do
    if ss -lnt 2>/dev/null | grep -qE "[:.]${p}[[:space:]]"; then
      warn "포트 $p 를 이미 누가 듣고 있다. msa-ez 의 postgres 면 **내리지 말고** [고치는 곳] 5번에서 우리 포트를 옮긴다."
    fi
  done
}

# 매니페스트에서 문자열 하나를 읽는다. sed 로 읽는 이유: 서버에 python3·jq 가
# 있다고 가정하지 않는다. 매니페스트는 기계가 쓰므로 들여쓰기가 일정하다.
# ⚠ 절 이름을 함께 받는다 — images.graphDb 와 imageIds.graphDb 가 **같은 키**다.
# ⚠ 빈 값으로 지나가지 않는다 — 여기서 멈춘다.
json_top() {  # json_top <파일> <최상위 키>
  local v
  v=$(sed -n "s/^  \"$2\": \"\([^\"]*\)\".*/\1/p" "$1" | head -1 || true)
  [[ -n $v ]] || die "매니페스트에서 $2 를 못 읽었다($1). 릴리스가 온전한지 본다."
  printf '%s\n' "$v"
}
json_in() {   # json_in <파일> <절> <키>
  local v
  v=$(sed -n "/^  \"$2\": {/,/^  }/p" "$1" | sed -n "s/^    \"$3\": \"\([^\"]*\)\".*/\1/p" | head -1 || true)
  [[ -n $v ]] || die "매니페스트에서 $2.$3 을 못 읽었다($1). 릴리스가 온전한지 본다."
  printf '%s\n' "$v"
}

# env_val <파일> <키>   — 파일이나 키가 없으면 빈 문자열
env_val() {
  [[ -f $1 ]] || { printf ''; return 0; }
  sed -n "s/^$2=//p" "$1" | head -1 || true
}

# ── 작업 폴더를 세운다 ───────────────────────────────────────────────────────
#  처음에는 릴리스 폴더의 central-server/ 안에서 돌린다. 그러면 필요한 파일과
#  **이 스크립트 자신**을 작업 폴더로 옮기고, 그 뒤로는 작업 폴더의 사본을
#  돌린다 — 채운 값이 그 사본에 남아 다음 사람이 읽을 수 있다.
stage_work_dir() {
  local src=$SCRIPT_DIR f
  [[ -f $src/compose.yml ]] ||
    die "compose.yml 이 이 스크립트 옆에 없다($src). 릴리스의 central-server/ 안에서 돌린다."
  mkdir -p "$WORK_DIR"
  if [[ $src != "$WORK_DIR" ]]; then
    for f in compose.yml runtime-manifest.json central-authority.env.example README.md; do
      [[ -f $src/$f ]] && cp -f "$src/$f" "$WORK_DIR/$f"
    done
    cp -f "$SCRIPT_PATH" "$WORK_DIR/robo-central.sh"
    chmod 600 "$WORK_DIR/robo-central.sh"
    ok "작업 폴더를 세웠다: $WORK_DIR"
    say "    ${DIM}다음부터는 그 폴더의 사본을 돌린다 — 채운 값이 거기 남아 있다${OFF}"
  fi
  cd "$WORK_DIR"
  [[ -f runtime-manifest.json ]] || die "runtime-manifest.json 이 없다: $WORK_DIR"
}

# ── 이미지를 올린다 ─────────────────────────────────────────────────────────
#  서버가 쓰는 것은 **세 장**이다(graph-db · graph-bolt · authority).
#  ⚠ 한 장만 보고 건너뛰지 않는다 — graphDb 는 있는데 authority 가 없으면
#    여기서는 조용히 지나가고, 뒤의 `compose run authority` 에서 엉뚱하게 터진다.
#  ⚠ 태그가 아니라 **image ID** 로 대조한다. 태그는 같고 내용은 다른 장이 있을
#    수 있고, 앱도 `ensureImages()` 에서 같은 대조를 해 거절한다.
LOAD_IMAGE_KEYS=(graphDb graphBolt authority)

images_all_present() {
  local key ref want got
  for key in "${LOAD_IMAGE_KEYS[@]}"; do
    ref=$(json_in runtime-manifest.json images "$key")
    want=$(json_in runtime-manifest.json imageIds "$key")
    got=$(docker image inspect --format '{{.Id}}' "$ref" 2>/dev/null || true)
    [[ $got == "$want" ]] || { MISSING_IMAGE="$ref"; return 1; }
  done
  return 0
}

load_images() {
  local tar
  MISSING_IMAGE=''
  if images_all_present; then
    ok "이미지 ${#LOAD_IMAGE_KEYS[@]}장이 이미 있다 (image ID 까지 같다)"
    return 0
  fi
  for tar in "$SCRIPT_DIR/../robo-images.tar" "$SCRIPT_DIR/robo-images.tar" "$WORK_DIR/robo-images.tar"; do
    if [[ -f $tar ]]; then
      say "  부품 묶음을 올린다 ($(du -h "$tar" | cut -f1)) — 몇 분 걸린다"
      docker load --input "$tar" | tail -3
      images_all_present ||
        die "묶음을 올렸는데 $MISSING_IMAGE 가 맞지 않는다. 릴리스가 섞였다 — 같은 판의 폴더인지 본다."
      ok '부품 묶음을 올렸다'
      return 0
    fi
  done
  die "robo-images.tar 를 못 찾았고 ${MISSING_IMAGE} 가 없다. 릴리스 폴더째로 옮긴 뒤 그 안의 central-server/ 에서 돌린다."
}

# ── 설정 파일 둘 ────────────────────────────────────────────────────────────
#  ⚠ 비밀 다섯은 **있으면 그대로 쓴다.** 다시 만들면 이미 초기화된 DB 와
#    어긋나고, 증상은 "모든 로그인 실패" 로만 나타난다.
read_or_make_secrets() {
  local made=0
  GRAPH_PW=$(env_val .env ROBO_GRAPH_PASSWORD)
  JWT_SECRET=$(env_val central-authority.env AUTH_JWT_SECRET)
  ROLE_SECRET=$(env_val central-authority.env AUTH_ROLE_SECRET)
  AUTH_RT_PW=$(sed -n 's#^OG_PG_DSN=postgresql://robo_authority:\([^@]*\)@.*#\1#p' central-authority.env 2>/dev/null | head -1 || true)
  OPER_PW=$(sed -n 's#^ROBO_PROJECT_OPERATOR_DSN=postgresql://robo_operator:\([^@]*\)@.*#\1#p' central-authority.env 2>/dev/null | head -1 || true)

  # DB 비밀번호 셋은 **hex** 다 — base64 의 / + = @ 가 DSN 의 사용자:비번@호스트 를 깨뜨린다.
  [[ -n $GRAPH_PW    ]] || { GRAPH_PW=$(openssl rand -hex 32);   made=1; }
  [[ -n $AUTH_RT_PW  ]] || { AUTH_RT_PW=$(openssl rand -hex 32); made=1; }
  [[ -n $OPER_PW     ]] || { OPER_PW=$(openssl rand -hex 32);    made=1; }
  # ⚠ \r 도 지운다 — 어떤 openssl 은 CRLF 로 내고, 그러면 비밀 끝에 CR 이 한 글자
  #   붙은 채 .env 에 들어간다(길이 65). 오류 없이 어긋난다 — 실제로 걸렸다.
  [[ -n $JWT_SECRET  ]] || { JWT_SECRET=$(openssl rand -base64 48 | tr -d '\r\n');  made=1; }
  [[ -n $ROLE_SECRET ]] || { ROLE_SECRET=$(openssl rand -base64 48 | tr -d '\r\n'); made=1; }
  if ((made)); then ok '비밀 다섯을 만들었다'; else ok '비밀 다섯이 이미 있다 — 그대로 둔다'; fi
}

write_env_files() {
  local img_db img_bolt img_auth g_user g_design g_analysis n
  img_db=$(json_in runtime-manifest.json images graphDb)
  img_bolt=$(json_in runtime-manifest.json images graphBolt)
  img_auth=$(json_in runtime-manifest.json images authority)
  g_user=$(json_in runtime-manifest.json graphs user)
  g_design=$(json_in runtime-manifest.json graphs design)
  g_analysis=$(json_in runtime-manifest.json graphs analysis)
  [[ $g_design != "$g_analysis" ]] ||
    die "매니페스트의 설계·분석 graph 이름이 같다($g_design). 그대로 올리면 분석이 설계를 지운다."

  {
    say '# robo-central .env — robo-central.sh 가 만든다. 손으로 고치지 않는다.'
    say '# 주소·포트를 바꿀 때는  bash robo-central.sh rebind'
    say "ROBO_IMAGE_GRAPH_DB=$img_db"
    say "ROBO_IMAGE_GRAPH_BOLT=$img_bolt"
    say "ROBO_IMAGE_AUTHORITY=$img_auth"
    say "ROBO_GRAPH_USER=$g_user"
    say "ROBO_GRAPH_PASSWORD=$GRAPH_PW"
    say "ROBO_GRAPH_DESIGN=$g_design"
    say "ROBO_GRAPH_ANALYSIS=$g_analysis"
    say "ROBO_GRAPH_BIND=$SERVER_IP"
    say "ROBO_AUTHORITY_BIND=$SERVER_IP"
    [[ -n $PG_PORT   ]] && say "ROBO_GRAPH_PG_PORT=$PG_PORT"     || :
    [[ -n $BOLT_PORT ]] && say "ROBO_GRAPH_BOLT_PORT=$BOLT_PORT" || :
  } > .env

  {
    say '# central-authority.env — robo-central.sh 가 만든다. 손으로 고치지 않는다.'
    say "AUTH_PROVIDER=$AUTH_PROVIDER"
    say 'AUTH_ENFORCE=true'
    say 'AUTH_DEV_LOGIN_ENABLED=false'
    say "AUTH_JWT_SECRET=$JWT_SECRET"
    say "AUTH_ROLE_SECRET=$ROLE_SECRET"
    say "OG_PG_DSN=postgresql://robo_authority:$AUTH_RT_PW@graph-db:5432/$g_design"
    say "ROBO_PROJECT_OPERATOR_DSN=postgresql://robo_operator:$OPER_PW@graph-db:5432/$g_design"
    if [[ $AUTH_PROVIDER == swp ]]; then
      # ⚠ 빈 값은 **적지 않는다.** 적으면 빈 문자열이 코드 기본값을 덮어쓴다.
      for n in SWP_SSO_LOGIN_URL SWP_SSO_VALID_CHECK_URL SWP_SSO_REDIRECT_URL \
               SWP_IDX_ID SWP_IDX_EMPNO SWP_IDX_DISPLAYNAME SWP_IDX_MAIL SWP_IDX_DEPT \
               SWP_EMAIL_FALLBACK_DOMAIN AUTH_CALLBACK_ALLOWLIST; do
        [[ -n ${!n} ]] && say "$n=${!n}" || :
      done
    fi
  } > central-authority.env

  chmod 600 .env central-authority.env
  ok "설정 파일 둘을 썼다 (.env $(wc -l < .env)줄 · central-authority.env $(wc -l < central-authority.env)줄)"

  if [[ $AUTH_PROVIDER == swp ]]; then
    if [[ -z $AUTH_CALLBACK_ALLOWLIST ]]; then
      warn 'AUTH_CALLBACK_ALLOWLIST 를 비웠다 — 콜백이 **loopback 만** 허용된다(localhost · 127.0.0.1 · ::1).'
      say  "    ${DIM}현장 콜백이 다른 origin 이면 거부된다. 그때 [고치는 곳] 4번에 적고 rebind 한다${OFF}"
    else
      warn 'AUTH_CALLBACK_ALLOWLIST 를 채웠다 — 그러면 **loopback 자동허용이 사라진다.**'
      say  "    ${DIM}적은 origin 만 허용된다. 현장 origin 을 빠뜨리지 않았는지 본다${OFF}"
    fi
    [[ -n $SWP_IDX_EMPNO ]] ||
      warn 'SWP_IDX_* 를 비웠다 — 코드 기본값(0·1·8·9·4)을 쓴다. 첫 연동 때 SWP_SSO_LOG_RAW=1 로 칸 순서를 확인한다.'
  fi
}

dc() { docker compose --env-file .env -f compose.yml "$@"; }

# ── DB 를 띄우고 역할을 넣는다 ───────────────────────────────────────────────
bring_up() {
  local user design sql
  user=$(env_val .env ROBO_GRAPH_USER)
  design=$(env_val .env ROBO_GRAPH_DESIGN)
  dc up -d --wait graph-db graph-bolt
  dc ps --format '    {{.Service}}  {{.Status}}  {{.Ports}}'

  # 역할 둘 — 있으면 비밀번호를 맞추고, 없으면 만든다. 여러 번 돌려도 안전하다.
  sql="DO \$do\$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'robo_authority')
    THEN ALTER ROLE robo_authority LOGIN PASSWORD '$AUTH_RT_PW';
    ELSE CREATE ROLE robo_authority LOGIN PASSWORD '$AUTH_RT_PW';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'robo_operator')
    THEN ALTER ROLE robo_operator LOGIN PASSWORD '$OPER_PW';
    ELSE CREATE ROLE robo_operator LOGIN PASSWORD '$OPER_PW';
  END IF;
END \$do\$;"
  printf '%s\n' "$sql" |
    dc exec -T graph-db psql -U "$user" -d "$design" -v ON_ERROR_STOP=1 -q
  ok 'DB 역할 둘 (robo_authority · robo_operator)'
}

# authority_cli <accounts_admin 인자...>
#  ⚠ OG_PG_DSN 은 **일회성**이다. 상시 authority 서비스에는 넣지 않는다 —
#    그 서비스는 central-authority.env 의 제한된 역할로만 붙는다.
authority_cli() {
  local dsn
  dsn="postgresql://$(env_val .env ROBO_GRAPH_USER):$GRAPH_PW@graph-db:5432/$(env_val .env ROBO_GRAPH_DESIGN)"
  dc run --rm --no-deps -e OG_PG_DSN="$dsn" authority python -m scripts.accounts_admin "$@"
}

init_accounts() {
  [[ -n $ADMIN_EMPNO ]] || die '[고치는 곳] 2번 ADMIN_EMPNO 가 비어 있다. 최초 관리자의 사번을 적는다.'
  say '  migrate'
  authority_cli migrate | sed 's/^/    /'
  # ⚠ 순서를 바꾸지 않는다 — grant 가 initialized 를 켠다. policy 가 먼저면 거절된다.
  say "  grant $ADMIN_EMPNO"
  authority_cli grant --employee-no "$ADMIN_EMPNO" --reason 'initial administrator' | sed 's/^/    /'
  say "  policy approval-required=$APPROVAL_REQUIRED"
  authority_cli policy --approval-required "$APPROVAL_REQUIRED" --reason 'delivery approval policy' | sed 's/^/    /'
}

verify() {
  local user design ext initialized
  user=$(env_val .env ROBO_GRAPH_USER)
  design=$(env_val .env ROBO_GRAPH_DESIGN)
  psql_q() { printf '%s\n' "$1" | dc exec -T graph-db psql -U "$user" -d "$design" -At; }

  head2 '확인'
  dc ps --format '    {{.Service}}  {{.Status}}  {{.Ports}}'
  # ⚠ Ports 칸이 비면 주소가 없어진 것이다 — 컨테이너는 healthy 인 채로 떠 있다.
  dc ps --format '{{.Ports}}' | grep -q "$SERVER_IP" ||
    warn "Ports 칸에 $SERVER_IP 가 없다. 주소가 바뀌었으면 rebind 한다."

  ext=$(psql_q "SELECT string_agg(extname, ', ' ORDER BY extname) FROM pg_extension;")
  say "    확장: $ext"
  case $ext in
    *ontological*) ok '그래프 확장 있음' ;;
    *) die 'ontological 확장이 없다. DB 가 속이 비었다 — docker compose logs graph-db 로 초기화 로그를 본다.' ;;
  esac

  say "    관리자: $(psql_q "SELECT uid || ' | ' || role || ' | ' || status FROM public.app_users ORDER BY uid;" | tr '\n' ' ')"
  initialized=$(psql_q 'SELECT initialized FROM public.app_auth_policy WHERE id=1;')
  [[ $initialized == t ]] ||
    die "app_auth_policy.initialized 가 '$initialized' 다. 초기화가 안 됐으면 **모든 로그인이 503** 이 된다."
  ok '초기화 됨 (initialized = t)'
}

# ── 사용자 PC 에 줄 접속값 ───────────────────────────────────────────────────
export_pc_setup() {
  local out=pc-central-setup.ps1 name value
  {
    say '# Robo Architect 접속값 — 비밀을 담고 있다. 넣은 뒤 이 파일을 지운다.'
    say '# 받는 사람은 사용자-설치-가이드 3번의 robo-env.ps1 위쪽 네 자리에 옮겨 적는다.'
    printf "[Environment]::SetEnvironmentVariable('%s', '%s', 'User')\n" ROBO_GRAPH_MODE     central
    printf "[Environment]::SetEnvironmentVariable('%s', '%s', 'User')\n" ROBO_GRAPH_HOST     "$SERVER_IP"
    printf "[Environment]::SetEnvironmentVariable('%s', '%s', 'User')\n" ROBO_GRAPH_PASSWORD "$GRAPH_PW"
    printf "[Environment]::SetEnvironmentVariable('%s', '%s', 'User')\n" AUTH_ROLE_SECRET    "$ROLE_SECRET"
    printf "[Environment]::SetEnvironmentVariable('%s', '%s', 'User')\n" AUTH_JWT_SECRET     "$JWT_SECRET"
    [[ -n $PG_PORT   ]] && printf "[Environment]::SetEnvironmentVariable('%s', '%s', 'User')\n" ROBO_GRAPH_PG_PORT   "$PG_PORT"   || :
    [[ -n $BOLT_PORT ]] && printf "[Environment]::SetEnvironmentVariable('%s', '%s', 'User')\n" ROBO_GRAPH_BOLT_PORT "$BOLT_PORT" || :
    say "'넣기 완료 — 로그아웃·재로그인 뒤 앱을 켜세요'"
  } > "$out"
  chmod 600 "$out"

  head2 '사용자 PC 에 줄 파일'
  say "    $WORK_DIR/$out   ($(wc -l < "$out")줄)"
  # ⚠ 값은 길이만 본다. (sed 로 뽑는다 — [[ =~ ]] 는 홑따옴표 이스케이프가
  #   셸에서 먼저 벗겨져 괄호가 정규식 묶음이 되어 버린다)
  #   구분자는 | 다 — hex·base64·이름 어디에도 나오지 않는다
  while IFS='|' read -r name value; do
    printf '      %-22s 길이 %s\n' "$name" "${#value}"
  done < <(sed -n "s/.*SetEnvironmentVariable('\([A-Z_]*\)', *'\(.*\)', *'User').*/\1|\2/p" "$out")
  warn '비밀 셋이 평문으로 들어 있다 — 메일·메신저로 보내지 않는다. 전달이 끝나면 양쪽에서 지운다.'
}

# ── 갈래 ────────────────────────────────────────────────────────────────────
main() {
case $CMD in
  up)
    head2 '점검'
    check_tools; check_stale_env; check_server_ip; check_ports
    head2 '작업 폴더'
    stage_work_dir
    head2 '부품 묶음'
    load_images
    head2 '설정 파일'
    read_or_make_secrets
    write_env_files
    head2 'DB 기동'
    bring_up
    head2 '스키마 · 관리자 · 정책'
    init_accounts
    verify
    export_pc_setup
    head2 '끝'
    say '    다음  사용자-설치-가이드.md 를 0-A 부터 따라 각 PC 에 앱을 깐다'
    say "    ${DIM}이 서버에서 다시 볼 때는  bash $WORK_DIR/robo-central.sh check${OFF}"
    ;;

  check)
    # 아무것도 바꾸지 않는다.
    check_tools
    cd "$WORK_DIR" 2>/dev/null || die "작업 폴더가 없다: $WORK_DIR — 아직 올리지 않았다."
    [[ -f .env ]] || die ".env 가 없다: $WORK_DIR — 아직 올리지 않았다."
    SERVER_IP=$(env_val .env ROBO_GRAPH_BIND)
    GRAPH_PW=$(env_val .env ROBO_GRAPH_PASSWORD)
    ROLE_SECRET=$(env_val central-authority.env AUTH_ROLE_SECRET)
    JWT_SECRET=$(env_val central-authority.env AUTH_JWT_SECRET)
    head2 '설정'
    say "    릴리스  $(json_top runtime-manifest.json releaseId)"
    say "    주소    $SERVER_IP"
    pg_now=$(env_val .env ROBO_GRAPH_PG_PORT); bolt_now=$(env_val .env ROBO_GRAPH_BOLT_PORT)
    say "    포트    DB ${pg_now:-5432} · Bolt ${bolt_now:-7687}"
    say "    로그인  $(env_val central-authority.env AUTH_PROVIDER)"
    printf '    %-22s 길이 %s\n' ROBO_GRAPH_PASSWORD "${#GRAPH_PW}"
    printf '    %-22s 길이 %s\n' AUTH_ROLE_SECRET    "${#ROLE_SECRET}"
    printf '    %-22s 길이 %s\n' AUTH_JWT_SECRET     "${#JWT_SECRET}"
    verify
    ;;

  rebind)
    check_tools; check_stale_env; check_server_ip
    cd "$WORK_DIR" 2>/dev/null || die "작업 폴더가 없다: $WORK_DIR"
    [[ -f .env ]] || die ".env 가 없다 — 먼저 'bash robo-central.sh' 로 올린다."
    head2 '주소를 고친다'
    sed -i "s#^ROBO_GRAPH_BIND=.*#ROBO_GRAPH_BIND=$SERVER_IP#" .env
    sed -i "s#^ROBO_AUTHORITY_BIND=.*#ROBO_AUTHORITY_BIND=$SERVER_IP#" .env
    sed -i '/^ROBO_GRAPH_PG_PORT=/d;/^ROBO_GRAPH_BOLT_PORT=/d' .env
    [[ -n $PG_PORT   ]] && say "ROBO_GRAPH_PG_PORT=$PG_PORT"     >> .env
    [[ -n $BOLT_PORT ]] && say "ROBO_GRAPH_BOLT_PORT=$BOLT_PORT" >> .env
    ok "ROBO_GRAPH_BIND · ROBO_AUTHORITY_BIND = $SERVER_IP"
    dc up -d --force-recreate --wait graph-db graph-bolt
    GRAPH_PW=$(env_val .env ROBO_GRAPH_PASSWORD)
    ROLE_SECRET=$(env_val central-authority.env AUTH_ROLE_SECRET)
    JWT_SECRET=$(env_val central-authority.env AUTH_JWT_SECRET)
    verify
    export_pc_setup
    head2 '아직 안 끝났다 — 세 자리 중 둘만 고쳤다'
    say '    남은 하나: **각 PC** 의 ROBO_GRAPH_HOST'
    say '      사용자-설치-가이드 3번의 robo-env.ps1 에서 $GRAPH_HOST 를 새 주소로 바꿔 다시 돌린다'
    say '      그다음 **앱을 껐다가 바탕화면 아이콘으로 다시 띄운다** — 중앙만 올려서는 안 풀린다'
    ;;

  migrate)
    # 새 릴리스로 올린 뒤 표 구조만 맞춘다. 여러 번 돌려도 안전하다(전부 IF NOT EXISTS).
    check_tools
    cd "$WORK_DIR" 2>/dev/null || die "작업 폴더가 없다: $WORK_DIR"
    GRAPH_PW=$(env_val .env ROBO_GRAPH_PASSWORD)
    head2 'migrate'
    authority_cli migrate | sed 's/^/    /'
    say ''
    say "    ${DIM}이미지까지 새 판으로 올리려면 관리자-DB올리기.md 9번을 읽는다 —${OFF}"
    say "    ${DIM}그래프 엔진이 바뀐 판은 볼륨을 새로 만들어야 하고, 그러면 데이터가 사라진다${OFF}"
    ;;

  down)
    check_tools
    cd "$WORK_DIR" 2>/dev/null || die "작업 폴더가 없다: $WORK_DIR"
    # ⚠ -v 를 붙이지 않는다 — 볼륨에 팀의 설계 전부가 있다.
    dc down
    ok '컨테이너를 내렸다. 볼륨은 그대로 있다 (팀의 설계가 거기 있다)'
    say "    ${DIM}다시 올리기:  bash $WORK_DIR/robo-central.sh${OFF}"
    ;;

  *)
    die "모르는 명령: $CMD   (쓸 수 있는 것: up · check · rebind · migrate · down)"
    ;;
esac
}

# 직접 돌릴 때만 갈래로 들어간다. source 하면 함수만 올라온다 —
# 시험이 함수를 하나씩 걸어 볼 수 있어야 해서 그렇게 뒀다.
if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
  main "$@"
fi
