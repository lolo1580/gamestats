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

$Dist = Join-Path $Root "dist"
$Portable = Join-Path $Dist "GameStatsAgent-portable.zip"
Compress-Archive -Path (Join-Path $Dist "GameStatsAgent\*") `
    -DestinationPath $Portable -Force

$Downloads = Join-Path (Split-Path -Parent $Root) "downloads"
New-Item -ItemType Directory -Force -Path $Downloads | Out-Null

if ($SkipInstaller) {
    Copy-Item $Portable $Downloads -Force
    Write-Host "Executable built: $Dist\GameStatsAgent\GameStatsAgent.exe"
    Write-Host "Published: $Downloads\GameStatsAgent-portable.zip"
    exit 0
}

$IsccCandidates = @()
if (${env:ProgramFiles(x86)}) {
    $IsccCandidates += (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe")
}
if ($env:ProgramFiles) {
    $IsccCandidates += (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
}
if ($env:LOCALAPPDATA) {
    $IsccCandidates += (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
}
$Iscc = $IsccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Iscc) {
    throw "Inno Setup 6 is required. Install it with 'winget install JRSoftware.InnoSetup' or from https://jrsoftware.org/isinfo.php, then rerun this script."
}

& $Iscc installer.iss
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup build failed."
}

$Installer = Join-Path $Dist "GameStatsAgentSetup.exe"
Copy-Item $Installer $Downloads -Force
Copy-Item $Portable $Downloads -Force

Write-Host "Installer built: $Installer"
Write-Host "Published: $Downloads\GameStatsAgentSetup.exe"
Write-Host "Published: $Downloads\GameStatsAgent-portable.zip"
