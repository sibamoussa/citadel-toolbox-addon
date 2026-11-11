from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from citadel_toolbox.cli import main
from citadel_toolbox.compiler import compile_bundle


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


@pytest.fixture
def entity(tmp_path):
    entity = tmp_path / "entities" / "contoso"
    entity.mkdir(parents=True)
    (entity / "overlay.yaml").write_text(
        "tools:\n"
        "  - id: enterprise-knowledge\n"
        "    provider:\n"
        "      project_connection_id: ${CONTOSO_SEARCH_CONNECTION_ID}\n"
        "      index_name: ${CONTOSO_SEARCH_INDEX_NAME}\n",
        encoding="utf-8",
    )
    return entity


def configure_arguments(entity: Path) -> list[str]:
    return [
        "configure-entity", entity.name,
        "--entities-dir", str(entity.parent),
        "--search-connection-id", "/projects/test/connections/search",
        "--search-index-name", "policies",
    ]


def test_configure_entity_writes_only_search_and_preserves_overlay(entity) -> None:
    original_overlay = (entity / "overlay.yaml").read_bytes()

    result = main(configure_arguments(entity))

    assert result == 0
    assert (entity / ".env").read_text(encoding="utf-8") == (
        "CONTOSO_SEARCH_CONNECTION_ID=/projects/test/connections/search\n"
        "CONTOSO_SEARCH_INDEX_NAME=policies\n"
    )
    assert (entity / "overlay.yaml").read_bytes() == original_overlay


def test_configure_entity_preserves_iq_configuration_on_reconfigure(entity) -> None:
    (entity / ".env").write_text(
        "# Existing IQ configuration\n"
        "WORK_IQ_PROJECT_CONNECTION_ID=/projects/test/connections/work-iq\n"
        "CONTOSO_FOUNDRY_IQ_CONNECTION_ID=/projects/test/connections/foundry-iq\n"
        "CONTOSO_SEARCH_INDEX_NAME=old-index\n",
        encoding="utf-8",
    )

    assert main(configure_arguments(entity)) == 0
    assert main(configure_arguments(entity)) == 0

    env = (entity / ".env").read_text(encoding="utf-8")
    assert env.startswith("# Existing IQ configuration\n")
    assert "WORK_IQ_PROJECT_CONNECTION_ID=/projects/test/connections/work-iq\n" in env
    assert "CONTOSO_FOUNDRY_IQ_CONNECTION_ID=/projects/test/connections/foundry-iq\n" in env
    assert "old-index" not in env
    assert env.count("CONTOSO_SEARCH_INDEX_NAME=") == 1


@pytest.mark.parametrize("option", ["--search-connection-id", "--search-index-name"])
@pytest.mark.parametrize("value", [" ", "value\ninjected=bad", "value\rinjected=bad"])
def test_configure_entity_rejects_invalid_values_before_writing(entity, option, value) -> None:
    arguments = configure_arguments(entity)
    arguments[arguments.index(option) + 1] = value

    with pytest.raises(SystemExit):
        main(arguments)

    assert not (entity / ".env").exists()


def test_configure_entity_uses_actual_example_without_additional_sources(tmp_path) -> None:
    root = Path(__file__).resolve().parents[1]
    entities = tmp_path / "entities"
    shutil.copytree(root / "entities/example", entities / "example")
    assert main([
        "init-entity", "contoso", "--display-name", "Contoso",
        "--entities-dir", str(entities),
    ]) == 0
    entity = entities / "contoso"
    assert main(configure_arguments(entity)) == 0
    variables = dict(
        line.split("=", 1) for line in (entity / ".env").read_text().splitlines()
    )

    bundle, rendered = compile_bundle(
        root / "catalog/core.yaml", entity / "overlay.yaml", variables=variables,
    )

    assert {tool["id"] for tool in bundle["tools"]} == {
        "enterprise-knowledge", "tool-discovery",
    }
    assert rendered["connections"] == [{"name": "search", "index": "policies"}]
    assert rendered["skills"] == [{"name": "enterprise-grounding"}]