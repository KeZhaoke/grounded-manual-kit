param(
    [switch]$Symlink,
    [switch]$Copy,
    [string]$Dest,
    [switch]$Force,
    [switch]$DryRun,
    [switch]$List,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

function Show-Usage {
    @"
Usage: scripts/install-codex-skills.ps1 [options]

Install this repository's skills into the Codex global skills directory.

Options:
  -Symlink        Install skills as symlinks (default)
  -Copy           Copy skills as snapshots
  -Dest DIR       Install into DIR (default: `${CODEX_HOME:-`$HOME/.codex}/skills)
  -Force          Replace an existing conflicting target
  -DryRun         Show what would change without writing anything
  -List           List discovered skills and target status
  -Help           Show this help
"@
}

function Resolve-MaybeMissing([string]$Path) {
    $full = [System.IO.Path]::GetFullPath($Path)
    return $full.TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
}

function Get-ExistingItem([string]$Path) {
    return Get-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
}

function Test-ExistingPath([string]$Path) {
    return $null -ne (Get-ExistingItem $Path)
}

function Get-MetadataValue([string]$File, [string]$Key) {
    if (-not (Test-Path -LiteralPath $File -PathType Leaf)) {
        return $null
    }

    foreach ($line in Get-Content -LiteralPath $File) {
        $parts = $line.Split("=", 2)
        if ($parts.Count -eq 2 -and $parts[0] -eq $Key) {
            return $parts[1]
        }
    }

    return $null
}

function New-TempPath([string]$Destination, [string]$Prefix) {
    $base = Join-Path $Destination ".$Prefix.$PID"
    $candidate = $base
    $i = 0

    while (Test-ExistingPath $candidate) {
        $i += 1
        $candidate = "$base.$i"
    }

    return $candidate
}

function Get-LinkTargetPath([string]$Target) {
    $item = Get-Item -LiteralPath $Target -Force
    $raw = $item.Target
    if ($raw -is [array]) {
        $raw = $raw[0]
    }
    if ([System.IO.Path]::IsPathRooted($raw)) {
        return Resolve-MaybeMissing $raw
    }
    return Resolve-MaybeMissing (Join-Path (Split-Path -Parent $Target) $raw)
}

function Get-TargetDescription([string]$Target) {
    $item = Get-ExistingItem $Target
    if (-not $item) {
        return "missing"
    }

    if ($item.LinkType -eq "SymbolicLink") {
        return "symlink -> $(Get-LinkTargetPath $Target)"
    }

    if ($item.PSIsContainer) {
        $metadata = Join-Path $Target ".codex-skill-source"
        $source = Get-MetadataValue $metadata "source_skill_path"
        $mode = Get-MetadataValue $metadata "mode"
        if ($source) {
            if ($mode) {
                return "directory copied from $source ($mode)"
            }
            return "directory copied from $source"
        }
        return "directory with unknown source"
    }

    return "file or special path"
}

function Write-CopyMetadata([string]$Staged, [string]$SourceReal, [string]$KitDirReal) {
    $installedAt = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    $metadata = @(
        "source_repo=$KitDirReal",
        "source_skill_path=$SourceReal",
        "mode=copy",
        "installed_at=$installedAt",
        "installer=install-codex-skills.ps1"
    )
    Set-Content -LiteralPath (Join-Path $Staged ".codex-skill-source") -Value $metadata -Encoding ASCII
}

function Replace-Target([string]$Staged, [string]$Target, [string]$Destination) {
    if (Test-ExistingPath $Target) {
        $backup = New-TempPath $Destination "$(Split-Path -Leaf $Target).old"
        Move-Item -LiteralPath $Target -Destination $backup
        try {
            Move-Item -LiteralPath $Staged -Destination $Target
            Remove-Item -LiteralPath $backup -Recurse -Force
        } catch {
            if (Test-ExistingPath $backup) {
                Move-Item -LiteralPath $backup -Destination $Target
            }
            throw
        }
    } else {
        Move-Item -LiteralPath $Staged -Destination $Target
    }
}

function Stop-Conflict([string]$SkillName, [string]$SourceReal, [string]$Target) {
    Write-Error @"
conflict: $Target already exists for skill '$SkillName'
current: $(Get-TargetDescription $Target)
source:  $SourceReal
use -Force to replace it
"@
}

function Assert-SkillAllowed($SkillDir) {
    $SkillName = $SkillDir.Name
    if ($SkillName -notmatch '^[A-Za-z0-9._-]+$') {
        throw "Unsafe skill name: $SkillName"
    }

    $SourceReal = (Resolve-Path -LiteralPath $SkillDir.FullName).Path
    $Target = Join-Path $Dest $SkillName

    if (-not (Test-ExistingPath $Target)) {
        return
    }

    $Item = Get-ExistingItem $Target
    if ($Item.LinkType -eq "SymbolicLink") {
        $Current = Get-LinkTargetPath $Target
        if ($Mode -eq "symlink" -and $Current -eq $SourceReal) {
            return
        }
        if (-not $Force) {
            Stop-Conflict $SkillName $SourceReal $Target
        }
    } elseif ($Item.PSIsContainer) {
        $Metadata = Join-Path $Target ".codex-skill-source"
        $Current = Get-MetadataValue $Metadata "source_skill_path"
        if ($Mode -eq "copy" -and $Current -eq $SourceReal) {
            return
        }
        if (-not $Force) {
            Stop-Conflict $SkillName $SourceReal $Target
        }
    } elseif (-not $Force) {
        Stop-Conflict $SkillName $SourceReal $Target
    }
}

