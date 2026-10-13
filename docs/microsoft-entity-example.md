# Microsoft Entity Example

This walkthrough creates a `microsoft-toolbox` from the shared Citadel catalog. It begins with a
read-only configuration and publishes it to an existing Microsoft Foundry project.

## Current Deployment

The POC is deployed with the admin identity to:

- Project: `customer-demo-project`
- Foundry resource: `customer-demo-project-resource`
- Resource group: `rg-sibamoussa-4268`
- Region: `uaenorth`
- Toolbox: `microsoft-toolbox`, default version `1`
- Search: connection `aisearchresourcenhwnaa`, index `policy-index`
- Read-only MCP: connection `weather-tool`

Version `1` also includes approved Microsoft web search, Tool Search, and all three core skills.
Work IQ and transactional actions remain disabled.

## Prerequisites

You need:

- Python 3.11 or newer
- Azure Developer CLI (`azd`)
- The `microsoft.foundry` azd extension
- Access to a Microsoft Foundry project with the **Foundry User** role
- An Azure AI Search project connection and index
- A deployed read-only MCP endpoint for Microsoft systems
- Foundry project connections for Search and MCP authentication

Run all commands from the repository root.

## 1. Install and Validate the Project

```powershell
python -m pip install -e '.[dev,mcp]'
python -m pytest
python -m ruff check .
```

## 2. Create the Microsoft Overlay

```powershell
python -m citadel_toolbox.cli init-entity microsoft --display-name "Microsoft"
```

This entity is already initialized at:

```text
entities/microsoft/
  .env.example
  overlay.yaml
```

The core catalog remains unchanged. All Microsoft-specific configuration belongs in this overlay.

## 3. Start with Read-Only Capabilities

The deployed POC configuration is in `entities/microsoft/overlay.yaml`. Its Search and MCP
providers use non-secret project connection resource IDs from `customer-demo-project`.

Use this shape for another Microsoft project:

```yaml
metadata:
  name: microsoft-toolbox
  description: Shared Citadel capabilities customized for Microsoft.

tools:
  - id: enterprise-knowledge
    provider:
      project_connection_id: ${MICROSOFT_SEARCH_CONNECTION_ID}
      index_name: ${MICROSOFT_SEARCH_INDEX_NAME}

  - id: employee-context
    enabled: false

  - id: government-systems
    provider:
      server_label: microsoft-systems
      server_url: ${MICROSOFT_SYSTEMS_MCP_URL}
      project_connection_id: ${MICROSOFT_SYSTEMS_CONNECTION_ID}

  - id: approved-web-search
    provider:
      filters:
        allowed_domains:
          - microsoft.com
          - learn.microsoft.com

  - id: workflow-actions
    enabled: false

skills:
  - id: government-service-routing
    configuration:
      entity_name: Microsoft
      preferred_language: en
```

The deployed profile enables enterprise knowledge, read-only systems access, approved web search, Tool Search, and
the three core skills inherited from the catalog. Work IQ and transactional actions remain disabled.

## 4. Review the Generated Definition

Compile with unresolved placeholders before creating any cloud connections:

```powershell
./scripts/Build-Toolbox.ps1 -Entity microsoft -AllowUnresolved
Get-Content ./generated/microsoft/toolbox.yaml
```

Confirm that:

- No credentials or tokens appear in the generated YAML.
- `workflow-actions` and `work_iq_preview` are absent.
- `toolbox_search` is present.
- The expected skills appear under `skills:`.

## 5. Prepare the Foundry Project

Install the Foundry extension and authenticate:

```powershell
azd ext install microsoft.foundry
azd auth login
```

Set the project endpoint for the current shell:

```powershell
$projectEndpoint = 'https://customer-demo-project-resource.services.ai.azure.com/api/projects/customer-demo-project'
$env:AZURE_DEV_USER_AGENT = 'microsoft_foundry_skill'
azd ai project set $projectEndpoint
Remove-Item Env:AZURE_DEV_USER_AGENT
```

The current project already provides:

1. Azure AI Search connection `aisearchresourcenhwnaa` with index `policy-index`.
2. Remote-tool connection `weather-tool` for the read-only MCP server.
3. Project-scoped connection authentication; no credentials are stored in this repository.

