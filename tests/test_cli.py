from __future__ import annotations

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