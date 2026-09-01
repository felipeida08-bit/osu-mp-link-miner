$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$python = Join-Path $projectRoot ".venv\\Scripts\\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Crie a venv antes: python -m venv .venv"
}

& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name "osu-mp-link-miner" `
    --icon "assets\\osu-binoculars.ico" `
    --add-data "assets\\osu-binoculars.png;assets" `
    "gui.py"

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller falhou com codigo $LASTEXITCODE"
}

Write-Host "Executavel criado em: $projectRoot\\dist\\osu-mp-link-miner.exe"
