"""pure ES6 js standard implementation. Works in modern browsers and developer console

Codegen notations:

- ES8 required if you need to use re.S (re.DOTALL) regex flag, other works in ES6
- annotations are generated in JSDoc format
    - https://jsdoc.app/
- method names (fields) auto convert to UpperCamelCase

SPECIAL METHODS NOTATIONS:

- field_name : _parse_{field_name} (add prefix `_parse` for every struct method parse)
    - `field_name` convert to UpperCamelCase
- __KEY__ -> `key`, `_parseKey`
- __VALUE__: `value`, `_parseValue`
- __ITEM__: `item`, `_parseItem`
- __PRE_VALIDATE__: `_preValidate`,
- __SPLIT_DOC__: `_splitDoc`,
- __START_PARSE__: `parse`,
"""

from ssc_codegen.converters.base import ConverterContext, BaseConverter
from ssc_codegen.ast import VariableType, StructType
from ssc_codegen.converters.helpers import (
    to_pascal_case,
    to_camel_case,
    jsonify_path_to_segments,
)

# module level
from ssc_codegen.ast import (
    Docstring,
    Imports,
    Utilities,
    JsonDef,
    JsonDefField,
    TypeDef,
    TypeDefField,
    Struct,
)

# struct layer
from ssc_codegen.ast import (
    Field,
    Init,
    InitField,
    PreValidate,
    SplitDoc,
    TableConfig,
    TableMatchKey,
    TableRow,
    Key,
    Value,
    StartParse,
    StructDocstring,
)

# selectors
from ssc_codegen.ast import (
    CssSelect,
    CssSelectAll,
    XpathSelect,
    XpathSelectAll,
    CssRemove,
    XpathRemove,
    Attr,
    Text,
    Raw,
)

# string
from ssc_codegen.ast import (
    Trim,
    Ltrim,
    Rtrim,
    RmPrefix,
    RmSuffix,
    RmPrefixSuffix,
    Fmt,
    Repl,
    ReplMap,
    Lower,
    Upper,
    Split,
    Join,
    Unescape,
    NormalizeSpace,
)

# regex
from ssc_codegen.ast import Re, ReAll, ReSub

# array
from ssc_codegen.ast import Index, Slice, Len, Unique

# casts
from ssc_codegen.ast import ToInt, ToFloat, ToBool, Jsonify, Nested

# controls
from ssc_codegen.ast import FallbackStart, FallbackEnd, Self, Return

# predicates
from ssc_codegen.ast import (
    Filter,
    Assert,
    Match,
    LogicAnd,
    LogicNot,
    LogicOr,
)

# pred exprs
from ssc_codegen.ast import (
    PredCss,
    PredContains,
    PredCountEq,
    PredCountGt,
    PredCountLt,
    PredCountNe,
    PredCountGe,
    PredCountLe,
    PredCountRange,
    PredEnds,
    PredEq,
    PredGe,
    PredGt,
    PredLe,
    PredHasAttr,
    PredIn,
    PredLt,
    PredNe,
    PredRange,
    PredRe,
    PredReAll,
    PredReAny,
    PredStarts,
    PredXpath,
    PredAttrContains,
    PredAttrEnds,
    PredAttrEq,
    PredAttrNe,
    PredAttrRe,
    PredAttrStarts,
    PredTextContains,
    PredTextEnds,
    PredTextRe,
    PredTextStarts,
)

JS_CONVERTER = BaseConverter(indent=" " * 2)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _js_str(value: str) -> str:
    """JS template-literal string."""
    return (
        "`"
        + value.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
        + "`"
    )


def _js_re(pattern: str) -> str:
    """Build a JS regex literal /pattern/flags from a pattern with inline flags.

    Pattern should have inline flags like (?i) or (?is) embedded.
    This function extracts them and converts to JS format.
    """
    import re as _re

    flags = ""
    m = _re.match(r"^\(\?([a-z]+)\)", pattern)
    if m:
        flags = "".join(c for c in m.group(1) if c in "ims")
        pattern = pattern[m.end() :]  # Remove the inline flags from pattern
    escaped = pattern.replace("/", "\\/")
    return f"/{escaped}/{flags}"


def py_sequence_to_js_array(values: tuple[str, ...] | list[str]) -> str:
    """note: value should be wrapper to"""
    val_arr = str(values)
    return "[" + val_arr[1:-1] + "]"


def _js_re_node(node) -> str:
    """Extract JS regex from a node that has a pattern attribute with inline flags."""
    return _js_re(node.pattern)


