from typing import Any, Callable, cast

from ssc_codegen.ast_ import (
    BaseAstNode,
    StructFieldMethod,
    StartParseMethod,
    StructParser,
)
from ssc_codegen.ast_.nodes_core import ExprClassVar
from ssc_codegen.tokens import TOKENS_DEFAULT, TokenType, VariableType


def have_default_expr(node: BaseAstNode) -> bool:
    node.parent = cast(StructFieldMethod, node.parent)
    return any(i.kind in TOKENS_DEFAULT for i in node.parent.body)


def have_pre_validate_call(node: StartParseMethod) -> bool:
    return any(
        i.kwargs.get("name") and i.kwargs["name"] == "__PRE_VALIDATE__"
        for i in node.body
    )


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


def is_prev_node_atomic_cond(node: BaseAstNode) -> bool:
    """return true if node is atomic condition (exclude body), NOT FIRST"""
    return node.index != 0 and not node.parent.body[node.index_prev].body


def is_first_node_cond(node: BaseAstNode) -> bool:
    """return true if node at the first and its EXPR_FILTER token"""
    return node.index == 0 and node.parent.kind == TokenType.EXPR_FILTER


def jsonify_query_parse(query: str) -> list[str]:
    """wrap string keys to quotas, digits ignore"""
    if not query:
        return []
    parts = []
    for part in query.split("."):
        if part.isdigit():
            parts.append(part)
        else:
            parts.append(repr(part))

    return parts


def literal_expr_attr_call(node: ExprClassVar, sep: str = ".") -> str:
    """convert to literal classvar call"""
    if node.kind != TokenType.CLASSVAR:
        raise TypeError("not found literal hook")
    return sep.join(node.literal_ref_name)


def get_classvar_hook_or_value(
    node: BaseAstNode,
    key: str,
    *,
    cb_literal_cast: Callable[
        [ExprClassVar, str], str
    ] = literal_expr_attr_call,
    cb_value_cast: Callable[[Any], str] | None = None,
) -> str:
    """generate call classvar literal or if not exists - returns variable"""
    assert key in node.kwargs, (
        f"Wrong key `{key}` for node {node.__class__.__name__}, expected `{', '.join(node.kwargs.keys())}`"
    )

    if lit_hook := node.classvar_hooks.get(key):
        return cb_literal_cast(lit_hook)
    return (
        cb_value_cast(node.kwargs[key]) if cb_value_cast else node.kwargs[key]
    )


def _py_default_cast_t(i) -> str:
    """convert variable to valid python literal"""
    if isinstance(i, list):
        if all(isinstance(j, str) for j in i):
            return "[" + ",".join(repr(j) for j in i) + "]"
        return "[]"
    elif isinstance(i, str):
        return repr(i)
    return str(i)


def py_get_classvar_hook_or_value(
    node: BaseAstNode,
    key: str,
    *,
    cb_literal_cast: Callable[
        [ExprClassVar, str], str
    ] = literal_expr_attr_call,
    cb_value_cast: Callable[[Any], str] | None = _py_default_cast_t,
):
    """python create a ref for classvar if exists or return literal value"""
    return get_classvar_hook_or_value(
        node, key, cb_literal_cast=cb_literal_cast, cb_value_cast=cb_value_cast
    )


def _js_default_cast_t(i) -> str:
    if i is None:
        return "null"
    # simular literal as python list
    if isinstance(i, list):
        if all(isinstance(j, str) for j in i):
            return "[" + ",".join(repr(j) for j in i) + "]"
        return "[]"
    elif isinstance(i, str):
        return repr(str)
    elif isinstance(i, bool):
        return "true" if i else "false"
    # int, float types
    return str(i)


def js_get_classvar_hook_or_value(
    node: BaseAstNode,
    key: str,
    cb_literal_cast: Callable[[ExprClassVar], str] = literal_expr_attr_call,
    cb_value_cast: Callable[[Any], str] | None = _js_default_cast_t,
):
    """javascript create a ref for classvar if exists or return literal value"""
    return get_classvar_hook_or_value(
        node, key, cb_literal_cast=cb_literal_cast, cb_value_cast=cb_value_cast
    )


def py_regex_flags(ignore_case: bool = False, dotall: bool = False) -> str:
    """generate python regex flags argument"""
    flags = ""
    if ignore_case and dotall:
        flags += "re.I | re.S"
    elif ignore_case:
        flags = "re.I"
    elif dotall:
        flags = "re.S"
    return flags
