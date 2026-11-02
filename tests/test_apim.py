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
    assert template["outputs"]["mcpPath"]["value"] == "/citadel-toolbox/mcp"
    xml = ElementTree.fromstring(policy["properties"]["value"])
    assert xml.find("backend/forward-request").attrib["buffer-response"] == "false"
    assert xml.find("inbound/set-header").attrib["exists-action"] == "delete"
    assert xml.find("inbound/authentication-managed-identity") is None
    assert xml.find("inbound/set-header[@name='Foundry-Features']") is None
    assert xml.find("inbound/set-query-parameter[@name='api-version']") is None


def test_actions_have_separate_registration_and_managed_identity() -> None:
    template = build_apim_template(
        apim_name="example-gateway",
        backend_url="https://actions.example.test/mcp",
        api_id="citadel-actions",
        path="government/actions",
        backend_audience="api://government-actions",
    )
    _, api, policy = template["resources"]
    assert api["name"] == "example-gateway/citadel-actions"
    assert api["properties"]["path"] == "government/actions"
    xml = ElementTree.fromstring(policy["properties"]["value"])
    assert xml.find("inbound/authentication-managed-identity").attrib == {
        "resource": "api://government-actions"
    }
    assert "'example-gateway', 'citadel-actions'" in policy["dependsOn"][0]


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
    assert template["resources"][0]["properties"]["url"] == endpoint
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