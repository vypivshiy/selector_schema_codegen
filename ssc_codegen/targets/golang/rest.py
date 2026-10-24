"""Go REST codegen — pure functions for MethodRest, MethodFetch,
ResultVariantDef, ResultAliasDef, MatcherListDef AST nodes.

Adapts the REST/fetch pattern to Go idioms:

- Each REST method returns ``(*T, error)``, ``([]T, error)``, or ``(struct{}, error)``
  by delegating to ``sscRestCallValue[T]``, ``sscRestCallSlice[T]``, or ``sscRestCallVoid``.
- Each ``@error`` generates a struct implementing ``error``.
- ``UnknownErr`` and ``TransportErr`` live in ``sscgen_runtime.go``.
"""

from __future__ import annotations

from ssc_codegen.ast import (
    MatcherListDef,
    MethodFetch,
    MethodRest,
    PlaceholderSpec,
    PlaceholderTemplate,
    ResultAliasDef,
    ResultVariantDef,
    Struct,
    StructBase,
)
from ssc_codegen.ast import (
    StructType as ST,
)
from ssc_codegen.ast.struct import RequestHttp
from ssc_codegen.naming import to_camel_case, to_pascal_case, to_snake_case
from ssc_codegen.request_spec import parse_json_template
from ssc_codegen.targets.golang.http_libs.base import GoHttpLibStrategy
from ssc_codegen.targets.golang.literals import go_str as _go_str
from ssc_codegen.traversal.context import WalkContext

# Go placeholder type mapping.
_GO_PH_TYPES = {
    "str": "string",
    "int": "int64",
    "float": "float64",
    "bool": "bool",
}


# ===========================================================================
# Placeholder / Template rendering
# ===========================================================================


def _go_fmt_placeholder(ph: PlaceholderSpec) -> str:
    """Return the `fmt.Sprintf` format verb for a placeholder specification.

    Args:
        ph (PlaceholderSpec): Placeholder metadata to inspect.

    Returns:
        str: Go `fmt.Sprintf` verb (`"%d"`, `"%f"`, `"%t"`, or `"%s"`).
    """
    if ph.type_name == "int":
        return "%d"
    if ph.type_name == "float":
        return "%f"
    if ph.type_name == "bool":
        return "%t"
    return "%s"


def render_url(tmpl: PlaceholderTemplate) -> str:
    """Render a `PlaceholderTemplate` as a Go string expression.

    Args:
        tmpl (PlaceholderTemplate): Template containing literal text and/or placeholders.

    Returns:
        str: Go string literal or `fmt.Sprintf(...)` expression.
    """
    if not tmpl.has_placeholders:
        return _go_str(tmpl.source)

    fmt_str = ""
    args: list[str] = []
    for part in tmpl.parts:
        if isinstance(part, PlaceholderSpec):
            fmt_str += _go_fmt_placeholder(part)
            args.append(to_camel_case(part.name))
        else:
            fmt_str += part.replace("%", "%%")
    return f"fmt.Sprintf({_go_str(fmt_str)}, {', '.join(args)})"


def render_body_json(tmpl: PlaceholderTemplate) -> str:
    """Render a JSON body template through `stdJSONBody` for structured serialization.

    Args:
        tmpl (PlaceholderTemplate): JSON body template with optional placeholders.

    Returns:
        str: Go `stdJSONBody(...)` invocation expression.
    """

    def emit(value: object) -> str:
        if isinstance(value, PlaceholderSpec):
            return to_camel_case(value.name)
        if isinstance(value, PlaceholderTemplate):
            return render_url(value)
        if value is None:
            return "nil"
        if isinstance(value, bool):
            return str(value).lower()
        if isinstance(value, (int, float)):
            return repr(value)
        if isinstance(value, str):
            return _go_str(value)
        if isinstance(value, list):
            return "[]any{" + ", ".join(emit(item) for item in value) + "}"
        if isinstance(value, dict):
            items = ", ".join(
                f"{_go_str(str(key))}: {emit(item)}"
                for key, item in value.items()
            )
            return "map[string]any{" + items + "}"
        raise TypeError(
            f"unsupported JSON body element: {type(value).__name__}"
        )

    return f"stdJSONBody({emit(parse_json_template(tmpl))})"


