"""Universal python expr codegen

Codegen notations:

- used legacy typing for support python 3.8 or higher
- generated types have `T_{schema_name}` names
- generated json types have `J_{json_schema_name}` names
- vars have prefix `v{index}`, start argument names as `v`

SPECIAL METHODS NOTATIONS:

- field_name : _parse_{field_name} (add prefix `_parse_` for every struct method parse)
- __KEY__ -> `key`, `_parse_key`
- __VALUE__: `value`, `_parse_value`
- "__ITEM__": `item`, `_parse_item`
- "__PRE_VALIDATE__": "_pre_validate",
- "__SPLIT_DOC__": "_split_doc",
- "__START_PARSE__": "parse",


TIP:

- for add new imports (parser backend), use post define TokenType.IMPORTS

REQUIRED IMPLEMENT expr:
- css, css_all, xpath, xpath_all,
- attr, attr_all,
- text, text_all,
- raw, raw_all,
- is_css, is_xpath
- optional: override init, parse_methods annotations
"""

from typing import cast

from typing_extensions import assert_never

from ssc_codegen.ast_ import (
    Docstring,
    ModuleImports,
    TypeDef,
    TypeDefField,
    JsonStruct,
    JsonStructField,
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
    ExprStringLeftTrim,
    ExprStringRightTrim,
    ExprListStringTrim,
    ExprListStringLeftTrim,
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
    ExprStringRmPrefix,
    ExprStringRmSuffix,
    ExprListStringRmSuffix,
    ExprStringRmPrefixAndSuffix,
    ExprListStringRmPrefixAndSuffix,
    ExprListStringAnyRegex,
    ExprListStringAllRegex,
)
from ssc_codegen.converters.base import (
    BaseCodeConverter,
    CB_FMT_DEBUG_COMMENT,
    debug_comment_cb,
)
from ssc_codegen.converters.helpers import (
    have_default_expr,
    have_pre_validate_call,
    prev_next_var,
    is_last_var_no_ret,
)
from ssc_codegen.tokens import StructType, VariableType, JsonVariableType

INDENT_CH = " "
INDENT_METHOD = INDENT_CH * 4
INDENT_METHOD_BODY = INDENT_CH * (4 * 2)
INDENT_DEFAULT_BODY = INDENT_CH * (4 * 3)
TYPE_PREFIX = "T_{}"
TYPE_DICT = "Dict[str, {}]"
TYPE_LIST = "List[{}]"
TYPE_ITEM = "TypedDict({}, {})"

TYPES = {
    VariableType.ANY: "Any",
    VariableType.STRING: "str",
    VariableType.LIST_STRING: "List[str]",
    VariableType.OPTIONAL_STRING: "Optional[str]",
    VariableType.OPTIONAL_LIST_STRING: "Optional[List[str]]",
    VariableType.OPTIONAL_INT: "Optional[int]",
    VariableType.OPTIONAL_LIST_INT: "Optional[List[int]]",
    VariableType.OPTIONAL_FLOAT: "Optional[float]",
    VariableType.OPTIONAL_LIST_FLOAT: "Optional[List[float]]",
    VariableType.INT: "int",
    VariableType.FLOAT: "float",
    VariableType.LIST_INT: "List[int]",
    VariableType.LIST_FLOAT: "List[float]",
    VariableType.BOOL: "bool",
}

JSON_TYPES = {
    JsonVariableType.BOOLEAN: "bool",
    JsonVariableType.STRING: "str",
    JsonVariableType.NUMBER: "int",
    JsonVariableType.FLOAT: "float",
    JsonVariableType.NULL: "NoneType",
    JsonVariableType.OPTIONAL_STRING: "Optional[str]",
    JsonVariableType.OPTIONAL_NUMBER: "Optional[int]",
    JsonVariableType.OPTIONAL_FLOAT: "Optional[float]",
    JsonVariableType.OPTIONAL_BOOLEAN: "Optional[bool]",
    JsonVariableType.ARRAY: "List",
    JsonVariableType.ARRAY_FLOAT: "List[float]",
    JsonVariableType.ARRAY_NUMBER: "List[int]",
    JsonVariableType.ARRAY_STRING: "List[str]",
    JsonVariableType.ARRAY_BOOLEAN: "List[bool]",
}

