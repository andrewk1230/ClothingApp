# Create the production .env BEFORE the first `docker compose up`.
# Postgres only applies POSTGRES_PASSWORD when initializing an empty volume.
$ErrorActionPreference = "Stop"
$repo = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $repo

if (Test-Path ".env") {
    Write-Error ".env already exists — refusing to overwrite. Delete it first if you really want to regenerate."
}

# 32 chars, URL-safe (goes into DATABASE_URL verbatim).
$chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
$password = -join ((1..32) | ForEach-Object { $chars[(Get-Random -Maximum $chars.Length)] })

$env_content = Get-Content ".env.example" -Raw
$env_content = $env_content -replace "ENVIRONMENT=development", "ENVIRONMENT=production"
$env_content = $env_content -replace "POSTGRES_PASSWORD=grailseeker", "POSTGRES_PASSWORD=$password"
$env_content = $env_content -replace "DATABASE_URL=postgresql\+asyncpg://grailseeker:grailseeker@", "DATABASE_URL=postgresql+asyncpg://grailseeker:${password}@"

Set-Content ".env" $env_content -NoNewline

Write-Host "Wrote .env with ENVIRONMENT=production and a generated POSTGRES_PASSWORD." -ForegroundColor Green
Write-Host ""
Write-Host "NOW EDIT .env AND FILL IN:" -ForegroundColor Yellow
Write-Host "  - SUPABASE_URL / SUPABASE_ANON_KEY / SUPABASE_SERVICE_ROLE_KEY"
Write-Host "  - EBAY_CLIENT_ID / EBAY_CLIENT_SECRET (production keyset)"
Write-Host "Leave SUPABASE_JWT_SECRET empty to use JWKS verification."
