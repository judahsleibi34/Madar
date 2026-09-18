# Run the loopback backend with development settings taking precedence over web/.env.
[CmdletBinding()]
param(
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'
$pythonPath = Join-Path $PSScriptRoot 'madar_back\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Local backend virtual environment missing: madar_back\Scripts\python.exe'
}

$localFrontendOrigins = 'http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174'
$developmentEnvironment = @{
    APP_ENV = 'development'
    MADAR_ENV_OVERRIDE = 'false'
    FRONTEND_URLS = $localFrontendOrigins
    FRONTEND_URL = 'http://localhost:5173'
    CSRF_TRUSTED_ORIGINS = $localFrontendOrigins
    COOKIE_SECURE = 'false'
    COOKIE_SAMESITE = 'lax'
    # Docker's redis hostname does not resolve from the Windows virtual environment.
    REDIS_URL = $(if ($env:REDIS_URL) { $env:REDIS_URL } else { 'redis://127.0.0.1:6379/0' })
}
$previousEnvironment = @{}
foreach ($name in $developmentEnvironment.Keys) {
    $previousEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
Push-Location $PSScriptRoot
try {
    foreach ($name in $developmentEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $developmentEnvironment[$name], 'Process')
    }
    & $pythonPath -m uvicorn app:app --reload --host 127.0.0.1 --port $Port
} finally {
    foreach ($name in $developmentEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $previousEnvironment[$name], 'Process')
    }
    Pop-Location
}
