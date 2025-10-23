from dataclasses import dataclass
from typing import TypedDict, ClassVar

from ssc_codegen.ast_.base import BaseAstNode, T_EMPTY_KWARGS
from ssc_codegen.tokens import TokenType, VariableType

KW_EXPR_INDEX = TypedDict("KW_EXPR_INDEX", {"index": int})
ARGS_EXPR_INDEX = tuple[int]


@dataclass(kw_only=True)
class ExprIndex(BaseAstNode[KW_EXPR_INDEX, ARGS_EXPR_INDEX]):
    """AST node representing an index access expression.
    
    This node represents an operation that accesses an element at a specific index 
    in a list of any type.

    Rules:
        - first index starts from `0`. if target language index starts by `1`, 
         codegen should be automatically convert
        - allow use negative indexes: last index starts by `-1`. 
            codegen should be automatically convert by (len(curr_value)-{index})
    Note:
        - if target html parser backend support pseudo selectors - recommended use it instead extract by index
            
    Kwargs:
        "index": int - index where need extract variable
    """
    kind: ClassVar[TokenType] = TokenType.EXPR_LIST_ANY_INDEX
    accept_type: VariableType = VariableType.LIST_ANY
    ret_type: VariableType = VariableType.ANY


KW_EXPR_JOIN = TypedDict("KW_EXPR_JOIN", {"sep": str})
ARGS_EXPR_JOIN = tuple[str]


@dataclass(kw_only=True)
class ExprListStringJoin(BaseAstNode[KW_EXPR_JOIN, ARGS_EXPR_JOIN]):
    """AST node representing a string join operation on a list of strings.
    
    This node represents an operation that joins a list of strings using a 
    specified separator.
    
    Kwargs:
        "sep": str - separator for array of strings
    """
    kind: ClassVar[TokenType] = TokenType.EXPR_LIST_JOIN
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class ExprToListLength(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    """AST node representing a list length operation.
    
    This node represents an operation that returns the length of a list.
    """
    kind: ClassVar[TokenType] = TokenType.EXPR_LIST_LEN
    accept_type: VariableType = VariableType.LIST_ANY
    ret_type: VariableType = VariableType.INT


KW_UNIQUE = TypedDict("KW_UNIQUE", {"keep_order": bool})
ARGS_UNIQUE = tuple[bool]


@dataclass(kw_only=True)
class ExprListUnique(BaseAstNode[KW_UNIQUE, ARGS_UNIQUE]):
    """AST node representing a unique elements operation on a list.
    
    This node represents an operation that removes duplicate elements from a list
    of strings, optionally preserving the order of elements. 
    Note: Currently only supports LIST_STRING, but TODO indicates support for 
    LIST_INT and LIST_FLOAT should be added.
    
    Kwargs:
        - keep_order: bool - guarante save order elements
    """
    # TODO: support LIST_INT, LIST_FLOAT
    kind: ClassVar[TokenType] = TokenType.EXPR_LIST_UNIQUE
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.LIST_STRING
