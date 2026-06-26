<#
  dev-desktop.ps1 — robo-architect 데스크톱 풀스택을 한 방에 기동 (Windows)

  무엇을 하나 (이번 세션 라이브 검증 절차의 코드화):
    0) 전제 점검            : uv·npm·java·node·Neo4j(7687) 확인
    1) 서브모듈 + 의존성    : git submodule update --init --recursive, venv 점검
    2) co-locate 빌드       : node scripts/build-desktop-frontend.mjs  (-SkipBuild 로 생략)
    3) 백엔드 4종 병렬 기동 : analyzer 5502 · catalog 5503 · antlr 8081 · gateway 9000 (헬스 대기)
    4) Electron 데스크톱    : ROBO_BACKEND_DIR 지정 + ELECTRON_RUN_AS_NODE 해제 + npm run dev (포그라운드)
    5) 종료 정리            : Electron 창 닫히면 백엔드 4종 자동 종료

  내장된 환경별 픽스(전부 이번 세션에 근본확인):
    - backend.ts 는 `python -m uvicorn`(앱제어정책이 uvicorn.exe 차단=os err 4551 회피) — desktop 코드측 수정 전제
    - architect api spawn 에 ROBO_BACKEND_DIR 필수(폴백이 Mac 경로)
    - ELECTRON_RUN_AS_NODE 해제(설정 시 electron 이 node 로 떠 죽음)
    - gateway 는 자체 mvnw 버그(distributionUrl) → 캐시된 maven mvn.cmd 사용
    - antlr 는 SERVER_PORT=8081(게이트웨이 기대치; mvn 기본 8080 아님)
    - robo-architect/.env 필요(없으면 Neo4j 기본비번→AuthError) — 존재만 점검, 비번은 스크립트에 안 박음

  사용:
    pwsh -File scripts\dev-desktop.ps1            # 빌드 후 풀스택+Electron
    pwsh -File scripts\dev-desktop.ps1 -SkipBuild # 빌드 생략(빠른 재기동)
    pwsh -File scripts\dev-desktop.ps1 -Stop      # 떠 있는 스택만 정리
    pwsh -File scripts\dev-desktop.ps1 -NoElectron# 백엔드만 기동(Electron 제외)
#>
[CmdletBinding()]
param(
  [switch]$SkipBuild,
  [switch]$NoElectron,
  [switch]$Stop
)

$ErrorActionPreference = 'Stop'

# ── 경로 해석 ────────────────────────────────────────────────────────────────
$Arch      = (Resolve-Path "$PSScriptRoot\..").Path           # robo-architect
$Workspace = (Resolve-Path "$Arch\..").Path                   # d:\work\robo\project
$Analyzer  = Join-Path $Workspace 'robo-data-analyzer'
$Antlr     = Join-Path $Workspace 'antlr-code-parser'
$Gateway   = Join-Path $Workspace 'api-gateway'
$Catalog   = Join-Path $Arch 'robo-analyzer\robo-data-catalog'
$Desktop   = Join-Path $Arch 'desktop'
$LogDir    = Join-Path $Arch '.dev-logs'

$Ports = @{ analyzer = 5502; catalog = 5503; antlr = 8081; gateway = 9000 }

function Info($m){ Write-Host "[dev] $m" -ForegroundColor Cyan }
function Ok($m)  { Write-Host "[dev] OK  $m" -ForegroundColor Green }
function Warn($m){ Write-Host "[dev] !   $m" -ForegroundColor Yellow }
function Die($m) { Write-Host "[dev] X   $m" -ForegroundColor Red; exit 1 }

# ── 스택 정리 (포트 점유 프로세스 + electron) ──────────────────────────────────
function Stop-Stack {
  foreach($p in $Ports.Values){
    try {
      Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique |
        ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
    } catch {}
  }
  # 우리 dev Electron 은 electron.exe (VS Code 는 Code.exe 라 안 건드림)
  Get-Process electron -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
}

if ($Stop) { Info '스택 정리 중...'; Stop-Stack; Ok '정리 완료'; exit 0 }

# ── 포트 리스닝 대기 (헬스) ───────────────────────────────────────────────────
function Wait-Port([int]$Port, [string]$Name, [int]$TimeoutSec = 120) {
  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  while ((Get-Date) -lt $deadline) {
    try {
      $c = New-Object System.Net.Sockets.TcpClient
      $c.Connect('127.0.0.1', $Port); $c.Close()
      Ok "$Name (port $Port) ready"; return $true
    } catch { Start-Sleep -Milliseconds 1500 }
  }
  Warn "$Name (port $Port) 가 ${TimeoutSec}s 안에 안 떴음 — 로그 확인: $LogDir\$Name.err.log"
  return $false
}

# ── 백엔드 1종 기동 (Start-Process -PassThru) ────────────────────────────────
function Start-Backend([string]$Name, [string]$Cwd, [string]$File, [string[]]$ArgList) {
  $out = Join-Path $LogDir "$Name.out.log"
  $err = Join-Path $LogDir "$Name.err.log"
  Info "start $Name  ($File)"
  return Start-Process -FilePath $File -ArgumentList $ArgList -WorkingDirectory $Cwd `
    -RedirectStandardOutput $out -RedirectStandardError $err `
    -NoNewWindow -PassThru
}

