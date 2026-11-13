<#
publish-images.ps1 — **인터넷 되는 PC 에서** CI 가 구운 이미지를 묶어 GitHub Release 에 올린다.
운영-업데이트-가이드.md §2. 사내 서버는 ghcr 에 못 닿고 github Release 는 curl 로 받는다.

  .\publish-images.ps1 -Tag posco-web-images-2026-11-20                 # web · architect-api (기본)
  .\publish-images.ps1 -Tag … -Images robo-posco-architect-api:delivery -Asset api.tar
  .\publish-images.ps1 -Tag … -DryRun                                    # 묶기까지만 (올리지 않는다)

준비  Docker Desktop 이 떠 있다 · gh 가 로그인돼 있다(gh auth status) · Actions "posco-web images" 가 초록
결과  Release <Tag> (prerelease) 에 <Asset> 과 <Asset>.sha256 — 서버의 update.sh 가 둘을 받는다
⚠ Release 는 공개 저장소에 올라간다 — 이미지가 이미 public 이라 새로 드러나는 것은 없다.
#>
param(
  [Parameter(Mandatory)][string]$Tag,
  [string[]]$Images = @('robo-posco-web:delivery', 'robo-posco-architect-api:delivery'),
  [string]$Asset = 'images.tar',
  [string]$Repo = 'uengine-oss/robo-architect',
  [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
$G = 'ghcr.io/uengine-oss'
$refs = $Images | ForEach-Object { "$G/$_" }

docker info --format '{{.ServerVersion}}' *> $null
if ($LASTEXITCODE) { throw 'Docker 엔진이 안 떠 있다 — Docker Desktop 을 켠다' }

foreach ($r in $refs) {
  docker pull $r
  if ($LASTEXITCODE) { throw "받지 못했다: $r" }
  $rev = docker image inspect $r --format '{{index .Config.Labels "org.opencontainers.image.revision"}}'
  Write-Host ("  {0}  revision {1}" -f $r, $rev)
}

$out = Join-Path $env:TEMP "robo-posco-$Tag"
New-Item -ItemType Directory -Force $out | Out-Null
$tar = Join-Path $out $Asset
Remove-Item $tar, "$tar.sha256" -ErrorAction SilentlyContinue
docker save -o $tar @refs
if ($LASTEXITCODE) { throw 'docker save 실패' }
$hash = (Get-FileHash $tar -Algorithm SHA256).Hash.ToLower()
# 서버의 sha256sum -c 가 읽는다 — LF 로 쓴다
[IO.File]::WriteAllText("$tar.sha256", "$hash  $Asset`n")
$size = (Get-Item $tar).Length
Write-Host ("묶음  {0}  {1:N0} B  sha256 {2}" -f $tar, $size, $hash.Substring(0, 8))

if ($DryRun) { Write-Host 'DryRun — 올리지 않는다'; return }

$notes = "posco-web 이미지 묶음 · $($Images -join ' · ')`n`nSHA256 $hash`n`n서버: bash update.sh $Tag $Asset"
gh release view $Tag --repo $Repo *> $null
if ($LASTEXITCODE -eq 0) {
  gh release upload $Tag $tar "$tar.sha256" --repo $Repo --clobber
} else {
  gh release create $Tag $tar "$tar.sha256" --repo $Repo --target posco-web --prerelease `
    --title "posco-web images $Tag" --notes $notes
}
if ($LASTEXITCODE) { throw 'Release 에 올리지 못했다' }

$url = "https://github.com/$Repo/releases/download/$Tag/$Asset"
$head = curl.exe -sIL -m 30 $url | Select-String -Pattern '^(HTTP|content-length)' | Select-Object -Last 2
Write-Host "확인  $url"
$head | ForEach-Object { Write-Host "  $_" }
Write-Host "서버  bash update.sh $Tag $Asset"
Remove-Item $tar, "$tar.sha256"
