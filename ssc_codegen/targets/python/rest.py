"""Python REST/fetch codegen — pure functions for MethodFetch, MethodRest,
ResultVariantDef, ResultAliasDef, MatcherListDef AST nodes.

Called by PythonVisitor via thin delegate methods.  The HTTP library strategy
(httpx/aiohttp/requests) is passed as a parameter where needed.
"""

from __future__ import annotations

import inspect
from typing import cast

from ssc_codegen.ast import (
    JsonDef,
    MatcherListDef,
    MethodFetch,
    MethodRest,
    Module,
    PlaceholderSpec,
    PlaceholderTemplate,
    ResultAliasDef,
    ResultVariantDef,
    StructBase,
)
from ssc_codegen.ast.struct import RequestHttp
from ssc_codegen.naming import (
    python_json_projector_name,
    to_pascal_case,
    to_snake_case,
)
from ssc_codegen.request_spec import parse_json_template
from ssc_codegen.targets.python.http_libs.base import HttpLibStrategy
from ssc_codegen.traversal.context import WalkContext
from ssc_codegen.traversal.utils import (
    find_enclosing_module,
    module_has_fetch,
    module_has_html_struct,
    module_has_rest,
    module_uses_http,
)


def format_docstring(doc: str, indent: str = "") -> list[str]:
    """Format a docstring as an indented triple-quoted Python string literal.

    Args:
        doc (str): Raw or cleaned docstring text.
        indent (str): Indentation prefix for each emitted line.

    Returns:
        list[str]: Formatted Python docstring lines, or an empty list if `doc` is empty.
    """
    cleaned = inspect.cleandoc(doc)
    if not cleaned:
        return []
    escaped = cleaned.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    if "\n" not in escaped:
        if escaped.endswith('"') and not escaped.endswith('\\"'):
            escaped = escaped[:-1] + '\\"'
        return [f'{indent}"""{escaped}"""']
    raw_lines = escaped.splitlines()
    if raw_lines[-1].endswith('"') and not raw_lines[-1].endswith('\\"'):
        raw_lines[-1] = raw_lines[-1][:-1] + '\\"'
    lines = [f'{indent}"""']
    for line in raw_lines:
        lines.append(f"{indent}{line}" if line else "")
    lines.append(f'{indent}"""')
    return lines


# ===========================================================================
# Placeholder / Template rendering (pure functions)
# ===========================================================================

_STYLE_SEPARATOR: dict[str, str] = {"csv": ",", "pipe": "|", "space": " "}

PH_PY_TYPES = {"str": "str", "int": "int", "float": "float", "bool": "bool"}


def _escape_fstring(tmpl: PlaceholderTemplate) -> str:
    """Escape literal braces and interpolate placeholders as a Python f-string body.

    Args:
        tmpl (PlaceholderTemplate): Parsed template containing literal segments and placeholders.

    Returns:
        str: Unquoted f-string body with `{}` doubled and placeholders interpolated.
    """
    result: list[str] = []
    for part in tmpl.parts:
        if isinstance(part, PlaceholderSpec):
            result.append("{" + part.name + "}")
        else:
            for ch in part:
                result.append(ch * 2 if ch in "{}" else ch)
    return "".join(result)


def render_value(tmpl: PlaceholderTemplate) -> str:
    """Render a `PlaceholderTemplate` as a Python expression.

    Args:
        tmpl (PlaceholderTemplate): Template to render.

    Returns:
        str: Python expression string representing the template value.
    """
    if ph := tmpl.single_placeholder():
        if ph.is_array and ph.style in ("csv", "pipe", "space"):
            sep = _STYLE_SEPARATOR[ph.style or "csv"]
            join_expr = f"{sep!r}.join(str(_x) for _x in {ph.name})"
            if ph.is_optional:
                return f"({join_expr} if {ph.name} is not None else None)"
            return join_expr
        return ph.name
    if tmpl.has_placeholders:
        return f'f"{_escape_fstring(tmpl)}"'
    return repr(tmpl.source)


