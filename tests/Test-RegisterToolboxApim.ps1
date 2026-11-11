param(
    [string]$PythonExecutable
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$registrationScript = Join-Path $root 'scripts/Register-ToolboxApim.ps1'
$temporaryDirectory = Join-Path ([System.IO.Path]::GetTempPath()) (
    'citadel-apim-tests-' + [guid]::NewGuid().ToString()
)
$null = New-Item -ItemType Directory -Path $temporaryDirectory
$global:CitadelApimRegistrationTestState = @{}
$clientId = '8bc8b977-050d-42a1-a619-2ea5fbcafb1f'
$productId = 'TOOL-ToolboxDemo-Publisha7e840b1f8f2-DEV'

function az {
    $state = $global:CitadelApimRegistrationTestState
    $operation = $args[0..2] -join ' '
    $state.Calls.Add($operation)
    $global:LASTEXITCODE = 0
    if ($operation -eq 'apim show --name') {
        if ($state.Mode -eq 'read-failure') {
            $global:LASTEXITCODE = 1
            return
        }
        $identity = if ($state.Mode -eq 'no-identity') { @{} } else { @{ principalId = 'test-id' } }
        if ($state.Mode -in @('uami-success', 'uami-product-success', 'product-read-failure')) {
            $identity = @{
                userAssignedIdentities = @{
                    '/identities/other' = @{ clientId = '11111111-1111-1111-1111-111111111111' }
                    '/identities/backend' = @{ clientId = $clientId; principalId = 'uami-principal' }
                }
            }
        }
        if ($state.Mode -eq 'uami-mismatch') {
            $identity.userAssignedIdentities = @{
                '/identities/other' = @{ clientId = '11111111-1111-1111-1111-111111111111' }
            }
        }
        $tier = if ($state.Mode -eq 'consumption') { 'Consumption' } else { 'StandardV2' }
        return @{
            sku = @{ name = $tier }
            identity = $identity
            gatewayUrl = 'https://gateway.example.test'
        } | ConvertTo-Json -Depth 6
    }
    if ($operation -eq 'rest --method GET') {
        $expectedUrl = "https://management.azure.com/subscriptions/test-subscription/resourceGroups/test-rg/providers/Microsoft.ApiManagement/service/test-apim/products/${productId}?api-version=2024-05-01"
        if ($args[([array]::IndexOf($args, '--url') + 1)] -ne $expectedUrl) {
            throw 'Unexpected product lookup URL.'
        }
        if ($args[([array]::IndexOf($args, '--subscription') + 1)] -ne 'test-subscription') {
            throw 'Product lookup must use the requested subscription.'
        }
        if ($state.Mode -eq 'product-read-failure') { $global:LASTEXITCODE = 1 }
        return
    }
    if ($operation -notin @('deployment group validate', 'deployment group create')) {
        throw "Unexpected Azure command: $operation"
    }
    if (($operation -eq 'deployment group validate' -and $state.Mode -eq 'validation-failure') -or
        ($operation -eq 'deployment group create' -and $state.Mode -eq 'deployment-failure')) {
        $global:LASTEXITCODE = 1
    }
}

$cases = @(
    @{ Mode = 'what-if'; Error = $null; Calls = 0 },
    @{ Mode = 'success'; Error = $null; Calls = 3 },
    @{ Mode = 'custom-path'; ApiPath = 'mcp/citadel-toolbox'; Error = $null; Calls = 3 },
    @{ Mode = 'generic-backend'; Error = $null; Calls = 3 },
    @{ Mode = 'uami-success'; Uami = $true; Error = $null; Calls = 3 },
    @{ Mode = 'uami-product-success'; Uami = $true; Product = $true; Error = $null; Calls = 4 },
    @{ Mode = 'product-success'; Product = $true; Error = $null; Calls = 4 },
    @{
        Mode = 'uami-mismatch'; Uami = $true; Calls = 1
        Error = 'The requested backend client ID is not a user-assigned identity attached to APIM.'
    },
    @{
        Mode = 'uami-missing'; Uami = $true; Calls = 1
        Error = 'The requested backend client ID is not a user-assigned identity attached to APIM.'
    },
    @{
        Mode = 'product-read-failure'; Uami = $true; Product = $true; Calls = 2
        Error = 'Unable to read the existing APIM product. Check ProductId and read permissions.'
    },
    @{
        Mode = 'invalid-client-id'; Calls = 0
        Error = 'Unable to generate the APIM registration template.'
    },
    @{
        Mode = 'client-without-audience'; Uami = $true; Calls = 0
        Error = 'Unable to generate the APIM registration template.'
    },
    @{
        Mode = 'invalid-product'; Calls = 0
        Error = 'Unable to generate the APIM registration template.'
    },
    @{ Mode = 'read-failure'; Error = 'Unable to read the existing APIM instance.'; Calls = 1 },
    @{
        Mode = 'no-identity'
        Error = 'Enable a system-assigned identity on APIM and grant it access to the backend first.'
        Calls = 1
    },
    @{
        Mode = 'consumption'
        Error = 'APIM Consumption does not support native MCP servers. Use a supported APIM tier.'
        Calls = 1
    },
    @{
        Mode = 'validation-failure'
        Error = 'APIM registration deployment validation failed.'
        Calls = 2
    },
    @{
        Mode = 'deployment-failure'
        Error = 'APIM registration failed. Inspect the resource group deployment.'
        Calls = 3
    }
)

try {
    $parseErrors = $null
    $tokens = $null
    $null = [System.Management.Automation.Language.Parser]::ParseFile(
        $registrationScript, [ref]$tokens, [ref]$parseErrors
    )
    if ($parseErrors.Count -gt 0) { throw ($parseErrors | Out-String) }

    foreach ($case in $cases) {
        $state = @{
            Mode = $case.Mode
            Calls = [System.Collections.Generic.List[string]]::new()
        }
        $global:CitadelApimRegistrationTestState = $state
        $outputPath = Join-Path $temporaryDirectory "$($case.Mode).json"
        $parameters = @{
            SubscriptionId = 'test-subscription'
            ResourceGroup = 'test-rg'
            ApimName = 'test-apim'
            BackendUrl = 'https://tools.example.test/mcp?api-version=v1'
            OutputPath = $outputPath
        }
        if ($PythonExecutable) { $parameters.PythonExecutable = $PythonExecutable }
        if ($case.ApiPath) { $parameters.ApiPath = $case.ApiPath }
        if ($case.Uami) { $parameters.BackendClientId = $clientId.ToUpperInvariant() }
        if ($case.Product) { $parameters.ProductId = $productId }
        if ($case.Mode -eq 'what-if') {
            $parameters.WhatIf = $true
            $parameters.BackendClientId = $clientId
            $parameters.ProductId = $productId
        }
        if ($case.Mode -eq 'generic-backend') { $parameters.BackendAudience = '' }
        if ($case.Mode -eq 'invalid-client-id') { $parameters.BackendClientId = 'invalid' }
        if ($case.Mode -eq 'client-without-audience') { $parameters.BackendAudience = '' }
        if ($case.Mode -eq 'invalid-product') { $parameters.ProductId = 'bad/product' }
        $actualError = $null
        $registrationOutput = @()
        try { $registrationOutput = @(& $registrationScript @parameters 6>&1) } catch { $actualError = $_.Exception.Message }
        if ($actualError -ne $case.Error) {
            throw "$($case.Mode): expected error '$($case.Error)', got '$actualError'"
        }
        if ($state.Calls.Count -ne $case.Calls) {
            throw "$($case.Mode): expected $($case.Calls) Azure commands, got $($state.Calls.Count)"
        }
        $expectedOrder = @('apim show --name')
        if ($case.Product) { $expectedOrder += 'rest --method GET' }
        $expectedOrder += @('deployment group validate', 'deployment group create')
        for ($index = 0; $index -lt $state.Calls.Count; $index++) {
            if ($state.Calls[$index] -ne $expectedOrder[$index]) {
                throw "$($case.Mode): unexpected Azure command order"
            }
        }
        if ($case.Mode -eq 'what-if') {
            if (Test-Path $outputPath) { throw 'WhatIf must not write a template.' }
        }
        if ($null -eq $case.Error -and $case.Mode -ne 'what-if') {
            $template = Get-Content $outputPath -Raw | ConvertFrom-Json
            if ($template.resources[1].properties.type -ne 'mcp') {
                throw 'Expected a native MCP API.'
            }
            [xml]$policy = $template.resources[2].properties.value
            $managedIdentity = $policy.SelectSingleNode('/policies/inbound/authentication-managed-identity')
            if ($case.Mode -eq 'success' -and $managedIdentity.resource -ne 'https://ai.azure.com') {
                throw 'Expected the Foundry managed-identity audience.'
            }
            if ($case.Mode -eq 'generic-backend' -and $null -ne $managedIdentity) {
                throw 'An empty audience must disable managed-identity policy generation.'
            }
            if ($case.Uami) {
                if ($managedIdentity.GetAttribute('client-id') -cne $parameters.BackendClientId) {
                    throw 'Expected the requested UAMI client ID in the policy.'
                }
            }
            elseif ($managedIdentity -and $managedIdentity.HasAttribute('client-id')) {
                throw 'System identity policy must not specify a client ID.'
            }
            $expectedResourceCount = if ($case.Product) { 4 } else { 3 }
            if ($template.resources.Count -ne $expectedResourceCount) {
                throw "Expected $expectedResourceCount template resources."
            }
            if ($case.Product -and
                $template.resources[3].name -ne "test-apim/$productId/citadel-toolbox") {
                throw 'Expected the existing product association.'
            }
            $expectedPath = if ($case.ApiPath) { $case.ApiPath } else { 'citadel-toolbox' }
            if ($template.resources[1].properties.path -ne $expectedPath -or
                $template.outputs.mcpPath.value -ne "/$expectedPath") {
                throw 'Expected the native MCP endpoint path.'
            }
            if ('Registered MCP server: https://gateway.example.test/' + $expectedPath -notin
                @($registrationOutput | ForEach-Object { "$_" })) {
                throw 'Expected the registered endpoint to match the configured API path.'
            }
        }
        Write-Output "PASS: $($case.Mode)"
    }
    Write-Output "All $($cases.Count) APIM registration script checks passed. No Azure calls were made."
}
finally {
    Remove-Item $temporaryDirectory -Recurse -Force
    Remove-Variable CitadelApimRegistrationTestState -Scope Global
}