# ── 0) 전제 점검 ──────────────────────────────────────────────────────────────
Info '0) 전제 점검'
foreach($t in 'uv','npm','node','java'){ if(-not (Get-Command $t -ErrorAction SilentlyContinue)){ Die "'$t' PATH 에 없음" } }
if (-not (Get-NetTCPConnection -LocalPort 7687 -State Listen -ErrorAction SilentlyContinue)) {
  Die 'Neo4j(7687) 미기동 — Neo4j Desktop 을 먼저 켜세요 (DB=neo4j, 비번 .env 일치).'
}
if (-not (Test-Path (Join-Path $Arch '.env'))) {
  Warn "robo-architect\.env 없음 → architect api 가 Neo4j 기본비번으로 떨어져 '분석 데이터 없음' 가능."
  Warn '  필요 키: NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD / NEO4J_DATABASE=neo4j / ANALYZER_NEO4J_DATABASE=neo4j'
}
Ok 'tooling + Neo4j 확인'

# ── 1) 서브모듈 + venv ────────────────────────────────────────────────────────
Info '1) 서브모듈 동기화 + venv 점검'
Push-Location $Arch
try { git submodule update --init --recursive } catch { Warn "submodule update 경고: $_" }
Pop-Location
$AnalyzerPy = Join-Path $Analyzer '.venv\Scripts\python.exe'
$CatalogPy  = Join-Path $Catalog  '.venv\Scripts\python.exe'
if (-not (Test-Path $AnalyzerPy)) { Die "analyzer venv 없음: $AnalyzerPy  (먼저: cd $Analyzer; python -m venv .venv; .venv\Scripts\python -m pip install -r requirements.txt)" }
if (-not (Test-Path $CatalogPy))  { Die "catalog venv 없음: $CatalogPy  (먼저: cd $Catalog; python -m venv .venv; .venv\Scripts\python -m pip install -r requirements.txt)" }
Ok 'venv 확인 (analyzer · catalog)'

# ── 2) co-locate 빌드 ─────────────────────────────────────────────────────────
if ($SkipBuild) { Warn '2) 빌드 생략 (-SkipBuild) — frontend\dist 기존본 사용' }
else {
  Info '2) co-locate 빌드 (host + analyzer remote) — 1~2분'
  Push-Location $Arch
  try { & node 'scripts\build-desktop-frontend.mjs'; if($LASTEXITCODE -ne 0){ Die '빌드 실패' } }
  finally { Pop-Location }
  Ok '빌드 완료'
}

# ── 3) 백엔드 4종 기동 ────────────────────────────────────────────────────────
Info '3) 백엔드 4종 기동'
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }
Stop-Stack   # 이전 잔여 정리(재실행 안전)
Start-Sleep -Milliseconds 500

$procs = @()
$procs += Start-Backend 'analyzer' $Analyzer $AnalyzerPy @('-m','uvicorn','main:app','--host','127.0.0.1','--port','5502')
$procs += Start-Backend 'catalog'  $Catalog  $CatalogPy  @('-m','uvicorn','main:app','--host','127.0.0.1','--port','5503')

# antlr: SERVER_PORT=8081 을 spawn 시점에만 주입(자식이 캡처, 직후 해제)
$env:SERVER_PORT = '8081'
$procs += Start-Backend 'antlr' $Antlr (Join-Path $Antlr 'mvnw.cmd') @('-q','spring-boot:run')
Remove-Item Env:SERVER_PORT -ErrorAction SilentlyContinue

# gateway: 자체 mvnw 버그 → 캐시된 maven mvn.cmd 탐색
$mvn = Get-ChildItem "$env:USERPROFILE\.m2\wrapper\dists\apache-maven-*\*\bin\mvn.cmd" -ErrorAction SilentlyContinue |
       Select-Object -First 1 -ExpandProperty FullName
if (-not $mvn) { Warn 'gateway: 캐시 maven(mvn.cmd) 못 찾음 → gateway 자체 mvnw.cmd 시도(버그 가능)'; $mvn = Join-Path $Gateway 'mvnw.cmd' }
$procs += Start-Backend 'gateway' $Gateway $mvn @('-q','spring-boot:run')

# 헬스 대기 (python 은 빨리, spring 은 느림)
Wait-Port 5502 'analyzer' 60  | Out-Null
Wait-Port 5503 'catalog'  60  | Out-Null
Wait-Port 8081 'antlr'    120 | Out-Null
Wait-Port 9000 'gateway'  120 | Out-Null

# ── 4) Electron ───────────────────────────────────────────────────────────────
if ($NoElectron) {
  Ok '백엔드 기동 완료 (-NoElectron). 종료: scripts\dev-desktop.ps1 -Stop'
  Info "로그: $LogDir"
  exit 0
}

Info '4) Electron 데스크톱 기동 (창 닫으면 백엔드 자동 종료)'
$env:ROBO_BACKEND_DIR = $Arch
$env:ROBO_GATEWAY_URL = 'http://127.0.0.1:9000'
Remove-Item Env:ELECTRON_RUN_AS_NODE -ErrorAction SilentlyContinue

try {
  Push-Location $Desktop
  & npm.cmd run dev          # 포그라운드 — 창 닫힐 때까지 블록
} finally {
  Pop-Location
  Info '5) Electron 종료 감지 → 백엔드 정리'
  Stop-Stack
  Ok '전체 종료 완료'
}
