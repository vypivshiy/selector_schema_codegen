from ssc_codegen.converters.base import ConverterContext
from ssc_codegen.converters.helpers import to_pascal_case

from ssc_codegen.ast import (
    Module,
    Struct,
    JsonDef,
    RequestConfig,
    ErrorResponse,
    PlaceholderSpec,
)



# ---------------------------------------------------------------------------
# Cluster A: REST module-level helpers (public API for all py_ converters)
# ---------------------------------------------------------------------------


def _module_has_rest(node) -> bool:
    """True if the given node's Module has any `struct type=rest`."""
    module = node
    while module is not None and not isinstance(module, Module):
        module = getattr(module, "parent", None)
    if module is None:
        return False
    return any(
        isinstance(n, Struct) and n.is_rest for n in getattr(module, "body", [])
    )


def rest_imports(node) -> list[str]:
    """Extra imports required when the module has any `struct type=rest`."""
    if not _module_has_rest(node):
        return []
    return [
        "from dataclasses import dataclass, field",
        "from typing import Generic, Literal, Mapping, TypeVar",
    ]


def http_client_import(ctx: ConverterContext) -> list[str]:
    """Return the import line(s) for the chosen HTTP client, or [] if none."""
    client = ctx.meta.get("http_client", "")
    if client == "requests":
        return ["import requests"]
    if client == "httpx":
        return ["import httpx"]
    return []


def rest_utilities(node) -> list[str]:
    """Ok/Err/UnknownErr/TransportErr + _parse_response block; empty if no REST."""
    if not _module_has_rest(node):
        return []
    return [
        "_T = TypeVar('_T')",
        "_E = TypeVar('_E')",
        "\n",
        "@dataclass(frozen=True)",
        "class Ok(Generic[_T]):",
        "    status: int = 0",
        "    headers: Mapping[str, str] = field(default_factory=dict)",
        "    value: _T = None  # type: ignore[assignment]",
        "    is_ok: Literal[True] = True",
        "\n",
        "@dataclass(frozen=True)",
        "class Err(Generic[_E]):",
        "    status: int = 0",
        "    headers: Mapping[str, str] = field(default_factory=dict)",
        "    value: _E = None  # type: ignore[assignment]",
        "    is_ok: Literal[False] = False",
        "\n",
        "@dataclass(frozen=True)",
        "class UnknownErr(Err[Any]):",
        "    pass",
        "\n",
        "@dataclass(frozen=True)",
        "class TransportErr(Err[None]):",
        "    status: Literal[0] = 0",
        "    cause: str = ''",
        "    value: None = None",
        "    headers: Mapping[str, str] = field(default_factory=dict)",
        "\n\n",
        "def _parse_response(_resp):",
        "    _status = _resp.status_code",
        "    _headers = {k.lower(): v for k, v in _resp.headers.items()}",
        "    try:",
        "        _body = _resp.json()",
        "    except Exception:",
        "        _body = None",
        "    return _status, _headers, _body",
        "\n\n",
    ]


# ---------------------------------------------------------------------------
# Cluster B: REST error helpers
# ---------------------------------------------------------------------------


def _err_subclass_name(struct_name: str, err: ErrorResponse) -> str:
    """Naming: `<Struct>Err<Status>[<FieldPascal>]`."""
    base = f"{to_pascal_case(struct_name)}Err{err.status}"
    if err.discriminator_field:
        base += to_pascal_case(err.discriminator_field)
    return base


def _err_value_type(err: ErrorResponse, struct: Struct) -> str:
    """Return the typed value annotation for an Err subclass."""
    schema = err.schema_name
    if not schema:
        return "Any"
    type_name = f"{to_pascal_case(schema)}Json"
    module = struct.parent
    if module is not None:
        for n in module.body:
            if isinstance(n, JsonDef) and n.name == schema and n.is_array:
                return f"List[{type_name}]"
    return type_name


def _rest_err_union_type(struct: Struct) -> str:
    """Return the typed union of all Err variants for _dispatch_err sig."""
    variants: list[str] = []
    seen: set[str] = set()
    for err in struct.errors:
        cls_name = _err_subclass_name(struct.name, err)
        if cls_name not in seen:
            seen.add(cls_name)
            variants.append(cls_name)
    return "Union[" + ", ".join([*variants, "UnknownErr", "None"]) + "]"


