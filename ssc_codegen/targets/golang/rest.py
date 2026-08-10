"""Go REST codegen — pure functions for MethodRest, MethodFetch,
ResultVariantDef, ResultAliasDef, MatcherListDef AST nodes.

Adapts the Python/JS REST pattern to Go idioms:

- Each REST method returns a marker interface (e.g. ``APIFetchResult``).
- ``Ok`` variant holds the parsed schema value.
- Each ``@error`` generates a struct implementing both ``error`` and the marker.
- ``UnknownErr`` / ``TransportErr`` are generated per-struct (not runtime).
- The runtime's ``sscRestCall`` returns ``sscResult``; the method converts.
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
    StructBase,
)
from ssc_codegen.ast.struct import RequestHttp
from ssc_codegen.naming import to_camel_case, to_pascal_case, to_snake_case
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
    """Go format verb for a placeholder."""
    if ph.type_name == "int":
        return "%d"
    if ph.type_name == "float":
        return "%f"
    if ph.type_name == "bool":
        return "%t"
    return "%s"


def render_url(tmpl: PlaceholderTemplate) -> str:
    """Render URL template as a Go expression (fmt.Sprintf or string literal)."""
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
    """Render JSON body template as a Go string expression."""
    if not tmpl.has_placeholders:
        return _go_str(tmpl.source)

    fmt_str = ""
    args: list[str] = []
    for part in tmpl.parts:
        if isinstance(part, PlaceholderSpec):
            fmt_str += _go_fmt_placeholder(part)
            args.append(to_camel_case(part.name))
        else:
            fmt_str += (
                part.replace("%", "%%").replace("{", "{{").replace("}", "}}")
            )

    if not args:
        return _go_str(tmpl.source)
    return f"fmt.Sprintf({_go_str(fmt_str)}, {', '.join(args)})"


def render_form_body(body: dict[str, PlaceholderTemplate]) -> str:
    """Render a form-urlencoded dict body as ``url.Values{...}.Encode()``.

    Keys are literal strings; values may contain placeholders (rendered via
    ``fmt.Sprintf`` through ``render_url``). ``url.Values`` properly escapes
    both keys and values per RFC 3986.
    """
    if not body:
        return '""'
    parts: list[str] = []
    for k, tmpl in body.items():
        val = (
            render_url(tmpl) if tmpl.has_placeholders else _go_str(tmpl.source)
        )
        parts.append(f"{_go_str(k)}: []string{{{val}}}")
    return f"url.Values{{{', '.join(parts)}}}.Encode()"


# ===========================================================================
# Placeholder parameter signature
# ===========================================================================


def placeholder_params(spec: RequestHttp) -> str:
    """Generate Go function parameters for placeholders."""
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
# Result type names
# ===========================================================================


def result_interface_name(struct_name: str, method_name: str) -> str:
    """Name of the marker interface for a REST method result."""
    pascal = to_pascal_case(struct_name)
    method_suffix = to_pascal_case(method_name) if method_name else "Fetch"
    return f"{pascal}{method_suffix}Result"


def ok_variant_name(struct_name: str, method_name: str) -> str:
    pascal = to_pascal_case(struct_name)
    method_suffix = to_pascal_case(method_name) if method_name else "Fetch"
    return f"{pascal}{method_suffix}Ok"


# ===========================================================================
# Emit functions
# ===========================================================================


def _build_opts(spec: RequestHttp, indent: str) -> list[str]:
    """Build sscReqOpts construction lines."""
    lines: list[str] = []
    has_headers = bool(spec.headers)
    has_body = spec.body_kind not in ("empty", None) and spec.body is not None

    if not has_headers and not has_body:
        return [f"{indent}nil"]

    lines.append(f"{indent}&sscReqOpts{{")
    if has_body:
        body = spec.body
        if isinstance(body, PlaceholderTemplate):
            lines.append(f"{indent}\tBody: {render_body_json(body)},")
        elif isinstance(body, dict):
            # form-urlencoded body — url.Values{...}.Encode()
            lines.append(f"{indent}\tBody: {render_form_body(body)},")
    if has_headers:
        parts = []
        for k, tmpl in spec.headers.items():
            if tmpl.has_placeholders:
                val = render_url(tmpl)
            else:
                val = _go_str(tmpl.source)
            parts.append(f"{_go_str(k)}: []string{{{val}}}")
        lines.append(f"{indent}\tHeaders: sscHeaders{{{', '.join(parts)}}},")
    lines.append(f"{indent}}}")
    return lines


def emit_method_fetch(
    node: MethodFetch,
    ctx: WalkContext,
    http: GoHttpLibStrategy,
) -> list[str]:
    """Emit a Go Fetch method for HTML-parser structs with ``@request``.

    Signature: ``func Fetch(ctx context.Context, client *http.Client, <phs>) (*Name, error)``

    Idiomatic Go: cancellation via ``context.Context``, async via ``go f(ctx)``
    on caller side. Headers/body inlined (no ``sscReqOpts`` dependency).
    Status >= 400 → typed ``error``. ``response_path`` extracts a sub-string
    via ``gjson`` before passing body to ``New<Name>``.
    """
    spec = node.http_request.with_renamed_placeholders(to_camel_case)
    struct = node.parent
    assert isinstance(struct, StructBase)
    name = to_pascal_case(struct.name)
    method_name = to_pascal_case(node.name) if node.name else "Fetch"
    ph_params = placeholder_params(spec)
    url_expr = render_url(spec.url)

    i1 = ctx.indent
    i2 = i1 + ctx.indent_char

    lines: list[str] = [
        f"{i1}func {method_name}(ctx context.Context, client {http.client_type}{ph_params}, opts ...sscReqOpt) (*{name}, error) {{",
        f"{i2}req, err := http.NewRequestWithContext(ctx, {_go_str(spec.method)}, {url_expr}, nil)",
        f"{i2}if err != nil {{",
        f"{i2}\treturn nil, err",
        f"{i2}}}",
    ]

    # Headers inline.
    for k, tmpl in spec.headers.items():
        val = (
            render_url(tmpl) if tmpl.has_placeholders else _go_str(tmpl.source)
        )
        lines.append(f"{i2}req.Header.Set({_go_str(k)}, {val})")

    # Body inline (json/raw or form).
    if spec.body_kind in ("json", "raw") and spec.body is not None:
        if isinstance(spec.body, PlaceholderTemplate):
            body_expr = render_body_json(spec.body)
            lines.append(
                f"{i2}req.Body = io.NopCloser(strings.NewReader({body_expr}))"
            )
    elif spec.body_kind == "form" and isinstance(spec.body, dict):
        body_expr = render_form_body(spec.body)
        lines.append(
            f"{i2}req.Body = io.NopCloser(strings.NewReader({body_expr}))"
        )

    # Apply per-call opts (user headers are additive).
    lines.append(f"{i2}if len(opts) > 0 {{")
    lines.append(f"{i2}\t_opts := &sscReqOpts{{}}")
    lines.append(f"{i2}\tfor _, o := range opts {{ o(_opts) }}")
    lines.append(f"{i2}\tfor _k, _vs := range _opts.Headers {{")
    lines.append(f"{i2}\t\tfor _, _v := range _vs {{ req.Header.Add(_k, _v) }}")
    lines.append(f"{i2}\t}}")
    lines.append(f"{i2}}}")

    # Execute.
    lines.extend(
        [
            f"{i2}resp, err := client.Do(req)",
            f"{i2}if err != nil {{",
            f"{i2}\treturn nil, err",
            f"{i2}}}",
            f"{i2}defer resp.Body.Close()",
            f"{i2}body, err := io.ReadAll(resp.Body)",
            f"{i2}if err != nil {{",
            f"{i2}\treturn nil, err",
            f"{i2}}}",
            f"{i2}if resp.StatusCode >= 400 {{",
            f'{i2}\treturn nil, fmt.Errorf("{name}: HTTP %d: %s", resp.StatusCode, string(body))',
            f"{i2}}}",
        ]
    )

    # response_path / response_join extraction via gjson.
    if node.response_path:
        path = _go_str(node.response_path)
        if node.response_join:
            join = _go_str(node.response_join)
            lines.extend(
                [
                    f"{i2}{{",
                    f"{i2}\t_parts := gjson.GetBytes(body, {path}).Array()",
                    f"{i2}\t_parts_strs := make([]string, len(_parts))",
                    f"{i2}\tfor _i, _p := range _parts {{",
                    f"{i2}\t\t_parts_strs[_i] = _p.String()",
                    f"{i2}\t}}",
                    f"{i2}\tbody = []byte(strings.Join(_parts_strs, {join}))",
                    f"{i2}}}",
                ]
            )
        else:
            lines.append(
                f"{i2}body = []byte(gjson.GetBytes(body, {path}).String())"
            )

    # Construct parser from body.
    lines.append(f"{i2}return New{name}(string(body))")
    lines.append(f"{i1}}}")
    lines.append("")
    return lines


def emit_method_rest(
    node: MethodRest,
    ctx: WalkContext,
    http: GoHttpLibStrategy,
) -> list[str]:
    """Emit a Go REST method that calls sscRestCall.

    Returns idiomatic ``(value, error)`` tuple:
      - typed value  → ``(*SchemaJson, error)`` or ``([]SchemaJson, error)``
      - void         → ``(struct{}, error)``

    Errors propagate as typed structs: ``@error`` variants via matchers,
    ``*UnknownErr`` for unmatched HTTP >= 400, ``*TransportErr`` for network.
    Caller uses ``errors.As`` to discriminate.
    """
    spec = node.http_request.with_renamed_placeholders(to_camel_case)
    struct = node.parent
    assert isinstance(struct, StructBase)
    method_name = to_pascal_case(node.name) if node.name else "Fetch"
    ph_params = placeholder_params(spec)
    matchers_var = f"{to_snake_case(struct.name)}Matchers"
    url_expr = render_url(spec.url)

    # Resolve return type from AST response_schema (no `any`).
    if node.response_schema:
        schema_go = f"{to_pascal_case(node.response_schema)}Json"
        if getattr(node, "response_is_array", False):
            schema_go = "[]" + schema_go
            ret_type = schema_go
            zero = "nil"
        else:
            ret_type = "*" + schema_go
            zero = "nil"
    else:
        # Void response: 2-value for consistent call sites.
        ret_type = "struct{}"
        zero = "struct{}{}"

    i1 = ctx.indent
    i2 = i1 + ctx.indent_char

    lines: list[str] = []

    # Function signature.
    lines.append(
        f"{i1}func {method_name}(client {http.client_type}{ph_params}, opts ...sscReqOpt) ({ret_type}, error) {{"
    )

    # Build _opts from DSL, apply per-call user opts, then call sscRestCall.
    opts_lines = _build_opts(spec, i2 + "\t")
    body_var = "_" if not node.response_schema else "body"

    # Assign DSL opts to _opts variable.
    if len(opts_lines) == 1 and opts_lines[0].strip() == "nil":
        lines.append(f"{i2}_opts := &sscReqOpts{{}}")
    else:
        lines.append(f"{i2}_opts := {opts_lines[0].strip()}")
        for ol in opts_lines[1:]:
            lines.append(ol)

    # Apply per-call opts (functional options).
    lines.append(f"{i2}for _, o := range opts {{ o(_opts) }}")

    lines.append(
        f"{i2}{body_var}, err := sscRestCall(client, {matchers_var}, "
        f"{_go_str(spec.method)}, {url_expr}, _opts)"
    )

    # Error propagation.
    lines.append(f"{i2}if err != nil {{")
    lines.append(f"{i2}\treturn {zero}, err")
    lines.append(f"{i2}}}")

    # Parse response body (when typed) or return void.
    if node.response_schema:
        schema_go = f"{to_pascal_case(node.response_schema)}Json"
        # response_path extraction: narrow body to the sub-object before
        # Unmarshal. gjson `.Raw` preserves JSON structure (works for both
        # scalar-object and array paths). Path wins over schema: the
        # schema type-checks the *extracted* value, not the envelope.
        if node.response_path:
            path = _go_str(node.response_path)
            lines.append(f"{i2}body = []byte(gjson.GetBytes(body, {path}).Raw)")
        if getattr(node, "response_is_array", False):
            lines.append(f"{i2}var val []{schema_go}")
        else:
            lines.append(f"{i2}var val {schema_go}")
        lines.append(
            f"{i2}if perr := json.Unmarshal(body, &val); perr != nil {{"
        )
        lines.append(
            f'{i2}\treturn {zero}, fmt.Errorf("ssc-gen: parse {schema_go}: %w", perr)'
        )
        lines.append(f"{i2}}}")
        if getattr(node, "response_is_array", False):
            lines.append(f"{i2}return val, nil")
        else:
            lines.append(f"{i2}return &val, nil")
    else:
        lines.append(f"{i2}return {zero}, nil")

    lines.append(f"{i1}}}")
    lines.append("")
    return lines


def emit_result_variant_def(node: ResultVariantDef) -> list[str]:
    """Emit a standalone ``@error`` variant as an ``error`` struct.

    No interface wiring — variants implement ``error`` directly. Discriminated
    by the caller via ``errors.As``.
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
    """Go backend uses ``(value, error)`` tuples — no marker interface needed.

    Returns no lines. Kept as a hook so the visitor stays consistent with
    Python/JS backends that do emit a result alias.
    """
    return []


