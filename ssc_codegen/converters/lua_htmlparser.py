"""htmlparser lua 5.2+ or luajit 2.0+ impl

Used as PoC:

- translation PCRE regex syntax to lua string pattern matcher
- translation CSS combinators and several pseudo selectors to equal functions

Convert to pure lua, if you dont use pcre-regex dependency

dependencies:

- html parser, css selectors https://github.com/msva/lua-htmlparser
- pcre-regex (OPTIONAL) https://github.com/rrthomas/lrexlib dependency (standard lua not support regex flags)
    - or try convert PCRE regex to equalent string pattern matching code
- json parser https://luarocks.org/modules/dhkolf/dkjson
- optional formatter dependency https://github.com/Koihik/LuaFormatter


for annotations, typehints used EmmyLua annotations syntax:
    - https://emmylua.github.io/annotation.html
    - https://github.com/LuaLS/lua-language-server/wiki/EmmyLua-Annotations/85b3e724f9e40e9d9bc450577bd68b35a9fcb464

"""

import logging
from typing import Any, cast


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
    ExprCssElementRemove,
    ExprMapAttrs,
    ExprMapAttrsAll,
    ExprXpathElementRemove,
    ExprListStringUnescape,
    ExprStringUnescape,
    ModuleImports,
)
from ssc_codegen.ast_.nodes_cast import ExprJsonifyDynamic
from ssc_codegen.ast_.nodes_core import (
    CodeEnd,
    ExprCallStructClassVar,
    ExprCallStructMethod,
    JsonStruct,
    JsonStructField,
    TypeDef,
    TypeDefField,
)
from ssc_codegen.ast_.nodes_filter import (
    ExprDocumentFilter,
    FilterDocAttrContains,
    FilterDocAttrEnds,
    FilterDocAttrEqual,
    FilterDocAttrRegex,
    FilterDocAttrStarts,
    FilterDocCss,
    FilterDocHasAttr,
    FilterDocHasRaw,
    FilterDocHasText,
    FilterDocIsRegexRaw,
    FilterDocIsRegexText,
    FilterDocXpath,
)
from ssc_codegen.converters.base import BaseCodeConverter
from ssc_codegen.converters.helpers import (
    have_pre_validate_call,
    is_first_node_cond,
    is_last_var_no_ret,
    is_prev_node_atomic_cond,
    jsonify_query_parse,
    lua_get_classvar_hook_or_value,
    prev_next_var,
)
from ssc_codegen.converters.templates.lua_base import (
    HELPER_FUNCTIONS,
    lua_struct_init,
)
from ssc_codegen.converters.templates.lua_css_compat import (
    css_query_to_lua_htmlparser_code,
)
from ssc_codegen.converters.templates.lua_re_compat import (
    py_regex_to_lua_pattern,
)
from ssc_codegen.str_utils import wrap_double_quotes
from ssc_codegen.tokens import JsonVariableType, StructType, VariableType


class LuaConverter(BaseCodeConverter):
    USE_PCRE = False
    """if True, convert to rexlib support flag else try pattern convert to build-in lua string pattern syntax"""


CONVERTER = LuaConverter(debug_comment_prefix="-- ")
CONVERTER.TEST_EXCLUDE_NODES.extend(
    # currently, this PoC translator not implemented document filter operaions
    [
        ExprDocumentFilter.kind,
        FilterDocCss.kind,
        FilterDocXpath.kind,  # TODO: move to callback and throw NotImplementedError
        FilterDocHasAttr.kind,
        FilterDocAttrEqual.kind,
        FilterDocAttrStarts.kind,
        FilterDocAttrEnds.kind,
        FilterDocAttrContains.kind,
        FilterDocAttrRegex.kind,
        FilterDocHasRaw.kind,
        FilterDocHasText.kind,
        FilterDocIsRegexText.kind,
        FilterDocIsRegexRaw.kind,
    ]
)

IMPORTS = r"""
local htmlparser = require("htmlparser"); 
local json = require("dkjson");
-- optional module for Buildins.re_any, Buildins.re_all, Buildins.re, Buildins.re_all, Buildins.re_sub
-- if not passed flag - codegen should be try convert to pattern matching synatax for simple cases
local ok, rex = pcall(require, "rex_pcre")
if not ok then rex = {} end
"""
MAGIC_METHODS = {"__KEY__": "key", "__VALUE__": "value", "__ITEM__": "item"}
LOGGER = logging.getLogger("ssc_gen")

# lua syntax ignore add field if values == nil
# for correct json serialize required usage special object
NIL_TYPE = "json.null"
WARNING_PCRE_MSG = """
PCRE regex detected via class variable. Conversion to Lua pattern is not supported.
- Either install C dependency 'lrexlib' for PCRE compatibility
- Or pass the regex directly to expression
- If you are using Lua pattern syntax inside a class variable, this warning can be ignored
- see also https://www.lua.org/manual/5.4/manual.html#6.4.1
"""

WARNING_DOTALL_FLAG = "lua pattern syntax not support re.X | re.DOTALL flag"
WARNING_CSS_QUERY_MSG = "lua htmlparser not full support CSS3 query selectors syntax. Recommended css query pass as argument"


TYPES = {
    VariableType.STRING: "string",
    VariableType.LIST_STRING: "string[]",
    VariableType.OPTIONAL_STRING: "string|nil",
    VariableType.OPTIONAL_LIST_STRING: "string[]|nil",
    VariableType.NULL: "nil",
    VariableType.INT: "integer",
    VariableType.OPTIONAL_INT: "integer|nil",
    VariableType.LIST_INT: "integer[]",
    VariableType.FLOAT: "number",
    VariableType.OPTIONAL_FLOAT: "number|nil",
    VariableType.LIST_FLOAT: "number[]",
    VariableType.OPTIONAL_LIST_FLOAT: "number[]|nil",
    VariableType.BOOL: "boolean",
}

JSON_TYPES = {
    JsonVariableType.STRING: "string",
    JsonVariableType.BOOLEAN: "bool",
    JsonVariableType.NUMBER: "integer",
    JsonVariableType.FLOAT: "number[]",
    JsonVariableType.OPTIONAL_NUMBER: "integer|nil",
    JsonVariableType.OPTIONAL_FLOAT: "number|nil",
    JsonVariableType.OPTIONAL_BOOLEAN: "boolean|nil",
    JsonVariableType.OPTIONAL_STRING: "string|nil",
    JsonVariableType.NULL: "nil",
    JsonVariableType.ARRAY_STRING: "string[]",
    JsonVariableType.ARRAY_FLOAT: "number[]",
    JsonVariableType.ARRAY_BOOLEAN: "boolean[]",
    JsonVariableType.ARRAY_NUMBER: "integer[]",
}


def make_lua_docstring(docstr: str) -> str:
    if not docstr:
        return ""
    return "\n".join([f"-- {i}" for i in docstr.split("\n")])


