"""Pure ES6 JS (DOM) codegen on the new Visitor API.

Emits plain JavaScript using the browser/DOM API (``querySelector`` etc.),
suitable for modern browsers and the Node.js + jsdom test runner.

Codegen notations:

- ES8 required if ``re.DOTALL`` regex flag is needed, otherwise ES6.
- Annotations are generated in JSDoc format.
- Method (field) names are converted to ``_parseUpperCamelCase``.
"""

from ssc_codegen.ast import (
    Attr,
    Assert,
    CheckMethod,
    CodeEndHook,
    CodeStartHook,
    CssRemove,
    CssSelect,
    CssSelectAll,
    Docstring,
    ErrorResponse,
    Fallback,
    Field,
    Filter,
    Fmt,
    Init,
    InitField,
    Index,
    JsonDef,
    JsonDefField,
    Jsonify,
    Join,
    Key,
    Len,
    LogicAnd,
    LogicNot,
    LogicOr,
    Lower,
    Ltrim,
    Match,
    MethodBase,
    MethodFetch,
    MethodRest,
    Module,
    Nested,
    NormalizeSpace,
    PlaceholderSpec,
    PreValidate,
    PredAttrContains,
    PredAttrEnds,
    PredAttrEq,
    PredAttrNe,
    PredAttrRe,
    PredAttrStarts,
    PredContains,
    PredCountEq,
    PredCountGe,
    PredCountGt,
    PredCountLe,
    PredCountLt,
    PredCountNe,
    PredCountRange,
    PredCss,
    PredEnds,
    PredEq,
    PredHasAttr,
    PredNe,
    PredRe,
    PredReAll,
    PredReAny,
    PredStarts,
    PredTextContains,
    PredTextEnds,
    PredTextRe,
    PredTextStarts,
    PredXpath,
    Raw,
    Re,
    ReAll,
    ReSub,
    Repl,
    ReplMap,
    Return,
    RmPrefix,
    RmPrefixSuffix,
    RmSuffix,
    Rtrim,
    Self,
    Slice,
    Split,
    SplitDoc,
    StartParse,
    Struct,
    StructBase,
    StructDocstring,
    StructRest,
    StructType as ST,
    TableConfig,
    TableMatchKey,
    TableRows,
    Text,
    ToBool,
    ToFloat,
    ToInt,
    Trim,
    TypeDef,
    TypeDefField,
    TypeInfo,
    Unique,
    Unescape,
    Upper,
    Utilities,
    Value,
    VariableType as VT,
    XpathRemove,
    XpathSelect,
    XpathSelectAll,
)
from ssc_codegen.converters.base import ConverterContext
from ssc_codegen.converters.helpers import (
    jsonify_path_to_segments,
    to_camel_case,
    to_pascal_case,
    to_snake_case,
)
from ssc_codegen.converters.visitor import (
    STD,
    TRAVERSE,
    VisitStream,
    Visitor,
)
from ssc_codegen.request_spec import (
    RequestSpec,
    normalize_placeholder_names,
)

import re as _re

# ===========================================================================
# Helpers
# ===========================================================================


def _js_str(value: str) -> str:
    return (
        "`"
        + value.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
        + "`"
    )


def _js_re(pattern: str) -> str:
    flags = ""
    m = _re.match(r"^\(\?([a-z]+)\)", pattern)
    if m:
        flags = "".join(c for c in m.group(1) if c in "ims")
        pattern = pattern[m.end() :]
    escaped = pattern.replace("/", "\\/")
    return f"/{escaped}/{flags}"


def _js_re_node(node) -> str:
    return _js_re(node.pattern)


def py_sequence_to_js_array(values) -> str:
    val_arr = str(tuple(values))
    return "[" + val_arr[1:-1] + "]"


