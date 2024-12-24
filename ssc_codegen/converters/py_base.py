"""base universal python codegen api"""
from functools import partial

from .base import BaseCodeConverter, left_right_var_names
from .templates import py
from ..ast_ssc import (
    TypeDef,
    StructParser,
    Docstring,
    ReturnExpression,
    NoReturnExpression,
    NestedExpression,
    PreValidateFunction,
    StartParseFunction,
    DefaultValueWrapper,
    FormatExpression,
    MapFormatExpression,
    TrimExpression,
    MapTrimExpression,
    LTrimExpression,
    MapLTrimExpression,
    RTrimExpression,
    MapRTrimExpression,
    ReplaceExpression,
    MapReplaceExpression,
    SplitExpression,
    RegexExpression,
    RegexAllExpression,
    RegexSubExpression,
    MapRegexSubExpression,
    IndexStringExpression,
    IndexDocumentExpression,
    JoinExpression,
    IsEqualExpression,
    IsNotEqualExpression,
    IsContainsExpression,
    IsRegexMatchExpression, ToInteger, ToListInteger, ToFloat, ToListFloat,
)
from ..tokens import TokenType, VariableType, StructType

lr_var_names = partial(left_right_var_names, name="value")

TYPES = py.TYPES
MAGIC_METHODS = py.MAGIC_METHODS


class BasePyCodeConverter(BaseCodeConverter):
    def __init__(self):
        super().__init__()
        # TODO link converters
        self.pre_definitions[TokenType.TYPEDEF] = tt_typedef
        self.pre_definitions[TokenType.STRUCT] = tt_struct
        self.pre_definitions[TokenType.DOCSTRING] = tt_docstring
        self.pre_definitions[TokenType.EXPR_RETURN] = tt_ret
        self.pre_definitions[TokenType.EXPR_NO_RETURN] = tt_no_ret
        self.pre_definitions[TokenType.EXPR_NESTED] = tt_nested
        self.pre_definitions[TokenType.STRUCT_PRE_VALIDATE] = tt_pre_validate

        self.pre_definitions[TokenType.STRUCT_PARSE_START] = tt_start_parse_pre
        self.post_definitions[
            TokenType.STRUCT_PARSE_START
        ] = tt_start_parse_post

        self.pre_definitions[TokenType.EXPR_DEFAULT] = tt_default_pre
        self.post_definitions[TokenType.EXPR_DEFAULT] = tt_default_post

        self.pre_definitions[TokenType.EXPR_STRING_FORMAT] = tt_string_format
        self.pre_definitions[
            TokenType.EXPR_LIST_STRING_FORMAT
        ] = tt_string_format_all
        self.pre_definitions[TokenType.EXPR_STRING_TRIM] = tt_string_trim
        self.pre_definitions[
            TokenType.EXPR_LIST_STRING_TRIM
        ] = tt_string_trim_all
        self.pre_definitions[TokenType.EXPR_STRING_TRIM] = tt_string_trim
        self.pre_definitions[
            TokenType.EXPR_LIST_STRING_TRIM
        ] = tt_string_trim_all
        self.pre_definitions[TokenType.EXPR_STRING_LTRIM] = tt_string_ltrim
        self.pre_definitions[
            TokenType.EXPR_LIST_STRING_LTRIM
        ] = tt_string_ltrim_all
        self.pre_definitions[TokenType.EXPR_STRING_RTRIM] = tt_string_rtrim
        self.pre_definitions[
            TokenType.EXPR_LIST_STRING_RTRIM
        ] = tt_string_rtrim_all
        self.pre_definitions[TokenType.EXPR_STRING_REPLACE] = tt_string_replace
        self.pre_definitions[
            TokenType.EXPR_LIST_STRING_REPLACE
        ] = tt_string_replace_all
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


def tt_typedef(node: TypeDef):
    def _fetch_node_type(node_):
        if node_.ret_type == VariableType.NESTED:
            return py.TYPE_PREFIX.format(node_.nested_class)
        return TYPES.get(node_.ret_type)

    t_name = py.TYPE_PREFIX.format(node.name)
    # DICT schema
    if all(f.name in ["__KEY__", "__VALUE__"] for f in node.body):
        value_ret = [f for f in node.body if f.name == "__VALUE__"][0].ret_type
        if node.body[-1].ret_type == VariableType.NESTED:
            type_ = py.TYPE_PREFIX.format(node.body[-1].nested_class)
        else:
            type_ = TYPES.get(value_ret)
        body = py.TYPE_DICT.format(type_)

    # Flat list schema
    elif all(f.name in ["__ITEM__"] for f in node.body):
        value_ret = [f for f in node.body if f.name == "__ITEM__"][0].ret_type
        if node.body[-1].ret_type == VariableType.NESTED:
            type_ = py.TYPE_PREFIX.format(node.body[-1].nested_class)
        else:
            type_ = TYPES.get(value_ret)
        body = py.TYPE_LIST.format(type_)
    # other
    else:
        t_dict_body = (
            "{"
            + ", ".join(f"{f.name!r}: {_fetch_node_type(f)}" for f in node.body)
            + "}"
        )
        body = py.TYPE_ITEM.format(repr(t_name), t_dict_body)
    return f"T_{node.name} = {body}"