def _js_literal(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return repr(value)
    return repr(value)


def _and(cond: str, ctx: ConverterContext) -> str:
    """Predicate condition with and-chaining."""
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


def _js_typedef_type(node: TypeDefField) -> str:
    type_ = JS_TYPES.get(node.ret, "?")
    if node.ret == VariableType.JSON and node.json_ref:
        type_name = to_pascal_case(node.json_ref)
        type_ = type_.format(type_name)
        if node.is_array:
            type_ = f"Array<{type_}>"
    elif node.ret == VariableType.NESTED and node.nested_ref:
        type_name = to_pascal_case(node.nested_ref)
        type_ = type_.format(type_name)
        if node.is_array:
            type_ = f"Array<{type_}>"
    return type_


JS_TYPES = {
    VariableType.STRING: "string",
    VariableType.BOOL: "boolean",
    VariableType.INT: "number",
    VariableType.FLOAT: "number",
    VariableType.NULL: "null",
    VariableType.LIST_STRING: "Array<string>",
    VariableType.LIST_INT: "Array<number>",
    VariableType.LIST_FLOAT: "Array<number>",
    VariableType.DOCUMENT: "Element",
    VariableType.LIST_DOCUMENT: "Array<Element>",
    VariableType.OPT_STRING: "string|null",
    VariableType.OPT_INT: "number|null",
    VariableType.OPT_FLOAT: "number|null",
    VariableType.JSON: "{}Json",
    VariableType.NESTED: "{}Type",
}


# ---------------------------------------------------------------------------
# MODULE LEVEL
# ---------------------------------------------------------------------------


@JS_CONVERTER(Docstring)
def pre_docstring(node: Docstring, _: ConverterContext):
    return _js_docblock(node.value.splitlines())


@JS_CONVERTER(Imports)
def pre_imports(node: Imports, _: ConverterContext):
    return [
        '"use strict";',
        "// autogenerated by ssc-gen. DO NOT EDIT",
    ]


@JS_CONVERTER(Utilities)
def pre_utilities(node: Utilities, _: ConverterContext):
    # TODO: wrong func _replMap
    return [
        "const UNMATCHED_TABLE_ROW = Symbol('UNMATCHED_TABLE_ROW');",
        "",
        "function _replMap(s, map) {",
        "    for (const [k, v] of Object.entries(map)) s = s.split(k).join(v);",
        "    return s;",
        "}",
        "",
        "function _normalizeText(s) { return s ? s.trim().replace(/\\s+/g, ' ') : ''; }",
        "",
        "function _unescapeText(s) {",
        "    const el = document.createElement('textarea');",
        "    el.innerHTML = s; return el.value;",
        "}",
        "",
        "function _rmPrefix(s, p) { return s.startsWith(p) ? s.slice(p.length) : s; }",
        "function _rmSuffix(s, p) { return s.endsWith(p) ? s.slice(0, -p.length) : s; }",
    ]


@JS_CONVERTER(JsonDef, post_callback=" */")
def pre_json_struct(node: JsonDef, _: ConverterContext):
    name = to_pascal_case(node.name)
    return ["/**", f" * @typedef {{Object}} {name}Json"]


@JS_CONVERTER(JsonDefField)
def pre_json_field(node: JsonDefField, ctx: ConverterContext):
    name = node.alias if node.alias else node.name
    type_ = JS_TYPES.get(node.ret, "?")
    if node.ret == VariableType.JSON and node.ref_name:
        type_name = to_pascal_case(node.ref_name)
        type_ = type_.format(type_name)
        if node.is_array:
            type_ = f"Array<{type_}>"
    return f" * @property {{{type_}}} {name}"


@JS_CONVERTER(TypeDef, post_callback=" */")
def pre_typedef(node: TypeDef, _: ConverterContext):
    name = to_pascal_case(node.name)
    if node.struct_type == StructType.DICT:
        value_field = next(
            f for f in node.fields if to_camel_case(f.name) == "value"
        )
        value_type = _js_typedef_type(value_field)
        return [
            "/**",
            f" * @typedef {{Object.<string, {value_type}>}} {name}Type",
        ]
    return ["/**", f" * @typedef {{Object}} {name}Type"]


@JS_CONVERTER(TypeDefField)
def pre_typedef_field(node: TypeDefField, ctx: ConverterContext):
    if node.typedef.struct_type == StructType.DICT:
        return None

    name = to_camel_case(node.name)
    if node.typedef.struct_type == StructType.TABLE and name == "value":
        return None

    type_ = _js_typedef_type(node)
    return f" * @property {{{type_}}} {name}"


# ---------------------------------------------------------------------------
# STRUCT LEVEL
# ---------------------------------------------------------------------------


@JS_CONVERTER(Struct, post_callback="}")
def pre_struct(node: Struct, ctx: ConverterContext):
    name = to_pascal_case(node.name)
    cls_line = f"class {name} " + "{"
    if node.docstring.value:
        return [*_js_docblock(node.docstring.value.splitlines()), cls_line]
    return cls_line


@JS_CONVERTER(StructDocstring)
def pre_struct_docstring(node: StructDocstring, ctx: ConverterContext):
    return None


@JS_CONVERTER(Init)
def pre_init(node: Init, ctx: ConverterContext):
    init_names = [
        to_camel_case(i.name) for i in node.body if isinstance(i, InitField)
    ]
    lines = [
        f"{ctx.indent}constructor(document) " + "{",
        f"{ctx.indent * 2}if (typeof document === 'string') " + "{",
        f"{ctx.indent * 3}const _p = new DOMParser();",
        f"{ctx.indent * 3}this._doc = _p.parseFromString(document, 'text/html');",
        f"{ctx.indent * 2}" + "} else {",
        f"{ctx.indent * 3}this._doc = document;",
        f"{ctx.indent * 2}" + "}",
    ]
    for name in init_names:
        cap = name[0].upper() + name[1:]
        lines.append(
            f"{ctx.indent * 2}this._{name} = this._init{cap}(this._doc);"
        )
    lines.append(f"{ctx.indent}" + "}")
    return lines


@JS_CONVERTER(InitField, post_callback=lambda _, ctx: ctx.indent + "}")
def pre_init_field(node: InitField, ctx: ConverterContext):
    name = to_camel_case(node.name)
    cap = name[0].upper() + name[1:]
    return [f"{ctx.indent}_init{cap}(v) " + "{"]


@JS_CONVERTER(Field, post_callback=lambda _, ctx: ctx.indent + "}")
def pre_struct_field(node: Field, ctx: ConverterContext):
    name = to_camel_case(node.name)
    cap = name[0].upper() + name[1:]
    return [f"{ctx.indent}_parse{cap}(v) " + "{"]


@JS_CONVERTER(PreValidate, post_callback=lambda _, ctx: ctx.indent + "}")
def pre_struct_pre_validate(node: PreValidate, ctx: ConverterContext):
    # Don't create a local variable here - let the child nodes (Assert) handle it if needed
    return [
        f"{ctx.indent}_preValidate(v) " + "{",
    ]


@JS_CONVERTER(SplitDoc, post_callback=lambda _, ctx: ctx.indent + "}")
def pre_struct_split_doc(node: SplitDoc, ctx: ConverterContext):
    return [f"{ctx.indent}_splitDoc(v) " + "{"]


@JS_CONVERTER(Key, post_callback=lambda _, ctx: ctx.indent + "}")
def pre_struct_key(node: Key, ctx: ConverterContext):
    return [f"{ctx.indent}_parseKey(v) " + "{"]


@JS_CONVERTER(Value, post_callback=lambda _, ctx: ctx.indent + "}")
def pre_struct_value(node: Value, ctx: ConverterContext):
    return [f"{ctx.indent}_parseValue(v) " + "{"]


@JS_CONVERTER(TableConfig, post_callback=lambda _, ctx: ctx.indent + "}")
def pre_struct_table_config(node: TableConfig, ctx: ConverterContext):
    return [f"{ctx.indent}_tableConfig(v) " + "{"]


@JS_CONVERTER(TableMatchKey, post_callback=lambda _, ctx: ctx.indent + "}")
def pre_struct_table_match_key(node: TableMatchKey, ctx: ConverterContext):
    return [f"{ctx.indent}_tableMatchKey(v) " + "{"]


@JS_CONVERTER(TableRow, post_callback=lambda _, ctx: ctx.indent + "}")
def pre_struct_table_row(node: TableRow, ctx: ConverterContext):
    return [f"{ctx.indent}_tableRows(v) " + "{"]


@JS_CONVERTER(StartParse)
def pre_start_parse(node: StartParse, ctx: ConverterContext):
    # type
    name = to_pascal_case(node.struct.name)
    match node.struct_type:
        case StructType.ITEM:
            ret_type = f"{name}Type"
        case StructType.LIST:
            ret_type = f"Array<{name}Type>"
        case StructType.FLAT:
            ret_type = "Array<string>"
        case StructType.DICT:
            ret_type = f"{name}Type"
        case StructType.TABLE:
            ret_type = f"{name}Type"
        case _:
            raise NotImplementedError(
                "Unknown struct type", repr(node.struct_type)
            )
    return [
        f"{ctx.indent}/**",
        f"{ctx.indent}* @returns {{{ret_type}}}",
        f"{ctx.indent}*/",
        f"{ctx.indent}parse() " + "{",
    ]


@JS_CONVERTER.post(StartParse)
def post_start_parse(node: StartParse, ctx: ConverterContext):
    lines: list[str] = []
    if node.use_pre_validate:
        lines.append(f"{ctx.indent * 2}this._preValidate(this._doc);")

    def _mname(field_name: str) -> str:
        n = to_camel_case(field_name)
        return f"_parse{n[0].upper() + n[1:]}"

    match node.struct_type:
        case StructType.ITEM:
            lines.append(f"{ctx.indent * 2}return " + "{")
            for f in node.fields:
                n = to_camel_case(f.name)
                lines.append(
                    f"{ctx.indent * 3}{n}: this.{_mname(f.name)}(this._doc),"
                )
            lines.append(f"{ctx.indent * 2}" + "};")
        case StructType.LIST:
            lines.append(
                f"{ctx.indent * 2}return Array.from(this._splitDoc(this._doc)).map(i => ({{"
            )
            for f in node.fields:
                n = to_camel_case(f.name)
                lines.append(f"{ctx.indent * 3}{n}: this.{_mname(f.name)}(i),")
            close = "}));"
            lines.append(f"{ctx.indent * 2}{close}")
        case StructType.DICT:
            lines.extend(
                [
                    f"{ctx.indent * 2}return Array.from(this._splitDoc(this._doc)).reduce((acc, e) => {{",
                    f"{ctx.indent * 3}acc[this._parseKey(e)] = this._parseValue(e);",
                    f"{ctx.indent * 3}return acc;",
                    f"{ctx.indent * 2}}}, {{}});",
                ]
            )
        case StructType.FLAT:
            lines.append(f"{ctx.indent * 2}let _result = [];")
            for f in node.fields:
                if f.ret == VariableType.STRING:
                    lines.append(
                        f"{ctx.indent * 2}_result.push(this.{_mname(f.name)}(this._doc));"
                    )
                else:
                    lines.append(
                        f"{ctx.indent * 2}_result = _result.concat(this.{_mname(f.name)}(this._doc));"
                    )
            if node.struct.keep_order:
                lines.append(
                    f"{ctx.indent * 2}return [...new Map(_result.map(x=>[x,x])).keys()];"
                )
            else:
                # js Set guaranteed keep order
                lines.append(f"{ctx.indent * 2}return [...new Set(_result)];")
        case StructType.TABLE:
            lines.append(f"{ctx.indent * 2}let _result = " + "{};")
            lines.append(
                f"{ctx.indent * 2}let _table = this._tableConfig(this._doc);"
            )
            lines.append(
                f"{ctx.indent * 2}for (let _row of this._tableRows(_table)) "
                + "{"
            )
            for f in node.fields:
                n = to_camel_case(f.name)
                lines.append(
                    f"{ctx.indent * 3}let _{n} = this.{_mname(f.name)}(_row);"
                )
                lines.append(
                    f"{ctx.indent * 3}if (_{n} !== UNMATCHED_TABLE_ROW && !Object.prototype.hasOwnProperty.call(_result, {repr(n)})) _result[{repr(n)}] = _{n};"
                )
            lines.append(f"{ctx.indent * 2}" + "}")
            lines.append(f"{ctx.indent * 2}return _result;")
        case _:
            raise NotImplementedError(
                "Unknown struct type", repr(node.struct_type)
            )

    lines.append(f"{ctx.indent}" + "}")
    return lines


# ---------------------------------------------------------------------------
# EXPRESSIONS — SELECTORS
# ---------------------------------------------------------------------------


@JS_CONVERTER(CssSelect)
def pre_expr_css_select(node: CssSelect, ctx: ConverterContext):
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
    return f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.querySelector({q});"


@JS_CONVERTER(CssSelectAll)
def pre_expr_css_select_all(node: CssSelectAll, ctx: ConverterContext):
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
    return f"{ctx.indent}let {ctx.nxt} = Array.from({ctx.prv}.querySelectorAll({q}));"


@JS_CONVERTER(XpathSelect)
def pre_expr_xpath_select(node: XpathSelect, ctx: ConverterContext):
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


@JS_CONVERTER(XpathSelectAll)
def pre_expr_xpath_select_all(node: XpathSelectAll, ctx: ConverterContext):
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


@JS_CONVERTER(CssRemove)
def pre_expr_css_remove(node: CssRemove, ctx: ConverterContext):
    q = repr(node.query)
    return [
        f"{ctx.indent}{ctx.prv}.querySelectorAll({q}).forEach(e => e.remove());",
        f"{ctx.indent}let {ctx.nxt} = {ctx.prv};",
    ]


@JS_CONVERTER(XpathRemove)
def pre_expr_xpath_remove(node: XpathRemove, ctx: ConverterContext):
    q = repr(node.query)
    return [
        f"for (let {ctx.prv}r = document.evaluate({q}, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null), {ctx.prv}i = {ctx.prv}r.snapshotLength; {ctx.prv}i--; ) {ctx.prv}r.snapshotItem({ctx.prv}i).remove(); ",
        f"{ctx.indent}let {ctx.nxt} = {ctx.prv};",
    ]


@JS_CONVERTER(Attr)
def pre_expr_attr(node: Attr, ctx: ConverterContext):
    keys = node.keys
    if node.accept == VariableType.DOCUMENT:
        if len(keys) == 1:
            return f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.getAttribute({keys[0]!r});"
        kl = py_sequence_to_js_array(keys)
        return f"{ctx.indent}let {ctx.nxt} = {kl}.map(k => {ctx.prv}.getAttribute(k)).filter(Boolean);"

    # LIST_DOCUMENT
    if len(keys) == 1:
        return f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(el => el.getAttribute({keys[0]!r}));"
    kl = py_sequence_to_js_array(keys)
    return f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.flatMap(el => {kl}.map(k => el.getAttribute(k)).filter(Boolean));"


@JS_CONVERTER(Text)
def pre_expr_text(node: Text, ctx: ConverterContext):
    if node.accept == VariableType.DOCUMENT:
        return f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.textContent;"
    return f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(el => el.textContent);"


@JS_CONVERTER(Raw)
def pre_expr_raw(node: Raw, ctx: ConverterContext):
    if node.accept == VariableType.DOCUMENT:
        return f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.outerHTML;"
    return f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(el => el.outerHTML);"


# ---------------------------------------------------------------------------
# EXPRESSIONS — STRING
# ---------------------------------------------------------------------------


@JS_CONVERTER(Trim)
def pre_expr_trim(node: Trim, ctx: ConverterContext):
    substr = node.substr
    if node.accept == VariableType.STRING:
        if not substr:
            return f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.trim();"
        return [
            f"{ctx.indent}let {ctx.nxt} = (function (str, chars) {{",
            "return str.replace(new RegExp(`^[${chars}]+|[${chars}]+$`, 'g'), '');",
            f"}})({ctx.prv}, {substr!r});",
        ]
    if not substr:
        return f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => s.trim());"
    return [
        f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(e =>",
        "(function (str, chars) {",
        "return str.replace(new RegExp(`^[${chars}]+|[${chars}]+$`, 'g'), '');",
        f"}})(e, {substr!r})",
        ");",
    ]


@JS_CONVERTER(Ltrim)
def pre_expr_ltrim(node: Ltrim, ctx: ConverterContext):
    substr = node.substr
    if node.accept == VariableType.STRING:
        if not substr:
            return f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.trimStart();"
        return [
            f"{ctx.indent}let {ctx.nxt} = (function (str, chars) {{",
            "return str.replace(new RegExp(`^[${chars}]+`, 'g'), '');",
            f"}})({ctx.prv}, {substr!r});",
        ]
    if not substr:
        return f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => s.trimStart());"
    return [
        f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(e =>",
        "(function (str, chars) {",
        "return str.replace(new RegExp(`^[${chars}]+`, 'g'), '');",
        f"}})(e, {substr!r})",
    ]


@JS_CONVERTER(Rtrim)
def pre_expr_rtrim(node: Rtrim, ctx: ConverterContext):
    substr = node.substr
    if node.accept == VariableType.STRING:
        if not substr:
            return f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.trimEnd();"
        return [
            f"{ctx.indent}let {ctx.nxt} = (function (str, chars) {{",
            "return str.replace(new RegExp(`[${chars}]+$`, 'g'), '');",
            f"}})({ctx.prv}, {substr!r});",
        ]

    if not substr:
        return f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => s.trimEnd());"
    return [
        f"let {ctx.nxt} = {ctx.prv}.map(e =>",
        "(function (str, chars) {",
        "return str.replace(new RegExp(`[${chars}]+$`, 'g'), '');",
        f"}})(e, {substr!r})",
        ");",
    ]


