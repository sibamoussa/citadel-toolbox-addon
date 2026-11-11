# Toolbox Tool Prerequisites

This is a **bring-your-own-data and bring-your-own-services** repository. Cloning it does not
provide policy documents, a populated Search index, Microsoft 365 access, or a model deployment.
Names such as `policy-index` in examples are placeholders for an index the entity owns, not a
dataset shipped with this repository. Do not reuse another customer's connections or data.

## Readiness by Capability

| Capability | Required before use | Repository automation | Proof of readiness |
| --- | --- | --- | --- |
| Native Azure AI Search (`enterprise-knowledge`) | Populated index, compatible retrieval configuration, authenticated Foundry Search connection | References an existing connection/index; optional initializer creates the connection only | An actual query returns authorized records, not just a discovered tool |
| Foundry IQ (`foundry-iq`) | Populated index with semantic configuration, knowledge source/base, authenticated MCP project connection | Optional initializer creates source, base, and connection over the existing index | `knowledge_base_retrieve` returns attributable evidence through the intended route |
| Toolbox Search (`tool-discovery`) | Published Toolbox with healthy enabled sources | Compiler includes built-in `toolbox_search`; no separate service or index | `tool_search` discovers expected tools; then invoke a discovered tool separately |
| Work IQ (`employee-context`, optional preview) | Supported M365 tenant/user entitlement, OAuth app/connection, consent, delegated identity flow, compatible networking | References an existing connection only | Authorized user retrieval succeeds and honors user permissions |
| Skills | Local skill files, published skill references, client resource support | Publisher creates missing skills; existing skills require explicit update | MCP resources are available and the consuming agent actually loads the instructions |

The shared catalog enables native Search and discovery, but disables Work IQ. The Microsoft overlay
also enables Foundry IQ and Work IQ. **Enabled in YAML does not mean provisioned or working.**

## Starting Without an Index

For the index-backed policy scenario, complete these steps in order:

1. Select the entity's documents, data owner, permitted users, and document-access rules.
2. Create an Azure AI Search service in a region/tier supporting the features you intend to use.
3. Design an index with a key, searchable document text, and retrievable citation metadata such as
   document title, source identifier/path, and page or section. Configure semantic ranking fields.
4. Build and run an ingestion pipeline to extract, chunk, and upload the documents. If using vector
   retrieval, generate embeddings and configure matching dimensions, vector profiles, and models.
5. Test retrieval directly against the populated index. An empty index or a successful index create
   is not a working knowledge source.
