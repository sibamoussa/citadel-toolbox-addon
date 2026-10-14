from __future__ import annotations

import argparse
import shutil
from collections.abc import Sequence
from pathlib import Path

from citadel_toolbox.compiler import ConfigurationError, compile_bundle, write_yaml


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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "init-entity":
        if not args.name.replace("-", "").isalnum() or args.name.lower() != args.name:
            parser.error("Entity name must contain lowercase letters, numbers, and hyphens")
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