# Entity Onboarding

Use the [README guided deployment](../README.md#guided-deployment) for the primary workflow. This checklist
captures the decisions an entity owner must approve before deployment.

## Inputs

Collect these non-secret values:

- Foundry project endpoint and owning tenant ID
- Azure AI Search project connection resource ID
- Existing Search index name and entity-scoping filter
- Read-only MCP project connection resource ID and HTTPS endpoint
- Approved public web domains
- Toolbox name and business owner

Credentials belong in Foundry project connections or an approved secret store, never in an overlay
or `.env` file.

## Configure and Publish

```powershell
./scripts/Setup-Toolbox.ps1
```

Alternatively, select **Citadel Toolbox: Guided setup and publish** from **Terminal > Run Task** in
VS Code. The workflow installs local dependencies, creates or reuses the entity, collects the inputs
above, strictly validates the generated definition, authenticates, creates missing skills, and
publishes version 1.

Use `-SkipPublish` to prepare and validate locally. Reruns preserve an existing `.env`; use
`-Reconfigure` when those values should be replaced. Keep Work IQ and workflow actions disabled for
the initial deployment.

## Advanced Usage

Build or publish an already configured entity directly when scripting the workflow:

```powershell
./scripts/Build-Toolbox.ps1 -Entity $entity
./scripts/Publish-Toolbox.ps1 `
    -Entity $entity `
    -ProjectEndpoint $projectEndpoint `
    -ToolboxName "$entity-toolbox"
```

The publish script provisions missing core skills and creates the first Toolbox version. It does not
provision the Foundry project, Search index, MCP server, or project connections.

Before connecting agents, verify:

- The version-specific MCP endpoint initializes successfully.
- Search returns authorized records with citations.
- Web search uses only approved domains.
- The read MCP enforces identity and record-level authorization.
- `resources/list` returns the expected skills.
- No state-changing tool is available.

## Optional Capabilities

Enable Work IQ only after confirming delegated-user consent, tenant policy, and network
compatibility. It is a preview capability and is unsuitable for network-isolated projects.

Enable workflow actions only after deploying a separate action MCP service and connection. Use a
separate identity, keep `require_approval: always`, and prove the consuming agent pauses the exact
pending call for explicit approval.

## Handoff Record

Record the entity owner, Foundry project, Toolbox name, default version, validation evidence,
connection owners, and rollback version in the customer's approved operational system. Do not add
customer resource identifiers to this public repository.