def render_url_values(d: dict[str, PlaceholderTemplate]) -> str:
    """Render a dictionary of templates as a Go `url.Values{...}.Encode()` expression.

    Args:
        d (dict[str, PlaceholderTemplate]): Key-value template mapping for query params or form fields.

    Returns:
        str: Go expression evaluating to an RFC 3986 URL-encoded string.
    """
    if not d:
        return '""'
    if any(
        (ph := tmpl.single_placeholder()) is not None and ph.is_array
        for tmpl in d.values()
    ):
        lines = ["func() string {", "_values := url.Values{}"]
        for key, tmpl in d.items():
            ph = tmpl.single_placeholder()
            if ph is None or not ph.is_array:
                lines.append(
                    f"_values.Set({_go_str(key)}, fmt.Sprint({render_url(tmpl)}))"
                )
                continue
            name = to_camel_case(ph.name)
            effective_key = f"{key}[]" if ph.style == "bracket" else key
            if ph.style in ("csv", "pipe", "space"):
                separator = {"csv": ",", "pipe": "|", "space": " "}[ph.style]
                parts_name = f"_{name}Parts"
                lines.extend(
                    [
                        f"{parts_name} := make([]string, len({name}))",
                        f"for _i, _value := range {name} {{",
                        f"{parts_name}[_i] = fmt.Sprint(_value)",
                        "}",
                        f"_values.Set({_go_str(effective_key)}, strings.Join({parts_name}, {_go_str(separator)}))",
                    ]
                )
            else:
                lines.extend(
                    [
                        f"for _, _value := range {name} {{",
                        f"_values.Add({_go_str(effective_key)}, fmt.Sprint(_value))",
                        "}",
                    ]
                )
        lines.extend(["return _values.Encode()", "}()"])
        return "\n".join(lines)
    parts: list[str] = []
    for k, tmpl in d.items():
        val = (
            render_url(tmpl) if tmpl.has_placeholders else _go_str(tmpl.source)
        )
        parts.append(f"{_go_str(k)}: []string{{{val}}}")
    return f"url.Values{{{', '.join(parts)}}}.Encode()"


def render_form_body(body: dict[str, PlaceholderTemplate]) -> str:
    """Render an `application/x-www-form-urlencoded` body via `url.Values.Encode()`.

    Args:
        body (dict[str, PlaceholderTemplate]): Form field templates keyed by field name.

    Returns:
        str: Go expression encoding the form fields.
    """
    return render_url_values(body)


def render_full_url(spec: RequestHttp) -> str:
    """Render the request URL expression with encoded query parameters appended.

    Args:
        spec (RequestHttp): HTTP request specification AST node.

    Returns:
        str: Go string expression for the full request URL.
    """
    base = render_url(spec.url)
    if not spec.params:
        return base
    return f'({base} + "?" + {render_url_values(spec.params)})'


def _render_cookie_pairs(
    spec: RequestHttp,
) -> list[tuple[str, str]]:
    """Render each request cookie as a `(key_expr, value_expr)` pair of Go expressions.

    Args:
        spec (RequestHttp): HTTP request specification AST node.

    Returns:
        list[tuple[str, str]]: Ordered list of Go key and value expression pairs.
    """
    pairs: list[tuple[str, str]] = []
    for k, tmpl in spec.cookies.items():
        key = _go_str(k)
        value = (
            render_url(tmpl) if tmpl.has_placeholders else _go_str(tmpl.source)
        )
        pairs.append((key, value))
    return pairs


def _url_values_imports(d: dict[str, PlaceholderTemplate]) -> set[str]:
    """Determine Go standard library imports required by `render_url_values(d)`.

    Args:
        d (dict[str, PlaceholderTemplate]): Key-value template mapping for query or form values.

    Returns:
        set[str]: Subset of `{"fmt", "net/url", "strings"}` required by `render_url_values`.
    """
    if not d:
        return set()
    imports: set[str] = {"net/url"}
    has_array = any(
        (ph := tmpl.single_placeholder()) is not None and ph.is_array
        for tmpl in d.values()
    )
    if has_array:
        imports.add("fmt")
        for tmpl in d.values():
            ph = tmpl.single_placeholder()
            if (
                ph is not None
                and ph.is_array
                and ph.style in ("csv", "pipe", "space")
            ):
                imports.add("strings")
    elif any(tmpl.has_placeholders for tmpl in d.values()):
        imports.add("fmt")
    return imports


