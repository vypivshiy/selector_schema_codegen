import re

from ssc_codegen.ast_ssc import (
    CallStructFunctionExpression,
    StartParseFunction,
    TypeDef,
    TypeDefField,
)
from ssc_codegen.tokens import TokenType, VariableType


def to_snake_case(s: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", s).lower()


def to_upper_camel_case(s: str) -> str:
    if not s:
        return s
    return "".join(word[0].upper() + word[1:] for word in s.split("_"))


def to_lower_camel_case(s: str) -> str:
    if not s:
        return s

    up_case = to_upper_camel_case(s)
    return up_case[0].lower() + up_case[1:]


def wrap_double_quotes(s: str, escape_ch: str = "\\") -> str:
    """used if string marks only in this chars"""
    return '"' + s.replace('"', escape_ch + '"') + '"'


def wrap_backtick(s: str, escape_ch: str = "\\") -> str:
    return "`" + s.replace("`", escape_ch + "`") + "`"


def escape_str(
    s: str, pattern: str = r"[\-.^$*+?{}\[\]\\|()]", escape_ch: str = "\\"
) -> str:
    """Sanitize matching characters.
    Used, for trim, l_trim, r_trim realizations by regex"""

    def _repl(ch: re.Match[str]) -> str:
        return escape_ch + ch[0]

    return re.sub(pattern, _repl, s)


def find_field_nested_struct(node: TypeDefField) -> TypeDef:
    if node.ret_type != VariableType.NESTED:
        raise TypeError("Return type is not NESTED")
    associated_typedef: TypeDef = [
        fn
        for fn in node.parent.parent.body  # type: ignore
        if getattr(fn, "name", None)
        and fn.name == node.nested_class
        and fn.kind == TokenType.TYPEDEF
    ][0]
    return associated_typedef


def find_tdef_field_node_by_name(
    node: TypeDef, name: str
) -> TypeDefField | None:
    """find node in body by name"""
    f = [f for f in node.body if f.name == name]
    if len(f) == 0:
        return None
    return f[0]


def find_callfn_field_node_by_name(
    node: StartParseFunction, name: str
) -> CallStructFunctionExpression | None:
    """find node in body by name"""
    f = [f for f in node.body if f.name == name]
    if len(f) == 0:
        return None
    return f[0]
