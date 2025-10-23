from dataclasses import dataclass
from typing import TypedDict, ClassVar

from ssc_codegen.ast_.base import BaseAstNode, T_EMPTY_KWARGS
from ssc_codegen.tokens import TokenType, VariableType

KW_STR_TRIM = TypedDict("KW_STR_TRIM", {"substr": str})


@dataclass(kw_only=True)
class ExprStringTrim(BaseAstNode[KW_STR_TRIM, tuple[str]]):
    """AST node representing a string trim operation.

    This node represents an operation that removes the specified substring
    from both the beginning and end of a string.

    Kwargs:
        "substr": str: the substring that will be deleted
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_STRING_TRIM
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class ExprStringLeftTrim(BaseAstNode[KW_STR_TRIM, tuple[str]]):
    """AST node representing a string left trim operation.

    This node represents an operation that removes the specified substring
    from the beginning (left side) of a string.

    Kwargs:
        "substr": str: the substring that will be deleted
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_STRING_LTRIM
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class ExprStringRightTrim(BaseAstNode[KW_STR_TRIM, tuple[str]]):
    """AST node representing a string right trim operation.

    This node represents an operation that removes the specified substring
    from the end (right side) of a string.

    Kwargs:
        "substr": str: the substring that will be deleted
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_STRING_RTRIM
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class ExprListStringTrim(BaseAstNode[KW_STR_TRIM, tuple[str]]):
    """AST node representing a list of strings trim operation.

    This node represents an operation that removes the specified substring
    from both the beginning and end of each string in a list of strings.

    Kwargs:
        "substr": str: the substring that will be deleted
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_LIST_STRING_TRIM
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.LIST_STRING


@dataclass(kw_only=True)
class ExprListStringLeftTrim(BaseAstNode[KW_STR_TRIM, tuple[str]]):
    """AST node representing a list of strings left trim operation.

    This node represents an operation that removes the specified substring
    from the beginning (left side) of each string in a list of strings.

    Kwargs:
        "substr": str: the substring that will be deleted
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_LIST_STRING_LTRIM
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.LIST_STRING


@dataclass(kw_only=True)
class ExprListStringRightTrim(BaseAstNode[KW_STR_TRIM, tuple[str]]):
    """AST node representing a list of strings right trim operation.

    This node represents an operation that removes the specified substring
    from the end (right side) of each string in a list of strings.

    Kwargs:
        "substr": str: the substring that will be deleted
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_LIST_STRING_RTRIM
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.LIST_STRING


KW_STR_FMT = TypedDict("KW_STR_FMT", {"fmt": str})


@dataclass(kw_only=True)
class ExprStringFormat(BaseAstNode[KW_STR_FMT, tuple[str]]):
    """AST node representing a string format operation.

    This node represents an operation that formats a string using the specified
    format string pattern.

    Kwargs:
        "fmt": str: ttemplate for formatting.
        For the target programming language,
        replace the placeholder "{{}}" with the target one.
        For example, replace to "{}", "%s"...
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_STRING_FORMAT
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class ExprListStringFormat(BaseAstNode[KW_STR_FMT, tuple[str]]):
    """AST node representing a list of strings format operation.

    This node represents an operation that formats each string in a list of strings
    using the specified format string pattern.

    Kwargs:
        "fmt": str: ttemplate for formatting.
        For the target programming language,
        replace the placeholder "{{}}" with the target one.
        For example, replace to "{}", "%s"...
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_LIST_STRING_FORMAT
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.LIST_STRING


KW_STR_SEP = TypedDict("KW_STR_SEP", {"sep": str})


