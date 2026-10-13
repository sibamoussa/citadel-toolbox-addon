from __future__ import annotations

import pytest

from citadel_toolbox.compiler import (
    ConfigurationError,
    compile_bundle,
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
                {"id": "web", "risk": "read", "provider": {"type": "web_search"}},
            ],
        },
    )

    assert merged["metadata"]["description"] == "Entity A"
    assert [tool["id"] for tool in merged["tools"]] == [
        "knowledge",
        "create_request",
        "web",
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


def test_write_tool_without_approval_is_rejected() -> None:
    bundle = core_bundle()
    bundle["tools"][1]["enabled"] = True
    bundle["tools"][1].pop("require_approval")

    with pytest.raises(ConfigurationError, match="require_approval: always"):
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
            "id": "systems",
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