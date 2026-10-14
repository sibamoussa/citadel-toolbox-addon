#requires -Version 7.0

param(
    [ValidatePattern('^[a-z0-9]+(?:-[a-z0-9]+)*$')]
    [string]$Entity,

    [string]$DisplayName,

    [string]$TenantId,

    [string]$ProjectEndpoint,

    [string]$SearchConnectionId,

    [string]$SearchIndexName,

    [string]$McpUrl,

    [string]$McpConnectionId,

    [string[]]$AllowedDomain,

    [string]$ToolboxName,

    [switch]$Reconfigure,

    [switch]$UpdateSkills,

    [switch]$SkipPublish
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $root '.venv\Scripts\python.exe'

function Read-RequiredValue {
    param(
        [Parameter(Mandatory)]
        [string]$Prompt,

        [string]$Value
    )

    $resolved = $Value
    while ([string]::IsNullOrWhiteSpace($resolved)) {
        $resolved = Read-Host $Prompt
    }
    return $resolved.Trim()
}

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

Set-Location $root

$Entity = Read-RequiredValue -Prompt 'Entity name (lowercase letters, numbers, hyphens)' -Value $Entity
if ($Entity -notmatch '^[a-z0-9]+(?:-[a-z0-9]+)*$') {
    throw 'Entity name must contain lowercase letters, numbers, and hyphens.'
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw 'Python 3.11 or newer is required.'
}

if (-not (Test-Path $venvPython)) {
    Write-Host 'Creating the local Python environment...'
    Invoke-CheckedCommand -Command { python -m venv .venv } `
        -FailureMessage 'Unable to create the Python environment.'
}

Invoke-CheckedCommand -Command {
    & $venvPython -c "import sys; raise SystemExit(sys.version_info < (3, 11))"
} -FailureMessage 'Python 3.11 or newer is required.'

Write-Host 'Installing the local package and validation dependencies...'
Invoke-CheckedCommand -Command { & $venvPython -m pip install -e '.[dev,mcp]' --quiet } `
    -FailureMessage 'Unable to install Python dependencies.'

$entityDirectory = Join-Path $root "entities\$Entity"
if (-not (Test-Path $entityDirectory)) {
    $DisplayName = Read-RequiredValue -Prompt 'Entity display name' -Value $DisplayName
    Invoke-CheckedCommand -Command {
        & $venvPython -m citadel_toolbox.cli init-entity $Entity --display-name $DisplayName
    } -FailureMessage 'Unable to initialize the entity.'
}
else {
    Write-Host "Using existing entity: $Entity"
}

$envFile = Join-Path $entityDirectory '.env'
$hasConfigurationArguments = $SearchConnectionId -or $SearchIndexName -or $McpUrl -or `
    $McpConnectionId -or $AllowedDomain
if ($Reconfigure -or $hasConfigurationArguments -or -not (Test-Path $envFile)) {
    $SearchConnectionId = Read-RequiredValue `
        -Prompt 'Full Azure AI Search project connection resource ID' -Value $SearchConnectionId
    $SearchIndexName = Read-RequiredValue -Prompt 'Existing Search index name' -Value $SearchIndexName
    $McpUrl = Read-RequiredValue -Prompt 'Read-only MCP HTTPS endpoint' -Value $McpUrl
    $McpConnectionId = Read-RequiredValue `
        -Prompt 'Full read-only MCP project connection resource ID' -Value $McpConnectionId
    if (-not $AllowedDomain) {
        $domainInput = Read-RequiredValue `
            -Prompt 'Approved web domains (comma-separated)' -Value ''
        $AllowedDomain = @($domainInput -split ',' | ForEach-Object { $_.Trim() })
    }

    $configureArguments = @(
        '-m', 'citadel_toolbox.cli', 'configure-entity', $Entity,
        '--search-connection-id', $SearchConnectionId,
        '--search-index-name', $SearchIndexName,
        '--mcp-url', $McpUrl,
        '--mcp-connection-id', $McpConnectionId
    )
    foreach ($domain in $AllowedDomain) {
        $configureArguments += @('--allowed-domain', $domain)
    }
    & $venvPython @configureArguments
    if ($LASTEXITCODE -ne 0) { throw 'Unable to configure the entity.' }
}
else {
    Write-Host "Keeping existing local configuration: $envFile"
}

& (Join-Path $PSScriptRoot 'Build-Toolbox.ps1') -Entity $Entity
if ($LASTEXITCODE -ne 0) { throw 'Toolbox validation failed.' }

if ($SkipPublish) {
    Write-Host 'Local setup and strict validation completed. Cloud publication was skipped.'
    return
}

if (-not (Get-Command azd -ErrorAction SilentlyContinue)) {
    throw 'Azure Developer CLI (azd) is required. Install it from https://aka.ms/install-azd.'
}

Write-Host 'Ensuring the Microsoft Foundry extension is installed...'
$env:AZURE_DEV_USER_AGENT = 'microsoft_foundry_skill'
try {
    Invoke-CheckedCommand -Command { azd extension install microsoft.foundry } `
        -FailureMessage 'Unable to install the microsoft.foundry extension.'

    $TenantId = Read-RequiredValue -Prompt 'Foundry project tenant ID' -Value $TenantId
    Invoke-CheckedCommand -Command { azd auth login --tenant-id $TenantId } `
        -FailureMessage 'Azure Developer CLI authentication failed.'
}
finally {
    Remove-Item Env:AZURE_DEV_USER_AGENT -ErrorAction SilentlyContinue
}

$ProjectEndpoint = Read-RequiredValue -Prompt 'AI Foundry API project endpoint' -Value $ProjectEndpoint
$projectUri = $null
if (-not [uri]::TryCreate($ProjectEndpoint, [UriKind]::Absolute, [ref]$projectUri) -or `
    $projectUri.Scheme -ne 'https') {
    throw 'The Foundry project endpoint must be an absolute HTTPS URL.'
}
if (-not $ToolboxName) { $ToolboxName = "$Entity-toolbox" }

$publishArguments = @(
    '-Entity', $Entity,
    '-ProjectEndpoint', $ProjectEndpoint,
    '-ToolboxName', $ToolboxName
)
if ($UpdateSkills) { $publishArguments += '-UpdateSkills' }
& (Join-Path $PSScriptRoot 'Publish-Toolbox.ps1') @publishArguments
if ($LASTEXITCODE -ne 0) { throw 'Toolbox publication failed.' }