@dataclass(kw_only=True)
class ExprStringSplit(BaseAstNode[KW_STR_SEP, tuple[str]]):
    """AST node representing a string split operation.

    This node represents an operation that splits a string into a list of strings
    using the specified separator.

    Kwargs:
        "sep": str - sepatare string how to split
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_STRING_SPLIT
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.LIST_STRING


KW_STR_REPL = TypedDict("KW_STR_REPL", {"old": str, "new": str})


@dataclass(kw_only=True)
class ExprStringReplace(BaseAstNode[KW_STR_REPL, tuple[str, str]]):
    """AST node representing a string replace operation.

    This node represents an operation that replaces occurrences of a substring
    with another substring in a string.

    Note: this expr does not has limit impl and replace all substrings

    Kwargs:
        "old": str - the target substring to be replaced
        "new": str - the target substring to replace it with
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_STRING_REPLACE
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class ExprListStringReplace(BaseAstNode[KW_STR_REPL, tuple[str, str]]):
    """AST node representing a list of strings replace operation.

    This node represents an operation that replaces occurrences of a substring
    with another substring in each string of a list of strings.

    Note: this expr does not has limit impl and replace all substrings

    Kwargs:
        "old": str - the target substring to be replaced
        "new": str - the target substring to replace it with
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_LIST_STRING_REPLACE
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.LIST_STRING


KW_STR_MAP_REPL = TypedDict(
    "KW_STR_MAP_REPL", {"old": tuple[str, ...], "new": tuple[str, ...]}
)
ARGS_STR_MAP_REPL = tuple[tuple[str, ...], tuple[str, ...]]


@dataclass(kw_only=True)
class ExprStringMapReplace(BaseAstNode[KW_STR_MAP_REPL, ARGS_STR_MAP_REPL]):
    """AST node representing a string map replace operation.

    This node represents an operation that replaces multiple substrings in a string
    according to mapping rules defined by tuples of old and new substrings.

    Note: this expr does not has limit impl and replace all substrings

    Kwargs:
        "old": str - the targets substrings to be replaced
        "new": str - the target substrings to replace it with
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_STRING_MAP_REPLACE
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class ExprListStringMapReplace(BaseAstNode[KW_STR_MAP_REPL, ARGS_STR_MAP_REPL]):
    """AST node representing a list of strings map replace operation.

    This node represents an operation that replaces multiple substrings in each
    string of a list according to mapping rules defined by tuples of old and new substrings.

    Note: this expr does not has limit impl and replace all substrings

    Kwargs:
        "old": str - the targets substrings to be replaced
        "new": str - the target substrings to replace it with
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_LIST_STRING_MAP_REPLACE
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.LIST_STRING


KW_STR_RE = TypedDict(
    "KW_STR_RE",
    {"pattern": str, "group": int, "ignore_case": bool, "dotall": bool},
)


@dataclass(kw_only=True)
class ExprStringRegex(BaseAstNode[KW_STR_RE, tuple[str, int, bool, bool]]):
    """AST node representing a string regex extraction operation.

    This node represents an operation that extracts a substring from a string
    using a regular expression pattern, with options for case sensitivity and
    dotall matching mode.

    Kwargs:
        "pattern": str - regex pattern
        "group": int - group for capture (default 1)
        "ignore_case": bool - add ignorecase flag
        "dotall": bool - add dotall flag
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_REGEX
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


KW_STR_RE_ALL = TypedDict(
    "KW_STR_RE_ALL", {"pattern": str, "ignore_case": bool, "dotall": bool}
)


