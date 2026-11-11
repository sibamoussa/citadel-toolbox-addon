from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlsplit
from uuid import UUID
from xml.etree import ElementTree


def build_apim_template(
    *,
    apim_name: str,
    backend_url: str,
    api_id: str = "citadel-toolbox",
    path: str = "citadel-toolbox",
    backend_audience: str | None = None,
    backend_client_id: str | None = None,
    product_id: str | None = None,
) -> dict:
    for label, value in (("APIM name", apim_name), ("API ID", api_id)):
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9-]{0,49}", value):
            raise ValueError(f"{label} must contain 1-50 letters, numbers, or hyphens")
    if not re.fullmatch(r"[a-zA-Z0-9_-]+(?:/[a-zA-Z0-9_-]+)*", path) or len(path) > 400:
        raise ValueError("API path must contain URL-safe segments without leading/trailing slashes")
    backend = urlsplit(backend_url)
    query = parse_qsl(backend.query, keep_blank_values=True, strict_parsing=True)
    valid_query = not query or (
        len(query) == 1
        and query[0][0] == "api-version"
        and re.fullmatch(r"[a-zA-Z0-9._-]+", query[0][1]) is not None
    )
    if (
        backend.scheme != "https"
        or not backend.hostname
        or backend.username is not None
        or backend.password is not None
        or not valid_query
        or backend.fragment
        or any(character.isspace() for character in backend_url)
        or len(backend_url) > 2000
    ):
        raise ValueError(
            "Backend URL must be HTTPS without credentials or fragment; "
            "only an api-version query parameter is allowed"
        )
    if backend_audience is not None and (
        not backend_audience.strip() or any(character.isspace() for character in backend_audience)
    ):
        raise ValueError("Backend audience must be a non-empty resource identifier")
    if backend_client_id is not None:
        try:
            if str(UUID(backend_client_id)) != backend_client_id.lower():
                raise ValueError
        except ValueError:
            raise ValueError("Backend client ID must be a hyphenated UUID") from None
        if not backend_audience:
            raise ValueError("Backend client ID requires a backend audience")
    if product_id is not None and not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,255}", product_id):
        raise ValueError("Product ID must be a URL-safe resource segment of 1-256 characters")

    policies = ElementTree.Element("policies")
    inbound = ElementTree.SubElement(policies, "inbound")
    ElementTree.SubElement(inbound, "base")
    ElementTree.SubElement(
        inbound, "set-header", {"name": "Ocp-Apim-Subscription-Key", "exists-action": "delete"}
    )
    ElementTree.SubElement(
        inbound, "set-query-parameter", {"name": "subscription-key", "exists-action": "delete"}
    )
    if backend_audience:
        identity_attributes = {"resource": backend_audience}
        if backend_client_id is not None:
            identity_attributes["client-id"] = backend_client_id
        ElementTree.SubElement(
            inbound, "authentication-managed-identity", identity_attributes
        )
    if backend_audience == "https://ai.azure.com":
        feature_header = ElementTree.SubElement(
            inbound, "set-header", {"name": "Foundry-Features", "exists-action": "override"}
        )
        ElementTree.SubElement(feature_header, "value").text = "Toolboxes=V1Preview"
    if query:
        version_parameter = ElementTree.SubElement(
            inbound, "set-query-parameter", {"name": "api-version", "exists-action": "override"}
        )
        ElementTree.SubElement(version_parameter, "value").text = query[0][1]
    backend_policy = ElementTree.SubElement(policies, "backend")
    ElementTree.SubElement(backend_policy, "forward-request", {"buffer-response": "false"})
    ElementTree.SubElement(ElementTree.SubElement(policies, "outbound"), "base")
    ElementTree.SubElement(ElementTree.SubElement(policies, "on-error"), "base")

    template = {
        "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
        "contentVersion": "1.0.0.0",
        "resources": [
            {
                "type": "Microsoft.ApiManagement/service/backends",
                "apiVersion": "2024-05-01",
                "name": f"{apim_name}/{api_id}-backend",
                "properties": {
                    "protocol": "http",
                    "url": backend._replace(query="").geturl(),
                    "tls": {"validateCertificateChain": True, "validateCertificateName": True},
                },
            },
            {
                "type": "Microsoft.ApiManagement/service/apis",
                "apiVersion": "2025-09-01-preview",
                "name": f"{apim_name}/{api_id}",
                "dependsOn": [
                    "[resourceId('Microsoft.ApiManagement/service/backends', "
                    f"'{apim_name}', '{api_id}-backend')]"
                ],
                "properties": {
                    "displayName": api_id,
                    "description": "Citadel Toolbox external MCP server (Streamable HTTP).",
                    "type": "mcp",
                    "path": path,
                    "protocols": ["https"],
                    "backendId": f"{api_id}-backend",
                    "subscriptionRequired": True,
                    "mcpProperties": {"transportType": "streamable"},
                },
            },
            {
                "type": "Microsoft.ApiManagement/service/apis/policies",
                "apiVersion": "2024-05-01",
                "name": f"{apim_name}/{api_id}/policy",
                "dependsOn": [
                    "[resourceId('Microsoft.ApiManagement/service/apis', "
                    f"'{apim_name}', '{api_id}')]"
                ],
                "properties": {
                    "format": "rawxml",
                    "value": ElementTree.tostring(policies, encoding="unicode"),
                },
            },
        ],
        "outputs": {"mcpPath": {"type": "string", "value": f"/{path}"}},
    }
    if product_id is not None:
        template["resources"].append({
            "type": "Microsoft.ApiManagement/service/products/apis",
            "apiVersion": "2024-05-01",
            "name": f"{apim_name}/{product_id}/{api_id}",
            "dependsOn": [
                "[resourceId('Microsoft.ApiManagement/service/apis', "
                f"'{apim_name}', '{api_id}')]"
            ],
            "properties": {},
        })
    return template