Use Foundry Toolkit, the Foundry portal, or `azd ai connection create`. Do not put connection
credentials in this repository.

## 6. Upload the Core Skills

Open **Foundry Toolkit** in VS Code, select the target project, and upload each skill:

- `skills/enterprise-grounding/SKILL.md`
- `skills/government-service-routing/SKILL.md`
- `skills/safe-transaction/SKILL.md`

Keep the skill names unchanged. Skills referenced by a Toolbox must already exist in the same
Foundry project. Create a new immutable skill version when instructions change.

## 7. Review the Microsoft Resource References

The current non-secret project endpoint, connection IDs, and MCP URL are recorded in
`entities/microsoft/.env.example`. The deployed overlay contains the same resource references so a
strict build is reproducible without credentials.

For a different project, replace the entity-specific values in the overlay or use variables:

```powershell
$env:MICROSOFT_SEARCH_CONNECTION_ID = '/subscriptions/<subscription>/resourceGroups/<resource-group>/providers/Microsoft.CognitiveServices/accounts/<account>/projects/<project>/connections/<search-connection>'
$env:MICROSOFT_SYSTEMS_MCP_URL = 'https://<microsoft-systems-host>/mcp'
$env:MICROSOFT_SYSTEMS_CONNECTION_ID = '/subscriptions/<subscription>/resourceGroups/<resource-group>/providers/Microsoft.CognitiveServices/accounts/<account>/projects/<project>/connections/<mcp-connection>'
```

These values are process-scoped and disappear when the terminal closes.

## 8. Run a Strict Build

```powershell
./scripts/Build-Toolbox.ps1 -Entity microsoft
```

The build fails if an enabled capability has an unresolved variable or a write-capable tool lacks
`require_approval: always`.

## 9. Publish a Toolbox Version

```powershell
./scripts/Publish-Toolbox.ps1 `
  -Entity microsoft `
  -ProjectEndpoint $projectEndpoint `
  -ToolboxName microsoft-toolbox
```

The first version becomes the default automatically. Later runs create immutable versions without
silently changing the version used by agents.

## 10. Test the New Version

Use the version-specific endpoint printed by `azd` during publication:

```text
{project-endpoint}/toolboxes/microsoft-toolbox/versions/{version}/mcp?api-version=v1
```

Verify:

1. `tools/list` exposes `tool_search` and `call_tool`.
2. `tool_search` discovers enterprise knowledge, web, and Microsoft systems capabilities.
3. Search answers include expected citations and respect the entity filter.
4. The MCP status tool returns only authorized records.
5. `resources/list` returns all attached skills.
6. No write operation is available in this initial profile.

## 11. Promote a Validated Version

For versions after the first, promote only after validation:

```powershell
$env:AZURE_DEV_USER_AGENT = 'microsoft_foundry_skill'
azd ai toolbox publish microsoft-toolbox <version> --no-prompt
Remove-Item Env:AZURE_DEV_USER_AGENT
```

Agents should use the stable consumer endpoint:

```text
{project-endpoint}/toolboxes/microsoft-toolbox/mcp?api-version=v1
```

## 12. Connect Agents

For a prompt agent, add the consumer endpoint as its remote MCP tool. For a Python hosted agent, use
Agent Framework `FoundryToolbox`. For a .NET hosted agent, use `AddFoundryToolboxes`.

The consuming runtime must support MCP Resources to load attached skills. If actions are enabled
later, the runtime must also pause the exact pending call and enforce `require_approval: always`.

## Optional: Enable Work IQ

Create a Work IQ project connection, set `MICROSOFT_WORK_IQ_PROJECT_CONNECTION_ID`, and override
`employee-context` with `enabled: true`. Work IQ is preview, requires delegated user context, and is
not supported in network-isolated Foundry projects.

## Optional: Enable Actions

Deploy a separate action MCP server and connection, then enable `workflow-actions`. Keep read and
write services on separate identities. Do not publish until the hosted or prompt-agent runtime has
been tested to enforce approval for every state-changing call.