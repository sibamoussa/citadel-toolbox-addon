param(
    [Parameter(Mandatory)]
    [ValidatePattern('^[a-z0-9]+(?:-[a-z0-9]+)*$')]
    [string]$Entity,

    [switch]$AllowUnresolved
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $root '.venv\Scripts\python.exe'
$python = if (Test-Path $venvPython) { $venvPython } else { (Get-Command python).Source }
$overlay = Join-Path $root "entities\$Entity\overlay.yaml"
$output = Join-Path $root "generated\$Entity\toolbox.yaml"

if (-not (Test-Path $overlay)) {
    throw "Entity overlay not found: $overlay"
}

$env:PYTHONPATH = Join-Path $root 'src'
$arguments = @(
    '-m', 'citadel_toolbox.cli', 'compile',
    '--core', (Join-Path $root 'catalog\core.yaml'),
    '--overlay', $overlay,
    '--output', $output
)
if ($AllowUnresolved) {
    $arguments += '--allow-unresolved'
}

& $python @arguments
if ($LASTEXITCODE -ne 0) {
    throw "Toolbox build failed with exit code $LASTEXITCODE"
}

Write-Host "Generated $output"