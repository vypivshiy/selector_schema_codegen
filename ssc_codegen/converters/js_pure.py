"""pure ES6 js standard implementation. Works in modern browsers and developer console

Codegen notations:

- exclude typing and struct serializations
- vars have prefix `v{index}`, start argument names as `v`
- methods auto convert to camelCase
- code formatter exclude

SPECIAL METHODS NOTATIONS:

- field_name : _parse_{field_name} (add prefix `_parse_` for every struct method parse)
- __KEY__ -> `key`, `_parseKey`
- __VALUE__: `value`, `_parseValue`
- __ITEM__: `item`, `_parseItem`
- __PRE_VALIDATE__: `_preValidate`,
- __SPLIT_DOC__: `_splitDoc`,
- __START_PARSE__: `parse`,
"""

from typing import cast

from typing_extensions import assert_never

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
)
from ssc_codegen.ast_.nodes_selectors import ExprMapAttrs, ExprMapAttrsAll
from ssc_codegen.ast_.nodes_string import (
    ExprListStringUnescape,
    ExprStringUnescape,
)
from ssc_codegen.converters.base import BaseCodeConverter
from ssc_codegen.converters.helpers import (
    prev_next_var,
    is_last_var_no_ret,
    have_pre_validate_call,
    is_first_node_cond,
    is_prev_node_atomic_cond,
)
from ssc_codegen.converters.templates.js_pure import (
    J2_STRUCT_INIT,
    J2_START_PARSE_DICT,
    J2_START_PARSE_FLAT_LIST,
    J2_START_PARSE_ITEM,
    J2_START_PARSE_LIST_PARSE,
    J2_PRE_LIST_STR_TRIM,
    J2_PRE_STR_LEFT_TRIM,
    J2_PRE_LIST_STR_LEFT_TRIM,
    J2_PRE_STR_RIGHT_TRIM,
    J2_PRE_LIST_STR_RIGHT_TRIM,
    J2_PRE_XPATH,
    J2_PRE_XPATH_ALL,
    J2_PRE_STR_TRIM,
    J2_IS_XPATH,
    J2_START_PARSE_ACC_LIST,
)
from ssc_codegen.str_utils import (
    wrap_backtick,
    to_upper_camel_case,
)
from ssc_codegen.tokens import StructType

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


# TODO: move to string_utils
def to_js_regexp(
    pattern: str, ignore_case: bool = False, is_global: bool = True
) -> str:
    """helper function for convert string pattern to js"""
    # fix backslashes translate
    pattern = pattern.replace("/", r"\/").replace(r"\\/", r"\/")

    pattern = f"/{pattern}/"
    if is_global:
        pattern += "g"
    if ignore_case:
        pattern += "i"
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


@CONVERTER(Docstring.kind)
def pre_docstring(node: Docstring) -> str:
    value = node.kwargs["value"]
    docstr = make_js_docstring(value)
    return docstr


@CONVERTER(StructPartDocMethod.kind)
def pre_part_doc(_node: StructPartDocMethod) -> str:
    return "_splitDoc(v) " + BRACKET_START


@CONVERTER.post(StructPartDocMethod.kind)
def post_part_doc(_node: StructPartDocMethod) -> str:
    return BRACKET_END


@CONVERTER(StructParser.kind)
def pre_struct_parser(node: StructParser) -> str:
    name = node.kwargs["name"]
    docstr = make_js_docstring(node.kwargs["docstring"])
    return docstr + "\n" + f"class {name}" + BRACKET_START


@CONVERTER.post(StructParser.kind)
def post_struct_parser(_node: StructParser) -> str:
    return BRACKET_END


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


@CONVERTER.post(StructPreValidateMethod.kind)
def post_pre_validate(_node: StructPreValidateMethod) -> str:
    return BRACKET_END


@CONVERTER(StructFieldMethod.kind)
def pre_parse_field(node: StructFieldMethod) -> str:
    name = node.kwargs["name"]
    name = MAGIC_METHODS.get(name, name)
    fn_name = "_parse" + to_upper_camel_case(name)
    return f"{fn_name}(v)" + BRACKET_START


@CONVERTER.post(StructFieldMethod.kind)
def post_parse_field(_node: StructFieldMethod) -> str:
    return BRACKET_END