@JS_CONVERTER(RmPrefix)
def pre_expr_rm_prefix(node: RmPrefix, ctx: ConverterContext):
    v = repr(node.substr)
    if node.accept == VariableType.STRING:
        return f"{ctx.indent}let {ctx.nxt} = _rmPrefix({ctx.prv}, {v});"
    return f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => _rmPrefix(s, {v}));"


@JS_CONVERTER(RmSuffix)
def pre_expr_rm_suffix(node: RmSuffix, ctx: ConverterContext):
    v = repr(node.substr)
    if node.accept == VariableType.STRING:
        return f"{ctx.indent}let {ctx.nxt} = _rmSuffix({ctx.prv}, {v});"
    return f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => _rmSuffix(s, {v}));"


@JS_CONVERTER(RmPrefixSuffix)
def pre_expr_rm_prefix_suffix(node: RmPrefixSuffix, ctx: ConverterContext):
    v = repr(node.substr)
    if node.accept == VariableType.STRING:
        return f"{ctx.indent}let {ctx.nxt} = _rmSuffix(_rmPrefix({ctx.prv}, {v}), {v});"
    return f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => _rmSuffix(_rmPrefix(s, {v}), {v}));"


@JS_CONVERTER(Fmt)
def pre_expr_fmt(node: Fmt, ctx: ConverterContext):
    tmpl = node.template.replace("{{}}", "${_v}").replace("`", "\\`")
    js_tmpl = "`" + tmpl + "`"
    if node.accept == VariableType.STRING:
        return f"{ctx.indent}let {ctx.nxt} = ((_v) => {js_tmpl})({ctx.prv});"
    return f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(_v => {js_tmpl});"


