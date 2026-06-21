param(
    [string]$TaskName = "Auto SEU-WLAN",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

if ($DryRun) {
    Write-Host "Would remove scheduled task: $TaskName"
    exit 0
}

try {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction Stop
    Write-Host "Removed scheduled task: $TaskName"
    exit 0
}
catch {
    Write-Warning "Unregister-ScheduledTask failed: $($_.Exception.Message)"
    Write-Warning "Falling back to schtasks.exe."
}

$Output = & schtasks.exe /Delete /TN $TaskName /F 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error ($Output -join [Environment]::NewLine)
    exit $LASTEXITCODE
}

Write-Host ($Output -join [Environment]::NewLine)
Write-Host "Removed scheduled task: $TaskName"
