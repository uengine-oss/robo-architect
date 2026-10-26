# =============================================================================
#  Robo Architect — 환경값 한 파일
# =============================================================================
#
#  이 파일 하나로 PC 설정이 끝납니다. 단계마다 PowerShell 을 치지 않습니다.
#
#  쓰는 법
#      1) 아래 [고치는 곳] 의 값만 채웁니다
#      2) powershell -ExecutionPolicy Bypass -File .\robo-env.ps1
#      3) **로그아웃·재로그인** 합니다 (Windows 는 로그인할 때 환경변수를 읽습니다)
#      4) ⚠ **이 파일을 지웁니다** — 비밀이 평문으로 들어 있습니다
#
#  다시 돌려도 됩니다. 같은 값이면 덮어쓸 뿐이고, 이 PC 가 만든 난수
#  (PDF2BPMN_FACADE_KEY)는 이미 있으면 **그대로 둡니다**.
#
#  지우려면   .\robo-env.ps1 -Clear
#  보기만     .\robo-env.ps1 -Check     (아무것도 바꾸지 않습니다)
#
# =============================================================================

param(
    [switch]$Clear,   # 이 프로그램이 쓰는 환경변수를 전부 지웁니다
    [switch]$Check    # 지금 상태만 봅니다 — 바꾸지 않습니다
)

# =============================================================================
#  [고치는 곳] — 여기만 채우면 됩니다
# =============================================================================

# --- AI 키 ------------------------------------------------------------------
#  발급받은 키 하나를 적습니다. 아래 다섯 이름에 **같은 값**이 들어갑니다
#  (서비스마다 읽는 이름이 달라서 그렇습니다).
$AI_KEY = ''

# --- 중앙 DB 접속값 ----------------------------------------------------------
#  **관리자가 줍니다.** 관리자가 이 PC 에 DB 를 올렸다면 이미 들어가 있으므로
#  비워 두면 됩니다 — 이 스크립트가 기존 값을 지우지 않습니다.
#
#  ⚠ $GRAPH_HOST 는 그 기계의 **사내망 IP** 여야 합니다.
#     localhost · 127.* · host.docker.internal · WSL 주소(172.*)는 앱이 거절합니다.
#     같은 값이 이 PC 의 컨테이너 여덟에도 그대로 들어가기 때문입니다.
$GRAPH_HOST     = ''
$GRAPH_PASSWORD = ''
$ROLE_SECRET    = ''   # ⚠ 모든 PC 가 **같은 값**. 한 번 정하면 못 바꿉니다
$JWT_SECRET     = ''

#  포트는 **보통 비워 둡니다** — 기본이 5432(DB) · 7687(Bolt) 입니다.
#  중앙 DB 가 **다른 포트로 열려 있을 때만** 적습니다. 관리자가 알려 줍니다.
#  (그 서버에서 msa-ez 가 5432 를 이미 쓰고 있으면 옮겨 열었을 수 있습니다)
$GRAPH_PG_PORT   = ''
$GRAPH_BOLT_PORT = ''

# --- 부품 묶음(robo-images.tar) 자리 -----------------------------------------
#  **보통 비워 둡니다** — 설치 가이드 §5 대로 복사해 두면 앱이 알아서 찾습니다.
#  공유 폴더·USB 에 둔 tar 를 **복사하지 않고 그대로 쓰려면** 그 절대 경로를
#  적습니다. 2.7GB 복사를 건너뜁니다.
#  ⚠ 그 자리가 없어지면 나중에 이미지를 다시 올릴 수 없습니다.
$IMAGE_TAR = ''

# --- 시험 로그인 -------------------------------------------------------------
#  ⚠ **납품 상태에서는 $DEV_LOGIN 을 $false 로 둡니다.**
#     아이디·비밀번호만으로 들어오는 문입니다.
$DEV_LOGIN    = $true
$DEV_ID       = 'admin'
$DEV_PASSWORD = 'admin'
$DEV_EMPNO    = 'DEV-ADMIN'          # 관리자가 grant 한 사번과 **같아야** 합니다
$DEV_NAME     = '관리자'
$DEV_ACCOUNTS = 'user1:user1::사용자1:개발'   # id:비번:사번:이름:부서

