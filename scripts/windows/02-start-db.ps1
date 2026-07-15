# Start Postgres (pgvector) and run migrations.
$ErrorActionPreference = "Stop"
$repo = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $repo

if (-not (Test-Path ".env")) {
    Write-Error "No .env — run 01-setup-env.ps1 first (POSTGRES_PASSWORD must be set BEFORE the first compose up)."
}

docker compose up -d

Write-Host "Waiting for Postgres to become healthy..."
$deadline = (Get-Date).AddMinutes(2)
while ($true) {
    $status = docker inspect --format "{{.State.Health.Status}}" grailseeker-db 2>$null
    if ($status -eq "healthy") { break }
    if ((Get-Date) -gt $deadline) { Write-Error "Postgres did not become healthy within 2 minutes." }
    Start-Sleep -Seconds 3
}
Write-Host "Postgres is healthy." -ForegroundColor Green

$python = Join-Path $repo "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "backend\.venv missing — run 03-install-backend.ps1, then rerun this script to apply migrations." -ForegroundColor Yellow
    exit 0
}

Set-Location (Join-Path $repo "backend")
& $python -m alembic upgrade head
Write-Host "Migrations applied." -ForegroundColor Green
