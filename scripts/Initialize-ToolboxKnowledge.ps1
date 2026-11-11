#Requires -Version 7.0
[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)][ValidatePattern('^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')][string]$SubscriptionId,
    [Parameter(Mandatory)][ValidatePattern('^[a-zA-Z0-9_()-][a-zA-Z0-9_.()-]{0,88}[a-zA-Z0-9_()-]$')][string]$ProjectResourceGroup,
    [Parameter(Mandatory)][ValidatePattern('^[a-zA-Z0-9][a-zA-Z0-9_-]{1,63}$')][string]$AccountName,
    [Parameter(Mandatory)][ValidatePattern('^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$')][string]$ProjectName,
    [Parameter(Mandatory)][ValidatePattern('^[a-zA-Z0-9_()-][a-zA-Z0-9_.()-]{0,88}[a-zA-Z0-9_()-]$')][string]$SearchResourceGroup,
    [Parameter(Mandatory)][ValidatePattern('^[a-z0-9](?:[a-z0-9-]{0,58}[a-z0-9])$')][string]$SearchServiceName,
    [Parameter(Mandatory)][ValidatePattern('^[a-z0-9][a-z0-9_-]{0,127}$')][string]$SearchIndexName,
    [Parameter(Mandatory)][ValidatePattern('^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$')][string]$SearchConnectionName,
    [Parameter(Mandatory)][ValidatePattern('^[a-z0-9][a-z0-9_-]{0,127}$')][string]$KnowledgeSourceName,
    [Parameter(Mandatory)][ValidatePattern('^[a-z0-9][a-z0-9_-]{0,127}$')][string]$KnowledgeBaseName,
    [Parameter(Mandatory)][ValidatePattern('^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$')][string]$FoundryIqConnectionName,
    [Parameter(Mandatory)][ValidatePattern('^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$')][string]$SemanticConfigurationName,
    [switch]$UseSearchApiKey
)

$ErrorActionPreference = 'Stop'
$VerbosePreference = 'SilentlyContinue'
$DebugPreference = 'SilentlyContinue'
$ProgressPreference = 'SilentlyContinue'
$operation = 'validate inputs'
$status = 'unavailable'
$managementToken = $null
$searchKey = $null
$managementHeaders = $null
$searchHeaders = $null

function Invoke-KnowledgeRequest {
    param([string]$Operation, [string]$Method, [string]$Uri, [hashtable]$Headers,
        [object]$Body, [switch]$AllowMissing)
    $script:operation = $Operation
    $script:status = 'unavailable'
    try {
        $request = @{
            Method = $Method; Uri = $Uri; Headers = $Headers
            ErrorAction = 'Stop'; Verbose = $false; Debug = $false
        }
        if ($null -ne $Body) {
            $request.Body = ConvertTo-Json -InputObject $Body -Depth 30 -Compress
            $request.ContentType = 'application/json'
        }
        $response = Invoke-RestMethod @request
        if ($AllowMissing -and $null -eq $response) {
            throw [System.InvalidOperationException]::new('Empty resource lookup response.')
        }
        return $response
    }
    catch {
        if ($null -ne $_.Exception.Response -and $null -ne $_.Exception.Response.StatusCode) {
            $script:status = [string][int]$_.Exception.Response.StatusCode
        }
        if ($AllowMissing -and $script:status -eq '404') { return $null }
        throw [System.InvalidOperationException]::new("Knowledge initialization failed: $Operation (HTTP $script:status).")
    }
}

function Test-KnowledgeMatch {
    param($Actual, $Expected)
    if ($Expected -is [System.Collections.IDictionary]) {
        foreach ($field in $Expected.Keys) {
            if (-not (Test-KnowledgeMatch $Actual.$field $Expected[$field])) { return $false }
        }
        return $true
    }
    if ($Expected -is [array]) {
        $actualItems = @($Actual | Where-Object { $null -ne $_ })
        if ($actualItems.Count -ne $Expected.Count) { return $false }
        for ($position = 0; $position -lt $Expected.Count; $position++) {
            if (-not (Test-KnowledgeMatch $actualItems[$position] $Expected[$position])) { return $false }
        }
        return $true
    }
    return ($null -ne $Actual -and $Actual -ceq $Expected)
}

