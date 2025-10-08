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

from typing import cast

from ssc_codegen.ast_ import (
    Docstring,
    StructParser,
    ExprReturn,
    ExprNoReturn,
    ExprNested,
    StructPreValidateMethod,
    StructFieldMethod,
    StartParseMethod,
    StructInitMethod,
    ExprDefaultValueStart,
    ExprDefaultValueEnd,
    ExprStringFormat,
    ExprListStringFormat,
    ExprStringTrim,
    ExprListStringTrim,
    ExprStringLeftTrim,
    ExprListStringLeftTrim,
    ExprStringRightTrim,
    ExprListStringRightTrim,
    ExprStringSplit,
    ExprStringReplace,
    ExprListStringReplace,
    ExprStringRegex,
    ExprStringRegexAll,
    ExprStringRegexSub,
    ExprListStringRegexSub,
    ExprIndex,
    ExprListStringJoin,
    ExprIsEqual,
    ExprIsNotEqual,
    ExprIsContains,
    ExprStringIsRegex,
    ExprToInt,
    ExprToListInt,
    ExprToFloat,
    ExprToListFloat,
    ExprToListLength,
    ExprToBool,
    ExprJsonify,
    ExprCss,
    ExprCssAll,
    ExprXpath,
    ExprXpathAll,
    ExprGetHtmlAttr,
    ExprGetHtmlAttrAll,
    ExprGetHtmlText,
    ExprGetHtmlTextAll,
    ExprGetHtmlRaw,
    ExprGetHtmlRawAll,
    StructPartDocMethod,
    ExprIsCss,
    ExprIsXpath,
    ExprStringRmPrefix,
    ExprListStringRmPrefix,
    ExprStringRmSuffix,
    ExprListStringRmSuffix,
    ExprStringRmPrefixAndSuffix,
    ExprListStringRmPrefixAndSuffix,
    ExprListStringAnyRegex,
    ExprListStringAllRegex,
    ExprListHasAttr,
    ExprHasAttr,
    FilterEqual,
    FilterNotEqual,
    FilterStrRe,
    FilterStrEnds,
    FilterStrStarts,
    FilterStrIn,
    FilterNot,
    FilterAnd,
    FilterOr,
    ExprFilter,
    FilterStrLenEq,
    FilterStrLenNe,
    FilterStrLenLt,
    FilterStrLenLe,
    FilterStrLenGt,
    FilterStrLenGe,
    ExprListUnique,
    ExprStringMapReplace,
    ExprListStringMapReplace,
    ExprClassVar,
)
from ssc_codegen.ast_.nodes_cast import ExprJsonifyDynamic
from ssc_codegen.ast_.nodes_core import (
    JsonStruct,
    JsonStructField,
    ModuleImports,
    TypeDef,
    TypeDefField,
)
from ssc_codegen.ast_.nodes_selectors import (
    ExprCssElementRemove,
    ExprMapAttrs,
    ExprMapAttrsAll,
    ExprXpathElementRemove,
)
from ssc_codegen.ast_.nodes_string import (
    ExprListStringUnescape,
    ExprStringUnescape,
)
from ssc_codegen.converters.base import BaseCodeConverter
from ssc_codegen.converters.helpers import (
    get_typedef_field_by_name,
    js_get_classvar_hook_or_value,
    jsonify_query_parse,
    prev_next_var,
    is_last_var_no_ret,
    have_pre_validate_call,
    is_first_node_cond,
    is_prev_node_atomic_cond,
)
from ssc_codegen.converters.templates.js_pure import (
    HELPER_FUNCTIONS,
    J2_STRUCT_INIT,
    J2_PRE_LIST_STR_TRIM,
    J2_PRE_STR_LEFT_TRIM,
    J2_PRE_LIST_STR_LEFT_TRIM,
    J2_PRE_STR_RIGHT_TRIM,
    J2_PRE_LIST_STR_RIGHT_TRIM,
    J2_PRE_XPATH,
    J2_PRE_XPATH_ALL,
    J2_PRE_STR_TRIM,
    J2_IS_XPATH,
)
from ssc_codegen.str_utils import (
    wrap_backtick,
    to_upper_camel_case,
)
from ssc_codegen.tokens import (
    JsonVariableType,
    StructType,
    TokenType,
    VariableType,
)

MAGIC_METHODS = {
    "__ITEM__": "Item",
    "__KEY__": "Key",
    "__VALUE__": "Value",
}
# Constants are deliberately used to avoid missing a character in the visitor
BRACKET_START = "{"
BRACKET_END = "}"

DOCSTR_START = "/**"
DOCSTR_END = "*/"
DOCSTR_SEP = "* "
CONVERTER = BaseCodeConverter(debug_comment_prefix="// ")
# javascript not support typing/annotations
CONVERTER.TEST_EXCLUDE_NODES.extend(
    [
        TokenType.TYPEDEF,
        TokenType.TYPEDEF_FIELD,
        TokenType.JSON_STRUCT,
        TokenType.JSON_FIELD,
    ]
)


# TODO: move to string_utils
def to_js_regexp(
    pattern: str,
    ignore_case: bool = False,
    is_global: bool = True,
    dotall: bool = False,
) -> str:
    """helper function for convert string pattern to js"""
    # fix backslashes translate
    pattern = pattern.replace("/", r"\/").replace(r"\\/", r"\/")

    pattern = f"/{pattern}/"
    if is_global:
        pattern += "g"
    if ignore_case:
        pattern += "i"
    # NOTE: ES9 (ES2018) supports only
    if dotall:
        pattern += "s"
    return pattern


def make_js_docstring(value: str) -> str:
    if not value:
        return ""
    docstr_start = DOCSTR_START
    docstr_parts = "\n".join(DOCSTR_SEP + line for line in value.split("\n"))
    docstr_end = DOCSTR_END
    return docstr_start + docstr_parts + docstr_end


