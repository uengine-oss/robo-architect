<# Windows compatibility wrapper for the shared Electron build pipeline. #>
[CmdletBinding()]
param(
  [switch]$Installer,
  [switch]$SkipFrontend
)

$ErrorActionPreference = 'Stop'
$ArchitectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$WorkspaceRoot = if ($env:ROBO_WORKSPACE_DIR) {
  $env:ROBO_WORKSPACE_DIR
} else {
  Join-Path (Split-Path (Split-Path $ArchitectRoot -Parent) -Parent) 'robo-workspace'
}
$Runner = Join-Path $WorkspaceRoot 'scripts\robo.ps1'

if (-not (Test-Path $Runner)) {
  throw "robo-workspace launcher not found: $Runner. Set ROBO_WORKSPACE_DIR to the cloned robo-workspace directory."
}

$variant = if ($Installer) { 'installer' } else { 'unpacked' }
Write-Host "[architect] workspace: $WorkspaceRoot" -ForegroundColor Cyan
& $Runner build architect-electron $variant -SkipFrontend:$SkipFrontend