try {
    if ($SearchConnectionName -ieq $FoundryIqConnectionName -or $SearchServiceName.Contains('--')) {
        throw 'Invalid names.'
    }
    $projectId = "/subscriptions/$SubscriptionId/resourceGroups/$ProjectResourceGroup/providers/Microsoft.CognitiveServices/accounts/$AccountName/projects/$ProjectName"
    $searchId = "/subscriptions/$SubscriptionId/resourceGroups/$SearchResourceGroup/providers/Microsoft.Search/searchServices/$SearchServiceName"
    $searchEndpoint = "https://$SearchServiceName.search.windows.net"
    $mcpUrl = "$searchEndpoint/knowledgebases/$KnowledgeBaseName/mcp?api-version=2026-08-01-preview"
    if (-not $PSCmdlet.ShouldProcess($projectId, 'Initialize knowledge source, knowledge base and project connections (API-key authentication)')) { return }
    $operation = 'acknowledge -UseSearchApiKey (broad Search admin credential stored in Foundry)'
    if (-not $UseSearchApiKey) { throw 'Explicit API-key acknowledgement required.' }
    $operation = 'acquire management token'
    try {
        $managementToken = az account get-access-token --subscription $SubscriptionId `
            --resource https://management.azure.com/ --query accessToken --output tsv --only-show-errors 2>$null
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($managementToken)) { throw 'Token unavailable.' }
    }
    catch { throw [System.InvalidOperationException]::new('Management authentication failed.') }
    $managementHeaders = @{ Authorization = "Bearer $managementToken" }
    $keys = Invoke-KnowledgeRequest -Operation 'read Search admin key' -Method POST `
        -Uri "https://management.azure.com$searchId/listAdminKeys?api-version=2025-05-01" -Headers $managementHeaders
    $operation = 'validate Search admin key response'
    $searchKey = $keys.primaryKey
    $keys = $null
    if ([string]::IsNullOrWhiteSpace($searchKey)) { throw 'Key unavailable.' }
    $searchHeaders = @{ 'api-key' = $searchKey }
    $index = Invoke-KnowledgeRequest -Operation 'read prerequisite Search index' -Method GET `
        -Uri "$searchEndpoint/indexes/${SearchIndexName}?api-version=2026-08-01-preview" -Headers $searchHeaders
    $operation = 'validate prerequisite semantic configuration'
    if ($SemanticConfigurationName -cnotin @($index.semantic.configurations | ForEach-Object { $_.name })) {
        throw 'Semantic configuration not present.'
    }
    $sourceFields = @(
        foreach ($fieldName in @('id', 'title', 'content', 'source_file', 'source_path', 'page_number')) {
            foreach ($field in $index.fields) {
                if ($field.name -ceq $fieldName -and $field.retrievable -ne $false) { @{ name = $fieldName } }
            }
        }
    )
    $source = @{
        name = $KnowledgeSourceName; kind = 'searchIndex'
        searchIndexParameters = @{
            searchIndexName = $SearchIndexName; semanticConfigurationName = $SemanticConfigurationName
            sourceDataFields = $sourceFields
        }
    }
    $base = @{
        name = $KnowledgeBaseName; knowledgeSources = @(@{ name = $KnowledgeSourceName })
        retrievalReasoningEffort = @{ kind = 'minimal' }; outputMode = 'extractiveData'
    }
    $searchConnection = @{ properties = @{ category = 'CognitiveSearch'; authType = 'ApiKey'; target = $searchEndpoint } }
    $iqConnection = @{ properties = @{
        category = 'RemoteTool'; authType = 'CustomKeys'; target = $mcpUrl; metadata = @{ type = 'custom_MCP' }
    } }
    $resources = @(
        @{ Label = 'knowledge source'; Uri = "$searchEndpoint/knowledgesources/${KnowledgeSourceName}?api-version=2026-08-01-preview"; Body = $source; Headers = $searchHeaders },
        @{ Label = 'knowledge base'; Uri = "$searchEndpoint/knowledgebases/${KnowledgeBaseName}?api-version=2026-08-01-preview"; Body = $base; Headers = $searchHeaders },
        @{ Label = 'Search connection'; Uri = "https://management.azure.com$projectId/connections/${SearchConnectionName}?api-version=2025-06-01"; Body = $searchConnection; Headers = $managementHeaders },
        @{ Label = 'Foundry IQ connection'; Uri = "https://management.azure.com$projectId/connections/${FoundryIqConnectionName}?api-version=2025-06-01"; Body = $iqConnection; Headers = $managementHeaders }
    )
    foreach ($resource in $resources) {
        $existing = Invoke-KnowledgeRequest -Operation "inspect $($resource.Label)" -Method GET `
            -Uri $resource.Uri -Headers $resource.Headers -AllowMissing
        $resource.Missing = $null -eq $existing
        $operation = "refuse drift in $($resource.Label)"
        if (-not $resource.Missing -and -not (Test-KnowledgeMatch $existing $resource.Body)) { throw 'Existing resource differs.' }
    }
    foreach ($resource in $resources) {
        if (-not $resource.Missing) { continue }
        if ($resource.Label -eq 'Search connection') { $resource.Body.properties.credentials = @{ key = $searchKey } }
        if ($resource.Label -eq 'Foundry IQ connection') { $resource.Body.properties.credentials = @{ keys = @{ 'api-key' = $searchKey } } }
        $createHeaders = $resource.Headers.Clone()
        $createHeaders['If-None-Match'] = '*'
        $null = Invoke-KnowledgeRequest -Operation "create $($resource.Label)" -Method PUT `
            -Uri $resource.Uri -Headers $createHeaders -Body $resource.Body
    }
    Write-Warning 'Existing connection credentials were not read or rotated. Validate runtime Search and Foundry IQ authentication before publication.'
    [pscustomobject]@{
        SearchConnectionId = "$projectId/connections/$SearchConnectionName"
        FoundryIqConnectionId = "$projectId/connections/$FoundryIqConnectionName"
        FoundryIqMcpUrl = $mcpUrl
        EnvironmentReferences = [pscustomobject]@{
            '<PREFIX>_SEARCH_CONNECTION_ID' = "$projectId/connections/$SearchConnectionName"
            '<PREFIX>_SEARCH_INDEX_NAME' = $SearchIndexName
            '<PREFIX>_FOUNDRY_IQ_CONNECTION_ID' = "$projectId/connections/$FoundryIqConnectionName"
            '<PREFIX>_FOUNDRY_IQ_MCP_URL' = $mcpUrl
        }
    }
}
catch {
    throw [System.InvalidOperationException]::new("Knowledge initialization failed: $operation (HTTP $status).")
}
finally {
    $managementToken = $null
    $searchKey = $null
    $managementHeaders = $null
    $searchHeaders = $null
    $resources = $null
    $searchConnection = $null
    $iqConnection = $null
    $createHeaders = $null
}