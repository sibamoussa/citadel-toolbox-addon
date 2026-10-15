# Python Agent Consumer

This example runs a Microsoft Agent Framework hosted agent that discovers and invokes the tools and
skills exposed by an existing Citadel Toolbox. `FoundryToolbox` authenticates each request and reads
the MCP consumer endpoint from `TOOLBOX_ENDPOINT`.

## Configure

From the repository root, run:

```powershell
./examples/python-agent/Setup.ps1
```

Edit `examples/python-agent/.env` and replace all three placeholders:

- `FOUNDRY_PROJECT_ENDPOINT`: the Foundry project endpoint.
- `AZURE_AI_MODEL_DEPLOYMENT_NAME`: a model deployment in that project.
- `TOOLBOX_ENDPOINT`: the stable consumer endpoint printed by `Setup-Toolbox.ps1` or
  `Publish-Toolbox.ps1`.

The local identity selected by `DefaultAzureCredential` needs **Foundry User** access to the project.
In Foundry hosting, the agent identity needs the same access. Project connections continue to hold
credentials for the services behind the Toolbox.

This example targets the default read-only Toolbox. Do not enable state-changing tools until the
agent runtime has a real approval handler; instructions and `require_approval` metadata alone do not
block tool execution.

## Run

In VS Code, press **F5** and select **Debug Citadel Toolbox Agent Example**. Foundry Toolkit opens
Agent Inspector after the Responses server starts. Try:

```text
What tools and skills can you use? Then find the relevant policy for my request and cite its source.
```

You can also start the server directly:

```powershell
./examples/python-agent/.venv/Scripts/python.exe ./examples/python-agent/main.py
```

## Browser Demo

After the agent server is listening on port 8088, start the standalone demo UI from the repository
root in a second terminal:

```powershell
./examples/python-agent/.venv/Scripts/python.exe ./examples/python-agent/demo-ui/server.py
```

Open `http://127.0.0.1:8090`. The local UI server serves the static chat interface and proxies only
readiness and Responses API requests to the agent, so Foundry credentials and Toolbox endpoints are
never sent to the browser. Conversation context remains in the browser and agent requests use
`store: false`.

The code does not contain service credentials. `DefaultAzureCredential` uses the signed-in developer
identity locally and the assigned workload identity when hosted.