def py_sequence_to_js_array(values: tuple[str, ...] | list[str]) -> str:
    """note: value should be wrapper to"""
    val_arr = str(values)
    return "[" + val_arr[1:-1] + "]"


@CONVERTER(ModuleImports.kind)
def pre_imports(_: ModuleImports) -> str:
    return HELPER_FUNCTIONS


@CONVERTER(Docstring.kind)
def pre_docstring(node: Docstring) -> str:
    value = node.kwargs["value"]
    docstr = make_js_docstring(value)
    return docstr


@CONVERTER(StructPartDocMethod.kind, post_callback=lambda _: BRACKET_END)
def pre_part_doc(_node: StructPartDocMethod) -> str:
    return "_splitDoc(v) " + BRACKET_START


@CONVERTER(StructParser.kind, post_callback=lambda _: BRACKET_END)
def pre_struct_parser(node: StructParser) -> str:
    name = node.kwargs["name"]
    docstr = make_js_docstring(node.kwargs["docstring"])
    return docstr + "\n" + f"class {name}" + BRACKET_START


@CONVERTER(ExprReturn.kind)
def pre_return(node: ExprReturn) -> str:
    return f"return v{node.index_prev};"


@CONVERTER(ExprNoReturn.kind)
def pre_no_return(_node: ExprReturn) -> str:
    return "return;"


@CONVERTER(ExprNested.kind)
def pre_nested(node: ExprNested) -> str:
    prv, nxt = prev_next_var(node)
    schema_name, schema_type = node.unpack_args()
    return f"let {nxt} = (new {schema_name}({prv})).parse();"


@CONVERTER(StructPreValidateMethod.kind)
def pre_pre_validate(_node: StructPreValidateMethod) -> str:
    return "_preValidate(v)" + BRACKET_START


@CONVERTER(ExprClassVar.kind)
def pre_classvar(node: ExprClassVar) -> str:
    value, _class_name, field_name, *_ = node.unpack_args()

    # fmt string generate a single line func

    if isinstance(value, str):
        if "{{}}" in value:
            value = wrap_backtick(value.replace("{{}}", "${e}"))
            return f"static {field_name} = (e) => {value}; "
        value = repr(value)
    elif isinstance(value, bool):
        value = "true" if value else "false"

    return f"static {field_name} = {value}; "


@CONVERTER(StructFieldMethod.kind, post_callback=lambda _: BRACKET_END)
def pre_parse_field(node: StructFieldMethod) -> str:
    name = node.kwargs["name"]
    name = MAGIC_METHODS.get(name, name)
    fn_name = "_parse" + to_upper_camel_case(name)
    return f"{fn_name}(v)" + BRACKET_START


@CONVERTER(StructInitMethod.kind)
def pre_struct_init(_node: StructInitMethod) -> str:
    return J2_STRUCT_INIT


JSDOC_TYPES = {
    VariableType.ANY: "?",
    VariableType.STRING: "string",
    VariableType.LIST_STRING: "Array<string>",
    VariableType.OPTIONAL_STRING: "string | null",
    VariableType.OPTIONAL_LIST_STRING: "Array<string> | null",
    VariableType.OPTIONAL_INT: "number | null",
    VariableType.OPTIONAL_LIST_INT: "Array<number> | null",
    VariableType.OPTIONAL_FLOAT: "Array<number> | null",
    VariableType.OPTIONAL_LIST_FLOAT: "Array<number> | null",
    VariableType.INT: "number",
    VariableType.FLOAT: "number",
    VariableType.LIST_INT: "Array<number>",
    VariableType.LIST_FLOAT: "Array<number>",
    VariableType.BOOL: "boolean",
}

JSDOC_JSON_TYPES = {
    JsonVariableType.BOOLEAN: "boolean",
    JsonVariableType.STRING: "string",
    JsonVariableType.NUMBER: "number",
    JsonVariableType.FLOAT: "number",
    JsonVariableType.NULL: "null",
    JsonVariableType.OPTIONAL_STRING: "string | null",
    JsonVariableType.OPTIONAL_NUMBER: "number | null",
    JsonVariableType.OPTIONAL_FLOAT: "number | null",
    JsonVariableType.OPTIONAL_BOOLEAN: "boolean | null",
    JsonVariableType.ARRAY: "Array",
    JsonVariableType.ARRAY_FLOAT: "Array<number>",
    JsonVariableType.ARRAY_NUMBER: "Array<number>",
    JsonVariableType.ARRAY_STRING: "Array<string>",
    JsonVariableType.ARRAY_BOOLEAN: "Array<boolean>",
}


# TYPEDEF
@CONVERTER(TypeDef.kind, StructType.ITEM, post_callback=lambda _: "*/\n")
def pre_typedef_item(node: TypeDef) -> str:
    name, _ = node.unpack_args()
    code = "/**\n"
    code += "* @typedef {Object} " + f"T_{name}"
    return code


@CONVERTER(TypeDef.kind, StructType.LIST, post_callback=lambda _: "*/\n")
def pre_typedef_list(node: TypeDef) -> str:
    name, _ = node.unpack_args()
    code = "/**\n"
    code += "* @typedef {Object} " + f"T_{name}"
    return code


@CONVERTER(TypeDef.kind, StructType.DICT, post_callback=lambda _: "*/\n")
def pre_typedef_dict(node: TypeDef) -> str:
    name, _ = node.unpack_args()
    code = "/**\n"
    value = get_typedef_field_by_name(node, "__VALUE__")
    _, var_type, *_ = value.unpack_args()
    type_ = JSDOC_TYPES[var_type]
    code += "* @typedef {Map<string, " + type_ + ">} " + f"T_{name}"
    return code


@CONVERTER(TypeDef.kind, StructType.FLAT_LIST, post_callback=lambda _: "*/\n")
def pre_typedef_flat_list(node: TypeDef) -> str:
    name, _ = node.unpack_args()
    code = "/**\n"
    value = get_typedef_field_by_name(node, "__ITEM__")
    _, var_type, *_ = value.unpack_args()
    type_ = JSDOC_TYPES[var_type]
    code += "* @typedef {Array<" + type_ + ">} " + f"T_{name}"
    return code


