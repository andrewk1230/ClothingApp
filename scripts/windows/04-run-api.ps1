# Run the GrailSeeker API (loopback only; the tunnel exposes it).
$ErrorActionPreference = "Stop"
$repo = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location (Join-Path $repo "backend")

$logDir = Join-Path $repo "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

# Some RDNA4 setups need this for GPU detection; harmless otherwise.
if (-not $env:HSA_OVERRIDE_GFX_VERSION) { $env:HSA_OVERRIDE_GFX_VERSION = "12.0.1" }

& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 *>> (Join-Path $logDir "api.log")