def py_var_to_lua_var(value: Any) -> str:
    if value is None:
        return NIL_TYPE
    elif isinstance(value, str):
        value = wrap_double_quotes(value)
    elif isinstance(value, bool):
        value = "true" if value else "false"
    elif isinstance(value, list):
        if all(isinstance(v, str) for v in value):
            value = [wrap_double_quotes(i) for i in value]
        else:
            # numbers, floats
            value = [str(i) for i in value]
        value = "{" + ", ".join(value) + "}"
    return value


def py_regex_to_lua_rex_pcre(
    pattern: str,
    ignore_case: bool = False,
    dotall: bool = False,
    multiline: bool = False,
) -> str:
    flags = ""
    if ignore_case:
        flags += "i"
    if dotall:
        flags += "s"
    if multiline:
        flags += "m"
    flags = f"(?{flags})" if flags else ""
    return wrap_double_quotes(flags + pattern).replace("\\", "\\\\")


@CONVERTER(ModuleImports.kind)
def pre_imports(_: ModuleImports) -> str:
    return IMPORTS + "\n" + HELPER_FUNCTIONS


@CONVERTER(Docstring.kind)
def pre_docstring(node: Docstring) -> str:
    return make_lua_docstring(node.kwargs["value"])


def get_typedef_field_by_name(node: TypeDef, field_name: str) -> str:
    value = [i for i in node.body if i.kwargs["name"] == field_name][0]
    value = cast(TypeDefField, value)
    if value.kwargs["type"] == VariableType.NESTED:
        type_ = f"T_{value.kwargs['cls_nested']}"
        if value.kwargs["cls_nested_type"] == StructType.LIST:
            type_ = f"{type_}[]"
    elif value.kwargs["type"] == VariableType.JSON:
        type_ = f"J_{value.kwargs['cls_nested']}"
        if value.kwargs["cls_nested_type"] == StructType.LIST:
            type_ = f"{type_}[]"
    else:
        type_ = TYPES[value.kwargs["type"]]
    return type_


@CONVERTER(TypeDef.kind, StructType.ACC_LIST, post_callback=lambda _: "\n")
def pre_typedef_acc_list(node: TypeDef) -> str:
    name, _st_type = node.unpack_args()
    return f"---@alias T_{name} string[]"


@CONVERTER(TypeDef.kind, StructType.FLAT_LIST, post_callback=lambda _: "\n")
def pre_typedef_flat_list(node: TypeDef) -> str:
    name, _st_type = node.unpack_args()
    type_ = get_typedef_field_by_name(node, "__ITEM__")
    return f"---@alias T_{name} {type_}[]"


@CONVERTER(TypeDef.kind, StructType.DICT, post_callback=lambda _: "\n")
def pre_typedef_flat_dict(node: TypeDef) -> str:
    name, _st_type = node.unpack_args()
    type_ = get_typedef_field_by_name(node, "__VALUE__")
    return f"---@alias T_{name} table<string, {type_}>"


@CONVERTER(TypeDef.kind, StructType.ITEM, post_callback=lambda _: "\n")
def pre_typedef_flat_item(node: TypeDef) -> str:
    name, _st_type = node.unpack_args()
    return f"---@class T_{name}"


@CONVERTER(TypeDef.kind, StructType.LIST, post_callback=lambda _: "\n")
def pre_typedef_list(node: TypeDef) -> str:
    name, _st_type = node.unpack_args()
    return f"---@class T_{name}"


@CONVERTER(TypeDefField.kind)
def pre_typedef_field(node: TypeDefField) -> str:
    # @alias types, skip
    if node.parent.kwargs["struct_type"] in {
        StructType.ACC_LIST,
        StructType.FLAT_LIST,
        StructType.DICT,
    }:
        return ""

    name, var_type, cls_nested, cls_nested_type = node.unpack_args()

    if cls_nested:
        if cls_nested_type in {
            StructType.ACC_LIST,
            StructType.LIST,
            StructType.FLAT_LIST,
        }:
            type_ = f"T_{cls_nested}[]"
        else:
            type_ = f"T_{cls_nested}"
    elif var_type == VariableType.JSON:
        if cls_nested_type == StructType.LIST:
            type_ = f"J_{cls_nested}[]"
        else:
            type_ = f"J_{cls_nested}"
    else:
        type_ = TYPES.get(var_type)
    return f"---@field {name} {type_}"


@CONVERTER(JsonStruct.kind, post_callback=lambda _: "\n")
def pre_json_struct(node: JsonStruct) -> str:
    name, _is_array = node.unpack_args()
    return f"---@class J_{name}"


@CONVERTER(JsonStructField.kind)
def pre_json_struct_field(node: JsonStructField) -> str:
    name, var_type = node.unpack_args()
    type_ = JSON_TYPES.get(var_type)
    return f"---@field {name} {type_}"


@CONVERTER(StructParser.kind)
def pre_struct_parser(node: StructParser) -> str:
    name = node.kwargs["name"]
    # TODO DOSTR SIGNATURE
    if node.kwargs["docstring"]:
        docstr = make_lua_docstring(node.kwargs["docstring"])
        return f"{docstr}\nlocal {name} = " + "{}; "
    return f"local {name} = " + "{}; "


@CONVERTER(StructPartDocMethod.kind, post_callback=lambda _: " end")
def pre_part_doc(node: StructPartDocMethod) -> str:
    parent = node.parent.kwargs["name"]

    return f"function {parent}:_split_doc(v) "


@CONVERTER(ExprReturn.kind)
def pre_return(node: ExprReturn) -> str:
    return f"return v{node.index_prev}; "


@CONVERTER(ExprNoReturn.kind)
def pre_no_return(_node: ExprReturn) -> str:
    # used in pre_validate function, not need use specual object json.null
    return "return nil; "


@CONVERTER(ExprNested.kind)
def pre_nested(node: ExprNested) -> str:
    prv, nxt = prev_next_var(node)
    schema_name, _schema_type = node.unpack_args()
    return f"local {nxt} = {schema_name}:new({prv}):parse(); "


@CONVERTER(StructPreValidateMethod.kind, post_callback=lambda _: " end")
def pre_pre_validate(node: StructPreValidateMethod) -> str:
    parent = node.parent.kwargs["name"]
    return f"function {parent}:_pre_validate(v) "


@CONVERTER(ExprClassVar.kind)
def pre_classvar(node: ExprClassVar) -> str:
    value, class_name, field_name, *_ = node.unpack_args()

    value = py_var_to_lua_var(value)
    # todo: move classvars to struct node for better code output
    return f"{class_name}.{field_name} = {value}; "


@CONVERTER(StructFieldMethod.kind, post_callback=lambda _: " end")
def pre_parse_field(node: StructFieldMethod) -> str:
    cls_name = node.parent.kwargs["name"]
    name = node.kwargs["name"]
    name = MAGIC_METHODS.get(name, name)
    fn_name = "_parse_" + name
    return f"function {cls_name}:{fn_name}(v)"


