# Demo: Use the Toolbox from a Foundry Agent in the Portal

This is the no-local-code counterpart to the [Python agent demo](../examples/python-agent/README.md).
Attach the same APIM-hosted Toolbox to a Foundry agent and use its Playground to discover tools
and retrieve evidence. No Python process is required for this path.

## Demo Outcome

Show an agent in a consuming Foundry project (the spoke) using one governed MCP endpoint:

```text
Foundry agent Playground -> APIM Toolbox API -> Foundry Toolbox -> configured knowledge sources
```

Adding a Toolbox API in APIM does **not** automatically add a connection to a spoke project or
attach it to an agent. The connection below is an explicit consumer setup step. Select a remote
MCP tool; do not select **Create toolbox**, which would create another collection instead.

## Before the Demo

- Publish a read-only Toolbox and complete [APIM registration](apim-mcp.md). Verify the backend
  version's enabled sources work. Use an isolated test route if unready sources are excluded.
- Have access to the intended Foundry spoke project, permission to configure its agent/connections,
  and a model deployment available to that agent.
- Obtain the exact APIM gateway URL and an active API-scoped or associated product-scoped
  subscription key securely. The model gateway key does not necessarily authorize the Toolbox API.
- Ensure the agent runtime can reach APIM. A private endpoint needs the appropriate network path;
  being able to open the Playground in a browser does not prove runtime reachability.
- Choose one question answered by the entity's indexed documents and confirm the expected source.
  This repository supplies no policy dataset.

Use the gateway endpoint printed by registration, for example:

```text
https://<apim-name>.azure-api.net/citadel-toolbox
```

The endpoint is exactly the configured APIM API path. Do not append `/mcp` automatically, use the
APIM management URL, or put the key in the URL. If your isolated test API uses a different path,
enter that full path instead. The Foundry backend URL is not the consumer URL for this demo.

## 1. Open the Agent

1. In Microsoft Foundry, select the intended spoke project.
2. Open **Agents**, create or select the demo agent, and open **Playground**.
3. Select its model. Keep existing model gateway configuration if applicable; the Toolbox connection
   is separate and does not change model authentication.
4. Under **Tools**, select **Add** and the **Model Context Protocol (MCP)** remote-tool option.
   Portal labels can vary by release; the target dialog is **Add Model Context Protocol tool**.

## 2. Connect to the APIM Endpoint

In that dialog, enter:

| Field | Value |
| --- | --- |
| Name | `citadel_toolbox`, or a unique name accepted by the portal |
| Remote MCP Server endpoint | Your exact APIM Toolbox gateway URL |
| Authentication | **Key-based** |
| Credential name, left input | `Ocp-Apim-Subscription-Key` |
| Credential value, right input | The authorized APIM subscription key, entered securely |

Select **Connect**, complete any connection/tool-selection prompts, and save the agent changes.
Confirm the MCP connection appears under **Tools**. If the portal offers an approval setting,
retain the organization's required approval policy; do not disable it merely for the demo.

Enter the key only in the credential field. Do not put it in agent instructions, a chat message,
screenshots, recordings, or committed YAML. Share an agent configuration only after removing any
secrets. This flow stores the credential with the managed connection; it does not provision OAuth
or propagate employee identity to downstream tools.

## 3. Set the Agent Instructions

Use the following instructions, adjusting the connection name to match the one you added:

```text
Use citadel_toolbox for enterprise knowledge.
Discover relevant capabilities with tool_search, then invoke a discovered tool with call_tool
using its exact returned name and parameter schema. If a discovered tool is exposed directly,
you may invoke it directly using that schema.
Answer policy questions only from retrieved evidence and cite returned document titles and
page or section identifiers when present. If evidence is insufficient, say so.
Report tool failures honestly. Finding a tool does not prove it can execute successfully.
Do not claim access to unconnected services or that attached skills have been loaded.
```

These are demo instructions, not a security or approval enforcement mechanism. Save the changes
and start a new conversation so the test uses the updated configuration.

## 4. Demonstrate Discovery

Ask:

```text
What tools do you have access to? Use tool_search to check enterprise search and knowledge-base
retrieval capabilities. Give exact discovered tool names and distinguish discovery from execution.
```

