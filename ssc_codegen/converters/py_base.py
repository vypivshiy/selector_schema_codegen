"""base universal python codegen api"""

from functools import partial

from ..ast_ssc import (
    DefaultEnd,
    DefaultStart,
    Docstring,
    FormatExpression,
    IndexDocumentExpression,
    IndexStringExpression,
    IsContainsExpression,
    IsEqualExpression,
    IsNotEqualExpression,
    IsRegexMatchExpression,
    JoinExpression,
    LTrimExpression,
    MapFormatExpression,
    MapLTrimExpression,
    MapRegexSubExpression,
    MapReplaceExpression,
    MapRTrimExpression,
    MapTrimExpression,
    ModuleImports,
    NestedExpression,
    NoReturnExpression,
    PreValidateFunction,
    RegexAllExpression,
    RegexExpression,
    RegexSubExpression,
    ReplaceExpression,
    ReturnExpression,
    RTrimExpression,
    SplitExpression,
    StartParseFunction,
    StructParser,
    ToFloat,
    ToInteger,
    ToListFloat,
    ToListInteger,
    TrimExpression,
    TypeDef,
    TypeDefField,
)
from ..tokens import StructType, TokenType, VariableType
from .base import BaseCodeConverter, left_right_var_names
from .templates import py

lr_var_names = partial(left_right_var_names, name="value")

MAGIC_METHODS = py.MAGIC_METHODS_NAME


class BasePyCodeConverter(BaseCodeConverter):
    def __init__(self) -> None:
        super().__init__()
        # TODO link converters
        self.pre_definitions[TokenType.IMPORTS] = tt_imports
        self.pre_definitions[TokenType.TYPEDEF] = tt_typedef
        self.pre_definitions[TokenType.STRUCT] = tt_struct
        self.pre_definitions[TokenType.DOCSTRING] = tt_docstring
        self.pre_definitions[TokenType.EXPR_RETURN] = tt_ret
        self.pre_definitions[TokenType.EXPR_NO_RETURN] = tt_no_ret
        self.pre_definitions[TokenType.EXPR_NESTED] = tt_nested
        self.pre_definitions[TokenType.STRUCT_PRE_VALIDATE] = tt_pre_validate
        self.pre_definitions[TokenType.STRUCT_PARSE_START] = tt_start_parse_pre
        self.post_definitions[TokenType.STRUCT_PARSE_START] = (
            tt_start_parse_post
        )

        self.pre_definitions[TokenType.EXPR_DEFAULT_START] = tt_default_start
        self.pre_definitions[TokenType.EXPR_DEFAULT_END] = tt_default_end

        self.pre_definitions[TokenType.EXPR_STRING_FORMAT] = tt_string_format
        self.pre_definitions[TokenType.EXPR_LIST_STRING_FORMAT] = (
            tt_string_format_all
        )
        self.pre_definitions[TokenType.EXPR_STRING_TRIM] = tt_string_trim
        self.pre_definitions[TokenType.EXPR_LIST_STRING_TRIM] = (
            tt_string_trim_all
        )
        self.pre_definitions[TokenType.EXPR_STRING_TRIM] = tt_string_trim
        self.pre_definitions[TokenType.EXPR_LIST_STRING_TRIM] = (
            tt_string_trim_all
        )
        self.pre_definitions[TokenType.EXPR_STRING_LTRIM] = tt_string_ltrim
        self.pre_definitions[TokenType.EXPR_LIST_STRING_LTRIM] = (
            tt_string_ltrim_all
        )
        self.pre_definitions[TokenType.EXPR_STRING_RTRIM] = tt_string_rtrim
        self.pre_definitions[TokenType.EXPR_LIST_STRING_RTRIM] = (
            tt_string_rtrim_all
        )
        self.pre_definitions[TokenType.EXPR_STRING_REPLACE] = tt_string_replace
        self.pre_definitions[TokenType.EXPR_LIST_STRING_REPLACE] = (
            tt_string_replace_all
        )
        self.pre_definitions[TokenType.EXPR_STRING_SPLIT] = tt_string_split
        self.pre_definitions[TokenType.EXPR_REGEX] = tt_regex
        self.pre_definitions[TokenType.EXPR_REGEX_ALL] = tt_regex_all
        self.pre_definitions[TokenType.EXPR_REGEX_SUB] = tt_regex_sub
        self.pre_definitions[TokenType.EXPR_LIST_REGEX_SUB] = tt_regex_sub_all
        self.pre_definitions[TokenType.EXPR_LIST_STRING_INDEX] = tt_index
        self.pre_definitions[TokenType.EXPR_LIST_DOCUMENT_INDEX] = tt_index
        self.pre_definitions[TokenType.EXPR_LIST_JOIN] = tt_join
        self.pre_definitions[TokenType.IS_EQUAL] = tt_is_equal
        self.pre_definitions[TokenType.IS_NOT_EQUAL] = tt_is_not_equal
        self.pre_definitions[TokenType.IS_CONTAINS] = tt_is_contains
        self.pre_definitions[TokenType.IS_REGEX_MATCH] = tt_is_regex

        self.pre_definitions[TokenType.TO_INT] = tt_to_int
        self.pre_definitions[TokenType.TO_INT_LIST] = tt_to_list_int
        self.pre_definitions[TokenType.TO_FLOAT] = tt_to_float
        self.pre_definitions[TokenType.TO_FLOAT_LIST] = tt_to_list_float