6. Create the Foundry project connections and, for Foundry IQ, the knowledge source and base. Use
   the [optional initializer](../README.md#optional-knowledge-initialization) only after steps 1-5.
7. Fill the entity's local references, build, publish, and test the version-specific Toolbox MCP
   endpoint before promoting it. Register and test APIM separately if consumers use the gateway.

Steps 1-5 are **not implemented by this repository**. Use an entity-owned ingestion process; the
Toolbox does not include sample policy content or copy documents from a different deployment.
Model embeddings and indexing/retrieval can incur separate charges.

## Native Azure AI Search

Required inputs:

- An existing Search service and populated index with retrievable source metadata.
- A Foundry project connection to that Search service, with working credentials or a supported
  identity that has query access. A connection resource existing is not proof its credentials work.
- A vector field and profile with a compatible **integrated vectorizer**, plus a semantic
  configuration, for the current `vector_semantic_hybrid` query mode. Existing document vectors
  alone do not provide query-time text-to-vector conversion. Configure model access and network
  reachability for the vectorizer as well.
- Network access from the retrieval runtime to Search and any embedding endpoint, and an
  authorization design appropriate for the indexed documents.
- Shared entity variables `AZURE_AI_SEARCH_CONNECTION_ID` and `AZURE_AI_SEARCH_INDEX_NAME`, or
  Microsoft variables `MICROSOFT_SEARCH_CONNECTION_ID` and `MICROSOFT_SEARCH_INDEX_NAME`.

If execution reports `Query type vector_semantic_hybrid requires a vector field with integrated
vectorizer, but none was found`, this is an index/retrieval configuration failure, not an APIM
subscription-key failure. Configure the compatible vectorizer, or independently configure and
verify a supported non-vector retrieval mode. Do not assume changing catalog metadata alone
changes the effective Foundry connection-backed tool configuration.

The initializer does not add vector fields, embeddings, vectorizers, or model permissions. Its
successful completion does **not** certify native hybrid Search readiness.

## Foundry IQ

For the Search-index-backed route implemented here, provide:

- A populated Search index with an existing semantic configuration and retrievable evidence fields.
- A Search `searchIndex` knowledge source pointing to that index and semantic configuration.
- A knowledge base referencing that source, using a supported Search API version.
- A `RemoteTool` MCP connection in the Toolbox's Foundry project, targeting the complete knowledge
  base endpoint, including its API-version query parameter, with working downstream authentication.
- `MICROSOFT_FOUNDRY_IQ_MCP_URL` and `MICROSOFT_FOUNDRY_IQ_CONNECTION_ID` for the Microsoft overlay.

The optional initializer creates a base with `minimal` retrieval reasoning and `extractiveData`.
That semantic retrieval path does not require the native Search tool's integrated vectorizer or a
retrieval reasoning model. Other knowledge-base configurations can have additional model, vector,
permission, and regional prerequisites. Foundry IQ working does not prove native Search works,
even when both use the same index.

The initializer requires API keys enabled, explicit `-UseSearchApiKey`, permission to list Search
admin keys, Search data-plane management access, and Foundry project-connection read/create access.
It stores a **broad existing Search admin key** in the two Foundry connections. This is not a
least-privilege query credential. Identity-based setup must be configured separately where supported;
there is no automatic authentication fallback. See the [initializer contract](../README.md#optional-knowledge-initialization)
for drift handling and partial-run behavior.

## Work IQ (Optional Preview)

Do not enable this tool merely because its catalog entry exists. Before publication, confirm:

- The intended tenant, users, Microsoft 365 data, licensing/entitlement, and tenant policy meet the
  current [Work IQ Foundry requirements](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/work-iq/mcp/quickstart/foundry).
- An approved OAuth client app registration and the required delegated permissions/consent exist.
  For custom OAuth, configure the required client credential securely, tenant authorization/token
  endpoints, the connection-generated redirect URI, and the documented scopes. Never put client
  secrets or signed consent links in Git, overlays, or chat.
- The Foundry MCP connection targets `https://workiq.svc.cloud.microsoft/mcp`, not the Work IQ A2A
  endpoint or the Foundry management MCP endpoint, and `WORK_IQ_PROJECT_CONNECTION_ID` references it.
- User sign-in and the supported delegated authorization flow work end to end. An APIM subscription
  key plus APIM's managed identity does **not** forward the user's identity or complete OAuth consent.
- The project's networking is compatible; this catalog marks Work IQ unsupported for
  network-isolated projects.

Neither the initializer nor the publisher creates the OAuth app, Work IQ connection, consent, or
delegated authentication flow. Missing/deleted connections and outstanding consent can block
Toolbox discovery, including otherwise healthy sources.

For a policy-only entity, disable Work IQ in its overlay before building:

```yaml
tools:
  - id: employee-context
    enabled: false
skills:
  - id: workplace-context
    enabled: false
```

This removes an optional source; it does not bypass authentication. Keep the relevant Search and/or
Foundry IQ sources enabled and configured. Existing immutable versions do not change: create and
test a new version, then explicitly promote it or use an isolated version-specific test route.

## Skills

Skills supply instructions, not data access or credentials. Verify published references through
MCP resources and explicitly load/apply those resources in the consuming agent. Tool discovery
alone does not prove skill instructions were loaded; the Python example does not automatically
load skill resources.

## Shared Runtime and APIM Requirements

- Install PowerShell 7+, Python 3.11+, Azure CLI, Azure Developer CLI, and the Foundry extension
  required by the [setup workflow](../README.md#part-1-create-and-publish-the-toolbox).
- Use an existing Foundry project with Toolbox availability and a publishing identity authorized
  to manage the Toolbox, skills, and required connections in the correct tenant.
- For an agent, supply a compatible accessible model deployment and its credentials. A model is
  needed by the agent, not by built-in Toolbox discovery. The Python example calls the model
  directly; registering the Toolbox in APIM does not register a model API.
- Follow the [APIM prerequisites](apim-mcp.md#prerequisites): existing supported APIM instance,
  reachable Toolbox, attached managed identity with Foundry invocation access, deployment rights,
  streaming-safe policies, and a valid consumer subscription. Products are optional but must exist
  if selected. The registration script does not create APIM, attach identities, grant roles, or
  issue subscriptions.
- Treat agent-to-APIM, APIM-to-Foundry, and Foundry-to-source authorization as separate boundaries.
  A grant on one does not establish access on the next. Validate document permissions before
  sharing a connection backed by a service identity or broad key.

## Acceptance Checklist

- [ ] Each enabled tool has entity-owned data/services, working authentication, and reachable endpoints.
- [ ] Strict build resolves all enabled references without placeholders; secrets stay outside Git.
- [ ] MCP initialization and `tools/list` succeed without JSON-RPC errors or consent failures.
- [ ] `tool_search` discovers the intended tools; discovery results are relevance matches, not a
  guaranteed complete inventory.
- [ ] Invoke each enabled retrieval tool independently; check JSON-RPC `error` and `isError`, not
  only HTTP 200. Verify authorized evidence and citations, plus denied access where applicable.
- [ ] Confirm intended skills are published and actually consumed by the agent.
- [ ] Repeat through APIM with a valid consumer subscription; an invalid key must be rejected.
- [ ] Run an agent question, inspect tool execution, and verify its answer against retrieved evidence
  before promoting the version or declaring the deployment ready.