@CONVERTER(TypeDef.kind, StructType.ACC_LIST, post_callback=lambda _: "*/\n")
def pre_typedef_acc_list(node: TypeDef) -> str:
    name, _ = node.unpack_args()
    code = "/**\n"
    code += "* @typedef {Array<string>} " + f"T_{name}"
    return code


@CONVERTER(TypeDefField.kind)
def pre_typedef_field(node: TypeDefField) -> str:
    name, var_type, cls_nested, cls_nested_type = node.unpack_args()
    node.parent = cast(TypeDef, node.parent)
    # skip format
    if node.parent.struct_type in (
        StructType.DICT,
        StructType.FLAT_LIST,
        StructType.ACC_LIST,
    ):
        return ""
    # always str
    if name == "__KEY__":
        return ""

    elif var_type == VariableType.NESTED:
        type_ = f"T_{cls_nested}"
        if cls_nested_type == StructType.LIST:
            type_ = f"Array<{type_}>"
    elif var_type == VariableType.JSON:
        type_ = f"J_{cls_nested}"
        if cls_nested_type == StructType.LIST:
            type_ = f"Array<{type_}>"
    else:
        type_ = JSDOC_TYPES[var_type]
    return "* @property {" + type_ + "} " + name


@CONVERTER(JsonStruct.kind, post_callback=lambda _: "\n\n")
def pre_json_struct(node: JsonStruct) -> str:
    name, _is_array = node.unpack_args()
    return "//*\n" + "* @typedef {Object} " + f"J_{name}"


@CONVERTER(JsonStructField.kind)
def pre_json_struct_field(node: JsonStructField) -> str:
    name, var_type = node.unpack_args()
    type_ = JSDOC_JSON_TYPES.get(var_type)
    return "* @property {" + type_ + "} " + name


# START PARSE
@CONVERTER(
    StartParseMethod.kind, StructType.ITEM, post_callback=lambda _: BRACKET_END
)
def pre_start_parse_item(node: StartParseMethod) -> str:
    node.parent = cast(StructParser, node.parent)
    st_name = node.parent.kwargs["name"]
    st_type = node.parent.kwargs["struct_type"]
    ret_type = (
        "Array<" + f"T_{st_name}" + ">"
        if st_type == StructType.LIST
        else f"T_{st_name}"
    )
    code = "/**\n" + "* " + "@returns " + "{" + ret_type + "}\n" + "*/\n"
    code += "parse() " + BRACKET_START

    if have_pre_validate_call(node):
        code += "this._preValidate(this._doc); "
    code += "return {"
    for expr in node.body:
        if expr.kind == TokenType.STRUCT_CALL_CLASSVAR:
            st_name, f_name, _ = expr.unpack_args()
            code += f"{f_name!r}: {st_name}.{f_name},"
        elif expr.kind == TokenType.STRUCT_CALL_FUNCTION and not expr.kwargs[
            "name"
        ].startswith("__"):
            name = expr.kwargs["name"]
            method_suffix = to_upper_camel_case(expr.kwargs["name"])
            code += f"{name}: this._parse{method_suffix}(this._doc), "
    code += "};"
    return code


@CONVERTER(
    StartParseMethod.kind, StructType.LIST, post_callback=lambda _: BRACKET_END
)
def pre_start_parse_list(node: StartParseMethod) -> str:
    code = "parse() " + BRACKET_START

    if have_pre_validate_call(node):
        code += "this._preValidate(this._doc); "
    code += "return Array.from(this._splitDoc(this._doc)).map((e) => ({"
    for expr in node.body:
        if expr.kind == TokenType.STRUCT_CALL_CLASSVAR:
            st_name, f_name, _ = expr.unpack_args()
            code += f"{f_name!r}: {st_name}.{f_name},"
        elif expr.kind == TokenType.STRUCT_CALL_FUNCTION and not expr.kwargs[
            "name"
        ].startswith("__"):
            name = expr.kwargs["name"]
            method_suffix = to_upper_camel_case(expr.kwargs["name"])
            code += f"{name}: this._parse{method_suffix}(this._doc), "
    code += "})); "
    return code


@CONVERTER(
    StartParseMethod.kind, StructType.DICT, post_callback=lambda _: BRACKET_END
)
def pre_start_parse_dict(node: StartParseMethod) -> str:
    code = "parse() " + BRACKET_START

    if have_pre_validate_call(node):
        code += "this._preValidate(this._doc); "
    code += "return Array.from(this._splitDoc(this._doc)).reduce((item, e) => "
    "(item[this._parseKey(e)] = this._parseValue(e), item), {});"
    return code


@CONVERTER(
    StartParseMethod.kind,
    StructType.FLAT_LIST,
    post_callback=lambda _: BRACKET_END,
)
def pre_start_parse_flat_list(node: StartParseMethod) -> str:
    code = "parse() " + BRACKET_START

    if have_pre_validate_call(node):
        code += "this._preValidate(this._doc); "
    code += "return Array.from(this._splitDoc(this._doc)).map((e) => this._parseItem(e));"
    return code


@CONVERTER(
    StartParseMethod.kind,
    StructType.ACC_LIST,
    post_callback=lambda _: BRACKET_END,
)
def pre_start_parse_acc_List(node: StartParseMethod) -> str:
    code = "parse() " + BRACKET_START

    if have_pre_validate_call(node):
        code += "this._preValidate(this._doc); "
    code += "return [...new Set(["
    for expr in node.body:
        method_suffix = to_upper_camel_case(expr.kwargs["name"])
        code += f"this._parse{method_suffix}(this._doc),"
    code += "].flat())]; "
    return code


