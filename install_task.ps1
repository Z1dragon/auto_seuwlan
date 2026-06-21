param(
    [string]$TaskName = "Auto SEU-WLAN",
    [string]$Python = "python",
    [string]$EnvFile = "",
    [string]$LogFile = "",
    [switch]$Console,
    [switch]$StartNow,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Script = Join-Path $ScriptRoot "auto_seuwlan.py"
if (-not $EnvFile) {
    $EnvFile = Join-Path $ScriptRoot ".env"
}
if (-not $LogFile) {
    $LogDir = Join-Path $ScriptRoot "logs"
    $LogFile = Join-Path $LogDir "auto_seuwlan.log"
}

if (-not (Test-Path -LiteralPath $Script)) {
    throw "Cannot find script: $Script"
}

$PythonCommand = Get-Command $Python -ErrorAction Stop
$PythonExe = $PythonCommand.Source
if (-not $PythonExe) {
    $PythonExe = $Python
}

$TaskPythonExe = $PythonExe
if (-not $Console) {
    $PythonDir = Split-Path -Parent $PythonExe
    $Pythonw = Join-Path $PythonDir "pythonw.exe"
    if (Test-Path -LiteralPath $Pythonw) {
        $TaskPythonExe = $Pythonw
    }
    else {
        Write-Warning "pythonw.exe was not found next to $PythonExe. The task will use python.exe and may show a console window."
    }
}

$Arguments = "`"$Script`" --daemon --env `"$EnvFile`" --log-file `"$LogFile`""
$TaskCommand = "`"$TaskPythonExe`" $Arguments"
$CurrentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

if ($DryRun) {
    Write-Host "TaskName: $TaskName"
    Write-Host "User: $CurrentUser"
    Write-Host "Execute: $TaskPythonExe"
    Write-Host "Console: $([bool]$Console)"
    Write-Host "Arguments: $Arguments"
    Write-Host "LogFile: $LogFile"
    Write-Host "Fallback schtasks /TR: $TaskCommand"
    exit 0
}

if (-not (Test-Path -LiteralPath $EnvFile)) {
    Write-Warning "Cannot find .env: $EnvFile. The task can still be registered, but login will fail until .env exists."
}

New-Item -ItemType Directory -Path (Split-Path -Parent $LogFile) -Force | Out-Null

try {
    $Action = New-ScheduledTaskAction -Execute $TaskPythonExe -Argument $Arguments -WorkingDirectory $ScriptRoot
    $Trigger = New-ScheduledTaskTrigger -AtLogOn -User $CurrentUser
    $Settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -ExecutionTimeLimit (New-TimeSpan -Seconds 0)
    $Principal = New-ScheduledTaskPrincipal -UserId $CurrentUser -LogonType Interactive -RunLevel Limited

    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -Principal $Principal `
        -Description "Auto reconnect and authenticate SEU-WLAN" `
        -Force `
        -ErrorAction Stop | Out-Null

    Write-Host "Registered scheduled task for current user: $TaskName"
    Write-Host "Log file: $LogFile"
    if ($StartNow) {
        Start-ScheduledTask -TaskName $TaskName
        Write-Host "Started scheduled task: $TaskName"
    }
    exit 0
}
catch {
    Write-Warning "Register-ScheduledTask failed: $($_.Exception.Message)"
    Write-Warning "Falling back to schtasks.exe for a current-user logon task."
}

$Output = & schtasks.exe /Create /TN $TaskName /SC ONLOGON /TR $TaskCommand /F /RL LIMITED 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error ($Output -join [Environment]::NewLine)
    Write-Error "Failed to register the task. Run PowerShell as Administrator, then retry: .\install_task.ps1"
    exit $LASTEXITCODE
}

Write-Host ($Output -join [Environment]::NewLine)
Write-Host "Registered scheduled task for current user: $TaskName"
Write-Host "Log file: $LogFile"
if ($StartNow) {
    & schtasks.exe /Run /TN $TaskName | Out-Host
}
