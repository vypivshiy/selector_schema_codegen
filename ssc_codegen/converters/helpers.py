from typing import cast

from ssc_codegen.ast_ import (
    BaseAstNode,
    StructFieldMethod,
    StartParseMethod,
    StructParser,
)
from ssc_codegen.tokens import TokenType, VariableType


def have_default_expr(node: BaseAstNode) -> bool:
    node.parent = cast(StructFieldMethod, node.parent)
    return any(i.kind in TokenType.default_tokens() for i in node.parent.body)


def have_pre_validate_call(node: StartParseMethod) -> bool:
    return any(i.kwargs["name"] == "__PRE_VALIDATE__" for i in node.body)


def prev_next_var(node: BaseAstNode, prefix: str = "v") -> tuple[str, str]:
    if node.index_prev == -1:
        return f"{prefix}", f"{prefix}{node.index}"
    return f"{prefix}{node.index_prev}", f"{prefix}{node.index}"


def is_last_var_no_ret(node: BaseAstNode) -> bool:
    return node.parent.body[node.index_next].kind == TokenType.EXPR_NO_RETURN  # type: ignore


def is_pre_validate_parent(node: BaseAstNode) -> bool:
    return node.parent.kind == TokenType.STRUCT_PRE_VALIDATE  # type: ignore


def get_last_ret_type(node: BaseAstNode) -> VariableType:
    return node.parent.body[-1].ret_type  # type: ignore


def get_struct_field_method_by_name(
    node: StructParser, name: str
) -> StructFieldMethod:
    """get struct field by name"""
    result = [
        i
        for i in node.body
        if i.kind == StructFieldMethod.kind and i.kwargs["name"] == name
    ][0]
    result = cast(StructFieldMethod, result)
    return result
