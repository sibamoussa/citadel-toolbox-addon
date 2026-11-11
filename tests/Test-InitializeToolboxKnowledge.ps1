#Requires -Version 7.0
$ErrorActionPreference = 'Stop'
$initializer = Join-Path (Split-Path -Parent $PSScriptRoot) 'scripts/Initialize-ToolboxKnowledge.ps1'
$parameters = @{
    SubscriptionId = '11111111-2222-3333-4444-555555555555'
    ProjectResourceGroup = 'project-rg'; AccountName = 'test-account'; ProjectName = 'test-project'
    SearchResourceGroup = 'search-rg'; SearchServiceName = 'test-search'; SearchIndexName = 'policy-index'
    SearchConnectionName = 'search'; KnowledgeSourceName = 'policy-source'; KnowledgeBaseName = 'policy-base'
    FoundryIqConnectionName = 'foundry-iq'; SemanticConfigurationName = 'semantic'; UseSearchApiKey = $true
}

function Assert-True($Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

function az {
    $global:ToolboxKnowledgeTestState.AuthCalls++
    Assert-True (($args[0..2] -join ' ') -eq 'account get-access-token --subscription') 'Unexpected CLI operation.'
    Assert-True ($args -notcontains 'SENTINEL-KEY') 'Key must never be a CLI argument.'
    Assert-True ($args -contains 'https://management.azure.com/') 'Management audience required.'
    $global:LASTEXITCODE = 0
    if ($global:ToolboxKnowledgeTestState.Mode -eq 'auth-failure') {
        $global:LASTEXITCODE = 1
        return 'SENTINEL-TOKEN'
    }
    'SENTINEL-TOKEN'
}

function Stop-Http([int]$Code) {
    $exception = [System.Exception]::new('SENTINEL-KEY SENTINEL-TOKEN private response body')
    $exception | Add-Member NoteProperty Response ([pscustomobject]@{ StatusCode = $Code })
    throw $exception
}

function Invoke-RestMethod {
    param($Method, $Uri, $Headers, $Body, $ContentType, $ErrorAction, $Verbose, $Debug)
    $state = $global:ToolboxKnowledgeTestState
    $state.Calls.Add([pscustomobject]@{ Method = $Method; Uri = $Uri })
    Assert-True ($Uri -notmatch 'listSecrets|SENTINEL') 'Do not read connection secrets or place credentials in URLs.'
    if ($Uri -match '/listAdminKeys\?') {
        if ($state.Mode -eq 'key-forbidden') { Stop-Http 403 }
        return @{ primaryKey = 'SENTINEL-KEY' }
    }
    if ($Uri -match '/indexes/') {
        if ($state.Mode -eq 'missing-index') { Stop-Http 404 }
        return @{
            semantic = @{ configurations = @(@{ name = $(if ($state.Mode -eq 'invalid-semantic') { 'wrong' } else { 'semantic' }) }) }
            fields = @(@{ name = 'id'; retrievable = $true }, @{ name = 'title' },
                @{ name = 'content'; retrievable = $false }, @{ name = 'source_path'; retrievable = $true },
                @{ name = 'unrelated'; retrievable = $true })
        }
    }
    if ($Method -eq 'GET') {
        if ($state.Mode -eq 'forbidden') { Stop-Http 403 }
        if ($state.Mode -eq 'empty-get') { return $null }
        if ($state.Mode -eq 'network') { throw 'SENTINEL-KEY network details' }
        if ($state.Store.ContainsKey($Uri)) { return $state.Store[$Uri] }
        Stop-Http 404
    }
    Assert-True ($Method -eq 'PUT') 'Unexpected HTTP method.'
    Assert-True ($Headers['If-None-Match'] -eq '*') 'Create must be conditional.'
    if ($state.Mode -eq 'race') { Stop-Http 412 }
    if ($state.Mode -eq 'arm-race' -and $Uri -match '/connections/') { Stop-Http 412 }
    if ($state.Mode -eq 'put-failure') { Stop-Http 500 }
    $parsed = $Body | ConvertFrom-Json -AsHashtable
    if ($Uri -match '/knowledgesources/') {
        Assert-True (($parsed.searchIndexParameters.sourceDataFields.name -join ',') -eq 'id,title,source_path') 'Fields must be actual and retrievable.'
        Assert-True ($parsed.kind -eq 'searchIndex' -and $parsed.searchIndexParameters.searchIndexName -eq 'policy-index') 'Incorrect source payload.'
        Assert-True ($parsed.searchIndexParameters.semanticConfigurationName -eq 'semantic') 'Incorrect semantic configuration.'
    }
    if ($Uri -match '/knowledgebases/') {
        Assert-True ($parsed.retrievalReasoningEffort.kind -eq 'minimal' -and $parsed.outputMode -eq 'extractiveData') 'Incorrect retrieval configuration.'
        Assert-True ($parsed.knowledgeSources.Count -eq 1 -and $parsed.knowledgeSources[0].name -eq 'policy-source') 'Incorrect knowledge source reference.'
    }
    if ($Uri -match '/connections/search\?') {
        Assert-True ($parsed.properties.credentials.key -eq 'SENTINEL-KEY') 'Search credential missing.'
        Assert-True ($parsed.properties.category -eq 'CognitiveSearch' -and $parsed.properties.authType -eq 'ApiKey') 'Incorrect Search connection type.'
        Assert-True ($parsed.properties.target -eq 'https://test-search.search.windows.net') 'Incorrect Search target.'
    }
    if ($Uri -match '/connections/foundry-iq\?') {
        Assert-True ($parsed.properties.credentials.keys['api-key'] -eq 'SENTINEL-KEY') 'MCP credential missing.'
        Assert-True ($parsed.properties.category -eq 'RemoteTool' -and $parsed.properties.authType -eq 'CustomKeys') 'Incorrect MCP connection type.'
        Assert-True ($parsed.properties.metadata.type -eq 'custom_MCP') 'Missing custom MCP metadata.'
        Assert-True ($parsed.properties.target -eq 'https://test-search.search.windows.net/knowledgebases/policy-base/mcp?api-version=2026-08-01-preview') 'Incorrect MCP target.'
    }
    if ($Uri -match '/connections/') {
        Assert-True ($Uri.EndsWith('?api-version=2025-06-01')) 'Incorrect ARM connection API.'
        $parsed.properties.Remove('credentials')
    }
    $state.Store[$Uri] = $parsed
    return $parsed
}

$script:state = @{ Mode = 'create'; AuthCalls = 0; Calls = [System.Collections.Generic.List[object]]::new(); Store = @{} }
$global:ToolboxKnowledgeTestState = $script:state
$tokens = $null
$parseErrors = $null
$null = [System.Management.Automation.Language.Parser]::ParseFile($initializer, [ref]$tokens, [ref]$parseErrors)
Assert-True ($parseErrors.Count -eq 0) 'Initializer parse failed.'
foreach ($mode in @('whatif', 'acknowledgement', 'invalid-uuid', 'invalid-path', 'same-connection', 'auth-failure',
    'create', 'reuse', 'drift-target', 'drift-auth', 'drift-category', 'drift-metadata', 'drift-source', 'drift-base',
    'forbidden', 'key-forbidden', 'empty-get', 'network', 'missing-index', 'invalid-semantic', 'race', 'arm-race', 'put-failure')) {
    $script:state.Mode = $mode
    $script:state.Calls.Clear()
    $script:state.AuthCalls = 0
    if ($mode -like 'drift-*') {
        $script:state.Store = $baseline | ConvertTo-Json -Depth 30 | ConvertFrom-Json -AsHashtable
        $connectionUri = @($script:state.Store.Keys | Where-Object { $_ -match '/connections/search\?' })[0]
        switch ($mode) {
            'drift-target' { $script:state.Store[$connectionUri].properties.target = 'https://wrong.search.windows.net' }
            'drift-auth' { $script:state.Store[$connectionUri].properties.authType = 'AAD' }
            'drift-category' { $script:state.Store[$connectionUri].properties.category = 'Other' }
            'drift-metadata' {
                $iqUri = @($script:state.Store.Keys | Where-Object { $_ -match '/connections/foundry-iq\?' })[0]
                $script:state.Store[$iqUri].properties.metadata.type = 'wrong'
            }
            'drift-source' {
                $sourceUri = @($script:state.Store.Keys | Where-Object { $_ -match '/knowledgesources/' })[0]
                $script:state.Store[$sourceUri].searchIndexParameters.searchIndexName = 'wrong'
            }
            'drift-base' {
                $baseUri = @($script:state.Store.Keys | Where-Object { $_ -match '/knowledgebases/' })[0]
                $script:state.Store[$baseUri].outputMode = 'answerSynthesis'
            }
        }
    }
    if ($mode -in @('race', 'arm-race', 'put-failure')) { $script:state.Store.Clear() }
    $arguments = $parameters.Clone()
    if ($mode -eq 'whatif') { $arguments.WhatIf = $true; $arguments.Remove('UseSearchApiKey') }
    if ($mode -eq 'acknowledgement') { $arguments.Remove('UseSearchApiKey') }
    if ($mode -eq 'invalid-uuid') { $arguments.SubscriptionId = 'invalid' }
    if ($mode -eq 'invalid-path') { $arguments.KnowledgeBaseName = '../other?query=bad' }
    if ($mode -eq 'same-connection') { $arguments.FoundryIqConnectionName = 'search' }
    $failure = $null
    $output = @()
    try { $output = @(& $initializer @arguments *>&1) } catch { $failure = $_.Exception.Message }
    $text = ($output | Out-String) + $failure
    Assert-True ($text -notmatch 'SENTINEL|private response body|network details') "Credential leakage: $mode"
    $writes = @($script:state.Calls | Where-Object Method -eq 'PUT')
    if ($mode -in @('whatif', 'create', 'reuse')) {
        Assert-True ($null -eq $failure) "Unexpected failure in ${mode}: $failure"
    }
    else {
        Assert-True ($null -ne $failure) "Expected failure: $mode"
    }
    if ($mode -eq 'create') {
        Assert-True ($writes.Count -eq 4) 'Expected four creates.'
        $baseline = $script:state.Store | ConvertTo-Json -Depth 30 | ConvertFrom-Json -AsHashtable
        $result = @($output | Where-Object { $_.PSObject.Properties.Name -contains 'SearchConnectionId' })
        Assert-True ($result.Count -eq 1 -and $result[0].EnvironmentReferences.'<PREFIX>_SEARCH_INDEX_NAME' -eq 'policy-index') 'Expected one nonsecret result object.'
    }
    elseif ($mode -eq 'race') { Assert-True ($writes.Count -eq 1 -and $failure -match '412') 'Race must fail without retry.' }
    elseif ($mode -eq 'arm-race') { Assert-True ($writes.Count -eq 3 -and $failure -match '412') 'ARM race must fail without overwrite or retry.' }
    elseif ($mode -eq 'put-failure') { Assert-True ($writes.Count -eq 1 -and $failure -match '500') 'Create failure must stop immediately.' }
    else { Assert-True ($writes.Count -eq 0) "Unexpected mutation: $mode" }
    if ($mode -in @('whatif', 'acknowledgement', 'invalid-uuid', 'invalid-path', 'same-connection')) {
        Assert-True ($script:state.AuthCalls -eq 0 -and $script:state.Calls.Count -eq 0) 'Dry run/acknowledgement must precede auth and HTTP.'
    }
    if ($mode -in @('forbidden', 'key-forbidden')) { Assert-True ($failure -match '403') 'Must preserve HTTP status without response body.' }
    if ($mode -eq 'missing-index') { Assert-True ($failure -match '404' -and $failure -match 'prerequisite Search index') 'Missing prerequisite must not be created.' }
    Write-Host "PASS $mode"
}
Remove-Variable ToolboxKnowledgeTestState -Scope Global
Write-Host 'All offline knowledge initialization tests passed.'