@CONVERTER(ExprDefaultValueStart.kind)
def pre_default_start(node: ExprDefaultValueStart) -> str:
    prv, nxt = prev_next_var(node)
    return f"let {nxt} = {prv};" + "try " + BRACKET_START


@CONVERTER(ExprDefaultValueEnd.kind)
def pre_default_end(node: ExprDefaultValueEnd) -> str:
    value = js_get_classvar_hook_or_value(node, "value")

    return f"}}catch(Error) {{ return {value}; }}"


@CONVERTER(ExprStringFormat.kind)
def pre_str_fmt(node: ExprStringFormat) -> str:
    prv, nxt = prev_next_var(node)
    fmt = js_get_classvar_hook_or_value(
        node,
        "fmt",
        # called classvar signature:
        # static {CLS_NAME}.{VALUE} = (fmt) => `template ${fmt}`;
        cb_literal_cast=lambda e: ".".join(e.literal_ref_name) + f"({prv})",
        cb_value_cast=lambda i: wrap_backtick(
            i.replace("{{}}", "${" + prv + "}")
        ),
    )
    return f"let {nxt} = {fmt};"


@CONVERTER(ExprListStringFormat.kind)
def pre_list_str_fmt(node: ExprListStringFormat) -> str:
    prv, nxt = prev_next_var(node)
    fmt = js_get_classvar_hook_or_value(
        node,
        "fmt",
        # called classvar signature:
        # static {CLS_NAME}.{VALUE} = (fmt) => `template ${fmt}`;
        cb_literal_cast=lambda e: ".".join(e.literal_ref_name) + "(e)",
        # string input, replace to placeholder
        cb_value_cast=lambda i: wrap_backtick(i.replace("{{}}", "${e}")),
    )
    return f"let {nxt} = {prv}.map(e => {fmt});"


@CONVERTER(ExprStringTrim.kind)
def pre_str_trim(node: ExprStringTrim) -> str:
    prv, nxt = prev_next_var(node)
    substr = js_get_classvar_hook_or_value(node, "substr")
    return J2_PRE_STR_TRIM.render(nxt=nxt, prv=prv, substr=substr)


@CONVERTER(ExprListStringTrim.kind)
def pre_list_str_trim(node: ExprListStringTrim) -> str:
    prv, nxt = prev_next_var(node)
    substr = js_get_classvar_hook_or_value(node, "substr")
    return J2_PRE_LIST_STR_TRIM.render(prv=prv, nxt=nxt, substr=substr)


@CONVERTER(ExprStringLeftTrim.kind)
def pre_str_left_trim(node: ExprStringLeftTrim) -> str:
    prv, nxt = prev_next_var(node)
    substr = js_get_classvar_hook_or_value(node, "substr")
    return J2_PRE_STR_LEFT_TRIM.render(prv=prv, nxt=nxt, substr=substr)


@CONVERTER(ExprListStringLeftTrim.kind)
def pre_list_str_left_trim(node: ExprListStringLeftTrim) -> str:
    prv, nxt = prev_next_var(node)
    substr = js_get_classvar_hook_or_value(node, "substr")
    return J2_PRE_LIST_STR_LEFT_TRIM.render(prv=prv, nxt=nxt, substr=substr)


@CONVERTER(ExprStringRightTrim.kind)
def pre_str_right_trim(node: ExprStringRightTrim) -> str:
    prv, nxt = prev_next_var(node)
    substr = js_get_classvar_hook_or_value(node, "substr")
    return J2_PRE_STR_RIGHT_TRIM.render(prv=prv, nxt=nxt, substr=substr)


@CONVERTER(ExprListStringRightTrim.kind)
def pre_list_str_right_trim(node: ExprListStringRightTrim) -> str:
    prv, nxt = prev_next_var(node)
    substr = js_get_classvar_hook_or_value(node, "substr")
    return J2_PRE_LIST_STR_RIGHT_TRIM.render(prv=prv, nxt=nxt, substr=substr)


@CONVERTER(ExprStringSplit.kind)
def pre_str_split(node: ExprStringSplit) -> str:
    prv, nxt = prev_next_var(node)
    sep = js_get_classvar_hook_or_value(node, "sep")
    return f"let {nxt} = {prv}.split({sep});"


@CONVERTER(ExprStringReplace.kind)
def pre_str_replace(node: ExprStringReplace) -> str:
    prv, nxt = prev_next_var(node)
    old = js_get_classvar_hook_or_value(node, "old")
    new = js_get_classvar_hook_or_value(node, "new")

    return f"let {nxt} = {prv}.replaceAll({old}, {new});"


@CONVERTER(ExprListStringReplace.kind)
def pre_list_str_replace(node: ExprListStringReplace) -> str:
    prv, nxt = prev_next_var(node)
    old = js_get_classvar_hook_or_value(node, "old")
    new = js_get_classvar_hook_or_value(node, "new")
    return f"let {nxt} = {prv}.map(e => e.replaceAll({old}, {new}));"


@CONVERTER(ExprStringRegex.kind)
def pre_str_regex(node: ExprStringRegex) -> str:
    prv, nxt = prev_next_var(node)
    pattern, group, ignore_case, dotall = node.unpack_args()
    if node.classvar_hooks.get("pattern"):
        pattern = js_get_classvar_hook_or_value(node, "pattern")
    else:
        pattern = to_js_regexp(
            pattern, ignore_case, is_global=False, dotall=dotall
        )

    return f"let {nxt} = {prv}.match({pattern})[{group}];"


@CONVERTER(ExprStringRegexAll.kind)
def pre_str_regex_all(node: ExprStringRegexAll) -> str:
    prv, nxt = prev_next_var(node)
    pattern, ignore_case, dotall = node.unpack_args()
    if node.classvar_hooks.get("pattern"):
        pattern = js_get_classvar_hook_or_value(node, "pattern")
    else:
        pattern = to_js_regexp(pattern, ignore_case, dotall=dotall)
    return f"let {nxt} = Array.from({prv}.match({pattern}));"