def render_dict(d: dict[str, PlaceholderTemplate]) -> str:
    """Render a mapping of `PlaceholderTemplate` values as a Python dict literal.

    Args:
        d (dict[str, PlaceholderTemplate]): Key-to-template mapping (headers, cookies, or params).

    Returns:
        str: Python dictionary literal expression.
    """
    if not d:
        return "{}"
    items: list[str] = []
    for k, v in d.items():
        ph = v.single_placeholder()
        effective_key = (
            f"{k}[]"
            if (ph is not None and ph.is_array and ph.style == "bracket")
            else k
        )
        items.append(f"{effective_key!r}: {render_value(v)}")
    return "{" + ", ".join(items) + "}"


def render_json_body(tmpl: PlaceholderTemplate) -> str:
    """Render a JSON body template as a structured Python literal expression.

    Args:
        tmpl (PlaceholderTemplate): JSON body template with optional placeholders.

    Returns:
        str: Python dict/list/scalar expression suitable for the `json=` request keyword.
    """
    def _emit(v: object) -> str:
        if isinstance(v, PlaceholderSpec):
            return v.name
        if isinstance(v, PlaceholderTemplate):
            return render_value(v)
        if v is None:
            return "None"
        if isinstance(v, bool):
            return "True" if v else "False"
        if isinstance(v, (int, float)):
            return repr(v)
        if isinstance(v, str):
            return repr(v)
        if isinstance(v, dict):
            items = ", ".join(f"{k!r}: {_emit(val)}" for k, val in v.items())
            return "{" + items + "}"
        if isinstance(v, list):
            items = ", ".join(_emit(x) for x in v)
            return "[" + items + "]"
        raise TypeError(f"unsupported JSON body element: {type(v).__name__}")

    return _emit(parse_json_template(tmpl))


def render_body(spec: RequestHttp) -> tuple[str, str] | None:
    """Render the request body option for a `RequestHttp` specification.

    Args:
        spec (RequestHttp): HTTP request specification AST node.

    Returns:
        tuple[str, str] | None: `(keyword_name, value_expr)` pair (`"json"` or `"data"`),
        or `None` when the request has no body.
    """
    if spec.body_kind == "empty" or spec.payload is None:
        return None
    if spec.body_kind == "json":
        assert isinstance(spec.payload, PlaceholderTemplate)
        return ("json", render_json_body(spec.payload))
    if spec.body_kind == "form":
        assert isinstance(spec.payload, dict)
        return ("data", render_dict(spec.payload))
    assert isinstance(spec.payload, PlaceholderTemplate)
    return ("data", render_value(spec.payload))


# ===========================================================================
# Condition lambda rendering
# ===========================================================================


def _py_path_expr(body_var: str, path: str) -> str:
    """Build a Python dictionary/index traversal expression for a dot-path.

    Args:
        body_var (str): Variable name holding the parsed response body.
        path (str): Dot-separated path string.

    Returns:
        str: Python expression accessing the nested path on `body_var`.
    """
    expr = body_var
    for seg in path.split("."):
        if seg.isdigit():
            expr += f"[{seg}]"
        else:
            expr += f".get({seg!r})"
    return expr


def render_py_condition_lambda(
    required_keys: list[str], conditions: dict[str, object]
) -> str | None:
    """Render an error-matcher predicate lambda checking required keys and field values.

    Args:
        required_keys (list[str]): Top-level keys that must exist in the JSON body.
        conditions (dict[str, object]): Dot-paths mapped to expected literal values.

    Returns:
        str | None: Python `lambda _b: ...` expression, or `None` if no checks apply.
    """
    parts: list[str] = []
    for key in required_keys:
        parts.append(f"{key!r} in _b")
    for path, value in conditions.items():
        lhs = _py_path_expr("_b", path)
        if isinstance(value, bool):
            parts.append(f"{lhs} is {value}")
        elif value is None:
            parts.append(f"{lhs} is None")
        elif isinstance(value, (int, float)):
            parts.append(f"{lhs} == {value}")
        else:
            parts.append(f"{lhs} == {value!r}")
    if not parts:
        return None
    return f"lambda _b: {' and '.join(parts)}"


