import re

from ssc_codegen.ast_ssc import (
    TypeDef,
    StructFieldFunction,
    TypeDefField,
    PartDocFunction,
)
from ssc_codegen.tokens import VariableType, TokenType


def to_snake_case(s: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", s).lower()


def to_upper_camel_case(s: str) -> str:
    return "".join(word[0].upper() + word[1:] for word in s.split("_"))


def to_lower_camel_case(s: str) -> str:
    words = s.replace("_", " ").split()
    return "".join(
        word.capitalize() if i != 0 else word.lower()
        for i, word in enumerate(words)
    )


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


def contains_assert_expr_fn(
    node: StructFieldFunction | PartDocFunction,
) -> bool:
    return any(
        t.kind
        in (
            TokenType.IS_CSS,
            TokenType.IS_EQUAL,
            TokenType.IS_NOT_EQUAL,
            TokenType.IS_CONTAINS,
            TokenType.IS_XPATH,
            TokenType.IS_REGEX_MATCH,
        )
        for t in node.body
        if t
    )


def find_nested_associated_typedef_by_t_field(node: TypeDefField) -> TypeDef:
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