@CONVERTER(StartParseMethod.kind)
def pre_start_parse_method(_node: StartParseMethod) -> str:
    return "parse()" + BRACKET_START


@CONVERTER.post(StartParseMethod.kind)
def post_start_parse_method(_node: StartParseMethod) -> str:
    return BRACKET_END


@CONVERTER(StructInitMethod.kind)
def pre_struct_init(_node: StructInitMethod) -> str:
    return J2_STRUCT_INIT


@CONVERTER(StartParseMethod.kind)
def pre_start_parse(node: StartParseMethod) -> str:
    node.parent = cast(StructParser, node.parent)
    code = "parse() " + BRACKET_START
    if have_pre_validate_call(node):
        code += "this._preValidate(this._doc);"

    exprs = [
        {
            "name": expr.kwargs["name"],
            "upper_name": to_upper_camel_case(expr.kwargs["name"]),
        }
        for expr in node.body
        if not expr.kwargs["name"].startswith("__")
    ]

    match node.parent.struct_type:
        case StructType.ITEM:
            code += J2_START_PARSE_ITEM.render(exprs=exprs)
        case StructType.LIST:
            code += J2_START_PARSE_LIST_PARSE.render(exprs=exprs)
        case StructType.DICT:
            code += J2_START_PARSE_DICT
        case StructType.FLAT_LIST:
            code += J2_START_PARSE_FLAT_LIST
        case StructType.ACC_LIST:
            code += J2_START_PARSE_ACC_LIST.render(exprs=exprs)
        case _:
            assert_never(node.parent.struct_type)  # type: ignore
    return code


@CONVERTER(ExprDefaultValueStart.kind)
def pre_default_start(node: ExprDefaultValueStart) -> str:
    prv, nxt = prev_next_var(node)
    return f"let {nxt} = {prv};" + "try " + BRACKET_START


@CONVERTER(ExprDefaultValueEnd.kind)
def pre_default_end(node: ExprDefaultValueEnd) -> str:
    value = node.kwargs["value"]
    if value is None:
        value = "null"
    elif isinstance(value, str):
        value = repr(value)
    elif isinstance(value, bool):
        value = "true" if value else "false"
    elif isinstance(value, list):
        value = "[]"
    return f"}}catch(Error) {{ return {value}; }}"


@CONVERTER(ExprStringFormat.kind)
def pre_str_fmt(node: ExprStringFormat) -> str:
    prv, nxt = prev_next_var(node)
    template = wrap_backtick(node.fmt.replace("{{}}", "${" + prv + "}"))
    return f"let {nxt} = {template};"


@CONVERTER(ExprListStringFormat.kind)
def pre_list_str_fmt(node: ExprListStringFormat) -> str:
    prv, nxt = prev_next_var(node)
    template = wrap_backtick(node.fmt.replace("{{}}", "${e}"))
    return f"let {nxt} = {prv}.map(e => {template});"


@CONVERTER(ExprStringTrim.kind)
def pre_str_trim(node: ExprStringTrim) -> str:
    prv, nxt = prev_next_var(node)
    substr = node.kwargs["substr"]
    return J2_PRE_STR_TRIM.render(nxt=nxt, prv=prv, substr=repr(substr))


@CONVERTER(ExprListStringTrim.kind)
def pre_list_str_trim(node: ExprListStringTrim) -> str:
    prv, nxt = prev_next_var(node)
    substr = node.kwargs["substr"]
    return J2_PRE_LIST_STR_TRIM.render(prv=prv, nxt=nxt, substr=repr(substr))


@CONVERTER(ExprStringLeftTrim.kind)
def pre_str_left_trim(node: ExprStringLeftTrim) -> str:
    prv, nxt = prev_next_var(node)
    substr = node.kwargs["substr"]
    return J2_PRE_STR_LEFT_TRIM.render(prv=prv, nxt=nxt, substr=repr(substr))


@CONVERTER(ExprListStringLeftTrim.kind)
def pre_list_str_left_trim(node: ExprListStringLeftTrim) -> str:
    prv, nxt = prev_next_var(node)
    substr = node.kwargs["substr"]
    return J2_PRE_LIST_STR_LEFT_TRIM.render(
        prv=prv, nxt=nxt, substr=repr(substr)
    )


