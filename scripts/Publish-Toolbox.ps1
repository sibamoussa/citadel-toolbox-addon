param(
    [Parameter(Mandatory)]
    [ValidatePattern('^[a-z0-9]+(?:-[a-z0-9]+)*$')]
    [string]$Entity,

    [Parameter(Mandatory)]
    [string]$ProjectEndpoint,

    [string]$ToolboxName = "$Entity-toolbox",

    [switch]$UpdateSkills
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$toolboxFile = Join-Path $root "generated\$Entity\toolbox.yaml"
$skillsRoot = Join-Path $root 'skills'

if (-not (Get-Command azd -ErrorAction SilentlyContinue)) {
    throw 'Azure Developer CLI (azd) is required. Install it from https://aka.ms/install-azd.'
}

& (Join-Path $PSScriptRoot 'Build-Toolbox.ps1') -Entity $Entity
if ($LASTEXITCODE -ne 0) {
    throw "Toolbox build failed"
}

$env:AZURE_DEV_USER_AGENT = 'microsoft_foundry_skill'
try {
    azd ai project set $ProjectEndpoint
    if ($LASTEXITCODE -ne 0) { throw 'Unable to select the Foundry project' }

    $toolboxInventoryJson = azd ai toolbox list `
        --project-endpoint $ProjectEndpoint --output json --no-prompt
    if ($LASTEXITCODE -ne 0) {
        throw 'Unable to list Foundry Toolboxes. Reauthenticate with azd and confirm project access.'
    }
    $toolboxInventoryResult = $toolboxInventoryJson | ConvertFrom-Json
    $toolboxes = if ($null -ne $toolboxInventoryResult.toolboxes) {
        @($toolboxInventoryResult.toolboxes)
    }
    else {
        @($toolboxInventoryResult)
    }
    if ($ToolboxName -in @($toolboxes | ForEach-Object { $_.name })) {
        throw "Toolbox '$ToolboxName' already exists. Follow the version update workflow in README.md."
    }

    $skillInventoryJson = azd ai skill list `
        --project-endpoint $ProjectEndpoint --output json --no-prompt
    if ($LASTEXITCODE -ne 0) {
        throw 'Unable to list Foundry skills. Run azd auth login --tenant-id <owning-tenant-id>, then confirm the identity has project access.'
    }
    $skillInventoryResult = $skillInventoryJson | ConvertFrom-Json
    $skillInventory = if ($null -ne $skillInventoryResult.skills) {
        @($skillInventoryResult.skills)
    }
    else {
        @($skillInventoryResult)
    }
    $existingSkillNames = @($skillInventory | ForEach-Object { $_.name })

    foreach ($skillFile in Get-ChildItem $skillsRoot -Filter SKILL.md -Recurse) {
        $skillName = $skillFile.Directory.Name
        if ($skillName -in $existingSkillNames) {
            if ($UpdateSkills) {
                azd ai skill update $skillName --file $skillFile.FullName `
                    --project-endpoint $ProjectEndpoint --no-prompt
                if ($LASTEXITCODE -ne 0) { throw "Unable to update Foundry skill: $skillName" }
            }
            else {
                Write-Host "Using existing Foundry skill: $skillName"
            }
        }
        else {
            azd ai skill create $skillName --file $skillFile.FullName `
                --project-endpoint $ProjectEndpoint --no-prompt
            if ($LASTEXITCODE -ne 0) { throw "Unable to create Foundry skill: $skillName" }
        }
    }

    azd ai toolbox create $ToolboxName --from-file $toolboxFile `
        --project-endpoint $ProjectEndpoint --no-prompt
    if ($LASTEXITCODE -ne 0) { throw 'Unable to create the Toolbox version' }
}
finally {
    Remove-Item Env:AZURE_DEV_USER_AGENT -ErrorAction SilentlyContinue
}

Write-Host "Test the version-specific endpoint printed above before promotion."
Write-Host "Consumer endpoint: $ProjectEndpoint/toolboxes/$ToolboxName/mcp?api-version=v1"