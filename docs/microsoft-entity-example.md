# Microsoft Entity Example

This generic example deploys `microsoft-toolbox` to an existing Microsoft Foundry project. It starts
read-only and contains no tenant, subscription, project, or endpoint values from a real deployment.

## 1. Initialize

The repository includes `entities/microsoft/overlay.yaml`. To recreate it from the shared template:

```powershell
python -m citadel_toolbox.cli init-entity microsoft --display-name 'Microsoft'
Copy-Item entities/microsoft/.env.example entities/microsoft/.env
```

## 2. Supply Project References

Replace every angle-bracket value in `entities/microsoft/.env`:

```dotenv
MICROSOFT_SEARCH_CONNECTION_ID=/subscriptions/<subscription>/resourceGroups/<resource-group>/providers/Microsoft.CognitiveServices/accounts/<account>/projects/<project>/connections/<search-connection>
MICROSOFT_SEARCH_INDEX_NAME=<existing-index-name>
MICROSOFT_SYSTEMS_MCP_URL=https://<read-mcp-host>/mcp
MICROSOFT_SYSTEMS_CONNECTION_ID=/subscriptions/<subscription>/resourceGroups/<resource-group>/providers/Microsoft.CognitiveServices/accounts/<account>/projects/<project>/connections/<read-mcp-connection>
```

These are resource references, not credentials. Foundry stores connection authentication.

The overlay enables Search, Microsoft-approved web domains, Toolbox Search, the read-only MCP
connection, and all core skills. Work IQ and workflow actions remain disabled.

## 3. Build

```powershell
./scripts/Build-Toolbox.ps1 -Entity microsoft
Get-Content generated/microsoft/toolbox.yaml
```

Compilation fails if `.env` is absent, incomplete, or still contains template placeholders. Confirm
that Search and MCP appear under `connections`, built-in providers under `tools`, and all three
skills under `skills`.

## 4. Authenticate and Publish

```powershell
azd extension install microsoft.foundry
azd auth login --tenant-id '<tenant-id>'
$projectEndpoint = 'https://<account>.services.ai.azure.com/api/projects/<project>'

./scripts/Publish-Toolbox.ps1 `
    -Entity microsoft `
    -ProjectEndpoint $projectEndpoint `
    -ToolboxName microsoft-toolbox
```

The script creates missing core skills before creating version 1. Existing skills are reused; pass
`-UpdateSkills` only when intentionally creating new skill versions.

## 5. Validate and Connect

Inspect the deployment and list versions:

```powershell
$env:AZURE_DEV_USER_AGENT = 'microsoft_foundry_skill'
try {
    azd ai toolbox show microsoft-toolbox `
        --project-endpoint $projectEndpoint --output json --no-prompt
    azd ai toolbox versions list microsoft-toolbox `
        --project-endpoint $projectEndpoint --output table --no-prompt
}
finally {
    Remove-Item Env:AZURE_DEV_USER_AGENT -ErrorAction SilentlyContinue
}
```

Validate the version-specific MCP endpoint. Test citations, domain restrictions, MCP authorization,
skill discovery, and the absence of write tools. Agents may then use:

```text
{project-endpoint}/toolboxes/microsoft-toolbox/mcp?api-version=v1
```

## Optional Changes

To enable Work IQ, create its project connection, add an entity variable and overlay override, and
confirm delegated-user and network requirements. To enable actions, deploy a separate action MCP
service and identity, retain `require_approval: always`, and verify approval behavior end to end.

For updates, promotion, and rollback, follow
[Operate Versions](../README.md#10-operate-versions).
