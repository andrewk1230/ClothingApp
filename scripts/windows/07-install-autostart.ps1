# Register Scheduled Tasks so the API + tunnel start on boot. Run as admin.
$ErrorActionPreference = "Stop"
$repo = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent

function Register-GrailseekerTask($name, $script) {
    $action = New-ScheduledTaskAction -Execute "powershell.exe" `
        -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`""
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $settings = New-ScheduledTaskSettingsSet -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) `
        -ExecutionTimeLimit (New-TimeSpan -Days 3650) -StartWhenAvailable
    Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings `
        -User "SYSTEM" -RunLevel Highest -Force | Out-Null
    Write-Host "Registered task: $name" -ForegroundColor Green
}

Register-GrailseekerTask "GrailSeeker API" (Join-Path $PSScriptRoot "04-run-api.ps1")
Register-GrailseekerTask "GrailSeeker Tunnel" (Join-Path $PSScriptRoot "06-run-tunnel.ps1")

Write-Host ""
Write-Host "Note: Docker Desktop must also start at boot (Settings -> General)." -ForegroundColor Yellow
Write-Host "Start now with: Start-ScheduledTask 'GrailSeeker API'; Start-ScheduledTask 'GrailSeeker Tunnel'"