@CONVERTER(ExprStringRightTrim.kind)
def pre_str_right_trim(node: ExprStringRightTrim) -> str:
    prv, nxt = prev_next_var(node)
    substr = node.kwargs["substr"]
    return J2_PRE_STR_RIGHT_TRIM.render(prv=prv, nxt=nxt, substr=repr(substr))


@CONVERTER(ExprListStringRightTrim.kind)
def pre_list_str_right_trim(node: ExprListStringRightTrim) -> str:
    prv, nxt = prev_next_var(node)
    substr = node.kwargs["substr"]
    return J2_PRE_LIST_STR_RIGHT_TRIM.render(
        prv=prv, nxt=nxt, substr=repr(substr)
    )


@CONVERTER(ExprStringSplit.kind)
def pre_str_split(node: ExprStringSplit) -> str:
    prv, nxt = prev_next_var(node)
    sep = node.kwargs["sep"]
    return f"let {nxt} = {prv}.split({sep!r});"


@CONVERTER(ExprStringReplace.kind)
def pre_str_replace(node: ExprStringReplace) -> str:
    prv, nxt = prev_next_var(node)
    old, new = node.unpack_args()
    return f"let {nxt} = {prv}.replaceAll({old!r}, {new!r});"


@CONVERTER(ExprListStringReplace.kind)
def pre_list_str_replace(node: ExprListStringReplace) -> str:
    prv, nxt = prev_next_var(node)
    old, new = node.unpack_args()
    return f"let {nxt} = {prv}.map(e => e.replaceAll({old!r}, {new!r}));"


@CONVERTER(ExprStringRegex.kind)
def pre_str_regex(node: ExprStringRegex) -> str:
    prv, nxt = prev_next_var(node)
    pattern, group, ignore_case = node.unpack_args()
    pattern = to_js_regexp(pattern, ignore_case, is_global=False)
    return f"let {nxt} = {prv}.match({pattern})[{group}];"


@CONVERTER(ExprStringRegexAll.kind)
def pre_str_regex_all(node: ExprStringRegexAll) -> str:
    prv, nxt = prev_next_var(node)
    pattern, ignore_case = node.unpack_args()
    pattern = to_js_regexp(pattern, ignore_case)
    return f"let {nxt} = Array.from({prv}.match({pattern}));"


@CONVERTER(ExprStringRegexSub.kind)
def pre_str_regex_sub(node: ExprStringRegexSub) -> str:
    prv, nxt = prev_next_var(node)
    pattern, repl = node.unpack_args()
    pattern = to_js_regexp(pattern)

    return f"let {nxt} = {prv}.replace({pattern}, {repl!r});"


@CONVERTER(ExprListStringRegexSub.kind)
def pre_list_str_regex_sub(node: ExprListStringRegexSub) -> str:
    prv, nxt = prev_next_var(node)
    pattern, repl = node.unpack_args()
    pattern = to_js_regexp(pattern)

    return f"let {nxt} = {prv}.map(e => e.replace({pattern}, {repl!r}));"


@CONVERTER(ExprIndex.kind)
def pre_index(node: ExprIndex) -> str:
    prv, nxt = prev_next_var(node)
    index, *_ = node.unpack_args()
    return f"let {nxt} = {prv}[{index}];"


@CONVERTER(ExprListStringJoin.kind)
def pre_list_str_join(node: ExprListStringJoin) -> str:
    prv, nxt = prev_next_var(node)
    sep = node.kwargs["sep"]
    return f"let {nxt} = {prv}.join({sep!r});"


@CONVERTER(ExprIsEqual.kind)
def pre_is_equal(node: ExprIsEqual) -> str:
    prv, nxt = prev_next_var(node)
    item, msg = node.unpack_args()
    if isinstance(item, str):
        item = repr(item)
    elif isinstance(item, bool):
        item = "true" if item else "false"
    expr = f"if ({item} != {prv}) throw new Error({msg!r});"
    if is_last_var_no_ret(node):
        return expr
    return expr + f"let {nxt} = {prv};"


@CONVERTER(ExprIsNotEqual.kind)
def pre_is_not_equal(node: ExprIsNotEqual) -> str:
    prv, nxt = prev_next_var(node)
    item, msg = node.unpack_args()
    if isinstance(item, str):
        item = repr(item)
    elif isinstance(item, bool):
        item = "true" if item else "false"
    expr = f"if ({item} == {prv}) throw new Error({msg!r});"
    if is_last_var_no_ret(node):
        return expr
    # HACK: avoid recalc variables
    return expr + f"let {nxt} = {prv};"