def tt_struct(node: StructParser) -> str:
    return py.CLS_HEAD.format(node.name)


def tt_docstring(node: Docstring) -> str:
    if not node.value:
        return ""
    # in codegen docstrings used in first line and inner classes
    indent = "" if node.parent.kind == TokenType.MODULE else py.INDENT_METHOD
    return indent + py.CLS_DOCSTRING.format(node.value)


def tt_ret(node: ReturnExpression) -> str:
    _, nxt = lr_var_names(variable=node.variable)
    if node.have_default_expr():
        return py.INDENT_DEFAULT_BODY + py.RET.format(nxt)
    return py.INDENT_METHOD_BODY + py.RET.format(nxt)


def tt_no_ret(_: NoReturnExpression) -> str:
    # used in __pre_validate__ case, ignore default wrap
    return py.INDENT_METHOD_BODY + py.NO_RET


def tt_nested(node: NestedExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    if node.have_default_expr():
        return py.INDENT_DEFAULT_BODY + py.E_PARSE_NESTED.format(
            nxt, node.schema, prv
        )
    return py.INDENT_METHOD_BODY + py.E_PARSE_NESTED.format(
        nxt, node.schema, prv
    )


def tt_pre_validate(node: PreValidateFunction) -> str:
    return py.INDENT_METHOD + py.CLS_PRE_VALIDATE_HEAD.format(
        MAGIC_METHODS.get(node.name)
    )


def tt_start_parse_pre(node: StartParseFunction) -> str:
    name = MAGIC_METHODS.get(node.name)
    if node.type == StructType.LIST:
        t_name = py.TYPE_LIST.format(
            py.TYPE_PREFIX.format(node.parent.typedef.name)
        )
    else:
        t_name = py.TYPE_PREFIX.format(node.parent.typedef.name)
    return py.INDENT_METHOD + py.FN_PARSE_START.format(name, t_name)


def tt_start_parse_post(node: StartParseFunction):
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


def tt_default_pre(node: DefaultValueWrapper) -> str:
    # is first attr (naive)
    # todo refactoring, return DefaultValueWrapper to body
    # issue: not contains variable and prv, nxt properties
    prv, nxt = "value", "value1"
    # prv, nxt = lr_var_names(variable=node.variable)
    return (py.INDENT_METHOD_BODY
            + f"{nxt} = {prv}"
            + '\n'
            + py.INDENT_METHOD_BODY
            + py.E_DEFAULT_WRAP)


def tt_default_post(node: DefaultValueWrapper) -> str:
    val = repr(node.value) if isinstance(node.value, str) else node.value
    return py.INDENT_METHOD_BODY + py.RET.format(val)


def tt_string_format(node: FormatExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    template = node.fmt.replace("{{}}", "{}")
    code = py.E_STR_FMT.format(nxt, repr(template), prv, prv, prv)
    if node.have_default_expr():
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


def tt_string_format_all(node: MapFormatExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    template = node.fmt.replace("{{}}", "{}")
    code = py.E_STR_FMT_ALL.format(nxt, repr(template), prv)
    if node.have_default_expr():
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


def tt_string_trim(node: TrimExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    chars = repr(node.value)
    code = py.E_STR_TRIM.format(nxt, prv, chars)
    if node.have_default_expr():
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


def tt_string_trim_all(node: MapTrimExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    chars = repr(node.value)
    code = py.E_STR_TRIM_ALL.format(nxt, chars, prv)
    if node.have_default_expr():
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


def tt_string_ltrim(node: LTrimExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    chars = repr(node.value)
    code = py.E_STR_LTRIM.format(nxt, prv, chars)
    if node.have_default_expr():
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


def tt_string_ltrim_all(node: MapLTrimExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    chars = repr(node.value)
    code = py.E_STR_LTRIM_ALL.format(nxt, chars, prv)
    if node.have_default_expr():
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


def tt_string_rtrim(node: RTrimExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    chars = repr(node.value)
    code = py.E_STR_RTRIM.format(nxt, prv, chars)
    if node.have_default_expr():
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


def tt_string_rtrim_all(node: MapRTrimExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    chars = repr(node.value)
    code = py.E_STR_RTRIM_ALL.format(nxt, chars, prv)
    if node.have_default_expr():
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


def tt_string_replace(node: ReplaceExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    old, new = repr(node.old), repr(node.new)
    code = py.E_STR_REPL.format(nxt, prv, old, new)
    if node.have_default_expr():
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


def tt_string_replace_all(node: MapReplaceExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    old, new = repr(node.old), repr(node.new)
    code = py.E_STR_REPL_ALL.format(nxt, old, new, prv)
    if node.have_default_expr():
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


def tt_string_split(node: SplitExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    sep = repr(node.sep)
    code = py.E_STR_SPLIT.format(nxt, prv, sep)
    if node.have_default_expr():
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


def tt_regex(node: RegexExpression):
    prv, nxt = lr_var_names(variable=node.variable)
    pattern = repr(node.pattern)
    group = node.group
    code = py.E_RE.format(nxt, pattern, prv, group)
    if node.have_default_expr():
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


def tt_regex_all(node: RegexAllExpression):
    prv, nxt = lr_var_names(variable=node.variable)
    pattern = repr(node.pattern)
    code = py.E_RE_ALL.format(nxt, pattern, prv)
    if node.have_default_expr():
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


def tt_regex_sub(node: RegexSubExpression):
    prv, nxt = lr_var_names(variable=node.variable)
    pattern = repr(node.pattern)
    repl = repr(node.repl)
    code = py.E_RE_SUB.format(nxt, pattern, repl, prv)
    if node.have_default_expr():
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


def tt_regex_sub_all(node: MapRegexSubExpression):
    prv, nxt = lr_var_names(variable=node.variable)
    pattern = repr(node.pattern)
    repl = repr(node.repl)
    code = py.E_RE_SUB_ALL.format(nxt, pattern, repl, prv)
    if node.have_default_expr():
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


def tt_index(node: IndexStringExpression | IndexDocumentExpression):
    prv, nxt = lr_var_names(variable=node.variable)
    i = node.value
    code = py.E_INDEX.format(nxt, prv, i)
    if node.have_default_expr():
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


def tt_join(node: JoinExpression):
    prv, nxt = lr_var_names(variable=node.variable)
    sep = repr(node.sep)
    code = py.E_JOIN.format(nxt, sep, prv)
    if node.have_default_expr():
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


def tt_is_equal(node: IsEqualExpression):
    prv, nxt = lr_var_names(variable=node.variable)
    value = repr(node.value)
    msg = repr(node.msg)
    indent = (
        py.INDENT_DEFAULT_BODY
        if node.have_default_expr()
        else py.INDENT_METHOD_BODY
    )
    code = py.E_EQ.format(prv, value, msg)

    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return indent + code
    return f"{indent}{code}\n{indent}{nxt} = {prv}"


def tt_is_not_equal(node: IsNotEqualExpression):
    prv, nxt = lr_var_names(variable=node.variable)
    value = repr(node.value)
    msg = repr(node.msg)
    indent = (
        py.INDENT_DEFAULT_BODY
        if node.have_default_expr()
        else py.INDENT_METHOD_BODY
    )
    code = py.E_NE.format(prv, value, msg)

    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return indent + code
    return f"{indent}{code}\n{indent}{nxt} = {prv}"


def tt_is_contains(node: IsContainsExpression):
    prv, nxt = lr_var_names(variable=node.variable)
    item = repr(node.item)
    msg = repr(node.msg)
    indent = (
        py.INDENT_DEFAULT_BODY
        if node.have_default_expr()
        else py.INDENT_METHOD_BODY
    )

    code = py.E_IN.format(item, prv, msg)
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return indent + code
    return f"{indent}{code}\n{indent}{nxt} = {prv}"


def tt_is_regex(node: IsRegexMatchExpression):
    prv, nxt = lr_var_names(variable=node.variable)
    pattern = repr(node.pattern)
    msg = repr(node.msg)
    indent = (
        py.INDENT_DEFAULT_BODY
        if node.have_default_expr()
        else py.INDENT_METHOD_BODY
    )

    code = py.E_IS_RE.format(pattern, prv, msg)
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return indent + code
    return f"{indent}{code}\n{indent}{nxt} = {prv}"


def tt_to_int(node: ToInteger):
    prv, nxt = lr_var_names(variable=node.variable)
    indent = (
        py.INDENT_DEFAULT_BODY
        if node.have_default_expr()
        else py.INDENT_METHOD_BODY
    )
    code = f"{nxt} = int({prv})"
    return indent + code


def tt_to_list_int(node: ToListInteger):
    prv, nxt = lr_var_names(variable=node.variable)
    indent = (
        py.INDENT_DEFAULT_BODY
        if node.have_default_expr()
        else py.INDENT_METHOD_BODY
    )
    code = f"{nxt} = [int(i) for i in {prv}]"
    return indent + code


def tt_to_float(node: ToFloat):
    prv, nxt = lr_var_names(variable=node.variable)
    indent = (
        py.INDENT_DEFAULT_BODY
        if node.have_default_expr()
        else py.INDENT_METHOD_BODY
    )
    code = f"{nxt} = float({prv})"
    return indent + code


def tt_to_list_float(node: ToListFloat):
    prv, nxt = lr_var_names(variable=node.variable)
    indent = (
        py.INDENT_DEFAULT_BODY
        if node.have_default_expr()
        else py.INDENT_METHOD_BODY
    )
    code = f"{nxt} = [float(i) for i in {prv}]"
    return indent + code
