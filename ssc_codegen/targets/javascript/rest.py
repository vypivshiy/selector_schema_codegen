"""JavaScript REST/fetch codegen — pure functions for MethodFetch, MethodRest,
ResultVariantDef, ResultAliasDef, MatcherListDef AST nodes.

Called by JsVisitor via thin delegate methods.  The HTTP library strategy
(fetch/axios) is passed as a parameter where needed.
"""

from __future__ import annotations

import inspect
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
from ssc_codegen.naming import (
    js_json_projector_name,
    to_camel_case,
    to_pascal_case,
    to_snake_case,
)
from ssc_codegen.request_spec import parse_json_template
from ssc_codegen.targets.javascript.http_libs.base import JsHttpLibStrategy
from ssc_codegen.traversal.context import WalkContext
from ssc_codegen.traversal.utils import (
    err_subclass_name,
    find_enclosing_module,
)

# ===========================================================================
# HTTP & REST shared runtime source
# ===========================================================================

HTTP_SHARED: list[str] = [
    *inspect.cleandoc(
        """
        function sscBuildParams(params) {
            if (params instanceof URLSearchParams) return params;
            const sp = new URLSearchParams();
            for (const [k, v] of Object.entries(params || {})) {
                if (v === undefined || v === null) continue;
                if (Array.isArray(v)) {
                    for (const _v of v) {
                        if (_v !== undefined && _v !== null) sp.append(k, String(_v));
                    }
                } else {
                    sp.set(k, String(v));
                }
            }
            return sp;
        }

        function sscPrepareReq(url, dslOpts = {}, opts = {}, isAxios = false) {
            const _kw = {};
            let _params = null;
            if (dslOpts && dslOpts.params) {
                _params = {};
                for (const [k, v] of Object.entries(dslOpts.params)) {
                    if (v !== undefined && v !== null) _params[k] = v;
                }
            }
            if (dslOpts && dslOpts.headers) {
                const _h = {};
                for (const [k, v] of Object.entries(dslOpts.headers)) {
                    if (v !== undefined && v !== null) _h[k] = v;
                }
                if (Object.keys(_h).length > 0) _kw.headers = _h;
            }
            if (dslOpts && dslOpts.body !== undefined) {
                if (isAxios) _kw.data = dslOpts.body;
                else _kw.body = dslOpts.body;
            }
            if (opts) {
                for (const [_k, _v] of Object.entries(opts)) {
                    if (_k === 'params' && _v !== undefined && _v !== null) {
                        if (_v instanceof URLSearchParams) {
                            _params = _params ? { ..._params, ...Object.fromEntries(_v.entries()) } : _v;
                        } else if (typeof _v === 'object') {
                            _params = { ...(_params || {}), ..._v };
                        }
                    } else if (typeof _kw[_k] === 'object' && _kw[_k] !== null && typeof _v === 'object' && _v !== null) {
                        _kw[_k] = { ..._kw[_k], ..._v };
                    } else {
                        _kw[_k] = _v;
                    }
                }
            }
            if (_params !== null) {
                const _sp = sscBuildParams(_params);
                const _qs = _sp.toString();
                if (isAxios) {
                    if (_qs) _kw.params = _sp;
                } else if (_qs) {
                    url = url + (url.includes('?') ? '&' : '?') + _qs;
                }
            }
            return { url, _kw };
        }
        """
    ).splitlines(),
    "",
]

