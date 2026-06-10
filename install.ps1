param(
    [switch]$Symlink,
    [switch]$Copy,
    [string]$Dest,
    [switch]$Force,
    [switch]$DryRun,
    [switch]$List
)

$ErrorActionPreference = "Stop"
$KitDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BinDir = Join-Path $HOME ".local\bin"

$SkillArgs = @()
if ($Symlink) {
    $SkillArgs += "-Symlink"
} elseif (-not $Copy) {
    $SkillArgs += "-Copy"
}
if ($Copy) { $SkillArgs += "-Copy" }
if ($Dest) { $SkillArgs += @("-Dest", $Dest) }
if ($Force) { $SkillArgs += "-Force" }
if ($DryRun) { $SkillArgs += "-DryRun" }
if ($List) { $SkillArgs += "-List" }

& (Join-Path $KitDir "scripts\install-codex-skills.ps1") @SkillArgs

if ($List) {
    exit 0
}

if ($DryRun) {
    Write-Host "would install commands into $BinDir"
    exit 0
}

New-Item -ItemType Directory -Force -Path $BinDir | Out-Null

$GroundedCmd = Join-Path $BinDir "grounded-manual.cmd"
$AuditorCmd = Join-Path $BinDir "citation-auditor.cmd"
Set-Content -Encoding ASCII $GroundedCmd "@echo off`r`npython `"$KitDir\scripts\grounded_manual.py`" %*`r`n"
Set-Content -Encoding ASCII $AuditorCmd "@echo off`r`npython `"$KitDir\scripts\grounded_manual.py`" audit-claims %*`r`n"

Write-Host "Installed commands into $BinDir"
Write-Host "Run: grounded-manual doctor"