MAGIC_METHODS = {
    "__ITEM__": "item",
    "__KEY__": "key",
    "__VALUE__": "value",
}

# used old style typing for support old python versions (3.8)
IMPORTS_MIN = """
import re
import sys
import json
from typing import List, Dict, TypedDict, Union, Optional
from contextlib import suppress

if sys.version_info >= (3, 10):
    from types import NoneType
else:
    NoneType = type(None)
"""


class BasePyCodeConverter(BaseCodeConverter):
    def __init__(
        self,
        debug_instructions: bool = False,
        debug_comment_prefix: str = "# ",
        comment_prefix_sep: str = "\n",
        debug_cb: CB_FMT_DEBUG_COMMENT = debug_comment_cb,
    ) -> None:
        super().__init__(
            debug_instructions,
            debug_comment_prefix,
            comment_prefix_sep,
            debug_cb,
        )
        from ssc_codegen.ast_ import ExprListStringRmPrefix

        self.pre_definitions = {
            Docstring.kind: pre_docstring,
            ModuleImports.kind: pre_imports,
            TypeDef.kind: pre_typedef,
            TypeDefField.kind: pre_typedef_field,
            JsonStruct.kind: pre_json_struct,
            JsonStructField.kind: pre_json_field,
            StructParser.kind: pre_struct_parser,
            ExprReturn.kind: pre_ret,
            ExprNoReturn.kind: pre_no_ret,
            ExprNested.kind: pre_nested,
            StructPreValidateMethod.kind: pre_pre_validate,
            StructFieldMethod.kind: pre_parse_field,
            StartParseMethod.kind: pre_start_parse,
            StructInitMethod.kind: pre_struct_init,
            ExprDefaultValueStart.kind: pre_default_start,
            ExprDefaultValueEnd.kind: pre_default_end,
            ExprStringFormat.kind: pre_str_fmt,
            ExprListStringFormat.kind: pre_list_str_fmt,
            ExprStringTrim.kind: pre_str_trim,
            ExprStringLeftTrim.kind: pre_str_left_trim,
            ExprStringRightTrim.kind: pre_str_right_trim,
            ExprListStringTrim.kind: pre_list_str_trim,
            ExprListStringLeftTrim.kind: pre_list_str_left_trim,
            ExprListStringRightTrim.kind: pre_list_str_right_trim,
            ExprStringSplit.kind: pre_str_split,
            ExprStringReplace.kind: pre_str_replace,
            ExprListStringReplace.kind: pre_list_str_replace,
            ExprStringRegex.kind: pre_str_regex,
            ExprStringRegexAll.kind: pre_str_regex_all,
            ExprStringRegexSub.kind: pre_str_regex_sub,
            ExprListStringRegexSub.kind: pre_list_str_regex_sub,
            ExprStringRmPrefix.kind: pre_str_rm_prefix,
            ExprListStringRmPrefix.kind: pre_list_str_rm_prefix,
            ExprStringRmSuffix.kind: pre_str_rm_suffix,
            ExprListStringRmSuffix.kind: pre_list_str_rm_suffix,
            ExprStringRmPrefixAndSuffix.kind: pre_str_rm_prefix_and_suffix,
            ExprListStringRmPrefixAndSuffix.kind: pre_list_str_rm_prefix_and_suffix,
            ExprIndex.kind: pre_index,
            ExprListStringJoin.kind: pre_list_str_join,
            ExprIsEqual.kind: pre_is_equal,
            ExprIsNotEqual.kind: pre_is_not_equal,
            ExprIsContains.kind: pre_is_contains,
            ExprStringIsRegex.kind: pre_is_regex,
            ExprListStringAllRegex.kind: pre_list_str_all_is_regex,
            ExprListStringAnyRegex.kind: pre_list_str_any_is_regex,
            ExprToInt.kind: pre_to_int,
            ExprToListInt.kind: pre_to_list_int,
            ExprToFloat.kind: pre_to_float,
            ExprToListFloat.kind: pre_to_list_float,
            ExprToListLength.kind: pre_to_len,
            ExprToBool.kind: pre_to_bool,
            ExprJsonify.kind: pre_jsonify,
        }

        self.post_definitions = {
            TypeDef.kind: post_typedef,
            JsonStruct.kind: post_json_struct,
            StartParseMethod.kind: post_start_parse,
        }


