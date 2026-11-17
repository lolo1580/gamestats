param(
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$PyLauncher = Get-Command py -ErrorAction SilentlyContinue
if ($PyLauncher) {
    & $PyLauncher.Source -3 -m venv .venv-build
} else {
    & python -m venv .venv-build
}

$VenvPython = Join-Path $Root ".venv-build\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    throw "Python virtual environment creation failed."
}

& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r requirements.txt pyinstaller
if ($LASTEXITCODE -ne 0) {
    throw "Python dependencies installation failed."
}

& $VenvPython -m PyInstaller --noconfirm --clean GameStatsAgent.spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed."
}

if ($SkipInstaller) {
    Write-Host "Executable built: $Root\dist\GameStatsAgent\GameStatsAgent.exe"
    exit 0
}

$IsccCandidates = @()
if (${env:ProgramFiles(x86)}) {
    $IsccCandidates += (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe")
}
if ($env:ProgramFiles) {
    $IsccCandidates += (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
}
$Iscc = $IsccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Iscc) {
    throw "Inno Setup 6 is required. Install it from https://jrsoftware.org/isinfo.php, then rerun this script."
}

& $Iscc installer.iss
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup build failed."
}

Write-Host "Installer built: $Root\dist\GameStatsAgentSetup.exe"
