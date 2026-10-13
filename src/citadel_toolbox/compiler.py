from __future__ import annotations

import copy
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

ENV_PATTERN = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")
LIST_KEYS = ("tools", "skills")


class ConfigurationError(ValueError):
    """Raised when a bundle cannot be safely compiled."""


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        value = yaml.safe_load(stream) or {}
    if not isinstance(value, dict):
        raise ConfigurationError(f"{path} must contain a YAML mapping")
    return value


def _merge_mapping(base: Mapping[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(dict(base))
    for key, value in overlay.items():
        if value is None:
            merged.pop(key, None)
        elif isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = _merge_mapping(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _merge_named_items(base: list[Any], overlay: list[Any], key: str) -> list[Any]:
    if any(not isinstance(item, dict) or key not in item for item in [*base, *overlay]):
        raise ConfigurationError(f"Every {key} list item must be a mapping containing '{key}'")

    by_name = {item[key]: copy.deepcopy(item) for item in base}
    order = [item[key] for item in base]
    for item in overlay:
        name = item[key]
        if name not in by_name:
            order.append(name)
            by_name[name] = {}
        by_name[name] = _merge_mapping(by_name[name], item)
    return [by_name[name] for name in order]


def merge_bundle(core: Mapping[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    overlay_metadata = {
        key: value for key, value in overlay.items() if key not in LIST_KEYS
    }
    merged = _merge_mapping(core, overlay_metadata)
    for list_key in LIST_KEYS:
        merged[list_key] = _merge_named_items(
            list(core.get(list_key, [])),
            list(overlay.get(list_key, [])),
            "id",
        )
    return merged


def _substitute(value: Any, variables: Mapping[str, str], unresolved: set[str]) -> Any:
    if isinstance(value, str):
        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in variables:
                unresolved.add(name)
                return match.group(0)
            return variables[name]

        return ENV_PATTERN.sub(replace, value)
    if isinstance(value, list):
        return [_substitute(item, variables, unresolved) for item in value]
    if isinstance(value, dict):
        return {key: _substitute(item, variables, unresolved) for key, item in value.items()}
    return value


def substitute_variables(
    bundle: Mapping[str, Any], variables: Mapping[str, str], *, strict: bool = True
) -> dict[str, Any]:
    unresolved: set[str] = set()
    result = _substitute(copy.deepcopy(dict(bundle)), variables, unresolved)
    if strict and unresolved:
        names = ", ".join(sorted(unresolved))
        raise ConfigurationError(f"Missing required variables: {names}")
    return result


def validate_bundle(bundle: Mapping[str, Any]) -> None:
    if bundle.get("apiVersion") != "citadel.microsoft.com/v1alpha1":
        raise ConfigurationError("apiVersion must be citadel.microsoft.com/v1alpha1")
    if bundle.get("kind") != "ToolboxBundle":
        raise ConfigurationError("kind must be ToolboxBundle")

    seen: set[str] = set()
    for tool in bundle.get("tools", []):
        tool_id = tool.get("id")
        if not tool_id or tool_id in seen:
            raise ConfigurationError(f"Tool IDs must be present and unique: {tool_id!r}")
        seen.add(tool_id)
        if not tool.get("enabled", True):
            continue
        if tool.get("risk") == "write" and tool.get("require_approval") != "always":
            raise ConfigurationError(
                f"Write-capable tool '{tool_id}' must set require_approval: always"
            )


def render_toolbox(bundle: Mapping[str, Any]) -> dict[str, Any]:
    validate_bundle(bundle)
    rendered: dict[str, Any] = {
        "description": bundle.get("metadata", {}).get("description", "Citadel Toolbox"),
        "connections": [],
        "tools": [],
        "skills": [],
    }
    for tool in bundle.get("tools", []):
        if not tool.get("enabled", True):
            continue
        provider = copy.deepcopy(tool.get("provider", {}))
        provider_type = provider.get("type")
        if provider_type in {"azure_ai_search", "mcp"}:
            connection_id = provider.get("project_connection_id", "")
            connection = {"name": connection_id.rstrip("/").rsplit("/", 1)[-1]}
            if provider_type == "azure_ai_search":
                connection["index"] = provider["index_name"]
            rendered["connections"].append(connection)
            continue
        if provider.get("type") != "toolbox_search":
            provider.setdefault("name", tool["id"])
        if "require_approval" in tool:
            provider["require_approval"] = tool["require_approval"]
        rendered["tools"].append(provider)
    for skill in bundle.get("skills", []):
        reference = {"name": skill["id"]}
        if "version" in skill:
            reference["version"] = str(skill["version"])
        rendered["skills"].append(reference)
    if not rendered["connections"]:
        del rendered["connections"]
    return rendered


def compile_bundle(
    core_path: Path,
    overlay_path: Path,
    *,
    variables: Mapping[str, str] | None = None,
    strict: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    bundle = merge_bundle(load_yaml(core_path), load_yaml(overlay_path))
    for list_key in LIST_KEYS:
        bundle[list_key] = [
            item for item in bundle.get(list_key, []) if item.get("enabled", True)
        ]
    bundle = substitute_variables(bundle, variables or os.environ, strict=strict)
    validate_bundle(bundle)
    return bundle, render_toolbox(bundle)


def write_yaml(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        yaml.safe_dump(dict(value), stream, sort_keys=False, allow_unicode=False)