#requires -Version 7.0
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$exampleRoot = $PSScriptRoot
$python = Join-Path $exampleRoot '.venv\Scripts\python.exe'

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory)]
        [scriptblock]$Command,

        [Parameter(Mandatory)]
        [string]$FailureMessage
    )

    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw $FailureMessage
    }
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw 'Python 3.11 or newer is required.'
}

Invoke-CheckedCommand -Command {
    python -c "import sys; raise SystemExit(sys.version_info < (3, 11))"
} -FailureMessage 'Python 3.11 or newer is required.'

if (-not (Test-Path $python)) {
    Invoke-CheckedCommand -Command {
        python -m venv (Join-Path $exampleRoot '.venv')
    } -FailureMessage 'Unable to create the agent example environment.'
}

Invoke-CheckedCommand -Command {
    & $python -m pip install --upgrade pip
} -FailureMessage 'Unable to upgrade pip.'
Invoke-CheckedCommand -Command {
    & $python -m pip install -r (Join-Path $exampleRoot 'requirements.txt')
} -FailureMessage 'Unable to install the agent example dependencies.'

$environmentFile = Join-Path $exampleRoot '.env'
if (-not (Test-Path $environmentFile)) {
    Copy-Item (Join-Path $exampleRoot '.env.example') $environmentFile
    Write-Host "Created $environmentFile. Replace its placeholders before running the agent."
}
else {
    Write-Host "Reusing $environmentFile."
}