@CONVERTER(StructInitMethod.kind)
def pre_struct_init(node: StructInitMethod) -> str:
    parent_name = node.parent.kwargs["name"]
    # `end` keyword inner function
    return lua_struct_init(parent_name)


@CONVERTER(StartParseMethod.kind)
def pre_start_parse(node: StartParseMethod) -> str:
    node.parent = cast(StructParser, node.parent)
    # skip create parse() method for literals-only struct
    if node.parent.struct_type == StructType.CONFIG_CLASSVARS:
        return ""

    parent_name = node.parent.kwargs["name"]
    ret_t = f"T_{parent_name}"
    if node.parent.struct_type in {
        StructType.ACC_LIST,
        StructType.FLAT_LIST,
        StructType.LIST,
    }:
        ret_t += "[]"
    # insert annotation
    return f"---@return {ret_t}\nfunction {parent_name}:parse() "


@CONVERTER.post(StartParseMethod.kind, StructType.ITEM)
def post_start_parse_item(node: StartParseMethod) -> str:
    code = ""
    if have_pre_validate_call(node):
        # throw error in runtime if check is failed
        code += "self:_pre_validate(self._document); "
    code += "local result = {}; "
    for expr in node.body:
        if expr.kind == ExprCallStructMethod.kind:
            name = expr.kwargs["name"]
            if name.startswith("__"):
                continue
            code += f"result[{name!r}] = self:_parse_{name}(self._document); "
        elif expr.kind == ExprCallStructClassVar.kind:
            st_name, f_name, _ = expr.unpack_args()
            code += f"result[{f_name}] = {st_name}.{f_name}; "
    code += "return result; end "
    return code


@CONVERTER.post(StartParseMethod.kind, StructType.LIST)
def post_start_parse_list(node: StartParseMethod) -> str:
    code = ""
    if have_pre_validate_call(node):
        code += "self:_pre_validate(self._document); "
    code += "local result = {}; "
    code += "for _, el in ipairs(self:_split_doc(self._document)) do "
    code += "table.insert(result, {"
    for expr in node.body:
        if expr.kind == ExprCallStructMethod.kind:
            name = expr.kwargs["name"]
            if name.startswith("__"):
                continue
            code += f"{name} = self:_parse_{name}(el), "
        elif expr.kind == ExprCallStructClassVar.kind:
            st_name, f_name, _ = expr.unpack_args()
            code += f"{f_name} = {st_name}.{f_name}, "
    code += " }) end "
    code += "return result; end "
    return code


@CONVERTER.post(StartParseMethod.kind, StructType.DICT)
def post_start_parse_dict(node: StartParseMethod) -> str:
    code = ""
    if have_pre_validate_call(node):
        # throw error in runtime if check is failed
        code += "self:_pre_validate(self._document); "
    code += "local result = {}; "
    code += "for _, el in ipairs(self:_split_doc(self._document)) do "
    code += "result[self:_parse_key(el)] = self:_parse_value(el) end "
    code += "return result; end "
    return code


@CONVERTER.post(StartParseMethod.kind, StructType.FLAT_LIST)
def post_start_parse_flat_list(node: StartParseMethod) -> str:
    code = ""
    if have_pre_validate_call(node):
        # throw error in runtime if check is failed
        code += "self:_pre_validate(self._document); "
    code += "local result = {}; "
    code += "for _, el in ipairs(self:_split_doc(self._document)) do "
    code += "table.insert(result, self:_parse_item(el)) end "
    code += "return result; end "
    return code


@CONVERTER.post(StartParseMethod.kind, StructType.ACC_LIST)
def post_start_parse_acc_list(node: StartParseMethod) -> str:
    code = ""
    if have_pre_validate_call(node):
        # throw error in runtime if check is failed
        code += "self:_pre_validate(self._document); "
    code += "local result = {}; "
    for expr in node.body:
        if expr.kind == ExprCallStructMethod.kind:
            name = expr.kwargs["name"]
            if name.startswith("__"):
                continue
            code += f"for _, e in ipairs(self:_parse_{name}(self._document)) do table.insert(result, e) end"
            # local function Buildins.unique(arr)
            code += "result = Buildins.unique(result); "
    code += "return result; end "
    return code


@CONVERTER(ExprDefaultValueStart.kind)
def pre_default_start(node: ExprDefaultValueStart) -> str:
    prv, nxt = prev_next_var(node)
    # ok, result = pcall(function() ... end); if ok ... else return ... end
    return f"local {nxt} = {prv}; local ok, result = pcall(function() "


@CONVERTER(ExprDefaultValueEnd.kind)
def pre_default_end(node: ExprDefaultValueEnd) -> str:
    value = lua_get_classvar_hook_or_value(node, "value")
    return f"end); if ok then return result else return {value} end"


@CONVERTER(ExprStringFormat.kind)
def pre_str_fmt(node: ExprStringFormat) -> str:
    prv, nxt = prev_next_var(node)
    fmt = lua_get_classvar_hook_or_value(node, "fmt")
    return f"local {nxt} = string.format({fmt}, {prv}); "


@CONVERTER(ExprListStringFormat.kind)
def pre_list_str_fmt(node: ExprListStringFormat) -> str:
    prv, nxt = prev_next_var(node)
    # local function Buildins.map(tbl, fn)
    fmt = lua_get_classvar_hook_or_value(node, "fmt")
    return f"local {nxt} = Buildins.map({prv}, function(e) return string.format({fmt}, e) end); "


@CONVERTER(ExprStringTrim.kind)
def pre_str_trim(node: ExprStringTrim) -> str:
    prv, nxt = prev_next_var(node)
    substr = lua_get_classvar_hook_or_value(node, "substr")
    # function Buildins.trim(s, chars)
    return f"local {nxt} = Buildins.trim({prv}, {substr}); "


@CONVERTER(ExprListStringTrim.kind)
def pre_list_str_trim(node: ExprListStringTrim) -> str:
    prv, nxt = prev_next_var(node)

    # local function trim(s, chars)
    # local function Buildins.map(tbl, fn)
    substr = lua_get_classvar_hook_or_value(node, "substr")
    return f"local {nxt} = Buildins.map({prv}, function(e) return Buildins.trim(e, {substr}) end); "


@CONVERTER(ExprStringLeftTrim.kind)
def pre_str_left_trim(node: ExprStringLeftTrim) -> str:
    prv, nxt = prev_next_var(node)
    substr = lua_get_classvar_hook_or_value(node, "substr")
    # local function ltrim(s, chars)
    return f"local {nxt} = Buildins.ltrim({prv}, {substr}); "