# ===========================================================================
# Runtime export names
# ===========================================================================

_RUNTIME_HTML_EXPORT_NAMES: list[str] = [
    "UNMATCHED_TABLE_ROW",
    "UnmatchedTableRow",
]

_RUNTIME_REST_EXPORT_NAMES: list[str] = [
    "Ok",
    "Err",
    "UnknownErr",
    "TransportErr",
    "ErrMatcher",
    "ssc_rest_call",
    "ssc_rest_call_async",
]

_RUNTIME_JSON_EXPORT_NAMES: list[str] = [
    "SscJsonError",
    "SscJsonPathError",
    "SscJsonFieldMissingError",
    "SscJsonSchemaError",
    "ssc_expect_dict",
    "ssc_expect_list",
    "ssc_resolve_dotpath",
    "ssc_json_req",
    "ssc_json_req_path",
]

# Always exported regardless of module type so consumer code can
# ``except SscAssertionError`` / ``except SscRegexError`` unconditionally —
# even if the current module has no ``assert {}`` / ``re`` blocks.
# Matches the always-export strategy for runtime helpers (catch stability
# over minimal-imports).
_RUNTIME_ALWAYS_EXPORT_NAMES: list[str] = [
    "SscAssertionError",
    "SscRegexError",
]


def runtime_export_names(
    module: Module,
    *,
    need_fallback: bool = False,
    http_io: str = "both",
    http_strategy: HttpLibStrategy | None = None,
) -> list[str]:
    """Compute the list of names the parser file must import from the runtime.

    Args:
        module (Module): AST module being processed.
        need_fallback (bool): Whether fallback HTML parsing constants are required.
        http_io (str): HTTP method generation mode ("both", "sync", "async").
            Defaults to "both".
        http_strategy (HttpLibStrategy | None): Optional HTTP transport strategy
            used to filter fetch helper exports (`ssc_fetch`, `ssc_fetch_async`).

    Returns:
        list[str]: List of symbol names to import from the shared runtime module.
    """
    names: list[str] = list(_RUNTIME_ALWAYS_EXPORT_NAMES)
    if module_has_html_struct(module):
        names.extend(_RUNTIME_HTML_EXPORT_NAMES)
        if need_fallback:
            names.append("FALLBACK_HTML_STR")
    if module_uses_http(module):
        names.append("ssc_merge_kwargs")
    if module_has_rest(module):
        rest_names = [
            "Ok",
            "Err",
            "UnknownErr",
            "TransportErr",
            "ErrMatcher",
        ]
        if http_io in ("both", "sync"):
            rest_names.append("ssc_rest_call")
        if http_io in ("both", "async"):
            rest_names.append("ssc_rest_call_async")
        names.extend(rest_names)
    if module_has_fetch(module):
        if http_strategy is not None:
            if http_strategy.async_fetch_delegates_to_sync:
                names.append("ssc_fetch")
            else:
                if (
                    http_io in ("both", "sync")
                    and http_strategy.supports_sync_fetch
                ):
                    names.append("ssc_fetch")
                if http_io in ("both", "async"):
                    names.append("ssc_fetch_async")
        else:
            if http_io in ("both", "sync"):
                names.append("ssc_fetch")
            if http_io in ("both", "async"):
                names.append("ssc_fetch_async")
    if any(isinstance(n, JsonDef) for n in module.body):
        names.extend(_RUNTIME_JSON_EXPORT_NAMES)
    return names


# ===========================================================================
# Placeholder parameter signature
# ===========================================================================