def _json_tree_uses_fmt(value: object) -> bool:
    """Check whether a parsed JSON template tree requires `fmt.Sprintf`.

    Args:
        value (object): Parsed JSON template node from `parse_json_template`.

    Returns:
        bool: `True` if any descendant is a composite `PlaceholderTemplate` with placeholders.
    """
    if isinstance(value, PlaceholderTemplate):
        return value.has_placeholders
    if isinstance(value, list):
        return any(_json_tree_uses_fmt(item) for item in value)
    if isinstance(value, dict):
        return any(_json_tree_uses_fmt(item) for item in value.values())
    return False


def go_method_imports(spec: RequestHttp) -> set[str]:
    """Determine Go standard library imports required by a generated HTTP method.

    Args:
        spec (RequestHttp): HTTP request specification AST node.

    Returns:
        set[str]: Required Go standard library package paths (subset of
        `{"fmt", "net/url", "strings"}`).
    """
    imports: set[str] = set()
    if spec.url.has_placeholders:
        imports.add("fmt")
    if any(tmpl.has_placeholders for tmpl in spec.headers.values()):
        imports.add("fmt")
    if any(tmpl.has_placeholders for tmpl in spec.cookies.values()):
        imports.add("fmt")
    imports.update(_url_values_imports(spec.params))

    has_body = (
        spec.body_kind not in ("empty", None) and spec.payload is not None
    )
    if has_body:
        if isinstance(spec.payload, dict):
            imports.update(_url_values_imports(spec.payload))
        elif isinstance(spec.payload, PlaceholderTemplate):
            if spec.body_kind == "json":
                if _json_tree_uses_fmt(parse_json_template(spec.payload)):
                    imports.add("fmt")
            elif spec.payload.has_placeholders:
                imports.add("fmt")
    return imports


# ===========================================================================
# Placeholder parameter signature
# ===========================================================================


def placeholder_params(spec: RequestHttp) -> str:
    """Generate Go function parameter declarations for request placeholders.

    Args:
        spec (RequestHttp): HTTP request specification containing placeholders.

    Returns:
        str: Leading `, <name> <type>...` parameter list fragment, or `""` if none.
    """
    if not spec.placeholders:
        return ""
    parts: list[str] = []
    for ph in sorted(spec.placeholders, key=lambda p: p.is_optional):
        go_type = _GO_PH_TYPES.get(ph.type_name, "string")
        if ph.is_array:
            go_type = "[]" + go_type
        name = to_camel_case(ph.name)
        parts.append(f"{name} {go_type}")
    return ", " + ", ".join(parts)


# ===========================================================================
# Emit functions
# ===========================================================================


def _build_opts_inline(spec: RequestHttp) -> str:
    """Build an inline `&sscReqOpts{...}` pointer expression (or `"nil"`).

    Args:
        spec (RequestHttp): HTTP request specification AST node.

    Returns:
        str: Go expression for the `dslOpts` argument (`"&sscReqOpts{...}"` or `"nil"`).
    """
    has_headers = bool(spec.headers)
    has_cookies = bool(spec.cookies)
    has_body = (
        spec.body_kind not in ("empty", None) and spec.payload is not None
    )

    if not has_headers and not has_body and not has_cookies:
        return "nil"

    fields: list[str] = []
    if has_body:
        payload = spec.payload
        if isinstance(payload, PlaceholderTemplate):
            body_expr = (
                render_body_json(payload)
                if spec.body_kind == "json"
                else render_url(payload)
            )
            fields.append(f"Body: {body_expr}")
        elif isinstance(payload, dict):
            # form-urlencoded body — url.Values{...}.Encode()
            fields.append(f"Body: {render_form_body(payload)}")
    if has_headers:
        parts = []
        for k, tmpl in spec.headers.items():
            if tmpl.has_placeholders:
                val = render_url(tmpl)
            else:
                val = _go_str(tmpl.source)
            parts.append(f"{_go_str(k)}: []string{{{val}}}")
        fields.append(f"Headers: sscHeaders{{{', '.join(parts)}}}")
    if has_cookies:
        parts = [f"{k}: []string{{{v}}}" for k, v in _render_cookie_pairs(spec)]
        fields.append(f"Cookies: sscHeaders{{{', '.join(parts)}}}")
    return f"&sscReqOpts{{{', '.join(fields)}}}"