@CONVERTER(ExprListStringLeftTrim.kind)
def pre_list_str_left_trim(node: ExprListStringLeftTrim) -> str:
    prv, nxt = prev_next_var(node)
    substr = lua_get_classvar_hook_or_value(node, "substr")
    # function Buildins.ltrim(s, chars)
    # function Buildins.map(tbl, fn)
    return f"local {nxt} = Buildins.map({prv}, function(e) return Buildins.ltrim(e, {substr}) end); "


@CONVERTER(ExprStringRightTrim.kind)
def pre_str_right_trim(node: ExprStringRightTrim) -> str:
    prv, nxt = prev_next_var(node)
    substr = lua_get_classvar_hook_or_value(node, "substr")
    # function Buildins.rtrim(s, chars)
    return f"local {nxt} = Buildins.rtrim({prv}, {substr}); "


@CONVERTER(ExprListStringRightTrim.kind)
def pre_list_str_right_trim(node: ExprListStringRightTrim) -> str:
    prv, nxt = prev_next_var(node)
    substr = lua_get_classvar_hook_or_value(node, "substr")
    # function Buildins.rtrim(s, chars)
    # function Buildins.map(tbl, fn)
    return f"local {nxt} = Buildins.map({prv}, function(e) return Buildins.rtrim(e, {substr}) end); "


@CONVERTER(ExprStringSplit.kind)
def pre_str_split(node: ExprStringSplit) -> str:
    prv, nxt = prev_next_var(node)
    sep = lua_get_classvar_hook_or_value(node, "sep")
    # function Buildins.split(s, sep)
    return f"local {nxt} = Buildins.split({prv}, {sep}); "


@CONVERTER(ExprStringReplace.kind)
def pre_str_replace(node: ExprStringReplace) -> str:
    prv, nxt = prev_next_var(node)
    old = lua_get_classvar_hook_or_value(node, "old")
    new = lua_get_classvar_hook_or_value(node, "new")

    return f"local {nxt} = string.gsub({prv}, Buildins.escape_pattern({old}), {new}); "


@CONVERTER(ExprListStringReplace.kind)
def pre_list_str_replace(node: ExprListStringReplace) -> str:
    prv, nxt = prev_next_var(node)
    old = lua_get_classvar_hook_or_value(node, "old")
    new = lua_get_classvar_hook_or_value(node, "new")
    # local function Buildins.map(tbl, fn)
    return f"local {nxt} = Buildins.map({prv}, function(e) string.gsub(e, Buildins.escape_pattern({old}), {new}) end); "


@CONVERTER(ExprStringRegex.kind)
def pre_str_regex(node: ExprStringRegex) -> str:
    prv, nxt = prev_next_var(node)
    pattern, _group, ignore_case, dotall = node.unpack_args()
    if node.classvar_hooks.get("pattern"):
        if not CONVERTER.USE_PCRE:
            LOGGER.warning(WARNING_PCRE_MSG)
        pattern = lua_get_classvar_hook_or_value(node, "pattern")
    else:
        if CONVERTER.USE_PCRE:
            # rex.match(s, pattern, flags)
            pattern = py_regex_to_lua_rex_pcre(
                pattern, ignore_case=ignore_case, dotall=dotall
            )
            code = f"rex.match({prv}, {pattern})"
        else:
            if dotall:
                LOGGER.warning(WARNING_DOTALL_FLAG)
            code = py_regex_to_lua_pattern(
                pattern, prv, mode="re", ignore_case=ignore_case
            )

    return f"local {nxt} = {code}"


@CONVERTER(ExprStringRegexAll.kind)
def pre_str_regex_all(node: ExprStringRegexAll) -> str:
    prv, nxt = prev_next_var(node)
    pattern, ignore_case, dotall = node.unpack_args()
    if node.classvar_hooks.get("pattern"):
        if not CONVERTER.USE_PCRE:
            LOGGER.warning(WARNING_PCRE_MSG)
        pattern = lua_get_classvar_hook_or_value(node, "pattern")
        code = f"{{}} for m in rex.gmatch({prv}, {pattern}) do table.insert(results, match) end"
    else:
        if CONVERTER.USE_PCRE:
            pattern = py_regex_to_lua_rex_pcre(
                pattern, ignore_case=ignore_case, dotall=dotall
            )
            code = f"{{}} for m in rex.gmatch({prv}, {pattern}) do table.insert(results, match) end"
        else:
            if dotall:
                LOGGER.warning(WARNING_DOTALL_FLAG)
            return py_regex_to_lua_pattern(
                pattern, prv, mode="re_all", ignore_case=ignore_case
            )

    return f"local {nxt} = {code}"


@CONVERTER(ExprStringRegexSub.kind)
def pre_str_regex_sub(node: ExprStringRegexSub) -> str:
    prv, nxt = prev_next_var(node)
    pattern, repl, ignore_case, dotall = node.unpack_args()

    repl = lua_get_classvar_hook_or_value(node, "repl")
    if node.classvar_hooks.get("pattern"):
        if not CONVERTER.USE_PCRE:
            LOGGER.warning(WARNING_PCRE_MSG)
        pattern = lua_get_classvar_hook_or_value(node, "pattern")
        code = f"rex.gsub({prv}, {pattern}, {repl})"
    else:
        if CONVERTER.USE_PCRE:
            pattern = py_regex_to_lua_rex_pcre(
                pattern, ignore_case=ignore_case, dotall=dotall
            )
            code = f"rex.gsub({prv}, {pattern}, {repl})"
        else:
            if dotall:
                LOGGER.warning(WARNING_DOTALL_FLAG)
            return py_regex_to_lua_pattern(
                pattern,
                prv,
                nxt,
                mode="re_sub",
                repl=repl,
                ignore_case=ignore_case,
            )
    return f"local {nxt} = {code}"


@CONVERTER(ExprListStringRegexSub.kind)
def pre_list_str_regex_sub(node: ExprListStringRegexSub) -> str:
    prv, nxt = prev_next_var(node)
    pattern, repl, ignore_case, dotall = node.unpack_args()

    repl = lua_get_classvar_hook_or_value(node, "repl")
    if node.classvar_hooks.get("pattern"):
        if not CONVERTER.USE_PCRE:
            LOGGER.warning(WARNING_PCRE_MSG)
        pattern = lua_get_classvar_hook_or_value(node, "pattern")
        # local function Buildins.map(tbl, fn)
        code = f"Buildins.map({prv}, function(e) rex.gsub(e, {pattern}, {repl}) end)"
    else:
        if CONVERTER.USE_PCRE:
            pattern = py_regex_to_lua_rex_pcre(
                pattern, ignore_case=ignore_case, dotall=dotall
            )
            code = f"Buildins.map({prv}, function(e) rex.gsub(e, {pattern}, {repl}) end)"
        else:
            if dotall:
                LOGGER.warning(WARNING_DOTALL_FLAG)
            return py_regex_to_lua_pattern(
                pattern,
                prv,
                mode="re_sub_map",
                repl=repl,
                ignore_case=ignore_case,
            )

    # local function Buildins.map(tbl, fn)
    return f"local {nxt} = {code}"