@JS_CONVERTER(Repl)
def pre_expr_repl(node: Repl, ctx: ConverterContext):
    old = repr(node.old)
    new = repr(node.new)
    if node.accept == VariableType.STRING:
        return (
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.replaceAll({old}, {new});"
        )
    return f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => s.replaceAll({old}, {new}));"


@JS_CONVERTER(ReplMap)
def pre_expr_repl_map(node: ReplMap, ctx: ConverterContext):
    rmap = repr(dict(node.replacements))
    if node.accept == VariableType.STRING:
        return f"{ctx.indent}let {ctx.nxt} = _replMap({ctx.prv}, {rmap});"
    return (
        f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => _replMap(s, {rmap}));"
    )


@JS_CONVERTER(Lower)
def pre_expr_lower(node: Lower, ctx: ConverterContext):
    if node.accept == VariableType.STRING:
        return f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.toLowerCase();"
    return f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => s.toLowerCase());"


@JS_CONVERTER(Upper)
def pre_expr_upper(node: Upper, ctx: ConverterContext):
    if node.accept == VariableType.STRING:
        return f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.toUpperCase();"
    return f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => s.toUpperCase());"


@JS_CONVERTER(Split)
def pre_expr_split(node: Split, ctx: ConverterContext):
    sep = repr(node.sep)
    return f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.split({sep});"