def tt_imports(node: ModuleImports) -> str:
    return py.BINDINGS[node.kind]


def tt_typedef(node: TypeDef) -> str:
    def _fetch_node_type(node_: TypeDefField) -> str:
        if node_.ret_type == VariableType.NESTED:
            return py.TYPE_PREFIX.format(node_.nested_class)
        return py.TYPES.get(node_.ret_type)

    t_name = py.TYPE_PREFIX.format(node.name)
    # DICT schema
    match node.struct_ref.type:
        case StructType.DICT:
            value_ret = [f for f in node.body if f.name == "__VALUE__"][
                0
            ].ret_type
            if node.body[-1].ret_type == VariableType.NESTED:
                type_ = py.TYPE_PREFIX.format(node.body[-1].nested_class)
            else:
                type_ = py.TYPES.get(value_ret)
            body = py.TYPE_DICT.format(type_)
        case StructType.FLAT_LIST:
            value_ret = [f for f in node.body if f.name == "__ITEM__"][
                0
            ].ret_type
            if node.body[-1].ret_type == VariableType.NESTED:
                type_ = py.TYPE_PREFIX.format(node.body[-1].nested_class)
            else:
                type_ = py.TYPES.get(value_ret)
            body = py.TYPE_LIST.format(type_)

        case StructType.ITEM:
            _dict_body = (
                "{"
                + ", ".join(
                    f"{f.name!r}: {_fetch_node_type(f)}" for f in node.body
                )
                + "}"
            )
            body = py.TYPE_ITEM.format(repr(t_name), _dict_body)
        case StructType.LIST:
            item_dict_body = (
                "{"
                + ", ".join(
                    f"{f.name!r}: {_fetch_node_type(f)}" for f in node.body
                )
                + "}"
            )
            item_name = f"{t_name}_ITEM"
            item_body = (
                item_name
                + " = "
                + py.TYPE_ITEM.format(repr(item_name), item_dict_body)
            )
            body = t_name + " = " + py.TYPE_LIST.format(item_name)
            return item_body + "\n" + body
    return t_name + " = " + body


def tt_struct(node: StructParser) -> str:
    return py.BINDINGS[node.kind, node.name]


def tt_docstring(node: Docstring) -> str:
    if not node.value:
        return ""
    # in codegen docstrings used in first line and inner classes
    indent = "" if node.parent.kind == TokenType.MODULE else py.INDENT_METHOD
    return indent + py.BINDINGS[node.kind, node.value]