def placeholder_params(http: RequestHttp) -> str:
    """Format keyword-only parameter declarations for request placeholders.

    Args:
        http (RequestHttp): HTTP request specification containing placeholders.

    Returns:
        str: Leading `, *, ...` parameter signature fragment, or `""` if none.
    """
    if not http.placeholders:
        return ""
    parts: list[str] = []
    for ph in sorted(http.placeholders, key=lambda p: p.is_optional):
        t = PH_PY_TYPES[ph.type_name]
        if ph.is_array:
            t = f"List[{t}]"
        parts.append(
            f"{ph.name}: Optional[{t}] = None"
            if ph.is_optional
            else f"{ph.name}: {t}"
        )
    return ", *, " + ", ".join(parts)


def placeholder_args(http: RequestHttp) -> str:
    """Build a keyword-argument forwarding string for delegating between fetch variants.

    Args:
        http (RequestHttp): HTTP request specification containing placeholders.

    Returns:
        str: Comma-separated `name=name` pairs for all request placeholders.
    """
    return ", ".join(f"{ph.name}={ph.name}" for ph in http.placeholders)


def _render_dsl_kw(spec: RequestHttp) -> str:
    """Render keyword argument unpacking expression for DSL request options.

    Args:
        spec (RequestHttp): HTTP request specification AST node.

    Returns:
        str: Unpacked keyword argument expression (`**kwargs` or `**ssc_merge_kwargs(...)`).
    """
    entries: list[str] = []
    for attr in ("headers", "cookies", "params"):
        d = getattr(spec, attr)
        if d:
            entries.append(f"{attr!r}: {render_dict(d)}")
    body_result = render_body(spec)
    if body_result:
        entries.append(f"{body_result[0]!r}: {body_result[1]}")
    if not entries:
        return "**kwargs"
    return f"**ssc_merge_kwargs({{{', '.join(entries)}}}, kwargs)"


# ===========================================================================
# Emit functions (called by PythonVisitor)
# ===========================================================================