@JS_CONVERTER(Join)
def pre_expr_join(node: Join, ctx: ConverterContext):
    sep = repr(node.sep)
    return f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.join({sep});"


@JS_CONVERTER(NormalizeSpace)
def pre_expr_normalize(node: NormalizeSpace, ctx: ConverterContext):
    if node.accept == VariableType.STRING:
        return f"{ctx.indent}let {ctx.nxt} = _normalizeText({ctx.prv});"
    return f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => _normalizeText(s));"


@JS_CONVERTER(Unescape)
def pre_expr_unescape(node: Unescape, ctx: ConverterContext):
    if node.accept == VariableType.STRING:
        return f"{ctx.indent}let {ctx.nxt} = _unescapeText({ctx.prv});"
    return f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => _unescapeText(s));"


# ---------------------------------------------------------------------------
# EXPRESSIONS — REGEX
# ---------------------------------------------------------------------------


@JS_CONVERTER(Re)
def pre_expr_re(node: Re, ctx: ConverterContext):
    rx = _js_re_node(node)
    if node.accept == VariableType.STRING:
        return f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.match({rx})[1];"
    return f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => s.match({rx})[1]);"


@JS_CONVERTER(ReAll)
def pre_expr_re_all(node: ReAll, ctx: ConverterContext):
    # Extract inline flags and add 'g' for global
    import re as _re

    flags = "g"
    pattern = node.pattern
    m = _re.match(r"^\(\?([a-z]+)\)", pattern)
    if m:
        flags += "".join(c for c in m.group(1) if c in "ims")
        pattern = pattern[m.end() :]
    escaped = pattern.replace("/", "\\/")
    rx_g = f"/{escaped}/{flags}"
    return f"{ctx.indent}let {ctx.nxt} = Array.from({ctx.prv}.matchAll({rx_g}), m => m[1]);"


@JS_CONVERTER(ReSub)
def pre_expr_re_sub(node: ReSub, ctx: ConverterContext):
    # Extract inline flags and add 'g' for global
    import re as _re

    flags = "g"
    pattern = node.pattern
    m = _re.match(r"^\(\?([a-z]+)\)", pattern)
    if m:
        flags += "".join(c for c in m.group(1) if c in "ims")
        pattern = pattern[m.end() :]
    escaped = pattern.replace("/", "\\/")
    rx_g = f"/{escaped}/{flags}"
    repl = repr(node.repl)
    if node.accept == VariableType.STRING:
        return f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.replace({rx_g}, {repl});"
    return f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => s.replace({rx_g}, {repl}));"


# ---------------------------------------------------------------------------
# EXPRESSIONS — ARRAY
# ---------------------------------------------------------------------------


@JS_CONVERTER(Index)
def pre_expr_index(node: Index, ctx: ConverterContext):
    i = node.i
    if i < 0:
        i = f"{ctx.prv}.length - {i}"
    return f"{ctx.indent}let {ctx.nxt} = {ctx.prv}[{i}];"


@JS_CONVERTER(Slice)
def pre_expr_slice(node: Slice, ctx: ConverterContext):
    start = node.start
    end = node.end
    if start < 0:
        start = f"{ctx.prv}.length - {start}"
    if end < 0:
        end = f"{ctx.prv}.length - {end}"
    return f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.slice({start}, {end});"


@JS_CONVERTER(Len)
def pre_expr_len(node: Len, ctx: ConverterContext):
    return f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.length;"


@JS_CONVERTER(Unique)
def pre_expr_unique(node: Unique, ctx: ConverterContext):
    # js Set(...) guaranteed keep order
    return f"{ctx.indent}let {ctx.nxt} = [...new Set({ctx.prv})];"


# ---------------------------------------------------------------------------
# EXPRESSIONS — CASTS
# ---------------------------------------------------------------------------