def tt_ret(node: ReturnExpression) -> str:
    if node.have_default_expr():
        indent = py.INDENT_DEFAULT_BODY
        _, nxt = lr_var_names(variable=node.prev.variable)
    else:
        indent = py.INDENT_METHOD_BODY
        _, nxt = lr_var_names(variable=node.variable)
    return indent + py.BINDINGS[node.kind, nxt]


def tt_no_ret(node: NoReturnExpression) -> str:
    # used in __pre_validate__ case, ignore default wrap
    indent = py.suggest_indent(node)
    return indent + py.BINDINGS[node.kind]


def tt_nested(node: NestedExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    if node.have_default_expr():
        indent = py.INDENT_DEFAULT_BODY
    else:
        indent = py.INDENT_METHOD_BODY
    return indent + py.BINDINGS[node.kind, nxt, node.schema, prv]


def tt_pre_validate(node: PreValidateFunction) -> str:
    name = MAGIC_METHODS.get(node.name)
    return py.INDENT_METHOD + py.BINDINGS[node.kind, name]


def tt_start_parse_pre(node: StartParseFunction) -> str:
    name = MAGIC_METHODS.get(node.name)
    t_name = py.TYPE_BINDINGS.create_name(node.parent.typedef.name)

    if node.type == StructType.LIST:
        t_name = py.TYPE_BINDINGS.create_name(node.parent.typedef.name)
        t_name = py.TYPE_BINDINGS[node.type, t_name]

    return py.INDENT_METHOD + py.BINDINGS[node.kind, name, t_name]


def tt_start_parse_post(node: StartParseFunction) -> str:
    code = ""
    if any(f.name == "__PRE_VALIDATE__" for f in node.body):
        name = MAGIC_METHODS.get("__PRE_VALIDATE__")
        code += (
            py.INDENT_METHOD_BODY
            + py.E_CALL_METHOD.format(name, "self._doc")
            + "\n"
        )

    match node.type:
        case StructType.ITEM:
            body = py.gen_item_body(node)
        case StructType.LIST:
            body = py.gen_list_body(node)
        case StructType.DICT:
            body = py.gen_dict_body(node)
        case StructType.FLAT_LIST:
            body = py.get_flat_list_body(node)
        case _:
            raise NotImplementedError("Unknown struct type")
    return f"{code}{py.INDENT_METHOD_BODY}return {body}"


def tt_default_start(node: DefaultStart) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    return (
        py.INDENT_METHOD_BODY
        + f"{nxt} = {prv}\n"
        + py.INDENT_METHOD_BODY
        + py.BINDINGS[node.kind]
    )


def tt_default_end(node: DefaultEnd) -> str:
    # prv, nxt = lr_var_names(variable=node.variable)
    val = repr(node.value) if isinstance(node.value, str) else node.value
    return py.INDENT_METHOD_BODY + py.BINDINGS[node.kind, val]


def tt_string_format(node: FormatExpression) -> str:
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    template = node.fmt.replace("{{}}", "{}")
    return indent + py.BINDINGS[node.kind, nxt, repr(template), prv, prv, prv]


def tt_string_format_all(node: MapFormatExpression) -> str:
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    template = node.fmt.replace("{{}}", "{}")
    code = py.BINDINGS[node.kind, nxt, repr(template), prv]
    return indent + code


def tt_string_trim(node: TrimExpression) -> str:
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    chars = repr(node.value)
    code = py.BINDINGS[node.kind, nxt, prv, chars]
    return indent + code


def tt_string_trim_all(node: MapTrimExpression) -> str:
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    chars = repr(node.value)
    code = py.BINDINGS[node.kind, nxt, chars, prv]
    return indent + code


def tt_string_ltrim(node: LTrimExpression) -> str:
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    chars = repr(node.value)
    code = py.BINDINGS[node.kind, nxt, prv, chars]
    return indent + code


def tt_string_ltrim_all(node: MapLTrimExpression) -> str:
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    chars = repr(node.value)
    code = py.BINDINGS[node.kind, nxt, chars, prv]
    return indent + code


def tt_string_rtrim(node: RTrimExpression) -> str:
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    chars = repr(node.value)
    code = py.BINDINGS[node.kind, nxt, prv, chars]
    return indent + code


def tt_string_rtrim_all(node: MapRTrimExpression) -> str:
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    chars = repr(node.value)
    code = py.BINDINGS[node.kind, nxt, prv, chars]
    return indent + code


def tt_string_replace(node: ReplaceExpression) -> str:
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    old, new = repr(node.old), repr(node.new)
    code = py.BINDINGS[node.kind, nxt, prv, old, new]
    return indent + code


def tt_string_replace_all(node: MapReplaceExpression) -> str:
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    old, new = repr(node.old), repr(node.new)
    code = py.BINDINGS[node.kind, nxt, old, new, prv]
    return indent + code


def tt_string_split(node: SplitExpression) -> str:
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    sep = repr(node.sep)
    code = py.BINDINGS[node.kind, nxt, prv, sep]
    return indent + code


def tt_regex(node: RegexExpression) -> str:
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    pattern = repr(node.pattern)
    group = node.group
    code = py.BINDINGS[node.kind, nxt, pattern, prv, group]
    return indent + code


def tt_regex_all(node: RegexAllExpression) -> str:
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    pattern = repr(node.pattern)
    code = py.BINDINGS[node.kind, nxt, pattern, prv]
    return indent + code


def tt_regex_sub(node: RegexSubExpression) -> str:
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    pattern = repr(node.pattern)
    repl = repr(node.repl)
    code = py.BINDINGS[node.kind, nxt, pattern, repl, prv]
    return indent + code


def tt_regex_sub_all(node: MapRegexSubExpression) -> str:
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    pattern = repr(node.pattern)
    repl = repr(node.repl)
    code = py.BINDINGS[node.kind, nxt, pattern, repl, prv]
    return indent + code


def tt_index(node: IndexStringExpression | IndexDocumentExpression) -> str:
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    i = node.value
    code = py.BINDINGS[node.kind, nxt, prv, i]
    return indent + code


def tt_join(node: JoinExpression) -> str:
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    sep = repr(node.sep)
    code = py.BINDINGS[nxt, sep, prv]
    return indent + code


def tt_is_equal(node: IsEqualExpression) -> str:
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    value = repr(node.value)
    msg = repr(node.msg)
    code = py.BINDINGS[node.kind, prv, value, msg]
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return indent + code
    return indent + code + "\n" + indent + f"{nxt} = {prv}"


def tt_is_not_equal(node: IsNotEqualExpression) -> str:
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    value = repr(node.value)
    msg = repr(node.msg)
    code = py.BINDINGS[node.kind, prv, value, msg]
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return indent + code
    return indent + code + "\n" + indent + f"{nxt} = {prv}"


def tt_is_contains(node: IsContainsExpression) -> str:
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    item = repr(node.item)
    msg = repr(node.msg)

    code = py.BINDINGS[node.kind, item, prv, msg]
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return indent + code
    return indent + code + "\n" + indent + f"{nxt} = {prv}"


def tt_is_regex(node: IsRegexMatchExpression) -> str:
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    pattern = repr(node.pattern)
    msg = repr(node.msg)

    code = py.BINDINGS[node.kind, pattern, prv, msg]
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return indent + code
    return indent + code + "\n" + indent + f"{nxt} = {prv}"


def tt_to_int(node: ToInteger) -> str:
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    code = py.BINDINGS[node.kind, nxt, prv]
    return indent + code


def tt_to_list_int(node: ToListInteger) -> str:
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    code = py.BINDINGS[node.kind, nxt, prv]
    return indent + code


def tt_to_float(node: ToFloat) -> str:
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    code = py.BINDINGS[node.kind, nxt, prv]
    return indent + code


def tt_to_list_float(node: ToListFloat) -> str:
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    code = py.BINDINGS[node.kind, nxt, prv]
    return indent + code