def get_typedef_field_by_name(node: TypeDef, field_name: str) -> str:
    value = [i for i in node.body if i.kwargs["name"] == field_name][0]
    value = cast(TypeDefField, value)
    if value.kwargs["type"] == VariableType.NESTED:
        type_ = f"T_{value.kwargs['cls_nested']}"
        if value.kwargs["cls_nested_type"] == StructType.LIST:
            type_ = f"List[{type_}]"
    elif value.kwargs["type"] == VariableType.JSON:
        type_ = f"J_{value.kwargs['cls_nested']}"
        if value.kwargs["cls_nested_type"] == StructType.LIST:
            type_ = f"List[{type_}]"
    else:
        type_ = TYPES[value.kwargs["type"]]
    return type_


def get_field_method_ret_type(node: StructFieldMethod) -> str:
    last_expr = node.body[-1]
    match last_expr.ret_type:
        case VariableType.NESTED:
            last_expr = node.body[-2]
            last_expr = cast(ExprNested, last_expr)
            schema_name, schema_type = last_expr.unpack_args()
            type_ = f"T_{schema_name}"
            if schema_type == StructType.LIST:
                type_ = f"List[{type_}]"
        case VariableType.JSON:
            last_expr = node.body[-2]
            last_expr = cast(ExprJsonify, last_expr)
            json_struct_name, is_array = last_expr.unpack_args()
            type_ = f"J_{json_struct_name}"
            if is_array:
                type_ = f"List[{type_}]"
        case _:
            type_ = TYPES[last_expr.ret_type]
    return type_


def pre_docstring(node: Docstring) -> str:
    value, *_ = node.unpack_args()
    if value:
        return '"""' + value + '"""'
    return ""


def pre_imports(_node: ModuleImports) -> str:
    return IMPORTS_MIN


def pre_typedef(node: TypeDef) -> str:
    name, struct_type = node.unpack_args()
    match struct_type:
        case StructType.DICT:
            type_ = get_typedef_field_by_name(node, "__VALUE__")
            return f"T_{name} = Dict[str, {type_}]"
        case StructType.FLAT_LIST:
            type_ = get_typedef_field_by_name(node, "__ITEM__")
            return f"T_{name} = List[{type_}]"
        case StructType.ITEM | StructType.LIST:
            return f'T_{name} = TypedDict("T_{name}", ' + "{"
        case _:
            assert_never(struct_type)
    raise NotImplementedError()  # noqa


def post_typedef(node: TypeDef) -> str:
    _, struct_type = node.unpack_args()
    match struct_type:
        case StructType.DICT:
            return ""
        case StructType.FLAT_LIST:
            return ""
        # close TypedDict type
        case StructType.ITEM | StructType.LIST:
            return "})"
        case _:
            assert_never(struct_type)
    raise NotImplementedError()  # noqa


def pre_typedef_field(node: TypeDefField) -> str:
    name, var_type, cls_nested, cls_nested_type = node.unpack_args()
    node.parent = cast(TypeDef, node.parent)
    # skip generated types
    if node.parent.struct_type in (StructType.DICT, StructType.FLAT_LIST):
        return ""
    # always string
    elif name == "__KEY__":
        return ""
    elif var_type == VariableType.NESTED:
        type_ = f"T_{cls_nested}"
        if cls_nested_type == StructType.LIST:
            type_ = f"List[{type_}]"
    elif var_type == VariableType.JSON:
        type_ = f"J_{cls_nested}"
        if cls_nested_type == StructType.LIST:
            type_ = f"List[{type_}]"
    else:
        type_ = TYPES[var_type]
    return f"{name!r}: {type_},"


def pre_json_struct(node: JsonStruct) -> str:
    name = node.kwargs["name"]
    return f'J_{name} = TypedDict("J_{name}", ' + "{"


def post_json_struct(_node: JsonStruct) -> str:
    return "})"


def pre_json_field(node: JsonStructField) -> str:
    name, json_type = node.unpack_args()
    if json_type.type == JsonVariableType.OBJECT:
        type_ = f"J_{json_type.name}"
    elif json_type.type == JsonVariableType.ARRAY_OBJECTS:
        type_ = f"List[J_{json_type.name}]"
    else:
        type_ = JSON_TYPES[json_type.type]
    return f'"{node.name}": {type_}, '