@CONVERTER(ExprIndex.kind)
def pre_index(node: ExprIndex) -> str:
    prv, nxt = prev_next_var(node)
    # HACK: in most languages index starts by `0`, inc value as default and use helper func
    # function Buildins.at0(arr, index)(arr, index)
    index = lua_get_classvar_hook_or_value(node, "index")
    # add check negative index value
    return f"local {nxt} = Buildins.at0({prv}, {index}); "


@CONVERTER(ExprListStringJoin.kind)
def pre_list_str_join(node: ExprListStringJoin) -> str:
    prv, nxt = prev_next_var(node)
    sep = lua_get_classvar_hook_or_value(node, "sep")
    return f"local {nxt} = table.concat({prv}, {sep}); "


@CONVERTER(ExprIsEqual.kind)
def pre_is_equal(node: ExprIsEqual) -> str:
    prv, nxt = prev_next_var(node)

    item = lua_get_classvar_hook_or_value(node, "item")
    msg = lua_get_classvar_hook_or_value(node, "msg")

    expr = f"assert({item} != {prv}, {msg}); "
    if is_last_var_no_ret(node):
        return expr
    return expr + f"local {nxt} = {prv}; "


@CONVERTER(ExprIsNotEqual.kind)
def pre_is_not_equal(node: ExprIsNotEqual) -> str:
    prv, nxt = prev_next_var(node)

    item = lua_get_classvar_hook_or_value(node, "item")
    msg = lua_get_classvar_hook_or_value(node, "msg")

    expr = f"assert({item} == {prv}, {msg}); "
    if is_last_var_no_ret(node):
        return expr
    return expr + f"local {nxt} = {prv}; "


@CONVERTER(ExprIsContains.kind)
def pre_is_contains(node: ExprIsContains) -> str:
    prv, nxt = prev_next_var(node)
    item = lua_get_classvar_hook_or_value(node, "item")
    msg = lua_get_classvar_hook_or_value(node, "msg")
    # local function contains(arr, value)
    expr = f"assert(contains({prv}, {item}), {msg}); "
    if is_last_var_no_ret(node):
        return expr
    return expr + f"local {nxt} = {prv};"


@CONVERTER(ExprStringIsRegex.kind)
def pre_is_regex(node: ExprStringIsRegex) -> str:
    prv, nxt = prev_next_var(node)
    pattern, ignore_case, msg = node.unpack_args()
    msg = lua_get_classvar_hook_or_value(node, "msg")

    if node.classvar_hooks.get("pattern"):
        if not CONVERTER.USE_PCRE:
            LOGGER.warning(WARNING_PCRE_MSG)
        pattern = lua_get_classvar_hook_or_value(node, "pattern")
        code = f"rex.match({prv}, {pattern}) ~= nil"
    else:
        if CONVERTER.USE_PCRE:
            pattern = py_regex_to_lua_rex_pcre(pattern, ignore_case=ignore_case)
            code = f"rex.match({prv}, {pattern}) ~= nil"
        else:
            code = py_regex_to_lua_pattern(pattern, prv, mode="re") + " ~= nil"
    expr = f"assert({code} ~= nil, {msg}); "
    if is_last_var_no_ret(node):
        return expr
    return expr + f"local {nxt} = {prv};"


@CONVERTER(ExprListStringAnyRegex.kind)
def pre_list_str_any_is_regex(node: ExprListStringAnyRegex) -> str:
    # a.some(i => (new RegExp("foo")).test(i))
    prv, nxt = prev_next_var(node)
    pattern, ignore_case, msg = node.unpack_args()
    msg = lua_get_classvar_hook_or_value(node, "msg")
    if node.classvar_hooks.get("pattern"):
        if not CONVERTER.USE_PCRE:
            LOGGER.warning(WARNING_PCRE_MSG)
        pattern = lua_get_classvar_hook_or_value(node, "pattern")
        code = f"Buildins.re_any({prv}, {pattern})"
    else:
        if CONVERTER.USE_PCRE:
            pattern = py_regex_to_lua_rex_pcre(pattern, ignore_case=ignore_case)
            code = f"Buildins.re_any({prv}, {pattern})"
        else:
            code = (
                py_regex_to_lua_pattern(
                    pattern, prv, ignore_case=ignore_case, mode="mre_any"
                )
                + " == true"
            )
    expr = f"assert({code}, {msg}); "
    if is_last_var_no_ret(node):
        return expr
    return expr + f"local {nxt} = {prv};"


@CONVERTER(ExprListStringAllRegex.kind)
def pre_list_str_all_is_regex(node: ExprListStringAllRegex) -> str:
    prv, nxt = prev_next_var(node)
    # a.every(i => (new RegExp("foo")).test)
    pattern, ignore_case, msg = node.unpack_args()

    msg = lua_get_classvar_hook_or_value(node, "msg")
    if node.classvar_hooks.get("pattern"):
        if not CONVERTER.USE_PCRE:
            LOGGER.warning(WARNING_PCRE_MSG)
        pattern = lua_get_classvar_hook_or_value(node, "pattern")
        code = f"Buildins.re_all({prv}, {pattern})"
    else:
        if CONVERTER.USE_PCRE:
            pattern = py_regex_to_lua_rex_pcre(pattern, ignore_case=ignore_case)
            code = f"Buildins.re_all({prv}, {pattern})"
        else:
            code = (
                py_regex_to_lua_pattern(
                    pattern, prv, ignore_case=ignore_case, mode="mre_all"
                )
                + " == true"
            )

    # local function re_all(arr, pattern)
    expr = f"assert({code}, {msg}); "
    if is_last_var_no_ret(node):
        return expr
    return expr + f"local {nxt} = {prv};"


@CONVERTER(ExprIsCss.kind)
def pre_is_css(node: ExprIsCss) -> str:
    prv, nxt = prev_next_var(node)
    query = lua_get_classvar_hook_or_value(node, "query")
    msg = lua_get_classvar_hook_or_value(node, "msg")
    if node.classvar_hooks.get("query"):
        LOGGER.warning(WARNING_CSS_QUERY_MSG)
        code = f"assert({prv}:querySelector({query}), {msg})"
        if not is_last_var_no_ret(node):
            code += f"\nlocal {nxt} = {prv};"
    else:
        expr = css_query_to_lua_htmlparser_code(query, prv, nxt)
        code = "\n".join(expr)
        code = (
            f"local tmp_{prv} = {prv}\n"
            + code
            + f"\nassert({prv} ~= nil, {msg})"
            + f"\n{nxt} = tmp_{prv}"
        )
    return code


@CONVERTER(ExprIsXpath.kind)
def pre_is_xpath(_: ExprIsXpath) -> str:
    raise NotImplementedError("lua htmlparser not support xpath")


