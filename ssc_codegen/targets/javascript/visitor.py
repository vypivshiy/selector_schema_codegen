"""Pure ES6 JS (DOM) codegen visitor on the BaseWalker model.

Ports all JS codegen from ``JsPure`` to the new ``list[str]`` traversal core.
Emits plain JavaScript using the browser/DOM API (``querySelector`` etc.),
suitable for modern browsers and the Node.js + jsdom test runner.

Codegen notations:

- ES8 required if ``re.DOTALL`` regex flag is needed, otherwise ES6.
- Annotations are generated in JSDoc format.
- Method (field) names are converted to ``_parseUpperCamelCase``.
"""

from __future__ import annotations

import json
import re as _re
from typing import Any

from ssc_codegen.ast import (
    Attr,
    Assert,
    CheckMethod,
    CodeEndHook,
    CodeStartHook,
    CssRemove,
    CssSelect,
    CssSelectAll,
    ErrorResponse,
    Fallback,
    Field,
    Filter,
    Fmt,
    Init,
    InitField,
    InitFieldCall,
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
    MethodFetch,
    MethodRest,
    Module,
    Nested,
    NormalizeSpace,
    PlaceholderSpec,
    PlaceholderTemplate,
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
    RequestHttp,
    ResultAliasDef,
    ResultVariantDef,
    MatcherListDef,
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
from ssc_codegen.naming import to_camel_case, to_pascal_case, to_snake_case
from ssc_codegen.traversal.utils import (
    dict_needs_builder,
    err_subclass_name,
    find_predicate_container,
    jsonify_path_to_segments,
    module_has_rest,
)
from ssc_codegen.generation.builder import ModuleBuilder
from ssc_codegen.targets.javascript.http_libs.axios import AxiosStrategy
from ssc_codegen.targets.javascript.http_libs.base import JsHttpLibStrategy
from ssc_codegen.targets.javascript.http_libs.fetch import FetchStrategy
from ssc_codegen.traversal.context import WalkContext
from ssc_codegen.traversal.walker import BaseWalker


# ===========================================================================
# Helpers
# ===========================================================================


def _py_re_to_js_re(pattern: str, global_flag: bool = False) -> str:
    """Convert a Python regex pattern to a JS regex literal.

    Strips a leading ``(?ims)`` inline-flag group, transfers ``i``/``m``/``s``
    to the JS flags, and optionally forces ``g`` for matchAll/replace.
    """
    flags = "g" if global_flag else ""
    m = _re.match(r"^\(\?([a-z]+)\)", pattern)
    if m:
        flags += "".join(c for c in m.group(1) if c in "ims")
        pattern = pattern[m.end() :]
    escaped = pattern.replace("/", "\\/")
    return f"/{escaped}/{flags}"


def py_sequence_to_js_array(values) -> str:
    return json.dumps(list(values))


def _js_literal(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return repr(value)


def _logic_prefix(op: str, ctx: WalkContext) -> str:
    if ctx.index == 0:
        return ctx.indent + "("
    return ctx.indent + f"{op} ("


def _js_docblock(lines: list[str]) -> list[str]:
    if not lines:
        return []
    return ["/**", *(f" * {line}" if line else " *" for line in lines), " */"]


def _pred_target(node, ctx: WalkContext) -> str:
    container = find_predicate_container(node)
    if isinstance(container, Filter):
        return "i"
    if isinstance(container, (Match, Assert, PreValidate)):
        return getattr(container, "_local_name", "i")
    return ctx.prv


def _pred_text_target(node, ctx: WalkContext) -> str:
    target = _pred_target(node, ctx)
    container = find_predicate_container(node)
    if target == "i" and isinstance(container, Filter):
        return "i.textContent"
    return target


def _pred_attr_target(node, ctx: WalkContext) -> str:
    return _pred_target(node, ctx)


# ===========================================================================
# REST infrastructure
# ===========================================================================


def _js_resolve_path_expr(body_var: str, path: str) -> str:
    expr = body_var
    for seg in path.split("."):
        if seg.isdigit():
            expr += f"[{seg}]"
        else:
            expr += f"[{seg!r}]"
    return expr


def _render_js_condition_check(
    required_keys: list[str], conditions: dict[str, object]
) -> str | None:
    """Render a JS ``(_b) => ...`` check from raw condition data.

    Consumed by ``visit_matcher_list_def``.
    """
    parts: list[str] = []
    for key in required_keys:
        parts.append(f"{key!r} in _b")
    for path, value in conditions.items():
        lhs = _js_resolve_path_expr("_b", path)
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
# StartParse helpers
# ===========================================================================


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


def _js_render_value(tmpl: PlaceholderTemplate) -> str:
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


def _js_render_obj(d: dict[str, PlaceholderTemplate]) -> str:
    if not d:
        return "{}"
    inner = ", ".join(f"{k!r}: {_js_render_value(v)}" for k, v in d.items())
    return "{" + inner + "}"


def _js_emit_obj_builder(
    varname: str, d: dict[str, PlaceholderTemplate], indent: str
) -> list[str]:
    lines = [f"{indent}const {varname} = {{}};"]
    for key, tmpl in d.items():
        ph = tmpl.single_placeholder()
        expr = _js_render_value(tmpl)
        if ph is not None and ph.is_optional:
            lines.append(
                f"{indent}if ({ph.name} !== undefined && {ph.name} !== null) "
                f"{varname}[{key!r}] = {expr};"
            )
        else:
            lines.append(f"{indent}{varname}[{key!r}] = {expr};")
    return lines


def _js_emit_params_builder(
    varname: str, d: dict[str, PlaceholderTemplate], indent: str
) -> list[str]:
    lines = [f"{indent}const {varname} = new URLSearchParams();"]
    for key, tmpl in d.items():
        ph = tmpl.single_placeholder()
        if ph is None:
            lines.append(
                f"{indent}{varname}.set({key!r}, {_js_render_value(tmpl)});"
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


def _js_render_json_body(tmpl: PlaceholderTemplate) -> str:
    inner = tmpl.map(
        lambda ph: "${" + ph.name + "}",
        lambda s: s.replace("\\", "\\\\").replace("`", "\\`"),
    )
    return f"`{inner}`"


def _js_render_body(spec: RequestHttp) -> tuple[str, str] | None:
    if spec.body_kind == "empty" or spec.body is None:
        return None
    if spec.body_kind == "json":
        assert isinstance(spec.body, PlaceholderTemplate)
        return ("body", _js_render_json_body(spec.body))
    if spec.body_kind == "form":
        assert isinstance(spec.body, dict)
        return ("body", f"new URLSearchParams({_js_render_obj(spec.body)})")
    assert isinstance(spec.body, PlaceholderTemplate)
    return ("body", _js_render_value(spec.body))


def _js_name(name: str) -> str:
    return to_camel_case(to_snake_case(name))


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
# JsVisitor
# ===========================================================================


class JsVisitor(BaseWalker):
    """Pure ES6 JS (DOM API) codegen visitor.

    All ``visit_*`` handlers return ``list[str]``.
    """

    TYPES = {
        VT.STRING: "string",
        VT.BOOL: "boolean",
        VT.INT: "number",
        VT.FLOAT: "number",
        VT.NULL: "null",
        VT.JSON: "any",
        VT.NESTED: "any",
        VT.AUTO: "any",
    }
    DEFAULT_TYPE = "any"
    ARRAY_TYPE_FMT = "{}[]"
    OPTIONAL_TYPE_FMT = "{}|null"
    OPTIONAL_ON_OMITEMPTY = True
    DOCUMENT_TYPE = "Document|Element"
    DOCUMENT_ARRAY_TYPE = "Array<Element>"
    AND_OP = "&&"
    STD_MODULE_NAME = "sscgen_runtime"

    _HTTP_STRATEGIES: dict[str, type[JsHttpLibStrategy]] = {
        "fetch": FetchStrategy,
        "axios": AxiosStrategy,
    }

    def __init__(self, var_name: str = "v", indent: str = " " * 2) -> None:
        self.var_name = var_name
        self.indent = indent
        self._file_providers: dict[str, Any] = {}
        self._reset_state()

    # === STATE ===

    def _reset_state(self) -> None:
        self._builder = ModuleBuilder()
        self._http: JsHttpLibStrategy = FetchStrategy()

    def _make_ctx(self, meta: dict) -> WalkContext:
        return WalkContext(
            var_name=self.var_name, indent_char=self.indent, meta=dict(meta)
        )

    # === FILE PROVIDERS ===

    def file(self, filename: str):
        def decorator(fn):
            self._file_providers[filename] = fn
            return fn

        return decorator

    # === PUBLIC API ===

    def convert(self, module_ast: Module, **meta) -> str:
        return self.convert_all(module_ast, **meta)[""]

    def convert_all(self, module_ast: Module, **meta) -> dict[str, str]:
        self._reset_state()
        client = meta.get("http_client")
        if client and client in self._HTTP_STRATEGIES:
            self._http = self._HTTP_STRATEGIES[client]()
        ctx = self._make_ctx(meta)
        self._walk_module(module_ast, ctx)
        lines = self._walk_module(module_ast, ctx)
        out: dict[str, str] = {"": "\n".join(lines)}
        for fname, provider in self._file_providers.items():
            out[fname] = provider(module_ast, ctx.meta)
        return out

    def convert_batch(
        self,
        modules: list[tuple[str, Module]],
        **meta,
    ) -> dict[str, str]:
        ctx = self._make_ctx(meta)
        results: dict[str, str] = {}
        for name, module_ast in modules:
            self._reset_state()
            client = meta.get("http_client")
            if client and client in self._HTTP_STRATEGIES:
                self._http = self._HTTP_STRATEGIES[client]()
            self._walk_module(module_ast, ctx)
            results[name] = "\n".join(self._walk_module(module_ast, ctx))
        return results

    def _walk_module(self, module_ast: Module, ctx: WalkContext) -> list[str]:
        lines: list[str] = list(self.visit_module(module_ast, ctx))
        for node in module_ast.body:
            lines.extend(self.walk(node, ctx))
        return lines

    # === STD RENDERING ===

    def _render_std_section(self, ctx: WalkContext) -> list[str]:
        if not self._builder.has_std:
            return []
        body: list[str] = []
        for _imps, code in self._builder.std_defs.values():
            body.extend(code.splitlines())
            body.append("")
        return body

    # === TYPE RESOLUTION ===

    def _resolve_type(self, type_info: TypeInfo | None) -> str:
        if type_info is None:
            return self.DEFAULT_TYPE
        if type_info.base == VT.NESTED and type_info.ref:
            t = f"{to_pascal_case(type_info.ref)}Type"
        elif type_info.base == VT.JSON and type_info.ref:
            t = f"{to_pascal_case(type_info.ref)}Json"
        elif type_info.base == VT.DOCUMENT:
            t = (
                self.DOCUMENT_ARRAY_TYPE
                if type_info.is_array
                else self.DOCUMENT_TYPE
            )
        else:
            t = self.TYPES.get(type_info.base, self.DEFAULT_TYPE)
        if type_info.is_array and type_info.base != VT.DOCUMENT:
            t = self.ARRAY_TYPE_FMT.format(t)
        if type_info.is_optional or (
            self.OPTIONAL_ON_OMITEMPTY and type_info.omitempty
        ):
            t = self.OPTIONAL_TYPE_FMT.format(t)
        return t

    def _pred_line(self, ctx: WalkContext, cond: str) -> str:
        prefix = "" if ctx.index == 0 else f"{self.AND_OP} "
        return f"{ctx.indent}{prefix}{cond}"

    # === MODULE ===

    def visit_module(self, node: Module, ctx: WalkContext) -> list[str]:
        lines: list[str] = []
        if node.doc:
            lines.extend(_js_docblock(node.doc.splitlines()))
        lines.append('"use strict";')
        lines.append("// autogenerated by ssc-gen. DO NOT EDIT")
        return lines

    def visit_utilities(self, node: Utilities, ctx: WalkContext) -> list[str]:
        lines: list[str] = [
            "const UNMATCHED_TABLE_ROW = Symbol('UNMATCHED_TABLE_ROW');",
            "",
        ]
        mod = node.parent
        if isinstance(mod, Module) and module_has_rest(mod):
            lines.extend(REST_SHARED)
            lines.extend(FetchStrategy().rest_call_lines())
            lines.extend(AxiosStrategy().rest_call_lines())
        lines.extend(self._render_std_section(ctx))
        return lines

    def visit_code_start_hook(
        self, node: CodeStartHook, ctx: WalkContext
    ) -> list[str]:
        return []

    def visit_code_end_hook(
        self, node: CodeEndHook, ctx: WalkContext
    ) -> list[str]:
        return []

    def visit_error_response(
        self, node: ErrorResponse, ctx: WalkContext
    ) -> list[str]:
        return []

    # === TYPES ===

    def visit_jsondef(self, node: JsonDef, ctx: WalkContext) -> list[str]:
        name = to_pascal_case(node.name)
        lines = ["/**", f" * @typedef {{Object}} {name}Json"]
        lines.extend(self.walk_children(node, ctx))
        lines.append(" */")
        return lines

    def visit_jsondef_field(
        self, node: JsonDefField, ctx: WalkContext
    ) -> list[str]:
        if node.type_info and node.type_info.skip:
            return []
        name = node.name
        type_ = self._resolve_type(node.type_info)
        if node.type_info.omitempty:
            return [f" * @property {{{type_}}} {name} (OMITEMPTY)"]
        return [f" * @property {{{type_}}} {name}"]

    def visit_typedef(self, node: TypeDef, ctx: WalkContext) -> list[str]:
        if node.struct_type == ST.REST:
            return []
        name = to_pascal_case(node.name)
        if node.struct_type == ST.FLAT:
            return [f"/** @typedef {{Array<string>}} {name}Type */"]
        if node.struct_type == ST.DICT:
            value_field = next(
                f for f in node.fields if to_camel_case(f.name) == "value"
            )
            value_type = self._resolve_type(value_field.type_info)
            return [
                "/**",
                f" * @typedef {{Object.<string, {value_type}>}} {name}Type",
                " */",
            ]
        lines = ["/**", f" * @typedef {{Object}} {name}Type"]
        lines.extend(self.walk_children(node, ctx))
        lines.append(" */")
        return lines

    def visit_typedef_field(
        self, node: TypeDefField, ctx: WalkContext
    ) -> list[str]:
        if node.typedef.struct_type in (ST.DICT, ST.FLAT):
            return []
        name = to_camel_case(node.name)
        if node.typedef.struct_type == ST.TABLE and name == "value":
            return []
        type_ = self._resolve_type(node.type_info)
        return [f" * @property {{{type_}}} {name}"]

    # === STRUCT ===

    def visit_struct(self, node: Struct, ctx: WalkContext) -> list[str]:
        lines = list(_js_struct_header(node))
        lines.extend(self.walk_children(node, ctx))
        lines.append("}")
        return lines

    def visit_struct_rest(
        self, node: StructRest, ctx: WalkContext
    ) -> list[str]:
        lines = list(_js_struct_header(node))
        lines.extend(self.walk_children(node, ctx))
        lines.append("}")
        return lines

    def visit_result_variant_def(
        self, node: ResultVariantDef, ctx: WalkContext
    ) -> list[str]:
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

    def visit_result_alias_def(
        self, node: ResultAliasDef, ctx: WalkContext
    ) -> list[str]:
        return []

    def visit_matcher_list_def(
        self, node: MatcherListDef, ctx: WalkContext
    ) -> list[str]:
        var = f"_{to_snake_case(node.struct_name)}Matchers"
        lines = [f"const {var} = ["]
        for e in node.entries:
            check = _render_js_condition_check(e.required_keys, e.conditions)
            check_arg = check if check else "null"
            lines.append(
                f"    {{ status: {e.status}, check: {check_arg}, "
                f"factory: (_s, _h, _b) => ({{ isOk: false, status: _s, "
                f"headers: _h, value: _b }}) }},"
            )
        lines.append("];")
        return lines

    def visit_init(self, node: Init, ctx: WalkContext) -> list[str]:
        if isinstance(node.parent, StructRest):
            return []
        i1, i2, i3 = ctx.indent, ctx.indent * 2, ctx.indent * 3
        lines = [
            f"{i1}constructor(document) {{",
            f"{i2}if (typeof document === 'string') {{",
            f"{i3}this._doc = (new DOMParser()).parseFromString(document, 'text/html');",
            f"{i2}}} else {{",
            f"{i3}this._doc = document;",
            f"{i2}}}",
        ]
        lines.extend(self.walk_children(node, ctx))
        lines.append(f"{i1}}}")
        return lines

    def visit_init_field_call(
        self, node: InitFieldCall, ctx: WalkContext
    ) -> list[str]:
        name = to_camel_case(node.name)
        cap = name[0].upper() + name[1:]
        return [f"{ctx.indent}this._{name} = this._init{cap}(this._doc);"]

    def visit_init_field(self, node: InitField, ctx: WalkContext) -> list[str]:
        name = to_camel_case(node.name)
        cap = name[0].upper() + name[1:]
        lines = [f"{ctx.indent}_init{cap}(v) {{"]
        lines.extend(self.walk_children(node, ctx))
        lines.append(f"{ctx.indent}}}")
        return lines

    def visit_field(self, node: Field, ctx: WalkContext) -> list[str]:
        name = to_camel_case(node.name)
        cap = name[0].upper() + name[1:]
        lines = [f"{ctx.indent}_parse{cap}(v) {{"]
        lines.extend(self.walk_children(node, ctx))
        lines.append(f"{ctx.indent}}}")
        return lines

    def visit_pre_validate(
        self, node: PreValidate, ctx: WalkContext
    ) -> list[str]:
        lines = [f"{ctx.indent}_preValidate(v) {{"]
        lines.extend(self.walk_children(node, ctx))
        lines.append(f"{ctx.indent}}}")
        return lines

    def visit_check_method(
        self, node: CheckMethod, ctx: WalkContext
    ) -> list[str]:
        method_name = to_camel_case(node.name)
        lines = [
            f"{ctx.indent}{method_name}() {{",
            f"{ctx.deeper().indent}let {ctx.var_name} = this._doc;",
        ]
        lines.extend(self.walk_children(node, ctx))
        lines.append("}")
        return lines

    def visit_split_doc(self, node: SplitDoc, ctx: WalkContext) -> list[str]:
        lines = [f"{ctx.indent}_splitDoc(v) {{"]
        lines.extend(self.walk_children(node, ctx))
        lines.append(f"{ctx.indent}}}")
        return lines

    def visit_key(self, node: Key, ctx: WalkContext) -> list[str]:
        lines = [f"{ctx.indent}_parseKey(v) {{"]
        lines.extend(self.walk_children(node, ctx))
        lines.append(f"{ctx.indent}}}")
        return lines

    def visit_value(self, node: Value, ctx: WalkContext) -> list[str]:
        lines = [f"{ctx.indent}_parseValue(v) {{"]
        lines.extend(self.walk_children(node, ctx))
        lines.append(f"{ctx.indent}}}")
        return lines

    def visit_table_config(
        self, node: TableConfig, ctx: WalkContext
    ) -> list[str]:
        lines = [f"{ctx.indent}_tableConfig(v) {{"]
        lines.extend(self.walk_children(node, ctx))
        lines.append(f"{ctx.indent}}}")
        return lines

    def visit_table_match_key(
        self, node: TableMatchKey, ctx: WalkContext
    ) -> list[str]:
        lines = [f"{ctx.indent}_tableMatchKey(v) {{"]
        lines.extend(self.walk_children(node, ctx))
        lines.append(f"{ctx.indent}}}")
        return lines

    def visit_table_rows(self, node: TableRows, ctx: WalkContext) -> list[str]:
        lines = [f"{ctx.indent}_tableRows(v) {{"]
        lines.extend(self.walk_children(node, ctx))
        lines.append(f"{ctx.indent}}}")
        return lines

    # === START_PARSE ===

    def visit_start_parse(
        self, node: StartParse, ctx: WalkContext
    ) -> list[str]:
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
        lines: list[str] = [
            f"{i1}/**",
            f"{i1}* @returns {{{ret_type}}}",
            f"{i1}*/",
            f"{i1}parse() {{",
        ]
        if node.use_pre_validate:
            lines.append(f"{i2}this._preValidate(this._doc);")
        if st == ST.ITEM:
            lines.append(f"{i2}return {{")
            for f in node.fields:
                n = to_camel_case(f.name)
                lines.append(
                    f"{i3}{n}: this.{_js_method_name(f.name)}(this._doc),"
                )
            lines.append(f"{i2}}};")
        elif st == ST.LIST:
            lines.append(
                f"{i2}return Array.from(this._splitDoc(this._doc)).map(i => ({{"
            )
            for f in node.fields:
                n = to_camel_case(f.name)
                lines.append(f"{i3}{n}: this.{_js_method_name(f.name)}(i),")
            lines.append(f"{i2}}}));")
        elif st == ST.FLAT:
            lines.append(f"{i2}let _result = [];")
            for f in node.fields:
                mname = _js_method_name(f.name)
                if f.ret_type_info.is_array:
                    lines.append(
                        f"{i2}_result = _result.concat(this.{mname}(this._doc));"
                    )
                else:
                    lines.append(f"{i2}_result.push(this.{mname}(this._doc));")
            if struct.keep_order:
                lines.append(
                    f"{i2}return [...new Map(_result.map(x=>[x,x])).keys()];"
                )
            else:
                lines.append(f"{i2}return [...new Set(_result)];")
        elif st == ST.DICT:
            lines.extend(
                [
                    f"{i2}return Array.from(this._splitDoc(this._doc)).reduce((acc, e) => {{",
                    f"{i3}acc[this._parseKey(e)] = this._parseValue(e);",
                    f"{i3}return acc;",
                    f"{i2}}}, {{}});",
                ]
            )
        elif st == ST.TABLE:
            lines.append(f"{i2}let _result = {{}};")
            lines.append(f"{i2}let _table = this._tableConfig(this._doc);")
            lines.append(f"{i2}for (let _row of this._tableRows(_table)) {{")
            for f in node.fields:
                n = to_camel_case(f.name)
                lines.append(
                    f"{i3}let _{n} = this.{_js_method_name(f.name)}(_row);"
                )
                lines.append(
                    f"{i3}if (_{n} !== UNMATCHED_TABLE_ROW "
                    f"&& !Object.prototype.hasOwnProperty.call(_result, {n!r})) "
                    f"_result[{n!r}] = _{n};"
                )
            lines.append(f"{i2}}}")
            lines.append(f"{i2}return _result;")
        lines.append(f"{i1}}}")
        return lines

    # === SELECTORS ===

    def visit_css_select(self, node: CssSelect, ctx: WalkContext) -> list[str]:
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
            return lines
        q = repr(node.query)
        return [f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.querySelector({q});"]

    def visit_css_select_all(
        self, node: CssSelectAll, ctx: WalkContext
    ) -> list[str]:
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
            return lines
        q = repr(node.query)
        return [
            f"{ctx.indent}let {ctx.nxt} = Array.from({ctx.prv}.querySelectorAll({q}));"
        ]

    def visit_css_remove(self, node: CssRemove, ctx: WalkContext) -> list[str]:
        q = repr(node.query)
        return [
            f"{ctx.indent}{ctx.prv}.querySelectorAll({q}).forEach(e => e.remove());",
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv};",
        ]

    def visit_xpath_select(
        self, node: XpathSelect, ctx: WalkContext
    ) -> list[str]:
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
            return lines
        q = repr(node.query)
        return [
            f"{ctx.indent}let xr{ctx.nxt} = document.evaluate({q}, {ctx.prv}, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);",
            f"{ctx.indent}let {ctx.nxt} = xr{ctx.nxt}.singleNodeValue;",
        ]

    def visit_xpath_select_all(
        self, node: XpathSelectAll, ctx: WalkContext
    ) -> list[str]:
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
            return lines
        q = repr(node.query)
        return [
            f"{ctx.indent}let xr{ctx.nxt} = document.evaluate({q}, {ctx.prv}, null, XPathResult.ORDERED_NODE_ITERATOR_TYPE, null);",
            f"{ctx.indent}let {ctx.nxt} = []; let xrn{ctx.nxt} = xr{ctx.nxt}.iterateNext();",
            f"{ctx.indent}while (xrn{ctx.nxt}) {{ {ctx.nxt}.push(xrn{ctx.nxt}); xrn{ctx.nxt} = xr{ctx.nxt}.iterateNext(); }}",
        ]

    def visit_xpath_remove(
        self, node: XpathRemove, ctx: WalkContext
    ) -> list[str]:
        q = repr(node.query)
        return [
            f"for (let {ctx.prv}r = document.evaluate({q}, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null), {ctx.prv}i = {ctx.prv}r.snapshotLength; {ctx.prv}i--; ) {ctx.prv}r.snapshotItem({ctx.prv}i).remove();",
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv};",
        ]

    def visit_text(self, node: Text, ctx: WalkContext) -> list[str]:
        if not node.is_array:
            return [f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.textContent;"]
        return [
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(el => el.textContent);"
        ]

    def visit_raw(self, node: Raw, ctx: WalkContext) -> list[str]:
        if not node.is_array:
            return [f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.outerHTML;"]
        return [
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(el => el.outerHTML);"
        ]

    def visit_attr(self, node: Attr, ctx: WalkContext) -> list[str]:
        keys = node.keys
        if not node.is_array:
            if len(keys) == 1:
                return [
                    f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.getAttribute({keys[0]!r});"
                ]
            kl = py_sequence_to_js_array(keys)
            return [
                f"{ctx.indent}let {ctx.nxt} = {kl}.map(k => {ctx.prv}.getAttribute(k)).filter(Boolean);"
            ]
        if len(keys) == 1:
            return [
                f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(el => el.getAttribute({keys[0]!r}));"
            ]
        kl = py_sequence_to_js_array(keys)
        return [
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.flatMap(el => {kl}.map(k => el.getAttribute(k)).filter(Boolean));"
        ]

    # === STRING ===

    def visit_trim(self, node: Trim, ctx: WalkContext) -> list[str]:
        substr = node.substr
        if not node.is_array:
            if not substr:
                return [f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.trim();"]
            return [
                f"{ctx.indent}let {ctx.nxt} = (function (str, chars) {{",
                "return str.replace(new RegExp(`^[${chars}]+|[${chars}]+$`, 'g'), '');",
                f"}})({ctx.prv}, {substr!r});",
            ]
        if not substr:
            return [
                f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => s.trim());"
            ]
        return [
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(e =>",
            "(function (str, chars) {",
            "return str.replace(new RegExp(`^[${chars}]+|[${chars}]+$`, 'g'), '');",
            f"}})(e, {substr!r})",
            ");",
        ]

    def visit_l_trim(self, node: Ltrim, ctx: WalkContext) -> list[str]:
        substr = node.substr
        if not node.is_array:
            if not substr:
                return [f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.trimStart();"]
            return [
                f"{ctx.indent}let {ctx.nxt} = (function (str, chars) {{",
                "return str.replace(new RegExp(`^[${chars}]+`, 'g'), '');",
                f"}})({ctx.prv}, {substr!r});",
            ]
        if not substr:
            return [
                f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => s.trimStart());"
            ]
        return [
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(e =>",
            "(function (str, chars) {",
            "return str.replace(new RegExp(`^[${chars}]+`, 'g'), '');",
            f"}})(e, {substr!r})",
            ");",
        ]

    def visit_r_trim(self, node: Rtrim, ctx: WalkContext) -> list[str]:
        substr = node.substr
        if not node.is_array:
            if not substr:
                return [f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.trimEnd();"]
            return [
                f"{ctx.indent}let {ctx.nxt} = (function (str, chars) {{",
                "return str.replace(new RegExp(`[${chars}]+$`, 'g'), '');",
                f"}})({ctx.prv}, {substr!r});",
            ]
        if not substr:
            return [
                f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => s.trimEnd());"
            ]
        return [
            f"let {ctx.nxt} = {ctx.prv}.map(e =>",
            "(function (str, chars) {",
            "return str.replace(new RegExp(`[${chars}]+$`, 'g'), '');",
            f"}})(e, {substr!r})",
            ");",
        ]

    def visit_rm_prefix(self, node: RmPrefix, ctx: WalkContext) -> list[str]:
        self._builder.require_std(
            "_rmPrefix",
            code="function _rmPrefix(s, p) { return s.startsWith(p) ? s.slice(p.length) : s; }",
        )
        v = repr(node.substr)
        if not node.is_array:
            return [f"{ctx.indent}let {ctx.nxt} = _rmPrefix({ctx.prv}, {v});"]
        return [
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => _rmPrefix(s, {v}));"
        ]

    def visit_rm_suffix(self, node: RmSuffix, ctx: WalkContext) -> list[str]:
        self._builder.require_std(
            "_rmSuffix",
            code="function _rmSuffix(s, p) { return s.endsWith(p) ? s.slice(0, -p.length) : s; }",
        )
        v = repr(node.substr)
        if not node.is_array:
            return [f"{ctx.indent}let {ctx.nxt} = _rmSuffix({ctx.prv}, {v});"]
        return [
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => _rmSuffix(s, {v}));"
        ]

    def visit_rm_prefix_suffix(
        self, node: RmPrefixSuffix, ctx: WalkContext
    ) -> list[str]:
        self._builder.require_std(
            "_rmPrefix",
            code="function _rmPrefix(s, p) { return s.startsWith(p) ? s.slice(p.length) : s; }",
        )
        self._builder.require_std(
            "_rmSuffix",
            code="function _rmSuffix(s, p) { return s.endsWith(p) ? s.slice(0, -p.length) : s; }",
        )
        v = repr(node.substr)
        if not node.is_array:
            return [
                f"{ctx.indent}let {ctx.nxt} = _rmSuffix(_rmPrefix({ctx.prv}, {v}), {v});"
            ]
        return [
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => _rmSuffix(_rmPrefix(s, {v}), {v}));"
        ]

    def visit_format(self, node: Fmt, ctx: WalkContext) -> list[str]:
        tmpl = node.template.replace("{{}}", "${_v}").replace("`", "\\`")
        js_tmpl = "`" + tmpl + "`"
        if not node.is_array:
            return [
                f"{ctx.indent}let {ctx.nxt} = ((_v) => {js_tmpl})({ctx.prv});"
            ]
        return [f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(_v => {js_tmpl});"]

    def visit_repl(self, node: Repl, ctx: WalkContext) -> list[str]:
        old = repr(node.old)
        new = repr(node.new)
        if not node.is_array:
            return [
                f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.replaceAll({old}, {new});"
            ]
        return [
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => s.replaceAll({old}, {new}));"
        ]

    def visit_repl_map(self, node: ReplMap, ctx: WalkContext) -> list[str]:
        self._builder.require_std(
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
            return [f"{ctx.indent}let {ctx.nxt} = _replMap({ctx.prv}, {rmap});"]
        return [
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => _replMap(s, {rmap}));"
        ]

    def visit_lower(self, node: Lower, ctx: WalkContext) -> list[str]:
        if not node.is_array:
            return [f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.toLowerCase();"]
        return [
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => s.toLowerCase());"
        ]

    def visit_upper(self, node: Upper, ctx: WalkContext) -> list[str]:
        if not node.is_array:
            return [f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.toUpperCase();"]
        return [
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => s.toUpperCase());"
        ]

    def visit_split(self, node: Split, ctx: WalkContext) -> list[str]:
        sep = repr(node.sep)
        return [f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.split({sep});"]

    def visit_join(self, node: Join, ctx: WalkContext) -> list[str]:
        sep = repr(node.sep)
        return [f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.join({sep});"]

    def visit_norm_space(
        self, node: NormalizeSpace, ctx: WalkContext
    ) -> list[str]:
        self._builder.require_std(
            "_normalizeText",
            code="function _normalizeText(s) { return s ? s.trim().replace(/\\s+/g, ' ') : ''; }",
        )
        if not node.is_array:
            return [f"{ctx.indent}let {ctx.nxt} = _normalizeText({ctx.prv});"]
        return [
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => _normalizeText(s));"
        ]

    def visit_unescape(self, node: Unescape, ctx: WalkContext) -> list[str]:
        self._builder.require_std(
            "_unescapeText",
            code=(
                "function _unescapeText(s) {\n"
                "    const el = document.createElement('textarea');\n"
                "    el.innerHTML = s; return el.value;\n"
                "}"
            ),
        )
        if not node.is_array:
            return [f"{ctx.indent}let {ctx.nxt} = _unescapeText({ctx.prv});"]
        return [
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => _unescapeText(s));"
        ]

    # === REGEX ===

    def visit_re(self, node: Re, ctx: WalkContext) -> list[str]:
        rx = _py_re_to_js_re(node.pattern)
        if not node.is_array:
            return [f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.match({rx})[1];"]
        return [
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => s.match({rx})[1]);"
        ]

    def visit_re_all(self, node: ReAll, ctx: WalkContext) -> list[str]:
        rx_g = _py_re_to_js_re(node.pattern, global_flag=True)
        return [
            f"{ctx.indent}let {ctx.nxt} = Array.from({ctx.prv}.matchAll({rx_g}), m => m[1]);"
        ]

    def visit_re_sub(self, node: ReSub, ctx: WalkContext) -> list[str]:
        rx_g = _py_re_to_js_re(node.pattern, global_flag=True)
        repl = repr(node.repl)
        if not node.is_array:
            return [
                f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.replace({rx_g}, {repl});"
            ]
        return [
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => s.replace({rx_g}, {repl}));"
        ]

    # === ARRAY ===

    def visit_index(self, node: Index, ctx: WalkContext) -> list[str]:
        i = node.i
        i_expr = f"{ctx.prv}.length - {i}" if i < 0 else str(i)
        return [f"{ctx.indent}let {ctx.nxt} = {ctx.prv}[{i_expr}];"]

    def visit_slice(self, node: Slice, ctx: WalkContext) -> list[str]:
        start = node.start
        end = node.end
        start_expr = f"{ctx.prv}.length - {start}" if start < 0 else str(start)
        end_expr = f"{ctx.prv}.length - {end}" if end < 0 else str(end)
        return [
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.slice({start_expr}, {end_expr});"
        ]

    def visit_len(self, node: Len, ctx: WalkContext) -> list[str]:
        return [f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.length;"]

    def visit_unique(self, node: Unique, ctx: WalkContext) -> list[str]:
        if node.keep_order:
            return [
                f"{ctx.indent}let {ctx.nxt} = [...new Map({ctx.prv}.map(x=>[x,x])).keys()];"
            ]
        return [f"{ctx.indent}let {ctx.nxt} = [...new Set({ctx.prv})];"]

    # === CASTS ===

    def visit_to_int(self, node: ToInt, ctx: WalkContext) -> list[str]:
        if not node.is_array:
            return [f"{ctx.indent}let {ctx.nxt} = parseInt({ctx.prv}, 10);"]
        return [
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => parseInt(s, 10));"
        ]

    def visit_to_float(self, node: ToFloat, ctx: WalkContext) -> list[str]:
        if not node.is_array:
            return [f"{ctx.indent}let {ctx.nxt} = parseFloat({ctx.prv});"]
        return [
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => parseFloat(s));"
        ]

    def visit_to_bool(self, node: ToBool, ctx: WalkContext) -> list[str]:
        return [f"{ctx.indent}let {ctx.nxt} = Boolean({ctx.prv});"]

    def visit_jsonify(self, node: Jsonify, ctx: WalkContext) -> list[str]:
        if node.path:
            parts = jsonify_path_to_segments(node.path)
            path = "".join(f"[{p}]" for p in parts)
            return [f"{ctx.indent}let {ctx.nxt} = JSON.parse({ctx.prv}){path};"]
        return [f"{ctx.indent}let {ctx.nxt} = JSON.parse({ctx.prv});"]

    def visit_nested(self, node: Nested, ctx: WalkContext) -> list[str]:
        cls = to_pascal_case(node.struct_name)
        return [f"{ctx.indent}let {ctx.nxt} = new {cls}({ctx.prv}).parse();"]

    # === CONTROL ===

    def visit_self(self, node: Self, ctx: WalkContext) -> list[str]:
        name = to_camel_case(node.name)
        return [f"{ctx.indent}let {ctx.nxt} = this._{name};"]

    def visit_return(self, node: Return, ctx: WalkContext) -> list[str]:
        if isinstance(node.parent, PreValidate):
            return [f"{ctx.indent}return;"]
        body = getattr(node.parent, "body", None) or []
        try:
            idx = body.index(node)
        except ValueError:
            idx = -1
        if idx > 0 and isinstance(body[idx - 1], Fallback):
            return []
        return [f"{ctx.indent}return {ctx.prv};"]

    def visit_fallback(self, node: Fallback, ctx: WalkContext) -> list[str]:
        inner_ctx = ctx.deeper()
        inner_indent = inner_ctx.indent
        last_idx = ctx.index + len(node.body)
        last_var = (
            ctx.var_name if last_idx == 0 else f"{ctx.var_name}{last_idx}"
        )
        val = _js_literal(node.value)
        lines = [f"{ctx.indent}try {{"]
        lines.extend(self.walk_pipeline(node.body, inner_ctx))
        lines.extend(
            [
                f"{inner_indent}return {last_var};",
                f"{ctx.indent}}} catch (e) {{",
                f"{inner_indent}return {val};",
                f"{ctx.indent}}}",
            ]
        )
        return lines

    # === PREDICATE CONTAINERS ===

    def visit_filter(self, node: Filter, ctx: WalkContext) -> list[str]:
        lines = [f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.filter(i => ("]
        lines.extend(self.walk_children(node, ctx))
        lines.append(f"{ctx.deeper().indent}));")
        return lines

    def visit_assert(self, node: Assert, ctx: WalkContext) -> list[str]:
        ob, cb = "{", "}"
        lines: list[str] = []
        if isinstance(node.parent, PreValidate):
            setattr(node, "_local_name", "v")
            lines.append(f"{ctx.indent}if (!(")
        else:
            local = f"i{ctx.prv}"
            setattr(node, "_local_name", local)
            lines.extend(
                [
                    f"{ctx.indent}let {local} = {ctx.prv};",
                    f"{ctx.indent}if (!(",
                ]
            )
        lines.extend(self.walk_children(node, ctx))
        if isinstance(node.parent, PreValidate):
            lines.append(
                f"{ctx.indent})) {ob} throw new Error('Assertion failed'); {cb}"
            )
        else:
            lines.extend(
                [
                    f"{ctx.indent})) {ob} throw new Error('Assertion failed'); {cb}",
                    f"{ctx.indent}let {ctx.nxt} = {ctx.prv};",
                ]
            )
        return lines

    def visit_match(self, node: Match, ctx: WalkContext) -> list[str]:
        local = f"i{ctx.prv}"
        setattr(node, "_local_name", local)
        lines = [
            f"{ctx.indent}let {local} = this._tableMatchKey({ctx.prv});",
            f"{ctx.indent}if (!(",
        ]
        lines.extend(self.walk_children(node, ctx))
        lines.extend(
            [
                f"{ctx.indent})) {{ return UNMATCHED_TABLE_ROW; }}",
                f"{ctx.indent}let {ctx.nxt} = this._parseValue({ctx.prv});",
            ]
        )
        return lines

    # === LOGIC ===

    def visit_logic_and(self, node: LogicAnd, ctx: WalkContext) -> list[str]:
        lines = [_logic_prefix("&&", ctx)]
        lines.extend(self.walk_children(node, ctx))
        lines.append(ctx.indent + ")")
        return lines

    def visit_logic_or(self, node: LogicOr, ctx: WalkContext) -> list[str]:
        lines = [_logic_prefix("||", ctx)]
        lines.extend(self.walk_children(node, ctx))
        lines.append(ctx.indent + ")")
        return lines

    def visit_logic_not(self, node: LogicNot, ctx: WalkContext) -> list[str]:
        lines: list[str] = []
        if ctx.index == 0:
            lines.append(f"{ctx.indent}!(")
        else:
            lines.append(f"{ctx.indent}&& !(")
        lines.extend(self.walk_children(node, ctx))
        lines.append(ctx.indent + ")")
        return lines

    # === PREDICATES ===

    def visit_predicate_css(self, node: PredCss, ctx: WalkContext) -> list[str]:
        q = repr(node.query)
        target = _pred_target(node, ctx)
        return [self._pred_line(ctx, f"{target}.querySelector({q}) !== null")]

    def visit_predicate_xpath(
        self, node: PredXpath, ctx: WalkContext
    ) -> list[str]:
        raise NotImplementedError("XPath predicates not supported in pure JS")

    def visit_predicate_has_attr(
        self, node: PredHasAttr, ctx: WalkContext
    ) -> list[str]:
        keys = node.attrs
        target = _pred_attr_target(node, ctx)
        if len(keys) == 1:
            cond = f"{target}.hasAttribute({keys[0]!r})"
        else:
            cond = f"{py_sequence_to_js_array(keys)}.some(k => {target}.hasAttribute(k))"
        return [self._pred_line(ctx, cond)]

    def visit_predicate_attr_eq(
        self, node: PredAttrEq, ctx: WalkContext
    ) -> list[str]:
        name, values = node.name, node.values
        target = _pred_attr_target(node, ctx)
        if len(values) == 1:
            cond = f"{target}.getAttribute({name!r}) === {values[0]!r}"
        else:
            cond = f"{py_sequence_to_js_array(values)}.some(v => {target}.getAttribute({name!r}) === v)"
        return [self._pred_line(ctx, cond)]

    def visit_predicate_attr_ne(
        self, node: PredAttrNe, ctx: WalkContext
    ) -> list[str]:
        name, values = node.name, node.values
        target = _pred_attr_target(node, ctx)
        if len(values) == 1:
            cond = f"{target}.getAttribute({name!r}) !== {values[0]!r}"
        else:
            cond = f"{py_sequence_to_js_array(values)}.every(v => {target}.getAttribute({name!r}) !== v)"
        return [self._pred_line(ctx, cond)]

    def visit_predicate_attr_starts(
        self, node: PredAttrStarts, ctx: WalkContext
    ) -> list[str]:
        name, values = node.name, node.values
        target = _pred_attr_target(node, ctx)
        if len(values) == 1:
            cond = f"({target}.getAttribute({name!r}) ?? '').startsWith({values[0]!r})"
        else:
            cond = f"{py_sequence_to_js_array(values)}.some(v => ({target}.getAttribute({name!r}) ?? '').startsWith(v))"
        return [self._pred_line(ctx, cond)]

    def visit_predicate_attr_ends(
        self, node: PredAttrEnds, ctx: WalkContext
    ) -> list[str]:
        name, values = node.name, node.values
        target = _pred_attr_target(node, ctx)
        if len(values) == 1:
            cond = f"({target}.getAttribute({name!r}) ?? '').endsWith({values[0]!r})"
        else:
            cond = f"{py_sequence_to_js_array(values)}.some(v => ({target}.getAttribute({name!r}) ?? '').endsWith(v))"
        return [self._pred_line(ctx, cond)]

    def visit_predicate_attr_contains(
        self, node: PredAttrContains, ctx: WalkContext
    ) -> list[str]:
        name, values = node.name, node.values
        target = _pred_attr_target(node, ctx)
        if len(values) == 1:
            cond = f"({target}.getAttribute({name!r}) ?? '').includes({values[0]!r})"
        else:
            cond = f"{py_sequence_to_js_array(values)}.some(v => ({target}.getAttribute({name!r}) ?? '').includes(v))"
        return [self._pred_line(ctx, cond)]

    def visit_predicate_attr_re(
        self, node: PredAttrRe, ctx: WalkContext
    ) -> list[str]:
        rx = _py_re_to_js_re(node.pattern)
        target = _pred_attr_target(node, ctx)
        return [
            self._pred_line(
                ctx, f"{rx}.test({target}.getAttribute({node.name!r}) ?? '')"
            )
        ]

    def visit_predicate_text_contains(
        self, node: PredTextContains, ctx: WalkContext
    ) -> list[str]:
        values = node.values
        target = _pred_text_target(node, ctx)
        if len(values) == 1:
            cond = f"{target}.includes({values[0]!r})"
        else:
            cond = f"{py_sequence_to_js_array(values)}.some(v => {target}.includes(v))"
        return [self._pred_line(ctx, cond)]

    def visit_predicate_text_starts(
        self, node: PredTextStarts, ctx: WalkContext
    ) -> list[str]:
        values = node.values
        target = _pred_text_target(node, ctx)
        if len(values) == 1:
            cond = f"{target}.startsWith({values[0]!r})"
        else:
            cond = f"{py_sequence_to_js_array(values)}.some(v => {target}.startsWith(v))"
        return [self._pred_line(ctx, cond)]

    def visit_predicate_text_ends(
        self, node: PredTextEnds, ctx: WalkContext
    ) -> list[str]:
        values = node.values
        target = _pred_text_target(node, ctx)
        if len(values) == 1:
            cond = f"{target}.endsWith({values[0]!r})"
        else:
            cond = f"{py_sequence_to_js_array(values)}.some(v => {target}.endsWith(v))"
        return [self._pred_line(ctx, cond)]

    def visit_predicate_text_re(
        self, node: PredTextRe, ctx: WalkContext
    ) -> list[str]:
        rx = _py_re_to_js_re(node.pattern)
        target = _pred_text_target(node, ctx)
        return [self._pred_line(ctx, f"{rx}.test({target})")]

    def visit_predicate_contains(
        self, node: PredContains, ctx: WalkContext
    ) -> list[str]:
        values = node.values
        target = _pred_target(node, ctx)
        if len(values) == 1:
            cond = f"{target}.includes({values[0]!r})"
        else:
            cond = f"{py_sequence_to_js_array(values)}.some(v => {target}.includes(v))"
        return [self._pred_line(ctx, cond)]

    def visit_predicate_eq(self, node: PredEq, ctx: WalkContext) -> list[str]:
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
        return [self._pred_line(ctx, cond)]

    def visit_predicate_ne(self, node: PredNe, ctx: WalkContext) -> list[str]:
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
        return [self._pred_line(ctx, cond)]

    def visit_predicate_starts(
        self, node: PredStarts, ctx: WalkContext
    ) -> list[str]:
        values = node.values
        target = _pred_target(node, ctx)
        if len(values) == 1:
            cond = f"{target}.startsWith({values[0]!r})"
        else:
            cond = f"{py_sequence_to_js_array(values)}.some(v => {target}.startsWith(v))"
        return [self._pred_line(ctx, cond)]

    def visit_predicate_ends(
        self, node: PredEnds, ctx: WalkContext
    ) -> list[str]:
        values = node.values
        target = _pred_target(node, ctx)
        if len(values) == 1:
            cond = f"{target}.endsWith({values[0]!r})"
        else:
            cond = f"{py_sequence_to_js_array(values)}.some(v => {target}.endsWith(v))"
        return [self._pred_line(ctx, cond)]

    def visit_predicate_count_eq(
        self, node: PredCountEq, ctx: WalkContext
    ) -> list[str]:
        target = _pred_target(node, ctx)
        return [self._pred_line(ctx, f"{target}.length === {node.value}")]

    def visit_predicate_count_gt(
        self, node: PredCountGt, ctx: WalkContext
    ) -> list[str]:
        target = _pred_target(node, ctx)
        return [self._pred_line(ctx, f"{target}.length > {node.value}")]

    def visit_predicate_count_lt(
        self, node: PredCountLt, ctx: WalkContext
    ) -> list[str]:
        target = _pred_target(node, ctx)
        return [self._pred_line(ctx, f"{target}.length < {node.value}")]

    def visit_predicate_count_ne(
        self, node: PredCountNe, ctx: WalkContext
    ) -> list[str]:
        target = _pred_target(node, ctx)
        return [self._pred_line(ctx, f"{target}.length !== {node.value}")]

    def visit_predicate_count_ge(
        self, node: PredCountGe, ctx: WalkContext
    ) -> list[str]:
        target = _pred_target(node, ctx)
        return [self._pred_line(ctx, f"{target}.length >= {node.value}")]

    def visit_predicate_count_le(
        self, node: PredCountLe, ctx: WalkContext
    ) -> list[str]:
        target = _pred_target(node, ctx)
        return [self._pred_line(ctx, f"{target}.length <= {node.value}")]

    def visit_pred_count_range(
        self, node: PredCountRange, ctx: WalkContext
    ) -> list[str]:
        target = _pred_target(node, ctx)
        return [
            self._pred_line(
                ctx,
                f"{node.start} < {target}.length && {target}.length < {node.end}",
            )
        ]

    def visit_predicate_re(self, node: PredRe, ctx: WalkContext) -> list[str]:
        rx = _py_re_to_js_re(node.pattern)
        target = _pred_target(node, ctx)
        return [self._pred_line(ctx, f"{rx}.test({target})")]

    def visit_predicate_re_all(
        self, node: PredReAll, ctx: WalkContext
    ) -> list[str]:
        rx = _py_re_to_js_re(node.pattern)
        target = _pred_target(node, ctx)
        return [self._pred_line(ctx, f"{target}.every(j => {rx}.test(j))")]

    def visit_predicate_re_any(
        self, node: PredReAny, ctx: WalkContext
    ) -> list[str]:
        rx = _py_re_to_js_re(node.pattern)
        target = _pred_target(node, ctx)
        return [self._pred_line(ctx, f"{target}.some(j => {rx}.test(j))")]

    # === REST / FETCH ===

    def visit_method_rest(
        self, node: MethodRest, ctx: WalkContext
    ) -> list[str]:
        spec = node.http_request.with_renamed_placeholders(_js_name)
        http_client = ctx.meta.get("http_client", "fetch")
        ind = ctx.indent_char
        i1, i2, i3 = (ctx.indent + ind * n for n in range(3))

        ph_param = ""
        if spec.placeholders:
            ordered = [
                p.name
                for p in sorted(spec.placeholders, key=lambda p: p.is_optional)
            ]
            ph_param = ", {" + ", ".join(ordered) + "}"

        pre_lines: list[str] = []
        params_expr = None
        if spec.params:
            if dict_needs_builder(spec.params):
                pre_lines.extend(
                    _js_emit_params_builder("_params", spec.params, i3)
                )
                params_expr = "_params"
            else:
                params_expr = _js_render_obj(spec.params)
        headers_expr = None
        if spec.headers:
            if dict_needs_builder(spec.headers):
                pre_lines.extend(
                    _js_emit_obj_builder("_headers", spec.headers, i3)
                )
                headers_expr = "_headers"
            else:
                headers_expr = _js_render_obj(spec.headers)
        body_result = _js_render_body(spec)
        body_expr = body_result[1] if body_result else None

        raw_name = node.name or "fetch"
        method_name = to_camel_case(to_snake_case(raw_name))
        if raw_name == "fetch":
            method_name = "fetch"

        parent = node.parent
        errors = parent.errors if isinstance(parent, StructBase) else []
        struct_name = parent.name if isinstance(parent, StructBase) else ""
        matchers_var = f"_{to_snake_case(struct_name)}Matchers"

        ok_payload = _js_ok_payload_type(node)
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

        fn_name = self._http.fn_name
        value_fn = "(_b) => null" if not node.response_schema else "null"

        if http_client == "axios":
            url_expr = _js_render_value(spec.url)
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
                url_expr = _js_render_value(spec.url)
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
            bracket = (
                f"[params.{p.name}]" if p.is_optional else f"params.{p.name}"
            )
            lines.append(f"{i1} * @param {{{t}}} {bracket}")
        lines.append(f"{i1} * @returns {{Promise<{return_union}>}}")
        lines.append(f"{i1} */")
        lines.append(f"{i1}static async {method_name}(client{ph_param}) {{")
        lines.extend(pre_lines)
        lines.append(
            f"{i2}return {fn_name}(client, {matchers_var}, "
            f"{spec.method!r}, {url_expr}, {value_fn}, {opts_obj});"
        )
        lines.append(f"{i1}}}")
        return lines

    def visit_method_fetch(
        self, node: MethodFetch, ctx: WalkContext
    ) -> list[str]:
        spec = node.http_request.with_renamed_placeholders(_js_name)
        http_client = ctx.meta.get("http_client", "fetch")
        ind = ctx.indent_char
        i1, i2, i3 = (ctx.indent + ind * n for n in range(3))

        ph_param = ""
        if spec.placeholders:
            ordered = [
                p.name
                for p in sorted(spec.placeholders, key=lambda p: p.is_optional)
            ]
            ph_param = ", {" + ", ".join(ordered) + "}"

        pre_lines: list[str] = []
        params_expr = None
        if spec.params:
            if dict_needs_builder(spec.params):
                pre_lines.extend(
                    _js_emit_params_builder("_params", spec.params, i3)
                )
                params_expr = "_params"
            else:
                params_expr = _js_render_obj(spec.params)
        headers_expr = None
        if spec.headers:
            if dict_needs_builder(spec.headers):
                pre_lines.extend(
                    _js_emit_obj_builder("_headers", spec.headers, i3)
                )
                headers_expr = "_headers"
            else:
                headers_expr = _js_render_obj(spec.headers)
        body_result = _js_render_body(spec)
        body_expr = body_result[1] if body_result else None

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
        lines.extend(pre_lines)

        if http_client == "fetch":
            if params_expr:
                url_inner = spec.url.map(
                    lambda ph: "${" + ph.name + "}",
                    lambda s: s.replace("`", "\\`"),
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
                    f"{k}={v.source}" for k, v in spec.cookies.items()
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
                    f"{i3}// cookies: {_js_render_obj(spec.cookies)},",
                )
            if body_expr:
                req_props.append(f"{i3}data: {body_expr},")
            lines.append(f"{i2}const _resp = await client.request({{")
            lines.extend(req_props)
            lines.append(f"{i2}}});")
            lines.extend(_response_lines("_resp.data"))

        lines.append(f"{i1}}}")
        return lines