@CONVERTER(ExprStringRegexSub.kind)
def pre_str_regex_sub(node: ExprStringRegexSub) -> str:
    prv, nxt = prev_next_var(node)
    pattern, repl, ignore_case, dotall = node.unpack_args()

    repl = js_get_classvar_hook_or_value(node, "repl")
    if node.classvar_hooks.get("pattern"):
        pattern = js_get_classvar_hook_or_value(node, "pattern")
    else:
        pattern = to_js_regexp(pattern, ignore_case=ignore_case, dotall=dotall)

    return f"let {nxt} = {prv}.replace({pattern}, {repl});"


@CONVERTER(ExprListStringRegexSub.kind)
def pre_list_str_regex_sub(node: ExprListStringRegexSub) -> str:
    prv, nxt = prev_next_var(node)
    pattern, repl, ignore_case, dotall = node.unpack_args()

    repl = js_get_classvar_hook_or_value(node, "repl")
    if node.classvar_hooks.get("pattern"):
        pattern = js_get_classvar_hook_or_value(node, "pattern")
    else:
        pattern = to_js_regexp(pattern, ignore_case=ignore_case, dotall=dotall)

    return f"let {nxt} = {prv}.map(e => e.replace({pattern}, {repl!r}));"


@CONVERTER(ExprIndex.kind)
def pre_index(node: ExprIndex) -> str:
    prv, nxt = prev_next_var(node)

    index = js_get_classvar_hook_or_value(node, "index")
    return f"let {nxt} = {prv}[{index}];"


@CONVERTER(ExprListStringJoin.kind)
def pre_list_str_join(node: ExprListStringJoin) -> str:
    prv, nxt = prev_next_var(node)
    sep = js_get_classvar_hook_or_value(node, "sep")
    return f"let {nxt} = {prv}.join({sep});"


@CONVERTER(ExprIsEqual.kind)
def pre_is_equal(node: ExprIsEqual) -> str:
    prv, nxt = prev_next_var(node)

    item = js_get_classvar_hook_or_value(node, "item")
    msg = js_get_classvar_hook_or_value(node, "msg")

    expr = f"if ({item} != {prv}) throw new Error({msg});"
    if is_last_var_no_ret(node):
        return expr
    return expr + f"let {nxt} = {prv};"


@CONVERTER(ExprIsNotEqual.kind)
def pre_is_not_equal(node: ExprIsNotEqual) -> str:
    prv, nxt = prev_next_var(node)

    item = js_get_classvar_hook_or_value(node, "item")
    msg = js_get_classvar_hook_or_value(node, "msg")

    expr = f"if ({item} == {prv}) throw new Error({msg});"
    if is_last_var_no_ret(node):
        return expr
    return expr + f"let {nxt} = {prv};"


@CONVERTER(ExprIsContains.kind)
def pre_is_contains(node: ExprIsContains) -> str:
    prv, nxt = prev_next_var(node)
    item = js_get_classvar_hook_or_value(node, "item")
    msg = js_get_classvar_hook_or_value(node, "msg")

    expr = f"if (!({item} in {prv})) throw new Error({msg});"
    if is_last_var_no_ret(node):
        return expr
    return expr + f"let {nxt} = {prv};"


@CONVERTER(ExprStringIsRegex.kind)
def pre_is_regex(node: ExprStringIsRegex) -> str:
    prv, nxt = prev_next_var(node)
    pattern, ignore_case, msg = node.unpack_args()
    msg = js_get_classvar_hook_or_value(node, "msg")

    if node.classvar_hooks.get("pattern"):
        pattern = js_get_classvar_hook_or_value(node, "pattern")
    else:
        pattern = to_js_regexp(pattern, ignore_case)

    expr = f"if ({prv}.match({pattern}) === null) throw new Error({msg});"
    if is_last_var_no_ret(node):
        return expr
    return expr + f"let {nxt} = {prv};"


@CONVERTER(ExprListStringAnyRegex.kind)
def pre_list_str_any_is_regex(node: ExprListStringAnyRegex) -> str:
    # a.some(i => (new RegExp("foo")).test(i))
    prv, nxt = prev_next_var(node)
    pattern, ignore_case, msg = node.unpack_args()
    msg = js_get_classvar_hook_or_value(node, "msg")
    if node.classvar_hooks.get("pattern"):
        pattern = js_get_classvar_hook_or_value(node, "pattern")
    else:
        pattern = to_js_regexp(pattern, ignore_case)

    expr = f"if (!{prv}.some(i => (new RegExp({pattern})).test(i))) throw new Error({msg});"
    if is_last_var_no_ret(node):
        return expr
    return expr + f"let {nxt} = {prv};"


@CONVERTER(ExprListStringAllRegex.kind)
def pre_list_str_all_is_regex(node: ExprListStringAllRegex) -> str:
    prv, nxt = prev_next_var(node)
    # a.every(i => (new RegExp("foo")).test)
    pattern, ignore_case, msg = node.unpack_args()

    msg = js_get_classvar_hook_or_value(node, "msg")
    if node.classvar_hooks.get("pattern"):
        pattern = js_get_classvar_hook_or_value(node, "pattern")
    else:
        pattern = to_js_regexp(pattern, ignore_case)

    expr = f"if (!{prv}.every(i => (new RegExp({pattern})).test(i))) throw new Error({msg});"
    if is_last_var_no_ret(node):
        return expr
    return expr + f"let {nxt} = {prv};"


@CONVERTER(ExprIsCss.kind)
def pre_is_css(node: ExprIsCss) -> str:
    prv, nxt = prev_next_var(node)
    query = js_get_classvar_hook_or_value(node, "query")
    msg = js_get_classvar_hook_or_value(node, "msg")

    expr = f"if ({prv}.querySelector({query}) === null) throw new Error({msg});"
    if is_last_var_no_ret(node):
        return expr
    # HACK: avoid recalc variables
    return expr + f"let {nxt} = {prv};"


