<#
publish-images.ps1 — **인터넷 되는 PC 에서** CI 가 구운 이미지를 묶어 GitHub Release 에 올린다.
운영-업데이트-가이드.md §2. 사내 서버는 ghcr 에 못 닿고 github Release 는 curl 로 받는다.

  .\publish-images.ps1 -Tag posco-web-images-2026-11-20                 # web · architect-api · analyzer (기본)
  .\publish-images.ps1 -Tag … -Images robo-posco-architect-api:delivery -Asset api.tar
  .\publish-images.ps1 -Tag … -DryRun                                    # 묶기까지만 (올리지 않는다)

준비  Docker Desktop 이 떠 있다 · gh 가 로그인돼 있다(gh auth status) · Actions "posco-web images" 가 초록
결과  Release <Tag> (prerelease) 에 <Asset> 과 <Asset>.sha256 — 서버의 update.sh 가 둘을 받는다
      묶음이 1.9 GB 를 넘으면(GitHub Release 자산 한 개 상한 2 GiB) <Asset>.part00… 로 나눠 올리고
      조각 목록 <Asset>.parts 를 같이 올린다 — update.sh 가 받아 이어 붙인 뒤 sha256 으로 대조한다.
⚠ Release 는 공개 저장소에 올라간다 — 이미지가 이미 public 이라 새로 드러나는 것은 없다.
#>
param(
  [Parameter(Mandatory)][string]$Tag,
  # 열한 장 전부 :delivery (2026-11-19 밤부터 — compose 가 열한 장 모두 :delivery 를 본다)
  [string[]]$Images = @('robo-posco-web:delivery', 'robo-posco-architect-api:delivery', 'robo-posco-analyzer:delivery',
                        'robo-posco-authority:delivery', 'robo-posco-graph-db:delivery', 'robo-posco-graph-bolt:delivery',
                        'robo-posco-fabric:delivery', 'robo-posco-catalog:delivery', 'robo-posco-parser:delivery',
                        'robo-posco-gateway:delivery', 'robo-posco-wireframe:delivery'),
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

# GitHub Release 자산은 한 개에 2 GiB 까지다 — 넘으면 조각으로(analyzer 에 재채점 모델이 들어간 뒤로 넘는다)
[long]$PartBytes = 1900MB
$uploads = @($tar)
if ($size -gt $PartBytes) {
  $names = @()
  $in = [IO.File]::OpenRead($tar)
  try {
    $buf = New-Object byte[] (8MB)
    $i = 0
    while ($in.Position -lt $in.Length) {
      $name = '{0}.part{1:D2}' -f $Asset, $i
      $o = [IO.File]::Create((Join-Path $out $name))
      try {
        $left = [Math]::Min([long]$PartBytes, [long]($in.Length - $in.Position))
        while ($left -gt 0) {
          $n = $in.Read($buf, 0, [int][Math]::Min([long]$buf.Length, [long]$left))
          $o.Write($buf, 0, $n); $left -= $n
        }
      } finally { $o.Close() }
      $names += $name; $i++
    }
  } finally { $in.Close() }
  [IO.File]::WriteAllText((Join-Path $out "$Asset.parts"), (($names -join "`n") + "`n"))
  $uploads = @($names | ForEach-Object { Join-Path $out $_ }) + @(Join-Path $out "$Asset.parts")
  Write-Host ("조각  {0}개 ({1})" -f $names.Count, ($names -join ' '))
}

if ($DryRun) { Write-Host 'DryRun — 올리지 않는다'; return }

$notes = "posco-web 이미지 묶음 · $($Images -join ' · ')`n`nSHA256 $hash`n`n서버: bash update.sh $Tag $Asset"
gh release view $Tag --repo $Repo *> $null
if ($LASTEXITCODE -eq 0) {
  gh release upload $Tag @uploads "$tar.sha256" --repo $Repo --clobber
} else {
  gh release create $Tag @uploads "$tar.sha256" --repo $Repo --target main --prerelease `
    --title "posco-web images $Tag" --notes $notes
}
if ($LASTEXITCODE) { throw 'Release 에 올리지 못했다' }

$first = Split-Path -Leaf $uploads[0]
$url = "https://github.com/$Repo/releases/download/$Tag/$first"
$head = curl.exe -sIL -m 30 $url | Select-String -Pattern '^(HTTP|content-length)' | Select-Object -Last 2
Write-Host "확인  $url"
$head | ForEach-Object { Write-Host "  $_" }
Write-Host "서버  bash update.sh $Tag $Asset"
Remove-Item $tar, "$tar.sha256"
Get-ChildItem $out -Filter "$Asset.part*" -ErrorAction SilentlyContinue | Remove-Item
