import re

from ssc_codegen.ast_ssc import TypeDef, StructFieldFunction, TypeDefField, PartDocFunction, \
    CallStructFunctionExpression, StructParser, StartParseFunction
from ssc_codegen.tokens import VariableType, TokenType


def to_snake_case(s: str):
    return re.sub(r"(?<!^)(?=[A-Z])", "_", s).lower()


def to_upper_camel_case(s: str):
    return "".join(word[0].upper() + word[1:] for word in s.split("_"))


def to_lower_camel_case(s: str):
    return "".join(word[0].lower() + word[1:] for word in s.split("_"))


def wrap_double_quotes(s: str, escape_ch: str = "\\") -> str:
    """used if string marks only in this chars"""
    return '"' + s.replace('"', escape_ch + '"') + '"'


def wrap_backtick(s: str, escape_ch: str = "\\") -> str:
    return '`' + s.replace('`', escape_ch + '`') + '`'


def escape_str(
        s: str, pattern: str = r"[\-.^$*+?{}\[\]\\|()]", escape_ch: str = "\\"
) -> str:
    """Sanitize matching characters.
    Used, for trim, l_trim, r_trim realizations by regex"""

    def _repl(ch: re.Match[str]) -> str:
        return escape_ch + ch[0]

    return re.sub(pattern, _repl, s)


def find_nested_associated_typedef_by_st_field_fn(node: StructFieldFunction) -> TypeDef:
    if node.ret_type != VariableType.NESTED:
        raise TypeError("Return type is not NESTED")
    associated_typedef: TypeDef = [fn for fn in node.parent.parent.body  # type: ignore
                                   if getattr(fn, 'name', None)
                                   and fn.name == node.body[-2].schema  # noqa
                                   and fn.kind == TokenType.TYPEDEF][0]
    return associated_typedef


def find_nested_associated_typedef_by_typedef_field(node: TypeDefField) -> TypeDef:
    if node.type != VariableType.NESTED:
        raise TypeError("Return type is not NESTED")
    associated_typedef: TypeDef = [fn for fn in node.parent.parent.body  # type: ignore
                                   if getattr(fn, 'name', None)
                                   and fn.name == node.nested_class
                                   and fn.kind == TokenType.TYPEDEF][0]
    return associated_typedef


def have_assert_expr(node: StructFieldFunction | PartDocFunction) -> bool:
    return any(t.kind in (TokenType.IS_CSS,
                          TokenType.IS_EQUAL,
                          TokenType.IS_NOT_EQUAL,
                          TokenType.IS_CONTAINS,
                          TokenType.IS_XPATH,
                          TokenType.IS_REGEX_MATCH,
                          )
               for t in node.body)


def find_st_field_fn_by_call_st_fn(node: CallStructFunctionExpression) -> StructFieldFunction:
    module_body = node.parent.parent
    for st_node in module_body.body:
        if st_node.kind != TokenType.STRUCT:
            continue
        st_node: StructParser
        for fn_node in st_node.body:
            if fn_node.name == node.name:
                return fn_node
        raise TypeError("Node not founded")


def have_start_parse_assert_expr(node: StartParseFunction) -> bool:
    for expr in node.body:
        if node.kind == TokenType.STRUCT_CALL_FUNCTION:
            fn_node = find_st_field_fn_by_call_st_fn(expr)
            if have_assert_expr(fn_node):
                return True
    return False


def have_call_expr_assert_expr(node: CallStructFunctionExpression) -> bool:
    module_body = node.parent.parent
    parent_st = node.parent
    for st_node in module_body.body:
        if st_node.kind != TokenType.STRUCT_FIELD and st_node.name != parent_st.name:
            continue
        st_node: StructFieldFunction
        if have_assert_expr(st_node):
            return True
    return False
