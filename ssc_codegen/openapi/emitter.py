"""Emit KDL text from converted OpenAPI data."""

from __future__ import annotations

from typing import TextIO

from .converter import (
    Endpoint,
    ErrorMapping,
    JsonField,
    JsonSchema,
)


def emit_kdl(
    title: str,
    base_url: str,
    schemas: list[JsonSchema],
    endpoints: list[Endpoint],
    errors: list[ErrorMapping],
    *,
    out: TextIO | None = None,
) -> str:
    """Assemble a complete ``.kdl`` file and return it as a string.

    If *out* is given, also writes to it.
    """
    parts: list[str] = []

    # 1. Module docstring
    doc_lines = [f"{title} REST API client.", f"Base URL: {base_url}"]
    parts.append(f'@doc """\n{" ".join(doc_lines)}\n"""')
    parts.append("")

    # 2. json schemas (topologically sorted — leaves first)
    for schema in schemas:
        parts.append(_emit_json_schema(schema))
        parts.append("")

    # 3. Error json schemas (deduplicated, placed before struct)
    seen_error_schemas: set[str] = set()
    for err in errors:
        if err.schema_name not in seen_error_schemas:
            seen_error_schemas.add(err.schema_name)
            # Only emit if not already in regular schemas
            schema_names = {s.name for s in schemas}
            if err.schema_name not in schema_names:
                parts.append(f"json {err.schema_name} {{")
                parts.append("    message str")
                parts.append("}")
                parts.append("")

    # 4. struct type=rest
    struct_name = _derive_struct_name(title)
    parts.append(f"struct {struct_name} type=rest {{")
    parts.append('    @doc """')
    parts.append(f"    {title} API client.")
    parts.append('    """')

    for ep in endpoints:
        parts.append("")
        parts.append(_emit_request(ep.request))

    # Deduplicated @error entries
    seen_errors: set[int] = set()
    for err in errors:
        if err.status not in seen_errors:
            seen_errors.add(err.status)
            parts.append(f"    @error {err.status} {err.schema_name}")

    parts.append("}")

    text = "\n".join(parts) + "\n"
    if out is not None:
        out.write(text)
    return text


def _emit_json_schema(schema: JsonSchema) -> str:
    array_marker = " array=#true" if schema.is_array else ""
    lines = [f"json {schema.name}{array_marker} {{"]
    for f in schema.fields:
        line = _emit_field(f)
        lines.append(f"    {line}")
    lines.append("}")
    return "\n".join(lines)


def _emit_field(f: JsonField) -> str:
    parts: list[str] = [f.name, f.type_token]
    if f.is_optional and not f.type_token.endswith("?"):
        parts[-1] += "?"
    if f.alias:
        parts.append(f'"{f.alias}"')
    line = " ".join(parts)
    if f.enum_comment:
        line = f"{f.enum_comment}\n    {line}"
    return line


def _emit_request(req: object) -> str:
    r = req  # type: RequestBlock
    attrs: list[str] = [f"name={r.name}"]
    if r.response_schema:
        attrs.append(f"response={r.response_schema}")
    if r.doc:
        attrs.append(f'doc="{r.doc}"')
    attr_str = " ".join(attrs)

    # Indent payload
    payload_lines = r.payload.split("\n")
    indented = "\n".join("    " + line for line in payload_lines)

    return f'    @request {attr_str} """\n{indented}\n    """'


def _derive_struct_name(title: str) -> str:
    """PascalCase struct name from API title."""
    import re

    cleaned = re.sub(r"[^A-Za-z0-9\s]", "", title)
    parts = cleaned.split()
    if not parts:
        return "Api"
    name = "".join(p.capitalize() for p in parts)
    if not name.endswith("Api"):
        name += "Api"
    return name
