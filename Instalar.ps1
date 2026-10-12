$ErrorActionPreference='Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Instala Python 3.11 o posterior y agrégalo al PATH.' }
}
& '.venv/Scripts/python.exe' -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias.' }
if (-not (Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
