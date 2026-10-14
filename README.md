# Citadel Toolbox Add-on

A reusable Microsoft Foundry Toolbox add-on for Citadel deployments. A governed core defines the
approved tools and skills; each customer supplies only an entity overlay and Foundry connection
references. Customers do not fork the catalog or store credentials in this repository.

## What Is Included

| Capability | Provider | Default |
| --- | --- | --- |
| Enterprise knowledge | Azure AI Search | Enabled |
| Government systems | Read-only MCP | Enabled |
| Approved public information | Restricted Web Search | Enabled |
| Tool discovery | Toolbox Search | Enabled |
| Employee and M365 context | Work IQ preview | Disabled |
| Workflow actions | Approval-gated MCP | Disabled |

Three reusable Foundry skills are provisioned by the publish script: enterprise grounding,
government service routing, and safe transactions.

## Prerequisites

- Windows PowerShell 7 or later
- Python 3.11 or newer
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli)
- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd)
- Access to an existing Microsoft Foundry project
- A project connection to Azure AI Search and an existing index
- A project connection to a deployed read-only MCP endpoint

The deployment identity must belong to the tenant that owns the project and have permission to use
the project and its connections. This add-on does not create the Foundry project, Search index, MCP
service, or project connections.

## Deploy in 10 Steps

Run every command from the repository root.

### 1. Clone and Install

```powershell
git clone https://github.com/sibamoussa/citadel-toolbox-addon.git
Set-Location citadel-toolbox-addon
python -m venv .venv
./.venv/Scripts/Activate.ps1
python -m pip install -e '.[dev,mcp]'
python -m pytest
python -m ruff check .
```

### 2. Install the Foundry Extension

```powershell
azd extension install microsoft.foundry
azd auth login --tenant-id '<tenant-id>'
```

Confirm the signed-in account is the intended deployment identity.

If a later command reports `AzureDeveloperCLICredential`, repeat `azd auth login` with the owning
tenant ID. Azure CLI and Azure Developer CLI maintain separate sign-in sessions.

### 3. Select the Foundry Project

Copy the `AI Foundry API` endpoint from the project overview in the Foundry portal. It has this
shape:

```text
https://<account>.services.ai.azure.com/api/projects/<project>
```

```powershell
$projectEndpoint = 'https://<account>.services.ai.azure.com/api/projects/<project>'
$env:AZURE_DEV_USER_AGENT = 'microsoft_foundry_skill'
try {
    azd ai project set $projectEndpoint
    azd ai project show
    azd ai connection list --project-endpoint $projectEndpoint
}
finally {
    Remove-Item Env:AZURE_DEV_USER_AGENT -ErrorAction SilentlyContinue
}
```

Identify the Search and read-only MCP project connection names. Their full resource IDs end in
`/connections/<connection-name>`.

### 4. Initialize the Entity

Use lowercase letters, numbers, and hyphens for the entity name.

```powershell
$entity = 'contoso'
python -m citadel_toolbox.cli init-entity $entity --display-name 'Contoso'
```

This creates `entities/contoso/overlay.yaml` and `entities/contoso/.env.example`. Keep customer
settings in this directory; do not edit `catalog/core.yaml` for one customer.

### 5. Configure the Entity

```powershell
Copy-Item "entities/$entity/.env.example" "entities/$entity/.env"
```

Edit the new `.env` and replace every angle-bracket value:

```dotenv
CONTOSO_SEARCH_CONNECTION_ID=/subscriptions/<subscription>/resourceGroups/<resource-group>/providers/Microsoft.CognitiveServices/accounts/<account>/projects/<project>/connections/<search-connection>
CONTOSO_SEARCH_INDEX_NAME=<existing-index-name>
CONTOSO_GOVERNMENT_SYSTEMS_MCP_URL=https://<read-mcp-host>/mcp
CONTOSO_GOVERNMENT_SYSTEMS_CONNECTION_ID=/subscriptions/<subscription>/resourceGroups/<resource-group>/providers/Microsoft.CognitiveServices/accounts/<account>/projects/<project>/connections/<read-mcp-connection>
```

Edit `entities/contoso/overlay.yaml` to set approved domains, the Search entity filter, names, and
descriptions. Leave Work IQ and workflow actions disabled for the first deployment.