def emit_method_fetch(
    node: MethodFetch,
    ctx: WalkContext,
    http: GoHttpLibStrategy,
) -> list[str]:
    """Emit a Go HTTP-entry constructor function for a `MethodFetch` node.

    Delegates HTTP execution, functional option merging, status checking, and
    `response_path` / `response_join` extraction to `sscFetchHTML`.

    Args:
        node (MethodFetch): AST node describing the document fetch request.
        ctx (WalkContext): Traversal context providing indentation and metadata.
        http (GoHttpLibStrategy): Active Go HTTP transport strategy.

    Returns:
        list[str]: Generated Go function lines.
    """
    spec = node.http_request.with_renamed_placeholders(to_camel_case)
    struct = node.parent
    assert isinstance(struct, StructBase)
    name = to_pascal_case(struct.name)
    method_suffix = to_pascal_case(node.name) if node.name else "Fetch"
    func_name = f"New{name}{method_suffix}"
    ph_params = placeholder_params(spec)
    url_expr = render_full_url(spec)
    path_expr = _go_str(node.response_path) if node.response_path else '""'
    join_expr = _go_str(node.response_join) if node.response_join else '""'
    opts_expr = _build_opts_inline(spec)

    i1 = ctx.indent
    i2 = i1 + ctx.indent_char

    lines: list[str] = []
    doc = getattr(node, "doc", "")
    if doc:
        for doc_line in doc.splitlines():
            lines.append(f"{i1}// {doc_line}" if doc_line else f"{i1}//")

    lines.extend(
        [
            f"{i1}func {func_name}(ctx context.Context, client {http.client_type}{ph_params}, opts ...sscReqOpt) (*{name}, error) {{",
            f"{i2}body, err := sscFetchHTML(ctx, client, {_go_str(name)}, {_go_str(spec.method)}, {url_expr}, {path_expr}, {join_expr}, {opts_expr}, opts...)",
            f"{i2}if err != nil {{",
            f"{i2}\treturn nil, err",
            f"{i2}}}",
        ]
    )

    # Construct parser from body.
    # (raw)struct constructor returns a single value (*Name), wrapper
    # signature is (*Name, error) → must add `, nil`. HTML constructor
    # already returns (*Name, error) so naked tuple pass-through works.
    if isinstance(struct, Struct) and struct.type == ST.RAW:
        lines.append(f"{i2}return New{name}(body), nil")
    else:
        lines.append(f"{i2}return New{name}(body)")
    lines.append(f"{i1}}}")
    lines.append("")
    return lines


def emit_method_rest(
    node: MethodRest,
    ctx: WalkContext,
    http: GoHttpLibStrategy,
    rcv: str,
) -> list[str]:
    """Emit a Go REST receiver method that delegates to generic runtime helpers.

    Args:
        node (MethodRest): AST node describing the REST endpoint request.
        ctx (WalkContext): Traversal context providing indentation and metadata.
        http (GoHttpLibStrategy): Active Go HTTP transport strategy.
        rcv (str): Receiver variable identifier for the enclosing struct.

    Returns:
        list[str]: Generated Go method lines.
    """
    spec = node.http_request.with_renamed_placeholders(to_camel_case)
    struct = node.parent
    assert isinstance(struct, StructBase)
    name = to_pascal_case(struct.name)
    method_name = to_pascal_case(node.name) if node.name else "Fetch"
    ph_params = placeholder_params(spec)
    matchers_var = f"{to_snake_case(struct.name)}Matchers"
    url_expr = render_full_url(spec)
    opts_expr = _build_opts_inline(spec)
    path_expr = _go_str(node.response_path) if node.response_path else '""'

    i1 = ctx.indent
    i2 = i1 + ctx.indent_char

    lines: list[str] = []
    if node.doc:
        for doc_line in node.doc.splitlines():
            lines.append(f"{i1}// {doc_line}" if doc_line else f"{i1}//")

    if node.response_schema:
        schema_go = f"{to_pascal_case(node.response_schema)}Json"
        if getattr(node, "response_is_array", False):
            ret_type = f"[]{schema_go}"
            call_expr = (
                f"sscRestCallSlice[{schema_go}](client, {matchers_var}, "
                f"{_go_str(spec.method)}, {url_expr}, {path_expr}, {opts_expr}, opts...)"
            )
        else:
            ret_type = f"*{schema_go}"
            call_expr = (
                f"sscRestCallValue[{schema_go}](client, {matchers_var}, "
                f"{_go_str(spec.method)}, {url_expr}, {path_expr}, {opts_expr}, opts...)"
            )
    else:
        ret_type = "struct{}"
        call_expr = (
            f"sscRestCallVoid(client, {matchers_var}, "
            f"{_go_str(spec.method)}, {url_expr}, {opts_expr}, opts...)"
        )

    lines.append(
        f"{i1}func ({rcv} {name}) {method_name}(client {http.client_type}{ph_params}, opts ...sscReqOpt) ({ret_type}, error) {{"
    )
    lines.append(f"{i2}return {call_expr}")
    lines.append(f"{i1}}}")
    lines.append("")
    return lines


