from __future__ import annotations

import pytest
import yaml

from citadel_toolbox.cli import main


def test_init_entity_replaces_example_identifiers(tmp_path) -> None:
    example = tmp_path / "entities" / "example"
    example.mkdir(parents=True)
    (example / "overlay.yaml").write_text(
        "metadata:\n  name: example-entity-toolbox\n"
        "  description: Example Entity\n"
        "tools:\n  - id: knowledge\n"
        "    provider:\n      value: ${EXAMPLE_SEARCH_CONNECTION_ID}\n",
        encoding="utf-8",
    )
    (example / ".env.example").write_text(
        "EXAMPLE_SEARCH_CONNECTION_ID=<value>\n", encoding="utf-8"
    )

    result = main(
        [
            "init-entity",
            "health-authority",
            "--display-name",
            "Health Authority",
            "--entities-dir",
            str(tmp_path / "entities"),
        ]
    )

    overlay = (tmp_path / "entities" / "health-authority" / "overlay.yaml").read_text()
    env_template = (tmp_path / "entities" / "health-authority" / ".env.example").read_text()
    assert result == 0
    assert "Health Authority" in overlay
    assert "health-authority-entity-toolbox" in overlay
    assert "HEALTH_AUTHORITY_SEARCH_CONNECTION_ID" in overlay
    assert "HEALTH_AUTHORITY_SEARCH_CONNECTION_ID" in env_template


def test_init_entity_supports_separate_template_and_destination(tmp_path) -> None:
    template = tmp_path / "template"
    destination = tmp_path / "customer-entities"
    template.mkdir()
    (template / "overlay.yaml").write_text(
        "metadata:\n  name: example-toolbox\n  description: Example Entity\n",
        encoding="utf-8",
    )
    (template / ".env.example").write_text("EXAMPLE_VALUE=<value>\n", encoding="utf-8")

    result = main(
        [
            "init-entity",
            "acme",
            "--display-name",
            "Acme",
            "--entities-dir",
            str(destination),
            "--template-dir",
            str(template),
        ]
    )

    assert result == 0
    assert (destination / "acme" / "overlay.yaml").is_file()


def test_configure_entity_writes_env_and_domains(tmp_path) -> None:
    entity = tmp_path / "entities" / "contoso"
    entity.mkdir(parents=True)
    (entity / "overlay.yaml").write_text(
        "tools:\n"
        "  - id: enterprise-knowledge\n"
        "    provider:\n"
        "      project_connection_id: ${CONTOSO_SEARCH_CONNECTION_ID}\n"
        "      index_name: ${CONTOSO_SEARCH_INDEX_NAME}\n"
        "  - id: government-systems\n"
        "    provider:\n"
        "      server_url: ${CONTOSO_SYSTEMS_URL}\n"
        "      project_connection_id: ${CONTOSO_SYSTEMS_CONNECTION_ID}\n"
        "  - id: approved-web-search\n"
        "    provider:\n"
        "      filters:\n"
        "        allowed_domains: [old.example]\n",
        encoding="utf-8",
    )

    result = main(
        [
            "configure-entity",
            "contoso",
            "--entities-dir",
            str(tmp_path / "entities"),
            "--search-connection-id",
            "/projects/test/connections/search",
            "--search-index-name",
            "policies",
            "--mcp-url",
            "https://mcp.contoso.example/mcp",
            "--mcp-connection-id",
            "/projects/test/connections/read-mcp",
            "--allowed-domain",
            "Contoso.com",
            "--allowed-domain",
            "learn.contoso.com",
        ]
    )

    env = (entity / ".env").read_text(encoding="utf-8")
    overlay = yaml.safe_load((entity / "overlay.yaml").read_text(encoding="utf-8"))
    assert result == 0
    assert "CONTOSO_SEARCH_INDEX_NAME=policies" in env
    assert "CONTOSO_SYSTEMS_URL=https://mcp.contoso.example/mcp" in env
    assert overlay["tools"][2]["provider"]["filters"]["allowed_domains"] == [
        "contoso.com",
        "learn.contoso.com",
    ]


def test_configure_entity_rejects_domain_before_writing_env(tmp_path) -> None:
    entity = tmp_path / "entities" / "contoso"
    entity.mkdir(parents=True)
    (entity / "overlay.yaml").write_text(
        "tools:\n"
        "  - id: enterprise-knowledge\n"
        "    provider:\n"
        "      project_connection_id: ${CONTOSO_SEARCH_CONNECTION_ID}\n"
        "      index_name: ${CONTOSO_SEARCH_INDEX_NAME}\n"
        "  - id: government-systems\n"
        "    provider:\n"
        "      server_url: ${CONTOSO_MCP_URL}\n"
        "      project_connection_id: ${CONTOSO_MCP_CONNECTION_ID}\n"
        "  - id: approved-web-search\n"
        "    provider: {}\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit):
        main(
            [
                "configure-entity",
                "contoso",
                "--entities-dir",
                str(tmp_path / "entities"),
                "--search-connection-id",
                "/connections/search",
                "--search-index-name",
                "policies",
                "--mcp-url",
                "https://mcp.example/mcp",
                "--mcp-connection-id",
                "/connections/mcp",
                "--allowed-domain",
                "https://invalid.example/path",
            ]
        )

    assert not (entity / ".env").exists()


def test_configure_entity_rejects_insecure_mcp_url(tmp_path) -> None:
    entity = tmp_path / "entities" / "contoso"
    entity.mkdir(parents=True)
    (entity / "overlay.yaml").write_text(
        "tools:\n"
        "  - id: enterprise-knowledge\n"
        "    provider:\n"
        "      project_connection_id: ${CONTOSO_SEARCH_CONNECTION_ID}\n"
        "      index_name: ${CONTOSO_SEARCH_INDEX_NAME}\n"
        "  - id: government-systems\n"
        "    provider:\n"
        "      server_url: ${CONTOSO_MCP_URL}\n"
        "      project_connection_id: ${CONTOSO_MCP_CONNECTION_ID}\n"
        "  - id: approved-web-search\n"
        "    provider: {}\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit):
        main(
            [
                "configure-entity",
                "contoso",
                "--entities-dir",
                str(tmp_path / "entities"),
                "--search-connection-id",
                "/connections/search",
                "--search-index-name",
                "policies",
                "--mcp-url",
                "http://mcp.example/mcp",
                "--mcp-connection-id",
                "/connections/mcp",
                "--allowed-domain",
                "example.com",
            ]
        )

    assert not (entity / ".env").exists()