The `.env` file is ignored by Git. It should contain resource references and URLs, never API keys,
tokens, passwords, or connection secrets.

### 6. Run the Strict Build

```powershell
./scripts/Build-Toolbox.ps1 -Entity $entity
Get-Content "generated/$entity/toolbox.yaml"
```

Strict compilation rejects missing variables, empty values, unchanged `<placeholder>` values,
missing connection fields, missing skill files, and unsafe write-tool approval settings.

Review the generated file. Search and MCP providers must be under `connections`; built-in providers
must be under `tools`; skills must be under `skills`. The file must not contain credentials.

### 7. Publish the First Version

```powershell
./scripts/Publish-Toolbox.ps1 `
    -Entity $entity `
    -ProjectEndpoint $projectEndpoint `
    -ToolboxName "$entity-toolbox"
```

The script strictly rebuilds the definition, selects the project, creates missing core skills,
reuses existing skills, checks for a Toolbox name collision, and creates version 1. Version 1
becomes the default automatically. Use `-UpdateSkills` only when intentionally publishing new skill
versions.

### 8. Validate the Deployment

```powershell
$toolboxName = "$entity-toolbox"
$env:AZURE_DEV_USER_AGENT = 'microsoft_foundry_skill'
try {
    azd ai toolbox show $toolboxName `
        --project-endpoint $projectEndpoint --output json --no-prompt
    azd ai toolbox versions list $toolboxName `
        --project-endpoint $projectEndpoint --output table --no-prompt
}
finally {
    Remove-Item Env:AZURE_DEV_USER_AGENT -ErrorAction SilentlyContinue
}
```

Test the version-specific MCP endpoint reported by the CLI before connecting agents. Confirm Search
returns expected citations, web search stays within approved domains, `resources/list` discovers the
skills, the read MCP enforces identity and authorization, and no state-changing operation is
available.

### 9. Connect an Agent

Use the stable endpoint only after validation:

```text
{project-endpoint}/toolboxes/{toolbox-name}/mcp?api-version=v1
```

Python hosted agents use Agent Framework `FoundryToolbox`; .NET hosted agents use
`AddFoundryToolboxes`; prompt agents attach the endpoint as a remote MCP tool. The client must
support MCP Resources to discover attached skills.

### 10. Operate Versions

Foundry Toolbox versions are immutable. The publish script creates the first version only. For an
existing Toolbox, use the installed `azd ai toolbox connection add/remove` and
`azd ai toolbox skill add/remove` commands to branch a new version, then test its version-specific
endpoint. Run each command with `--help` because available provider options follow the installed
`microsoft.foundry` extension version.

Promote a validated version:

```powershell
$env:AZURE_DEV_USER_AGENT = 'microsoft_foundry_skill'
try {
    azd ai toolbox publish $toolboxName '<new-version>' `
        --project-endpoint $projectEndpoint --no-prompt
}
finally {
    Remove-Item Env:AZURE_DEV_USER_AGENT -ErrorAction SilentlyContinue
}
```

Rollback uses the same command with the last known-good version. List available versions first:

```powershell
azd ai toolbox versions list $toolboxName `
    --project-endpoint $projectEndpoint --output table --no-prompt
azd ai toolbox publish $toolboxName '<known-good-version>' `
    --project-endpoint $projectEndpoint --no-prompt
```

## Local MCP Reference Server

The included in-memory MCP service is a development adapter, not a production backend. Read and
action profiles are deliberately separate:

```powershell
python -m citadel_toolbox_mcp.server --profile read --transport streamable-http
python -m citadel_toolbox_mcp.server --profile actions --transport streamable-http
```

The VS Code development configuration in `.vscode/mcp.json` starts the read profile over stdio.
Replace `GovernmentService` with an authenticated entity backend before production deployment.

## Production Guardrails

- Store credentials only in Foundry project connections or an approved secret store.
- Use separate read and action MCP deployments, connections, and managed identities.
- Enforce approval in the consuming runtime; metadata alone does not block a call.
- Test immutable version endpoints before changing the default version.
- Keep Work IQ disabled unless delegated-user consent and network constraints are satisfied.
- Treat generated Toolbox definitions as disposable build artifacts.

See [entity onboarding](docs/entity-onboarding.md), the generic
[Microsoft example](docs/microsoft-entity-example.md), and [architecture](docs/architecture.md) for
additional context.
