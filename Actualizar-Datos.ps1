param([string]$Desde='2021-01-01', [string]$Hasta=([DateTime]::UtcNow.AddDays(1).ToString('yyyy-MM-dd')), [switch]$SubirS3)
$ErrorActionPreference='Stop'
Set-Location $PSScriptRoot
$pythonProyecto=Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonProyecto)) { throw 'Ejecuta primero Instalar.ps1.' }
$argumentosProyecto=@('run_pipeline.py','--start',$Desde,'--end',$Hasta)
if ($SubirS3) { $argumentosProyecto+='--upload-s3' }
& $pythonProyecto @argumentosProyecto
if ($LASTEXITCODE -ne 0) { throw 'La actualización falló; revisa el mensaje anterior.' }
