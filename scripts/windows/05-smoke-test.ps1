# Smoke-test a running API at 127.0.0.1:8000 (production config).
$ErrorActionPreference = "Stop"
$base = "http://127.0.0.1:8000"
$failures = 0

function Check($name, $ok, $detail = "") {
    if ($ok) { Write-Host "[PASS] $name" -ForegroundColor Green }
    else { Write-Host "[FAIL] $name  $detail" -ForegroundColor Red; $script:failures++ }
}

# 1. /health
try { $h = Invoke-RestMethod "$base/health"; Check "/health returns ok" ($h.status -eq "ok") }
catch { Check "/health returns ok" $false $_.Exception.Message }

# 2. /docs must be disabled in production
try { Invoke-WebRequest "$base/docs" | Out-Null; Check "/docs disabled (404)" $false "got 200 — ENVIRONMENT is not production!" }
catch { Check "/docs disabled (404)" ($_.Exception.Response.StatusCode.value__ -eq 404) $_.Exception.Message }

# 3. Invalid Bearer token must 401 (never treated as guest)
try { Invoke-WebRequest "$base/api/v1/history" -Headers @{Authorization = "Bearer not-a-token"} | Out-Null; Check "invalid token -> 401" $false "got 200" }
catch { Check "invalid token -> 401" ($_.Exception.Response.StatusCode.value__ -eq 401) $_.Exception.Message }

# 4. /segment accepts an image and returns rate-limit headers
Add-Type -AssemblyName System.Drawing
$tmp = Join-Path $env:TEMP "grailseeker-smoke.jpg"
$bmp = New-Object System.Drawing.Bitmap 320, 320
$gfx = [System.Drawing.Graphics]::FromImage($bmp)
$gfx.Clear([System.Drawing.Color]::IndianRed)
$bmp.Save($tmp, [System.Drawing.Imaging.ImageFormat]::Jpeg)
$gfx.Dispose(); $bmp.Dispose()

try {
    $seg = Invoke-WebRequest "$base/api/v1/search/segment" -Method Post -Form @{ image = Get-Item $tmp }
    $body = $seg.Content | ConvertFrom-Json
    Check "/segment returns 200 with image dims" ($body.image_width -gt 0)
    Check "/segment sets X-RateLimit-* headers" ($null -ne $seg.Headers["X-RateLimit-Limit"])
} catch { Check "/segment returns 200" $false $_.Exception.Message }

# 5. /find returns a results array (may be empty pre-seed)
try {
    $find = Invoke-WebRequest "$base/api/v1/search/find" -Method Post -Form @{ image = Get-Item $tmp }
    $fbody = $find.Content | ConvertFrom-Json
    Check "/find returns results array" ($null -ne $fbody.results)
    Write-Host "       ($($fbody.results.Count) results — 0 is normal before seeding)"
} catch { Check "/find returns results array" $false $_.Exception.Message }

Remove-Item $tmp -ErrorAction SilentlyContinue

if ($failures -eq 0) { Write-Host "`nAll smoke tests passed." -ForegroundColor Green }
else { Write-Host "`n$failures smoke test(s) FAILED." -ForegroundColor Red; exit 1 }