def _js_literal(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return repr(value)


def _and(cond: str, ctx: ConverterContext) -> str:
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + "&& " + cond


def _logic_prefix(op: str, ctx: ConverterContext) -> str:
    if ctx.index == 0:
        return ctx.indent + "("
    return ctx.indent + f"{op} ("


def _js_docblock(lines: list[str]) -> list[str]:
    if not lines:
        return []
    return ["/**", *(f" * {line}" if line else " *" for line in lines), " */"]


def _find_predicate_container(node):
    cur = node.parent
    while cur:
        if isinstance(cur, (Filter, Assert, Match, PreValidate)):
            return cur
        cur = cur.parent
    return None


def _pred_target(node, ctx: ConverterContext) -> str:
    container = _find_predicate_container(node)
    if isinstance(container, Filter):
        return "i"
    if isinstance(container, (Match, Assert, PreValidate)):
        return getattr(container, "_local_name", "i")
    return ctx.prv


def _pred_text_target(node, ctx: ConverterContext) -> str:
    target = _pred_target(node, ctx)
    container = _find_predicate_container(node)
    if target == "i" and isinstance(container, Filter):
        return "i.textContent"
    return target


def _pred_attr_target(node, ctx: ConverterContext) -> str:
    return _pred_target(node, ctx)


JS_TYPES = {
    VT.STRING: "string",
    VT.BOOL: "boolean",
    VT.INT: "number",
    VT.FLOAT: "number",
    VT.NULL: "null",
    VT.DOCUMENT: "Element",
    VT.JSON: "Any",
    VT.NESTED: "Any",
    VT.AUTO: "Any",
}


def _resolve_js_type(type_info: TypeInfo | None) -> str:
    if type_info is None:
        return "?"
    if type_info.base == VT.NESTED and type_info.ref:
        type_ = f"{to_pascal_case(type_info.ref)}Type"
    elif type_info.base == VT.JSON and type_info.ref:
        type_ = f"{to_pascal_case(type_info.ref)}Json"
    else:
        type_ = JS_TYPES.get(type_info.base, "?")
    if type_info.is_array:
        type_ = f"Array<{type_}>"
    if type_info.is_optional:
        type_ = f"({type_}|null)"
    return type_


# ===========================================================================
# REST infrastructure
# ===========================================================================


def module_has_rest(module: Module) -> bool:
    return any(isinstance(n, StructRest) for n in module.body)


def _js_err_subclass_name(struct_name: str, err: ErrorResponse) -> str:
    base = f"{to_pascal_case(struct_name)}Err{err.status}"
    for key in err.required_keys:
        base += to_pascal_case(key.replace(".", "_").replace("-", "_"))
    if err.conditions:
        for key in err.conditions:
            base += to_pascal_case(key.replace(".", "_").replace("-", "_"))
    return base


def _js_resolve_path_expr(body_var: str, path: str) -> str:
    expr = body_var
    for seg in path.split("."):
        if seg.isdigit():
            expr += f"[{seg}]"
        else:
            expr += f"[{seg!r}]"
    return expr


def _js_condition_check_expr(err: ErrorResponse) -> str:
    parts: list[str] = []
    for key in err.required_keys:
        parts.append(f"{key!r} in _body")
    for path, value in err.conditions.items():
        lhs = _js_resolve_path_expr("_body", path)
        if isinstance(value, bool):
            parts.append(f"{lhs} === {str(value).lower()}")
        elif value is None:
            parts.append(f"{lhs} === null")
        elif isinstance(value, (int, float)):
            parts.append(f"{lhs} === {value}")
        else:
            parts.append(f"{lhs} === {value!r}")
    return " && ".join(parts)


def _js_err_value_type(err: ErrorResponse, struct: StructBase) -> str:
    schema = err.schema_name
    if not schema:
        return "*"
    type_name = f"{to_pascal_case(schema)}Json"
    module = struct.parent
    if module is not None:
        for n in module.body:
            if isinstance(n, JsonDef) and n.name == schema and n.is_array:
                return f"Array<{type_name}>"
    return type_name


REST_TYPEDEFS: list[str] = [
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
    "async function sscParseResponse(_resp) {",
    "    const _status = _resp.status;",
    "    const _headers = Object.fromEntries([..._resp.headers.entries()]);",
    "    let _body = null;",
    "    try { _body = await _resp.json(); } catch (e) {}",
    "    return [_status, _headers, _body];",
    "}",
    "",
    "function sscParseResponseAxios(_resp) {",
    "    const _status = _resp.status;",
    "    const _headers = {};",
    "    for (const [k, v] of Object.entries(_resp.headers || {})) "
    "{ _headers[String(k).toLowerCase()] = String(v); }",
    "    return [_status, _headers, _resp.data];",
    "}",
    "",
]


def _emit_dispatch_err_js(node: StructRest, ctx: ConverterContext) -> list[str]:
    i1 = ctx.indent
    i2 = i1 + ctx.indent_char
    i3 = i2 + ctx.indent_char

    errors = node.errors
    status_errors = [
        e for e in errors if not e.conditions and not e.required_keys
    ]
    field_errors = [e for e in errors if e.conditions or e.required_keys]

    lines: list[str] = [
        f"{i1}static sscDispatchErr(_status, _headers, _body) {{",
        f"{i2}if (_status >= 200 && _status < 300) {{",
    ]
    for err in field_errors:
        if 200 <= err.status < 300:
            cond = _js_condition_check_expr(err)
            lines.append(
                f"{i3}if (_status === {err.status} && _body "
                f"&& _body instanceof Object && {cond}) {{"
            )
            lines.append(
                f"{i3}{ctx.indent_char}return {{ isOk: false, "
                f"status: _status, headers: _headers, value: _body }};"
            )
            lines.append(f"{i3}}}")
    lines.append(f"{i3}return null;")
    lines.append(f"{i2}}}")

    for err in status_errors:
        lines.append(f"{i2}if (_status === {err.status}) {{")
        lines.append(
            f"{i3}return {{ isOk: false, status: _status, "
            f"headers: _headers, value: _body }};"
        )
        lines.append(f"{i2}}}")
    for err in field_errors:
        if not (200 <= err.status < 300):
            cond = _js_condition_check_expr(err)
            lines.append(
                f"{i2}if (_status === {err.status} && _body "
                f"&& _body instanceof Object && {cond}) {{"
            )
            lines.append(
                f"{i3}return {{ isOk: false, status: _status, "
                f"headers: _headers, value: _body }};"
            )
            lines.append(f"{i2}}}")

    lines.append(
        f"{i2}return {{ isOk: false, status: _status, "
        f"headers: _headers, value: _body }};"
    )
    lines.append(f"{i1}}}")
    return lines


# ===========================================================================
# StartParse helpers
# ===========================================================================

_JS_PARSE_RETURN_TYPE = {
    Struct: "{}Type",
    "list": "Array<{}Type>",
    "flat": "Array<string>",
    "dict": "{}Type",
    "table": "{}Type",
}


def _js_method_name(field_name: str) -> str:
    n = to_camel_case(field_name)
    return f"_parse{n[0].upper() + n[1:]}"


def _js_struct_header(node: StructBase) -> list[str]:
    doc_lines = _js_docblock(node.doc.splitlines()) if node.doc else []
    return [*doc_lines, f"class {to_pascal_case(node.name)} {{"]


# ===========================================================================
# @request helpers
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


def _js_render_value(v: str) -> str:
    if ph := PlaceholderSpec.parse(v):
        if ph.is_array and ph.style in ("csv", "pipe", "space"):
            return _js_array_join(ph)
        return ph.name
    if PlaceholderSpec.search(v):
        inner = v.replace("\\", "\\\\").replace("`", "\\`")
        inner = PlaceholderSpec.sub(inner, lambda ph: "${" + ph.name + "}")
        return f"`{inner}`"
    return repr(v)


def _js_render_obj(d: dict[str, str]) -> str:
    if not d:
        return "{}"
    inner = ", ".join(
        f"{k!r}: {_js_render_value(str(v))}" for k, v in d.items()
    )
    return "{" + inner + "}"


def _js_dict_entry_placeholder(v: str) -> PlaceholderSpec | None:
    return PlaceholderSpec.parse(str(v))


def _js_dict_needs_builder(d: dict[str, str]) -> bool:
    for v in d.values():
        ph = _js_dict_entry_placeholder(str(v))
        if ph is None:
            continue
        if ph.is_optional or ph.is_array:
            return True
    return False


def _js_emit_obj_builder(
    varname: str, d: dict[str, str], indent: str
) -> list[str]:
    lines = [f"{indent}const {varname} = {{}};"]
    for key, value in d.items():
        value = str(value)
        ph = _js_dict_entry_placeholder(value)
        expr = _js_render_value(value)
        if ph is not None and ph.is_optional:
            lines.append(
                f"{indent}if ({ph.name} !== undefined && {ph.name} !== null) "
                f"{varname}[{key!r}] = {expr};"
            )
        else:
            lines.append(f"{indent}{varname}[{key!r}] = {expr};")
    return lines


def _js_emit_params_builder(
    varname: str, d: dict[str, str], indent: str
) -> list[str]:
    lines = [f"{indent}const {varname} = new URLSearchParams();"]
    for key, value in d.items():
        value = str(value)
        ph = _js_dict_entry_placeholder(value)
        if ph is None:
            lines.append(
                f"{indent}{varname}.set({key!r}, {_js_render_value(value)});"
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


def _js_render_json_body(raw: str) -> str:
    inner = raw.replace("\\", "\\\\").replace("`", "\\`")
    inner = PlaceholderSpec.sub(inner, lambda ph: "${" + ph.name + "}")
    return f"`{inner}`"


def _js_render_body(spec: RequestSpec) -> tuple[str, str] | None:
    if spec.body_kind == "empty" or spec.body is None:
        return None
    if spec.body_kind == "json":
        return ("body", _js_render_json_body(str(spec.body)))
    if spec.body_kind == "form":
        assert isinstance(spec.body, dict)
        return ("body", f"new URLSearchParams({_js_render_obj(spec.body)})")
    return ("body", _js_render_value(str(spec.body)))


def _js_name(name: str) -> str:
    return to_camel_case(to_snake_case(name))


def _js_build_request_args(node: MethodBase, ctx: ConverterContext):
    http = node.http_request
    spec = normalize_placeholder_names(
        RequestSpec(
            method=http.method,
            url=http.url,
            headers=dict(http.headers),
            cookies=dict(http.cookies),
            params=dict(http.params),
            body_kind=http.body_kind,
            body=http.body,
        ),
        _js_name,
    )
    http_client = ctx.meta.get("http_client", "fetch")
    ind = ctx.indent_char
    i1, i2, i3, i4 = (ctx.indent + ind * n for n in range(4))

    ph_param = ""
    if spec.placeholders:
        ordered = [
            p.name
            for p in sorted(spec.placeholders, key=lambda p: p.is_optional)
        ]
        ph_param = ", {" + ", ".join(ordered) + "}"

    pre_lines: list[str] = []

    def _resolve(d, varname, builder_fn):
        if not d:
            return None
        if _js_dict_needs_builder(d):
            pre_lines.extend(builder_fn(varname, d, i3))
            return varname
        return _js_render_obj(d)

    params_expr = _resolve(spec.params, "_params", _js_emit_params_builder)
    headers_expr = _resolve(spec.headers, "_headers", _js_emit_obj_builder)
    cookies_expr = _resolve(spec.cookies, "_cookies", _js_emit_obj_builder)

    body_result = _js_render_body(spec)
    body_expr = body_result[1] if body_result else None

    return (
        spec,
        pre_lines,
        ph_param,
        http_client,
        params_expr,
        headers_expr,
        cookies_expr,
        body_expr,
        i1,
        i2,
        i3,
        i4,
    )


def _js_ok_payload_type(node: MethodRest) -> str:
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
# Visitor
# ===========================================================================


class JsPure(Visitor):
    """Pure ES6 JS (DOM API) codegen."""

    def __init__(self, var_name: str = "v", indent: str = " " * 2) -> None:
        super().__init__(var_name=var_name, indent=indent)

    # === module ===

    def visit_module(self, node: Module, ctx: ConverterContext) -> VisitStream:
        if node.doc:
            yield from _js_docblock(node.doc.splitlines())
        yield '"use strict";'
        yield "// autogenerated by ssc-gen. DO NOT EDIT"

    def visit_docstring(
        self, node: Docstring, ctx: ConverterContext
    ) -> VisitStream:
        return

    def visit_utilities(
        self, node: Utilities, ctx: ConverterContext
    ) -> VisitStream:
        yield "const UNMATCHED_TABLE_ROW = Symbol('UNMATCHED_TABLE_ROW');"
        yield ""
        mod = node.parent
        if isinstance(mod, Module) and module_has_rest(mod):
            yield REST_TYPEDEFS
        result = super().visit_utilities(node, ctx)
        if result is not None:
            yield from result

    def visit_code_start_hook(
        self, node: CodeStartHook, ctx: ConverterContext
    ) -> VisitStream:
        return

    def visit_code_end_hook(
        self, node: CodeEndHook, ctx: ConverterContext
    ) -> VisitStream:
        return

    def visit_struct_docstring(
        self, node: StructDocstring, ctx: ConverterContext
    ) -> VisitStream:
        return

    def visit_error_response(
        self, node: ErrorResponse, ctx: ConverterContext
    ) -> VisitStream:
        return

    # === types ===

    def visit_jsondef(
        self, node: JsonDef, ctx: ConverterContext
    ) -> VisitStream:
        name = to_pascal_case(node.name)
        yield ["/**", f" * @typedef {{Object}} {name}Json"]
        yield TRAVERSE
        yield " */"

    def visit_jsondef_field(
        self, node: JsonDefField, ctx: ConverterContext
    ) -> VisitStream:
        if node.type_info and node.type_info.skip:
            return
        name = node.alias if node.alias else node.name
        type_ = _resolve_js_type(node.type_info)
        if node.type_info and (
            node.type_info.is_optional or node.type_info.omitempty
        ):
            type_ = f"{type_}="
        yield f" * @property {{{type_}}} {name}"

    def visit_typedef(
        self, node: TypeDef, ctx: ConverterContext
    ) -> VisitStream:
        if node.struct_type == ST.REST:
            return
        name = to_pascal_case(node.name)
        if node.struct_type == ST.FLAT:
            yield f"/** @typedef {{Array<string>}} {name}Type */"
            return
        if node.struct_type == ST.DICT:
            value_field = next(
                f for f in node.fields if to_camel_case(f.name) == "value"
            )
            value_type = _resolve_js_type(value_field.type_info)
            yield [
                "/**",
                f" * @typedef {{Object.<string, {value_type}>}} {name}Type",
            ]
            yield TRAVERSE
            yield " */"
            return
        yield ["/**", f" * @typedef {{Object}} {name}Type"]
        yield TRAVERSE
        yield " */"

    def visit_typedef_field(
        self, node: TypeDefField, ctx: ConverterContext
    ) -> VisitStream:
        if node.typedef.struct_type in (ST.DICT, ST.FLAT):
            return
        name = to_camel_case(node.name)
        if node.typedef.struct_type == ST.TABLE and name == "value":
            return
        type_ = _resolve_js_type(node.type_info)
        yield f" * @property {{{type_}}} {name}"

    # === struct ===

    def visit_struct(self, node: Struct, ctx: ConverterContext) -> VisitStream:
        yield _js_struct_header(node)
        yield TRAVERSE
        yield "}"

    def visit_struct_rest(
        self, node: StructRest, ctx: ConverterContext
    ) -> VisitStream:
        seen: set[str] = set()
        for err in node.errors:
            cls_name = _js_err_subclass_name(node.name, err)
            if cls_name in seen:
                continue
            seen.add(cls_name)
            value_type = _js_err_value_type(err, node)
            yield [
                "/**",
                f" * @typedef {{Object}} {cls_name}",
                " * @property {false} isOk",
                f" * @property {{{err.status}}} status",
                " * @property {Object<string, string>} headers",
                f" * @property {{{value_type}}} value",
                " */",
                "",
            ]
        yield _js_struct_header(node)
        yield _emit_dispatch_err_js(node, ctx.deeper())
        yield TRAVERSE
        yield "}"

    def visit_init(self, node: Init, ctx: ConverterContext) -> VisitStream:
        if isinstance(node.parent, StructRest):
            return
        init_names = [
            to_camel_case(i.name) for i in node.body if isinstance(i, InitField)
        ]
        i1, i2, i3 = ctx.indent, ctx.indent * 2, ctx.indent * 3
        yield f"{i1}constructor(document) {{"
        yield f"{i2}if (typeof document === 'string') {{"
        yield f"{i3}const _p = new DOMParser();"
        yield f"{i3}this._doc = _p.parseFromString(document, 'text/html');"
        yield f"{i2}}} else {{"
        yield f"{i3}this._doc = document;"
        yield f"{i2}}}"
        for name in init_names:
            cap = name[0].upper() + name[1:]
            yield f"{i2}this._{name} = this._init{cap}(this._doc);"
        yield f"{i1}}}"
        # Emit the _init<Name> method definitions at class-body level.
        # The framework's InitField special-case (_emit_pipeline at same depth)
        # miscalculates indentation, so we emit header + body manually:
        # header at class-body depth, pipeline body one level deeper.
        for child in node.body:
            if isinstance(child, InitField):
                cname = to_camel_case(child.name)
                cap = cname[0].upper() + cname[1:]
                yield f"{i1}_init{cap}(v) {{"
                yield self._emit_pipeline(child.body, ctx.deeper())
                yield f"{i1}}}"

    def visit_init_field(
        self, node: InitField, ctx: ConverterContext
    ) -> VisitStream:
        name = to_camel_case(node.name)
        cap = name[0].upper() + name[1:]
        yield f"{ctx.indent}_init{cap}(v) {{"
        yield TRAVERSE
        yield f"{ctx.indent}}}"

    def visit_field(self, node: Field, ctx: ConverterContext) -> VisitStream:
        name = to_camel_case(node.name)
        cap = name[0].upper() + name[1:]
        yield f"{ctx.indent}_parse{cap}(v) {{"
        yield TRAVERSE
        yield f"{ctx.indent}}}"

    def visit_pre_validate(
        self, node: PreValidate, ctx: ConverterContext
    ) -> VisitStream:
        yield f"{ctx.indent}_preValidate(v) {{"
        yield TRAVERSE
        yield f"{ctx.indent}}}"

    def visit_check_method(
        self, node: CheckMethod, ctx: ConverterContext
    ) -> VisitStream:
        method_name = to_camel_case(node.name)
        yield [
            f"{ctx.indent}{method_name}() {{",
            f"{ctx.deeper().indent}let {ctx.var_name} = this._doc;",
        ]
        yield TRAVERSE
        yield "}"

    def visit_split_doc(
        self, node: SplitDoc, ctx: ConverterContext
    ) -> VisitStream:
        yield f"{ctx.indent}_splitDoc(v) {{"
        yield TRAVERSE
        yield f"{ctx.indent}}}"

    def visit_key(self, node: Key, ctx: ConverterContext) -> VisitStream:
        yield f"{ctx.indent}_parseKey(v) {{"
        yield TRAVERSE
        yield f"{ctx.indent}}}"

    def visit_value(self, node: Value, ctx: ConverterContext) -> VisitStream:
        yield f"{ctx.indent}_parseValue(v) {{"
        yield TRAVERSE
        yield f"{ctx.indent}}}"

    def visit_table_config(
        self, node: TableConfig, ctx: ConverterContext
    ) -> VisitStream:
        yield f"{ctx.indent}_tableConfig(v) {{"
        yield TRAVERSE
        yield f"{ctx.indent}}}"

    def visit_table_match_key(
        self, node: TableMatchKey, ctx: ConverterContext
    ) -> VisitStream:
        yield f"{ctx.indent}_tableMatchKey(v) {{"
        yield TRAVERSE
        yield f"{ctx.indent}}}"

    def visit_table_rows(
        self, node: TableRows, ctx: ConverterContext
    ) -> VisitStream:
        yield f"{ctx.indent}_tableRows(v) {{"
        yield TRAVERSE
        yield f"{ctx.indent}}}"

    # === start_parse ===

    def visit_start_parse(
        self, node: StartParse, ctx: ConverterContext
    ) -> VisitStream:
        struct = node.struct
        name = to_pascal_case(struct.name)
        st = struct.type
        if st == ST.ITEM:
            ret_type = f"{name}Type"
        elif st == ST.LIST:
            ret_type = f"Array<{name}Type>"
        elif st == ST.FLAT:
            ret_type = "Array<string>"
        else:
            ret_type = f"{name}Type"
        i1, i2, i3 = ctx.indent, ctx.indent * 2, ctx.indent * 3
        yield [
            f"{i1}/**",
            f"{i1}* @returns {{{ret_type}}}",
            f"{i1}*/",
            f"{i1}parse() {{",
        ]
        if node.use_pre_validate:
            yield f"{i2}this._preValidate(this._doc);"
        if st == ST.ITEM:
            yield f"{i2}return {{"
            for f in node.fields:
                n = to_camel_case(f.name)
                yield f"{i3}{n}: this.{_js_method_name(f.name)}(this._doc),"
            yield f"{i2}}};"
        elif st == ST.LIST:
            yield f"{i2}return Array.from(this._splitDoc(this._doc)).map(i => ({{"
            for f in node.fields:
                n = to_camel_case(f.name)
                yield f"{i3}{n}: this.{_js_method_name(f.name)}(i),"
            yield f"{i2}}}));"
        elif st == ST.FLAT:
            yield f"{i2}let _result = [];"
            for f in node.fields:
                mname = _js_method_name(f.name)
                if f.ret_type_info.is_array:
                    yield f"{i2}_result = _result.concat(this.{mname}(this._doc));"
                else:
                    yield f"{i2}_result.push(this.{mname}(this._doc));"
            if struct.keep_order:
                yield f"{i2}return [...new Map(_result.map(x=>[x,x])).keys()];"
            else:
                yield f"{i2}return [...new Set(_result)];"
        elif st == ST.DICT:
            yield [
                f"{i2}return Array.from(this._splitDoc(this._doc)).reduce((acc, e) => {{",
                f"{i3}acc[this._parseKey(e)] = this._parseValue(e);",
                f"{i3}return acc;",
                f"{i2}}}, {{}});",
            ]
        elif st == ST.TABLE:
            yield f"{i2}let _result = {{}};"
            yield f"{i2}let _table = this._tableConfig(this._doc);"
            yield f"{i2}for (let _row of this._tableRows(_table)) {{"
            for f in node.fields:
                n = to_camel_case(f.name)
                yield f"{i3}let _{n} = this.{_js_method_name(f.name)}(_row);"
                yield (
                    f"{i3}if (_{n} !== UNMATCHED_TABLE_ROW "
                    f"&& !Object.prototype.hasOwnProperty.call(_result, {n!r})) "
                    f"_result[{n!r}] = _{n};"
                )
            yield f"{i2}}}"
            yield f"{i2}return _result;"
        yield f"{i1}}}"

    # === selectors ===

    def visit_css_select(
        self, node: CssSelect, ctx: ConverterContext
    ) -> VisitStream:
        if node.queries:
            lines: list[str] = []
            for i, query in enumerate(node.queries):
                q = repr(query)
                if i == 0:
                    lines.append(
                        f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.querySelector({q});"
                    )
                else:
                    lines.append(
                        f"{ctx.indent}if ({ctx.nxt} === null) {ctx.nxt} = {ctx.prv}.querySelector({q});"
                    )
            yield lines
            return
        q = repr(node.query)
        yield f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.querySelector({q});"

    def visit_css_select_all(
        self, node: CssSelectAll, ctx: ConverterContext
    ) -> VisitStream:
        if node.queries:
            lines: list[str] = []
            for i, query in enumerate(node.queries):
                q = repr(query)
                if i == 0:
                    lines.append(
                        f"{ctx.indent}let {ctx.nxt} = Array.from({ctx.prv}.querySelectorAll({q}));"
                    )
                else:
                    lines.append(
                        f"{ctx.indent}if ({ctx.nxt}.length === 0) {ctx.nxt} = Array.from({ctx.prv}.querySelectorAll({q}));"
                    )
            yield lines
            return
        q = repr(node.query)
        yield f"{ctx.indent}let {ctx.nxt} = Array.from({ctx.prv}.querySelectorAll({q}));"

    def visit_css_remove(
        self, node: CssRemove, ctx: ConverterContext
    ) -> VisitStream:
        q = repr(node.query)
        yield [
            f"{ctx.indent}{ctx.prv}.querySelectorAll({q}).forEach(e => e.remove());",
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv};",
        ]

    def visit_xpath_select(
        self, node: XpathSelect, ctx: ConverterContext
    ) -> VisitStream:
        if node.queries:
            lines: list[str] = []
            for i, query in enumerate(node.queries):
                q = repr(query)
                if i == 0:
                    lines.extend(
                        [
                            f"{ctx.indent}let xr{ctx.nxt} = document.evaluate({q}, {ctx.prv}, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);",
                            f"{ctx.indent}let {ctx.nxt} = xr{ctx.nxt}.singleNodeValue;",
                        ]
                    )
                else:
                    lines.extend(
                        [
                            f"{ctx.indent}if ({ctx.nxt} === null) {{",
                            f"{ctx.indent}    xr{ctx.nxt} = document.evaluate({q}, {ctx.prv}, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);",
                            f"{ctx.indent}    {ctx.nxt} = xr{ctx.nxt}.singleNodeValue;",
                            f"{ctx.indent}}}",
                        ]
                    )
            yield lines
            return
        q = repr(node.query)
        yield [
            f"{ctx.indent}let xr{ctx.nxt} = document.evaluate({q}, {ctx.prv}, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);",
            f"{ctx.indent}let {ctx.nxt} = xr{ctx.nxt}.singleNodeValue;",
        ]

    def visit_xpath_select_all(
        self, node: XpathSelectAll, ctx: ConverterContext
    ) -> VisitStream:
        if node.queries:
            lines: list[str] = []
            for i, query in enumerate(node.queries):
                q = repr(query)
                if i == 0:
                    lines.extend(
                        [
                            f"{ctx.indent}let xr{ctx.nxt} = document.evaluate({q}, {ctx.prv}, null, XPathResult.ORDERED_NODE_ITERATOR_TYPE, null);",
                            f"{ctx.indent}let {ctx.nxt} = []; let xrn{ctx.nxt} = xr{ctx.nxt}.iterateNext();",
                            f"{ctx.indent}while (xrn{ctx.nxt}) {{ {ctx.nxt}.push(xrn{ctx.nxt}); xrn{ctx.nxt} = xr{ctx.nxt}.iterateNext(); }}",
                        ]
                    )
                else:
                    lines.extend(
                        [
                            f"{ctx.indent}if ({ctx.nxt}.length === 0) {{",
                            f"{ctx.indent}    xr{ctx.nxt} = document.evaluate({q}, {ctx.prv}, null, XPathResult.ORDERED_NODE_ITERATOR_TYPE, null);",
                            f"{ctx.indent}    xrn{ctx.nxt} = xr{ctx.nxt}.iterateNext();",
                            f"{ctx.indent}    while (xrn{ctx.nxt}) {{ {ctx.nxt}.push(xrn{ctx.nxt}); xrn{ctx.nxt} = xr{ctx.nxt}.iterateNext(); }}",
                            f"{ctx.indent}}}",
                        ]
                    )
            yield lines
            return
        q = repr(node.query)
        yield [
            f"{ctx.indent}let xr{ctx.nxt} = document.evaluate({q}, {ctx.prv}, null, XPathResult.ORDERED_NODE_ITERATOR_TYPE, null);",
            f"{ctx.indent}let {ctx.nxt} = []; let xrn{ctx.nxt} = xr{ctx.nxt}.iterateNext();",
            f"{ctx.indent}while (xrn{ctx.nxt}) {{ {ctx.nxt}.push(xrn{ctx.nxt}); xrn{ctx.nxt} = xr{ctx.nxt}.iterateNext(); }}",
        ]

    def visit_xpath_remove(
        self, node: XpathRemove, ctx: ConverterContext
    ) -> VisitStream:
        q = repr(node.query)
        yield [
            f"for (let {ctx.prv}r = document.evaluate({q}, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null), {ctx.prv}i = {ctx.prv}r.snapshotLength; {ctx.prv}i--; ) {ctx.prv}r.snapshotItem({ctx.prv}i).remove();",
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv};",
        ]

    def visit_text(self, node: Text, ctx: ConverterContext) -> VisitStream:
        if not node.is_array:
            yield f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.textContent;"
        else:
            yield f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(el => el.textContent);"

    def visit_raw(self, node: Raw, ctx: ConverterContext) -> VisitStream:
        if not node.is_array:
            yield f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.outerHTML;"
        else:
            yield f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(el => el.outerHTML);"

    def visit_attr(self, node: Attr, ctx: ConverterContext) -> VisitStream:
        keys = node.keys
        if not node.is_array:
            if len(keys) == 1:
                yield f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.getAttribute({keys[0]!r});"
            else:
                kl = py_sequence_to_js_array(keys)
                yield f"{ctx.indent}let {ctx.nxt} = {kl}.map(k => {ctx.prv}.getAttribute(k)).filter(Boolean);"
            return
        if len(keys) == 1:
            yield f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(el => el.getAttribute({keys[0]!r}));"
        else:
            kl = py_sequence_to_js_array(keys)
            yield f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.flatMap(el => {kl}.map(k => el.getAttribute(k)).filter(Boolean));"

    # === string ===

    def visit_trim(self, node: Trim, ctx: ConverterContext) -> VisitStream:
        substr = node.substr
        if not node.is_array:
            if not substr:
                yield f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.trim();"
            else:
                yield [
                    f"{ctx.indent}let {ctx.nxt} = (function (str, chars) {{",
                    "return str.replace(new RegExp(`^[${chars}]+|[${chars}]+$`, 'g'), '');",
                    f"}})({ctx.prv}, {substr!r});",
                ]
            return
        if not substr:
            yield f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => s.trim());"
        else:
            yield [
                f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(e =>",
                "(function (str, chars) {",
                "return str.replace(new RegExp(`^[${chars}]+|[${chars}]+$`, 'g'), '');",
                f"}})(e, {substr!r})",
                ");",
            ]

    def visit_l_trim(self, node: Ltrim, ctx: ConverterContext) -> VisitStream:
        substr = node.substr
        if not node.is_array:
            if not substr:
                yield f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.trimStart();"
            else:
                yield [
                    f"{ctx.indent}let {ctx.nxt} = (function (str, chars) {{",
                    "return str.replace(new RegExp(`^[${chars}]+`, 'g'), '');",
                    f"}})({ctx.prv}, {substr!r});",
                ]
            return
        if not substr:
            yield f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => s.trimStart());"
        else:
            yield [
                f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(e =>",
                "(function (str, chars) {",
                "return str.replace(new RegExp(`^[${chars}]+`, 'g'), '');",
                f"}})(e, {substr!r})",
                ");",
            ]

    def visit_r_trim(self, node: Rtrim, ctx: ConverterContext) -> VisitStream:
        substr = node.substr
        if not node.is_array:
            if not substr:
                yield f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.trimEnd();"
            else:
                yield [
                    f"{ctx.indent}let {ctx.nxt} = (function (str, chars) {{",
                    "return str.replace(new RegExp(`[${chars}]+$`, 'g'), '');",
                    f"}})({ctx.prv}, {substr!r});",
                ]
            return
        if not substr:
            yield f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => s.trimEnd());"
        else:
            yield [
                f"let {ctx.nxt} = {ctx.prv}.map(e =>",
                "(function (str, chars) {",
                "return str.replace(new RegExp(`[${chars}]+$`, 'g'), '');",
                f"}})(e, {substr!r})",
                ");",
            ]

    def visit_rm_prefix(
        self, node: RmPrefix, ctx: ConverterContext
    ) -> VisitStream:
        yield STD(
            "_rmPrefix",
            code="function _rmPrefix(s, p) { return s.startsWith(p) ? s.slice(p.length) : s; }",
        )
        v = repr(node.substr)
        if not node.is_array:
            yield f"{ctx.indent}let {ctx.nxt} = _rmPrefix({ctx.prv}, {v});"
        else:
            yield f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => _rmPrefix(s, {v}));"

    def visit_rm_suffix(
        self, node: RmSuffix, ctx: ConverterContext
    ) -> VisitStream:
        yield STD(
            "_rmSuffix",
            code="function _rmSuffix(s, p) { return s.endsWith(p) ? s.slice(0, -p.length) : s; }",
        )
        v = repr(node.substr)
        if not node.is_array:
            yield f"{ctx.indent}let {ctx.nxt} = _rmSuffix({ctx.prv}, {v});"
        else:
            yield f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => _rmSuffix(s, {v}));"

    def visit_rm_prefix_suffix(
        self, node: RmPrefixSuffix, ctx: ConverterContext
    ) -> VisitStream:
        yield STD(
            "_rmPrefix",
            code="function _rmPrefix(s, p) { return s.startsWith(p) ? s.slice(p.length) : s; }",
        )
        yield STD(
            "_rmSuffix",
            code="function _rmSuffix(s, p) { return s.endsWith(p) ? s.slice(0, -p.length) : s; }",
        )
        v = repr(node.substr)
        if not node.is_array:
            yield f"{ctx.indent}let {ctx.nxt} = _rmSuffix(_rmPrefix({ctx.prv}, {v}), {v});"
        else:
            yield f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => _rmSuffix(_rmPrefix(s, {v}), {v}));"

    def visit_format(self, node: Fmt, ctx: ConverterContext) -> VisitStream:
        tmpl = node.template.replace("{{}}", "${_v}").replace("`", "\\`")
        js_tmpl = "`" + tmpl + "`"
        if not node.is_array:
            yield f"{ctx.indent}let {ctx.nxt} = ((_v) => {js_tmpl})({ctx.prv});"
        else:
            yield f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(_v => {js_tmpl});"

    def visit_repl(self, node: Repl, ctx: ConverterContext) -> VisitStream:
        old = repr(node.old)
        new = repr(node.new)
        if not node.is_array:
            yield f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.replaceAll({old}, {new});"
        else:
            yield f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => s.replaceAll({old}, {new}));"

    def visit_repl_map(
        self, node: ReplMap, ctx: ConverterContext
    ) -> VisitStream:
        yield STD(
            "_replMap",
            code=(
                "function _replMap(s, map) {\n"
                "    for (const [k, v] of Object.entries(map)) s = s.split(k).join(v);\n"
                "    return s;\n"
                "}"
            ),
        )
        rmap = repr(dict(node.replacements))
        if not node.is_array:
            yield f"{ctx.indent}let {ctx.nxt} = _replMap({ctx.prv}, {rmap});"
        else:
            yield f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => _replMap(s, {rmap}));"

    def visit_lower(self, node: Lower, ctx: ConverterContext) -> VisitStream:
        if not node.is_array:
            yield f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.toLowerCase();"
        else:
            yield f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => s.toLowerCase());"

    def visit_upper(self, node: Upper, ctx: ConverterContext) -> VisitStream:
        if not node.is_array:
            yield f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.toUpperCase();"
        else:
            yield f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => s.toUpperCase());"

    def visit_split(self, node: Split, ctx: ConverterContext) -> VisitStream:
        sep = repr(node.sep)
        yield f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.split({sep});"

    def visit_join(self, node: Join, ctx: ConverterContext) -> VisitStream:
        sep = repr(node.sep)
        yield f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.join({sep});"

    def visit_norm_space(
        self, node: NormalizeSpace, ctx: ConverterContext
    ) -> VisitStream:
        yield STD(
            "_normalizeText",
            code="function _normalizeText(s) { return s ? s.trim().replace(/\\s+/g, ' ') : ''; }",
        )
        if not node.is_array:
            yield f"{ctx.indent}let {ctx.nxt} = _normalizeText({ctx.prv});"
        else:
            yield f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => _normalizeText(s));"

    def visit_unescape(
        self, node: Unescape, ctx: ConverterContext
    ) -> VisitStream:
        yield STD(
            "_unescapeText",
            code=(
                "function _unescapeText(s) {\n"
                "    const el = document.createElement('textarea');\n"
                "    el.innerHTML = s; return el.value;\n"
                "}"
            ),
        )
        if not node.is_array:
            yield f"{ctx.indent}let {ctx.nxt} = _unescapeText({ctx.prv});"
        else:
            yield f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => _unescapeText(s));"

    # === regex ===

    def visit_re(self, node: Re, ctx: ConverterContext) -> VisitStream:
        rx = _js_re_node(node)
        if not node.is_array:
            yield f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.match({rx})[1];"
        else:
            yield f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => s.match({rx})[1]);"

    def visit_re_all(self, node: ReAll, ctx: ConverterContext) -> VisitStream:
        flags = "g"
        pattern = node.pattern
        m = _re.match(r"^\(\?([a-z]+)\)", pattern)
        if m:
            flags += "".join(c for c in m.group(1) if c in "ims")
            pattern = pattern[m.end() :]
        escaped = pattern.replace("/", "\\/")
        rx_g = f"/{escaped}/{flags}"
        yield f"{ctx.indent}let {ctx.nxt} = Array.from({ctx.prv}.matchAll({rx_g}), m => m[1]);"

    def visit_re_sub(self, node: ReSub, ctx: ConverterContext) -> VisitStream:
        flags = "g"
        pattern = node.pattern
        m = _re.match(r"^\(\?([a-z]+)\)", pattern)
        if m:
            flags += "".join(c for c in m.group(1) if c in "ims")
            pattern = pattern[m.end() :]
        escaped = pattern.replace("/", "\\/")
        rx_g = f"/{escaped}/{flags}"
        repl = repr(node.repl)
        if not node.is_array:
            yield f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.replace({rx_g}, {repl});"
        else:
            yield f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => s.replace({rx_g}, {repl}));"

    # === array ===

    def visit_index(self, node: Index, ctx: ConverterContext) -> VisitStream:
        i = node.i
        i_expr = f"{ctx.prv}.length - {i}" if i < 0 else str(i)
        yield f"{ctx.indent}let {ctx.nxt} = {ctx.prv}[{i_expr}];"

    def visit_slice(self, node: Slice, ctx: ConverterContext) -> VisitStream:
        start = node.start
        end = node.end
        start_expr = f"{ctx.prv}.length - {start}" if start < 0 else str(start)
        end_expr = f"{ctx.prv}.length - {end}" if end < 0 else str(end)
        yield f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.slice({start_expr}, {end_expr});"

    def visit_len(self, node: Len, ctx: ConverterContext) -> VisitStream:
        yield f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.length;"

    def visit_unique(self, node: Unique, ctx: ConverterContext) -> VisitStream:
        if node.keep_order:
            yield f"{ctx.indent}let {ctx.nxt} = [...new Map({ctx.prv}.map(x=>[x,x])).keys()];"
        else:
            yield f"{ctx.indent}let {ctx.nxt} = [...new Set({ctx.prv})];"

    # === casts ===

    def visit_to_int(self, node: ToInt, ctx: ConverterContext) -> VisitStream:
        if not node.is_array:
            yield f"{ctx.indent}let {ctx.nxt} = parseInt({ctx.prv}, 10);"
        else:
            yield f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => parseInt(s, 10));"

    def visit_to_float(
        self, node: ToFloat, ctx: ConverterContext
    ) -> VisitStream:
        if not node.is_array:
            yield f"{ctx.indent}let {ctx.nxt} = parseFloat({ctx.prv});"
        else:
            yield f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => parseFloat(s));"

    def visit_to_bool(self, node: ToBool, ctx: ConverterContext) -> VisitStream:
        yield f"{ctx.indent}let {ctx.nxt} = Boolean({ctx.prv});"

    def visit_jsonify(
        self, node: Jsonify, ctx: ConverterContext
    ) -> VisitStream:
        if node.path:
            parts = jsonify_path_to_segments(node.path)
            path = "".join(f"[{p}]" for p in parts)
            yield f"{ctx.indent}let {ctx.nxt} = JSON.parse({ctx.prv}){path};"
        else:
            yield f"{ctx.indent}let {ctx.nxt} = JSON.parse({ctx.prv});"

    def visit_nested(self, node: Nested, ctx: ConverterContext) -> VisitStream:
        cls = to_pascal_case(node.struct_name)
        yield f"{ctx.indent}let {ctx.nxt} = new {cls}({ctx.prv}).parse();"

    # === control ===

    def visit_self(self, node: Self, ctx: ConverterContext) -> VisitStream:
        name = to_camel_case(node.name)
        yield f"{ctx.indent}let {ctx.nxt} = this._{name};"

    def visit_return(self, node: Return, ctx: ConverterContext) -> VisitStream:
        if isinstance(node.parent, PreValidate):
            yield f"{ctx.indent}return;"
            return
        # Suppress the trailing Return after a Fallback: the fallback emits its
        # own `return <var>` inside the try-block (JS `let` is block-scoped, so
        # the var is unreachable after the try/catch — unlike Python).
        body = getattr(node.parent, "body", None) or []
        try:
            idx = body.index(node)
        except ValueError:
            idx = -1
        if idx > 0 and isinstance(body[idx - 1], Fallback):
            return
        yield f"{ctx.indent}return {ctx.prv};"

    def visit_fallback(
        self, node: Fallback, ctx: ConverterContext
    ) -> VisitStream:
        val = _js_literal(node.value)
        inner = ctx.indent + ctx.indent_char
        yield f"{ctx.indent}try {{"
        yield TRAVERSE
        last_idx = ctx.index + len(node.body)
        last_var = (
            ctx.var_name if last_idx == 0 else f"{ctx.var_name}{last_idx}"
        )
        yield [
            f"{inner}return {last_var};",
            f"{ctx.indent}}} catch (e) {{",
            f"{inner}return {val};",
            f"{ctx.indent}}}",
        ]

    # === predicate containers ===

    def visit_filter(self, node: Filter, ctx: ConverterContext) -> VisitStream:
        yield f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.filter(i => ("
        yield TRAVERSE
        yield f"{ctx.deeper().indent}));"

    def visit_assert(self, node: Assert, ctx: ConverterContext) -> VisitStream:
        ob, cb = "{", "}"
        if isinstance(node.parent, PreValidate):
            setattr(node, "_local_name", "v")
            yield f"{ctx.indent}if (!("
        else:
            local = f"i{ctx.prv}"
            setattr(node, "_local_name", local)
            yield [
                f"{ctx.indent}let {local} = {ctx.prv};",
                f"{ctx.indent}if (!(",
            ]
        yield TRAVERSE
        if isinstance(node.parent, PreValidate):
            yield f"{ctx.indent})) {ob} throw new Error('Assertion failed'); {cb}"
        else:
            yield [
                f"{ctx.indent})) {ob} throw new Error('Assertion failed'); {cb}",
                f"{ctx.indent}let {ctx.nxt} = {ctx.prv};",
            ]

    def visit_match(self, node: Match, ctx: ConverterContext) -> VisitStream:
        local = f"i{ctx.prv}"
        setattr(node, "_local_name", local)
        yield [
            f"{ctx.indent}let {local} = this._tableMatchKey({ctx.prv});",
            f"{ctx.indent}if (!(",
        ]
        yield TRAVERSE
        yield [
            f"{ctx.indent})) {{ return UNMATCHED_TABLE_ROW; }}",
            f"{ctx.indent}let {ctx.nxt} = this._parseValue({ctx.prv});",
        ]

    # === logic ===

    def visit_logic_and(
        self, node: LogicAnd, ctx: ConverterContext
    ) -> VisitStream:
        yield _logic_prefix("&&", ctx)
        yield TRAVERSE
        yield ctx.indent + ")"

    def visit_logic_or(
        self, node: LogicOr, ctx: ConverterContext
    ) -> VisitStream:
        yield _logic_prefix("||", ctx)
        yield TRAVERSE
        yield ctx.indent + ")"

    def visit_logic_not(
        self, node: LogicNot, ctx: ConverterContext
    ) -> VisitStream:
        if ctx.index == 0:
            yield f"{ctx.indent}!("
        else:
            yield f"{ctx.indent}&& !("
        yield TRAVERSE
        yield ctx.indent + ")"

    # === predicates ===

    def visit_predicate_css(
        self, node: PredCss, ctx: ConverterContext
    ) -> VisitStream:
        q = repr(node.query)
        target = _pred_target(node, ctx)
        yield _and(f"{target}.querySelector({q}) !== null", ctx)

    def visit_predicate_xpath(
        self, node: PredXpath, ctx: ConverterContext
    ) -> VisitStream:
        raise NotImplementedError("XPath predicates not supported in pure JS")

    def visit_predicate_has_attr(
        self, node: PredHasAttr, ctx: ConverterContext
    ) -> VisitStream:
        keys = node.attrs
        target = _pred_attr_target(node, ctx)
        cond = (
            f"{target}.hasAttribute({keys[0]!r})"
            if len(keys) == 1
            else f"{py_sequence_to_js_array(keys)}.some(k => {target}.hasAttribute(k))"
        )
        yield _and(cond, ctx)

    def visit_predicate_attr_eq(
        self, node: PredAttrEq, ctx: ConverterContext
    ) -> VisitStream:
        name, values = node.name, node.values
        target = _pred_attr_target(node, ctx)
        cond = (
            f"{target}.getAttribute({name!r}) === {values[0]!r}"
            if len(values) == 1
            else f"{py_sequence_to_js_array(values)}.some(v => {target}.getAttribute({name!r}) === v)"
        )
        yield _and(cond, ctx)

    def visit_predicate_attr_ne(
        self, node: PredAttrNe, ctx: ConverterContext
    ) -> VisitStream:
        name, values = node.name, node.values
        target = _pred_attr_target(node, ctx)
        cond = (
            f"{target}.getAttribute({name!r}) !== {values[0]!r}"
            if len(values) == 1
            else f"{py_sequence_to_js_array(values)}.every(v => {target}.getAttribute({name!r}) !== v)"
        )
        yield _and(cond, ctx)

    def visit_predicate_attr_starts(
        self, node: PredAttrStarts, ctx: ConverterContext
    ) -> VisitStream:
        name, values = node.name, node.values
        target = _pred_attr_target(node, ctx)
        cond = (
            f"({target}.getAttribute({name!r}) ?? '').startsWith({values[0]!r})"
            if len(values) == 1
            else f"{py_sequence_to_js_array(values)}.some(v => ({target}.getAttribute({name!r}) ?? '').startsWith(v))"
        )
        yield _and(cond, ctx)

    def visit_predicate_attr_ends(
        self, node: PredAttrEnds, ctx: ConverterContext
    ) -> VisitStream:
        name, values = node.name, node.values
        target = _pred_attr_target(node, ctx)
        cond = (
            f"({target}.getAttribute({name!r}) ?? '').endsWith({values[0]!r})"
            if len(values) == 1
            else f"{py_sequence_to_js_array(values)}.some(v => ({target}.getAttribute({name!r}) ?? '').endsWith(v))"
        )
        yield _and(cond, ctx)

    def visit_predicate_attr_contains(
        self, node: PredAttrContains, ctx: ConverterContext
    ) -> VisitStream:
        name, values = node.name, node.values
        target = _pred_attr_target(node, ctx)
        cond = (
            f"({target}.getAttribute({name!r}) ?? '').includes({values[0]!r})"
            if len(values) == 1
            else f"{py_sequence_to_js_array(values)}.some(v => ({target}.getAttribute({name!r}) ?? '').includes(v))"
        )
        yield _and(cond, ctx)

    def visit_predicate_attr_re(
        self, node: PredAttrRe, ctx: ConverterContext
    ) -> VisitStream:
        rx = _js_re_node(node)
        target = _pred_attr_target(node, ctx)
        yield _and(
            f"{rx}.test({target}.getAttribute({node.name!r}) ?? '')", ctx
        )

    def visit_predicate_text_contains(
        self, node: PredTextContains, ctx: ConverterContext
    ) -> VisitStream:
        values = node.values
        target = _pred_text_target(node, ctx)
        cond = (
            f"{target}.includes({values[0]!r})"
            if len(values) == 1
            else f"{py_sequence_to_js_array(values)}.some(v => {target}.includes(v))"
        )
        yield _and(cond, ctx)

    def visit_predicate_text_starts(
        self, node: PredTextStarts, ctx: ConverterContext
    ) -> VisitStream:
        values = node.values
        target = _pred_text_target(node, ctx)
        cond = (
            f"{target}.startsWith({values[0]!r})"
            if len(values) == 1
            else f"{py_sequence_to_js_array(values)}.some(v => {target}.startsWith(v))"
        )
        yield _and(cond, ctx)

    def visit_predicate_text_ends(
        self, node: PredTextEnds, ctx: ConverterContext
    ) -> VisitStream:
        values = node.values
        target = _pred_text_target(node, ctx)
        cond = (
            f"{target}.endsWith({values[0]!r})"
            if len(values) == 1
            else f"{py_sequence_to_js_array(values)}.some(v => {target}.endsWith(v))"
        )
        yield _and(cond, ctx)

    def visit_predicate_text_re(
        self, node: PredTextRe, ctx: ConverterContext
    ) -> VisitStream:
        rx = _js_re_node(node)
        target = _pred_text_target(node, ctx)
        yield _and(f"{rx}.test({target})", ctx)

    def visit_predicate_contains(
        self, node: PredContains, ctx: ConverterContext
    ) -> VisitStream:
        values = node.values
        target = _pred_target(node, ctx)
        cond = (
            f"{target}.includes({values[0]!r})"
            if len(values) == 1
            else f"{py_sequence_to_js_array(values)}.some(v => {target}.includes(v))"
        )
        yield _and(cond, ctx)

    def visit_predicate_eq(
        self, node: PredEq, ctx: ConverterContext
    ) -> VisitStream:
        values = node.values
        target = _pred_target(node, ctx)
        if isinstance(values[0], int):
            cond = f"{target}.length === {values[0]}"
        elif len(values) == 1:
            cond = f"{target} === {values[0]!r}"
        else:
            cond = (
                f"{py_sequence_to_js_array(values)}.some(v => {target} === v)"
            )
        yield _and(cond, ctx)

    def visit_predicate_ne(
        self, node: PredNe, ctx: ConverterContext
    ) -> VisitStream:
        values = node.values
        target = _pred_target(node, ctx)
        if isinstance(values[0], int):
            cond = f"{target}.length !== {values[0]}"
        elif len(values) == 1:
            cond = f"{target} !== {values[0]!r}"
        else:
            cond = (
                f"{py_sequence_to_js_array(values)}.every(v => {target} !== v)"
            )
        yield _and(cond, ctx)

    def visit_predicate_starts(
        self, node: PredStarts, ctx: ConverterContext
    ) -> VisitStream:
        values = node.values
        target = _pred_target(node, ctx)
        cond = (
            f"{target}.startsWith({values[0]!r})"
            if len(values) == 1
            else f"{py_sequence_to_js_array(values)}.some(v => {target}.startsWith(v))"
        )
        yield _and(cond, ctx)

    def visit_predicate_ends(
        self, node: PredEnds, ctx: ConverterContext
    ) -> VisitStream:
        values = node.values
        target = _pred_target(node, ctx)
        cond = (
            f"{target}.endsWith({values[0]!r})"
            if len(values) == 1
            else f"{py_sequence_to_js_array(values)}.some(v => {target}.endsWith(v))"
        )
        yield _and(cond, ctx)

    def visit_predicate_count_eq(
        self, node: PredCountEq, ctx: ConverterContext
    ) -> VisitStream:
        target = _pred_target(node, ctx)
        yield _and(f"{target}.length === {node.value}", ctx)

    def visit_predicate_count_gt(
        self, node: PredCountGt, ctx: ConverterContext
    ) -> VisitStream:
        target = _pred_target(node, ctx)
        yield _and(f"{target}.length > {node.value}", ctx)

    def visit_predicate_count_lt(
        self, node: PredCountLt, ctx: ConverterContext
    ) -> VisitStream:
        target = _pred_target(node, ctx)
        yield _and(f"{target}.length < {node.value}", ctx)

    def visit_predicate_count_ne(
        self, node: PredCountNe, ctx: ConverterContext
    ) -> VisitStream:
        target = _pred_target(node, ctx)
        yield _and(f"{target}.length !== {node.value}", ctx)

    def visit_predicate_count_ge(
        self, node: PredCountGe, ctx: ConverterContext
    ) -> VisitStream:
        target = _pred_target(node, ctx)
        yield _and(f"{target}.length >= {node.value}", ctx)

    def visit_predicate_count_le(
        self, node: PredCountLe, ctx: ConverterContext
    ) -> VisitStream:
        target = _pred_target(node, ctx)
        yield _and(f"{target}.length <= {node.value}", ctx)

    def visit_pred_count_range(
        self, node: PredCountRange, ctx: ConverterContext
    ) -> VisitStream:
        target = _pred_target(node, ctx)
        yield _and(
            f"{node.start} < {target}.length && {target}.length < {node.end}",
            ctx,
        )

    def visit_predicate_re(
        self, node: PredRe, ctx: ConverterContext
    ) -> VisitStream:
        rx = _js_re_node(node)
        target = _pred_target(node, ctx)
        yield _and(f"{rx}.test({target})", ctx)

    def visit_predicate_re_all(
        self, node: PredReAll, ctx: ConverterContext
    ) -> VisitStream:
        rx = _js_re_node(node)
        target = _pred_target(node, ctx)
        yield _and(f"{target}.every(j => {rx}.test(j))", ctx)

    def visit_predicate_re_any(
        self, node: PredReAny, ctx: ConverterContext
    ) -> VisitStream:
        rx = _js_re_node(node)
        target = _pred_target(node, ctx)
        yield _and(f"{target}.some(j => {rx}.test(j))", ctx)

    # === REST / fetch ===

    def visit_method_rest(
        self, node: MethodRest, ctx: ConverterContext
    ) -> VisitStream:
        (
            spec,
            pre_lines,
            ph_param,
            http_client,
            params_expr,
            headers_expr,
            _cookies_expr,
            body_expr,
            i1,
            i2,
            i3,
            i4,
        ) = _js_build_request_args(node, ctx)

        raw_name = node.name or "fetch"
        method_name = to_camel_case(to_snake_case(raw_name))
        if raw_name == "fetch":
            method_name = "fetch"

        parent = node.parent
        errors = parent.errors if isinstance(parent, StructBase) else []
        struct_name = parent.name if isinstance(parent, StructBase) else ""

        ok_payload = _js_ok_payload_type(node)
        err_variants: list[str] = []
        seen: set[str] = set()
        for err in errors:
            cls_name = _js_err_subclass_name(struct_name, err)
            if cls_name not in seen:
                seen.add(cls_name)
                err_variants.append(cls_name)
        return_union = " | ".join(
            [f"Ok<{ok_payload}>", *err_variants, "UnknownErr", "TransportErr"]
        )

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
            bracket = (
                f"[params.{p.name}]" if p.is_optional else f"params.{p.name}"
            )
            lines.append(f"{i1} * @param {{{t}}} {bracket}")
        lines.append(f"{i1} * @returns {{Promise<{return_union}>}}")
        lines.append(f"{i1} */")
        lines.append(f"{i1}static async {method_name}(client{ph_param}) {{")
        lines.append(f"{i2}let _resp;")
        lines.append(f"{i2}try {{")
        lines.extend(pre_lines)

        if http_client == "axios":
            req_props: list[str] = [
                f"{i4}method: {spec.method!r},",
                f"{i4}url: {_js_render_value(spec.url)},",
                f"{i4}validateStatus: () => true,",
            ]
            if params_expr:
                req_props.append(f"{i4}params: {params_expr},")
            if headers_expr:
                req_props.append(f"{i4}headers: {headers_expr},")
            if body_expr:
                req_props.append(f"{i4}data: {body_expr},")
            lines.append(f"{i3}_resp = await client.request({{")
            lines.extend(req_props)
            lines.append(f"{i3}}});")
        else:
            if params_expr:
                url_inner = PlaceholderSpec.sub(
                    spec.url.replace("`", "\\`"),
                    lambda ph: "${" + ph.name + "}",
                )
                if params_expr == "_params":
                    url_expr = f"`{url_inner}?${{{params_expr}.toString()}}`"
                else:
                    url_expr = (
                        f"`{url_inner}?${{new URLSearchParams({params_expr})}}`"
                    )
            else:
                url_expr = _js_render_value(spec.url)
            options: list[str] = [f"{i4}method: {spec.method!r},"]
            if headers_expr:
                options.append(f"{i4}headers: {headers_expr},")
            if body_expr:
                options.append(f"{i4}body: {body_expr},")
            lines.append(f"{i3}_resp = await client({url_expr}, {{")
            lines.extend(options)
            lines.append(f"{i3}}});")

        lines.append(f"{i2}}} catch (e) {{")
        lines.append(
            f"{i3}return {{ isOk: false, status: 0, headers: {{}}, "
            f"value: null, cause: String(e) }};"
        )
        lines.append(f"{i2}}}")
        parser_fn = (
            "sscParseResponseAxios"
            if http_client == "axios"
            else "sscParseResponse"
        )
        parse_prefix = "" if http_client == "axios" else "await "
        lines.append(
            f"{i2}const [_status, _headers, _body] = {parse_prefix}{parser_fn}(_resp);"
        )
        struct_pascal = to_pascal_case(struct_name) if struct_name else ""
        lines.append(
            f"{i2}const _err = {struct_pascal}.sscDispatchErr(_status, _headers, _body);"
        )
        lines.append(f"{i2}if (_err !== null) return _err;")
        lines.append(
            f"{i2}return {{ isOk: true, status: _status, headers: _headers, value: _body }};"
        )
        lines.append(f"{i1}}}")
        yield lines

    def visit_method_fetch(
        self, node: MethodFetch, ctx: ConverterContext
    ) -> VisitStream:
        (
            spec,
            _pre_lines,
            ph_param,
            http_client,
            params_expr,
            headers_expr,
            _cookies_expr,
            body_expr,
            i1,
            i2,
            i3,
            _i4,
        ) = _js_build_request_args(node, ctx)

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

        lines: list[str] = [
            f"{i1}static async {method_name}(client{ph_param}) {{"
        ]

        if http_client == "fetch":
            if params_expr:
                url_inner = PlaceholderSpec.sub(
                    spec.url.replace("`", "\\`"),
                    lambda ph: "${" + ph.name + "}",
                )
                url_expr = (
                    f"`{url_inner}?${{new URLSearchParams({params_expr})}}`"
                )
            else:
                url_expr = _js_render_value(spec.url)
            options: list[str] = [f"{i3}method: {spec.method!r},"]
            if headers_expr:
                options.append(f"{i3}headers: {headers_expr},")
            if spec.cookies:
                cookie_str = "; ".join(
                    f"{k}={v}" for k, v in spec.cookies.items()
                )
                options.append(
                    f"{i3}// cookies: {cookie_str!r}  /* set via headers or credentials */"
                )
            if body_expr:
                options.append(f"{i3}body: {body_expr},")
            lines.append(f"{i2}const _resp = await client({url_expr}, {{")
            lines.extend(options)
            lines.append(f"{i2}}});")
            lines.append(
                f"{i2}if (!_resp.ok) throw new Error(`HTTP ${{_resp.status}}`);"
            )
            if node.response_path:
                lines.extend(_response_lines("await _resp.json()"))
            else:
                lines.extend(_response_lines("await _resp.text()"))
        else:
            req_props: list[str] = [
                f"{i3}method: {spec.method!r},",
                f"{i3}url: {_js_render_value(spec.url)},",
            ]
            if params_expr:
                req_props.append(f"{i3}params: {params_expr},")
            if headers_expr:
                req_props.append(f"{i3}headers: {headers_expr},")
            if spec.cookies:
                req_props.append(
                    f"{i3}// cookies: {_js_render_obj(spec.cookies)},"
                )
            if body_expr:
                req_props.append(f"{i3}data: {body_expr},")
            lines.append(f"{i2}const _resp = await client.request({{")
            lines.extend(req_props)
            lines.append(f"{i2}}});")
            lines.extend(_response_lines("_resp.data"))

        lines.append(f"{i1}}}")
        yield lines


JS_CONVERTER = JsPure()