@CONVERTER(ExprToInt.kind)
def pre_to_int(node: ExprToInt) -> str:
    prv, nxt = prev_next_var(node)
    return f"local {nxt} = tonumber({prv}); "


@CONVERTER(ExprToListInt.kind)
def pre_to_list_int(node: ExprToListInt) -> str:
    prv, nxt = prev_next_var(node)
    # local function Buildins.map(tbl, fn)
    return f"local {nxt} = Buildins.map({prv}, function(e) tonumber(e) end); "


@CONVERTER(ExprToFloat.kind)
def pre_to_float(node: ExprToFloat) -> str:
    prv, nxt = prev_next_var(node)
    # both used convert float64 or int function
    # https://www.lua.org/manual/5.3/manual.html#pdf-tonumber
    return f"local {nxt} = tonumber({prv}); "


@CONVERTER(ExprToListFloat.kind)
def pre_to_list_float(node: ExprToListFloat) -> str:
    prv, nxt = prev_next_var(node)
    # local function Buildins.map(tbl, fn)
    return f"local {nxt} = Buildins.map({prv}, function(e) tonumber(e) end); "


@CONVERTER(ExprToListLength.kind)
def pre_to_len(node: ExprToListLength) -> str:
    prv, nxt = prev_next_var(node)
    # The length operator is denoted by the unary prefix operator `#`
    # https://www.lua.org/manual/5.3/manual.html#3.4.7
    return f"local {nxt} = #{prv}; "


@CONVERTER(ExprToBool.kind)
def pre_to_bool(node: ExprToBool) -> str:
    prv, nxt = prev_next_var(node)
    # Buildins.to_bool(v)
    return f"local {nxt} = Buildins.to_bool({prv});"


@CONVERTER(ExprJsonify.kind)
def pre_jsonify(node: ExprJsonify) -> str:
    prv, nxt = prev_next_var(node)
    _, _, query = node.unpack_args()
    # lua index starts by 1, fix query
    expr = "".join(
        f"[{int(i) + 1}]" if i.isdigit() else f"[{i}]"
        for i in jsonify_query_parse(query)
    )

    return f"local {nxt} = json.decode({prv}){expr}; "


@CONVERTER(ExprCss.kind)
def pre_css(node: ExprCss) -> str:
    prv, nxt = prev_next_var(node)
    query = lua_get_classvar_hook_or_value(node, "query")
    if node.classvar_hooks.get("query"):
        LOGGER.warning(WARNING_CSS_QUERY_MSG)
        code = f"local {nxt} = {prv}:select({query})[1]"
    else:
        # TODO: compare: array or sinlge object?
        code = (
            "\n".join(css_query_to_lua_htmlparser_code(query, prv, nxt)) + "[1]"
        )

    return code


@CONVERTER(ExprCssAll.kind)
def pre_css_all(node: ExprCssAll) -> str:
    prv, nxt = prev_next_var(node)
    query = lua_get_classvar_hook_or_value(node, "query")
    if node.classvar_hooks.get("query"):
        LOGGER.warning(WARNING_CSS_QUERY_MSG)
        code = f"local {nxt} = {prv}:select({query})"
    else:
        # TODO: compare: array or sinlge object?
        code = "\n".join(css_query_to_lua_htmlparser_code(query, prv, nxt))
    # returns table of ElementNode object
    return code


@CONVERTER(ExprXpath.kind)
def pre_xpath(_node: ExprXpath) -> str:
    raise NotImplementedError("lua htmlparser not support xpath")


@CONVERTER(ExprXpathAll.kind)
def pre_xpath_all(node: ExprXpathAll) -> str:
    raise NotImplementedError("lua htmlparser not support xpath")


@CONVERTER(ExprGetHtmlAttr.kind)
def pre_html_attr(node: ExprGetHtmlAttr) -> str:
    prv, nxt = prev_next_var(node)
    keys = node.kwargs["key"]
    if len(keys) == 1:
        key = keys[0]
        if key == "class":
            return f'local {nxt} = table.concat({prv}.classes, " "); '
        elif key == "id":
            return f"local {nxt} = {prv}.id; "
        return f"local {nxt} = {prv}.attributes[{key!r}];"

    keys = py_var_to_lua_var(list(keys))  # too lazy add tuple converter
    # CssExt.get_attr_values(el, keys)
    return f"local {nxt} = CssExt.get_attr_values({prv}, {keys}); "


@CONVERTER(ExprGetHtmlAttrAll.kind)
def pre_html_attr_all(node: ExprGetHtmlAttrAll) -> str:
    prv, nxt = prev_next_var(node)
    keys = node.kwargs["key"]
    if len(keys) == 1:
        key = keys[0]
        # local function Buildins.map(tbl, fn)
        # TODO: helper func for iterate extract attributes
        return f"local {nxt} = Buildins.map({prv}, function(e) return CssExt.attr(e, {key!r}) end)"
    keys = py_var_to_lua_var(list(keys))
    # local function CssExt.flat_get_attr_values(elements, keys)
    return f"local {nxt} = CssExt.flat_get_attr_values({prv}, {keys}); "


@CONVERTER(ExprGetHtmlText.kind)
def pre_html_text(node: ExprGetHtmlText) -> str:
    prv, nxt = prev_next_var(node)

    # in lua-htmparser :getcontent() means - extract text, :gettext() - extract raw outherHtml content
    return f"local {nxt} = {prv}:getcontent()"


@CONVERTER(ExprGetHtmlTextAll.kind)
def pre_html_text_all(node: ExprGetHtmlTextAll) -> str:
    prv, nxt = prev_next_var(node)
    # naive apologize, its element objects, not document
    # local function Buildins.map(tbl, fn)
    return f"local {nxt} = Buildins.map({prv}, function(e) e:getcontent() end)"


@CONVERTER(ExprGetHtmlRaw.kind)
def pre_html_raw(node: ExprGetHtmlRaw) -> str:
    prv, nxt = prev_next_var(node)
    # local function get_outer_html(node)
    return f"local {nxt} = {prv}:gettext()"


@CONVERTER(ExprGetHtmlRawAll.kind)
def pre_html_raw_all(node: ExprGetHtmlRawAll) -> str:
    prv, nxt = prev_next_var(node)
    # local function Buildins.map(tbl, fn)
    return f"local {nxt} = Buildins.map({prv}, function(e) e:gettext() end)"


@CONVERTER(ExprStringRmPrefix.kind)
def pre_str_rm_prefix(node: ExprStringRmPrefix) -> str:
    prv, nxt = prev_next_var(node)
    substr = lua_get_classvar_hook_or_value(node, "substr")
    # local function Buildins.remove_prefix(s, prefix)
    return f"local {nxt} = Buildins.remove_prefix({prv}, {substr}); "


