from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import urlsplit

from agent_framework import MCPStreamableHTTPTool
from agent_framework_foundry_hosting import FoundryToolbox
from azure.core.credentials import TokenCredential


def create_toolbox(
    credential: TokenCredential, environment: Mapping[str, str]
) -> MCPStreamableHTTPTool:
    mode = environment.get("TOOLBOX_CONNECTION_MODE", "foundry").strip().lower()
    if mode not in {"apim", "foundry"}:
        raise ValueError("TOOLBOX_CONNECTION_MODE must be apim or foundry")
    endpoint = environment.get("TOOLBOX_ENDPOINT", "").strip()
    parsed = urlsplit(endpoint)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or "<" in endpoint
        or any(character.isspace() for character in endpoint)
    ):
        raise ValueError(
            "TOOLBOX_ENDPOINT must be a full HTTPS URL without credentials or placeholders"
        )
    if mode == "foundry":
        return FoundryToolbox(credential, url=endpoint)
    if parsed.query:
        raise ValueError("The APIM TOOLBOX_ENDPOINT must not contain query parameters")
    subscription_key = environment.get("APIM_SUBSCRIPTION_KEY", "").strip()
    if (
        not subscription_key
        or "<" in subscription_key
        or any(character.isspace() for character in subscription_key)
    ):
        raise ValueError("Set APIM_SUBSCRIPTION_KEY to a valid API-scoped subscription key")
    return MCPStreamableHTTPTool(
        name="citadel-toolbox",
        url=endpoint,
        static_headers={"Ocp-Apim-Subscription-Key": subscription_key},
        load_prompts=False,
    )