[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$DataRoot = Join-Path $ProjectRoot "services\data"
$VenvPython = Join-Path $DataRoot ".venv\Scripts\python.exe"
$Requirements = Join-Path $DataRoot "requirements.txt"
$Proof = Join-Path $DataRoot "src\proofs\oh18_rfq_quotation.py"

Set-Location $ProjectRoot

if (-not (Test-Path $Proof)) {
    throw "OH18 proof runner not found: $Proof"
}

if (-not (Test-Path $VenvPython)) {

    $SystemPython =
        Get-Command python -ErrorAction SilentlyContinue

    if ($null -eq $SystemPython) {
        throw "Python is required to create the Origin Hut data virtual environment."
    }

    Write-Host "Creating active-checkout Python virtual environment..."

    & $SystemPython.Source -m venv (Join-Path $DataRoot ".venv")

    if ($LASTEXITCODE -ne 0) {
        throw "Unable to create Python virtual environment."
    }

    & $VenvPython -m pip install --upgrade pip

    if ($LASTEXITCODE -ne 0) {
        throw "Unable to upgrade pip."
    }

    & $VenvPython -m pip install -r $Requirements

    if ($LASTEXITCODE -ne 0) {
        throw "Unable to install Origin Hut data requirements."
    }
}

if (-not (Test-Path (Join-Path $ProjectRoot "node_modules"))) {

    Write-Host "Installing Node dependencies..."

    npm ci

    if ($LASTEXITCODE -ne 0) {
        throw "npm ci failed."
    }
}

& $VenvPython $Proof

exit $LASTEXITCODE
