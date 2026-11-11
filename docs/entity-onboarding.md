# Entity Onboarding

Use the [README setup workflow](../README.md#part-1-create-and-publish-the-toolbox) for the primary workflow. This checklist
captures the decisions an entity owner must approve before deployment.

## Inputs

Collect these non-secret values:

- Foundry project endpoint and owning tenant ID
- Azure AI Search project connection resource ID
- Existing Search index name and entity-scoping filter
- Microsoft Foundry IQ knowledge-base endpoint and project connection reference, when enabled
- Work IQ project connection reference and delegated-user requirements, when enabled
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
`-Reconfigure` when those values should be replaced. Work IQ is optional and disabled by default in
the shared catalog; the Microsoft overlay enables it and requires its connection reference.

## Advanced Usage

After initializing an entity, configure its Search inputs with the local CLI:

```powershell
citadel-toolbox configure-entity example `
    --search-connection-id '<search-project-connection-resource-id>' `
    --search-index-name '<existing-index-name>'
```

The positional name selects the entity; `--entities-dir` optionally selects a different entity
directory. These are the only required connection inputs for `configure-entity`. It writes the
entity's `.env` with Search values only, replacing existing contents. After running it, add any
Microsoft Foundry IQ or Work IQ references required by the overlay, following the entity's
`.env.example`, before strict validation. Reconfiguration requires restoring those additional
references.

Build or publish an already configured entity directly when scripting the workflow:

```powershell
./scripts/Build-Toolbox.ps1 -Entity $entity
./scripts/Publish-Toolbox.ps1 `
    -Entity $entity `
    -ProjectEndpoint $projectEndpoint `
    -ToolboxName "$entity-toolbox"
```

The publish script provisions missing core skills and creates the first Toolbox version. It does not
provision the Foundry project, Search index, knowledge base, or project connections.

Before connecting agents, verify:

- The version-specific MCP endpoint initializes successfully.
- Search returns authorized records with citations.
- Microsoft Foundry IQ retrieval enforces the intended identity and document-level access, when enabled.
- Toolbox Search discovers the expected tools independently of document retrieval.
- `resources/list` returns the expected skills.
- The shared definition references enterprise-grounding; the Microsoft overlay also references
    workplace-context for Work IQ. Existing published versions
    retain their attached skills until explicitly updated and promoted.

## Work IQ Readiness

Enable Work IQ only after confirming delegated-user consent, tenant policy, and network
compatibility. It is a preview capability and is unsuitable for network-isolated projects.

For the Microsoft overlay, these are prerequisites rather than an enablement step. The standard
APIM subscription-key plus managed-identity route does not propagate end-user identity and alone
does not provide delegated Work IQ access. Resolve user consent and validate the delegated flow
before claiming successful operation.

## Handoff Record

Record the entity owner, Foundry project, Toolbox name, default version, validation evidence,
connection owners, and rollback version in the customer's approved operational system. Do not add
customer resource identifiers to this public repository.
