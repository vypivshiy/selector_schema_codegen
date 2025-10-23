from dataclasses import dataclass
from typing import TypedDict, ClassVar, Sequence

from ssc_codegen.ast_.base import BaseAstNode
from ssc_codegen.tokens import TokenType, VariableType

T_EQ_OR_NE_ARG = str | int | float | bool

KW_ASSERT_EQ_OR_NE = TypedDict(
    "KW_ASSERT_EQ_OR_NE", {"item": T_EQ_OR_NE_ARG, "msg": str, "invert": bool}
)
ARGS_ASSERT_EQ = tuple[T_EQ_OR_NE_ARG, str, bool]


@dataclass(kw_only=True)
class ExprIsEqual(BaseAstNode[KW_ASSERT_EQ_OR_NE, ARGS_ASSERT_EQ]):
    """AST node representing an equality assertion operation.
    
    This node represents an operation that checks if a value equals a specified item,
    with an optional message for assertion failure. It excludes certain complex types
    like documents, lists of documents, JSON, and nested structures.
    
    Kwargs:
        "item": str | int | float | bool - item for compare
        "msg": str
    """
    kind: ClassVar[TokenType] = TokenType.IS_EQUAL
    accept_type: VariableType = VariableType.ANY
    ret_type: VariableType = VariableType.ANY

    exclude_types: Sequence[VariableType] = (
        VariableType.DOCUMENT,
        VariableType.LIST_DOCUMENT,
        VariableType.JSON,
        VariableType.NESTED,
    )



T_IS_IN_ARG = str | int | float
KW_ASSERT_IN = TypedDict("KW_ASSERT_IN", {"item": T_EQ_OR_NE_ARG, "msg": str, "invert": bool})
ARGS_ASSERT_IN = tuple[T_EQ_OR_NE_ARG, str, bool]


@dataclass(kw_only=True)
class ExprIsContains(BaseAstNode[KW_ASSERT_IN, ARGS_ASSERT_IN]):
    """AST node representing a containment assertion operation.
    
    This node represents an operation that checks if a list contains a specified item,
    with an optional message for assertion failure. It excludes list of documents
    from the allowed types.
    """
    kind: ClassVar[TokenType] = TokenType.IS_CONTAINS
    accept_type: VariableType = VariableType.LIST_ANY
    ret_type: VariableType = VariableType.ANY
    exclude_types: Sequence[VariableType] = (VariableType.LIST_DOCUMENT,)


KW_IS_REGEX = TypedDict(
    "KW_IS_REGEX", {"pattern": str, "ignore_case": bool, "msg": str, "invert": bool}
)
ARGS_IS_REGEX = tuple[str, bool, str, bool]


@dataclass(kw_only=True)
class ExprStringIsRegex(BaseAstNode[KW_IS_REGEX, ARGS_IS_REGEX]):
    """AST node representing a string regex matching assertion operation.
    
    This node represents an operation that checks if a string matches a specified
    regular expression pattern, with options for case sensitivity and an optional
    message for assertion failure.
    
    Attributes:
        kind: The token type for this node (TokenType.IS_STRING_REGEX_MATCH).
        accept_type: The variable type accepted by this expression (VariableType.STRING).
        ret_type: The variable type returned by this expression (VariableType.STRING).
    """
    kind: ClassVar[TokenType] = TokenType.IS_STRING_REGEX_MATCH
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class ExprListStringAnyRegex(BaseAstNode[KW_IS_REGEX, ARGS_IS_REGEX]):
    """AST node representing a list of strings any regex matching assertion operation.
    
    This node represents an operation that checks if any string in a list matches
    a specified regular expression pattern, with options for case sensitivity and
    an optional message for assertion failure.
    
    Attributes:
        kind: The token type for this node (TokenType.ANY_LIST_STRING_REGEX_MATCH).
        accept_type: The variable type accepted by this expression (VariableType.LIST_STRING).
        ret_type: The variable type returned by this expression (VariableType.LIST_STRING).
    """
    kind: ClassVar[TokenType] = TokenType.ANY_LIST_STRING_REGEX_MATCH
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.LIST_STRING