def pre_struct_parser(node: StructParser) -> str:
    name, _struct_type, docstring = node.unpack_args()
    return f"class {name}:\n" + INDENT_METHOD + '"""' + docstring + '"""'


def pre_ret(node: ExprReturn) -> str:
    prv, _ = prev_next_var(node)
    expr = f"return {prv}"
    if have_default_expr(node):
        return INDENT_DEFAULT_BODY + expr
    return INDENT_METHOD_BODY + expr


def pre_no_ret(_node: ExprNoReturn) -> str:
    # used in __pre_validate__ case, ignore default wrap
    return INDENT_METHOD_BODY + "return"


def pre_nested(node: ExprNested) -> str:
    # not allowed default expr in nested
    prv, nxt = prev_next_var(node)
    schema_name, schema_type = node.unpack_args()

    return INDENT_METHOD_BODY + f"{nxt} = {schema_name}({prv}).parse()"


def pre_pre_validate(_node: StructPreValidateMethod) -> str:
    # __SPLIT_DOC__ = "_pre_validate()...)
    return INDENT_METHOD + "def _pre_validate(self, v):"


def pre_parse_field(node: StructFieldMethod) -> str:
    name = node.kwargs["name"]
    name = MAGIC_METHODS.get(name, name)
    type_ = get_field_method_ret_type(node)
    return INDENT_METHOD + f"def _parse_{name}(self, v) -> {type_}:"


def pre_start_parse(node: StartParseMethod) -> str:
    node.parent = cast(StructParser, node.parent)
    name = node.parent.kwargs["name"]
    st_type = node.parent.kwargs["struct_type"]
    type_ = f"T_{name}"
    if st_type == StructType.LIST:
        type_ = f"List[{type_}]"
    return INDENT_METHOD + f"def parse(self) -> {type_}:"


def pre_struct_init(_node: StructInitMethod) -> str:
    return (
        INDENT_METHOD
        + "def __init__(self, document):"
        + INDENT_METHOD_BODY
        + "self._document = document"
    )


def post_start_parse(node: StartParseMethod) -> str:
    node.parent = cast(StructParser, node.parent)
    code = ""
    if have_pre_validate_call(node):
        code += INDENT_METHOD_BODY + "self._pre_validate(self._document)\n"
    match node.parent.struct_type:
        case StructType.ITEM:
            # return {...}
            code += INDENT_METHOD_BODY + "return {"
            for expr in node.body:
                name = expr.kwargs["name"]
                if name.startswith("__"):
                    continue
                code += f"{name!r}: self._parse_{name}(self._document),"
            code += "}"
        case StructType.LIST:
            # return [{...} for el in self._split_doc(self.document)]
            code += INDENT_METHOD_BODY + "return [{"
            for expr in node.body:
                name = expr.kwargs["name"]
                if name.startswith("__"):
                    continue
                code += f"{name!r}: self._parse_{name}(el),"
            code += "} for el in self._split_doc(self._document)]"
        case StructType.DICT:
            # return {key: value, ...}
            code += (
                INDENT_METHOD_BODY
                + "return {self._parse_key(el): self._parse_value(el)"
                + " for el in self._split_doc(self._document)}"
            )
        case StructType.FLAT_LIST:
            # return [item, ...]
            code += (
                INDENT_METHOD_BODY
                + "return [self._parse_item(el) for el in self._split_doc(self._document)]"
            )
        case _:
            assert_never(node.parent.struct_type)  # type: ignore
    return code


# EXPRESSIONS


def pre_default_start(node: ExprDefaultValueStart) -> str:
    # HACK, for avoid recalc indexes use assign var trick
    prv, nxt = prev_next_var(node)
    return (
        INDENT_METHOD_BODY
        + f"{nxt} = {prv}"
        + "\n"
        + INDENT_METHOD_BODY
        + "with suppress(Exception):"
    )


def pre_default_end(node: ExprDefaultValueEnd) -> str:
    value = node.kwargs["value"]
    if isinstance(value, str):
        value = repr(value)
    elif isinstance(value, list):
        value = "[]"
    return INDENT_METHOD_BODY + f"return {value}"


def pre_str_fmt(node: ExprStringFormat) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    fmt = "f" + repr(node.kwargs["fmt"].replace("{{}}", "{" + prv + "}"))
    return indent + f"{nxt} = {fmt}"


