# Entity Onboarding

For a complete worked example, see [Microsoft entity example](microsoft-entity-example.md).

## 1. Create an Overlay

```powershell
$env:PYTHONPATH = "$PWD/src"
python -m citadel_toolbox.cli init-entity entity-name --display-name "Entity Name"
```

Edit `entities/entity-name/overlay.yaml`. Disable capabilities the entity does not permit and replace
connection IDs, indexes, filters, domains, and MCP endpoints through environment variables.

## 2. Prepare Foundry

Create or select the entity's Foundry project. Create its Azure AI Search, MCP, and optional Work IQ
project connections using least privilege. Upload each enabled folder under `skills/` as a versioned
Foundry skill through Foundry Toolkit. Skill names must remain unchanged because the generated
Toolbox references them by name.

Work IQ is optional, preview, delegated-user based, and not supported in network-isolated projects.
Keep it disabled when those constraints do not fit the entity.

## 3. Build

Set every variable referenced by an enabled capability, then run:

```powershell
./scripts/Build-Toolbox.ps1 -Entity entity-name
```

For template review without secrets or endpoints, add `-AllowUnresolved`.

## 4. Publish and Promote

Install the `microsoft.foundry` azd extension and authenticate. Publish a new immutable version:

```powershell
./scripts/Publish-Toolbox.ps1 `
  -Entity entity-name `
  -ProjectEndpoint 'https://<account>.services.ai.azure.com/api/projects/<project>'
```

Test the version-specific endpoint printed by `azd`. Promote only after tool calls, approval handling,
identity, citations, and `resources/list` skill discovery pass:

```powershell
$env:AZURE_DEV_USER_AGENT = 'microsoft_foundry_skill'
azd ai toolbox publish entity-name-toolbox <version> --no-prompt
Remove-Item Env:AZURE_DEV_USER_AGENT
```

## 5. Connect Agents

Use the stable consumer endpoint:

```text
{project-endpoint}/toolboxes/{toolbox-name}/mcp?api-version=v1
```

Hosted Python agents should use Agent Framework `FoundryToolbox`; hosted .NET agents should use
`AddFoundryToolboxes`. Prompt agents attach the Toolbox MCP endpoint as their remote MCP tool.
Clients must support MCP Resources to discover attached skills.