function Test-RefreshCopy([string]$Target, [string]$SourceReal) {
    if ($Mode -ne "copy") {
        return $false
    }

    $Item = Get-ExistingItem $Target
    if (-not $Item -or -not $Item.PSIsContainer) {
        return $false
    }

    $Metadata = Join-Path $Target ".codex-skill-source"
    $Current = Get-MetadataValue $Metadata "source_skill_path"
    return $Current -eq $SourceReal
}

if ($Help) {
    Show-Usage
    exit 0
}

if ($Copy -and $Symlink) {
    throw "Choose only one of -Copy or -Symlink."
}

$Mode = if ($Copy) { "copy" } else { "symlink" }
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$KitDir = Resolve-MaybeMissing (Join-Path $ScriptDir "..")
$KitDirReal = (Resolve-Path -LiteralPath $KitDir).Path
$SkillsDirReal = (Resolve-Path -LiteralPath (Join-Path $KitDir "skills")).Path

if (-not $Dest) {
    $CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" }
    $Dest = Join-Path $CodexHome "skills"
}
$Dest = Resolve-MaybeMissing $Dest

$SkillsPrefix = $SkillsDirReal.TrimEnd(
    [System.IO.Path]::DirectorySeparatorChar,
    [System.IO.Path]::AltDirectorySeparatorChar
) + [System.IO.Path]::DirectorySeparatorChar
if (
    $Dest.Equals($SkillsDirReal, [System.StringComparison]::OrdinalIgnoreCase) -or
    $Dest.StartsWith($SkillsPrefix, [System.StringComparison]::OrdinalIgnoreCase)
) {
    throw "Destination must not be inside source skills directory: $SkillsDirReal"
}

$SkillDirs = Get-ChildItem -LiteralPath (Join-Path $KitDir "skills") -Directory |
    Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName "SKILL.md") } |
    Sort-Object Name

if (-not $SkillDirs) {
    throw "No skills found under $(Join-Path $KitDir "skills")"
}

if (-not $List) {
    foreach ($SkillDir in $SkillDirs) {
        Assert-SkillAllowed $SkillDir
    }
}

if (-not $DryRun -and -not $List) {
    New-Item -ItemType Directory -Force -Path $Dest | Out-Null
}

if ($List) {
    Write-Host "Skills from $(Join-Path $KitDir "skills")"
    Write-Host "Destination: $Dest"
}

foreach ($SkillDir in $SkillDirs) {
    $SkillName = $SkillDir.Name
    if ($SkillName -notmatch '^[A-Za-z0-9._-]+$') {
        throw "Unsafe skill name: $SkillName"
    }

    $SourceReal = (Resolve-Path -LiteralPath $SkillDir.FullName).Path
    $Target = Join-Path $Dest $SkillName

    if ($List) {
        Write-Host "- $SkillName"
        Write-Host "  source: $SourceReal"
        Write-Host "  target: $Target"
        Write-Host "  status: $(Get-TargetDescription $Target)"
        continue
    }

    $TargetExists = Test-ExistingPath $Target
    if ($TargetExists) {
        $Item = Get-ExistingItem $Target
        if ($Item.LinkType -eq "SymbolicLink") {
            $Current = Get-LinkTargetPath $Target
            if ($Mode -eq "symlink" -and $Current -eq $SourceReal) {
                Write-Host "ok: $SkillName already linked to $SourceReal"
                continue
            }
            if (-not $Force) {
                Stop-Conflict $SkillName $SourceReal $Target
            }
        } elseif ($Item.PSIsContainer) {
            $Metadata = Join-Path $Target ".codex-skill-source"
            $Current = Get-MetadataValue $Metadata "source_skill_path"
            if ($Mode -eq "copy" -and $Current -eq $SourceReal) {
                # Refresh same-source copies so deployments pick up current skill files.
            } elseif (-not $Force) {
                Stop-Conflict $SkillName $SourceReal $Target
            }
        } elseif (-not $Force) {
            Stop-Conflict $SkillName $SourceReal $Target
        }
    }

    if ($DryRun) {
        if (Test-RefreshCopy $Target $SourceReal) {
            Write-Host "would refresh: $Target with copy from $SourceReal"
        } elseif ($TargetExists) {
            Write-Host "would replace: $Target with $Mode from $SourceReal"
        } else {
            Write-Host "would install: $Target with $Mode from $SourceReal"
        }
        continue
    }

    $Refresh = Test-RefreshCopy $Target $SourceReal
    $Staged = New-TempPath $Dest "$SkillName.tmp"
    if ($Mode -eq "symlink") {
        New-Item -ItemType SymbolicLink -Path $Staged -Target $SourceReal | Out-Null
    } else {
        Copy-Item -LiteralPath $SourceReal -Destination $Staged -Recurse
        Write-CopyMetadata $Staged $SourceReal $KitDirReal
    }

    Replace-Target $Staged $Target $Dest
    if ($Refresh) {
        Write-Host "refreshed: $SkillName -> $Target ($Mode)"
    } else {
        Write-Host "installed: $SkillName -> $Target ($Mode)"
    }
}

if (-not $List -and -not $DryRun) {
    Write-Host "Installed skills into $Dest"
    Write-Host "Restart Codex to pick up new skills."
}
