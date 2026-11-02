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
        $tier = if ($state.Mode -eq 'consumption') { 'Consumption' } else { 'StandardV2' }
        return @{
            sku = @{ name = $tier }
            identity = $identity
            gatewayUrl = 'https://gateway.example.test'
        } | ConvertTo-Json
    }
    if (($operation -eq 'deployment group validate' -and $state.Mode -eq 'validation-failure') -or
        ($operation -eq 'deployment group create' -and $state.Mode -eq 'deployment-failure')) {
        $global:LASTEXITCODE = 1
    }
}

$cases = @(
    @{ Mode = 'what-if'; Error = $null; Calls = 0 },
    @{ Mode = 'success'; Error = $null; Calls = 3 },
    @{ Mode = 'generic-backend'; Error = $null; Calls = 3 },
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
        if ($case.Mode -eq 'what-if') { $parameters.WhatIf = $true }
        if ($case.Mode -eq 'generic-backend') { $parameters.BackendAudience = '' }
        $actualError = $null
        try { & $registrationScript @parameters } catch { $actualError = $_.Exception.Message }
        if ($actualError -ne $case.Error) {
            throw "$($case.Mode): expected error '$($case.Error)', got '$actualError'"
        }
        if ($state.Calls.Count -ne $case.Calls) {
            throw "$($case.Mode): expected $($case.Calls) Azure commands, got $($state.Calls.Count)"
        }
        $expectedOrder = @('apim show --name', 'deployment group validate', 'deployment group create')
        for ($index = 0; $index -lt $state.Calls.Count; $index++) {
            if ($state.Calls[$index] -ne $expectedOrder[$index]) {
                throw "$($case.Mode): unexpected Azure command order"
            }
        }
        if ($case.Mode -eq 'what-if') {
            if (Test-Path $outputPath) { throw 'WhatIf must not write a template.' }
        }
        if ($case.Mode -in @('success', 'generic-backend')) {
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
        }
        Write-Output "PASS: $($case.Mode)"
    }
    Write-Output 'All 8 APIM registration script checks passed. No Azure calls were made.'
}
finally {
    Remove-Item $temporaryDirectory -Recurse -Force
    Remove-Variable CitadelApimRegistrationTestState -Scope Global
}