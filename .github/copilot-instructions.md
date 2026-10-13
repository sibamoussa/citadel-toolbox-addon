# Citadel Toolbox Add-on

- Keep the core toolbox catalog reusable across entities.
- Put entity-specific values in `entities/<entity>/overlay.yaml`; do not fork core definitions.
- Never commit credentials, tokens, tenant IDs, or service endpoints containing secrets.
- Treat generated toolbox definitions as disposable build artifacts.
- Require explicit approval metadata for tools that create, update, submit, or delete data.
- Keep MCP and OpenAPI contracts stable while allowing entity-specific backend implementations.
- Use Python 3.11 or newer and keep the package type checked and covered by focused tests.
- If you are in VS Code, read the vscode-microsoft-foundry skill first.