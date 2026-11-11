from __future__ import annotations

from pathlib import Path

import pytest

from citadel_toolbox.compiler import (
    ConfigurationError,
    compile_bundle,
    load_yaml,
    merge_bundle,
    render_toolbox,
    substitute_variables,
    validate_bundle,
)


def core_bundle() -> dict:
    return {
        "apiVersion": "citadel.microsoft.com/v1alpha1",
        "kind": "ToolboxBundle",
        "metadata": {"description": "Core"},
        "tools": [
            {
                "id": "knowledge",
                "enabled": True,
                "risk": "read",
                "provider": {
                    "type": "azure_ai_search",
                    "project_connection_id": "/projects/demo/connections/search",
                    "index_name": "${SEARCH_INDEX}",
                },
            },
            {
                "id": "create_request",
                "enabled": False,
                "risk": "write",
                "require_approval": "always",
                "provider": {"type": "mcp", "url": "${MCP_URL}"},
            },
        ],
        "skills": [{"id": "policy-answer", "enabled": True}],
    }


def test_overlay_merges_named_items_and_disables_core_tool() -> None:
    merged = merge_bundle(
        core_bundle(),
        {
            "metadata": {"description": "Entity A"},
            "tools": [
                {"id": "knowledge", "enabled": False},
                {"id": "discovery", "risk": "read", "provider": {"type": "toolbox_search"}},
            ],
        },
    )

    assert merged["metadata"]["description"] == "Entity A"
    assert [tool["id"] for tool in merged["tools"]] == [
        "knowledge",
        "create_request",
        "discovery",
    ]
    assert merged["tools"][0]["enabled"] is False


def test_variables_are_substituted_recursively() -> None:
    result = substitute_variables(
        core_bundle(), {"SEARCH_INDEX": "policies-v1", "MCP_URL": "https://mcp.example"}
    )

    assert result["tools"][0]["provider"]["index_name"] == "policies-v1"
    assert result["tools"][1]["provider"]["url"] == "https://mcp.example"


def test_missing_variable_is_rejected() -> None:
    with pytest.raises(ConfigurationError, match="MCP_URL, SEARCH_INDEX"):
        substitute_variables(core_bundle(), {})


def test_empty_variable_is_rejected() -> None:
    with pytest.raises(ConfigurationError, match="SEARCH_INDEX"):
        substitute_variables(
            core_bundle(), {"SEARCH_INDEX": "", "MCP_URL": "https://mcp.example"}
        )


def test_template_value_is_rejected_in_strict_mode() -> None:
    with pytest.raises(ConfigurationError, match="<index-name>"):
        substitute_variables(
            core_bundle(),
            {"SEARCH_INDEX": "<index-name>", "MCP_URL": "https://mcp.example"},
        )


def test_write_tool_without_approval_is_rejected() -> None:
    bundle = core_bundle()
    bundle["tools"][1]["enabled"] = True
    bundle["tools"][1].pop("require_approval")

    with pytest.raises(ConfigurationError, match="require_approval: always"):
        validate_bundle(bundle)


def test_connection_tool_requires_provider_fields() -> None:
    bundle = core_bundle()
    bundle["tools"][0]["provider"].pop("project_connection_id")

    with pytest.raises(ConfigurationError, match="project_connection_id"):
        validate_bundle(bundle)


def test_renderer_excludes_disabled_tools() -> None:
    rendered = render_toolbox(core_bundle())

    assert rendered == {
        "description": "Core",
        "connections": [{"name": "search", "index": "${SEARCH_INDEX}"}],
        "tools": [],
        "skills": [{"name": "policy-answer"}],
    }


def test_renderer_maps_connection_backed_tools() -> None:
    bundle = core_bundle()
    bundle["tools"] = [
        {
            "id": "knowledge",
            "provider": {
                "type": "azure_ai_search",
                "project_connection_id": "/projects/demo/connections/search-connection",
                "index_name": "policy-index",
            },
        },
        {
            "id": "knowledge-mcp",
            "provider": {
                "type": "mcp",
                "project_connection_id": "/projects/demo/connections/read-mcp",
                "server_url": "https://example.invalid/mcp",
            },
        },
    ]

    rendered = render_toolbox(bundle)

    assert rendered["connections"] == [
        {"name": "search-connection", "index": "policy-index"},
        {"name": "read-mcp"},
    ]
    assert rendered["tools"] == []


def test_renderer_keeps_toolbox_search_nameless() -> None:
    bundle = core_bundle()
    bundle["tools"].append(
        {"id": "tool-discovery", "risk": "read", "provider": {"type": "toolbox_search"}}
    )

    rendered = render_toolbox(bundle)

    assert rendered["tools"][-1] == {"type": "toolbox_search"}