def pre_list_str_fmt(node: ExprListStringFormat) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    fmt = "f" + repr(node.kwargs["fmt"].replace("{{}}", "{i}"))
    return indent + f"{nxt} = [{fmt} for i in {prv}]"


def pre_str_rm_prefix(node: ExprStringRmPrefix) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    substr = node.kwargs["substr"]
    return (
        indent
        + f"{nxt} = {prv}[len({substr!r}):] if {prv}.startswith({substr!r}) else {prv}"
    )


def pre_list_str_rm_prefix(node: ExprStringRmPrefix) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    substr = node.kwargs["substr"]
    return (
        indent
        + f"{nxt} = "
        + f"[i[len({substr!r}):] if i.startswith({substr!r}) else i "
        + f"for i in {prv}]"
    )


# NOTE: rm prefixes and rm suffixes use hacks with slices instead str.removeprefix() and str.removesuffix()
# for py3.8 compatibility
def pre_str_rm_suffix(node: ExprStringRmSuffix) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    substr = node.kwargs["substr"]
    return (
        indent
        + f"{nxt} = {prv}[:-(len({substr!r}))] if {prv}.endswith({substr!r}) else {prv}"
    )


def pre_list_str_rm_suffix(node: ExprListStringRmSuffix) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    substr = node.kwargs["substr"]
    return (
        indent
        + f"{nxt} = "
        + f"[i[:-(len({substr!r}))] if i.endswith({substr!r}) else i "
        + f"for i in {prv}]"
    )


def pre_str_rm_prefix_and_suffix(node: ExprStringRmPrefixAndSuffix) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    substr = node.kwargs["substr"]
    return (
        indent
        + f"{nxt} = ({prv}[len({substr!r}):] if {prv}.startswith({substr!r}) else {prv})"
        + f"[:-(len({substr!r}))] if {prv}.endswith({substr!r}) else {prv}"
    )


def pre_list_str_rm_prefix_and_suffix(
    node: ExprListStringRmPrefixAndSuffix,
) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    substr = node.kwargs["substr"]
    return (
        indent
        + f"{nxt} = [(i[len({substr!r}):] if i.startswith({substr!r}) else i)"
        + f"[:-(len({substr!r}))] if i.endswith({substr!r}) else i for i in {prv}"
        + "]"
    )


def pre_str_trim(node: ExprStringTrim) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    substr = node.kwargs["substr"]
    return indent + f"{nxt} = {prv}.strip({substr!r})"


def pre_list_str_trim(node: ExprListStringTrim) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    substr = node.kwargs["substr"]
    return indent + f"{nxt} = [i.strip({substr!r}) for i in {prv}]"


def pre_str_left_trim(node: ExprStringLeftTrim) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    substr = node.kwargs["substr"]
    return indent + f"{nxt} = {prv}.lstrip({substr!r})"


def pre_list_str_left_trim(node: ExprListStringLeftTrim) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    substr = node.kwargs["substr"]
    return indent + f"{nxt} = [i.lstrip({substr!r}) for i in {prv}]"


def pre_str_right_trim(node: ExprStringRightTrim) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    substr = node.kwargs["substr"]
    return indent + f"{nxt} = {prv}.rstrip({substr!r})"


def pre_list_str_right_trim(node: ExprListStringRightTrim) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    substr = node.kwargs["substr"]
    return indent + f"{nxt} = [i.rstrip({substr!r}) for i in {prv}]"


def pre_str_split(node: ExprStringSplit) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    sep = node.kwargs["sep"]
    return indent + f"{nxt} = {prv}.split({sep!r})"


def pre_str_replace(node: ExprStringReplace) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    old, new = node.unpack_args()
    return indent + f"{nxt} = {prv}.replace({old!r}, {new!r})"


def pre_list_str_replace(node: ExprListStringReplace) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    old, new = node.unpack_args()
    return indent + f"{nxt} = [i.replace({old!r}, {new!r}) for i in {prv}]"


def pre_str_regex(node: ExprStringRegex) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    pattern, group, ignore_case = node.unpack_args()
    if ignore_case:
        return (
            indent
            + f"{nxt} = re.search({pattern!r}, {prv}, re.IGNORECASE)[{group}]"
        )
    return indent + f"{nxt} = re.search({pattern!r}, {prv})[{group}]"


