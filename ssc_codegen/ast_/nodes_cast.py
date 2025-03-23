from dataclasses import dataclass
from typing import TypedDict, Type, TYPE_CHECKING, TypeAlias, ClassVar

from ssc_codegen.tokens import TokenType, VariableType
from ssc_codegen.ast_.base import BaseAstNode, T_EMPTY_KWARGS

if TYPE_CHECKING:
    from ssc_codegen.schema import BaseSchema
    from ssc_codegen.json_struct import Json


@dataclass(kw_only=True)
class ExprToInt(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    kind: ClassVar[TokenType] = TokenType.TO_INT
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.INT


@dataclass(kw_only=True)
class ExprToListInt(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    kind: ClassVar[TokenType] = TokenType.TO_INT_LIST
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.LIST_INT


@dataclass(kw_only=True)
class ExprToFloat(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    kind: ClassVar[TokenType] = TokenType.TO_FLOAT
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.FLOAT


@dataclass(kw_only=True)
class ExprToListFloat(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    kind: ClassVar[TokenType] = TokenType.TO_FLOAT_LIST
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.LIST_FLOAT


@dataclass(kw_only=True)
class ExprToBool(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    kind: ClassVar[TokenType] = TokenType.TO_BOOL
    accept_type: VariableType = VariableType.ANY
    ret_type: VariableType = VariableType.BOOL


_T_SCHEMA: TypeAlias = Type["BaseSchema"]
KW_EXPR_NESTED = TypedDict("KW_EXPR_NESTED", {"schema_name": str})
EXPR_NESTED_ARGS = tuple[str]


@dataclass(kw_only=True)
class ExprNested(BaseAstNode[KW_EXPR_NESTED, EXPR_NESTED_ARGS]):
    kind: ClassVar[TokenType] = TokenType.EXPR_NESTED
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.NESTED


_T_JSON: TypeAlias = Type["Json"]  # todo: provide json struct name only
KW_EXPR_JSONIFY = TypedDict("KW_EXPR_JSONIFY", {"json_struct": _T_JSON})
ARGS_EXPR_JSONIFY = tuple[_T_JSON]


@dataclass(kw_only=True)
class ExprJsonify(BaseAstNode[KW_EXPR_JSONIFY, ARGS_EXPR_JSONIFY]):
    kind: ClassVar[TokenType] = TokenType.TO_JSON
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.JSON