def test_renderer_can_pin_skill_version() -> None:
    bundle = core_bundle()
    bundle["skills"][0]["version"] = "2"

    rendered = render_toolbox(bundle)

    assert rendered["skills"] == [{"name": "policy-answer", "version": "2"}]


def test_compile_does_not_require_disabled_tool_variables(tmp_path) -> None:
    import yaml

    core = core_bundle()
    core_path = tmp_path / "core.yaml"
    overlay_path = tmp_path / "overlay.yaml"
    core_path.write_text(yaml.safe_dump(core), encoding="utf-8")
    overlay_path.write_text("tools:\n  - id: knowledge\n    enabled: false\n", encoding="utf-8")

    bundle, rendered = compile_bundle(core_path, overlay_path, variables={})

    assert bundle["tools"] == []
    assert rendered["tools"] == []


def test_microsoft_overlay_has_exact_remaining_sources_and_skills() -> None:
    root = Path(__file__).resolve().parents[1]
    bundle, rendered = compile_bundle(
        root / "catalog/core.yaml",
        root / "entities/microsoft/overlay.yaml",
        variables={
            "MICROSOFT_SEARCH_CONNECTION_ID": "/projects/demo/connections/search",
            "MICROSOFT_SEARCH_INDEX_NAME": "policy-index",
            "MICROSOFT_FOUNDRY_IQ_MCP_URL": (
                "https://demo.search.windows.net/knowledgebases/policies/mcp"
                "?api-version=2026-08-01-preview"
            ),
            "MICROSOFT_FOUNDRY_IQ_CONNECTION_ID": "/projects/demo/connections/foundry-iq",
            "WORK_IQ_PROJECT_CONNECTION_ID": "/projects/demo/connections/work-iq",
        },
    )

    tools = {tool["id"]: tool for tool in bundle["tools"]}
    assert set(tools) == {
        "enterprise-knowledge", "employee-context", "foundry-iq", "tool-discovery",
    }
    assert [skill["id"] for skill in bundle["skills"]] == [
        "enterprise-grounding", "workplace-context",
    ]
    assert rendered["skills"] == [
        {"name": "enterprise-grounding"}, {"name": "workplace-context"},
    ]
    assert tools["employee-context"]["constraints"]["identity"] == "delegated-user"
    assert rendered["tools"] == [{"type": "toolbox_search"}]
    assert rendered["connections"] == [
        {"name": "search", "index": "policy-index"},
        {"name": "work-iq"},
        {"name": "foundry-iq"},
    ]


def test_catalog_and_overlays_define_only_remaining_sources_and_skills() -> None:
    root = Path(__file__).resolve().parents[1]
    core = load_yaml(root / "catalog/core.yaml")
    assert {tool["id"] for tool in core["tools"]} == {
        "enterprise-knowledge", "employee-context", "tool-discovery",
    }
    assert [skill["id"] for skill in core["skills"]] == ["enterprise-grounding"]
    assert {path.parent.name for path in (root / "skills").glob("*/SKILL.md")} == {
        "enterprise-grounding", "workplace-context",
    }
    for entity, expected in (
        ("example", {"enterprise-knowledge", "employee-context"}),
        ("microsoft", {"enterprise-knowledge", "employee-context", "foundry-iq", "tool-discovery"}),
    ):
        overlay = load_yaml(root / f"entities/{entity}/overlay.yaml")
        assert {tool["id"] for tool in overlay["tools"]} == expected


@pytest.mark.parametrize("missing_variable", [
    "MICROSOFT_FOUNDRY_IQ_MCP_URL",
    "MICROSOFT_FOUNDRY_IQ_CONNECTION_ID",
    "WORK_IQ_PROJECT_CONNECTION_ID",
])
def test_microsoft_overlay_requires_iq_configuration(missing_variable: str) -> None:
    root = Path(__file__).resolve().parents[1]
    variables = {
        "MICROSOFT_SEARCH_CONNECTION_ID": "/projects/demo/connections/search",
        "MICROSOFT_SEARCH_INDEX_NAME": "policy-index",
        "MICROSOFT_FOUNDRY_IQ_MCP_URL": "https://demo.search.windows.net/knowledgebases/policies/mcp?api-version=2026-08-01-preview",
        "MICROSOFT_FOUNDRY_IQ_CONNECTION_ID": "/projects/demo/connections/foundry-iq",
        "WORK_IQ_PROJECT_CONNECTION_ID": "/projects/demo/connections/work-iq",
    }
    variables.pop(missing_variable)
    with pytest.raises(ConfigurationError, match=missing_variable):
        compile_bundle(
            root / "catalog/core.yaml",
            root / "entities/microsoft/overlay.yaml",
            variables=variables,
        )