# =============================================================================
#  [아래는 손대지 않습니다]
# =============================================================================

$ErrorActionPreference = 'Stop'

# 이 프로그램이 쓰는 이름 전부. -Clear 와 -Check 가 이 목록을 봅니다.
$ALL_NAMES = @(
    'ROBO_GRAPH_MODE','ROBO_GRAPH_HOST','ROBO_GRAPH_PASSWORD',
    'ROBO_GRAPH_PG_PORT','ROBO_GRAPH_BOLT_PORT','ROBO_IMAGE_ARCHIVE',
    'ROBO_AUTHORITY_URL','ROBO_INGESTION_URL',
    'AUTH_JWT_SECRET','AUTH_ROLE_SECRET','AUTH_APPROVAL_REQUIRED',
    'AUTH_DEV_LOGIN_ENABLED','AUTH_DEV_LOGIN_ACCOUNTS',
    'AUTH_DEV_LOGIN_ID','AUTH_DEV_LOGIN_PASSWORD',
    'AUTH_DEV_LOGIN_EMPNO','AUTH_DEV_LOGIN_NAME','AUTH_DEV_LOGIN_ALLOW_REMOTE',
    'PDF2BPMN_FACADE_KEY',
    'OPENAI_API_KEY','LLM_API_KEY','ROBO_LLM_API_KEY',
    'ROBO_EMBED_API_KEY','ROBO_SEARCH_LLM_API_KEY'
)

# AI 키를 받는 다섯 이름. 값은 전부 같습니다.
$AI_NAMES = @('OPENAI_API_KEY','LLM_API_KEY','ROBO_LLM_API_KEY',
              'ROBO_EMBED_API_KEY','ROBO_SEARCH_LLM_API_KEY')

function Get-User($name) { [Environment]::GetEnvironmentVariable($name, 'User') }
function Set-User($name, $value) { [Environment]::SetEnvironmentVariable($name, $value, 'User') }

function Show-State($names, $title) {
    ""
    $title
    ('-' * 64)
    foreach ($n in $names) {
        $v = Get-User $n
        # ⚠ **값은 절대 찍지 않습니다.** 화면 캡처·채팅에 남으면 그 키는 폐기해야 합니다.
        "{0,-26} {1}" -f $n, $(if ($v) { "있음 (길이 $($v.Length))" } else { '★ 없음' })
    }
}

# --- -Clear : 전부 지웁니다 ---------------------------------------------------
if ($Clear) {
    ""
    "⚠ AI 키를 따로 보관하고 계십니까? 지우면 되돌릴 수 없습니다."
    "   빼두려면: [Environment]::GetEnvironmentVariable('OPENAI_API_KEY','User') | Set-Content -NoNewline `"`$env:USERPROFILE\Desktop\ai-key.txt`""
    ""
    $answer = Read-Host "전부 지웁니다. 계속하려면 '지움' 이라고 치세요"
    if ($answer -ne '지움') { "그만둡니다."; exit 1 }
    foreach ($n in $ALL_NAMES) { Set-User $n $null }
    Show-State $ALL_NAMES "지운 뒤 — 전부 '★ 없음' 이어야 합니다"
    ""
    "지웠습니다. **로그아웃·재로그인** 하십시오."
    exit 0
}

# --- -Check : 보기만 ---------------------------------------------------------
if ($Check) {
    Show-State $ALL_NAMES "지금 상태 — 값은 보지 않고 길이만 봅니다"
    ""
    $manifest = "$env:LOCALAPPDATA\Programs\Robo-Architect\resources\runtime\runtime-manifest.json"
    if (Test-Path $manifest) {
        $m = Get-Content $manifest -Raw | ConvertFrom-Json
        ""
        "이 릴리스가 **기동에 요구하는** 이름: $($m.credentialNames.Count)개"
        ('-' * 64)
        foreach ($n in $m.credentialNames) {
            $v = Get-User $n
            "{0,-26} {1}" -f $n, $(if ($v) { '있음' } else { '★ 없음 — 창이 안 뜹니다' })
        }
    } else {
        "(설치본을 아직 안 깔아서 매니페스트를 못 읽었습니다 — §4 뒤에 다시 보세요)"
    }
    exit 0
}