@JS_CONVERTER(ToInt)
def pre_expr_to_int(node: ToInt, ctx: ConverterContext):
    if node.accept == VariableType.STRING:
        return f"{ctx.indent}let {ctx.nxt} = parseInt({ctx.prv}, 10);"
    return f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => parseInt(s, 10));"


@JS_CONVERTER(ToFloat)
def pre_expr_to_float(node: ToFloat, ctx: ConverterContext):
    if node.accept == VariableType.STRING:
        return f"{ctx.indent}let {ctx.nxt} = parseFloat({ctx.prv});"
    return f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => parseFloat(s));"


@JS_CONVERTER(ToBool)
def pre_expr_to_bool(node: ToBool, ctx: ConverterContext):
    return f"{ctx.indent}let {ctx.nxt} = Boolean({ctx.prv});"


@JS_CONVERTER(Jsonify)
def pre_expr_jsonify(node: Jsonify, ctx: ConverterContext):
    if node.path:
        parts = jsonify_path_to_segments(node.path)
        # TODO: check negative arrays (how?)
        path = "".join(
            f"[{p}]" if p.lstrip("-").isdigit() else f"[{p}]" for p in parts
        )
        return f"{ctx.indent}let {ctx.nxt} = JSON.parse({ctx.prv}){path};"
    return f"{ctx.indent}let {ctx.nxt} = JSON.parse({ctx.prv});"


@JS_CONVERTER(Nested)
def pre_expr_nested(node: Nested, ctx: ConverterContext):
    cls = to_pascal_case(node.struct_name)
    return f"{ctx.indent}let {ctx.nxt} = new {cls}({ctx.prv}).parse();"


# ---------------------------------------------------------------------------
# EXPRESSIONS — CONTROLS
# ---------------------------------------------------------------------------


@JS_CONVERTER(Self)
def pre_expr_self(node: Self, ctx: ConverterContext):
    name = to_camel_case(node.name)
    return f"{ctx.indent}let {ctx.nxt} = this._{name};"


@JS_CONVERTER(Return)
def pre_expr_return(node: Return, ctx: ConverterContext):
    if isinstance(node.parent, PreValidate):
        return f"{ctx.indent}return;"
    # ignore return stmt (inner in Fallback wrapper)
    elif isinstance(node.parent.body[0], FallbackStart):
        return
    return f"{ctx.indent}return {ctx.prv};"


@JS_CONVERTER(FallbackStart)
def pre_expr_fallback_start(node: FallbackStart, ctx: ConverterContext):
    return f"{ctx.indent}try {{"


@JS_CONVERTER(FallbackEnd)
def pre_expr_fallback_end(node: FallbackEnd, ctx: ConverterContext):
    val = _js_literal(node.value)
    ob, cb = "{", "}"
    return [
        f"{ctx.indent}return {ctx.prv};",
        f"{ctx.indent}{cb} catch (e) {ob}",
        f"{ctx.indent}{ctx.indent_char}return {val};",
        f"{ctx.indent}{cb}",
    ]


# ---------------------------------------------------------------------------
# EXPRESSIONS — PREDICATES
# ---------------------------------------------------------------------------


