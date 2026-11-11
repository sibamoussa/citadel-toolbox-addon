from __future__ import annotations

import json
from xml.etree import ElementTree

import pytest

from citadel_toolbox.apim import build_apim_template
from citadel_toolbox.cli import main


def test_external_mcp_registration_preserves_full_endpoint() -> None:
    template = build_apim_template(
        apim_name="example-gateway", backend_url="https://tools.example.test/providers/read/mcp"
    )
    backend, api, policy = template["resources"]
    assert api["properties"]["type"] == "mcp"
    assert backend["properties"]["url"] == "https://tools.example.test/providers/read/mcp"
    assert api["properties"]["backendId"] == "citadel-toolbox-backend"
    assert backend["properties"]["protocol"] == "http"
    assert backend["properties"]["tls"] == {
        "validateCertificateChain": True, "validateCertificateName": True
    }
    assert api["properties"]["mcpProperties"] == {"transportType": "streamable"}
    assert api["properties"]["subscriptionRequired"] is True
    assert api["properties"]["protocols"] == ["https"]
    assert template["outputs"]["mcpPath"]["value"] == "/citadel-toolbox"
    xml = ElementTree.fromstring(policy["properties"]["value"])
    assert xml.find("backend/forward-request").attrib["buffer-response"] == "false"
    assert xml.find("inbound/set-header").attrib["exists-action"] == "delete"
    assert xml.find("inbound/authentication-managed-identity") is None
    assert xml.find("inbound/set-header[@name='Foundry-Features']") is None
    assert xml.find("inbound/set-query-parameter[@name='api-version']") is None


@pytest.mark.parametrize("path", ["enterprise/knowledge", "mcp/citadel-toolbox", "custom/mcp"])
def test_knowledge_mcp_has_custom_registration_and_managed_identity(path: str) -> None:
    template = build_apim_template(
        apim_name="example-gateway",
        backend_url="https://knowledge.example.test/mcp",
        api_id="citadel-knowledge",
        path=path,
        backend_audience="api://enterprise-knowledge",
    )
    _, api, policy = template["resources"]
    assert api["name"] == "example-gateway/citadel-knowledge"
    assert api["properties"]["path"] == path
    assert template["outputs"]["mcpPath"]["value"] == f"/{path}"
    xml = ElementTree.fromstring(policy["properties"]["value"])
    assert xml.find("inbound/authentication-managed-identity").attrib == {
        "resource": "api://enterprise-knowledge"
    }
    assert "'example-gateway', 'citadel-knowledge'" in policy["dependsOn"][0]


@pytest.mark.parametrize(
    "backend_url",
    [
        "http://tools.example.test/mcp",
        "https://user:secret@tools.example.test/mcp",
        "https://tools.example.test/mcp?key=secret",
        "https://tools.example.test/mcp?api-version=v1&key=secret",
        "https://tools.example.test/mcp?api-version=",
        "https://tools.example.test/mcp?api-version=v1&api-version=v2",
        "https://tools.example.test/mcp#fragment",
        "https:///mcp",
        "https://tools.example.test/ mc p",
    ],
)
def test_rejects_unsafe_backend_urls(backend_url: str) -> None:
    with pytest.raises(ValueError, match="Backend URL"):
        build_apim_template(apim_name="example-gateway", backend_url=backend_url)


@pytest.mark.parametrize("field", ["apim_name", "api_id", "path"])
def test_rejects_invalid_resource_names(field: str) -> None:
    values = {"apim_name": "gateway", "backend_url": "https://tools.example.test/mcp"}
    values[field] = "bad'value"
    with pytest.raises(ValueError):
        build_apim_template(**values)


def test_cli_exports_registration_without_azure_access(tmp_path) -> None:
    output = tmp_path / "generated" / "apim.json"
    assert main([
        "export-apim", "--apim-name", "example-gateway",
        "--backend-url", "https://tools.example.test/mcp", "--output", str(output),
    ]) == 0
    api = json.loads(output.read_text())["resources"][1]
    assert api["properties"]["type"] == "mcp"
    assert api["properties"]["path"] == "citadel-toolbox"
    assert api["name"] == "example-gateway/citadel-toolbox"


def test_foundry_toolbox_version_query_is_preserved() -> None:
    endpoint = (
        "https://example.services.ai.azure.com/api/projects/example"
        "/toolboxes/example-toolbox/mcp?api-version=v1"
    )
    template = build_apim_template(
        apim_name="gateway", backend_url=endpoint, backend_audience="https://ai.azure.com"
    )
    assert template["resources"][0]["properties"]["url"] == endpoint.split("?", 1)[0]
    xml = ElementTree.fromstring(template["resources"][2]["properties"]["value"])
    feature_header = xml.find("inbound/set-header[@name='Foundry-Features']")
    assert feature_header.attrib["exists-action"] == "override"
    assert feature_header.findtext("value") == "Toolboxes=V1Preview"
    version_parameter = xml.find("inbound/set-query-parameter[@name='api-version']")
    assert version_parameter.attrib["exists-action"] == "override"
    assert version_parameter.findtext("value") == "v1"


