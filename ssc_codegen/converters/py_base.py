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
    FilterOr,
    FilterAnd,
    FilterNot,
    ExprFilter,
    FilterStrIn,
    FilterStrStarts,
    FilterStrEnds,
    FilterStrRe,
    FilterEqual,
    FilterNotEqual,
    FilterStrLenEq,
    FilterStrLenNe,
    FilterStrLenLt,
    FilterStrLenLe,
    FilterStrLenGt,
    FilterStrLenGe,
    ExprListUnique,
    ExprStringMapReplace,
    ExprListStringMapReplace,
    ExprListStringRmPrefix,
    ExprListStringUnescape,
    ExprStringUnescape,
    ExprClassVar,
    ExprJsonifyDynamic,
)

from ssc_codegen.converters.base import (
    BaseCodeConverter,
    CB_FMT_DEBUG_COMMENT,
    debug_comment_cb,
)
from ssc_codegen.converters.helpers import (
    have_default_expr,
    have_pre_validate_call,
    jsonify_query_parse,
    prev_next_var,
    is_last_var_no_ret,
    is_prev_node_atomic_cond,
    is_first_node_cond,
    py_get_classvar_hook_or_value,
    py_regex_flags,
)
from ssc_codegen.json_struct import JsonType
from ssc_codegen.tokens import (
    StructType,
    TokenType,
    VariableType,
    JsonVariableType,
)
from ssc_codegen.converters.templates.py_base import (
    HELPER_FUNCTIONS,
    IMPORTS_MIN,
)

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

LITERAL_TYPES = {
    list: "ClassVar[list]",
    int: "ClassVar[int]",
    bool: "ClassVar[bool]",
    float: "ClassVar[float]",
    str: "ClassVar[str]",
}

