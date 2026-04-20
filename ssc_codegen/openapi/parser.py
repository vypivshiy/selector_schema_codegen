"""OpenAPI 3.x / Swagger 2.x specification parser with $ref resolution."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

JsonDict = dict[str, Any]


def load_spec(path: str | Path) -> JsonDict:
    """Load an OpenAPI spec from YAML or JSON file (auto-detected)."""
    raw = Path(path).read_text(encoding="utf-8")

    # Try JSON first (faster, no external dep for parsing)
    try:
        result = json.loads(raw)
        if isinstance(result, dict):
            return result
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback to YAML
    result = yaml.safe_load(raw)
    if not isinstance(result, dict):
        msg = f"Expected a mapping in {path}, got {type(result).__name__}"
        raise ValueError(msg)
    return result


def resolve_refs(spec: JsonDict) -> JsonDict:
    """Return a deep copy of *spec* with all ``$ref`` pointers resolved."""
    return _resolve(spec, spec, set())


def _resolve(value: Any, root: JsonDict, seen: frozenset[str]) -> Any:
    if isinstance(value, dict):
        if "$ref" in value:
            ref_path = value["$ref"]
            if ref_path in seen:
                logger.warning("circular $ref detected: %s", ref_path)
                return value
            target = _follow_ref(ref_path, root)
            # Merge any sibling keys alongside the resolved ref
            siblings = {k: v for k, v in value.items() if k != "$ref"}
            if siblings and isinstance(target, dict):
                target = {**target, **siblings}
            return _resolve(target, root, seen | {ref_path})

        if "allOf" in value:
            return _resolve_allof(value, root, seen)

        if "oneOf" in value:
            variant = value["oneOf"][0]
            logger.warning("oneOf encountered, using first variant")
            return _resolve(variant, root, seen)

        if "anyOf" in value:
            variant = value["anyOf"][0]
            logger.warning("anyOf encountered, using first variant")
            return _resolve(variant, root, seen)

        return {k: _resolve(v, root, seen) for k, v in value.items()}

    if isinstance(value, list):
        return [_resolve(item, root, seen) for item in value]

    return value


def _follow_ref(ref: str, root: JsonDict) -> Any:
    """Follow a JSON pointer like ``#/components/schemas/Name``."""
    if not ref.startswith("#/"):
        msg = f"Only local $ref pointers supported, got: {ref}"
        raise ValueError(msg)
    parts = ref[2:].split("/")
    node: Any = root
    for part in parts:
        # Handle JSON pointer escaping
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict):
            node = node.get(part)
        else:
            return None
        if node is None:
            logger.warning("unresolved $ref: %s", ref)
            return {}
    return node


def _resolve_allof(
    node: JsonDict, root: JsonDict, seen: frozenset[str]
) -> JsonDict:
    """Merge all allOf entries into a single flat dict."""
    merged: JsonDict = {}
    for entry in node["allOf"]:
        resolved = _resolve(entry, root, seen)
        if isinstance(resolved, dict):
            _deep_merge(merged, resolved)

    # Preserve sibling keys (e.g. description alongside allOf)
    for k, v in node.items():
        if k != "allOf":
            merged[k] = _resolve(v, root, seen)
    return merged


def _deep_merge(target: JsonDict, source: JsonDict) -> None:
    for key, value in source.items():
        if (
            key in target
            and isinstance(target[key], dict)
            and isinstance(value, dict)
        ):
            _deep_merge(target[key], value)
        else:
            target[key] = value


def normalize_spec(spec: JsonDict) -> JsonDict:
    """Normalize Swagger 2 differences so downstream code can treat it as OpenAPI 3."""
    if spec.get("swagger", "").startswith("2"):
        spec.setdefault("components", {})
        # Move definitions → components/schemas
        if "definitions" in spec:
            spec["components"].setdefault("schemas", {})
            spec["components"]["schemas"].update(spec.pop("definitions"))
        # Move responses → components/responses
        if "responses" in spec:
            spec["components"].setdefault("responses", {})
            spec["components"]["responses"].update(spec.pop("responses"))
        # Move parameters → components/parameters
        if "parameters" in spec:
            spec["components"].setdefault("parameters", {})
            spec["components"]["parameters"].update(spec.pop("parameters"))
        logger.info("Normalized Swagger 2 spec to OpenAPI 3 format")
    return spec