Show the tool-call context or **Traces**, rather than relying only on the answer text. Depending on
the available sources, the expected evidence includes:

- A successful `tool_search` call and its returned schemas.
- The native Azure AI Search tool under the entity's Search connection name, if enabled.
- The Foundry IQ `knowledge_base_retrieve` tool under its connection-qualified name, if enabled.
- `tool_search` and `call_tool` as the Toolbox's discovery and invocation entry points.

Connection-qualified names differ per deployment. Discovery is relevance-based and might not return
every tool in one call. If prompted for approval, review the exact call and approve it according to
policy. A green approval indicator means the call was approved, not that every backend was tested.

## 5. Demonstrate a Grounded Answer

Ask a question based on your own documents, for example:

```text
Use the Foundry IQ knowledge-base retrieval tool to find the conditions for employees providing
services to third parties. Summarize only what the returned evidence supports, with source citations.
```

Replace the example topic if it is not in your dataset. In the call context or traces, show:

1. Discovery of the appropriate knowledge retrieval tool.
2. Actual invocation using `call_tool`, or a direct invocation of an exposed discovered tool.
3. A successful result containing evidence and source metadata, not a JSON-RPC error or `isError`.
4. An answer whose claims and citations match that evidence.

If native Search is also enabled, test it independently with a query known to be in the index.
Foundry IQ success does not prove native Search works: the native hybrid path requires an integrated
vectorizer, while the initializer's minimal semantic Foundry IQ path does not.

## 6. Explain the Authentication During the Demo

| Boundary | What happens |
| --- | --- |
| Foundry agent to APIM | The managed MCP connection sends the configured subscription key as `Ocp-Apim-Subscription-Key`. |
| APIM to Foundry Toolbox | APIM obtains a token using its selected managed identity, which needs Toolbox invocation access. |
| Toolbox to a source | Each Foundry project connection supplies its own downstream authentication. The optional initializer uses a broad Search admin API key. |
| Agent to model | Uses the agent's independently configured model access, including its model gateway route when configured. |

The consuming spoke does not need downstream Search credentials, but shared connections do not
automatically enforce each employee's document permissions. Work IQ requires its separate supported
delegated OAuth flow; APIM's shared identity does not provide it. See the
[authentication explanation](../README.md#three-authentication-boundaries).

## Skills Are a Separate Demo

This remote-MCP walkthrough demonstrates callable tools. Attached Toolbox skills are MCP resources,
not additional callable tools. Do not claim they are loaded merely because the connection works or
the agent names them in an answer. Verify resource support and explicit skill loading in the chosen
client before demonstrating their effect. The instructions above are manually supplied agent
instructions, not proof that the Toolbox's published skills were consumed.

## Troubleshoot a Failed Demo

| Symptom | Next check |
| --- | --- |
| Toolbox does not appear automatically in the spoke | Add the remote MCP connection explicitly in that project/agent. APIM registration is not catalog synchronization. |
| Generic tool-execution banner | Open the failed call's details or trace and inspect the underlying error. Never share keys, bearer tokens, or signed consent links when collecting evidence. |
| HTTP 401/403 | Check header spelling, subscription state/scope, and gateway policies; then separately check APIM's backend identity and source authorization. |
| HTTP 404 | Compare the full gateway URL with the API's configured path. |
| Missing connection or consent error | Fix the enabled source, or use a tested version/route that excludes it. Do not bypass authentication. |
| Discovery works, native Search execution fails | Check the effective query mode and index vectorizer/semantic configuration. |
| Agent says it has skills | Check actual resource loading; an answer alone is not proof. |

Before presenting the demo, verify both discovery and retrieval in a fresh conversation. The
[per-tool checklist](tool-prerequisites.md#acceptance-checklist) defines the broader readiness checks.

## Continue with the Python Demo

Use the same APIM endpoint with the [Python agent example](../examples/python-agent/README.md),
preferably using a separate consumer subscription for independent revocation and auditing. Only
the client changes: the gateway, Toolbox, and downstream connections are reused. The Python sample
calls its model directly; the portal agent can independently use its configured AI Gateway model.