@CONVERTER(ExprIsContains.kind)
def pre_is_contains(node: ExprIsContains) -> str:
    prv, nxt = prev_next_var(node)
    item, msg = node.unpack_args()
    if isinstance(item, str):
        item = repr(item)
    elif isinstance(item, bool):
        item = "true" if item else "false"
    expr = f"if (!({item} in {prv})) throw new Error({msg!r});"
    if is_last_var_no_ret(node):
        return expr
    # HACK: avoid recalc variables
    return expr + f"let {nxt} = {prv};"


@CONVERTER(ExprStringIsRegex.kind)
def pre_is_regex(node: ExprStringIsRegex) -> str:
    prv, nxt = prev_next_var(node)
    pattern, ignore_case, msg = node.unpack_args()
    pattern = to_js_regexp(pattern, ignore_case)

    expr = f"if ({prv}.match({pattern}) === null) throw new Error({msg!r});"
    if is_last_var_no_ret(node):
        return expr
    # HACK: avoid recalc variables
    return expr + f"let {nxt} = {prv};"


@CONVERTER(ExprListStringAnyRegex.kind)
def pre_list_str_any_is_regex(node: ExprListStringAnyRegex) -> str:
    # a.some(i => (new RegExp("foo")).test(i))
    prv, nxt = prev_next_var(node)
    pattern, ignore_case, msg = node.unpack_args()
    pattern = pattern.replace("/", "\\/")
    pattern = f"/{pattern}/g"
    if ignore_case:
        pattern += "i"

    expr = f"if (!{prv}.some(i => (new RegExp({pattern})).test(i))) throw new Error({msg!r});"
    if is_last_var_no_ret(node):
        return expr
    # HACK: avoid recalc variables
    return expr + f"let {nxt} = {prv};"


@CONVERTER(ExprListStringAllRegex.kind)
def pre_list_str_all_is_regex(node: ExprListStringAllRegex) -> str:
    prv, nxt = prev_next_var(node)
    # a.every(i => (new RegExp("foo")).test)
    pattern, ignore_case, msg = node.unpack_args()
    pattern = pattern.replace("/", "\\/")
    pattern = f"/{pattern}/g"
    if ignore_case:
        pattern += "i"

    expr = f"if (!{prv}.every(i => (new RegExp({pattern})).test(i))) throw new Error({msg!r});"
    if is_last_var_no_ret(node):
        return expr
    # HACK: avoid recalc variables
    return expr + f"let {nxt} = {prv};"


@CONVERTER(ExprIsCss.kind)
def pre_is_css(node: ExprIsCss) -> str:
    prv, nxt = prev_next_var(node)
    query, msg = node.unpack_args()
    expr = f"if ({prv}.querySelector({query!r}) === null) throw new Error({msg!r});"
    if is_last_var_no_ret(node):
        return expr
    # HACK: avoid recalc variables
    return expr + f"let {nxt} = {prv};"


@CONVERTER(ExprIsXpath.kind)
def pre_is_xpath(node: ExprIsXpath) -> str:
    prv, nxt = prev_next_var(node)
    query, msg = node.unpack_args()
    msg = repr(msg)
    expr = J2_IS_XPATH.render(prv=prv, nxt=nxt, msg=msg)
    if is_last_var_no_ret(node):
        return expr
    # HACK: avoid recalc variables
    # TODO: move to j2 template
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
    return f"let {nxt} = JSON.parse({prv});"


@CONVERTER(ExprCss.kind)
def pre_css(node: ExprCss) -> str:
    prv, nxt = prev_next_var(node)
    query = node.kwargs["query"]
    return f"let {nxt} = {prv}.querySelector({query!r});"


@CONVERTER(ExprCssAll.kind)
def pre_css_all(node: ExprCssAll) -> str:
    prv, nxt = prev_next_var(node)
    query = node.kwargs["query"]
    return f"let {nxt} = Array.from({prv}.querySelectorAll({query!r}));"


