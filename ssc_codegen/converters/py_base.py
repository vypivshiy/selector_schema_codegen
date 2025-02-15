"""base universal python codegen api"""

from functools import partial

from typing_extensions import assert_never

from .ast_utils import find_json_struct_instance
from ssc_codegen.ast_ssc import (
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
    ToJson,
    JsonStruct,
    JsonStructField,
)
from ssc_codegen.tokens import (
    StructType,
    TokenType,
    VariableType,
    JsonFieldType,
)
from .base import BaseCodeConverter, left_right_var_names
from .templates import py

lr_var_names = partial(left_right_var_names, name="value")

MAGIC_METHODS = py.MAGIC_METHODS_NAME


class BasePyCodeConverter(BaseCodeConverter):
    def __init__(self) -> None:
        super().__init__()
        # TODO link converters
        self.pre_definitions[TokenType.IMPORTS] = tt_imports

        self.pre_definitions[TokenType.TYPEDEF] = tt_typedef_pre
        self.post_definitions[TokenType.TYPEDEF] = tt_typedef_post
        self.pre_definitions[TokenType.TYPEDEF_FIELD] = tt_typedef_field

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

        self.pre_definitions[TokenType.TO_JSON] = tt_to_json
        self.pre_definitions[TokenType.JSON_STRUCT] = tt_json_struct_pre
        self.post_definitions[TokenType.JSON_STRUCT] = tt_json_struct_post
        self.pre_definitions[TokenType.JSON_FIELD] = tt_json_field


def tt_imports(node: ModuleImports) -> str:
    return py.BINDINGS[node.kind]


def tt_typedef_pre(node: TypeDef) -> str:
    match node.struct_ref.type:  # type: ignore
        case StructType.DICT:
            return f"T_{node.name} = Dict[str, "
        case StructType.FLAT_LIST:
            return f"T_{node.name} = List["
        case StructType.ITEM:
            return f'T_{node.name} = TypedDict("T_{node.name}", ' + "{"
        case StructType.LIST:
            return f'T_{node.name} = TypedDict("T_{node.name}", ' + "{"
        case _:
            assert_never(node.struct_ref.type)
    raise NotImplementedError()  # noqa


def tt_typedef_post(node: TypeDef) -> str:
    match node.struct_ref.type:  # type: ignore
        case StructType.DICT:
            return "]"
        case StructType.FLAT_LIST:
            return "]"
        case StructType.ITEM:
            return "})"
        case StructType.LIST:
            return "})"
        case _:
            assert_never(node.struct_ref.type)
    raise NotImplementedError()  # noqa


def tt_typedef_field(node: TypeDefField) -> str:
    # always str
    if node.name == "__KEY__":
        return ""

    if node.ret_type == VariableType.NESTED:
        type_ = f"T_{node.nested_class}"
        if node.nested_node_ref.type == StructType.LIST:
            type_ = f"List[{type_}]"
    elif node.ret_type == VariableType.JSON:
        instance = find_json_struct_instance(node)
        if instance.__IS_ARRAY__:
            type_ = f"List[J_{instance.__name__}]"
        else:
            type_ = f"J_{instance.__name__}"
    else:
        type_ = py.TYPES.get(node.ret_type, "Any")

    match node.parent.struct_ref.type:
        case StructType.DICT:
            return type_
        case StructType.FLAT_LIST:
            return type_
        case StructType.ITEM:
            return f'"{node.name}": {type_}, '
        case StructType.LIST:
            return f'"{node.name}": {type_}, '
        case _:
            assert_never(node.parent.struct_ref.type)
    # unreached code
    raise NotImplementedError()  # noqa


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
    t_name = f"T_{node.parent.typedef.name}"

    if node.type == StructType.LIST:
        t_name = f"List[{t_name}]"
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
    return code + py.INDENT_METHOD_BODY + "return " + body


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
    code = py.BINDINGS[node.kind, nxt, sep, prv]
    return indent + code


def tt_is_equal(node: IsEqualExpression) -> str:
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    value = repr(node.value) if isinstance(node.value, str) else node.value
    msg = repr(node.msg)
    code = py.BINDINGS[node.kind, prv, value, msg]
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return indent + code
    return indent + code + "\n" + indent + f"{nxt} = {prv}"


def tt_is_not_equal(node: IsNotEqualExpression) -> str:
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    value = repr(node.value) if isinstance(node.value, str) else node.value
    msg = repr(node.msg)
    code = py.BINDINGS[node.kind, prv, value, msg]
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return indent + code
    return indent + code + "\n" + indent + f"{nxt} = {prv}"


def tt_is_contains(node: IsContainsExpression) -> str:
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)

    item = repr(node.item) if isinstance(node.item, str) else node.item
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


# json
def tt_json_struct_pre(node: JsonStruct) -> str:
    return f'J_{node.name} = TypedDict("J_{node.name}", ' + "{"


def tt_json_struct_post(_: JsonStruct) -> str:
    return "})"


def tt_json_field(node: JsonStructField) -> str:
    match node.value.kind:
        case JsonFieldType.BASIC:
            return f'"{node.name}": {py.JSON_TYPES.get(node.ret_type.TYPE, "Any")}, '
        case JsonFieldType.OBJECT:
            return f'"{node.name}": J_{node.struct_ref}, '
        case JsonFieldType.ARRAY:
            if isinstance(node.ret_type.TYPE, dict):
                type_ = f"List[J_{node.value.TYPE.name}]"
            else:
                type_ = f"List[{py.JSON_TYPES.get(node.ret_type.TYPE, 'Any')}]"
            return f'"{node.name}": {type_}, '
        case _:
            assert_never(node.value.kind)  # noqa
    raise NotImplementedError("inreached code")  # noqa


def tt_to_json(node: ToJson) -> str:
    # TODO: move consts to templates
    indent = py.suggest_indent(node)
    prv, nxt = lr_var_names(variable=node.variable)
    code = f"{nxt} = json.loads({prv})"
    return indent + code
