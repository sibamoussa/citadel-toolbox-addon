# Entity Onboarding

Use the [README deployment workflow](../README.md#deploy-in-10-steps) for commands. This checklist
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

## Configure

```powershell
$entity = 'contoso'
python -m citadel_toolbox.cli init-entity $entity --display-name 'Contoso'
Copy-Item "entities/$entity/.env.example" "entities/$entity/.env"
```

Fill every value in `.env`, then review `overlay.yaml`. Start with Work IQ and workflow actions
disabled. Keep customer values in the overlay; modify the core catalog only for a capability that
should change for every entity.

## Validate and Publish

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