@CONVERTER(ExprListStringRmPrefix.kind)
def pre_list_str_rm_prefix(node: ExprListStringRmPrefix) -> str:
    prv, nxt = prev_next_var(node)
    substr = lua_get_classvar_hook_or_value(node, "substr")
    # local function Buildins.remove_prefix(s, prefix)
    # Buildins.map(tbl, fn)
    return f"local {nxt} = Buildins.map({prv}, function(e) Buildins.remove_prefix(e, {substr}) end); "


@CONVERTER(ExprStringRmSuffix.kind)
def pre_str_rm_suffix(node: ExprStringRmSuffix) -> str:
    prv, nxt = prev_next_var(node)
    substr = lua_get_classvar_hook_or_value(node, "substr")
    # local function Buildins.remove_suffix(s, suffix)
    return f"local {nxt} = Buildins.remove_suffix({prv}, {substr}); "


@CONVERTER(ExprListStringRmSuffix.kind)
def pre_list_str_rm_suffix(node: ExprListStringRmSuffix) -> str:
    prv, nxt = prev_next_var(node)
    substr = lua_get_classvar_hook_or_value(node, "substr")
    # local function Buildins.remove_suffix(s, suffix)
    return f"local {nxt} = Buildins.map({prv}, function(e) Buildins.remove_suffix(e, {substr}) end); "


@CONVERTER(ExprStringRmPrefixAndSuffix.kind)
def pre_str_rm_prefix_and_suffix(node: ExprStringRmPrefixAndSuffix) -> str:
    prv, nxt = prev_next_var(node)
    substr = lua_get_classvar_hook_or_value(node, "substr")
    # local function Buildins.remove_prefix_suffix(s, substr)
    return f"local {nxt} = Buildins.remove_prefix_suffix({prv}, {substr})"


@CONVERTER(ExprListStringRmPrefixAndSuffix.kind)
def pre_list_str_rm_prefix_and_suffix(
    node: ExprListStringRmPrefixAndSuffix,
) -> str:
    prv, nxt = prev_next_var(node)
    substr = lua_get_classvar_hook_or_value(node, "substr")
    # local function Buildins.remove_prefix_suffix(s, substr)
    return f"local {nxt} = Buildins.map({prv}, function(e) Buildins.remove_prefix_suffix(e, {substr}) end)"


@CONVERTER(ExprHasAttr.kind)
def pre_has_attr(node: ExprHasAttr) -> str:
    prv, nxt = prev_next_var(node)
    key = lua_get_classvar_hook_or_value(node, "key")
    msg = lua_get_classvar_hook_or_value(node, "msg")
    expr = f"assert({prv}.attributes[{key!r}] ~= nil, {msg})"
    if is_last_var_no_ret(node):
        return expr
    return expr + f"local {nxt} = {prv};"


@CONVERTER(ExprListHasAttr.kind)
def pre_list_has_attr(node: ExprListHasAttr) -> str:
    prv, nxt = prev_next_var(node)
    key = lua_get_classvar_hook_or_value(node, "key")
    msg = lua_get_classvar_hook_or_value(node, "msg")
    # local function CssExt.all_has_attr(nodelist, attr)
    expr = f"assert(CssExt.all_has_attr({prv}, {key}, {msg})"
    if is_last_var_no_ret(node):
        return expr
    return expr + f"local {nxt} = {prv}"


@CONVERTER(ExprFilter.kind, post_callback=lambda _: "end ); ")
def pre_expr_filter(node: ExprFilter) -> str:
    # function Buildins.filter(tbl, fn)
    prv, nxt = prev_next_var(node)
    return f"local {nxt} = Buildins.filter({prv}, function(e) "


@CONVERTER(FilterOr.kind, post_callback=lambda _: ")")
def pre_filter_or(_node: FilterOr) -> str:
    return " or ("


@CONVERTER(FilterAnd.kind, post_callback=lambda _: ")")
def pre_filter_and(_node: FilterAnd) -> str:
    return " and ("


@CONVERTER(FilterNot.kind, post_callback=lambda _: ")")
def pre_filter_not(_node: FilterNot) -> str:
    return " not ("


@CONVERTER(FilterStrIn.kind)
def pre_filter_in(node: FilterStrIn) -> str:
    values, *_ = node.unpack_args()
    if len(values) == 1:
        # local function F.in_(s, sub)
        expr = f"F.in_(e, {values[0]!r})"
    else:
        val_arr = py_var_to_lua_var(list(values))
        # local function F.any_in(s, arr)
        expr = f"F.any_in(e, {val_arr})"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" and {expr}"
    return expr


@CONVERTER(FilterStrStarts.kind)
def pre_filter_starts_with(node: FilterStrStarts) -> str:
    values, *_ = node.unpack_args()
    if len(values) == 1:
        # local function F.sw(s, prefix)
        expr = f"F.sw(e, {values[0]!r})"
    else:
        val_arr = py_var_to_lua_var(list(values))
        # local function F.any_sw(s, arr)
        expr = f"F.any_sw(e, {val_arr})"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" and {expr}"
    return expr


@CONVERTER(FilterStrEnds.kind)
def pre_filter_ends_with(node: FilterStrEnds) -> str:
    values, *_ = node.unpack_args()
    if len(values) == 1:
        # local function F.ew(s, suffix)
        expr = f"F.ew(e, {values[0]!r})"
    else:
        val_arr = py_var_to_lua_var(list(values))
        # local function F.any_ew(s, arr)
        expr = f"F.any_ew(e, {val_arr})"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" and {expr}"
    return expr


@CONVERTER(FilterStrRe.kind)
def pre_filter_re(node: FilterStrRe) -> str:
    pattern, ignore_case, *_ = node.unpack_args()
    if node.classvar_hooks.get("pattern"):
        if not CONVERTER.USE_PCRE:
            LOGGER.warning(WARNING_PCRE_MSG)
        pattern = lua_get_classvar_hook_or_value(node, "pattern")
        expr = f"F.re(e, {pattern})"
    else:
        if CONVERTER.USE_PCRE:
            # local function F.re(s, pat, flags)
            pattern = py_regex_to_lua_rex_pcre(pattern, ignore_case=ignore_case)
            expr = f"F.re(e, {pattern})"
        else:
            # backport pattern matching impl
            # F.pm = function(s, pat, ...)
            expr = py_regex_to_lua_pattern(pattern, "e", mode="re_f")

    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" and {expr}"
    return expr


@CONVERTER(FilterEqual.kind)
def pre_filter_eq(node: FilterEqual) -> str:
    values, *_ = node.unpack_args()
    # i == value
    # or any(i == value for i in values)
    if len(values) == 1:
        # local function F.eq(s, other)
        expr = f"F.eq(e, {values[0]!r})"
    else:
        # local function F.any_eq(s, arr)
        val_arr = py_var_to_lua_var(list(values))
        expr = f"F.any_eq(e, {val_arr})"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" and {expr}"
    return expr