@CONVERTER(ExprXpath.kind)
def pre_xpath(node: ExprXpath) -> str:
    prv, nxt = prev_next_var(node)
    query = node.kwargs["query"]
    return J2_PRE_XPATH.render(prv=prv, nxt=nxt, query=query)


@CONVERTER(ExprXpathAll.kind)
def pre_xpath_all(node: ExprXpathAll) -> str:
    prv, nxt = prev_next_var(node)
    query = node.kwargs["query"]
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
    substr = repr(node.kwargs["substr"])
    return f"let {nxt} = {prv}.startsWith({substr}) ? {prv}.slice({substr}.length) : {prv};"


@CONVERTER(ExprListStringRmPrefix.kind)
def pre_list_str_rm_prefix(node: ExprListStringRmPrefix) -> str:
    prv, nxt = prev_next_var(node)
    substr = repr(node.kwargs["substr"])
    return f"let {nxt} = {prv}.map((e) => e.startsWith({substr}) ? e.slice({substr}.length) : e);"


@CONVERTER(ExprStringRmSuffix.kind)
def pre_str_rm_suffix(node: ExprStringRmSuffix) -> str:
    prv, nxt = prev_next_var(node)
    substr = repr(node.kwargs["substr"])
    return f"let {nxt} = {prv}.endsWith({substr}) ? {prv}.slice(0, -{substr}.length) : {prv};"


@CONVERTER(ExprListStringRmSuffix.kind)
def pre_list_str_rm_suffix(node: ExprListStringRmSuffix) -> str:
    prv, nxt = prev_next_var(node)
    substr = repr(node.kwargs["substr"])
    return f"let {nxt} = {prv}.map((e) => e.endsWith({substr}) ? e.slice(0, -{substr}.length) : e);"


@CONVERTER(ExprStringRmPrefixAndSuffix.kind)
def pre_str_rm_prefix_and_suffix(node: ExprStringRmPrefixAndSuffix) -> str:
    prv, nxt = prev_next_var(node)
    substr = repr(node.kwargs["substr"])
    return (
        f"let {nxt} = {prv}.startsWith({substr}) ? {prv}.slice({substr}.length) : {prv}; "
        + f"{nxt} = {nxt}.endsWith({substr}) ? {prv}.slice(0, -{substr}.length) : {prv};"
    )


@CONVERTER(ExprListStringRmPrefixAndSuffix.kind)
def pre_list_str_rm_prefix_and_suffix(
    node: ExprListStringRmPrefixAndSuffix,
) -> str:
    prv, nxt = prev_next_var(node)
    substr = repr(node.kwargs["substr"])
    return (
        f"let {nxt} = {prv}.map((e) => e.startsWith({substr}) ? e.slice({substr}.length) : e);"
        + f"{nxt} = {nxt}.map((e) => e.endsWith({substr}) ? e.slice(0, -{substr}.length) : e);"
    )


@CONVERTER(ExprHasAttr.kind)
def pre_has_attr(node: ExprHasAttr) -> str:
    prv, nxt = prev_next_var(node)
    key, msg = node.unpack_args()
    expr = f"if (!{prv}?.hasAttribute({key!r})) throw new Error({msg!r});"
    if is_last_var_no_ret(node):
        return expr
    return expr + f"let {nxt} = {prv};"


@CONVERTER(ExprListHasAttr.kind)
def pre_list_has_attr(node: ExprListHasAttr) -> str:
    prv, nxt = prev_next_var(node)
    key, msg = node.unpack_args()
    expr = f"if (!{prv}.every(e => e?.hasAttribute({key!r}))) throw new Error({msg!r});"
    if is_last_var_no_ret(node):
        return expr
    return expr + f"let {nxt} = {prv};"


@CONVERTER(ExprFilter.kind)
def pre_expr_filter(node: ExprFilter) -> str:
    prv, nxt = prev_next_var(node)
    return f"let {nxt} = {prv}.filter(i => "


@CONVERTER.post(ExprFilter.kind)
def post_expr_filter(_node: ExprFilter) -> str:
    return ");"


@CONVERTER(FilterOr.kind)
def pre_filter_or(_node: FilterOr) -> str:
    return " || ("


@CONVERTER.post(FilterOr.kind)
def post_filter_or(_node: FilterOr) -> str:
    return ")"


@CONVERTER(FilterAnd.kind)
def pre_filter_and(_node: FilterAnd) -> str:
    return " && ("