def _emit_dispatch_err_py(node: Struct, ctx: ConverterContext) -> list[str]:
    """Emit the `_dispatch_err` @staticmethod lines inside a REST class.

    ctx arrives from StructDocstring — already at class-body depth.
    """
    i1 = ctx.indent  # class-body level
    i2 = i1 + ctx.indent_char  # method body
    i3 = i2 + ctx.indent_char  # nested (if ...:)
    i4 = i3 + ctx.indent_char

    errors = node.errors
    status_errors = [e for e in errors if e.discriminator_field is None]
    field_errors = [e for e in errors if e.discriminator_field is not None]
    union_type = _rest_err_union_type(node)

    lines: list[str] = [
        f"{i1}@staticmethod",
        f"{i1}def _dispatch_err("
        f"_status: int, _headers: Mapping[str, str], _body: Any"
        f") -> {union_type}:",
        f"{i2}if 200 <= _status < 300:",
    ]

    # 2xx field discriminators check first, inside the 2xx branch
    if field_errors:
        lines.append(f"{i3}if isinstance(_body, dict):")
        emitted_field_branch = False
        for err in field_errors:
            if 200 <= err.status < 300:
                cls_name = _err_subclass_name(node.name, err)
                lines.append(
                    f"{i4}if _status == {err.status} "
                    f"and {err.discriminator_field!r} in _body:"
                )
                lines.append(
                    f"{i4}{ctx.indent_char}return {cls_name}("
                    f"headers=_headers, value=_body)"
                )
                emitted_field_branch = True
        if not emitted_field_branch:
            # no 2xx-field errors → drop the isinstance guard
            lines.pop()
    lines.append(f"{i3}return None")

    # non-2xx status routing
    for err in status_errors:
        cls_name = _err_subclass_name(node.name, err)
        lines.append(f"{i2}if _status == {err.status}:")
        lines.append(f"{i3}return {cls_name}(headers=_headers, value=_body)")
    # non-2xx field discriminators (unusual but supported)
    for err in field_errors:
        if not (200 <= err.status < 300):
            cls_name = _err_subclass_name(node.name, err)
            lines.append(
                f"{i2}if _status == {err.status} "
                f"and isinstance(_body, dict) "
                f"and {err.discriminator_field!r} in _body:"
            )
            lines.append(
                f"{i3}return {cls_name}(headers=_headers, value=_body)"
            )

    lines.append(
        f"{i2}return UnknownErr(status=_status, headers=_headers, value=_body)"
    )
    return lines


# ---------------------------------------------------------------------------
# Cluster C: Request/fetch method builders
# ---------------------------------------------------------------------------


_PY_PRIM_ANNO = {"str": "str", "int": "int", "float": "float", "bool": "bool"}


def _ph_to_py_annotation(ph: PlaceholderSpec) -> tuple[str, str]:
    """Return (annotation, default_suffix). Suffix is '' or ' = None'."""
    anno = _PY_PRIM_ANNO[ph.type_name]
    if ph.is_array:
        anno = f"List[{anno}]"
    if ph.is_optional:
        return f"Optional[{anno}]", " = None"
    return anno, ""


def _render_signature_params(placeholders: list[PlaceholderSpec]) -> str:
    """Build keyword-only parameters clause: ', *, a: int, b: Optional[str] = None'."""
    if not placeholders:
        return ""
    required = [p for p in placeholders if not p.is_optional]
    optional = [p for p in placeholders if p.is_optional]
    parts: list[str] = []
    for ph in required + optional:
        anno, default = _ph_to_py_annotation(ph)
        parts.append(f"{ph.name}: {anno}{default}")
    return ", *, " + ", ".join(parts)


def _resolve_ok_payload_type(node: RequestConfig) -> str:
    """Return the Python type annotation for the successful payload."""
    if not node.response_schema:
        return "None"
    struct = node.parent
    module = struct.parent if struct is not None else None
    schema_type = f"{to_pascal_case(node.response_schema)}Json"
    if module is not None:
        for n in module.body:
            if isinstance(n, JsonDef) and n.name == node.response_schema:
                if n.is_array:
                    return f"List[{schema_type}]"
                break
    return schema_type