@dataclass(kw_only=True)
class ExprListStringAllRegex(BaseAstNode[KW_IS_REGEX, ARGS_IS_REGEX]):
    """AST node representing a list of strings all regex matching assertion operation.
    
    This node represents an operation that checks if all strings in a list match
    a specified regular expression pattern, with options for case sensitivity and
    an optional message for assertion failure.
    
    Attributes:
        kind: The token type for this node (TokenType.ALL_LIST_STRING_REGEX_MATCH).
        accept_type: The variable type accepted by this expression (VariableType.LIST_STRING).
        ret_type: The variable type returned by this expression (VariableType.LIST_STRING).
    """
    kind: ClassVar[TokenType] = TokenType.ALL_LIST_STRING_REGEX_MATCH
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.LIST_STRING


KW_IS_SELECT = TypedDict("KW_IS_SELECT", {"query": str, "msg": str, "invert": bool})
ARGS_IS_SELECT = tuple[str, str, bool]


@dataclass(kw_only=True)
class ExprIsCss(BaseAstNode[KW_IS_SELECT, ARGS_IS_SELECT]):
    """AST node representing a CSS selector validation operation.
    
    This node represents an operation that validates if a document contains elements
    that match a specified CSS selector query, with an optional message for
    assertion failure.
    
    Attributes:
        kind: The token type for this node (TokenType.IS_CSS).
        accept_type: The variable type accepted by this expression (VariableType.DOCUMENT).
        ret_type: The variable type returned by this expression (VariableType.DOCUMENT).
    """
    kind: ClassVar[TokenType] = TokenType.IS_CSS
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT


@dataclass(kw_only=True)
class ExprIsXpath(BaseAstNode[KW_IS_SELECT, ARGS_IS_SELECT]):
    """AST node representing an XPath selector validation operation.
    
    This node represents an operation that validates if a document contains elements
    that match a specified XPath selector query, with an optional message for
    assertion failure.
    
    Attributes:
        kind: The token type for this node (TokenType.IS_XPATH).
        accept_type: The variable type accepted by this expression (VariableType.DOCUMENT).
        ret_type: The variable type returned by this expression (VariableType.DOCUMENT).
    """
    kind: ClassVar[TokenType] = TokenType.IS_XPATH
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT


KW_HAS_ATTR = TypedDict("KW_HAS_ATTR", {"key": str, "msg": str, "invert": bool})
ARGS_HAS_ATTR = tuple[str, str, bool]


@dataclass(kw_only=True)
class ExprHasAttr(BaseAstNode[KW_HAS_ATTR, ARGS_HAS_ATTR]):
    """AST node representing a document attribute existence validation operation.
    
    This node represents an operation that validates if a document contains a
    specified attribute key, with an optional message for assertion failure.
    
    Attributes:
        kind: The token type for this node (TokenType.HAS_ATTR).
        accept_type: The variable type accepted by this expression (VariableType.DOCUMENT).
        ret_type: The variable type returned by this expression (VariableType.DOCUMENT).
    """
    kind: ClassVar[TokenType] = TokenType.HAS_ATTR
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT


@dataclass(kw_only=True)
class ExprListHasAttr(BaseAstNode[KW_HAS_ATTR, ARGS_HAS_ATTR]):
    """AST node representing a list of documents attribute existence validation operation.
    
    This node represents an operation that validates if each document in a list
    contains a specified attribute key, with an optional message for assertion failure.
    
    Attributes:
        kind: The token type for this node (TokenType.HAS_LIST_ATTR).
        accept_type: The variable type accepted by this expression (VariableType.LIST_DOCUMENT).
        ret_type: The variable type returned by this expression (VariableType.LIST_DOCUMENT).
    """
    kind: ClassVar[TokenType] = TokenType.HAS_LIST_ATTR
    accept_type: VariableType = VariableType.LIST_DOCUMENT
    ret_type: VariableType = VariableType.LIST_DOCUMENT
