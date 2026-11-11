import asyncio
import os
from pathlib import Path

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
from toolbox_connection import create_toolbox


async def main() -> None:
    load_dotenv(Path(__file__).with_name(".env"))
    with DefaultAzureCredential() as credential:
        toolbox = create_toolbox(credential, os.environ)
        client = FoundryChatClient(
            project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
            model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
            credential=credential,
        )

        async with toolbox:
            agent = Agent(
                client=client,
                instructions=(
                    "You are a Citadel assistant. Use the Toolbox for grounded answers, "
                    "include source citations when available, and use enterprise sources."
                ),
                tools=toolbox,
                default_options={"store": False},
            )

            server = ResponsesHostServer(agent)
            await server.run_async()


if __name__ == "__main__":
    asyncio.run(main())