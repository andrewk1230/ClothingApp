# Expose the local API via Cloudflare Tunnel (ephemeral trycloudflare URL).
# For a stable hostname use a named tunnel — see RUNBOOK.md step 6.
$ErrorActionPreference = "Stop"
$repo = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$logDir = Join-Path $repo "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
    Write-Error "cloudflared not found. Install: winget install Cloudflare.cloudflared"
}

Write-Host "Starting Cloudflare Tunnel -> http://localhost:8000 (URL appears below and in logs\tunnel.log)"
cloudflared tunnel --url http://localhost:8000 *>> (Join-Path $logDir "tunnel.log")
