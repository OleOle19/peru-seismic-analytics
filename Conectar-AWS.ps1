param(
    [Parameter(Mandatory=$true)][string]$Bucket,
    [string]$Region='us-east-2'
)
$ErrorActionPreference='Stop'
$cliProyecto='C:/Program Files/Amazon/AWSCLIV2/aws.exe'
if (-not (Test-Path -LiteralPath $cliProyecto)) { throw 'Instala AWS CLI v2 primero.' }
if ($Bucket -notmatch '^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$') { throw 'El nombre del bucket no es válido.' }
if ($Region -notmatch '^[a-z]{2}-[a-z]+-\d+$') { throw 'La región no es válida.' }

# The user authorizes the temporary session in the browser. No access keys are requested.
& $cliProyecto login --profile seismic-login --region $Region
if ($LASTEXITCODE -ne 0) { throw 'No se completó la autorización de AWS en el navegador.' }

# Use the standard process provider so boto3 can use the temporary CLI session.
$proveedorProyecto='"'+$cliProyecto+'" configure export-credentials --profile seismic-login --format process'
& $cliProyecto configure set credential_process $proveedorProyecto --profile seismic
if ($LASTEXITCODE -ne 0) { throw 'No se pudo configurar el perfil del proyecto.' }
& $cliProyecto configure set region $Region --profile seismic
if ($LASTEXITCODE -ne 0) { throw 'No se pudo configurar la región.' }

$archivoProyecto=Join-Path $PSScriptRoot '.env'
if (-not (Test-Path -LiteralPath $archivoProyecto)) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot '.env.example') -Destination $archivoProyecto
}
$contenidoProyecto=[IO.File]::ReadAllText($archivoProyecto)
foreach ($ajusteProyecto in @{AWS_S3_BUCKET=$Bucket;AWS_PROFILE='seismic';AWS_REGION=$Region}.GetEnumerator()) {
    $patronProyecto='(?m)^'+$ajusteProyecto.Key+'=.*$'
    if ($contenidoProyecto -match $patronProyecto) {
        $contenidoProyecto=[regex]::Replace($contenidoProyecto,$patronProyecto,$ajusteProyecto.Key+'='+$ajusteProyecto.Value)
    } else { $contenidoProyecto+="`n"+$ajusteProyecto.Key+'='+$ajusteProyecto.Value }
}
[IO.File]::WriteAllText($archivoProyecto,$contenidoProyecto,[Text.UTF8Encoding]::new($false))
Write-Output 'Sesión configurada. El siguiente paso es probar la carga del proyecto a S3.'
