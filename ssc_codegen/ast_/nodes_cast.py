from dataclasses import dataclass
from typing import TypedDict, Type, TYPE_CHECKING, TypeAlias, ClassVar

from ssc_codegen.tokens import TokenType, VariableType, StructType
from ssc_codegen.ast_.base import BaseAstNode, T_EMPTY_KWARGS

if TYPE_CHECKING:
    from ssc_codegen.schema import BaseSchema


@dataclass(kw_only=True)
class ExprToInt(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    """AST node representing an integer conversion expression.
    
    This node represents an operation that converts a string value to an integer.
    """
    kind: ClassVar[TokenType] = TokenType.TO_INT
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.INT


@dataclass(kw_only=True)
class ExprToListInt(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    """AST node representing a list of integers conversion expression.
    
    This node represents an operation that converts a list of string values to a list of integers.
    """
    kind: ClassVar[TokenType] = TokenType.TO_INT_LIST
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.LIST_INT


@dataclass(kw_only=True)
class ExprToFloat(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    """AST node representing a float conversion expression.
    
    This node represents an operation that converts a string value to a float.
    """
    kind: ClassVar[TokenType] = TokenType.TO_FLOAT
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.FLOAT


@dataclass(kw_only=True)
class ExprToListFloat(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    """AST node representing a list of floats conversion expression.
    
    This node represents an operation that converts a list of string values to a list of floats.
    """
    kind: ClassVar[TokenType] = TokenType.TO_FLOAT_LIST
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.LIST_FLOAT


@dataclass(kw_only=True)
class ExprToBool(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    """AST node representing a boolean conversion expression.
    
    This node represents an operation that converts any value to a boolean.
    Currently cast to bool logic:

    returns `false` if value is:
        - None
        - empty sequence
        - empty string

    Other returns `true`
    """
    kind: ClassVar[TokenType] = TokenType.TO_BOOL
    accept_type: VariableType = VariableType.ANY
    ret_type: VariableType = VariableType.BOOL


_T_SCHEMA: TypeAlias = Type["BaseSchema"]
KW_EXPR_NESTED = TypedDict(
    "KW_EXPR_NESTED", {"schema_name": str, "schema_type": StructType}
)
EXPR_NESTED_ARGS = tuple[str, StructType]


@dataclass(kw_only=True)
class ExprNested(BaseAstNode[KW_EXPR_NESTED, EXPR_NESTED_ARGS]):
    """AST node representing a nested structure expression.
    
    This node represents an operation that processes nested structures,
    using a schema name and structure type to determine how to handle
    the nested data.
    
    Kwargs:
        "schema_name": str - called nested schema name 
        "schema_type": StructType - called nested schema StructType
    """
    kind: ClassVar[TokenType] = TokenType.EXPR_NESTED
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.NESTED


KW_EXPR_JSONIFY = TypedDict(
    "KW_EXPR_JSONIFY", {"json_struct_name": str, "is_array": bool, "query": str}
)
ARGS_EXPR_JSONIFY = tuple[str, bool, str]


@dataclass(kw_only=True)
class ExprJsonify(BaseAstNode[KW_EXPR_JSONIFY, ARGS_EXPR_JSONIFY]):
    """AST node representing a JSON conversion expression.
    
    This node represents an operation that converts a string to JSON format,
    using a JSON structure name, array flag, and query to determine how to
    structure the resulting JSON.
    
    Kwargs:
        "json_struct_name": str - json struct name
        "is_array": bool - true if entrypoint array of structs 
        "query": str - optional query syntax where need start parse and serialize raw json data
            maybe useful for skip non-nessesary data (eg: NEST.js states)
    """
    kind: ClassVar[TokenType] = TokenType.TO_JSON
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.JSON


KW_EXPR_JSONIFY_DYNAMIC = TypedDict("KW_EXPR_JSONIFY_DYNAMIC", {"query": str})
ARGS_EXPR_JSONIFY_DYNAMIC = tuple[str]


@dataclass(kw_only=True)
class ExprJsonifyDynamic(
    BaseAstNode[KW_EXPR_JSONIFY_DYNAMIC, ARGS_EXPR_JSONIFY_DYNAMIC]
):
    """AST node representing a dynamic JSON conversion expression.
    
    This node represents an operation that dynamically converts a string to JSON format,
    using a query to determine how to structure the resulting JSON. The return type
    is currently stubbed to ANY.
    
    NOTE:
        maybe not supports in static-typed languages
    
    Kwargs:
        "query": str - optional query syntax where need start parse and serialize raw json data
            maybe useful for skip non-nessesary data (eg: NEST.js states)
    """
    kind: ClassVar[TokenType] = TokenType.TO_JSON_DYNAMIC
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.ANY  # STUBBED
