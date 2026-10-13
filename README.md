# Citadel Toolbox Add-on

A reusable Microsoft Foundry Toolbox product for organizations that deploy the Microsoft Citadel
reference architecture. The core catalog is centrally governed while every entity configures its own
connections, indexes, approved domains, enabled capabilities, and skill versions without a fork.

## Included Capabilities

| Capability | Core implementation | Default |
| --- | --- | --- |
| Enterprise knowledge | Azure AI Search | Enabled |
| Employee and M365 context | Work IQ preview | Disabled |
| Government systems | Read-only MCP | Enabled |
| Approved public information | Restricted Web Search | Enabled |
| Workflow actions | Approval-gated MCP | Disabled |
| Tool discovery | Toolbox Search | Enabled |

The Toolbox also exposes three reusable skills as MCP resources: enterprise grounding, government
service routing, and safe transactions.

## Project Layout

- `catalog/core.yaml`: governed capabilities and defaults
- `entities/<entity>/overlay.yaml`: entity-owned customization
- `skills/`: versioned Foundry skill sources
- `src/citadel_toolbox/`: merge, validation, and rendering CLI
- `src/citadel_toolbox_mcp/`: replaceable reference government MCP provider
- `scripts/`: local build and Foundry version publication
- `docs/`: architecture and entity onboarding

## Local Setup

```powershell
python -m pip install -e '.[dev,mcp]'
$env:PYTHONPATH = "$PWD/src"
python -m pytest
python -m citadel_toolbox.cli compile `
	--overlay entities/example/overlay.yaml `
	--output generated/example/toolbox.yaml `
	--allow-unresolved
```

Run the sample MCP server over Streamable HTTP:

```powershell
python -m mcp run src/citadel_toolbox_mcp/server.py --transport streamable-http
```

The development MCP configuration is in `.vscode/mcp.json`.

## Customize an Entity

```powershell
python -m citadel_toolbox.cli init-entity entity-name --display-name "Entity Name"
```

See [entity onboarding](docs/entity-onboarding.md) for connection, skill upload, publication, testing,
and promotion. Follow the [Microsoft entity example](docs/microsoft-entity-example.md) for a complete
step-by-step walkthrough. See [architecture](docs/architecture.md) for ownership and security
boundaries.

## Replicate the Microsoft Entity Deployment

Use this workflow to deploy the shared catalog into another entity's existing Foundry project. Run
the commands from the repository root and replace values in angle brackets.

### 1. Validate Local Prerequisites

```powershell
python --version
az account show --query '{subscription:id, tenant:tenantId, user:user.name}' -o json
azd version
azd extension list

python -m pip install -e '.[dev,mcp]'
python -m pytest
python -m ruff check .
```

Install the Foundry extension if it is missing:

```powershell
azd extension install microsoft.foundry
```

Python 3.11 or newer is required. The Azure identity must exist in the tenant that owns the target
subscription. A subscription administrator from another tenant cannot sign in to the project unless
that identity is first added as an external user and granted the required RBAC role.

### 2. Find the Target Foundry Project

List Foundry-capable resources and their child projects in the intended subscription:

```powershell
$subscriptionId = '<subscription-id>'

az resource list `
	--subscription $subscriptionId `
	--resource-type Microsoft.CognitiveServices/accounts `
	--query "[?kind=='AIServices'].{name:name, resourceGroup:resourceGroup, location:location, id:id}" `
	-o table

az resource list `
	--subscription $subscriptionId `
	--query "[?type=='Microsoft.CognitiveServices/accounts/projects'].{name:name, resourceGroup:resourceGroup, location:location, id:id}" `
	-o table
```

Retrieve the selected project and copy its `AI Foundry API` endpoint:

```powershell
$projectResourceId = '<full-project-resource-id>'
$project = az resource show --ids $projectResourceId --api-version 2025-06-01 | ConvertFrom-Json
$projectEndpoint = $project.properties.endpoints.'AI Foundry API'
$projectEndpoint
```

Confirm `provisioningState` is `Succeeded`. If multiple projects exist, select the target explicitly;
do not infer it from the resource name.

### 3. Authenticate `azd` to the Owning Tenant

Use the tenant from `az account show` or the project identity metadata:

```powershell
$tenantId = '<tenant-id>'
azd auth logout
azd auth login --tenant-id $tenantId
```

Verify that the reported account is the intended deployment identity. Set the project context:

```powershell
$env:AZURE_DEV_USER_AGENT = 'microsoft_foundry_skill'
try {
	azd ai project set $projectEndpoint
	azd ai project show
}
finally {
	Remove-Item Env:AZURE_DEV_USER_AGENT -ErrorAction SilentlyContinue
}
```

### 4. Inventory Project Connections

Toolboxes reference existing Foundry project connections; they do not store connection credentials.
List non-secret connection metadata from the management plane:

```powershell
$connections = az rest `
	--method get `
	--url "https://management.azure.com$projectResourceId/connections?api-version=2025-06-01" |
	ConvertFrom-Json

$connections.value | ForEach-Object {
	[pscustomobject]@{
		Name = $_.name
		Category = $_.properties.category
		Authentication = $_.properties.authType
		Target = $_.properties.target
		ResourceId = $_.id
	}
} | Format-Table -AutoSize
```

For the initial read-only profile, identify:

- One `CognitiveSearch` connection and an existing semantic Search index.
- One `RemoteTool` connection to a read-only MCP server.
- Approved public domains for built-in web search.

Use the Foundry portal or an identity with `Search Index Data Reader` to list indexes. Do not store
Search admin keys, API keys, OAuth tokens, or connection secrets in this repository.

### 5. Create and Configure the Entity Overlay