def emit_matcher_list_def(
    node: MatcherListDef, err_schema_map: dict[str, str] | None = None
) -> list[str]:
    """Emit the matchers slice for a REST struct."""
    err_schema_map = err_schema_map or {}
    var = f"{to_snake_case(node.struct_name)}Matchers"
    lines = [f"var {var} = []sscErrMatcher{{"]
    for e in node.entries:
        check_expr: str
        if e.required_keys:
            checks = []
            for key in e.required_keys:
                checks.append(f"gjson.GetBytes(_b, {_go_str(key)}).Exists()")
            check_expr = " && ".join(checks)
        elif e.conditions:
            checks = []
            for path, val in e.conditions.items():
                go_path = _go_str(path)
                if isinstance(val, bool):
                    checks.append(
                        f"gjson.GetBytes(_b, {go_path}).Bool() == {str(val).lower()}"
                    )
                elif isinstance(val, (int, float)):
                    checks.append(
                        f"gjson.GetBytes(_b, {go_path}).Int() == {val}"
                    )
                elif val is None:
                    checks.append(f"!gjson.GetBytes(_b, {go_path}).Exists()")
                else:
                    checks.append(
                        f"gjson.GetBytes(_b, {go_path}).String() == {_go_str(str(val))}"
                    )
            check_expr = " && ".join(checks)
        else:
            check_expr = ""

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
                lines.append(
                    f'\t\t\treturn fmt.Errorf("ssc-gen: parse {body_type}: %w", _err)'
                )
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
