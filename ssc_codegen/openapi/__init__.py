"""OpenAPI → KDL converter.

Public API:
    convert_openapi(spec_path, output_path, endpoints=None) -> str
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Sequence

from .converter import (
    Endpoint,
    ErrorMapping,
    JsonSchema,
    RequestConverter,
    SchemaConverter,
    extract_base_url,
    topological_sort,
)
from .emitter import emit_kdl
from .parser import load_spec, normalize_spec, resolve_refs

logger = logging.getLogger(__name__)


def convert_openapi(
    spec_path: str | Path,
    output_path: str | Path | None = None,
    endpoints: Sequence[tuple[str, str]] | None = None,
) -> str:
    """Convert an OpenAPI/Swagger spec to a ``.kdl`` file.

    Args:
        spec_path: Path to YAML or JSON spec file.
        output_path: Optional output file path. If given, writes result.
        endpoints: Optional filter as ``[(method, path), ...]``, e.g.
            ``[("GET", "/pets"), ("POST", "/pets")]``.

    Returns:
        Generated KDL text.
    """
    # 1. Parse
    raw = load_spec(spec_path)
    spec = normalize_spec(raw)

    # 2. Schemas — use unresolved so $ref names are preserved
    schemas_raw = spec.get("components", {}).get("schemas", {})
    schema_converter = SchemaConverter(all_schemas=schemas_raw)
    schemas = schema_converter.convert_schemas(schemas_raw)
    schemas = topological_sort(schemas)

    # 3. Resolve refs for request body resolution only
    resolved = resolve_refs(spec)
    schemas_resolved = resolved.get("components", {}).get("schemas", {})

    # 4. Endpoints — unresolved paths for $ref extraction in responses/errors,
    #    resolved schemas for body property resolution.
    base_url = extract_base_url(spec)
    raw_paths = spec.get("paths", {})
    endpoints_filter = set(endpoints) if endpoints else None
    req_converter = RequestConverter()
    ep_list = req_converter.convert_paths(
        raw_paths, base_url, schemas_resolved, endpoints_filter
    )

    # 5. Collect errors (deduplicated)
    all_errors: list[ErrorMapping] = []
    seen: set[tuple[int, str]] = set()
    for ep in ep_list:
        for err in ep.errors:
            key = (err.status, err.schema_name)
            if key not in seen:
                seen.add(key)
                all_errors.append(err)

    # 6. Title
    title = spec.get("info", {}).get("title", "API")

    # 7. Emit
    text = emit_kdl(title, base_url, schemas, ep_list, all_errors)

    if output_path is not None:
        Path(output_path).write_text(text, encoding="utf-8")

    return text
