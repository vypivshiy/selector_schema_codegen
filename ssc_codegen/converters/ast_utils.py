from ssc_codegen.ast_ssc import TypeDef, TypeDefField, StartParseFunction, CallStructFunctionExpression
from ssc_codegen.tokens import VariableType, TokenType


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