def pre_str_regex_all(node: ExprStringRegexAll) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    pattern, ignore_case = node.unpack_args()
    if ignore_case:
        return indent + f"{nxt} = re.findall({pattern!r}, {prv}, re.IGNORECASE)"
    return indent + f"{nxt} = re.findall({pattern!r}, {prv})"


def pre_str_regex_sub(node: ExprStringRegexSub) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    pattern, repl = node.unpack_args()
    return indent + f"{nxt} = re.sub({pattern!r}, {repl!r}, {prv})"


def pre_list_str_regex_sub(node: ExprListStringRegexSub) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    pattern, repl = node.unpack_args()
    return indent + f"{nxt} = [re.sub({pattern!r}, {repl!r}, i) for i in {prv}]"


def pre_index(node: ExprIndex) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    index, *_ = node.unpack_args()
    return indent + f"{nxt} = {prv}[{index}]"


def pre_list_str_join(node: ExprListStringJoin) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    sep = node.kwargs["sep"]
    return indent + f"{nxt} = {sep!r}.join({prv})"


def pre_is_equal(node: ExprIsEqual) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    item, msg = node.unpack_args()
    if isinstance(item, str):
        item = repr(item)
    expr = indent + f"assert {prv} != {item}, {msg!r}"
    if is_last_var_no_ret(node):
        return expr
    # HACK: avoid recalc variables
    return expr + "\n" + indent + f"{nxt} = {prv}"


def pre_is_not_equal(node: ExprIsNotEqual) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    item, msg = node.unpack_args()
    if isinstance(item, str):
        item = repr(item)
    expr = indent + f"assert {prv} == {item}, {msg!r}"
    if is_last_var_no_ret(node):
        return expr
    # HACK: avoid recalc variables
    return expr + "\n" + indent + f"{nxt} = {prv}"


def pre_is_contains(node: ExprIsContains) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    item, msg = node.unpack_args()
    if isinstance(item, str):
        item = repr(item)
    expr = indent + f"assert {item} not in {prv}, {msg!r}"
    if is_last_var_no_ret(node):
        return expr
    # HACK: avoid recalc variables
    return expr + "\n" + indent + f"{nxt} = {prv}"


def pre_is_regex(node: ExprStringIsRegex) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    pattern, ignore_case, msg = node.unpack_args()
    expr = indent + f"assert re.search({pattern!r}, {prv}), {msg!r}"
    if is_last_var_no_ret(node):
        return expr
    # HACK: avoid recalc variables
    return expr + "\n" + indent + f"{nxt} = {prv}"


def pre_list_str_any_is_regex(node: ExprListStringAnyRegex) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    pattern, ignore_case, msg = node.unpack_args()
    expr = (
        indent
        + f"assert any(re.search({pattern!r}, i) for i in {prv}), {msg!r}"
    )
    if is_last_var_no_ret(node):
        return expr
    # HACK: avoid recalc variables
    return expr + "\n" + indent + f"{nxt} = {prv}"


def pre_list_str_all_is_regex(node: ExprListStringAllRegex) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    pattern, ignore_case, msg = node.unpack_args()
    expr = (
        indent
        + f"assert all(re.search({pattern!r}, i) for i in {prv}), {msg!r}"
    )
    if is_last_var_no_ret(node):
        return expr
    # HACK: avoid recalc variables
    return expr + "\n" + indent + f"{nxt} = {prv}"


def pre_to_int(node: ExprToInt) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    return indent + f"{nxt} = int({prv})"


def pre_to_list_int(node: ExprToListInt) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    return indent + f"{nxt} = [int(i) for i in {prv}]"


def pre_to_float(node: ExprToFloat) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    return indent + f"{nxt} = float({prv})"


def pre_to_list_float(node: ExprToListFloat) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    return indent + f"{nxt} = [float(i) for i in {prv}]"


def pre_to_len(node: ExprToListLength) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    return indent + f"{nxt} = len({prv})"


def pre_to_bool(node: ExprToBool) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    return indent + f"{nxt} = bool({prv} or {prv} == 0)"


def pre_jsonify(node: ExprJsonify) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    _name, _is_array = node.unpack_args()
    return indent + f"{nxt} = json.loads({prv})"
