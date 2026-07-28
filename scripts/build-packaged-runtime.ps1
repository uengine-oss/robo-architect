<#
.SYNOPSIS
Build the relocatable Windows Architect API runtime used by Electron.

.DESCRIPTION
The Docker-backed desktop release keeps the Architect API on the host so it
can access Windows project paths, local CLIs, and ConPTY. This script copies a
uv-managed CPython installation and installs dependencies into that copy.

Only `desktop/resources/runtime/architect` is replaced. Docker assets and the
release manifest remain owned by robo-workspace.
#>
[CmdletBinding()]
param(
  [string]$OutputRoot,
  [string]$PythonVersion = '3.11'
)

$ErrorActionPreference = 'Stop'
$ArchitectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RuntimeRoot = if ($OutputRoot) {
  [IO.Path]::GetFullPath($OutputRoot)
} else {
  Join-Path $ArchitectRoot 'desktop\resources\runtime'
}
$BundleRoot = Join-Path $RuntimeRoot 'architect'
$PythonRoot = Join-Path $BundleRoot 'python'
$AppRoot = Join-Path $BundleRoot 'app'
$RequirementsPath = Join-Path $BundleRoot 'requirements.lock.txt'

function Assert-ChildPath([string]$Parent, [string]$Candidate, [string]$Label) {
  $resolvedParent = [IO.Path]::GetFullPath($Parent).TrimEnd('\', '/')
  $resolvedCandidate = [IO.Path]::GetFullPath($Candidate)
  if (-not $resolvedCandidate.StartsWith("$resolvedParent\", [StringComparison]::OrdinalIgnoreCase)) {
    throw "$Label escapes its expected parent: $resolvedCandidate"
  }
}

function Invoke-Checked([string]$File, [string[]]$Arguments, [string]$WorkingDirectory) {
  Push-Location $WorkingDirectory
  try {
    & $File @Arguments
    if ($LASTEXITCODE -ne 0) {
      throw "$File failed with exit code $LASTEXITCODE"
    }
  } finally {
    Pop-Location
  }
}

function Copy-SourceTree([string]$Source, [string]$Destination) {
  New-Item -ItemType Directory -Force -Path $Destination | Out-Null
  $arguments = @(
    $Source,
    $Destination,
    '/E',
    '/XD', '__pycache__', '.pytest_cache', 'logs',
    '/XF', '*.pyc', '*.pyo',
    '/NFL', '/NDL', '/NJH', '/NJS', '/NP'
  )
  & robocopy.exe @arguments | Out-Null
  if ($LASTEXITCODE -gt 7) {
    throw "robocopy failed with exit code $LASTEXITCODE"
  }
}

Assert-ChildPath $RuntimeRoot $BundleRoot 'Architect bundle'
New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null
if (Test-Path $BundleRoot) {
  Remove-Item -LiteralPath $BundleRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $BundleRoot | Out-Null

Write-Host "[runtime] ensuring uv-managed CPython $PythonVersion" -ForegroundColor Cyan
Invoke-Checked 'uv.exe' @('python', 'install', $PythonVersion) $ArchitectRoot
$ManagedPython = (& uv.exe python find --managed-python $PythonVersion).Trim()
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $ManagedPython)) {
  throw "uv-managed Python $PythonVersion was not found"
}

$ManagedRoot = Split-Path $ManagedPython -Parent
Write-Host "[runtime] copying Python from $ManagedRoot" -ForegroundColor Cyan
Copy-SourceTree $ManagedRoot $PythonRoot
$BundledPython = Join-Path $PythonRoot 'python.exe'
if (-not (Test-Path $BundledPython)) {
  throw "bundled interpreter missing: $BundledPython"
}

Write-Host '[runtime] installing Architect dependencies' -ForegroundColor Cyan
Invoke-Checked 'uv.exe' @(
  'export',
  '--locked',
  '--no-dev',
  '--no-emit-project',
  '--output-file', $RequirementsPath
) $ArchitectRoot
Invoke-Checked 'uv.exe' @(
  'pip', 'install',
  '--python', $BundledPython,
  '--requirements', $RequirementsPath,
  '--require-hashes',
  '--break-system-packages',
  '--link-mode', 'copy',
  '--strict'
) $ArchitectRoot

Write-Host '[runtime] copying application sources' -ForegroundColor Cyan
Copy-SourceTree (Join-Path $ArchitectRoot 'api') (Join-Path $AppRoot 'api')
Copy-SourceTree (Join-Path $ArchitectRoot 'skills') (Join-Path $AppRoot 'skills')
Copy-Item -LiteralPath (Join-Path $ArchitectRoot 'pyproject.toml') -Destination $AppRoot
Copy-Item -LiteralPath (Join-Path $ArchitectRoot 'uv.lock') -Destination $AppRoot

$originalPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = $AppRoot
try {
  Invoke-Checked $BundledPython @(
    '-c',
    'import api.main'
  ) $AppRoot
} finally {
  $env:PYTHONPATH = $originalPythonPath
}

Write-Host "[runtime] ready: $BundleRoot" -ForegroundColor Green
