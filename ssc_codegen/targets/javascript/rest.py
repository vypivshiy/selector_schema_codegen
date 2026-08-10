"""JavaScript REST/fetch codegen — pure functions for MethodFetch, MethodRest,
ResultVariantDef, ResultAliasDef, MatcherListDef AST nodes.

Called by JsVisitor via thin delegate methods.  The HTTP library strategy
(fetch/axios) is passed as a parameter where needed.
"""

from __future__ import annotations

import json

from ssc_codegen.ast import (
    JsonDef,
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
from ssc_codegen.targets.javascript.http_libs.base import JsHttpLibStrategy
from ssc_codegen.traversal.context import WalkContext
from ssc_codegen.traversal.utils import dict_needs_builder, err_subclass_name


# ===========================================================================
# REST shared runtime source (Ok/Err/sscDispatchErr/etc.)
# ===========================================================================

REST_SHARED: list[str] = [
    "/**",
    " * @template T",
    " * @typedef {Object} Ok",
    " * @property {true} isOk",
    " * @property {number} status",
    " * @property {Object<string, string>} headers",
    " * @property {T} value",
    " */",
    "",
    "/**",
    " * @template E",
    " * @typedef {Object} Err",
    " * @property {false} isOk",
    " * @property {number} status",
    " * @property {Object<string, string>} headers",
    " * @property {E} value",
    " */",
    "",
    "/**",
    " * @typedef {Object} UnknownErr",
    " * @property {false} isOk",
    " * @property {number} status",
    " * @property {Object<string, string>} headers",
    " * @property {*} value",
    " */",
    "",
    "/**",
    " * @typedef {Object} TransportErr",
    " * @property {false} isOk",
    " * @property {0} status",
    " * @property {Object<string, string>} headers",
    " * @property {null} value",
    " * @property {string} cause",
    " */",
    "",
    "/**",
    " * @typedef {Object} ErrMatcher",
    " * @property {number} status",
    " * @property {function(Object): boolean|null} check",
    " * @property {function(number, Object, *): Err} factory",
    " */",
    "",
    "function sscDispatchErr(_matchers, _status, _headers, _body) {",
    "    for (const _m of _matchers) {",
    "        if (_m.status !== _status) continue;",
    "        if (_m.check !== null) {",
    "            if (!(_body instanceof Object) || !_m.check(_body)) continue;",
    "        }",
    "        return _m.factory(_status, _headers, _body);",
    "    }",
    "    if (_status >= 200 && _status < 300) return null;",
    "    return { isOk: false, status: _status, headers: _headers, value: _body };",
    "}",
    "",
]


# ===========================================================================
# Placeholder / Template rendering (pure functions)
# ===========================================================================

_JS_STYLE_SEP = {"csv": ",", "pipe": "|", "space": " "}
_JS_PRIM_JSDOC = {
    "str": "string",
    "int": "number",
    "float": "number",
    "bool": "boolean",
}


def _js_array_join(ph: PlaceholderSpec) -> str:
    sep = _JS_STYLE_SEP[ph.style or "csv"]
    return f"{ph.name}.map(String).join({sep!r})"


def render_value(tmpl: PlaceholderTemplate) -> str:
    if ph := tmpl.single_placeholder():
        if ph.is_array and ph.style in ("csv", "pipe", "space"):
            return _js_array_join(ph)
        return ph.name
    if tmpl.has_placeholders:
        inner = tmpl.map(
            lambda ph: "${" + ph.name + "}",
            lambda s: s.replace("\\", "\\\\").replace("`", "\\`"),
        )
        return f"`{inner}`"
    return repr(tmpl.source)


def render_obj(d: dict[str, PlaceholderTemplate]) -> str:
    if not d:
        return "{}"
    inner = ", ".join(f"{k!r}: {render_value(v)}" for k, v in d.items())
    return "{" + inner + "}"


def emit_obj_builder(
    varname: str, d: dict[str, PlaceholderTemplate], indent: str
) -> list[str]:
    lines = [f"{indent}const {varname} = {{}};"]
    for key, tmpl in d.items():
        ph = tmpl.single_placeholder()
        expr = render_value(tmpl)
        if ph is not None and ph.is_optional:
            lines.append(
                f"{indent}if ({ph.name} !== undefined && {ph.name} !== null) "
                f"{varname}[{key!r}] = {expr};"
            )
        else:
            lines.append(f"{indent}{varname}[{key!r}] = {expr};")
    return lines


def emit_params_builder(
    varname: str, d: dict[str, PlaceholderTemplate], indent: str
) -> list[str]:
    lines = [f"{indent}const {varname} = new URLSearchParams();"]
    for key, tmpl in d.items():
        ph = tmpl.single_placeholder()
        if ph is None:
            lines.append(
                f"{indent}{varname}.set({key!r}, {render_value(tmpl)});"
            )
            continue
        effective_key = (
            f"{key}[]" if (ph.is_array and ph.style == "bracket") else key
        )
        if ph.is_array and ph.style in (None, "repeat", "bracket"):
            op = (
                f"for (const _v of {ph.name}) "
                f"{varname}.append({effective_key!r}, String(_v));"
            )
        elif ph.is_array:
            op = f"{varname}.set({effective_key!r}, {_js_array_join(ph)});"
        else:
            scalar = ph.name if ph.type_name == "str" else f"String({ph.name})"
            op = f"{varname}.set({effective_key!r}, {scalar});"
        if ph.is_optional:
            lines.append(
                f"{indent}if ({ph.name} !== undefined && {ph.name} !== null) {op}"
            )
        else:
            lines.append(f"{indent}{op}")
    return lines


def render_json_body(tmpl: PlaceholderTemplate) -> str:
    inner = tmpl.map(
        lambda ph: "${" + ph.name + "}",
        lambda s: s.replace("\\", "\\\\").replace("`", "\\`"),
    )
    return f"`{inner}`"


def render_body(spec: RequestHttp) -> tuple[str, str] | None:
    if spec.body_kind == "empty" or spec.body is None:
        return None
    if spec.body_kind == "json":
        assert isinstance(spec.body, PlaceholderTemplate)
        return ("body", render_json_body(spec.body))
    if spec.body_kind == "form":
        assert isinstance(spec.body, dict)
        return ("body", f"new URLSearchParams({render_obj(spec.body)})")
    assert isinstance(spec.body, PlaceholderTemplate)
    return ("body", render_value(spec.body))


# ===========================================================================
# Condition check rendering
# ===========================================================================


def _resolve_path_expr(body_var: str, path: str) -> str:
    expr = body_var
    for seg in path.split("."):
        if seg.isdigit():
            expr += f"[{seg}]"
        else:
            expr += f"[{seg!r}]"
    return expr


def render_js_condition_check(
    required_keys: list[str], conditions: dict[str, object]
) -> str | None:
    parts: list[str] = []
    for key in required_keys:
        parts.append(f"{key!r} in _b")
    for path, value in conditions.items():
        lhs = _resolve_path_expr("_b", path)
        if isinstance(value, bool):
            parts.append(f"{lhs} === {str(value).lower()}")
        elif value is None:
            parts.append(f"{lhs} === null")
        elif isinstance(value, (int, float)):
            parts.append(f"{lhs} === {value}")
        else:
            parts.append(f"{lhs} === {value!r}")
    if not parts:
        return None
    return f"(_b) => {' && '.join(parts)}"


# ===========================================================================
# Helpers
# ===========================================================================


def js_name(name: str) -> str:
    return to_camel_case(to_snake_case(name))


def ok_payload_type(node: MethodRest) -> str:
    if not node.response_schema:
        return "null"
    struct = node.parent
    module = struct.parent if struct is not None else None
    schema_type = f"{to_pascal_case(node.response_schema)}Json"
    if module is not None:
        for n in module.body:
            if isinstance(n, JsonDef) and n.name == node.response_schema:
                if n.is_array:
                    return f"Array<{schema_type}>"
                break
    return schema_type


# ===========================================================================
# Shared request preparation
# ===========================================================================


def _prepare_request(
    spec: RequestHttp, i3: str
) -> tuple[list[str], str | None, str | None, str | None]:
    """Extract pre_lines + params/headers/body expressions from a spec."""
    pre_lines: list[str] = []
    params_expr = None
    if spec.params:
        if dict_needs_builder(spec.params):
            pre_lines.extend(emit_params_builder("_params", spec.params, i3))
            params_expr = "_params"
        else:
            params_expr = render_obj(spec.params)
    headers_expr = None
    if spec.headers:
        if dict_needs_builder(spec.headers):
            pre_lines.extend(emit_obj_builder("_headers", spec.headers, i3))
            headers_expr = "_headers"
        else:
            headers_expr = render_obj(spec.headers)
    body_result = render_body(spec)
    body_expr = body_result[1] if body_result else None
    return pre_lines, params_expr, headers_expr, body_expr


def _placeholder_param(spec: RequestHttp) -> str:
    if not spec.placeholders:
        return ""
    ordered = [
        p.name for p in sorted(spec.placeholders, key=lambda p: p.is_optional)
    ]
    return ", {" + ", ".join(ordered) + "}"


# ===========================================================================
# Emit functions (called by JsVisitor)
# ===========================================================================


def emit_method_rest(
    node: MethodRest, ctx: WalkContext, http: JsHttpLibStrategy
) -> list[str]:
    spec = node.http_request.with_renamed_placeholders(js_name)
    http_client = ctx.meta.get("http_client", "fetch")
    ind = ctx.indent_char
    i1, i2, i3 = (ctx.indent + ind * n for n in range(3))

    ph_param = _placeholder_param(spec)
    pre_lines, params_expr, headers_expr, body_expr = _prepare_request(spec, i3)

    raw_name = node.name or "fetch"
    method_name = to_camel_case(to_snake_case(raw_name))
    if raw_name == "fetch":
        method_name = "fetch"

    parent = node.parent
    errors = parent.errors if isinstance(parent, StructBase) else []
    struct_name = parent.name if isinstance(parent, StructBase) else ""
    matchers_var = f"_{to_snake_case(struct_name)}Matchers"

    ok_payload = ok_payload_type(node)
    err_variants: list[str] = []
    seen: set[str] = set()
    for err in errors:
        cls_name = err_subclass_name(struct_name, err)
        if cls_name not in seen:
            seen.add(cls_name)
            err_variants.append(cls_name)
    return_union = " | ".join(
        [f"Ok<{ok_payload}>", *err_variants, "UnknownErr", "TransportErr"]
    )

    fn_name = http.fn_name
    if node.response_path:
        accessor = "".join(
            f"[{json.dumps(p)}]" for p in node.response_path.split(".")
        )
        value_fn = f"(_b) => _b{accessor}"
    elif not node.response_schema:
        value_fn = "(_b) => null"
    else:
        value_fn = "null"

    if http_client == "axios":
        url_expr = render_value(spec.url)
        opts_parts: list[str] = []
        if params_expr:
            opts_parts.append(f"params: {params_expr}")
        if headers_expr:
            opts_parts.append(f"headers: {headers_expr}")
        if body_expr:
            opts_parts.append(f"data: {body_expr}")
    else:
        if params_expr:
            url_inner = spec.url.map(
                lambda ph: "${" + ph.name + "}",
                lambda s: s.replace("`", "\\`"),
            )
            if params_expr == "_params":
                url_expr = f"`{url_inner}?${{{params_expr}.toString()}}`"
            else:
                url_expr = (
                    f"`{url_inner}?${{new URLSearchParams({params_expr})}}`"
                )
        else:
            url_expr = render_value(spec.url)
        opts_parts = []
        if headers_expr:
            opts_parts.append(f"headers: {headers_expr}")
        if body_expr:
            opts_parts.append(f"body: {body_expr}")

    opts_obj = "{" + ", ".join(opts_parts) + "}" if opts_parts else "{}"

    lines: list[str] = []
    if node.doc:
        lines.append(f"{i1}/**")
        for doc_line in node.doc.splitlines():
            lines.append(f"{i1} * {doc_line}")
        lines.append(f"{i1} */")
    lines.append(f"{i1}/**")
    for p in sorted(spec.placeholders, key=lambda p: p.is_optional):
        t = _JS_PRIM_JSDOC[p.type_name]
        if p.is_array:
            t = f"{t}[]"
        bracket = f"[params.{p.name}]" if p.is_optional else f"params.{p.name}"
        lines.append(f"{i1} * @param {{{t}}} {bracket}")
    lines.append(f"{i1} * @param {{Object}} [opts] per-call request options (headers, etc.)")
    lines.append(f"{i1} * @returns {{Promise<{return_union}>}}")
    lines.append(f"{i1} */")
    lines.append(f"{i1}static async {method_name}(client{ph_param}, opts = {{}}) {{")
    lines.extend(pre_lines)
    lines.append(f"{i2}const _kw = {opts_obj};")
    lines.append(f"{i2}for (const [_k, _v] of Object.entries(opts)) {{")
    lines.append(f"{i2}    if (typeof _kw[_k] === 'object' && _kw[_k] !== null && typeof _v === 'object' && _v !== null) {{")
    lines.append(f"{i2}        _kw[_k] = {{..._kw[_k], ..._v}};")
    lines.append(f"{i2}    }} else {{")
    lines.append(f"{i2}        _kw[_k] = _v;")
    lines.append(f"{i2}    }}")
    lines.append(f"{i2}}}")
    lines.append(
        f"{i2}return {fn_name}(client, {matchers_var}, "
        f"{spec.method!r}, {url_expr}, {value_fn}, _kw);"
    )
    lines.append(f"{i1}}}")
    return lines


def emit_method_fetch(
    node: MethodFetch, ctx: WalkContext, http: JsHttpLibStrategy
) -> list[str]:
    spec = node.http_request.with_renamed_placeholders(js_name)
    http_client = ctx.meta.get("http_client", "fetch")
    ind = ctx.indent_char
    i1, i2, i3 = (ctx.indent + ind * n for n in range(3))

    ph_param = _placeholder_param(spec)
    pre_lines, params_expr, headers_expr, body_expr = _prepare_request(spec, i3)

    struct_name = to_pascal_case(node.parent.name)  # type: ignore[union-attr]
    method_name = "fetch" + (to_pascal_case(node.name) if node.name else "")

    def _response_lines(data_expr: str) -> list[str]:
        rl: list[str] = []
        if node.response_path:
            accessor = "".join(
                f"[{p!r}]" for p in node.response_path.split(".")
            )
            rl.append(f"{i2}const _data = {data_expr};")
            if node.response_join:
                rl.append(
                    f"{i2}const _body = _data{accessor}.join({node.response_join!r});"
                )
            else:
                rl.append(f"{i2}const _body = _data{accessor};")
        else:
            rl.append(f"{i2}const _body = {data_expr};")
        rl.append(f"{i2}return new {struct_name}(_body);")
        return rl

    lines: list[str] = [f"{i1}static async {method_name}(client{ph_param}, opts = {{}}) {{"]
    lines.extend(pre_lines)

    # Build _kw from DSL-specified request options (method/url stay out).
    kw_parts: list[str] = []
    if http_client == "fetch":
        if params_expr:
            url_inner = spec.url.map(
                lambda ph: "${" + ph.name + "}",
                lambda s: s.replace("`", "\\`"),
            )
            url_expr = f"`{url_inner}?${{new URLSearchParams({params_expr})}}`"
        else:
            url_expr = render_value(spec.url)
        if headers_expr:
            kw_parts.append(f"headers: {headers_expr}")
        if spec.cookies:
            cookie_str = "; ".join(
                f"{k}={v.source}" for k, v in spec.cookies.items()
            )
            kw_parts.append(
                f"// cookies: {cookie_str!r}  /* set via headers or credentials */"
            )
        if body_expr:
            kw_parts.append(f"body: {body_expr}")
        kw_obj = "{" + ", ".join(kw_parts) + "}" if kw_parts else "{}"
        lines.append(f"{i2}const _kw = {kw_obj};")
        lines.append(f"{i2}for (const [_k, _v] of Object.entries(opts)) {{")
        lines.append(f"{i2}    if (typeof _kw[_k] === 'object' && _kw[_k] !== null && typeof _v === 'object' && _v !== null) {{")
        lines.append(f"{i2}        _kw[_k] = {{..._kw[_k], ..._v}};")
        lines.append(f"{i2}    }} else {{")
        lines.append(f"{i2}        _kw[_k] = _v;")
        lines.append(f"{i2}    }}")
        lines.append(f"{i2}}}")
        lines.append(
            f"{i2}const _resp = await client({url_expr},"
            f" {{ method: {spec.method!r}, ..._kw }});"
        )
        lines.append(
            f"{i2}if (!_resp.ok) throw new Error(`HTTP ${{_resp.status}}`);"
        )
        if node.response_path:
            lines.extend(_response_lines("await _resp.json()"))
        else:
            lines.extend(_response_lines("await _resp.text()"))
    else:
        url_expr = render_value(spec.url)
        if params_expr:
            kw_parts.append(f"params: {params_expr}")
        if headers_expr:
            kw_parts.append(f"headers: {headers_expr}")
        if spec.cookies:
            kw_parts.append(
                f"// cookies: {render_obj(spec.cookies)},"
            )
        if body_expr:
            kw_parts.append(f"data: {body_expr}")
        kw_obj = "{" + ", ".join(kw_parts) + "}" if kw_parts else "{}"
        lines.append(f"{i2}const _kw = {kw_obj};")
        lines.append(f"{i2}for (const [_k, _v] of Object.entries(opts)) {{")
        lines.append(f"{i2}    if (typeof _kw[_k] === 'object' && _kw[_k] !== null && typeof _v === 'object' && _v !== null) {{")
        lines.append(f"{i2}        _kw[_k] = {{..._kw[_k], ..._v}};")
        lines.append(f"{i2}    }} else {{")
        lines.append(f"{i2}        _kw[_k] = _v;")
        lines.append(f"{i2}    }}")
        lines.append(f"{i2}}}")
        lines.append(
            f"{i2}const _resp = await client.request({{"
            f" method: {spec.method!r}, url: {url_expr}, ..._kw }});"
        )
        lines.extend(_response_lines("_resp.data"))

    lines.append(f"{i1}}}")
    return lines


def emit_result_variant_def(node: ResultVariantDef) -> list[str]:
    if node.schema_name:
        base = f"{to_pascal_case(node.schema_name)}Json"
        value_type = f"Array<{base}>" if node.schema_is_array else base
    else:
        value_type = "*"
    return [
        "/**",
        f" * @typedef {{Object}} {node.name}",
        " * @property {false} isOk",
        f" * @property {{{node.status}}} status",
        " * @property {Object<string, string>} headers",
        f" * @property {{{value_type}}} value",
        " */",
        "",
    ]


def emit_result_alias_def(node: ResultAliasDef) -> list[str]:
    return []


def emit_matcher_list_def(node: MatcherListDef) -> list[str]:
    var = f"_{to_snake_case(node.struct_name)}Matchers"
    lines = [f"const {var} = ["]
    for e in node.entries:
        check = render_js_condition_check(e.required_keys, e.conditions)
        check_arg = check if check else "null"
        lines.append(
            f"    {{ status: {e.status}, check: {check_arg}, "
            f"factory: (_s, _h, _b) => ({{ isOk: false, status: _s, "
            f"headers: _h, value: _b }}) }},"
        )
    lines.append("];")
    return lines