@CONVERTER(ExprIsXpath.kind)
def pre_is_xpath(node: ExprIsXpath) -> str:
    prv, nxt = prev_next_var(node)
    query = js_get_classvar_hook_or_value(node, "query")
    msg = js_get_classvar_hook_or_value(node, "msg")

    expr = J2_IS_XPATH.render(prv=prv, nxt=nxt, msg=msg, query=query)
    if is_last_var_no_ret(node):
        return expr
    return expr + f"let {nxt} = {prv};"


@CONVERTER(ExprToInt.kind)
def pre_to_int(node: ExprToInt) -> str:
    prv, nxt = prev_next_var(node)
    return f"let {nxt} = parseInt({prv}, 10);"


@CONVERTER(ExprToListInt.kind)
def pre_to_list_int(node: ExprToListInt) -> str:
    prv, nxt = prev_next_var(node)
    return f"let {nxt} = {prv}.map(i => parseInt(i, 10));"


@CONVERTER(ExprToFloat.kind)
def pre_to_float(node: ExprToFloat) -> str:
    prv, nxt = prev_next_var(node)
    return f"let {nxt} = parseFloat({prv}, 64);"


@CONVERTER(ExprToListFloat.kind)
def pre_to_list_float(node: ExprToListFloat) -> str:
    prv, nxt = prev_next_var(node)
    return f"let {nxt} = {prv}.map(i => parseFloat(i, 64));"


@CONVERTER(ExprToListLength.kind)
def pre_to_len(node: ExprToListLength) -> str:
    prv, nxt = prev_next_var(node)
    return f"let {nxt} = {prv}.length;"


@CONVERTER(ExprToBool.kind)
def pre_to_bool(node: ExprToBool) -> str:
    prv, nxt = prev_next_var(node)
    return f"let {nxt} = {prv} || {prv} === 0 ? true : false;"


@CONVERTER(ExprJsonify.kind)
def pre_jsonify(node: ExprJsonify) -> str:
    prv, nxt = prev_next_var(node)
    _, _, query = node.unpack_args()
    expr = "".join(f"[{i}]" for i in jsonify_query_parse(query))

    return f"let {nxt} = JSON.parse({prv}){expr};"


@CONVERTER(ExprCss.kind)
def pre_css(node: ExprCss) -> str:
    prv, nxt = prev_next_var(node)
    query = js_get_classvar_hook_or_value(node, "query")
    return f"let {nxt} = {prv}.querySelector({query});"


@CONVERTER(ExprCssAll.kind)
def pre_css_all(node: ExprCssAll) -> str:
    prv, nxt = prev_next_var(node)
    query = js_get_classvar_hook_or_value(node, "query")
    return f"let {nxt} = Array.from({prv}.querySelectorAll({query}));"


@CONVERTER(ExprXpath.kind)
def pre_xpath(node: ExprXpath) -> str:
    prv, nxt = prev_next_var(node)
    query = js_get_classvar_hook_or_value(node, "query")
    return J2_PRE_XPATH.render(prv=prv, nxt=nxt, query=query)


@CONVERTER(ExprXpathAll.kind)
def pre_xpath_all(node: ExprXpathAll) -> str:
    prv, nxt = prev_next_var(node)
    query = js_get_classvar_hook_or_value(node, "query")
    snapshot_var = f"s{nxt}"
    return J2_PRE_XPATH_ALL.render(
        prv=prv, nxt=nxt, query=query, snapshot_var=snapshot_var
    )


@CONVERTER(ExprGetHtmlAttr.kind)
def pre_html_attr(node: ExprGetHtmlAttr) -> str:
    prv, nxt = prev_next_var(node)
    keys = node.kwargs["key"]
    if len(keys) == 1:
        key = keys[0]
        return f"let {nxt} = {prv}.getAttribute({key!r});"
    js_keys = py_sequence_to_js_array(keys)
    return f"let {nxt} = {js_keys}.map(k => {prv}?.getAttribute(k)).filter(Boolean); "


@CONVERTER(ExprGetHtmlAttrAll.kind)
def pre_html_attr_all(node: ExprGetHtmlAttrAll) -> str:
    prv, nxt = prev_next_var(node)
    keys = node.kwargs["key"]
    if len(keys) == 1:
        key = keys[0]
        return f"let {nxt} = {prv}.map(e => e.getAttribute({key!r})); "
    js_keys = py_sequence_to_js_array(keys)
    return f"let {nxt} = Array.from({prv}).flatMap(e => {js_keys}.map(k => e.getAttribute(k)).filter(Boolean)); "


@CONVERTER(ExprGetHtmlText.kind)
def pre_html_text(node: ExprGetHtmlText) -> str:
    prv, nxt = prev_next_var(node)
    return (
        f"let {nxt} = typeof {prv}.textContent ==="
        + f'"undefined" ? {prv}.documentElement.textContent : {prv}.textContent;'
    )


@CONVERTER(ExprGetHtmlTextAll.kind)
def pre_html_text_all(node: ExprGetHtmlTextAll) -> str:
    prv, nxt = prev_next_var(node)
    # naive apologize, its element objects, not document
    return f"let {nxt} = {prv}.map(e => e.textContent);"


@CONVERTER(ExprGetHtmlRaw.kind)
def pre_html_raw(node: ExprGetHtmlRaw) -> str:
    prv, nxt = prev_next_var(node)
    return (
        f'let {nxt} = typeof {prv}.outerHTML === "undefined" '
        f"? {prv}.documentElement.outerHTML : {prv}.outerHTML;"
    )


@CONVERTER(ExprGetHtmlRawAll.kind)
def pre_html_raw_all(node: ExprGetHtmlRawAll) -> str:
    prv, nxt = prev_next_var(node)
    return f"let {nxt} = {prv}.map(e => e.outerHTML);"


