# Part 2: Register the Toolbox as an APIM MCP Server

Yes. The published Microsoft Foundry Toolbox is already an MCP server. Register that full endpoint
as an **existing MCP server** in Azure API Management, rather than importing the catalog YAML or
converting the tools to REST. The registration appears under **APIs > MCP servers**.
Start with [Part 1 in the README](../README.md#part-1-create-and-publish-the-toolbox) to create,
publish, and validate the Toolbox before registering it here.

```text
Agent -> APIM native MCP server -> managed Foundry Toolbox -> configured tools and skills
```

APIM is a gateway, not the Toolbox runtime. Publish the Toolbox first using the existing workflow.
Pass the **Consumer endpoint** printed by the publish script, including `?api-version=v1`.
Register the Toolbox endpoint rather than an individual downstream knowledge provider so consumers
can discover the governed tools and skill resources.

## Prerequisites

- An existing APIM instance in a supported tier: Developer, Basic, Standard, Premium, or a supported
  v2 equivalent. Consumption and APIM workspaces are not supported for native MCP registration.
- A published Foundry Toolbox endpoint reachable from APIM, including any required private routing.
- A system-assigned managed identity enabled on APIM. Grant that identity the least-privilege
  Foundry project data-plane role that permits invoking the Toolbox (typically Azure AI User),
  plus any downstream permissions required by your connection authentication model. The script
  checks identity presence; it does not create role assignments or prove data-plane access.
- Azure CLI signed in to the correct tenant, permission to read APIM and deploy its backend, API,
  and API policy in the selected subscription/resource group, and this Python package installed.
- At **All APIs**, set diagnostic frontend response payload logging to **0 bytes**. Also disable
  response body logging for this API and avoid inherited policies that access `context.Response.Body`.
  Response buffering can break MCP streaming. The registration does not modify global settings.

The generated policy uses APIM's identity to obtain a token for `https://ai.azure.com`. This is a
shared service identity, not delegated user identity. Do not use this default when Toolbox tools
require user-level authorization, such as delegated Work IQ; design and validate that flow separately.

## Register

Run from the repository root after installing the package through the normal setup workflow:

```powershell
./scripts/Register-ToolboxApim.ps1 `
  -SubscriptionId '<subscription-id>' `
  -ResourceGroup '<existing-apim-resource-group>' `
  -ApimName '<existing-apim-name>' `
  -BackendUrl 'https://<foundry-account>.services.ai.azure.com/api/projects/<project>/toolboxes/<toolbox>/mcp?api-version=v1'
```

Use `-WhatIf` to preview the target without writing files or calling Azure. The actual run generates
an ignored ARM template under `generated/apim/registration.json`, checks APIM, validates the
deployment, then incrementally creates or updates three resources:

1. A TLS-validated backend pointing to the exact Toolbox MCP endpoint.
2. A native `type: mcp` API using Streamable HTTP and requiring an APIM subscription.
3. An API policy that removes the client's subscription key before backend forwarding, obtains a
  managed-identity token, and disables response buffering. For the Foundry audience it also sends
  `Foundry-Features: Toolboxes=V1Preview`. If the backend URL includes `api-version`, the policy
  overrides that query parameter with the configured value rather than trusting client input.

The default API ID and path are `citadel-toolbox`. Use `-ApiId` and `-ApiPath` for separate entity
registrations. Reusing an API ID **replaces that API's policy and backend configuration**;
choose a new ID if an existing API has hand-managed policies. The script does not create products
or subscriptions, enforce approval in an agent, or change the Toolbox catalog.
Use a distinct API-scoped subscription for each allowed consumer. Add organization-specific rate
limits, permitted-tool policies, and metadata-only auditing before production use.

The registration uses APIM's `2025-09-01-preview` native MCP management contract. Confirm that API
version is available in your target cloud. The backend must support MCP `2025-06-18` or later.
APIM currently supports MCP tools and resources, not prompts.

## Generate Without Deploying

```powershell
citadel-toolbox export-apim `
  --apim-name '<existing-apim-name>' `
  --backend-url 'https://<foundry-account>.services.ai.azure.com/api/projects/<project>/toolboxes/<toolbox>/mcp?api-version=v1' `
  --api-id citadel-toolbox --path citadel-toolbox `
  --backend-audience https://ai.azure.com `
  --output generated/apim/registration.json
```

This command requires no Azure login or MCP SDK. It rejects credentials in URLs and query parameters
other than `api-version`. The generated template can also be deployed through your normal ARM pipeline.
For a non-Foundry MCP backend, supply its token audience. Omit `--backend-audience` for offline export,
or pass `-BackendAudience ''` to the registration script, only when backend authentication is handled
separately. Never expose an unauthenticated production backend that bypasses APIM access controls.

## Connect and Verify

The script prints the gateway endpoint, normally
`https://<apim-name>.azure-api.net/citadel-toolbox/mcp`. Use the actual gateway URL when APIM has a
custom domain. Merge the following example into your client's MCP configuration, substituting the
endpoint. Do not put keys in source control.

```json
{
  "inputs": [
    {
      "id": "citadel-apim-key",
      "type": "promptString",
      "description": "APIM API-scoped subscription key",
      "password": true
    }
  ],
  "servers": {
    "citadel-toolbox": {
      "type": "http",
      "url": "https://<apim-name>.azure-api.net/citadel-toolbox/mcp",
      "headers": {
        "Ocp-Apim-Subscription-Key": "${input:citadel-apim-key}"
      }
    }
  }
}
```

In VS Code, start that MCP server and verify initialization and tool discovery. Make a read-only
tool call and check its result against a direct Toolbox call. Requests without a valid APIM
subscription must fail. A successful ARM deployment alone does not establish backend connectivity,
RBAC correctness, tool behavior, or approval enforcement. Keep state-changing tool tests behind
explicit approval.

For a runnable hosted agent using the same APIM subscription-key route, see the
[Python example](../examples/python-agent/README.md#connect-through-apim). Set
`TOOLBOX_CONNECTION_MODE=apim`, point `TOOLBOX_ENDPOINT` at this gateway URL, and inject
`APIM_SUBSCRIPTION_KEY` into the agent process. The model still authenticates separately using
`DefaultAzureCredential`; APIM's managed identity authenticates the Toolbox backend calls.

If the backend returns 401/403, check APIM identity, token audience, project role assignments, and
the Toolbox's downstream connections. If discovery hangs, check network access and global/API
response logging and buffering policies first.

## Offline Regression Checks

Run from the repository root with the development dependencies installed:

```powershell
./.venv/Scripts/python.exe -m pytest tests
./.venv/Scripts/python.exe -m ruff check src tests
./tests/Test-RegisterToolboxApim.ps1
```

On Linux/macOS, use `.venv/bin/python` for the Python commands. The PowerShell test uses the same
interpreter detection as registration and also accepts `-PythonExecutable`. It mocks Azure CLI
calls and checks `-WhatIf`, deployment ordering, identity/tier prerequisites, failures, and explicit
authentication opt-out. These checks do not replace a live MCP initialization and tool-call test.

Reference: [Expose an existing MCP server in APIM](https://learn.microsoft.com/azure/api-management/expose-existing-mcp-server).