REST_SHARED: list[str] = [
    *inspect.cleandoc(
        """
        /**
         * @template T
         * @typedef {Object} Ok
         * @property {true} isOk
         * @property {number} status
         * @property {Object<string, string>} headers
         * @property {T} value
         */

        /**
         * @template E
         * @typedef {Object} Err
         * @property {false} isOk
         * @property {number} status
         * @property {Object<string, string>} headers
         * @property {E} value
         */

        /**
         * @typedef {Object} UnknownErr
         * @property {false} isOk
         * @property {number} status
         * @property {Object<string, string>} headers
         * @property {*} value
         */

        /**
         * @typedef {Object} TransportErr
         * @property {false} isOk
         * @property {0} status
         * @property {Object<string, string>} headers
         * @property {null} value
         * @property {string} cause
         */

        /**
         * @typedef {Object} ErrMatcher
         * @property {number} status
         * @property {function(Object): boolean|null} check
         * @property {function(number, Object, *): Err} factory
         */

        function sscDispatchErr(_matchers, _status, _headers, _body) {
            for (const _m of _matchers) {
                if (_m.status !== _status) continue;
                if (_body === null || typeof _body !== 'object') continue;
                if (_m.check !== null) {
                    if (Array.isArray(_body) || !_m.check(_body)) continue;
                }
                try {
                    return _m.factory(_status, _headers, _body);
                } catch (_e) {
                    continue;
                }
            }
            if (_status >= 200 && _status < 300) return null;
            return { isOk: false, status: _status, headers: _headers, value: _body };
        }
        """
    ).splitlines(),
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
    """Render a JavaScript array join expression for a delimited array placeholder.

    Args:
        ph (PlaceholderSpec): Array placeholder metadata specification.

    Returns:
        str: JavaScript `.map(String).join(...)` expression (null-guarded if optional).
    """
    sep = _JS_STYLE_SEP[ph.style or "csv"]
    joined = f"{ph.name}.map(String).join({sep!r})"
    if ph.is_optional:
        return f"({ph.name} != null ? {joined} : null)"
    return joined


def render_value(tmpl: PlaceholderTemplate) -> str:
    """Render a `PlaceholderTemplate` as a JavaScript expression.

    Args:
        tmpl (PlaceholderTemplate): Template containing literal parts and/or placeholders.

    Returns:
        str: JavaScript expression string representing the template value.
    """
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
    """Render a dictionary of `PlaceholderTemplate` values as a JavaScript object literal.

    Args:
        d (dict[str, PlaceholderTemplate]): Key-to-template mapping for params, headers, or form fields.

    Returns:
        str: JavaScript object literal expression.
    """
    if not d:
        return "{}"
    parts: list[str] = []
    for k, v in d.items():
        ph = v.single_placeholder()
        eff_k = (
            f"{k}[]"
            if (ph is not None and ph.is_array and ph.style == "bracket")
            else k
        )
        parts.append(f"{eff_k!r}: {render_value(v)}")
    return "{" + ", ".join(parts) + "}"


def render_json_body(tmpl: PlaceholderTemplate) -> str:
    """Render a JSON body template as a `JSON.stringify(...)` JavaScript expression.

    Args:
        tmpl (PlaceholderTemplate): JSON body template with optional placeholders.

    Returns:
        str: JavaScript `JSON.stringify(...)` expression.
    """

    def emit(value: object) -> str:
        if isinstance(value, PlaceholderSpec):
            return value.name
        if isinstance(value, PlaceholderTemplate):
            return render_value(value)
        if value is None:
            return "null"
        if isinstance(value, bool):
            return str(value).lower()
        if isinstance(value, (int, float)):
            return repr(value)
        if isinstance(value, str):
            return json.dumps(value)
        if isinstance(value, list):
            return "[" + ", ".join(emit(item) for item in value) + "]"
        if isinstance(value, dict):
            items = ", ".join(
                f"{json.dumps(str(key))}: {emit(item)}"
                for key, item in value.items()
            )
            return "{" + items + "}"
        raise TypeError(
            f"unsupported JSON body element: {type(value).__name__}"
        )

    return f"JSON.stringify({emit(parse_json_template(tmpl))})"


def render_body(spec: RequestHttp) -> tuple[str, str] | None:
    """Render the request body option for a `RequestHttp` specification.

    Args:
        spec (RequestHttp): HTTP request specification AST node.

    Returns:
        tuple[str, str] | None: `("body", value_expr)` pair, or `None` when empty.
    """
    if spec.body_kind == "empty" or spec.payload is None:
        return None
    if spec.body_kind == "json":
        assert isinstance(spec.payload, PlaceholderTemplate)
        return ("body", render_json_body(spec.payload))
    if spec.body_kind == "form":
        assert isinstance(spec.payload, dict)
        return ("body", f"new URLSearchParams({render_obj(spec.payload)})")
    assert isinstance(spec.payload, PlaceholderTemplate)
    return ("body", render_value(spec.payload))


# ===========================================================================
# Condition check rendering
# ===========================================================================


def _js_path_expr(body_var: str, path: str) -> str:
    """Build a safe JavaScript optional-chaining access expression for a dot-path.

    Args:
        body_var (str): Identifier of the parsed JSON body variable.
        path (str): Dot-separated property path.

    Returns:
        str: JavaScript optional-chaining bracket-access expression.
    """
    expr = body_var
    for seg in path.split("."):
        if seg.isdigit():
            expr += f"?.[{seg}]"
        else:
            expr += f"?.[{seg!r}]"
    return expr


def render_js_condition_check(
    required_keys: list[str], conditions: dict[str, object]
) -> str | None:
    """Render an arrow function checking required keys and field conditions on `_b`.

    Args:
        required_keys (list[str]): Top-level or dot-path keys that must exist in `_b`.
        conditions (dict[str, object]): Dot-paths mapped to expected literal values.

    Returns:
        str | None: JavaScript `(_b) => ...` predicate expression, or `None` if no checks apply.
    """
    parts: list[str] = []
    for key in required_keys:
        if "." in key:
            parts.append(f"{_js_path_expr('_b', key)} !== undefined")
        else:
            parts.append(f"{key!r} in _b")
    for path, value in conditions.items():
        lhs = _js_path_expr("_b", path)
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
    """Convert a DSL identifier into a camelCase JavaScript identifier.

    Args:
        name (str): Raw DSL identifier string.

    Returns:
        str: camelCase JavaScript identifier.
    """
    return to_camel_case(to_snake_case(name))


def ok_payload_type(node: MethodRest) -> str:
    """Resolve the JSDoc type expression for the `Ok<T>` payload of a `MethodRest` node.

    Args:
        node (MethodRest): REST endpoint method AST node.

    Returns:
        str: JSDoc type string for the successful response value.
    """
    if not node.response_schema:
        return "null"
    module = find_enclosing_module(node)
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


def _render_dsl_opts(
    spec: RequestHttp,
    *,
    response_path: str = "",
    response_join: str = "",
) -> str:
    """Render the JavaScript DSL request options object literal passed to runtime helpers.

    Args:
        spec (RequestHttp): HTTP request specification AST node.
        response_path (str): Optional dot-path to extract from the response body.
        response_join (str): Optional delimiter used to join array fragments.

    Returns:
        str: JavaScript object literal expression (e.g. `"{params: ..., headers: ...}"` or `"{}"`).
    """
    opts_parts: list[str] = []
    if spec.params:
        opts_parts.append(f"params: {render_obj(spec.params)}")
    if spec.headers:
        opts_parts.append(f"headers: {render_obj(spec.headers)}")
    body_result = render_body(spec)
    if body_result:
        opts_parts.append(f"body: {body_result[1]}")
    if response_path:
        opts_parts.append(f"responsePath: {response_path!r}")
    if response_join:
        opts_parts.append(f"responseJoin: {response_join!r}")
    return "{" + ", ".join(opts_parts) + "}" if opts_parts else "{}"


def _placeholder_param(spec: RequestHttp) -> str:
    """Format the destructured placeholder parameter declaration for a JS request method.

    Args:
        spec (RequestHttp): HTTP request specification containing placeholders.

    Returns:
        str: Leading `, {a, b}` parameter fragment, or `""` if there are no placeholders.
    """
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
    """Emit a static async JavaScript REST endpoint method for a `MethodRest` node.

    Args:
        node (MethodRest): AST node describing the REST endpoint request.
        ctx (WalkContext): Traversal context providing indentation and metadata.
        http (JsHttpLibStrategy): Active JavaScript HTTP transport strategy.

    Returns:
        list[str]: Generated JavaScript JSDoc and method lines.
    """
    spec = node.http_request.with_renamed_placeholders(js_name)
    ind = ctx.indent_char
    i1, i2 = ctx.indent, ctx.indent + ind

    ph_param = _placeholder_param(spec)
    url_expr = render_value(spec.url)
    dsl_opts = _render_dsl_opts(spec)

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
    module = find_enclosing_module(node)
    has_response_schema = False
    if node.response_schema and module is not None:
        has_response_schema = any(
            isinstance(n, JsonDef) and n.name == node.response_schema
            for n in module.body
        )

    if node.response_path:
        accessor = "".join(
            f"[{json.dumps(p)}]" for p in node.response_path.split(".")
        )
        if has_response_schema:
            proj_fn = js_json_projector_name(node.response_schema)
            value_fn = f"(_b) => {proj_fn}(_b{accessor})"
        else:
            value_fn = f"(_b) => _b{accessor}"
    elif not node.response_schema:
        value_fn = "(_b) => null"
    elif has_response_schema:
        proj_fn = js_json_projector_name(node.response_schema)
        value_fn = f"(_b) => {proj_fn}(_b)"
    else:
        value_fn = "null"

    lines: list[str] = []
    if node.doc:
        lines.append(f"{i1}/**")
        for doc_line in node.doc.splitlines():
            safe_doc_line = doc_line.replace("*/", "*\\/")
            lines.append(
                f"{i1} * {safe_doc_line}" if safe_doc_line else f"{i1} *"
            )
        lines.append(f"{i1} */")
    lines.append(f"{i1}/**")
    for p in sorted(spec.placeholders, key=lambda p: p.is_optional):
        t = _JS_PRIM_JSDOC[p.type_name]
        if p.is_array:
            t = f"{t}[]"
        bracket = f"[params.{p.name}]" if p.is_optional else f"params.{p.name}"
        lines.append(f"{i1} * @param {{{t}}} {bracket}")
    lines.append(
        f"{i1} * @param {{Object}} [opts] per-call request options (headers, etc.)"
    )
    lines.append(f"{i1} * @returns {{Promise<{return_union}>}}")
    lines.append(f"{i1} */")
    lines.append(
        f"{i1}static async {method_name}(client{ph_param}, opts = {{}}) {{"
    )
    lines.append(
        f"{i2}return {fn_name}(client, {matchers_var}, "
        f"{spec.method!r}, {url_expr}, {value_fn}, {dsl_opts}, opts);"
    )
    lines.append(f"{i1}}}")
    return lines


def emit_method_fetch(
    node: MethodFetch, ctx: WalkContext, http: JsHttpLibStrategy
) -> list[str]:
    """Emit a static async JavaScript document `fetch` method for a `MethodFetch` node.

    Args:
        node (MethodFetch): AST node describing the document fetch request.
        ctx (WalkContext): Traversal context providing indentation and metadata.
        http (JsHttpLibStrategy): Active JavaScript HTTP transport strategy.

    Returns:
        list[str]: Generated JavaScript JSDoc and method lines.
    """
    spec = node.http_request.with_renamed_placeholders(js_name)
    ind = ctx.indent_char
    i1, i2 = ctx.indent, ctx.indent + ind

    ph_param = _placeholder_param(spec)
    url_expr = render_value(spec.url)
    dsl_opts = _render_dsl_opts(
        spec,
        response_path=node.response_path,
        response_join=node.response_join,
    )

    struct_name = to_pascal_case(node.parent.name)  # type: ignore[union-attr]
    method_name = "fetch" + (to_pascal_case(node.name) if node.name else "")
    fetch_fn = http.fetch_fn_name

    lines: list[str] = []
    doc = getattr(node, "doc", "")
    if doc:
        lines.append(f"{i1}/**")
        for doc_line in doc.splitlines():
            safe_doc_line = doc_line.replace("*/", "*\\/")
            lines.append(
                f"{i1} * {safe_doc_line}" if safe_doc_line else f"{i1} *"
            )
        lines.append(f"{i1} */")
    lines.extend(
        [
            f"{i1}static async {method_name}(client{ph_param}, opts = {{}}) {{",
            f"{i2}return new {struct_name}(await {fetch_fn}(client, {spec.method!r}, {url_expr}, {dsl_opts}, opts));",
            f"{i1}}}",
        ]
    )
    return lines


def emit_result_variant_def(node: ResultVariantDef) -> list[str]:
    """Emit a JSDoc `@typedef` block for a `ResultVariantDef` error variant.

    Args:
        node (ResultVariantDef): Error variant AST node.

    Returns:
        list[str]: Generated JSDoc `@typedef` comment lines.
    """
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
    """Emit a `ResultAliasDef` node (no-op in JavaScript, which inlines return unions).

    Args:
        node (ResultAliasDef): Result alias AST node.

    Returns:
        list[str]: Empty list.
    """
    return []


def emit_matcher_list_def(node: MatcherListDef) -> list[str]:
    """Emit the `const _<struct>Matchers = [...]` array for a REST struct.

    Args:
        node (MatcherListDef): Matcher list AST node.

    Returns:
        list[str]: Generated JavaScript matcher array lines.
    """
    var = f"_{to_snake_case(node.struct_name)}Matchers"
    lines = [f"const {var} = ["]
    module = find_enclosing_module(node)
    definitions = (
        {n.name: n for n in module.body if isinstance(n, JsonDef)}
        if module is not None
        else {}
    )
    for e in node.entries:
        check = render_js_condition_check(e.required_keys, e.conditions)
        check_arg = check if check else "null"
        proj_fn = None
        if e.error_schema and e.error_schema in definitions:
            proj_fn = js_json_projector_name(e.error_schema)
        value_expr = f"{proj_fn}(_b)" if proj_fn is not None else "_b"
        lines.append(
            f"    {{ status: {e.status}, check: {check_arg}, "
            f"factory: (_s, _h, _b) => ({{ isOk: false, status: _s, "
            f"headers: _h, value: {value_expr} }}) }},"
        )
    lines.append("];")
    return lines
