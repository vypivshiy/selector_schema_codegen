"""OpenAPI schemas and endpoints → KDL json/@request conversion."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from .parser import JsonDict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type mapping
# ---------------------------------------------------------------------------

_TYPE_MAP: dict[str, str] = {
    "string": "str",
    "integer": "int",
    "number": "float",
    "boolean": "bool",
}


def _oas_type_to_kdl(schema: JsonDict) -> str:
    """Convert an OpenAPI schema to its KDL type token."""
    if "$ref" in schema:
        return _ref_name(schema["$ref"])

    oas_type = schema.get("type", "string")

    if oas_type == "array":
        items = schema.get("items", {"type": "string"})
        item_type = _oas_type_to_kdl(items)
        return f"(array){item_type}"

    if oas_type == "object":
        # Inline anonymous object — caller should have extracted it
        return "str"

    return _TYPE_MAP.get(oas_type, "str")


def _ref_name(ref: str) -> str:
    """Extract schema name from a ``$ref`` pointer."""
    return ref.rsplit("/", 1)[-1]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NON_IDENT_RE = re.compile(r"[^A-Za-z0-9_]")


def _to_snake(name: str) -> str:
    """Convert camelCase / hyphenated name to snake_case."""
    s1 = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    s2 = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s1)
    return _NON_IDENT_RE.sub("_", s2).lower().strip("_")


def _is_snake_case(name: str) -> bool:
    return bool(re.fullmatch(r"[a-z][a-z0-9_]*", name))


def _to_pascal(name: str) -> str:
    return "".join(
        part.capitalize() for part in _NON_IDENT_RE.split(name) if part
    )


def _placeholder_name(param_name: str) -> str:
    """Convert bracket query names like ``f[sorting]`` to ``f_sorting``."""
    cleaned = param_name.replace("[", "_").replace("]", "")
    return _to_snake(cleaned)


# ---------------------------------------------------------------------------
# JsonSchema — intermediate representation for a KDL ``json`` block
# ---------------------------------------------------------------------------


@dataclass
class JsonField:
    name: str  # snake_case field name
    type_token: str  # e.g. "str", "(array)int", "Pet"
    is_optional: bool = False
    alias: str | None = None  # original JSON key if differs
    enum_comment: str | None = None  # e.g. '// original: enum ["A", "B"]'


@dataclass
class JsonSchema:
    name: str
    fields: list[JsonField] = field(default_factory=list)
    is_array: bool = False
    deps: set[str] = field(default_factory=set)  # referenced schema names


# ---------------------------------------------------------------------------
# SchemaConverter
# ---------------------------------------------------------------------------


class SchemaConverter:
    """Convert OpenAPI schemas → list[JsonSchema].

    Works on **unresolved** schemas so ``$ref`` names are preserved.
    Only ``allOf`` is resolved internally for property merging.
    """

    def __init__(self, all_schemas: JsonDict | None = None) -> None:
        self._schemas = all_schemas or {}

    def convert_schemas(self, schemas: JsonDict) -> list[JsonSchema]:
        """Convert all schemas from ``components.schemas`` (or ``definitions``)."""
        self._schemas = schemas
        result: list[JsonSchema] = []
        for name, schema in schemas.items():
            js = self._convert_schema(name, schema)
            result.append(js)
        return result

    def _convert_schema(self, name: str, schema: JsonDict) -> JsonSchema:
        # Resolve allOf inline
        schema = self._resolve_allof(schema)

        fields: list[JsonField] = []
        deps: set[str] = set()
        required = set(schema.get("required", []))

        props = schema.get("properties", {})
        for prop_name, prop_schema in props.items():
            prop_schema = self._resolve_allof(prop_schema)
            f = self._convert_field(
                prop_name, prop_schema, prop_name in required
            )
            fields.append(f)
            if (
                f.type_token not in _TYPE_MAP.values()
                and not f.type_token.startswith("(array)")
            ):
                deps.add(f.type_token)
            if f.type_token.startswith("(array)"):
                inner = f.type_token[len("(array)") :]
                if inner not in _TYPE_MAP.values():
                    deps.add(inner)

        return JsonSchema(name=name, fields=fields, deps=deps)

    def _convert_field(
        self, prop_name: str, schema: JsonDict, is_required: bool
    ) -> JsonField:
        enum_values = schema.get("enum")
        enum_comment = None
        if enum_values:
            vals = ", ".join(repr(v) for v in enum_values)
            enum_comment = f"// original: enum [{vals}]"

        type_token = _oas_type_to_kdl(schema)

        snake = _to_snake(prop_name)
        alias = prop_name if prop_name != snake else None

        is_optional = not is_required or schema.get("nullable", False)

        return JsonField(
            name=snake,
            type_token=type_token,
            is_optional=is_optional,
            alias=alias,
            enum_comment=enum_comment,
        )

    def _resolve_allof(self, schema: JsonDict) -> JsonDict:
        if "allOf" not in schema:
            return schema
        merged: JsonDict = {"type": "object", "properties": {}}
        all_required: list[str] = []
        for entry in schema["allOf"]:
            if "$ref" in entry:
                ref_name = _ref_name(entry["$ref"])
                ref_schema = self._schemas.get(ref_name, {})
                ref_schema = self._resolve_allof(ref_schema)
            else:
                ref_schema = entry
            merged.get("properties", {}).update(
                ref_schema.get("properties", {})
            )
            all_required.extend(ref_schema.get("required", []))
        # Preserve sibling keys
        for k, v in schema.items():
            if k != "allOf":
                merged[k] = v
        if all_required:
            merged["required"] = list(set(all_required))
        return merged


def topological_sort(schemas: list[JsonSchema]) -> list[JsonSchema]:
    """Sort schemas so dependencies come before dependents (leaves first)."""
    by_name = {s.name: s for s in schemas}
    visited: set[str] = set()
    order: list[JsonSchema] = []

    def visit(name: str) -> None:
        if name in visited:
            return
        visited.add(name)
        s = by_name.get(name)
        if s:
            for dep in s.deps:
                if dep in by_name:
                    visit(dep)
            order.append(s)

    for s in schemas:
        visit(s.name)
    return order


# ---------------------------------------------------------------------------
# Endpoint data
# ---------------------------------------------------------------------------


@dataclass
class RequestBlock:
    """Represents a single ``@request`` block."""

    name: str  # method-resource, e.g. "list-pets"
    format: str  # "curl" | "raw_http"
    payload: str  # complete @request body text
    doc: str = ""
    response_schema: str = ""  # empty = void return


@dataclass
class ErrorMapping:
    status: int
    schema_name: str


@dataclass
class Endpoint:
    method: str
    path: str
    request: RequestBlock
    errors: list[ErrorMapping] = field(default_factory=list)


# ---------------------------------------------------------------------------
# RequestConverter
# ---------------------------------------------------------------------------

_STYLE_MAP: dict[tuple[str, bool], str] = {
    ("form", True): "repeat",
    ("form", False): "csv",
    ("pipeDelimited", True): "pipe",
    ("pipeDelimited", False): "pipe",
    ("spaceDelimited", True): "space",
    ("spaceDelimited", False): "space",
}


def _method_name(method: str, path: str) -> str:
    """Derive ``name=`` from HTTP method + path segments.

    GET /pets → get-pets, POST /pets → post-pets,
    GET /pets/{id} → get-pets, DELETE /pets/{id} → delete-pets.
    """
    parts = [p for p in path.strip("/").split("/") if not p.startswith("{")]
    resource = "-".join(parts) if parts else "root"
    return f"{method.lower()}-{resource}"


def _oas_type_to_placeholder(type_name: str | None) -> str:
    """Map OpenAPI parameter type → KDL placeholder type."""
    return _TYPE_MAP.get(type_name or "string", "str")


class RequestConverter:
    """Convert OpenAPI paths/items → list[Endpoint]."""

    def convert_paths(
        self,
        paths: JsonDict,
        base_url: str,
        schemas: JsonDict,
        endpoints_filter: set[tuple[str, str]] | None = None,
    ) -> list[Endpoint]:
        result: list[Endpoint] = []
        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue
            # shared parameters at path level
            path_params = path_item.get("parameters", [])
            for method in ("get", "post", "put", "patch", "delete"):
                operation = path_item.get(method)
                if not operation:
                    continue
                if (
                    endpoints_filter
                    and (method.upper(), path) not in endpoints_filter
                ):
                    continue
                ep = self._convert_operation(
                    method, path, operation, base_url, schemas, path_params
                )
                if ep:
                    result.append(ep)

        # Deduplicate method names by appending -N suffix
        name_counts: dict[str, int] = {}
        for ep in result:
            base = ep.request.name
            count = name_counts.get(base, 0)
            name_counts[base] = count + 1
        # Second pass: rename only if count > 1
        name_idx: dict[str, int] = {}
        for ep in result:
            base = ep.request.name
            if name_counts[base] > 1:
                idx = name_idx.get(base, 1)
                name_idx[base] = idx + 1
                ep.request.name = f"{base}-{idx}"

        return result

    def _convert_operation(
        self,
        method: str,
        path: str,
        operation: JsonDict,
        base_url: str,
        schemas: JsonDict,
        path_level_params: list[JsonDict],
    ) -> Endpoint | None:
        all_params = self._merge_params(
            path_level_params, operation.get("parameters", [])
        )

        # Separate params by location
        path_params = [p for p in all_params if p.get("in") == "path"]
        query_params = [p for p in all_params if p.get("in") == "query"]

        # Determine body
        body_info = self._extract_body(operation, schemas)
        body_type = body_info["type"]  # "none" | "json" | "form"
        body_schema = body_info.get("schema")
        body_required = body_info.get("required", [])

        # Determine response schema
        response_schema = self._extract_response_schema(operation, schemas)

        # Determine format
        fmt = self._select_format(method, body_type)

        # Build placeholder args
        name = _method_name(method, path)

        # Build payload
        if fmt == "curl":
            payload = self._build_curl(
                method, path, base_url, path_params, query_params
            )
        else:
            payload = self._build_raw_http(
                method,
                path,
                base_url,
                path_params,
                query_params,
                body_schema,
                body_required,
            )

        # Extract errors
        errors = self._extract_errors(operation, schemas)

        request = RequestBlock(
            name=name,
            format=fmt,
            payload=payload,
            doc=operation.get("summary", ""),
            response_schema=response_schema,
        )
        return Endpoint(
            method=method, path=path, request=request, errors=errors
        )

    # ---- helpers ----

    @staticmethod
    def _merge_params(
        path_params: list[JsonDict], op_params: list[JsonDict]
    ) -> list[JsonDict]:
        """Merge path-level and operation-level parameters, op overrides."""
        by_name: dict[str, JsonDict] = {}
        for p in path_params:
            if "$ref" in p:
                continue
            key = f"{p.get('in')}:{p.get('name')}"
            by_name[key] = p
        for p in op_params:
            if "$ref" in p:
                continue
            key = f"{p.get('in')}:{p.get('name')}"
            by_name[key] = p
        return list(by_name.values())

    @staticmethod
    def _select_format(method: str, body_type: str) -> str:
        if method.lower() in ("get", "delete"):
            return "curl"
        if body_type == "json":
            return "raw_http"
        if body_type == "form":
            return "curl"
        return "curl"

    def _build_curl(
        self,
        method: str,
        path: str,
        base_url: str,
        path_params: list[JsonDict],
        query_params: list[JsonDict],
    ) -> str:
        url = self._build_url(path, base_url, path_params, query_params)
        parts = []
        if method.lower() == "delete":
            parts.append(f"curl -X DELETE '{url}'")
        elif method.lower() == "get":
            parts.append(f"curl '{url}'")
        else:
            parts.append(f"curl -X {method.upper()} '{url}'")
        return "\n".join(parts)

    def _build_url(
        self,
        path: str,
        base_url: str,
        path_params: list[JsonDict],
        query_params: list[JsonDict],
    ) -> str:
        url = path
        # Replace path params: /pets/{petId} → /pets/{{pet_id:int}}
        for p in path_params:
            name = p["name"]
            ptype = _oas_type_to_placeholder(self._schema_of(p).get("type"))
            ph_name = _placeholder_name(name)
            ph = "{{" + ph_name + ":" + ptype + "}}"
            url = url.replace("{" + name + "}", ph)

        # Build query string
        qs_parts = []
        for p in query_params:
            ph_name = _placeholder_name(p["name"])
            p_schema = self._schema_of(p)
            ptype = _oas_type_to_placeholder(p_schema.get("type"))
            is_required = p.get("required", False)
            is_array = p_schema.get("type") == "array"

            ph = "{{" + ph_name + ":" + ptype
            if is_array:
                ph += "[]"
            if not is_required:
                ph += "?"
            # Array style
            if is_array:
                style = p.get("style", "form")
                explode = p.get("explode", True)
                kdl_style = _STYLE_MAP.get((style, explode), "repeat")
                ph += "|" + kdl_style
            ph += "}}"

            # Keep original param name (may have brackets) in URL
            qs_parts.append(p["name"] + "=" + ph)

        if qs_parts:
            url += "?" + "&".join(qs_parts)

        return base_url.rstrip("/") + url

    def _build_raw_http(
        self,
        method: str,
        path: str,
        base_url: str,
        path_params: list[JsonDict],
        query_params: list[JsonDict],
        body_schema: JsonDict | None,
        body_required: list[str],
    ) -> str:
        from urllib.parse import urlparse

        parsed = urlparse(base_url)
        host = parsed.hostname
        if parsed.port:
            host = f"{host}:{parsed.port}"

        url_path = path
        # Replace path params
        for p in path_params:
            pname = p["name"]
            ptype = _oas_type_to_placeholder(self._schema_of(p).get("type"))
            ph_name = _placeholder_name(pname)
            ph = "{{" + ph_name + ":" + ptype + "}}"
            url_path = url_path.replace("{" + pname + "}", ph)

        # Add query params
        qs_parts = []
        for p in query_params:
            ph_name = _placeholder_name(p["name"])
            ptype = _oas_type_to_placeholder(self._schema_of(p).get("type"))
            is_required = p.get("required", False)
            ph = "{{" + ph_name + ":" + ptype
            if not is_required:
                ph += "?"
            ph += "}}"
            qs_parts.append(p["name"] + "=" + ph)
        if qs_parts:
            url_path += "?" + "&".join(qs_parts)

        lines = [
            f"{method.upper()} {url_path} HTTP/1.1",
            f"Host: {host}",
            "Content-Type: application/json",
        ]

        # Build JSON body
        if body_schema:
            body = self._build_json_body(body_schema, set(body_required))
            lines.append("")
            lines.append(body)

        return "\n".join(lines)

    def _build_json_body(self, schema: JsonDict, required: set[str]) -> str:
        """Build a JSON template string with placeholders."""
        props = schema.get("properties", {})
        if not props:
            return "{}"

        parts: list[str] = []
        for key, prop_schema in props.items():
            snake = _to_snake(key)
            ptype = _oas_type_to_placeholder(prop_schema.get("type"))
            is_req = key in required

            if prop_schema.get("type") in ("integer", "number"):
                # Numeric: no quotes
                ph = f"{{{{{snake}:{ptype}"
                if not is_req:
                    ph += "?"
                ph += "}}"
                parts.append(f'"{key}": {ph}')
            elif prop_schema.get("type") == "boolean":
                ph = f"{{{{{snake}:{ptype}"
                if not is_req:
                    ph += "?"
                ph += "}}"
                parts.append(f'"{key}": {ph}')
            elif prop_schema.get("type") == "object":
                # Nested object — inline
                inner = self._build_json_body(
                    prop_schema, set(prop_schema.get("required", []))
                )
                parts.append(f'"{key}": {inner}')
            else:
                # String-like
                ph = f"{{{{{snake}:{ptype}"
                if not is_req:
                    ph += "?"
                ph += "}}"
                parts.append(f'"{key}": "{ph}"')

        return "{" + ", ".join(parts) + "}"

    def _extract_body(self, operation: JsonDict, schemas: JsonDict) -> JsonDict:
        """Extract request body info from an operation."""
        body = operation.get("requestBody")
        if not body:
            return {"type": "none"}

        content = body.get("content", {})
        if "application/json" in content:
            schema = self._resolve_inline(
                content["application/json"].get("schema", {}), schemas
            )
            return {
                "type": "json",
                "schema": schema,
                "required": schema.get("required", []),
            }
        if "application/x-www-form-urlencoded" in content:
            schema = self._resolve_inline(
                content["application/x-www-form-urlencoded"].get("schema", {}),
                schemas,
            )
            return {
                "type": "form",
                "schema": schema,
                "required": schema.get("required", []),
            }
        return {"type": "none"}

    def _extract_response_schema(
        self, operation: JsonDict, schemas: JsonDict
    ) -> str:
        """Get the response schema name for the 2xx response."""
        responses = operation.get("responses", {})
        for code in sorted(responses):
            if not code.startswith("2"):
                continue
            resp = responses[code]
            content = resp.get("content", {})
            for ct, ct_info in content.items():
                schema_ref = ct_info.get("schema", {}).get("$ref")
                if schema_ref:
                    return _ref_name(schema_ref)
                # Inline schema — extract to named
                schema = ct_info.get("schema")
                if schema and schema.get("type") == "array":
                    items = schema.get("items", {})
                    if "$ref" in items:
                        return _ref_name(items["$ref"])
        return ""

    def _extract_errors(
        self, operation: JsonDict, schemas: JsonDict
    ) -> list[ErrorMapping]:
        """Extract @error mappings from non-2xx responses."""
        errors: list[ErrorMapping] = []
        seen: set[int] = set()
        responses = operation.get("responses", {})
        for code, resp in responses.items():
            try:
                status = int(code)
            except ValueError:
                continue
            if 200 <= status < 300:
                continue
            content = resp.get("content", {})
            for ct_info in content.values():
                ref = ct_info.get("schema", {}).get("$ref")
                if ref and status not in seen:
                    errors.append(
                        ErrorMapping(status=status, schema_name=_ref_name(ref))
                    )
                    seen.add(status)
        return errors

    @staticmethod
    def _schema_of(param: JsonDict) -> JsonDict:
        """Get the schema dict of a parameter (handles inline schema)."""
        return param.get("schema", {"type": "string"})

    @staticmethod
    def _resolve_inline(schema: JsonDict, schemas: JsonDict) -> JsonDict:
        if "$ref" in schema:
            name = _ref_name(schema["$ref"])
            return schemas.get(name, schema)
        return schema


def extract_base_url(spec: JsonDict) -> str:
    """Extract the first server URL from the spec."""
    servers = spec.get("servers", [])
    if servers:
        url = servers[0].get("url", "")
        if url:
            return url.rstrip("/")

    # Swagger 2
    host = spec.get("host")
    base_path = spec.get("basePath", "")
    schemes = spec.get("schemes", ["https"])
    if host:
        return f"{schemes[0]}://{host}{base_path}".rstrip("/")

    return ""
