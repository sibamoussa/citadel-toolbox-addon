from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, Mock, patch

import httpx
import main as agent_main
from agent_framework import MCPStreamableHTTPTool
from mcp.server.fastmcp import FastMCP
from toolbox_connection import create_toolbox


class ToolboxConnectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.credential = Mock()
        self.environment = {
            "TOOLBOX_CONNECTION_MODE": "apim",
            "TOOLBOX_ENDPOINT": "https://gateway.example.test/citadel-toolbox/mcp",
            "APIM_SUBSCRIPTION_KEY": "test-key-not-a-real-credential",
        }

    @patch("toolbox_connection.MCPStreamableHTTPTool")
    @patch("toolbox_connection.FoundryToolbox")
    def test_apim_uses_header_without_foundry_credentials(self, foundry, mcp) -> None:
        self.assertIs(create_toolbox(self.credential, self.environment), mcp.return_value)
        mcp.assert_called_once_with(
            name="citadel-toolbox",
            url=self.environment["TOOLBOX_ENDPOINT"],
            static_headers={"Ocp-Apim-Subscription-Key": self.environment["APIM_SUBSCRIPTION_KEY"]},
            load_prompts=False,
        )
        foundry.assert_not_called()
        self.credential.get_token.assert_not_called()

    @patch("toolbox_connection.FoundryToolbox")
    def test_legacy_configuration_remains_direct_foundry(self, foundry) -> None:
        del self.environment["TOOLBOX_CONNECTION_MODE"]
        self.environment["TOOLBOX_ENDPOINT"] = (
            "https://account.services.ai.azure.com/api/projects/project/toolboxes/tools/mcp?api-version=v1"
        )
        create_toolbox(self.credential, self.environment)
        foundry.assert_called_once_with(
            self.credential, url=self.environment["TOOLBOX_ENDPOINT"]
        )

    def test_invalid_configuration_fails_before_client_creation(self) -> None:
        invalid_values = [
            ("TOOLBOX_CONNECTION_MODE", "unknown"),
            ("TOOLBOX_ENDPOINT", "http://gateway.example.test/mcp"),
            ("TOOLBOX_ENDPOINT", "https://user:secret@gateway.example.test/mcp"),
            ("TOOLBOX_ENDPOINT", "https://<apim-name>.azure-api.net/mcp"),
            ("TOOLBOX_ENDPOINT", "https://gateway.example.test/mcp?subscription-key=secret"),
            ("TOOLBOX_ENDPOINT", "https://gateway.example.test/mcp#fragment"),
            ("TOOLBOX_ENDPOINT", ""),
            ("APIM_SUBSCRIPTION_KEY", ""),
            ("APIM_SUBSCRIPTION_KEY", "<api-scoped-subscription-key>"),
            ("APIM_SUBSCRIPTION_KEY", "bad\r\nheader"),
        ]
        for field, value in invalid_values:
            with self.subTest(field=field, value=value):
                environment = {**self.environment, field: value}
                with patch("toolbox_connection.MCPStreamableHTTPTool") as mcp:
                    with self.assertRaises(ValueError):
                        create_toolbox(self.credential, environment)
                    mcp.assert_not_called()


class AgentLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_mcp_session_is_open_while_host_runs_and_closed_after_failure(self) -> None:
        credential = Mock()
        credential.__enter__ = Mock(return_value=credential)
        credential.__exit__ = Mock(return_value=False)
        toolbox = Mock()
        toolbox.__aenter__ = AsyncMock(return_value=toolbox)
        toolbox.__aexit__ = AsyncMock(return_value=False)

        async def run_server() -> None:
            toolbox.__aenter__.assert_awaited_once()
            toolbox.__aexit__.assert_not_awaited()
            raise RuntimeError("test host stopped")

        with (
            patch.object(agent_main, "load_dotenv"),
            patch.object(agent_main, "DefaultAzureCredential", return_value=credential),
            patch.object(agent_main, "create_toolbox", return_value=toolbox),
            patch.object(agent_main, "FoundryChatClient"),
            patch.object(agent_main, "Agent") as agent,
            patch.object(agent_main, "ResponsesHostServer") as host,
            patch.dict(agent_main.os.environ, {
                "FOUNDRY_PROJECT_ENDPOINT": "https://project.example.test",
                "AZURE_AI_MODEL_DEPLOYMENT_NAME": "test-model",
            }),
        ):
            host.return_value.run_async = AsyncMock(side_effect=run_server)
            with self.assertRaisesRegex(RuntimeError, "test host stopped"):
                await agent_main.main()
            self.assertIs(agent.call_args.kwargs["tools"], toolbox)
        toolbox.__aexit__.assert_awaited_once()
        credential.__exit__.assert_called_once()


class MCPTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_mcp_discovery_and_call_send_subscription_header(self) -> None:
        server = FastMCP("Test Toolbox", host="gateway.example.test", stateless_http=True)

        @server.tool()
        def get_application_status(application_id: str) -> str:
            return f"{application_id}: in review"

        app = server.streamable_http_app()
        received_keys = []

        async def gateway(scope, receive, send):
            if scope["type"] == "http":
                headers = dict(scope["headers"])
                received_keys.append(headers.get(b"ocp-apim-subscription-key"))
                self.assertNotIn(b"authorization", headers)
            await app(scope, receive, send)

        environment = {
            "TOOLBOX_CONNECTION_MODE": "apim",
            "TOOLBOX_ENDPOINT": "https://gateway.example.test/mcp",
            "APIM_SUBSCRIPTION_KEY": "test-key-not-a-real-credential",
        }
        async with (
            server.session_manager.run(),
            httpx.AsyncClient(transport=httpx.ASGITransport(app=gateway)) as http_client,
        ):
            def client_factory(**kwargs):
                return MCPStreamableHTTPTool(**kwargs, http_client=http_client)

            with patch("toolbox_connection.MCPStreamableHTTPTool", side_effect=client_factory):
                toolbox = create_toolbox(Mock(), environment)
            async with toolbox:
                self.assertIn("get_application_status", [tool.name for tool in toolbox.functions])
                result = await toolbox.call_tool("get_application_status", application_id="APP-42")
                text = result if isinstance(result, str) else " ".join(
                    content.text or "" for content in result
                )
                self.assertIn("APP-42: in review", text)
        self.assertGreaterEqual(len(received_keys), 3)
        self.assertEqual(set(received_keys), {b"test-key-not-a-real-credential"})


if __name__ == "__main__":
    unittest.main()