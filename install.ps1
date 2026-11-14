<#
.SYNOPSIS
Installs or updates agents_bundle on Windows.
.DESCRIPTION
Checks Python 3 and Bash, checks for command name conflicts in PATH,
installs agents_bundle and a .cmd shim into $HOME\.local\bin, and prints
the AI agent instructions (--agents-md).
#>
param(
    [string]$Name = $env:AGENTS_BUNDLE_NAME,
    [string]$Dir = $env:AGENTS_BUNDLE_INSTALL_DIR,
    [switch]$Yes,
    [switch]$Help
)
$ErrorActionPreference = 'Stop'

if ($Help) {
    Write-Host 'Usage: install.ps1 [-Name <cmd>] [-Dir <dir>] [-Yes] [-Help]'
    exit 0
}

$RepoMarker = 'agents_bundle-repo: vitalio/agents_bundle'
$RawUrl = if ($env:AGENTS_BUNDLE_UPDATE_URL) { $env:AGENTS_BUNDLE_UPDATE_URL } else { 'https://raw.githubusercontent.com/vitalio/agents_bundle/main/agents_bundle' }

if (-not (Get-Command python3 -ErrorAction SilentlyContinue) -and -not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error 'Python 3 is required but was not found in PATH.'
    exit 1
}
if (-not (Get-Command bash -ErrorAction SilentlyContinue) -and -not (Get-Command pwsh -ErrorAction SilentlyContinue) -and -not (Get-Command powershell -ErrorAction SilentlyContinue)) {
    Write-Error 'bash or PowerShell (pwsh) is required but was not found in PATH.'
    exit 1
}

function Test-OurBinary($PathToCheck) {
    if (-not $PathToCheck -or -not (Test-Path $PathToCheck)) { return $false }
    $content = Get-Content -Path $PathToCheck -Raw -ErrorAction SilentlyContinue
    return ($null -ne $content -and $content.Contains($RepoMarker))
}

if (-not $Name) {
    $Name = 'agents_bundle'
    $existing = Get-Command $Name -ErrorAction SilentlyContinue
    if ($existing -and -not (Test-OurBinary $existing.Source)) {
        Write-Host "Notice: '$Name' already exists at $($existing.Source) (another program)."
        $alt = 'agents_bundle_cli'
        if (-not $Yes) {
            $inputName = Read-Host "Enter an alternative command name [$alt]"
            $Name = if ($inputName) { $inputName } else { $alt }
        } else {
            $Name = $alt
        }
    }
}

if (-not $Dir) {
    $Dir = Join-Path $HOME '.local\bin'
}
New-Item -ItemType Directory -Force -Path $Dir | Out-Null
$PyTarget = Join-Path $Dir "$Name.py"
$ShTarget = Join-Path $Dir $Name
$CmdTarget = Join-Path $Dir "$Name.cmd"

Invoke-WebRequest -UseBasicParsing -Uri $RawUrl -OutFile $PyTarget
Copy-Item -Path $PyTarget -Destination $ShTarget -Force
$CmdContent = "@echo off`r`npython `"%~dp0$Name.py`" %*`r`n"
Set-Content -Path $CmdTarget -Value $CmdContent -Encoding ASCII

$UserPath = [Environment]::GetEnvironmentVariable('Path', 'User')
if ($UserPath -notlike "*$Dir*") {
    [Environment]::SetEnvironmentVariable('Path', "$Dir;$UserPath", 'User')
    $env:Path = "$Dir;$env:Path"
}

Write-Host '============================================================'
python $PyTarget --version
Write-Host "Installed to: $Dir ($Name)"
Write-Host "Tip: run '$Name --init' and '$Name' in any repo to build a context bundle."
Write-Host '============================================================'