@dataclass(kw_only=True)
class ExprStringRegexAll(BaseAstNode[KW_STR_RE_ALL, tuple[str, bool, bool]]):
    """AST node representing a string regex extraction operation for all matches.

    This node represents an operation that extracts all substring matches from a string
    using a regular expression pattern, with options for case sensitivity and
    dotall matching mode. Returns a list of all matches.

    Kwargs:
        "pattern": str - regex pattern
        "ignore_case": bool - add ignorecase flag
        "dotall": bool - add dotall flag
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_REGEX_ALL
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.LIST_STRING


KW_STR_RE_SUB = TypedDict(
    "KW_STR_RE_SUB",
    {"pattern": str, "repl": str, "ignore_case": bool, "dotall": bool},
)


@dataclass(kw_only=True)
class ExprStringRegexSub(
    BaseAstNode[KW_STR_RE_SUB, tuple[str, str, bool, bool]]
):
    """AST node representing a string regex substitution operation.

    This node represents an operation that substitutes substrings in a string
    using a regular expression pattern and replacement string, with options for
    case sensitivity and dotall matching mode.

    Kwargs:
        "pattern": str - regex pattern
        "repl": str - replacement string
        "ignore_case": bool - add ignorecase flag
        "dotall": bool - add dotall flag
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_REGEX_SUB
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class ExprListStringRegexSub(
    BaseAstNode[KW_STR_RE_SUB, tuple[str, str, bool, bool]]
):
    """AST node representing a list of strings regex substitution operation.

    This node represents an operation that substitutes substrings in each string
    of a list using a regular expression pattern and replacement string, with
    options for case sensitivity and dotall matching mode.

    Kwargs:
        "pattern": str - regex pattern
        "repl": str - replacement string
        "ignore_case": bool - add ignorecase flag
        "dotall": bool - add dotall flag
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_LIST_REGEX_SUB
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.LIST_STRING


KW_STR_RM_PREFIX_OR_SUFFIX = TypedDict(
    "KW_STR_RM_PREFIX_OR_SUFFIX", {"substr": str}
)
ARGS_STR_RM_PREFIX_OR_SUFFIX = tuple[str]


@dataclass(kw_only=True)
class ExprStringRmPrefix(
    BaseAstNode[KW_STR_RM_PREFIX_OR_SUFFIX, ARGS_STR_RM_PREFIX_OR_SUFFIX]
):
    """AST node representing a string prefix removal operation.

    This node represents an operation that removes a specified prefix substring
    from the beginning of a string.

    Kwargs:
        "substr": str - remove prefix substr
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_STRING_RM_PREFIX
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class ExprStringRmSuffix(
    BaseAstNode[KW_STR_RM_PREFIX_OR_SUFFIX, ARGS_STR_RM_PREFIX_OR_SUFFIX]
):
    """AST node representing a string suffix removal operation.

    This node represents an operation that removes a specified suffix substring
    from the end of a string.

    Kwargs:
        "substr": str - remove suffix substr
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_STRING_RM_SUFFIX
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class ExprStringRmPrefixAndSuffix(
    BaseAstNode[KW_STR_RM_PREFIX_OR_SUFFIX, ARGS_STR_RM_PREFIX_OR_SUFFIX]
):
    """AST node representing a string prefix and suffix removal operation.

    This node represents an operation that removes specified prefix and suffix
    substrings from both the beginning and end of a string.

    Kwargs:
        "substr": str - remove prefix and suffix substr
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_STRING_RM_PREFIX_AND_SUFFIX
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class ExprListStringRmPrefix(
    BaseAstNode[KW_STR_RM_PREFIX_OR_SUFFIX, ARGS_STR_RM_PREFIX_OR_SUFFIX]
):
    """AST node representing a list of strings prefix removal operation.

    This node represents an operation that removes a specified prefix substring
    from the beginning of each string in a list of strings.

    Kwargs:
        "substr": str - remove prefix substr
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_LIST_STRING_RM_PREFIX
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.LIST_STRING


@dataclass(kw_only=True)
class ExprListStringRmSuffix(
    BaseAstNode[KW_STR_RM_PREFIX_OR_SUFFIX, ARGS_STR_RM_PREFIX_OR_SUFFIX]
):
    """AST node representing a list of strings suffix removal operation.

    This node represents an operation that removes a specified suffix substring
    from the end of each string in a list of strings.

    Kwargs:
        "substr": str - remove suffix substr
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_LIST_STRING_RM_SUFFIX
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.LIST_STRING


@dataclass(kw_only=True)
class ExprListStringRmPrefixAndSuffix(
    BaseAstNode[KW_STR_RM_PREFIX_OR_SUFFIX, ARGS_STR_RM_PREFIX_OR_SUFFIX]
):
    """AST node representing a list of strings prefix and suffix removal operation.

    This node represents an operation that removes specified prefix and suffix
    substrings from both the beginning and end of each string in a list of strings.

    Kwargs:
        "substr": str - remove prefix and suffix substr
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_LIST_STRING_RM_PREFIX_AND_SUFFIX
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.LIST_STRING


@dataclass(kw_only=True)
class ExprStringUnescape(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    """AST node representing a string unescape operation.

    This node represents an operation that unescapes special characters in a string,
    such as converting "\\n" to newline characters or "\\t" to tab characters.

    """

    kind: ClassVar[TokenType] = TokenType.EXPR_STRING_UNESCAPE
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class ExprListStringUnescape(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    """AST node representing a list of strings unescape operation.

    This node represents an operation that unescapes special characters in each
    string of a list, such as converting "\\n" to newline characters or "\\t" to
    tab characters.

    Attributes:
        kind: The token type for this node (TokenType.EXPR_LIST_STRING_UNESCAPE).
        accept_type: The variable type accepted by this expression (VariableType.LIST_STRING).
        ret_type: The variable type returned by this expression (VariableType.LIST_STRING).
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_LIST_STRING_UNESCAPE
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.LIST_STRING