@CONVERTER(ExprStringRmPrefix.kind)
def pre_str_rm_prefix(node: ExprStringRmPrefix) -> str:
    prv, nxt = prev_next_var(node)
    substr = js_get_classvar_hook_or_value(node, "substr")
    #  sscRmPrefix = (v, p)
    return f"let {nxt} = sscRmPrefix({prv}, {substr});"


@CONVERTER(ExprListStringRmPrefix.kind)
def pre_list_str_rm_prefix(node: ExprListStringRmPrefix) -> str:
    prv, nxt = prev_next_var(node)
    substr = js_get_classvar_hook_or_value(node, "substr")
    #  sscRmPrefix = (v, p)
    return f"let {nxt} = {prv}.map((e) => sscRmPrefix(e, {substr}));"


@CONVERTER(ExprStringRmSuffix.kind)
def pre_str_rm_suffix(node: ExprStringRmSuffix) -> str:
    prv, nxt = prev_next_var(node)
    substr = js_get_classvar_hook_or_value(node, "substr")
    # sscRmSuffix = (v, s)
    return f"let {nxt} = sscRmSuffix({prv}, {substr});"


@CONVERTER(ExprListStringRmSuffix.kind)
def pre_list_str_rm_suffix(node: ExprListStringRmSuffix) -> str:
    prv, nxt = prev_next_var(node)
    substr = js_get_classvar_hook_or_value(node, "substr")
    # sscRmSuffix = (v, s)
    return f"let {nxt} = {prv}.map((e) => sscRmSuffix(e, {substr}));"


@CONVERTER(ExprStringRmPrefixAndSuffix.kind)
def pre_str_rm_prefix_and_suffix(node: ExprStringRmPrefixAndSuffix) -> str:
    prv, nxt = prev_next_var(node)
    substr = js_get_classvar_hook_or_value(node, "substr")
    # sscRmPrefixSuffix = (v, p, s)
    return f"let {nxt} = sscRmPrefixSuffix({prv}, {substr}, {substr});"


@CONVERTER(ExprListStringRmPrefixAndSuffix.kind)
def pre_list_str_rm_prefix_and_suffix(
    node: ExprListStringRmPrefixAndSuffix,
) -> str:
    prv, nxt = prev_next_var(node)
    substr = js_get_classvar_hook_or_value(node, "substr")
    # sscRmPrefixSuffix = (v, p, s)
    return f"let {nxt} = {prv}.map((e) => sscRmPrefixSuffix(e,{substr}, {substr}));"


@CONVERTER(ExprHasAttr.kind)
def pre_has_attr(node: ExprHasAttr) -> str:
    prv, nxt = prev_next_var(node)
    key = js_get_classvar_hook_or_value(node, "key")
    msg = js_get_classvar_hook_or_value(node, "msg")

    expr = f"if (!{prv}?.hasAttribute({key})) throw new Error({msg});"
    if is_last_var_no_ret(node):
        return expr
    return expr + f"let {nxt} = {prv};"


@CONVERTER(ExprListHasAttr.kind)
def pre_list_has_attr(node: ExprListHasAttr) -> str:
    prv, nxt = prev_next_var(node)
    key = js_get_classvar_hook_or_value(node, "key")
    msg = js_get_classvar_hook_or_value(node, "msg")

    expr = f"if (!{prv}.every(e => e?.hasAttribute({key}))) throw new Error({msg});"
    if is_last_var_no_ret(node):
        return expr
    return expr + f"let {nxt} = {prv};"


@CONVERTER(ExprFilter.kind, post_callback=lambda _: ");")
def pre_expr_filter(node: ExprFilter) -> str:
    prv, nxt = prev_next_var(node)
    return f"let {nxt} = {prv}.filter(i => "


@CONVERTER(FilterOr.kind, post_callback=lambda _: ")")
def pre_filter_or(_node: FilterOr) -> str:
    return " || ("


@CONVERTER(FilterAnd.kind, post_callback=lambda _: ")")
def pre_filter_and(_node: FilterAnd) -> str:
    return " && ("


@CONVERTER(FilterNot.kind, post_callback=lambda _: ")")
def pre_filter_not(_node: FilterNot) -> str:  # type: ignore
    return "!("


@CONVERTER(FilterStrIn.kind)
def pre_filter_in(node: FilterStrIn) -> str:
    values, *_ = node.unpack_args()
    if len(values) == 1:
        expr = f"i.includes({values[0]!r})"
    else:
        # to js array
        val_arr = str(values)
        val_arr = "[" + val_arr[1:-1] + "]"
        expr = f"{val_arr}.some(e => i.includes(e))"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" && {expr}"
    return expr


@CONVERTER(FilterStrStarts.kind)
def pre_filter_starts_with(node: FilterStrStarts) -> str:
    values, *_ = node.unpack_args()
    if len(values) == 1:
        expr = f"i.startsWith({values[0]!r})"
    else:
        # to js array
        val_arr = str(values)
        val_arr = "[" + val_arr[1:-1] + "]"
        expr = f"{val_arr}.some(e => i.startsWith(e))"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" && {expr}"
    return expr


@CONVERTER(FilterStrEnds.kind)
def pre_filter_ends_with(node: FilterStrEnds) -> str:
    values, *_ = node.unpack_args()
    if len(values) == 1:
        expr = f"i.endsWith({values[0]!r})"
    else:
        # to js array
        val_arr = str(values)
        val_arr = "[" + val_arr[1:-1] + "]"
        expr = f"{val_arr}.some(e => i.endsWith(e))"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" && {expr}"
    return expr


@CONVERTER(FilterStrRe.kind)
def pre_filter_re(node: FilterStrRe) -> str:
    pattern, ignore_case, *_ = node.unpack_args()
    pattern = to_js_regexp(pattern, ignore_case, is_global=False)

    expr = f"(new RegExp({pattern})).test(i)"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" && {expr}"
    return expr


