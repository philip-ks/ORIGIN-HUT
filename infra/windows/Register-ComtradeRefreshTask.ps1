[CmdletBinding()]
param(
    [datetime]$At = (Get-Date "03:00")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$TaskName = "Origin Hut - UN Comtrade Refresh"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

$Runner = Join-Path $ProjectRoot "infra\windows\Run-ComtradeRefresh.ps1"

$ExampleConfig = Join-Path $ProjectRoot "services\data\config\comtrade_refresh.example.json"

$LocalConfig = Join-Path $ProjectRoot "services\data\config\comtrade_refresh.local.json"


if (-not (Test-Path $Runner)) {
    throw "Refresh runner not found: $Runner"
}

if (-not (Test-Path $ExampleConfig)) {
    throw "Refresh example config not found: $ExampleConfig"
}


if (-not (Test-Path $LocalConfig)) {

    Copy-Item `
        -Path $ExampleConfig `
        -Destination $LocalConfig

    Write-Host "Created local refresh config:"
    Write-Host $LocalConfig
}


$ActionArguments = '-NoProfile -ExecutionPolicy Bypass -File "' +
    $Runner +
    '" -ConfigPath "' +
    $LocalConfig +
    '"'


$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument $ActionArguments `
    -WorkingDirectory $ProjectRoot


$Trigger = New-ScheduledTaskTrigger `
    -Daily `
    -At $At


$Settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)


$UserId = "$env:USERDOMAIN\$env:USERNAME"


$Principal = New-ScheduledTaskPrincipal `
    -UserId $UserId `
    -LogonType Interactive `
    -RunLevel Limited


Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal `
    -Description "Origin Hut scheduled UN Comtrade refresh. Authenticated access required for production." `
    -Force |
    Out-Null


Disable-ScheduledTask `
    -TaskName $TaskName |
    Out-Null


$Task = Get-ScheduledTask `
    -TaskName $TaskName


$TaskInfo = Get-ScheduledTaskInfo `
    -TaskName $TaskName


Write-Host ""
Write-Host "=== ORIGIN HUT SCHEDULED TASK ==="

Write-Host "TaskName:    $($Task.TaskName)"
Write-Host "State:       $($Task.State)"
Write-Host "NextRunTime: $($TaskInfo.NextRunTime)"
Write-Host "User:        $($Task.Principal.UserId)"
Write-Host "Runner:      $Runner"
Write-Host "Config:      $LocalConfig"

Write-Host ""
Write-Host "Task intentionally registered DISABLED."