MAGIC_METHODS = {
    "__ITEM__": "item",
    "__KEY__": "key",
    "__VALUE__": "value",
}


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

        self.pre_definitions = {
            Docstring.kind: pre_docstring,
            ModuleImports.kind: pre_imports,
            TypeDefField.kind: pre_typedef_field,
            JsonStruct.kind: pre_json_struct,
            JsonStructField.kind: pre_json_field,
            StructParser.kind: pre_struct_parser,
            ExprClassVar.kind: pre_expr_classvar,
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
            ExprJsonifyDynamic.kind: pre_to_json_dynamic,
            # FILTER,
            ExprFilter.kind: pre_expr_filter,
            FilterAnd.kind: pre_filter_and,
            FilterOr.kind: pre_filter_or,
            FilterNot.kind: pre_filter_not,
            FilterStrStarts.kind: pre_filter_starts_with,
            FilterStrEnds.kind: pre_filter_ends_with,
            FilterStrIn.kind: pre_filter_in,
            FilterStrRe.kind: pre_filter_re,
            FilterEqual.kind: pre_filter_eq,
            FilterNotEqual.kind: pre_filter_ne,
            FilterStrLenEq.kind: pre_filter_str_len_eq,
            FilterStrLenNe.kind: pre_filter_str_len_ne,
            FilterStrLenLt.kind: pre_filter_str_len_lt,
            FilterStrLenLe.kind: pre_filter_str_len_le,
            FilterStrLenGe.kind: pre_filter_str_len_ge,
            FilterStrLenGt.kind: pre_filter_str_len_gt,
            ExprListUnique.kind: pre_list_unique,
            ExprStringMapReplace.kind: pre_str_map_replace,
            ExprListStringMapReplace.kind: pre_list_str_map_replace,
            ExprStringUnescape.kind: pre_str_unescape,
            ExprListStringUnescape.kind: pre_list_str_unescape,
            # shortcut structures:
            (TypeDef.kind, StructType.ITEM): pre_typedef_item,
            (TypeDef.kind, StructType.LIST): pre_typedef_list,
            (TypeDef.kind, StructType.DICT): pre_typedef_dict,
            (TypeDef.kind, StructType.FLAT_LIST): pre_typedef_flat_list,
            (TypeDef.kind, StructType.ACC_LIST): pre_typedef_acc_list,
        }

        self.post_definitions = {
            ModuleImports.kind: post_imports,
            JsonStruct.kind: post_json_struct,
            ExprFilter.kind: post_expr_filter,
            FilterAnd.kind: post_filter_and,
            FilterOr.kind: post_filter_or,
            FilterNot.kind: post_filter_not,
            # shortcuts parsers
            (StartParseMethod.kind, StructType.ITEM): post_start_parse_item,
            (StartParseMethod.kind, StructType.LIST): post_start_parse_list,
            (StartParseMethod.kind, StructType.DICT): post_start_parse_dict,
            (
                StartParseMethod.kind,
                StructType.FLAT_LIST,
            ): post_start_parse_flat_list,
            (
                StartParseMethod.kind,
                StructType.ACC_LIST,
            ): post_start_parse_acc_list,
            (TypeDef.kind, StructType.ITEM): post_typedef_item,
            (TypeDef.kind, StructType.LIST): post_typedef_list,
            (TypeDef.kind, StructType.DICT): post_typedef_dict,
            (TypeDef.kind, StructType.FLAT_LIST): post_typedef_flat_list,
            (TypeDef.kind, StructType.ACC_LIST): post_typedef_acc_list,
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
            json_struct_name, is_array, *_ = last_expr.unpack_args()
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


def post_imports(_: ModuleImports) -> str:
    return HELPER_FUNCTIONS


# TYPEDEF
def pre_typedef_item(node: TypeDef) -> str:
    name, _ = node.unpack_args()
    return f'T_{name} = TypedDict("T_{name}", ' + "{"


def post_typedef_item(_: TypeDef) -> str:
    return "})"


def pre_typedef_list(node: TypeDef) -> str:
    name, _ = node.unpack_args()
    return f'T_{name} = TypedDict("T_{name}", ' + "{"


def post_typedef_list(_: TypeDef) -> str:
    return "})"


def pre_typedef_dict(node: TypeDef) -> str:
    name, _ = node.unpack_args()
    type_ = get_typedef_field_by_name(node, "__VALUE__")
    return f"T_{name} = Dict[str, {type_}]"


def post_typedef_dict(_: TypeDef) -> str:
    return ""


def pre_typedef_flat_list(node: TypeDef) -> str:
    name, _ = node.unpack_args()
    type_ = get_typedef_field_by_name(node, "__VALUE__")
    return f"T_{name} = List[{type_}]"


def post_typedef_flat_list(_: TypeDef) -> str:
    return ""


def pre_typedef_acc_list(node: TypeDef) -> str:
    name, _ = node.unpack_args()
    return f"T_{name} = List[str]"


def post_typedef_acc_list(_: TypeDef) -> str:
    return ""


def pre_typedef_field(node: TypeDefField) -> str:
    name, var_type, cls_nested, cls_nested_type = node.unpack_args()
    node.parent = cast(TypeDef, node.parent)
    # skip generated types
    if node.parent.struct_type in (
        StructType.DICT,
        StructType.FLAT_LIST,
        StructType.ACC_LIST,
    ):
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


# END TYPEDEF


def pre_json_struct(node: JsonStruct) -> str:
    name = node.kwargs["name"]
    return f'J_{name} = TypedDict("J_{name}", ' + "{"


def post_json_struct(_node: JsonStruct) -> str:
    return "})"


def pre_json_field(node: JsonStructField) -> str:
    name, json_type = node.unpack_args()
    json_type: JsonType
    if json_type.type == JsonVariableType.OBJECT:
        type_ = f"J_{json_type.name}"
    elif json_type.type == JsonVariableType.ARRAY_OBJECTS:
        type_ = f"List[J_{json_type.name}]"
    else:
        type_ = JSON_TYPES[json_type.type]

    return f'"{json_type.get_mapped_field()}": {type_}, '


def pre_struct_parser(node: StructParser) -> str:
    name, _struct_type, docstring = node.unpack_args()
    return f"class {name}:\n" + INDENT_METHOD + '"""' + docstring + '"""'


def pre_expr_classvar(node: ExprClassVar) -> str:
    value, _st_name, field_name, *_ = node.unpack_args()
    if isinstance(value, str):
        # ExprStringFormat template
        if "{{}}" in value:
            value = value.replace("{{}}", "{}")
        value = repr(value)
    # classvar type add
    type_ = LITERAL_TYPES.get(type(value))
    return f"{INDENT_METHOD}{field_name}: {type_} = {value}"


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
    schema_name, _schema_type = node.unpack_args()

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


# START_PARSE
def post_start_parse_item(node: StartParseMethod) -> str:
    code = ""
    if have_pre_validate_call(node):
        code += INDENT_METHOD_BODY + "self._pre_validate(self._document)\n"
    code += INDENT_METHOD_BODY + "return {"
    for expr in node.body:
        if expr.kind == TokenType.STRUCT_CALL_FUNCTION:
            name = expr.kwargs["name"]
            if name.startswith("__"):
                continue
            code += f"{name!r}: self._parse_{name}(self._document),"
        elif expr.kind == TokenType.STRUCT_CALL_CLASSVAR:
            # {"struct_name": str, "field_name": str, "type": VariableType},
            st_name, f_name, _ = expr.unpack_args()
            code += f"{f_name!r}: {st_name}.{f_name},"
    code += "}"
    return code


def post_start_parse_list(node: StartParseMethod) -> str:
    code = ""
    if have_pre_validate_call(node):
        code += INDENT_METHOD_BODY + "self._pre_validate(self._document)\n"
    # return [{...} for el in self._split_doc(self.document)]
    code += INDENT_METHOD_BODY + "return [{"
    for expr in node.body:
        if expr.kind == TokenType.STRUCT_CALL_FUNCTION:
            name = expr.kwargs["name"]
            if name.startswith("__"):
                continue
            code += f"{name!r}: self._parse_{name}(el),"
        elif expr.kind == TokenType.STRUCT_CALL_CLASSVAR:
            # {"struct_name": str, "field_name": str, "type": VariableType},
            st_name, f_name, _ = expr.unpack_args()
            code += f"{f_name!r}: {st_name}.{f_name},"
    code += "} for el in self._split_doc(self._document)]"
    return code


def post_start_parse_acc_list(node: StartParseMethod) -> str:
    code = ""
    if have_pre_validate_call(node):
        code += INDENT_METHOD_BODY + "self._pre_validate(self._document)\n"
    code += INDENT_METHOD_BODY + "return list(set("
    methods = []
    for expr in node.body:
        name = expr.kwargs["name"]
        if name.startswith("__"):
            continue
        # acc list of str (all list are flatten)
        methods.append(f"self._parse_{name}(self._document)")
    code += " + ".join(methods)
    code += "))"
    return code


def post_start_parse_dict(node: StartParseMethod) -> str:
    code = ""
    if have_pre_validate_call(node):
        code += INDENT_METHOD_BODY + "self._pre_validate(self._document)\n"
    code += (
        INDENT_METHOD_BODY
        + "return {self._parse_key(el): self._parse_value(el)"
        + " for el in self._split_doc(self._document)}"
    )
    return code


def post_start_parse_flat_list(node: StartParseMethod) -> str:
    code = ""
    if have_pre_validate_call(node):
        code += INDENT_METHOD_BODY + "self._pre_validate(self._document)\n"
    # return [item, ...]
    code += (
        INDENT_METHOD_BODY
        + "return [self._parse_item(el) for el in self._split_doc(self._document)]"
    )
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
    value = py_get_classvar_hook_or_value(node, "value")
    return INDENT_METHOD_BODY + f"return {value}"


def pre_str_fmt(node: ExprStringFormat) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    fmt = py_get_classvar_hook_or_value(
        node,
        "fmt",
        # literal value already patched `{{}}` to `{}`
        cb_literal_cast=lambda e: ".".join(e.literal_ref_name)
        + f".format({prv})",
        cb_value_cast=lambda i: "f" + repr(i.replace("{{}}", "{" + prv + "}")),
    )
    return indent + f"{nxt} = {fmt}"


def pre_list_str_fmt(node: ExprListStringFormat) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    fmt = py_get_classvar_hook_or_value(
        node,
        "fmt",
        cb_literal_cast=lambda e: ".".join(e.literal_ref_name) + ".format(i)",
        cb_value_cast=lambda i: "f" + repr(i.replace("{{}}", "{i}")),
    )

    return indent + f"{nxt} = [{fmt} for i in {prv}]"


# NOTE: rm prefixes and rm suffixes use hacks with slices instead str.removeprefix() and str.removesuffix()
# for py3.8 compatibility
def pre_str_rm_prefix(node: ExprStringRmPrefix) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    substr = py_get_classvar_hook_or_value(node, "substr")

    return indent + f"{nxt} = ssc_rm_prefix({prv}, {substr})"


def pre_list_str_rm_prefix(node: ExprStringRmPrefix) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    substr = py_get_classvar_hook_or_value(node, "substr")

    # def ssc_rm_prefix(v: str, p: str) -> str:
    return f"{indent}{nxt} = [ssc_rm_prefix(i, {substr}) for i in {prv}]"


def pre_str_rm_suffix(node: ExprStringRmSuffix) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    substr = py_get_classvar_hook_or_value(node, "substr")

    return f"{indent}{nxt} = ssc_rm_suffix({prv}, {substr})"


def pre_list_str_rm_suffix(node: ExprListStringRmSuffix) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    substr = py_get_classvar_hook_or_value(node, "substr")

    # def ssc_rm_suffix(v: str, s: str) -> str:
    return f"{indent}{nxt} = [ssc_rm_suffix(i, {substr}) for i in {prv}]"


def pre_str_rm_prefix_and_suffix(node: ExprStringRmPrefixAndSuffix) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    substr = py_get_classvar_hook_or_value(node, "substr")

    # def ssc_rm_prefix_and_suffix(v: str, p: str, s: str)
    return (
        f"{indent}{nxt} = ssc_rm_prefix_and_suffix({prv}, {substr}, {substr})"
    )


def pre_list_str_rm_prefix_and_suffix(
    node: ExprListStringRmPrefixAndSuffix,
) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    substr = py_get_classvar_hook_or_value(node, "substr")

    # def ssc_rm_prefix_and_suffix(v: str, p: str, s: str)
    return f"{indent}{nxt} = [ssc_rm_prefix_and_suffix(i, {substr}, {substr}) for i in {prv}]"


def pre_str_trim(node: ExprStringTrim) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    substr = py_get_classvar_hook_or_value(node, "substr")

    return indent + f"{nxt} = {prv}.strip({substr})"


def pre_list_str_trim(node: ExprListStringTrim) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    substr = py_get_classvar_hook_or_value(node, "substr")

    return indent + f"{nxt} = [i.strip({substr}) for i in {prv}]"


def pre_str_left_trim(node: ExprStringLeftTrim) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    substr = py_get_classvar_hook_or_value(node, "substr")

    return indent + f"{nxt} = {prv}.lstrip({substr})"


def pre_list_str_left_trim(node: ExprListStringLeftTrim) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    substr = py_get_classvar_hook_or_value(node, "substr")

    return indent + f"{nxt} = [i.lstrip({substr}) for i in {prv}]"


def pre_str_right_trim(node: ExprStringRightTrim) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    substr = py_get_classvar_hook_or_value(node, "substr")

    return indent + f"{nxt} = {prv}.rstrip({substr})"


def pre_list_str_right_trim(node: ExprListStringRightTrim) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    substr = py_get_classvar_hook_or_value(node, "substr")

    return indent + f"{nxt} = [i.rstrip({substr}) for i in {prv}]"


def pre_str_split(node: ExprStringSplit) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    sep = py_get_classvar_hook_or_value(node, "sep")

    return indent + f"{nxt} = {prv}.split({sep})"


def pre_str_replace(node: ExprStringReplace) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    old = py_get_classvar_hook_or_value(node, "old")
    new = py_get_classvar_hook_or_value(node, "new")

    return indent + f"{nxt} = {prv}.replace({old}, {new})"


def pre_list_str_replace(node: ExprListStringReplace) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    old = py_get_classvar_hook_or_value(node, "old")
    new = py_get_classvar_hook_or_value(node, "new")

    return indent + f"{nxt} = [i.replace({old}, {new}) for i in {prv}]"


def pre_str_regex(node: ExprStringRegex) -> str:
    # FIXME issues:
    # regex throw error in parsel exprs
    # https://github.com/libanime/libanime_schema/blob/main/player/kodik.py#L216
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    pattern, group, ignore_case, dotall = node.unpack_args()
    if node.classvar_hooks:
        pattern = py_get_classvar_hook_or_value(node, "pattern")
        return indent + f"re.search({pattern}, {prv})[{group}]"
    flags = py_regex_flags(ignore_case, dotall)
    if flags:
        return (
            indent + f"{nxt} = re.search({pattern!r}, {prv}, {flags})[{group}]"
        )
    return indent + f"{nxt} = re.search({pattern!r}, {prv})[{group}]"


def pre_str_regex_all(node: ExprStringRegexAll) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    pattern, ignore_case, dotall = node.unpack_args()
    if node.classvar_hooks:
        pattern = py_get_classvar_hook_or_value(node, "pattern")
        return indent + f"re.findall({pattern}, {prv})"
    flags = py_regex_flags(ignore_case, dotall)
    if flags:
        return indent + f"{nxt} = re.findall({pattern!r}, {prv}, {flags})"
    return indent + f"{nxt} = re.findall({pattern!r}, {prv})"


def pre_str_regex_sub(node: ExprStringRegexSub) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    pattern, repl, ignore_case, dotall = node.unpack_args()
    if node.classvar_hooks.get("pattern"):
        pattern = py_get_classvar_hook_or_value(node, "pattern")
        if node.classvar_hooks.get("repl"):
            repl = py_get_classvar_hook_or_value(node, "repl")
        else:
            repl = repr(repl)
        return indent + f"{nxt}" + f"re.sub({pattern}, {repl}, {prv})"
    else:
        flags = py_regex_flags(ignore_case, dotall)
        if flags:
            return (
                indent
                + f"{nxt} = re.sub({pattern!r}, {repl!r}, {prv}, {flags})"
            )
        return indent + f"{nxt} = re.sub({pattern!r}, {repl!r}, {prv})"


def pre_list_str_regex_sub(node: ExprListStringRegexSub) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    pattern, repl, ignore_case, dotall = node.unpack_args()
    if node.classvar_hooks.get("pattern"):
        pattern = py_get_classvar_hook_or_value(node, "pattern")
        if node.classvar_hooks.get("repl"):
            repl = py_get_classvar_hook_or_value(node, "repl")
        else:
            repl = repr(repl)
        return (
            indent + f"{nxt} = [re.sub({pattern}), {repl}, i) for i in {prv}]"
        )
    flags = py_regex_flags(ignore_case, dotall)
    if flags:
        return (
            indent
            + f"{nxt} = [re.sub({pattern!r}, {repl!r}, i, {flags}) for i in {prv}]"
        )
    return indent + f"{nxt} = [re.sub({pattern!r}, {repl!r}, i) for i in {prv}]"


def pre_index(node: ExprIndex) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    index, *_ = node.unpack_args()
    index = py_get_classvar_hook_or_value(node, "index")
    return indent + f"{nxt} = {prv}[{index}]"


def pre_list_str_join(node: ExprListStringJoin) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    sep = py_get_classvar_hook_or_value(node, "sep")
    return indent + f"{nxt} = {sep}.join({prv})"


def pre_is_equal(node: ExprIsEqual) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    item, msg = node.unpack_args()
    item = py_get_classvar_hook_or_value(node, "item")
    msg = py_get_classvar_hook_or_value(node, "msg")

    expr = indent + f"assert {prv} != {item}, {msg}"
    if is_last_var_no_ret(node):
        return expr
    return expr + "\n" + indent + f"{nxt} = {prv}"


def pre_is_not_equal(node: ExprIsNotEqual) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    item, msg = node.unpack_args()
    item = py_get_classvar_hook_or_value(node, "item")
    msg = py_get_classvar_hook_or_value(node, "msg")

    expr = indent + f"assert {prv} == {item}, {msg}"
    if is_last_var_no_ret(node):
        return expr
    return expr + "\n" + indent + f"{nxt} = {prv}"


def pre_is_contains(node: ExprIsContains) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    item, msg = node.unpack_args()

    item = py_get_classvar_hook_or_value(node, "item")
    msg = py_get_classvar_hook_or_value(node, "msg")

    expr = indent + f"assert {item} not in {prv}, {msg!r}"
    if is_last_var_no_ret(node):
        return expr
    return expr + "\n" + indent + f"{nxt} = {prv}"


def pre_is_regex(node: ExprStringIsRegex) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    pattern, ignore_case, msg = node.unpack_args()

    msg = py_get_classvar_hook_or_value(node, "msg")

    if node.classvar_hooks.get("pattern"):
        pattern = py_get_classvar_hook_or_value(node, "pattern")
        expr = f"re.search({pattern}, {prv})"
    else:
        flags = py_regex_flags(ignore_case)
        if flags:
            expr = f"re.search({pattern!r}, {prv}, re.I)"
        else:
            expr = f"re.search({pattern!r}, {prv})"

    expr = indent + f"assert {expr}, {msg}"
    if is_last_var_no_ret(node):
        return expr
    return expr + "\n" + indent + f"{nxt} = {prv}"


def pre_list_str_any_is_regex(node: ExprListStringAnyRegex) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    pattern, ignore_case, msg = node.unpack_args()

    if node.classvar_hooks.get("pattern"):
        pattern = py_get_classvar_hook_or_value(node, "pattern")
        expr = f"re.search({pattern}, i)"
    else:
        flags = py_regex_flags(ignore_case)
        if flags:
            expr = f"re.search({pattern!r}, i, re.I)"
        else:
            expr = f"re.search({pattern!r}, i)"

    expr = indent + f"assert any({expr} for i in {prv}), {msg!r}"
    if is_last_var_no_ret(node):
        return expr
    return expr + "\n" + indent + f"{nxt} = {prv}"


def pre_list_str_all_is_regex(node: ExprListStringAllRegex) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    pattern, ignore_case, msg = node.unpack_args()

    if node.classvar_hooks.get("pattern"):
        pattern = py_get_classvar_hook_or_value(node, "pattern")
        expr = f"re.search({pattern}, i)"
    else:
        flags = py_regex_flags(ignore_case)
        if flags:
            expr = f"re.search({pattern!r}, i, re.I)"
        else:
            expr = f"re.search({pattern!r}, i)"

    expr = indent + f"assert all({expr} for i in {prv}), {msg!r}"
    if is_last_var_no_ret(node):
        return expr
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
    _name, _is_array, query = node.unpack_args()
    expr = "".join(f"[{i}]" for i in jsonify_query_parse(query))
    return indent + f"{nxt} = json.loads({prv}){expr}"


# FILTERS


def pre_expr_filter(node: ExprFilter) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    return indent + f"{nxt} = [i for i in {prv} if "


def post_expr_filter(_node: ExprFilter) -> str:
    return "]"


def pre_filter_or(_node: FilterOr) -> str:
    return " or ("


def post_filter_or(_node: FilterOr) -> str:
    return ")"


def pre_filter_and(_node: FilterAnd) -> str:
    return " and ("


def post_filter_and(_node: FilterAnd) -> str:
    return ")"


def pre_filter_not(_node: FilterNot) -> str:
    return "not ("


def post_filter_not(_node: FilterNot) -> str:
    return ")"


def pre_filter_in(node: FilterStrIn) -> str:
    values, *_ = node.unpack_args()

    if len(values) == 1:
        expr = f"{values[0]!r} in i"
    else:
        expr = f"any(s in i for s in {values})"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" and {expr}"
    return expr


def pre_filter_starts_with(node: FilterStrStarts) -> str:
    start_, *_ = node.unpack_args()
    # build-in python startswith accept tuple[str, ...]
    expr = f"i.startswith({start_})"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" and {expr}"
    return expr


def pre_filter_ends_with(node: FilterStrEnds) -> str:
    suffix_, *_ = node.unpack_args()
    # build-in python endswith accept tuple[str, ...]
    expr = f"i.endswith({suffix_})"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" and {expr}"
    return expr


def pre_filter_re(node: FilterStrRe) -> str:
    pattern, ignore_case, *_ = node.unpack_args()
    if ignore_case:
        expr = f"re.search({pattern!r}, i, re.IGNORECASE)"
    else:
        expr = f"re.search({pattern!r}, i)"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" and {expr}"
    return expr


def pre_filter_eq(node: FilterEqual) -> str:
    values, *_ = node.unpack_args()
    # currently support only str
    if len(values) == 1:
        expr = f"i == {values[0]!r}"
    else:
        expr = f"any(s == i for s in {values})"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" and {expr}"
    return expr


def pre_filter_ne(node: FilterNotEqual) -> str:
    values, *_ = node.unpack_args()
    # currently support only str
    if len(values) == 1:
        expr = f"i != {values[0]!r}"
    else:
        expr = f"all(s != i for s in {values})"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" and {expr}"
    return expr


def pre_filter_str_len_eq(node: FilterStrLenEq) -> str:
    length, *_ = node.unpack_args()
    expr = f"len(i) == {length}"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" and {expr}"
    return expr


def pre_filter_str_len_ne(node: FilterStrLenNe) -> str:
    length, *_ = node.unpack_args()
    expr = f"len(i) != {length}"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" and {expr}"
    return expr


def pre_filter_str_len_lt(node: FilterStrLenLt) -> str:
    length, *_ = node.unpack_args()
    expr = f"len(i) < {length}"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" and {expr}"
    return expr


def pre_filter_str_len_le(node: FilterStrLenLe) -> str:
    length, *_ = node.unpack_args()
    expr = f"len(i) <= {length}"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" and {expr}"
    return expr


def pre_filter_str_len_gt(node: FilterStrLenGt) -> str:
    length, *_ = node.unpack_args()
    expr = f"len(i) > {length}"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" and {expr}"
    return expr


def pre_filter_str_len_ge(node: FilterStrLenGe) -> str:
    length, *_ = node.unpack_args()
    expr = f"len(i) >= {length}"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" and {expr}"
    return expr


def pre_list_unique(node: ExprListUnique) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    keep_order, *_ = node.unpack_args()
    prv, nxt = prev_next_var(node)
    if keep_order:
        # py 3.7+ dicts order elements guaranteed
        return f"{indent}{nxt} = list(dict.fromkeys({prv}))"
    return f"{indent}{nxt} = list(set({prv}))"


def pre_str_map_replace(node: ExprStringMapReplace) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    old_arr, new_arr = node.unpack_args()
    replacements = dict(zip(old_arr, new_arr))

    prv, nxt = prev_next_var(node)
    # ssc_map_replace(s: str, replacements: Dict[str, str]) -> str
    return f"{indent}{nxt} = ssc_map_replace({prv}, {replacements})"


def pre_list_str_map_replace(node: ExprListStringMapReplace) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    old_arr, new_arr = node.unpack_args()
    replacements = dict(zip(old_arr, new_arr))

    prv, nxt = prev_next_var(node)
    # ssc_map_replace(s: str, replacements: Dict[str, str]) -> str
    return (
        f"{indent}{nxt} = [ssc_map_replace(i, {replacements}) for i in {prv}]"
    )


def pre_str_unescape(node: ExprStringUnescape) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    # ssc_unescape(s: str) -> str
    return f"{indent}{nxt} = ssc_unescape({prv})"


def pre_list_str_unescape(node: ExprListStringUnescape) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    # ssc_unescape(s: str) -> str
    return f"{indent}{nxt} = [ssc_unescape(i) for i in {prv}]"


def pre_to_json_dynamic(node: ExprJsonifyDynamic) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    query = node.unpack_args()

    expr = "".join(f"[{i}]" for i in jsonify_query_parse(query))

    return f"{indent}{nxt} = json.loads({prv}){expr}"
