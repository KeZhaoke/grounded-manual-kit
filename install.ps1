$ErrorActionPreference = "Stop"

$KitDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" }
$SkillDir = Join-Path $CodexHome "skills"
$BinDir = Join-Path $HOME ".local\bin"

New-Item -ItemType Directory -Force -Path $SkillDir | Out-Null
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null

$GroundedSkill = Join-Path $SkillDir "grounded-manual"
$AuditorSkill = Join-Path $SkillDir "citation-auditor"
Remove-Item -Force -Recurse -ErrorAction SilentlyContinue $GroundedSkill
Remove-Item -Force -Recurse -ErrorAction SilentlyContinue $AuditorSkill
Copy-Item -Recurse (Join-Path $KitDir "skills\grounded-manual") $GroundedSkill
Copy-Item -Recurse (Join-Path $KitDir "skills\citation-auditor") $AuditorSkill

$GroundedCmd = Join-Path $BinDir "grounded-manual.cmd"
$AuditorCmd = Join-Path $BinDir "citation-auditor.cmd"
Set-Content -Encoding ASCII $GroundedCmd "@echo off`r`npython `"$KitDir\scripts\grounded_manual.py`" %*`r`n"
Set-Content -Encoding ASCII $AuditorCmd "@echo off`r`npython `"$KitDir\scripts\grounded_manual.py`" audit-claims %*`r`n"

Write-Host "Installed skills into $SkillDir"
Write-Host "Installed commands into $BinDir"
Write-Host "Run: grounded-manual doctor"

