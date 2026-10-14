param(
    [Parameter(Mandatory)]
    [ValidatePattern('^[a-z0-9]+(?:-[a-z0-9]+)*$')]
    [string]$Entity,

    [switch]$AllowUnresolved,

    [string]$EnvFile
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $root '.venv\Scripts\python.exe'
$python = if (Test-Path $venvPython) { $venvPython } else { (Get-Command python).Source }
$overlay = Join-Path $root "entities\$Entity\overlay.yaml"
$output = Join-Path $root "generated\$Entity\toolbox.yaml"
$defaultEnvFile = Join-Path $root "entities\$Entity\.env"

if (-not (Test-Path $overlay)) {
    throw "Entity overlay not found: $overlay"
}

$resolvedEnvFile = if ($EnvFile) { $EnvFile } elseif (Test-Path $defaultEnvFile) { $defaultEnvFile } else { $null }
if ($resolvedEnvFile) {
    if (-not (Test-Path $resolvedEnvFile)) {
        throw "Environment file not found: $resolvedEnvFile"
    }
    foreach ($line in Get-Content $resolvedEnvFile) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith('#')) { continue }
        $name, $value = $trimmed -split '=', 2
        if (-not $value) { throw "Invalid environment entry in ${resolvedEnvFile}: $line" }
        [Environment]::SetEnvironmentVariable($name.Trim(), $value.Trim(), 'Process')
    }
    Write-Host "Loaded entity configuration from $resolvedEnvFile"
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
    if (-not $AllowUnresolved -and -not $resolvedEnvFile) {
        Write-Host "Create entities\$Entity\.env from entities\$Entity\.env.example, fill every value, and retry."
    }
    throw "Toolbox build failed with exit code $LASTEXITCODE"
}

Write-Host "Generated $output"