def _result_alias_name(raw_name: str) -> str:
    """Convert raw @request name to public Result type alias name."""
    return to_pascal_case(raw_name or "fetch") + "Result"


def _emit_result_aliases(struct: Struct) -> list[str]:
    """Emit per-endpoint Result type alias definitions for a REST struct."""
    lines: list[str] = []
    for child in struct.body:
        if not isinstance(child, RequestConfig):
            continue
        raw_name = child.name or "fetch"
        alias_name = _result_alias_name(raw_name)
        payload = _resolve_ok_payload_type(child)
        err_variants: list[str] = []
        seen: set[str] = set()
        for err in struct.errors:
            cls_name = _err_subclass_name(struct.name, err)
            if cls_name not in seen:
                seen.add(cls_name)
                err_variants.append(cls_name)
        parts = [f"Ok[{payload}]", *err_variants, "UnknownErr", "TransportErr"]
        lines.append(f"{alias_name} = Union[" + ", ".join(parts) + "]")
    return lines


def _resolve_response_type(node: RequestConfig) -> str:
    """Return the Result type alias name for a REST method signature."""
    return _result_alias_name(node.name)


def _build_request_method(
    *,
    name: str,
    is_async: bool,
    client_type: str,
    struct_name: str,
    call_args: list[str],
    ph_params: str,
    pre_lines: list[str],
    response_path: str,
    response_join: str,
    i1: str,
    i2: str,
    i3: str,
) -> list[str]:
    async_kw = "async " if is_async else ""
    await_kw = "await " if is_async else ""
    lines: list[str] = [
        f"{i1}@classmethod",
        f'{i1}{async_kw}def {name}(cls, client: {client_type}{ph_params}) -> "{struct_name}":',
    ]
    lines.extend(pre_lines)
    lines.append(f"{i2}_resp = {await_kw}client.request(")
    lines.extend(f"{i3}{a}" for a in call_args)
    lines.append(f"{i2})")
    lines.append(f"{i2}_resp.raise_for_status()")
    if response_path:
        accessor = "".join(f"[{p!r}]" for p in response_path.split("."))
        lines.append(f"{i2}_data = _resp.json()")
        if response_join:
            lines.append(f"{i2}_body = {response_join!r}.join(_data{accessor})")
        else:
            lines.append(f"{i2}_body = _data{accessor}")
    else:
        lines.append(f"{i2}_body = _resp.text")
    lines.append(f"{i2}return cls(_body)")
    return lines


def _build_rest_method(
    *,
    node: RequestConfig,
    name: str,
    is_async: bool,
    client_type: str,
    call_args: list[str],
    ph_params: str,
    pre_lines: list[str],
    ret_type: str,
    transport_exc: str,
    i1: str,
    i2: str,
    i3: str,
    i4: str,
) -> list[str]:
    async_kw = "async " if is_async else ""
    await_kw = "await " if is_async else ""

    lines: list[str] = [
        f"{i1}@classmethod",
        f"{i1}{async_kw}def {name}(cls, client: {client_type}"
        f"{ph_params}) -> {ret_type}:",
    ]
    if node.doc:
        lines.append(f'{i2}"""{node.doc}"""')
    lines.extend(pre_lines)
    lines.append(f"{i2}try:")
    lines.append(f"{i3}_resp = {await_kw}client.request(")
    lines.extend(f"{i4}{a}" for a in call_args)
    lines.append(f"{i3})")
    lines.append(f"{i2}except {transport_exc} as _exc:")
    lines.append(f"{i3}return TransportErr(cause=repr(_exc))")
    lines.append(f"{i2}_status, _headers, _body = _parse_response(_resp)")
    lines.append(f"{i2}_err = cls._dispatch_err(_status, _headers, _body)")
    lines.append(f"{i2}if _err is not None:")
    lines.append(f"{i3}return _err")
    ok_value = "_body" if node.response_schema else "None"
    lines.append(
        f"{i2}return Ok(status=_status, headers=_headers, value={ok_value})"
    )
    return lines
