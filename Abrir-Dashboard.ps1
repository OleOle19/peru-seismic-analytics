$ErrorActionPreference='Stop'
$informeProyecto=Join-Path $PSScriptRoot 'powerbi/Seismic.pbix'
if (-not (Test-Path -LiteralPath $informeProyecto)) { $informeProyecto=Join-Path $PSScriptRoot 'powerbi/Seismic.pbip' }
$ejecutablePowerBI='C:/Program Files/Microsoft Power BI Desktop/bin/PBIDesktop.exe'
if (-not (Test-Path -LiteralPath $ejecutablePowerBI)) { throw 'Instala Power BI Desktop desde Microsoft.' }
Start-Process -FilePath $ejecutablePowerBI -ArgumentList ('"'+$informeProyecto+'"')