def test_registration_resource_dependencies_and_versions() -> None:
    template = build_apim_template(apim_name="gateway", backend_url="https://tools.example.test/mcp")
    backend, api, policy = template["resources"]
    assert backend["apiVersion"] == "2024-05-01"
    assert api["apiVersion"] == "2025-09-01-preview"
    assert policy["apiVersion"] == "2024-05-01"
    assert api["dependsOn"] == [
        "[resourceId('Microsoft.ApiManagement/service/backends', "
        "'gateway', 'citadel-toolbox-backend')]"
    ]
    assert policy["dependsOn"] == [
        "[resourceId('Microsoft.ApiManagement/service/apis', 'gateway', 'citadel-toolbox')]"
    ]


def test_cli_rejects_unsafe_urls_before_writing(tmp_path) -> None:
    output = tmp_path / "apim.json"
    with pytest.raises(SystemExit) as error:
        main([
            "export-apim", "--apim-name", "example-gateway",
            "--backend-url", "http://localhost/mcp", "--output", str(output),
        ])
    assert error.value.code == 2
    assert not output.exists()


def test_user_assigned_identity_and_existing_product() -> None:
    client_id = "8bc8b977-050d-42a1-a619-2ea5fbcafb1f"
    product_id = "TOOL-ToolboxDemo-Publisha7e840b1f8f2-DEV"
    template = build_apim_template(
        apim_name="gateway", backend_url="https://tools.example.test/mcp",
        api_id="custom-api", backend_audience="https://ai.azure.com",
        backend_client_id=client_id, product_id=product_id,
    )
    backend, api, policy, association = template["resources"]
    xml = ElementTree.fromstring(policy["properties"]["value"])
    assert xml.find("inbound/authentication-managed-identity").attrib == {
        "resource": "https://ai.azure.com", "client-id": client_id,
    }
    assert association == {
        "type": "Microsoft.ApiManagement/service/products/apis",
        "apiVersion": "2024-05-01",
        "name": f"gateway/{product_id}/custom-api",
        "dependsOn": [
            "[resourceId('Microsoft.ApiManagement/service/apis', 'gateway', 'custom-api')]"
        ],
        "properties": {},
    }
    assert api["properties"]["path"] == "citadel-toolbox"
    assert template["outputs"]["mcpPath"]["value"] == "/citadel-toolbox"


@pytest.mark.parametrize("client_id", ["", "not-a-uuid", "8bc8b977050d42a1a6192ea5fbcafb1f"])
def test_rejects_invalid_backend_client_id(client_id: str) -> None:
    with pytest.raises(ValueError, match="Backend client ID must be"):
        build_apim_template(
            apim_name="gateway", backend_url="https://tools.example.test/mcp",
            backend_audience="https://ai.azure.com", backend_client_id=client_id,
        )


def test_backend_client_id_requires_audience() -> None:
    with pytest.raises(ValueError, match="requires a backend audience"):
        build_apim_template(
            apim_name="gateway", backend_url="https://tools.example.test/mcp",
            backend_client_id="8bc8b977-050d-42a1-a619-2ea5fbcafb1f",
        )


@pytest.mark.parametrize("product_id", ["", "../product", "bad/product", "bad'product", "bad?x=1",
                                       "bad product", "[parameters('product')]", "a" * 257])
def test_rejects_invalid_product_id(product_id: str) -> None:
    with pytest.raises(ValueError, match="Product ID"):
        build_apim_template(
            apim_name="gateway", backend_url="https://tools.example.test/mcp",
            product_id=product_id,
        )


def test_cli_exports_user_identity_and_product(tmp_path) -> None:
    output = tmp_path / "apim.json"
    client_id = "8bc8b977-050d-42a1-a619-2ea5fbcafb1f"
    assert main([
        "export-apim", "--apim-name", "gateway", "--backend-url", "https://tools.example.test/mcp",
        "--backend-audience", "https://ai.azure.com", "--backend-client-id", client_id,
        "--product-id", "existing-product", "--output", str(output),
    ]) == 0
    resources = json.loads(output.read_text())["resources"]
    assert len(resources) == 4
    assert resources[3]["name"] == "gateway/existing-product/citadel-toolbox"
    xml = ElementTree.fromstring(resources[2]["properties"]["value"])
    assert xml.find("inbound/authentication-managed-identity").attrib["client-id"] == client_id


@pytest.mark.parametrize("options", [
    ["--backend-client-id", "8bc8b977-050d-42a1-a619-2ea5fbcafb1f"],
    ["--backend-audience", "https://ai.azure.com", "--backend-client-id", "invalid"],
    ["--product-id", "bad/product"],
])
def test_cli_rejects_invalid_identity_or_product_before_writing(tmp_path, options) -> None:
    output = tmp_path / "generated" / "apim.json"
    with pytest.raises(SystemExit) as error:
        main([
            "export-apim", "--apim-name", "gateway", "--backend-url", "https://tools.example.test/mcp",
            "--output", str(output), *options,
        ])
    assert error.value.code == 2
    assert not output.parent.exists()