@CONVERTER.post(FilterAnd.kind)
def post_filter_and(_node: FilterAnd) -> str:
    return ")"


@CONVERTER(FilterNot.kind)
def pre_filter_not(_node: FilterNot) -> str:  # type: ignore
    return "!("


@CONVERTER.post(FilterNot.kind)
def post_filter_not(_node: FilterNot) -> str:
    return ")"


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
        expr = f"{val_arr}.every(e => i === e)"
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
    # save order guaranteed
    # https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Set#description
    return f"let {nxt} = [...new Set({prv})]; "


@CONVERTER(ExprStringMapReplace.kind)
def pre_str_map_repl(node: ExprStringMapReplace) -> str:
    old_arr, new_arr = node.unpack_args()
    old_arr = list(old_arr)  # type: ignore
    new_arr = list(new_arr)  # type: ignore
    prv, nxt = prev_next_var(node)
    # py list<str> literal syntax equal js Array<string> literal
    return f"let {nxt} = {old_arr}.reduce((s, v, i) => s.replaceAll(v, {new_arr}[i] ?? ''), {prv});"


@CONVERTER(ExprListStringMapReplace.kind)
def pre_list_str_map_repl(node: ExprListStringMapReplace) -> str:
    old_arr, new_arr = node.unpack_args()
    old_arr = list(old_arr)  # type: ignore
    new_arr = list(new_arr)  # type: ignore
    prv, nxt = prev_next_var(node)
    return f"let {nxt} = {prv}.map(s => {old_arr}.reduce((s, v, i) => s.replaceAll(v, {new_arr}[i] ?? ''), s));"


@CONVERTER(ExprStringUnescape.kind)
def pre_str_unescape(node: ExprStringUnescape) -> str:
    prv, nxt = prev_next_var(node)
    return (
        f"let {nxt} = {prv}"
        + ".replace(/&amp;/g, '&')"
        + ".replace(/&lt;/g, '<')"
        + ".replace(/&gt;/g, '>')"
        + ".replace(/&quot;/g, '\"')"
        + '.replace(/&#039;/g, "\'")'
        + ".replace(/&#x2F;/g, '/')"
        + ".replace(/&nbsp;/g, ' ')"
        + ".replace(/&#x([0-9a-fA-F]+);/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)))"
        + r".replace(/\\u([0-9a-fA-F]{4})/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)))"
        + r".replace(/\\x([0-9a-fA-F]{2})/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)))"
        + r".replace(/\\([bfnrt])/g, (_, ch) => ({b:'\\b',f:'\\f',n:'\\n',r:'\\r',t:'\\t'})[ch])"
        + ";"
    )


@CONVERTER(ExprListStringUnescape.kind)
def pre_list_str_unescape(node: ExprListStringUnescape) -> str:
    prv, nxt = prev_next_var(node)
    return (
        f"let {nxt} = {prv}.map(s => s"
        + ".replace(/&amp;/g, '&')"
        + ".replace(/&lt;/g, '<')"
        + ".replace(/&gt;/g, '>')"
        + ".replace(/&quot;/g, '\"')"
        + '.replace(/&#039;/g, "\'")'
        + ".replace(/&#x2F;/g, '/')"
        + ".replace(/&nbsp;/g, ' ')"
        + ".replace(/&#x([0-9a-fA-F]+);/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)))"
        + r".replace(/\\u([0-9a-fA-F]{4})/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)))"
        + r".replace(/\\x([0-9a-fA-F]{2})/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)))"
        + r".replace(/\\([bfnrt])/g, (_, ch) => ({b:'\b',f:'\f',n:'\n',r:'\r',t:'\\t'})[ch])"
        + ");"
    )


@CONVERTER(ExprMapAttrs.kind)
def pre_map_attrs(node: ExprMapAttrs) -> str:
    prv, nxt = prev_next_var(node)
    return f"let {nxt} = Array.from({prv}.attributes).map(a => a.value); "


@CONVERTER(ExprMapAttrsAll.kind)
def pre_map_attrs_all(node: ExprMapAttrsAll) -> str:
    prv, nxt = prev_next_var(node)
    return f"let {nxt} = [].concat(...{prv}.map(e => Array.from(e.attributes).map(a => a.value))); "
