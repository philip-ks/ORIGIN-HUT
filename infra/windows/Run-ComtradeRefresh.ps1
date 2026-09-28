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
$EnvFile = Join-Path $ProjectRoot ".env"
$ComposeFile = Join-Path $ProjectRoot "infra\docker\compose.yml"
$LogRoot = Join-Path $ProjectRoot "logs\comtrade-refresh"

New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null

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


function Write-LoggedOutput {

    param(
        [object]$Lines
    )

    foreach ($Item in @($Lines)) {

        $Text = [string]$Item

        Write-Host $Text

        Add-Content `
            -Path $LogPath `
            -Value $Text `
            -Encoding UTF8
    }
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

        Write-RefreshLog "SKIP: another Origin Hut Comtrade refresh is already running."

        return
    }


    Write-RefreshLog "START Origin Hut Comtrade refresh."
    Write-RefreshLog "ProjectRoot=$ProjectRoot"
    Write-RefreshLog "ConfigPath=$ConfigPath"
    Write-RefreshLog "DryRun=$DryRun"


    if (-not $DryRun) {

        Write-RefreshLog "START PostgreSQL runtime preflight."


        if (-not (Test-Path $EnvFile)) {
            throw "Origin Hut .env file not found: $EnvFile"
        }

        if (-not (Test-Path $ComposeFile)) {
            throw "Docker Compose file not found: $ComposeFile"
        }

        $DockerCommand =
            Get-Command `
                docker `
                -ErrorAction SilentlyContinue

        if ($null -eq $DockerCommand) {
            throw "Docker CLI is not available on PATH."
        }


        $DockerPath =
            $DockerCommand.Source


        $PreviousNativeErrorActionPreference =
            $ErrorActionPreference


        try {

            $ErrorActionPreference =
                "Continue"


            $DockerOutput =
                & $DockerPath compose `
                    --env-file $EnvFile `
                    -f $ComposeFile `
                    up `
                    -d `
                    postgres `
                    2>&1


            $DockerExit =
                $LASTEXITCODE
        }
        finally {

            $ErrorActionPreference =
                $PreviousNativeErrorActionPreference
        }


        Write-LoggedOutput `
            -Lines $DockerOutput


        Write-RefreshLog `
            "DockerComposeExitCode=$DockerExit"


        if ($DockerExit -ne 0) {
            throw "Unable to start Origin Hut PostgreSQL."
        }


        $Healthy = $false


        for ($Attempt = 1; $Attempt -le 30; $Attempt++) {

            $PreviousNativeErrorActionPreference =
                $ErrorActionPreference


            try {

                $ErrorActionPreference =
                    "Continue"


                $HealthOutput =
                    & $DockerPath inspect `
                        --format "{{.State.Health.Status}}" `
                        originhut-postgres `
                        2>&1


                $HealthExit =
                    $LASTEXITCODE
            }
            finally {

                $ErrorActionPreference =
                    $PreviousNativeErrorActionPreference
            }


            if ($HealthExit -eq 0) {

                $Health =
                    [string](
                        $HealthOutput |
                        Select-Object -First 1
                    )

                $Health = $Health.Trim()


                if ($Health -eq "healthy") {

                    $Healthy = $true

                    Write-RefreshLog "PostgreSQLHealth=healthy"

                    break
                }
            }


            Start-Sleep -Seconds 2
        }


        if (-not $Healthy) {
            throw "Origin Hut PostgreSQL did not become healthy within 60 seconds."
        }


        Write-RefreshLog "PASS PostgreSQL runtime preflight."
    }
    else {

        Write-RefreshLog "SKIP PostgreSQL preflight for dry-run."
    }


    $Arguments = @(
        $RefreshScript,
        "--config",
        $ConfigPath
    )


    if ($DryRun) {
        $Arguments += "--dry-run"
    }


    $PreviousNativeErrorActionPreference =
        $ErrorActionPreference


    try {

        $ErrorActionPreference =
            "Continue"


        $OutputLines =
            & $Python @Arguments 2>&1


        $ExitCode =
            $LASTEXITCODE
    }
    finally {

        $ErrorActionPreference =
            $PreviousNativeErrorActionPreference
    }


    Write-LoggedOutput `
        -Lines $OutputLines


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
