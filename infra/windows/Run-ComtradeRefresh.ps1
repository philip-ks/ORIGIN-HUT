[CmdletBinding()]
param(
    [string]$ConfigPath = "",
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

if ([string]::IsNullOrWhiteSpace($ConfigPath)) {
    $ConfigPath = Join-Path $ProjectRoot "services\data\config\comtrade_refresh.local.json"
}

if (-not [System.IO.Path]::IsPathRooted($ConfigPath)) {
    $ConfigPath = Join-Path $ProjectRoot $ConfigPath
}

$ConfigPath = [System.IO.Path]::GetFullPath($ConfigPath)

$Python = Join-Path $ProjectRoot "services\data\.venv\Scripts\python.exe"

$RefreshScript = Join-Path $ProjectRoot "services\data\src\connectors\comtrade_refresh.py"

$LogRoot = Join-Path $ProjectRoot "logs\comtrade-refresh"

New-Item `
    -ItemType Directory `
    -Force `
    -Path $LogRoot |
    Out-Null

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"

$LogPath = Join-Path $LogRoot "comtrade-refresh-$Timestamp.log"


function Write-RefreshLog {

    param(
        [Parameter(Mandatory)]
        [string]$Message
    )

    $Line = "$(Get-Date -Format o) $Message"

    Write-Host $Line

    Add-Content `
        -Path $LogPath `
        -Value $Line `
        -Encoding UTF8
}


if (-not (Test-Path $Python)) {
    throw "Python virtual environment not found: $Python"
}

if (-not (Test-Path $RefreshScript)) {
    throw "Refresh orchestrator not found: $RefreshScript"
}

if (-not (Test-Path $ConfigPath)) {
    throw "Refresh configuration not found: $ConfigPath"
}


$Mutex = [System.Threading.Mutex]::new(
    $false,
    "Local\OriginHutComtradeRefresh"
)

$LockAcquired = $false


try {

    try {
        $LockAcquired = $Mutex.WaitOne(0)
    }
    catch [System.Threading.AbandonedMutexException] {
        $LockAcquired = $true
    }


    if (-not $LockAcquired) {

        Write-RefreshLog `
            "SKIP: another Origin Hut Comtrade refresh is already running."

        return
    }


    Write-RefreshLog "START Origin Hut Comtrade refresh."
    Write-RefreshLog "ProjectRoot=$ProjectRoot"
    Write-RefreshLog "ConfigPath=$ConfigPath"
    Write-RefreshLog "DryRun=$DryRun"


    $Arguments = @(
        $RefreshScript,
        "--config",
        $ConfigPath
    )


    if ($DryRun) {
        $Arguments += "--dry-run"
    }


    $Output = & $Python @Arguments 2>&1
    $ExitCode = $LASTEXITCODE


    foreach ($OutputLine in $Output) {

        $Text = [string]$OutputLine

        Write-Host $Text

        Add-Content `
            -Path $LogPath `
            -Value $Text `
            -Encoding UTF8
    }


    Write-RefreshLog "PythonExitCode=$ExitCode"


    if ($ExitCode -ne 0) {
        throw "Comtrade refresh failed with exit code $ExitCode. See $LogPath"
    }


    Write-RefreshLog "PASS Origin Hut Comtrade refresh completed."
}
finally {

    if ($LockAcquired) {

        try {
            $Mutex.ReleaseMutex()
        }
        catch {
        }
    }

    $Mutex.Dispose()
}