# --- 넣기 --------------------------------------------------------------------

$problems = @()

if (-not $AI_KEY) {
    $problems += 'AI 키($AI_KEY)가 비어 있습니다 — 이 파일 위쪽에 적으십시오'
}

# ⚠ 주소 규칙을 **넣기 전에** 봅니다. 잘못 들어가면 컨테이너가 조용히 못 붙고,
#    증상이 "fabric is unhealthy" 로 엉뚱하게 나옵니다.
if ($GRAPH_HOST) {
    if ($GRAPH_HOST -match '^(localhost|127\.|::1|0\.0\.0\.0|host\.docker\.internal)') {
        $problems += "ROBO_GRAPH_HOST 에 '$GRAPH_HOST' 는 쓸 수 없습니다 — 그 기계의 사내망 IP 를 쓰십시오"
    }
    if ($GRAPH_HOST -match '^172\.(1[6-9]|2[0-9]|3[01])\.') {
        $problems += "ROBO_GRAPH_HOST '$GRAPH_HOST' 는 WSL 가상 주소로 보입니다 — 다른 PC 가 닿지 못합니다"
    }
}

# tar 경로는 **실제로 있어야** 합니다. 앱은 없으면 조용히 다음 자리(복사본)로
# 넘어가므로, 오타를 여기서 잡지 않으면 **엉뚱한 판을 쓰고도 모릅니다**.
if ($IMAGE_TAR) {
    if (-not [System.IO.Path]::IsPathRooted($IMAGE_TAR)) {
        $problems += "ROBO_IMAGE_ARCHIVE 는 **절대 경로**여야 합니다: '$IMAGE_TAR'"
    } elseif (-not (Test-Path -LiteralPath $IMAGE_TAR -PathType Leaf)) {
        $problems += "ROBO_IMAGE_ARCHIVE 가 가리키는 파일이 없습니다: '$IMAGE_TAR'"
    }
}

# 포트는 숫자여야 합니다. 오타가 나면 컨테이너가 **없는 포트로** 붙으려 하고,
# 증상이 또 "unhealthy" 로 엉뚱하게 나옵니다.
foreach ($p in @{ 'ROBO_GRAPH_PG_PORT' = $GRAPH_PG_PORT
                  'ROBO_GRAPH_BOLT_PORT' = $GRAPH_BOLT_PORT }.GetEnumerator()) {
    if ($p.Value -and ($p.Value -notmatch '^[0-9]+$' -or
                       [int]$p.Value -lt 1 -or [int]$p.Value -gt 65535)) {
        $problems += "$($p.Key) 에 '$($p.Value)' 는 쓸 수 없습니다 — 1~65535 사이의 숫자여야 합니다"
    }
}

if ($problems) {
    ""
    "넣지 않았습니다. 아래를 고치고 다시 실행하십시오."
    ('-' * 64)
    $problems | ForEach-Object { "  · $_" }
    exit 1
}

# AI 키 다섯
foreach ($n in $AI_NAMES) { Set-User $n $AI_KEY }

# 이 PC 만 쓰는 난수 — **이미 있으면 그대로 둡니다**
#  (바꾸면 떠 있는 pdf2bpmn 컨테이너와 어긋납니다)
if (-not (Get-User 'PDF2BPMN_FACADE_KEY')) {
    $bytes = New-Object byte[] 48
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    Set-User 'PDF2BPMN_FACADE_KEY' ([Convert]::ToBase64String($bytes))
    $facadeNote = '새로 만들었습니다'
} else {
    $facadeNote = '이미 있어 그대로 둡니다'
}

