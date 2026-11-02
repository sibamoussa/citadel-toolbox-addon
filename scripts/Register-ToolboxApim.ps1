[CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'Medium')]
param(
    [Parameter(Mandatory)]
    [string]$SubscriptionId,

    [Parameter(Mandatory)]
    [string]$ResourceGroup,

    [Parameter(Mandatory)]
    [string]$ApimName,

    [Parameter(Mandatory)]
    [string]$BackendUrl,

    [string]$ApiId = 'citadel-toolbox',
    [string]$ApiPath = 'citadel-toolbox',
    [string]$BackendAudience = 'https://ai.azure.com',
    [string]$PythonExecutable,
    [string]$OutputPath
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
if (-not $PythonExecutable) {
    $PythonExecutable = Join-Path $root '.venv/Scripts/python.exe'
    if (-not (Test-Path $PythonExecutable)) {
        $PythonExecutable = Join-Path $root '.venv/bin/python'
    }
}
if (-not $OutputPath) {
    $OutputPath = Join-Path $root 'generated/apim/registration.json'
}
if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    throw 'Azure CLI is required. Install it from https://aka.ms/installazurecli.'
}
if (-not (Get-Command $PythonExecutable -ErrorAction SilentlyContinue)) {
    throw 'Install this package in .venv or pass -PythonExecutable with the installed package.'
}
if (-not $PSCmdlet.ShouldProcess(
    "$ApimName/$ApiId in $SubscriptionId/$ResourceGroup",
    'Create or update the MCP backend, native MCP API, and API policy'
)) {
    return
}

$exportArguments = @(
    '-m', 'citadel_toolbox.cli', 'export-apim',
    '--apim-name', $ApimName, '--backend-url', $BackendUrl,
    '--api-id', $ApiId, '--path', $ApiPath, '--output', $OutputPath
)
if ($BackendAudience) {
    $exportArguments += @('--backend-audience', $BackendAudience)
}
& $PythonExecutable @exportArguments
if ($LASTEXITCODE -ne 0) { throw 'Unable to generate the APIM registration template.' }

$serviceJson = az apim show --name $ApimName --resource-group $ResourceGroup `
    --subscription $SubscriptionId --output json --only-show-errors
if ($LASTEXITCODE -ne 0) { throw 'Unable to read the existing APIM instance.' }
$service = $serviceJson | ConvertFrom-Json
if ($service.sku.name -eq 'Consumption') {
    throw 'APIM Consumption does not support native MCP servers. Use a supported APIM tier.'
}
if ($BackendAudience -and -not $service.identity.principalId) {
    throw 'Enable a system-assigned identity on APIM and grant it access to the backend first.'
}

az deployment group validate --subscription $SubscriptionId --resource-group $ResourceGroup `
    --template-file $OutputPath --only-show-errors --output none
if ($LASTEXITCODE -ne 0) { throw 'APIM registration deployment validation failed.' }

az deployment group create --subscription $SubscriptionId --resource-group $ResourceGroup `
    --name "register-$ApiId" --mode Incremental --template-file $OutputPath `
    --only-show-errors --output none
if ($LASTEXITCODE -ne 0) { throw 'APIM registration failed. Inspect the resource group deployment.' }

$endpoint = "$($service.gatewayUrl.TrimEnd('/'))/$ApiPath/mcp"
Write-Host "Registered MCP server: $endpoint"
Write-Host 'Use an API-scoped APIM subscription key in the Ocp-Apim-Subscription-Key header.'
Write-Host 'Verify MCP initialization and tools/list with the client before routing production traffic.'