@CONVERTER(FilterNotEqual.kind)
def pre_filter_ne(node: FilterNotEqual) -> str:
    values, *_ = node.unpack_args()
    # if single value !=
    # else all(i != e for e in values)
    if len(values) == 1:
        # local function F.ne(s, other)
        expr = f"F.ne(e, {values[0]!r})"
    else:
        val_arr = py_var_to_lua_var(list(values))
        # local function F.all_ne(s, arr)
        expr = f"F.all_ne(e, {val_arr})"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" and {expr}"
    return expr


@CONVERTER(FilterStrLenEq.kind)
def pre_filter_str_len_eq(node: FilterStrLenEq) -> str:
    length, *_ = node.unpack_args()
    # len(i) == lenght

    # local function F.len_eq(s, n)
    expr = f"F.len_eq(e, {length})"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" and {expr}"
    return expr


@CONVERTER(FilterStrLenNe.kind)
def pre_filter_str_len_ne(node: FilterStrLenNe) -> str:
    length, *_ = node.unpack_args()
    # local function F.len_ne(s, n)
    expr = f"F.len_ne(e, {length})"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" and {expr}"
    return expr


@CONVERTER(FilterStrLenLt.kind)
def pre_filter_str_len_lt(node: FilterStrLenLt) -> str:
    length, *_ = node.unpack_args()
    # local function F.len_lt(s, n)
    expr = f"F.len_lt(e, {length})"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" and {expr}"
    return expr


@CONVERTER(FilterStrLenLe.kind)
def pre_filter_str_len_le(node: FilterStrLenLe) -> str:
    length, *_ = node.unpack_args()
    # len(i) <= lenght
    # local function F.len_le(s, n)
    expr = f"F.len_le(e, {length})"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" and {expr}"
    return expr


@CONVERTER(FilterStrLenGt.kind)
def pre_filter_str_len_gt(node: FilterStrLenGt) -> str:
    length, *_ = node.unpack_args()
    # len(i) > lenght
    # local function F.len_gt(s, n)
    expr = f"F.len_gt(e, {length})"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" and {expr}"
    return expr


@CONVERTER(FilterStrLenGe.kind)
def pre_filter_str_len_ge(node: FilterStrLenGe) -> str:
    length, *_ = node.unpack_args()
    # len(i) >= lenght
    # local function F.len_ge(s, n)
    expr = f"F.len_ge(e, {length})"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" and {expr}"
    return expr


@CONVERTER(ExprListUnique.kind)
def pre_list_unique(node: ExprListUnique) -> str:
    prv, nxt = prev_next_var(node)
    # function Buildins.unique(arr)

    # this impl save elements order
    return f"local {nxt} = Buildins.unique({prv})"


@CONVERTER(ExprStringMapReplace.kind)
def pre_str_map_repl(node: ExprStringMapReplace) -> str:
    prv, nxt = prev_next_var(node)

    old_arr, new_arr = node.unpack_args()
    old_arr = py_var_to_lua_var(list(old_arr))  # type: ignore
    new_arr = py_var_to_lua_var(list(new_arr))  # type: ignore
    # local Buildins.map_replace(s, old, new)
    return f"local {nxt} = Buildins.map_replace({prv}, {old_arr}, {new_arr})"


@CONVERTER(ExprListStringMapReplace.kind)
def pre_list_str_map_repl(node: ExprListStringMapReplace) -> str:
    prv, nxt = prev_next_var(node)

    old_arr, new_arr = node.unpack_args()
    old_arr = py_var_to_lua_var(list(old_arr))  # type: ignore
    new_arr = py_var_to_lua_var(list(new_arr))  # type: ignore
    return f"local {nxt} = Buildins.map({prv}, function(e) Buildins.map_replace(e, {old_arr}, {new_arr}) end)"


@CONVERTER(ExprStringUnescape.kind)
def pre_str_unescape(node: ExprStringUnescape) -> str:
    prv, nxt = prev_next_var(node)
    # function Buildins.unescape(v)
    return f"local {nxt} = Buildins.unescape({prv})"


@CONVERTER(ExprListStringUnescape.kind)
def pre_list_str_unescape(node: ExprListStringUnescape) -> str:
    prv, nxt = prev_next_var(node)
    # function Buildins.unescape(v)
    return f"local {nxt} = Buildins.map({prv}, function(e) Buildins.unescape(e) end)"


@CONVERTER(ExprMapAttrs.kind)
def pre_map_attrs(node: ExprMapAttrs) -> str:
    prv, nxt = prev_next_var(node)
    # function CssExt.get_all_attr_values(el)
    return f"local {nxt} = CssExt.get_all_attr_values({prv}); "


@CONVERTER(ExprMapAttrsAll.kind)
def pre_map_attrs_all(node: ExprMapAttrsAll) -> str:
    prv, nxt = prev_next_var(node)
    # CssExt.flat_get_all_attr_values(els)
    return f"local {nxt} = CssExt.flat_get_all_attr_values({prv}); "


@CONVERTER(ExprCssElementRemove.kind)
def pre_css_remove(node: ExprCssElementRemove) -> str:
    prv, nxt = prev_next_var(node)
    query = lua_get_classvar_hook_or_value(node, "query")
    if node.classvar_hooks.get("query"):
        LOGGER.warning(WARNING_CSS_QUERY_MSG)
    else:
        # store current root nodes state
        code_select = css_query_to_lua_htmlparser_code(query, prv, nxt)
        # all CSS3 syntax supports
        if len(code_select) == 1:
            code = f"CssExt.remove({prv}, {query}); local {nxt} = {prv}"
        else:
            # select elements and remove from root
            # CssExt.remove_elements(node, elements)
            code = (
                f"local tmp_prv = {prv};"
                + "\n".join(code_select)
                + f"; CssExt.remove_elements(tmp_{prv}, {prv}); "
                + f" {nxt} = tmp_{prv}"
            )
    # set patched root as nxt var
    return code


@CONVERTER(ExprXpathElementRemove.kind)
def pre_xpath_remove(node: ExprXpathElementRemove) -> str:
    raise NotImplementedError("lua htmlparser not support xpath")


@CONVERTER(CodeEnd.kind)
def pre_code_end(node: CodeEnd) -> str:
    # https://www.lua.org/pil/15.2.html
    classes: list[StructParser] = [
        n for n in node.parent.body if n.kind == StructParser.kind
    ]
    names = [n.kwargs["name"] + "=" + n.kwargs["name"] for n in classes]
    return "return {" + ", ".join(names) + "}"


@CONVERTER(ExprJsonifyDynamic.kind)
def pre_jsonify_dynamic(node: ExprJsonifyDynamic) -> str:
    prv, nxt = prev_next_var(node)
    query = node.unpack_args()
    # lua index starts by 1, fix query
    expr = "".join(
        f"[{int(i) + 1}]" if i.isdigit() else f"[{i}]"
        for i in jsonify_query_parse(query)
    )

    return f"local {nxt} = json.decode({prv}){expr}; "