@JS_CONVERTER(Filter, post_callback=lambda _, ctx: ctx.deeper().indent + "));")
def pre_expr_filter(node: Filter, ctx: ConverterContext):
    return f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.filter(i => ("


@JS_CONVERTER(Assert)
def pre_expr_assert(node: Assert, ctx: ConverterContext):
    # Only create a local if we're not already inside PreValidate
    # PreValidate uses 'v' as the input, Assert predicates should evaluate against ctx.prv
    if isinstance(node.parent, PreValidate):
        # Inside PreValidate, predicates evaluate against 'v' directly
        setattr(node, "_local_name", "v")
        return [
            f"{ctx.indent}if (!(",
        ]
    else:
        # Outside PreValidate, create a local variable
        local = f"i{ctx.prv}"
        setattr(node, "_local_name", local)
        return [
            f"{ctx.indent}let {local} = {ctx.prv};",
            f"{ctx.indent}if (!(",
        ]


@JS_CONVERTER.post(Assert)
def post_expr_assert(node: Assert, ctx: ConverterContext):
    # TODO: message API
    ob, cb = "{", "}"
    if isinstance(node.parent, PreValidate):
        # Inside PreValidate, just throw and return
        return [
            f"{ctx.indent})) {ob} throw new Error('Assertion failed'); {cb}",
        ]
    else:
        return [
            f"{ctx.indent})) {ob} throw new Error('Assertion failed'); {cb}",
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv};",
        ]


@JS_CONVERTER(Match)
def pre_expr_match(node: Match, ctx: ConverterContext):
    local = f"i{ctx.prv}"
    setattr(node, "_local_name", local)
    return [
        f"{ctx.indent}let {local} = this._tableMatchKey({ctx.prv});",
        f"{ctx.indent}if (!(",
    ]


@JS_CONVERTER.post(Match)
def post_expr_match(node: Match, ctx: ConverterContext):
    # TODO: check API
    ob, cb = "{", "}"
    return [
        f"{ctx.indent})) {ob} return UNMATCHED_TABLE_ROW; {cb}",
        f"{ctx.indent}let {ctx.nxt} = this._parseValue({ctx.prv});",
    ]


@JS_CONVERTER(LogicAnd, post_callback=lambda _, ctx: ctx.indent + ")")
def pre_expr_logic_and(node: LogicAnd, ctx: ConverterContext):
    return _logic_prefix("&&", ctx)


@JS_CONVERTER(LogicOr, post_callback=lambda _, ctx: ctx.indent + ")")
def pre_expr_logic_or(node: LogicOr, ctx: ConverterContext):
    return _logic_prefix("||", ctx)


@JS_CONVERTER(LogicNot, post_callback=lambda _, ctx: ctx.indent + ")")
def pre_expr_logic_not(node: LogicNot, ctx: ConverterContext):
    if ctx.index == 0:
        return f"{ctx.indent}!("
    return f"{ctx.indent}&& !("


# ---------------------------------------------------------------------------
# PREDICATE OPS
# ---------------------------------------------------------------------------


@JS_CONVERTER(PredCss)
def pre_expr_pred_css(node: PredCss, ctx: ConverterContext):
    q = repr(node.query)
    target = _pred_target(node, ctx)
    return _and(f"{target}.querySelector({q}) !== null", ctx)


@JS_CONVERTER(PredXpath)
def pre_expr_pred_xpath(node: PredXpath, ctx: ConverterContext):
    # TODO: xpath API (its supported)
    raise NotImplementedError("XPath predicates not supported in pure JS")


@JS_CONVERTER(PredContains)
def pre_expr_pred_contains(node: PredContains, ctx: ConverterContext):
    values = node.values
    target = _pred_target(node, ctx)
    cond = (
        f"{target}.includes({values[0]!r})"
        if len(values) == 1
        else f"{py_sequence_to_js_array(values)}.some(v => {target}.includes(v))"
    )
    return _and(cond, ctx)


@JS_CONVERTER(PredEq)
def pre_expr_pred_eq(node: PredEq, ctx: ConverterContext):
    values = node.values
    target = _pred_target(node, ctx)
    if isinstance(values[0], int):
        cond = f"{target}.length === {values[0]}"
    elif len(values) == 1:
        cond = f"{target} === {values[0]!r}"
    else:
        cond = f"{py_sequence_to_js_array(values)}.some(v => {target} === v)"
    return _and(cond, ctx)


@JS_CONVERTER(PredNe)
def pre_expr_pred_ne(node: PredNe, ctx: ConverterContext):
    values = node.values
    target = _pred_target(node, ctx)
    if isinstance(values[0], int):
        cond = f"{target}.length !== {values[0]}"
    elif len(values) == 1:
        cond = f"{target} !== {values[0]!r}"
    else:
        cond = f"{py_sequence_to_js_array(values)}.every(v => {target} !== v)"
    return _and(cond, ctx)


@JS_CONVERTER(PredStarts)
def pre_expr_pred_starts(node: PredStarts, ctx: ConverterContext):
    values = node.values
    target = _pred_target(node, ctx)
    cond = (
        f"{target}.startsWith({values[0]!r})"
        if len(values) == 1
        else f"{py_sequence_to_js_array(values)}.some(v => {target}.startsWith(v))"
    )
    return _and(cond, ctx)


@JS_CONVERTER(PredEnds)
def pre_expr_pred_ends(node: PredEnds, ctx: ConverterContext):
    values = node.values
    target = _pred_target(node, ctx)
    cond = (
        f"{target}.endsWith({values[0]!r})"
        if len(values) == 1
        else f"{py_sequence_to_js_array(values)}.some(v => {target}.endsWith(v))"
    )
    return _and(cond, ctx)


# TODO: drop this node (new API used)
@JS_CONVERTER(PredCountEq)
def pre_expr_pred_count_eq(node: PredCountEq, ctx: ConverterContext):
    target = _pred_target(node, ctx)
    return _and(f"{target}.length === {node.value}", ctx)


@JS_CONVERTER(PredCountGt)
def pre_expr_pred_count_gt(node: PredCountGt, ctx: ConverterContext):
    target = _pred_target(node, ctx)
    return _and(f"{target}.length > {node.value}", ctx)


@JS_CONVERTER(PredCountLt)
def pre_expr_pred_count_lt(node: PredCountLt, ctx: ConverterContext):
    target = _pred_target(node, ctx)
    return _and(f"{target}.length < {node.value}", ctx)


@JS_CONVERTER(PredCountNe)
def pre_expr_pred_count_ne(node: PredCountNe, ctx: ConverterContext):
    target = _pred_target(node, ctx)
    return _and(f"{target}.length !== {node.value}", ctx)


@JS_CONVERTER(PredCountGe)
def pre_expr_pred_count_ge(node: PredCountGe, ctx: ConverterContext):
    target = _pred_target(node, ctx)
    return _and(f"{target}.length >= {node.value}", ctx)


@JS_CONVERTER(PredCountLe)
def pre_expr_pred_count_le(node: PredCountLe, ctx: ConverterContext):
    target = _pred_target(node, ctx)
    return _and(f"{target}.length <= {node.value}", ctx)


@JS_CONVERTER(PredCountRange)
def pre_expr_pred_count_range(node: PredCountRange, ctx: ConverterContext):
    target = _pred_target(node, ctx)
    return _and(f"{target}.length > {node.start} && {target}.length < {node.end}", ctx)


@JS_CONVERTER(PredHasAttr)
def pre_expr_pred_has_attr(node: PredHasAttr, ctx: ConverterContext):
    keys = node.attrs
    target = _pred_attr_target(node, ctx)
    cond = (
        f"{target}.hasAttribute({keys[0]!r})"
        if len(keys) == 1
        else f"{py_sequence_to_js_array(keys)}.some(k => {target}.hasAttribute(k))"
    )
    return _and(cond, ctx)


@JS_CONVERTER(PredAttrEq)
def pre_expr_pred_attr_eq(node: PredAttrEq, ctx: ConverterContext):
    name, values = node.name, node.values
    target = _pred_attr_target(node, ctx)
    cond = (
        f"{target}.getAttribute({name!r}) === {values[0]!r}"
        if len(values) == 1
        else f"{py_sequence_to_js_array(values)}.some(v => {target}.getAttribute({name!r}) === v)"
    )
    return _and(cond, ctx)


@JS_CONVERTER(PredAttrNe)
def pre_expr_pred_attr_ne(node: PredAttrNe, ctx: ConverterContext):
    name, values = node.name, node.values
    target = _pred_attr_target(node, ctx)
    cond = (
        f"{target}.getAttribute({name!r}) !== {values[0]!r}"
        if len(values) == 1
        else f"{py_sequence_to_js_array(values)}.every(v => {target}.getAttribute({name!r}) !== v)"
    )
    return _and(cond, ctx)


@JS_CONVERTER(PredAttrStarts)
def pre_expr_pred_attr_starts(node: PredAttrStarts, ctx: ConverterContext):
    name, values = node.name, node.values
    target = _pred_attr_target(node, ctx)
    cond = (
        f"({target}.getAttribute({name!r}) ?? '').startsWith({values[0]!r})"
        if len(values) == 1
        else f"{py_sequence_to_js_array(values)}.some(v => ({target}.getAttribute({name!r}) ?? '').startsWith(v))"
    )
    return _and(cond, ctx)


@JS_CONVERTER(PredAttrEnds)
def pre_expr_pred_attr_ends(node: PredAttrEnds, ctx: ConverterContext):
    name, values = node.name, node.values
    target = _pred_attr_target(node, ctx)
    cond = (
        f"({target}.getAttribute({name!r}) ?? '').endsWith({values[0]!r})"
        if len(values) == 1
        else f"{py_sequence_to_js_array(values)}.some(v => ({target}.getAttribute({name!r}) ?? '').endsWith(v))"
    )
    return _and(cond, ctx)


@JS_CONVERTER(PredAttrContains)
def pre_expr_pred_attr_contains(node: PredAttrContains, ctx: ConverterContext):
    name, values = node.name, node.values
    target = _pred_attr_target(node, ctx)
    cond = (
        f"({target}.getAttribute({name!r}) ?? '').includes({values[0]!r})"
        if len(values) == 1
        else f"{py_sequence_to_js_array(values)}.some(v => ({target}.getAttribute({name!r}) ?? '').includes(v))"
    )
    return _and(cond, ctx)


@JS_CONVERTER(PredAttrRe)
def pre_expr_pred_attr_re(node: PredAttrRe, ctx: ConverterContext):
    rx = _js_re_node(node)
    target = _pred_attr_target(node, ctx)
    return _and(f"{rx}.test({target}.getAttribute({node.name!r}) ?? '')", ctx)


@JS_CONVERTER(PredTextContains)
def pre_expr_pred_text_contains(node: PredTextContains, ctx: ConverterContext):
    values = node.values
    target = _pred_text_target(node, ctx)
    cond = (
        f"{target}.includes({values[0]!r})"
        if len(values) == 1
        else f"{py_sequence_to_js_array(values)}.some(v => {target}.includes(v))"
    )
    return _and(cond, ctx)


@JS_CONVERTER(PredTextStarts)
def pre_expr_pred_text_starts(node: PredTextStarts, ctx: ConverterContext):
    values = node.values
    target = _pred_text_target(node, ctx)
    cond = (
        f"{target}.startsWith({values[0]!r})"
        if len(values) == 1
        else f"{py_sequence_to_js_array(values)}.some(v => {target}.startsWith(v))"
    )
    return _and(cond, ctx)


@JS_CONVERTER(PredTextEnds)
def pre_expr_pred_text_ends(node: PredTextEnds, ctx: ConverterContext):
    values = node.values
    target = _pred_text_target(node, ctx)
    cond = (
        f"{target}.endsWith({values[0]!r})"
        if len(values) == 1
        else f"{py_sequence_to_js_array(values)}.some(v => {target}.endsWith(v))"
    )
    return _and(cond, ctx)


@JS_CONVERTER(PredTextRe)
def pre_expr_pred_text_re(node: PredTextRe, ctx: ConverterContext):
    rx = _js_re_node(node)
    target = _pred_text_target(node, ctx)
    return _and(f"{rx}.test({target})", ctx)


@JS_CONVERTER(PredIn)
def pre_expr_pred_in(node: PredIn, ctx: ConverterContext):
    values = node.values
    target = _pred_target(node, ctx)
    return _and(f"{py_sequence_to_js_array(values)}.includes({target})", ctx)


@JS_CONVERTER(PredGe)
def pre_expr_pred_ge(node: PredGe, ctx: ConverterContext):
    target = _pred_target(node, ctx)
    return _and(f"{target}.length >= {node.value}", ctx)


@JS_CONVERTER(PredGt)
def pre_expr_pred_gt(node: PredGt, ctx: ConverterContext):
    target = _pred_target(node, ctx)
    return _and(f"{target}.length > {node.value}", ctx)


@JS_CONVERTER(PredLe)
def pre_expr_pred_le(node: PredLe, ctx: ConverterContext):
    target = _pred_target(node, ctx)
    return _and(f"{target}.length <= {node.value}", ctx)


@JS_CONVERTER(PredLt)
def pre_expr_pred_lt(node: PredLt, ctx: ConverterContext):
    target = _pred_target(node, ctx)
    return _and(f"{target}.length < {node.value}", ctx)


@JS_CONVERTER(PredRange)
def pre_expr_pred_range(node: PredRange, ctx: ConverterContext):
    target = _pred_target(node, ctx)
    return _and(
        f"{node.start} < {target}.length && {target}.length < {node.end}", ctx
    )


@JS_CONVERTER(PredRe)
def pre_expr_pred_re(node: PredRe, ctx: ConverterContext):
    rx = _js_re_node(node)
    target = _pred_target(node, ctx)
    return _and(f"{rx}.test({target})", ctx)


@JS_CONVERTER(PredReAll)
def pre_expr_pred_re_all(node: PredReAll, ctx: ConverterContext):
    rx = _js_re_node(node)
    target = _pred_target(node, ctx)
    return _and(f"{target}.every(j => {rx}.test(j))", ctx)


@JS_CONVERTER(PredReAny)
def pre_expr_pred_re_any(node: PredReAny, ctx: ConverterContext):
    rx = _js_re_node(node)
    target = _pred_target(node, ctx)
    return _and(f"{target}.some(j => {rx}.test(j))", ctx)