# 중앙 DB 접속값 — **빈 칸은 건너뜁니다**(관리자가 이미 넣어 둔 값을 지우지 않습니다)
if ($GRAPH_HOST)     { Set-User 'ROBO_GRAPH_MODE' 'central'; Set-User 'ROBO_GRAPH_HOST' $GRAPH_HOST }
if ($GRAPH_PASSWORD) { Set-User 'ROBO_GRAPH_PASSWORD' $GRAPH_PASSWORD }
if ($ROLE_SECRET)    { Set-User 'AUTH_ROLE_SECRET' $ROLE_SECRET }
if ($JWT_SECRET)     { Set-User 'AUTH_JWT_SECRET' $JWT_SECRET }
# 포트는 비워 두면 건드리지 않습니다 — 앱이 기본값(5432·7687)을 씁니다
if ($GRAPH_PG_PORT)   { Set-User 'ROBO_GRAPH_PG_PORT'   $GRAPH_PG_PORT }
if ($GRAPH_BOLT_PORT) { Set-User 'ROBO_GRAPH_BOLT_PORT' $GRAPH_BOLT_PORT }
# tar 경로도 비우면 건드리지 않습니다 — 앱이 복사본 자리를 찾습니다
if ($IMAGE_TAR)       { Set-User 'ROBO_IMAGE_ARCHIVE'    $IMAGE_TAR }

# 시험 로그인
if ($DEV_LOGIN) {
    Set-User 'AUTH_DEV_LOGIN_ENABLED'  'true'
    Set-User 'AUTH_DEV_LOGIN_ID'       $DEV_ID
    Set-User 'AUTH_DEV_LOGIN_PASSWORD' $DEV_PASSWORD
    Set-User 'AUTH_DEV_LOGIN_EMPNO'    $DEV_EMPNO
    Set-User 'AUTH_DEV_LOGIN_NAME'     $DEV_NAME
    Set-User 'AUTH_DEV_LOGIN_ACCOUNTS' $DEV_ACCOUNTS
} else {
    # ⚠ 끌 때는 **여섯 개를 모두** 지웁니다. ENABLED 하나만 지워도 문은 닫히지만,
    #    나머지가 남아 있으면 다음 사람이 그걸 보고 다시 켭니다.
    foreach ($n in 'AUTH_DEV_LOGIN_ENABLED','AUTH_DEV_LOGIN_ID','AUTH_DEV_LOGIN_PASSWORD',
                   'AUTH_DEV_LOGIN_EMPNO','AUTH_DEV_LOGIN_NAME','AUTH_DEV_LOGIN_ACCOUNTS',
                   'AUTH_DEV_LOGIN_ALLOW_REMOTE') { Set-User $n $null }
}

# --- 결과 --------------------------------------------------------------------

Show-State $AI_NAMES "AI 키 다섯 — 같은 값이 들어갑니다"
Show-State @('PDF2BPMN_FACADE_KEY') "이 PC 가 만든 난수 ($facadeNote)"
Show-State @('ROBO_GRAPH_MODE','ROBO_GRAPH_HOST','ROBO_GRAPH_PASSWORD',
             'AUTH_ROLE_SECRET','AUTH_JWT_SECRET',
             'ROBO_GRAPH_PG_PORT','ROBO_GRAPH_BOLT_PORT') "중앙 DB 접속값 — 관리자가 주는 값"
Show-State @('ROBO_IMAGE_ARCHIVE') "부품 묶음 자리 (비면 §5 복사본을 찾습니다)"
if ($DEV_LOGIN) {
    Show-State @('AUTH_DEV_LOGIN_ENABLED','AUTH_DEV_LOGIN_ID','AUTH_DEV_LOGIN_PASSWORD',
                 'AUTH_DEV_LOGIN_EMPNO','AUTH_DEV_LOGIN_NAME','AUTH_DEV_LOGIN_ACCOUNTS') `
              "시험 로그인 — ⚠ 납품 때는 `$DEV_LOGIN = `$false"
}

""
('=' * 64)
"넣었습니다."
""
"다음 둘을 **반드시** 하십시오:"
"  1) **로그아웃·재로그인** — Windows 는 로그인할 때 환경변수를 읽습니다"
"  2) ⚠ **이 파일을 지웁니다** — 비밀이 평문으로 들어 있습니다"
""
"설치본을 깐 뒤에는 `.\robo-env.ps1 -Check` 로"
"**이 릴리스가 기동에 요구하는 이름**이 다 찼는지 볼 수 있습니다."
('=' * 64)
