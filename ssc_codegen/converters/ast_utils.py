from typing import Type

from ssc_codegen import Json
from ssc_codegen.ast_ssc import (
    CallStructFunctionExpression,
    StartParseFunction,
    TypeDef,
    TypeDefField,
    StructFieldFunction,
)
from ssc_codegen.tokens import TokenType, VariableType


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


def is_optional_variable(var: VariableType) -> bool:
    return var in (
        VariableType.OPTIONAL_STRING,
        VariableType.OPTIONAL_INT,
        VariableType.OPTIONAL_FLOAT,
        VariableType.OPTIONAL_LIST_FLOAT,
        VariableType.OPTIONAL_LIST_INT,
        VariableType.OPTIONAL_LIST_STRING,
    )


def find_json_struct_instance(
    node: StructFieldFunction | TypeDefField,
) -> Type[Json] | None:
    # -1 TT_RET, -2 - TO_JSON (not included anything casts (naive))
    if node.kind == TokenType.TYPEDEF_FIELD:
        node = [i for i in node.parent.struct_ref.body if i.name == node.name][
            0
        ]

    if node.ret_type != VariableType.JSON:
        return None
    to_json_node = node.body[-2]
    return to_json_node.value
