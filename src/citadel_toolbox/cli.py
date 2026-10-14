from __future__ import annotations

import argparse
import shutil
from collections.abc import Sequence
from pathlib import Path
from urllib.parse import urlsplit

import yaml

from citadel_toolbox.compiler import ENV_PATTERN, ConfigurationError, compile_bundle, write_yaml


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="citadel-toolbox",
        description="Build and validate entity-specific Citadel Toolbox definitions.",
    )
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    subparsers = parser.add_subparsers(dest="command")

    compile_parser = subparsers.add_parser(
        "compile", help="Merge core and entity configuration into a Toolbox definition."
    )
    compile_parser.add_argument("--core", type=Path, default=Path("catalog/core.yaml"))
    compile_parser.add_argument("--overlay", type=Path, required=True)
    compile_parser.add_argument("--output", type=Path, required=True)
    compile_parser.add_argument(
        "--allow-unresolved",
        action="store_true",
        help="Keep unresolved ${VARIABLE} placeholders in generated output.",
    )

    validate_parser = subparsers.add_parser("validate", help="Validate a core and overlay pair.")
    validate_parser.add_argument("--core", type=Path, default=Path("catalog/core.yaml"))
    validate_parser.add_argument("--overlay", type=Path, required=True)
    validate_parser.add_argument("--allow-unresolved", action="store_true")

    init_parser = subparsers.add_parser("init-entity", help="Create a new entity overlay.")
    init_parser.add_argument("name", help="Lowercase entity folder name.")
    init_parser.add_argument("--display-name", required=True)
    init_parser.add_argument("--entities-dir", type=Path, default=Path("entities"))
    init_parser.add_argument(
        "--template-dir",
        type=Path,
        help="Template directory (defaults to <entities-dir>/example).",
    )

    configure_parser = subparsers.add_parser(
        "configure-entity", help="Write an entity's local connection references and domains."
    )
    configure_parser.add_argument("name", help="Lowercase entity folder name.")
    configure_parser.add_argument("--entities-dir", type=Path, default=Path("entities"))
    configure_parser.add_argument("--search-connection-id", required=True)
    configure_parser.add_argument("--search-index-name", required=True)
    configure_parser.add_argument("--mcp-url", required=True)
    configure_parser.add_argument("--mcp-connection-id", required=True)
    configure_parser.add_argument("--allowed-domain", action="append", required=True)
    return parser


def _validate_entity_name(parser: argparse.ArgumentParser, name: str) -> None:
    if not name.replace("-", "").isalnum() or name.lower() != name:
        parser.error("Entity name must contain lowercase letters, numbers, and hyphens")


def _configure_entity(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    _validate_entity_name(parser, args.name)
    target = args.entities_dir / args.name
    overlay_path = target / "overlay.yaml"
    if not overlay_path.is_file():
        parser.error(f"Entity overlay not found: {overlay_path}")

    values = {
        "search connection ID": args.search_connection_id,
        "search index name": args.search_index_name,
        "MCP URL": args.mcp_url,
        "MCP connection ID": args.mcp_connection_id,
    }
    invalid = [label for label, value in values.items() if not value.strip() or "\n" in value]
    if invalid:
        parser.error(f"Invalid values: {', '.join(invalid)}")
    mcp_url = urlsplit(args.mcp_url)
    if mcp_url.scheme != "https" or not mcp_url.netloc:
        parser.error("MCP URL must be an absolute HTTPS endpoint")

    overlay = yaml.safe_load(overlay_path.read_text(encoding="utf-8"))
    tools = overlay.get("tools", [])

    def find_tool(tool_id: str) -> dict:
        tool = next((item for item in tools if item.get("id") == tool_id), None)
        if tool is None:
            parser.error(f"Entity overlay must define the {tool_id} tool")
        return tool

    def variable_name(value: object, field: str) -> str:
        match = ENV_PATTERN.fullmatch(value) if isinstance(value, str) else None
        if match is None:
            parser.error(f"Entity overlay field {field} must contain an environment variable")
        return match.group(1)

    search_provider = find_tool("enterprise-knowledge").get("provider", {})
    mcp_provider = find_tool("government-systems").get("provider", {})
    env_values = {
        variable_name(search_provider.get("project_connection_id"), "search connection ID"):
            args.search_connection_id.strip(),
        variable_name(search_provider.get("index_name"), "search index name"):
            args.search_index_name.strip(),
        variable_name(mcp_provider.get("server_url"), "MCP URL"): args.mcp_url.strip(),
        variable_name(mcp_provider.get("project_connection_id"), "MCP connection ID"):
            args.mcp_connection_id.strip(),
    }
    web_tool = find_tool("approved-web-search")
    domains = list(dict.fromkeys(domain.strip().lower() for domain in args.allowed_domain))
    if any(not domain or "://" in domain or "/" in domain for domain in domains):
        parser.error("Approved domains must be host names without schemes or paths")

    env_path = target / ".env"
    env_path.write_text(
        "\n".join([*(f"{name}={value}" for name, value in env_values.items()), ""]),
        encoding="utf-8",
        newline="\n",
    )

    web_tool.setdefault("provider", {}).setdefault("filters", {})["allowed_domains"] = domains
    write_yaml(overlay_path, overlay)
    print(f"Configured {target}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "init-entity":
        _validate_entity_name(parser, args.name)
        source = args.template_dir or args.entities_dir / "example"
        target = args.entities_dir / args.name
        if not source.is_dir():
            parser.error(f"Entity template not found: {source}")
        if target.exists():
            parser.error(f"Entity already exists: {target}")
        shutil.copytree(source, target)
        overlay = target / "overlay.yaml"
        content = overlay.read_text(encoding="utf-8")
        content = content.replace("Example Entity", args.display_name)
        content = content.replace("EXAMPLE", args.name.replace("-", "_").upper())
        content = content.replace("example", args.name)
        overlay.write_text(content, encoding="utf-8", newline="\n")
        env_template = target / ".env.example"
        env_content = env_template.read_text(encoding="utf-8")
        env_content = env_content.replace("EXAMPLE", args.name.replace("-", "_").upper())
        env_template.write_text(env_content, encoding="utf-8", newline="\n")
        print(f"Created {target}")
        return 0

    if args.command == "configure-entity":
        return _configure_entity(parser, args)

    try:
        _, rendered = compile_bundle(
            args.core,
            args.overlay,
            strict=not args.allow_unresolved,
        )
    except (ConfigurationError, OSError) as error:
        parser.error(str(error))

    if args.command == "compile":
        write_yaml(args.output, rendered)
        print(f"Wrote {args.output}")
    else:
        print("Configuration is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())