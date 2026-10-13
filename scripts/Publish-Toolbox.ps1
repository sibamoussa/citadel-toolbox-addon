param(
    [Parameter(Mandatory)]
    [ValidatePattern('^[a-z0-9]+(?:-[a-z0-9]+)*$')]
    [string]$Entity,

    [Parameter(Mandatory)]
    [string]$ProjectEndpoint,

    [string]$ToolboxName = "$Entity-toolbox"
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$toolboxFile = Join-Path $root "generated\$Entity\toolbox.yaml"

& (Join-Path $PSScriptRoot 'Build-Toolbox.ps1') -Entity $Entity
if ($LASTEXITCODE -ne 0) {
    throw "Toolbox build failed"
}

$env:AZURE_DEV_USER_AGENT = 'microsoft_foundry_skill'
try {
    azd ai project set $ProjectEndpoint
    if ($LASTEXITCODE -ne 0) { throw 'Unable to select the Foundry project' }

    azd ai toolbox create $ToolboxName --from-file $toolboxFile --no-prompt
    if ($LASTEXITCODE -ne 0) { throw 'Unable to create the Toolbox version' }
}
finally {
    Remove-Item Env:AZURE_DEV_USER_AGENT -ErrorAction SilentlyContinue
}

Write-Host "Test the version-specific endpoint printed above before promotion."
Write-Host "Consumer endpoint: $ProjectEndpoint/toolboxes/$ToolboxName/mcp?api-version=v1"