def emit_result_variant_def(node: ResultVariantDef) -> list[str]:
    """Emit a standalone `@error` variant as a Go struct implementing `error`.

    Args:
        node (ResultVariantDef): Error variant AST node.

    Returns:
        list[str]: Generated Go struct and `Error()` method lines.
    """
    lines: list[str] = []
    if node.schema_name:
        body_type = f"{to_pascal_case(node.schema_name)}Json"
        lines.append(f"type {node.name} struct {{")
        lines.append("\tStatus int")
        lines.append(f"\tBody   {body_type}")
        lines.append("}")
        lines.append("")
        lines.append(f"func (e *{node.name}) Error() string {{")
        lines.append('\treturn fmt.Sprintf("HTTP %d: %v", e.Status, e.Body)')
        lines.append("}")
    else:
        # Error without schema
        lines.append(f"type {node.name} struct {{")
        lines.append("\tStatus int")
        lines.append("\tBody   string")
        lines.append("}")
        lines.append("")
        lines.append(f"func (e *{node.name}) Error() string {{")
        lines.append('\treturn fmt.Sprintf("HTTP %d: %s", e.Status, e.Body)')
        lines.append("}")
    lines.append("")
    return lines


def emit_result_alias_def(node: ResultAliasDef) -> list[str]:
    """Emit a result alias node (no-op for Go, which returns `(value, error)` tuples).

    Args:
        node (ResultAliasDef): Result alias AST node.

    Returns:
        list[str]: Empty list.
    """
    return []


def emit_matcher_list_def(
    node: MatcherListDef, err_schema_map: dict[str, str] | None = None
) -> list[str]:
    """Emit the `[]sscErrMatcher` slice declaration for a REST struct.

    Args:
        node (MatcherListDef): Matcher list AST node.
        err_schema_map (dict[str, str] | None): Optional mapping from error variant
            names to JSON schema names.

    Returns:
        list[str]: Generated Go slice declaration lines.
    """
    err_schema_map = err_schema_map or {}
    var = f"{to_snake_case(node.struct_name)}Matchers"
    lines = [f"var {var} = []sscErrMatcher{{"]
    for e in node.entries:
        checks = [
            f"gjson.GetBytes(_b, {_go_str(key)}).Exists()"
            for key in e.required_keys
        ]
        for path, val in e.conditions.items():
            go_path = _go_str(path)
            if isinstance(val, bool):
                checks.append(
                    f"gjson.GetBytes(_b, {go_path}).Bool() == {str(val).lower()}"
                )
            elif isinstance(val, int):
                checks.append(f"gjson.GetBytes(_b, {go_path}).Int() == {val}")
            elif isinstance(val, float):
                checks.append(f"gjson.GetBytes(_b, {go_path}).Float() == {val}")
            elif val is None:
                checks.append(f"!gjson.GetBytes(_b, {go_path}).Exists()")
            else:
                checks.append(
                    f"gjson.GetBytes(_b, {go_path}).String() == {_go_str(str(val))}"
                )
        check_expr = " && ".join(checks)

        if check_expr:
            lines.append(
                f"\t{{Status: {e.status}, Check: func(_b []byte) bool {{ return {check_expr} }}, Factory: func(_s int, _b []byte) error {{"
            )
        else:
            lines.append(
                f"\t{{Status: {e.status}, Factory: func(_s int, _b []byte) error {{"
            )

        if e.factory_name:
            schema = err_schema_map.get(e.factory_name, "")
            if schema:
                body_type = f"{to_pascal_case(schema)}Json"
                lines.append(f"\t\tvar _body {body_type}")
                lines.append(
                    "\t\tif _err := json.Unmarshal(_b, &_body); _err != nil {"
                )
                lines.append("\t\t\treturn nil")
                lines.append("\t\t}")
                lines.append(
                    f"\t\treturn &{e.factory_name}{{Status: _s, Body: _body}}"
                )
            else:
                lines.append(f"\t\treturn &{e.factory_name}{{Status: _s}}")
        else:
            lines.append("\t\treturn nil")
        lines.append("\t}},")
    lines.append("}")
    return lines
