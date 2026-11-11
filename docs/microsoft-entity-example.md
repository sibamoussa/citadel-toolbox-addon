# Microsoft Entity Example

This generic example deploys `microsoft-toolbox` to an existing Microsoft Foundry project. It starts
read-only and contains no tenant, subscription, project, or endpoint values from a real deployment.

## Guided Deployment

The repository includes `entities/microsoft/overlay.yaml`. Run one guided command from the repository
root:

```powershell
./scripts/Setup-Toolbox.ps1 -Entity microsoft -DisplayName 'Microsoft'
```

In VS Code, the equivalent is **Terminal > Run Task > Citadel Toolbox: Guided setup and publish**.
Enter `microsoft` when prompted for the entity. The script installs dependencies, reuses the
checked-in overlay, collects project references, creates `.env`, validates, authenticates, and
publishes.

## Collected Project References

Search configuration writes the first two values to ignored `entities/microsoft/.env`. Add the
Microsoft Foundry IQ and Work IQ references required by this overlay before strict validation,
following [the environment template](../entities/microsoft/.env.example):

```dotenv
MICROSOFT_SEARCH_CONNECTION_ID=/subscriptions/<subscription>/resourceGroups/<resource-group>/providers/Microsoft.CognitiveServices/accounts/<account>/projects/<project>/connections/<search-connection>
MICROSOFT_SEARCH_INDEX_NAME=<existing-index-name>
MICROSOFT_FOUNDRY_IQ_MCP_URL=https://<search-service>.search.windows.net/knowledgebases/<knowledge-base>/mcp?api-version=2026-08-01-preview
MICROSOFT_FOUNDRY_IQ_CONNECTION_ID=/subscriptions/<subscription>/resourceGroups/<resource-group>/providers/Microsoft.CognitiveServices/accounts/<account>/projects/<project>/connections/<foundry-iq-mcp-connection>
WORK_IQ_PROJECT_CONNECTION_ID=/subscriptions/<subscription>/resourceGroups/<resource-group>/providers/Microsoft.CognitiveServices/accounts/<account>/projects/<project>/connections/<work-iq-connection>
```

The overlay enables Azure AI Search, Microsoft Foundry IQ, Work IQ, and distinct Toolbox Search.
The shared catalog supplies enterprise-grounding; the Microsoft overlay adds workplace-context
for authorized Work IQ retrieval and consent handling. Work IQ is optional and disabled by
default in the shared catalog, but enabled for Microsoft. Both IQ integrations require existing,
compatible project connections; the setup does not create them or obtain delegated-user consent.

Use `-Reconfigure` to update Search values in an existing `.env`, or `-SkipPublish` to stop after strict local
validation. These values are resource references, not credentials; Foundry stores authentication.

To configure the Search values directly for the existing entity:

```powershell
citadel-toolbox configure-entity microsoft `
    --search-connection-id '<search-project-connection-resource-id>' `
    --search-index-name '<existing-index-name>'
```

This command updates Search values and preserves existing IQ references in `.env`. For a new
configuration, add the IQ references above before building or publishing.

## Advanced Build

```powershell
./scripts/Build-Toolbox.ps1 -Entity microsoft
Get-Content generated/microsoft/toolbox.yaml
```

Compilation fails if `.env` is absent, incomplete, or still contains template placeholders. Confirm
that Search and the IQ project connections appear under `connections`, `toolbox_search` appears
under `tools`, and both `enterprise-grounding` and `workplace-context` appear under `skills`.

## Advanced Publish

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

## Validate and Connect

On 2026-11-11, `microsoft-toolbox` version 3 was published and independently verified as the default.
Editing the source catalog does not change its attached skills or connections. Work IQ's last
runtime check returned `CONSENT_REQUIRED`, blocking tool discovery. Publication does not prove
delegated access or successful end-to-end operation through APIM.

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

Validate the version-specific MCP endpoint. Test authorized Search and Foundry IQ retrieval with
citations, Toolbox Search, skill discovery, and delegated Work IQ access. The direct backend
consumer endpoint is:

```text
{project-endpoint}/toolboxes/microsoft-toolbox/mcp?api-version=v1
```

To consume this endpoint from code, follow the runnable
[Python Agent Framework example](../examples/python-agent/README.md). Set `TOOLBOX_ENDPOINT` to the
URL above with `TOOLBOX_CONNECTION_MODE=foundry` for direct validation, configure the project
endpoint and model deployment, then press **F5** in VS Code. For the governed APIM route, use
`TOOLBOX_CONNECTION_MODE=apim`, the gateway URL, and an API-scoped subscription key. Neither route
alone implements delegated Work IQ authentication.

## Work IQ Requirements

Microsoft already enables Work IQ. Confirm its project connection, delegated-user consent, tenant
policy, and network requirements. Work IQ preview does not support network-isolated Foundry
projects. APIM's shared managed identity does not forward the user's identity; validate a supported
delegated authentication flow separately and resolve `CONSENT_REQUIRED` before claiming readiness.

For updates, promotion, and rollback, follow
[Operate Versions](../README.md#operate-versions).
