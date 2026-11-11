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
    [string]$BackendClientId,
    [string]$ProductId,
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
    'Create or update the MCP backend, native MCP API, API policy, and optional product association'
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
if ($PSBoundParameters.ContainsKey('BackendClientId')) {
    $exportArguments += @('--backend-client-id', $BackendClientId)
}
if ($PSBoundParameters.ContainsKey('ProductId')) {
    $exportArguments += @('--product-id', $ProductId)
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
if ($BackendClientId) {
    $attachedIdentities = @($service.identity.userAssignedIdentities.PSObject.Properties |
        Where-Object { $_.Value.clientId -eq $BackendClientId })
    if ($attachedIdentities.Count -eq 0) {
        throw 'The requested backend client ID is not a user-assigned identity attached to APIM.'
    }
}
elseif ($BackendAudience -and -not $service.identity.principalId) {
    throw 'Enable a system-assigned identity on APIM and grant it access to the backend first.'
}

if ($ProductId) {
    $productUrl = "https://management.azure.com/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroup/providers/Microsoft.ApiManagement/service/$ApimName/products/${ProductId}?api-version=2024-05-01"
    az rest --method GET --url $productUrl --subscription $SubscriptionId --only-show-errors --output none
    if ($LASTEXITCODE -ne 0) {
        throw 'Unable to read the existing APIM product. Check ProductId and read permissions.'
    }
}

az deployment group validate --subscription $SubscriptionId --resource-group $ResourceGroup `
    --template-file $OutputPath --only-show-errors --output none
if ($LASTEXITCODE -ne 0) { throw 'APIM registration deployment validation failed.' }

az deployment group create --subscription $SubscriptionId --resource-group $ResourceGroup `
    --name "register-$ApiId" --mode Incremental --template-file $OutputPath `
    --only-show-errors --output none
if ($LASTEXITCODE -ne 0) { throw 'APIM registration failed. Inspect the resource group deployment.' }

$endpoint = "$($service.gatewayUrl.TrimEnd('/'))/$ApiPath"
Write-Host "Registered MCP server: $endpoint"
if ($ProductId) {
    Write-Host "Associated with existing APIM product: $ProductId"
    Write-Host 'Use a valid API-scoped or associated product-scoped APIM subscription key in the Ocp-Apim-Subscription-Key header.'
}
else {
    Write-Host 'Use an API-scoped APIM subscription key in the Ocp-Apim-Subscription-Key header.'
}
Write-Host 'Verify MCP initialization and tools/list with the client before routing production traffic.'