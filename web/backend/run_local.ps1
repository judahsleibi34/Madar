$ErrorActionPreference = "Stop"

# Load secrets and shared settings from ../.env, while preserving the local
# process settings below instead of replacing them with Docker defaults.
$env:APP_ENV = "development"
$env:MADAR_ENV_OVERRIDE = "false"
$env:RATE_LIMIT_FAIL_OPEN = "true"

& "$PSScriptRoot\madar_back\Scripts\python.exe" `
  -m uvicorn app:app --reload --host 127.0.0.1 --port 8000