@CONVERTER(FilterEqual.kind)
def pre_filter_eq(node: FilterEqual) -> str:
    values, *_ = node.unpack_args()
    if len(values) == 1:
        expr = f"i === {values[0]!r}"
    else:
        val_arr = str(values)
        val_arr = "[" + val_arr[1:-1] + "]"
        expr = f"{val_arr}.some(e => i === e)"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" && {expr}"
    return expr


@CONVERTER(FilterNotEqual.kind)
def pre_filter_ne(node: FilterNotEqual) -> str:
    values, *_ = node.unpack_args()
    if len(values) == 1:
        expr = f"i !== {values[0]!r}"
    else:
        val_arr = str(values)
        val_arr = "[" + val_arr[1:-1] + "]"
        expr = f"{val_arr}.every(e => i !== e)"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" && {expr}"
    return expr


@CONVERTER(FilterStrLenEq.kind)
def pre_filter_str_len_eq(node: FilterStrLenEq) -> str:
    length, *_ = node.unpack_args()
    expr = f"i.length == {length}"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" && {expr}"
    return expr


@CONVERTER(FilterStrLenNe.kind)
def pre_filter_str_len_ne(node: FilterStrLenNe) -> str:
    length, *_ = node.unpack_args()
    expr = f"i.length != {length}"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" && {expr}"
    return expr


@CONVERTER(FilterStrLenLt.kind)
def pre_filter_str_len_lt(node: FilterStrLenLt) -> str:
    length, *_ = node.unpack_args()
    expr = f"i.length < {length}"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" && {expr}"
    return expr


@CONVERTER(FilterStrLenLe.kind)
def pre_filter_str_len_le(node: FilterStrLenLe) -> str:
    length, *_ = node.unpack_args()
    expr = f"i.length <= {length}"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" && {expr}"
    return expr


@CONVERTER(FilterStrLenGt.kind)
def pre_filter_str_len_gt(node: FilterStrLenGt) -> str:
    length, *_ = node.unpack_args()
    expr = f"i.length > {length}"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" && {expr}"
    return expr


@CONVERTER(FilterStrLenGe.kind)
def pre_filter_str_len_ge(node: FilterStrLenGe) -> str:
    length, *_ = node.unpack_args()
    expr = f"i.length >= {length}"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" && {expr}"
    return expr


@CONVERTER(ExprListUnique.kind)
def pre_list_unique(node: ExprListUnique) -> str:
    prv, nxt = prev_next_var(node)
    # elements order guaranteed, ignore node's argument `keep_oreder`
    # https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Set#description
    return f"let {nxt} = [...new Set({prv})]; "


@CONVERTER(ExprStringMapReplace.kind)
def pre_str_map_repl(node: ExprStringMapReplace) -> str:
    old_arr, new_arr = node.unpack_args()
    # py list<str> literal syntax equal js Array<string> literal
    old_arr = list(old_arr)  # type: ignore
    new_arr = list(new_arr)  # type: ignore
    prv, nxt = prev_next_var(node)
    return f"let {nxt} = {old_arr}.reduce((s, v, i) => s.replaceAll(v, {new_arr}[i] ?? ''), {prv});"


@CONVERTER(ExprListStringMapReplace.kind)
def pre_list_str_map_repl(node: ExprListStringMapReplace) -> str:
    old_arr, new_arr = node.unpack_args()
    # py list<str> literal syntax equal js Array<string> literal
    old_arr = list(old_arr)  # type: ignore
    new_arr = list(new_arr)  # type: ignore
    prv, nxt = prev_next_var(node)
    return f"let {nxt} = {prv}.map(s => {old_arr}.reduce((s, v, i) => s.replaceAll(v, {new_arr}[i] ?? ''), s));"


@CONVERTER(ExprStringUnescape.kind)
def pre_str_unescape(node: ExprStringUnescape) -> str:
    prv, nxt = prev_next_var(node)
    # function sscUnescape(v)
    return f"let {nxt} = sscUnescape{prv});"


@CONVERTER(ExprListStringUnescape.kind)
def pre_list_str_unescape(node: ExprListStringUnescape) -> str:
    prv, nxt = prev_next_var(node)
    # function sscUnescape(v)
    return f"let {nxt} = {prv}.map(s => sscUnescape(s));"


@CONVERTER(ExprMapAttrs.kind)
def pre_map_attrs(node: ExprMapAttrs) -> str:
    prv, nxt = prev_next_var(node)
    return f"let {nxt} = Array.from({prv}.attributes).map(a => a.value); "


@CONVERTER(ExprMapAttrsAll.kind)
def pre_map_attrs_all(node: ExprMapAttrsAll) -> str:
    prv, nxt = prev_next_var(node)
    return f"let {nxt} = [].concat(...{prv}.map(e => Array.from(e.attributes).map(a => a.value))); "


@CONVERTER(ExprCssElementRemove.kind)
def pre_css_remove(node: ExprCssElementRemove) -> str:
    prv, nxt = prev_next_var(node)
    query = js_get_classvar_hook_or_value(node, "query")
    return f"document.querySelectorAll({query}).forEach(el => el.remove()); let {nxt} = {prv};"


@CONVERTER(ExprXpathElementRemove.kind)
def pre_xpath_remove(node: ExprXpathElementRemove) -> str:
    prv, nxt = prev_next_var(node)
    query = js_get_classvar_hook_or_value(node, "query")
    return (
        f"for (let {prv}r = document.evaluate({query}, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null), {prv}i = {prv}r.snapshotLength; {prv}i--; ) {prv}r.snapshotItem({prv}i).remove(); "
        + f"let {nxt} = {prv}; "
    )


@CONVERTER(ExprJsonifyDynamic.kind)
def pre_jsonify_dynamic(node: ExprJsonifyDynamic) -> str:
    prv, nxt = prev_next_var(node)
    query, *_ = node.unpack_args()

    expr = "".join(f"[{i}]" for i in jsonify_query_parse(query))

    return f"let {nxt} = JSON.parse({prv}){expr};"