def emit_method_fetch(
    node: MethodFetch, ctx: WalkContext, http: HttpLibStrategy
) -> list[str]:
    """Emit Python `fetch` and/or `async_fetch` classmethods for a `MethodFetch` node.

    Args:
        node (MethodFetch): AST node describing the document fetch request.
        ctx (WalkContext): Traversal context providing indentation and metadata.
        http (HttpLibStrategy): Active Python HTTP transport strategy.

    Returns:
        list[str]: Generated Python method lines.
    """
    spec = node.http_request.with_renamed_placeholders(to_snake_case)
    assert node.parent is not None
    struct_name = to_pascal_case(cast(StructBase, node.parent).name)
    suffix = ("_" + to_snake_case(node.name)) if node.name else ""
    ph_params = placeholder_params(spec)
    ph_kwargs = placeholder_args(spec)
    http_io = ctx.meta.get("http_io", "both")

    i1 = ctx.indent
    i2 = i1 + ctx.indent_char
    i3 = i2 + ctx.indent_char

    doc_lines = format_docstring(node.doc, i2) if node.doc else []
    kw_expr = _render_dsl_kw(spec)

    extra_call_args: list[str] = []
    if node.response_path:
        extra_call_args.append(f"{i3}response_path={node.response_path!r},")
    if node.response_join:
        extra_call_args.append(f"{i3}response_join={node.response_join!r},")

    def _sync_fetch_lines(fn_name: str) -> list[str]:
        return [
            f"{i1}@classmethod",
            f'{i1}def {fn_name}{suffix}(cls, client: {http.sync_client_type}{ph_params}, **kwargs: Any) -> "{struct_name}":',
            *doc_lines,
            f"{i2}return cls(ssc_fetch(",
            f"{i3}client, {spec.method!r}, {render_value(spec.url)},",
            *extra_call_args,
            f"{i3}{kw_expr},",
            f"{i2}))",
        ]

    lines: list[str] = []

    # --- sync fetch (httpx, requests) -------------------------------------
    has_sync = http_io in ("both", "sync") and http.supports_sync_fetch
    if has_sync:
        lines.extend(_sync_fetch_lines("fetch"))

    # When requests + async only, we need a private sync implementation (_fetch)
    # for async_fetch to delegate to via asyncio.to_thread.
    needs_private_sync = (
        http_io == "async" and http.async_fetch_delegates_to_sync
    )
    if needs_private_sync:
        lines.extend(_sync_fetch_lines("_fetch"))

    # --- async_fetch ------------------------------------------------------
    if http_io in ("both", "async"):
        if lines:
            lines.append("")
        lines.append(f"{i1}@classmethod")
        lines.append(
            f'{i1}async def async_fetch{suffix}(cls, client: {http.async_client_type}{ph_params}, **kwargs: Any) -> "{struct_name}":'
        )
        lines.extend(doc_lines)
        if http.async_fetch_delegates_to_sync:
            # requests: no native async — run the sync fetch in a worker thread
            # via asyncio.to_thread (non-blocking, yields control to the loop).
            if ph_kwargs:
                to_thread_args = f"client, {ph_kwargs}, **kwargs"
            else:
                to_thread_args = "client, **kwargs"
            lines.append(f"{i2}import asyncio")
            target_method = "cls._fetch" if needs_private_sync else "cls.fetch"
            lines.append(
                f"{i2}return await asyncio.to_thread("
                f"{target_method}{suffix}, {to_thread_args})"
            )
        else:
            lines.extend(
                [
                    f"{i2}return cls(await ssc_fetch_async(",
                    f"{i3}client, {spec.method!r}, {render_value(spec.url)},",
                    *extra_call_args,
                    f"{i3}{kw_expr},",
                    f"{i2}))",
                ]
            )
    return lines


def emit_method_rest(
    node: MethodRest, ctx: WalkContext, http: HttpLibStrategy
) -> list[str]:
    """Emit Python sync and/or async REST endpoint classmethods for a `MethodRest` node.

    Args:
        node (MethodRest): AST node describing the REST endpoint request.
        ctx (WalkContext): Traversal context providing indentation and metadata.
        http (HttpLibStrategy): Active Python HTTP transport strategy.

    Returns:
        list[str]: Generated Python method lines.
    """
    spec = node.http_request.with_renamed_placeholders(to_snake_case)
    struct = node.parent
    assert isinstance(struct, StructBase)
    method_name = to_snake_case(node.name) if node.name else "fetch"
    ret_type = node.result_alias_name or "None"
    ph_params = placeholder_params(spec)
    matchers_var = f"{to_snake_case(struct.name).upper()}_MATCHERS"
    http_io = ctx.meta.get("http_io", "both")

    i1 = ctx.indent
    i2 = i1 + ctx.indent_char
    i3 = i2 + ctx.indent_char

    doc_lines = format_docstring(node.doc, i2) if node.doc else []
    kw_expr = _render_dsl_kw(spec)

    value_kwarg: list[str] = []
    module = find_enclosing_module(node)
    has_response_schema = False
    if node.response_schema and isinstance(module, Module):
        has_response_schema = any(
            isinstance(n, JsonDef) and n.name == node.response_schema
            for n in module.body
        )

    if node.response_path:
        accessor = "".join(f"[{p!r}]" for p in node.response_path.split("."))
        if has_response_schema:
            value_kwarg = [
                f"{i3}value_fn=lambda _b: {python_json_projector_name(node.response_schema)}(_b{accessor}),"
            ]
        else:
            value_kwarg = [f"{i3}value_fn=lambda _b: _b{accessor},"]
    elif not node.response_schema:
        value_kwarg = [f"{i3}value_fn=lambda _: None,"]
    elif has_response_schema:
        value_kwarg = [
            f"{i3}value_fn=lambda _b: {python_json_projector_name(node.response_schema)}(_b),"
        ]

    def _body(fn_name: str, await_kw: str) -> list[str]:
        body: list[str] = list(doc_lines)
        body.append(f"{i2}return cast({ret_type}, {await_kw}{fn_name}(")
        body.append(
            f"{i3}client, {matchers_var}, {spec.method!r},"
            f" {render_value(spec.url)},"
        )
        body.extend(value_kwarg)
        body.append(f"{i3}{kw_expr},")
        body.append(f"{i2}))")
        return body

    lines: list[str] = []
    if http_io in ("both", "sync"):
        lines.append(f"{i1}@classmethod")
        lines.append(
            f"{i1}def {method_name}(cls, client: {http.sync_client_type}{ph_params}, **kwargs: Any) -> {ret_type}:"
        )
        lines.extend(_body("ssc_rest_call", ""))

    if http_io in ("both", "async"):
        if lines:
            lines.append("")
        lines.append(f"{i1}@classmethod")
        lines.append(
            f"{i1}async def async_{method_name}(cls, client: {http.async_client_type}{ph_params}, **kwargs: Any) -> {ret_type}:"
        )
        lines.extend(_body("ssc_rest_call_async", "await "))
    return lines


