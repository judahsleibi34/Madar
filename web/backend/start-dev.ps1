# Run the local backend with development mode taking precedence over web/.env.
[CmdletBinding()]
param(
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'
$pythonPath = Join-Path $PSScriptRoot 'madar_back\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Local backend virtual environment missing: madar_back\Scripts\python.exe'
}

$previousAppEnv = $env:APP_ENV
$previousOverride = $env:MADAR_ENV_OVERRIDE
Push-Location $PSScriptRoot
try {
    $env:APP_ENV = 'development'
    $env:MADAR_ENV_OVERRIDE = 'false'
    & $pythonPath -m uvicorn app:app --reload --host 127.0.0.1 --port $Port
} finally {
    $env:APP_ENV = $previousAppEnv
    $env:MADAR_ENV_OVERRIDE = $previousOverride
    Pop-Location
}