```powershell
$entity = '<entity-name>'
python -m citadel_toolbox.cli init-entity $entity --display-name '<Entity Display Name>'
```

Edit `entities/<entity-name>/overlay.yaml`. Keep project-specific values here rather than changing
`catalog/core.yaml`:

```yaml
metadata:
	name: <entity-name>-toolbox
	description: Shared Citadel capabilities customized for <Entity Display Name>.

tools:
	- id: enterprise-knowledge
		provider:
			project_connection_id: <full-search-connection-resource-id>
			index_name: <search-index-name>

	- id: employee-context
		enabled: false

	- id: government-systems
		provider:
			server_label: <entity-name>-systems
			server_url: https://<read-only-mcp-host>/mcp
			project_connection_id: <full-mcp-connection-resource-id>

	- id: approved-web-search
		provider:
			filters:
				allowed_domains:
					- <approved-domain.example>

	- id: workflow-actions
		enabled: false

skills:
	- id: government-service-routing
		configuration:
			entity_name: <Entity Display Name>
			preferred_language: en
```

Start read-only. Enable Work IQ only after delegated-user consent and network compatibility are
confirmed. Enable action tools only when the consuming runtime enforces explicit approval.

### 6. Build and Review Before Publishing

Use an unresolved build while preparing connections, then require a strict build before publication:

```powershell
./scripts/Build-Toolbox.ps1 -Entity $entity -AllowUnresolved
Get-Content "./generated/$entity/toolbox.yaml"

./scripts/Build-Toolbox.ps1 -Entity $entity
```

The generated Foundry file must place Search and MCP references under `connections`, built-in tools
under `tools`, and reusable skill references under `skills`. Confirm it contains no credentials and
that disabled Work IQ and action providers are absent.

### 7. Upload the Core Skills

Skills must exist in the same Foundry project before the Toolbox references them. For a new project:

```powershell
$env:AZURE_DEV_USER_AGENT = 'microsoft_foundry_skill'
try {
	azd ai skill create enterprise-grounding `
		--file ./skills/enterprise-grounding/SKILL.md `
		--project-endpoint $projectEndpoint --no-prompt

	azd ai skill create government-service-routing `
		--file ./skills/government-service-routing/SKILL.md `
		--project-endpoint $projectEndpoint --no-prompt

	azd ai skill create safe-transaction `
		--file ./skills/safe-transaction/SKILL.md `
		--project-endpoint $projectEndpoint --no-prompt

	azd ai skill list --project-endpoint $projectEndpoint --output json --no-prompt
}
finally {
	Remove-Item Env:AZURE_DEV_USER_AGENT -ErrorAction SilentlyContinue
}
```

If a skill already exists, use `azd ai skill update <name> --file <path>` to create a new immutable
default version instead of deleting it.

### 8. Create the Toolbox Version

```powershell
$toolboxName = "$entity-toolbox"

./scripts/Publish-Toolbox.ps1 `
	-Entity $entity `
	-ProjectEndpoint $projectEndpoint `
	-ToolboxName $toolboxName
```

The first successful version becomes the default automatically. The command prints a version-specific
endpoint for validation and a stable consumer endpoint for agents.

### 9. Verify the Cloud Definition and MCP Endpoint

Inspect the deployed definition:

```powershell
$env:AZURE_DEV_USER_AGENT = 'microsoft_foundry_skill'
try {
	azd ai toolbox show $toolboxName `
		--project-endpoint $projectEndpoint `
		--output json --no-prompt
}
finally {
	Remove-Item Env:AZURE_DEV_USER_AGENT -ErrorAction SilentlyContinue
}
```

Check the immutable version endpoint with an MCP initialization request:

```powershell
$version = '<created-version>'
$versionEndpoint = "$projectEndpoint/toolboxes/$toolboxName/versions/$version/mcp?api-version=v1"
$token = az account get-access-token --resource https://ai.azure.com --query accessToken -o tsv

try {
	$headers = @{
		Authorization = "Bearer $token"
		Accept = 'application/json, text/event-stream'
	}
	$body = @{
		jsonrpc = '2.0'
		id = 1
		method = 'initialize'
		params = @{
			protocolVersion = '2025-03-26'
			capabilities = @{}
			clientInfo = @{ name = 'citadel-toolbox-validation'; version = '1.0' }
		}
	} | ConvertTo-Json -Depth 8

	Invoke-WebRequest `
		-Method Post -Uri $versionEndpoint -Headers $headers `
		-ContentType 'application/json' -Body $body
}
finally {
	$token = $null
	$headers = $null
}
```

Expect HTTP `200` and an MCP initialization result. Then test Search citations, MCP authorization,
web-domain restrictions, skill resources, and the absence of write operations.

### 10. Promote Later Versions

Creating later immutable versions does not change the version used by consumers. Promote only after
version-specific validation:

```powershell
$env:AZURE_DEV_USER_AGENT = 'microsoft_foundry_skill'
try {
	azd ai toolbox publish $toolboxName <validated-version> `
		--project-endpoint $projectEndpoint --no-prompt
}
finally {
	Remove-Item Env:AZURE_DEV_USER_AGENT -ErrorAction SilentlyContinue
}
```

Configure agents with the stable consumer endpoint:

```text
{project-endpoint}/toolboxes/{toolbox-name}/mcp?api-version=v1
```

## Production Guardrails

- Store credentials only in Foundry project connections or an approved secret store.
- Use separate read and action MCP services, connections, and identities.
- Enforce approval in the consuming runtime; Toolbox metadata alone does not block a tool call.
- Test immutable version endpoints before promoting the default version.
- Treat Work IQ, Toolbox Search, and attached skills according to their current preview terms.