def emit_result_variant_def(node: ResultVariantDef) -> list[str]:
    """Emit a frozen `@dataclass` error subclass for a `ResultVariantDef` node.

    Args:
        node (ResultVariantDef): Error variant AST node.

    Returns:
        list[str]: Generated Python class definition lines.
    """
    if node.schema_name:
        base = f"{to_pascal_case(node.schema_name)}Json"
        value_type = f"List[{base}]" if node.schema_is_array else base
    else:
        value_type = "Any"
    return [
        "@dataclass(frozen=True)",
        f"class {node.name}(Err[{value_type}]):",
        f"    status: Literal[{node.status}] = {node.status}",
        "",
    ]


def emit_result_alias_def(node: ResultAliasDef) -> list[str]:
    """Emit a `Union[Ok[...], ...]` type alias for a `ResultAliasDef` node.

    Args:
        node (ResultAliasDef): Result union alias AST node.

    Returns:
        list[str]: Generated Python type alias lines.
    """
    if node.response_schema:
        base = f"{to_pascal_case(node.response_schema)}Json"
        ok_type = f"List[{base}]" if node.response_is_array else base
    else:
        ok_type = "None"
    parts = [
        f"Ok[{ok_type}]",
        *node.err_variants,
        "UnknownErr",
        "TransportErr",
    ]
    return [f"{node.name} = Union[{', '.join(parts)}]", ""]


def emit_matcher_list_def(node: MatcherListDef) -> list[str]:
    """Emit the `<STRUCT>_MATCHERS` list of `ErrMatcher` entries for a REST struct.

    Args:
        node (MatcherListDef): Matcher list AST node.

    Returns:
        list[str]: Generated Python matcher list definition lines.
    """
    var = f"{to_snake_case(node.struct_name).upper()}_MATCHERS"
    lines = [f"{var}: List[ErrMatcher] = ["]
    module = find_enclosing_module(node)
    definitions = (
        {n.name: n for n in module.body if isinstance(n, JsonDef)}
        if isinstance(module, Module)
        else {}
    )
    for e in node.entries:
        check = render_py_condition_lambda(e.required_keys, e.conditions)
        check_arg = check if check else "None"
        factory = e.factory_name
        if e.error_schema and e.error_schema in definitions:
            factory = (
                f"lambda headers, value: {e.factory_name}(headers=headers, "
                f"value={python_json_projector_name(e.error_schema)}(value))"
            )
        lines.append(f"    ErrMatcher({e.status}, {check_arg}, {factory}),")
    lines.append("]")
    lines.append("")
    return lines
