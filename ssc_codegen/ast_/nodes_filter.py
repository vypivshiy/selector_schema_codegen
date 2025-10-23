from dataclasses import dataclass
from typing import TypedDict, ClassVar

from ssc_codegen.ast_.base import BaseAstNode, T_EMPTY_KWARGS
from ssc_codegen.tokens import TokenType, VariableType


# TODO: static analyzer for filter operations
# TODO: implement operators for DOCUMENT, INT, FLOAT


@dataclass(kw_only=True)
class FilterOr(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    """AST node representing a logical OR filter operation.

    This node represents a logical OR operation that combines multiple filter
    conditions. It can be reused in element filters and accepts string or
    document types, but is currently typed as ANY for flexibility.

    body accept all filter-like operations and combine all by logical AND
    """

    kind: ClassVar[TokenType] = TokenType.FILTER_OR
    # cast for reuse in Elements filters
    # real accept: VariableType.STRING, VariableType.DOCUMENT
    accept_type: VariableType = VariableType.ANY
    ret_type: VariableType = VariableType.ANY


@dataclass(kw_only=True)
class FilterAnd(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    """AST node representing a logical AND filter operation.

    This node represents a logical AND operation that combines multiple filter
    conditions. It accepts any variable type as input and returns any type.

    body accept all filter-like operations and combine all by logical AND
    """

    kind: ClassVar[TokenType] = TokenType.FILTER_AND
    # cast for reuse in Elements filters
    # real accept: VariableType.STRING, VariableType.DOCUMENT
    accept_type: VariableType = VariableType.ANY
    ret_type: VariableType = VariableType.ANY


@dataclass(kw_only=True)
class FilterNot(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    """AST node representing a logical NOT filter operation.

    This node represents a logical NOT operation that negates a filter condition.
    It accepts any variable type as input and returns any type.

    body accept all filter-like operations and combine all by logical AND
    """

    kind: ClassVar[TokenType] = TokenType.FILTER_NOT
    # cast for reuse in Elements filters
    # real accept: VariableType.STRING, VariableType.DOCUMENT
    accept_type: VariableType = VariableType.ANY
    ret_type: VariableType = VariableType.ANY


KW_STR_IN = TypedDict("KW_STR_IN", {"substr": tuple[str, ...]})
ARGS_STR_IN = tuple[tuple[str, ...]]

KW_STR_STARTS_OR_ENDS = TypedDict(
    "KW_STR_STARTS_OR_ENDS", {"substr": tuple[str, ...]}
)
ARGS_STR_STARTS_OR_ENDS = tuple[tuple[str, ...]]


@dataclass(kw_only=True)
class FilterStrIn(BaseAstNode[KW_STR_IN, ARGS_STR_IN]):
    """AST node representing a string inclusion filter operation.

    This node represents a filter that checks if a string contains any of the
    specified substrings from a given tuple of possible substrings.

    If more than 1 argument is passed, they must be converted to a logical OR

    Pseudocode Example:

        ```
        F().contains("a")  # "a" in v

        F().contains("a", "b", "c") # any(i in v for i in ["a", "b", "c"])
        ```
    Kwargs:
        "substr": tuple[str, ...] - strings that must be included.
    """

    kind: ClassVar[TokenType] = TokenType.FILTER_STR_IN
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class FilterStrStarts(
    BaseAstNode[KW_STR_STARTS_OR_ENDS, ARGS_STR_STARTS_OR_ENDS]
):
    """AST node representing a string starts-with filter operation.

    This node represents a filter that checks if a string starts with any of the
    specified substrings from a given tuple of possible starting substrings.

    If more than 1 argument is passed, they must be converted to a logical OR

    Pseudocode Example:

        ```
        F().starts("a")  # v.startswith("a")

        F().contains("a", "b", "c")  # any(v.startswith(i) for i in ["a", "b", "c"])
        ```

    Kwargs:
        "substr": tuple[str, ...] - strings that must be included.
    """

    kind: ClassVar[TokenType] = TokenType.FILTER_STR_STARTS
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class FilterStrEnds(
    BaseAstNode[KW_STR_STARTS_OR_ENDS, ARGS_STR_STARTS_OR_ENDS]
):
    """AST node representing a string ends-with filter operation.

    This node represents a filter that checks if a string ends with any of the
    specified substrings from a given tuple of possible ending substrings.

    If more than 1 argument is passed, they must be converted to a logical OR

    Pseudocode Example:

        ```
        F().ends("a")  # v.endswith("a")

        F().contains("a", "b", "c")  # any(v.endswith(i) for i in ["a", "b", "c"])
        ```

    Kwargs:
        "substr": tuple[str, ...] - strings that must be included.
    """

    kind: ClassVar[TokenType] = TokenType.FILTER_STR_ENDS
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


KW_STR_RE = TypedDict("KW_STR_RE", {"pattern": str, "ignore_case": bool})
ARGS_STR_RE = tuple[str, bool]


@dataclass(kw_only=True)
class FilterStrRe(BaseAstNode[KW_STR_RE, ARGS_STR_RE]):
    """AST node representing a string regex filter operation.

    This node represents a filter that checks if a string matches a specified
    regular expression pattern, with optional case-insensitive matching.

    Kwargs:
        "pattern": str - regex pattern
        "ignore_case": bool - add re.I flag (ignorecase)
    """

    kind: ClassVar[TokenType] = TokenType.FILTER_STR_RE
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


KW_STR_LEN = TypedDict("KW_STR_LEN", {"length": int})
ARGS_STR_LEN = tuple[int]


@dataclass(kw_only=True)
class FilterStrLenEq(BaseAstNode[KW_STR_LEN, ARGS_STR_LEN]):
    """AST node representing a string length equals filter operation.

    This node represents a filter that checks if the length of a string equals
    the specified length value.

    Kwargs:
        "length": int - string lenght value
    """

    kind: ClassVar[TokenType] = TokenType.FILTER_STR_LEN_EQ
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class FilterStrLenNe(BaseAstNode[KW_STR_LEN, ARGS_STR_LEN]):
    """AST node representing a string length not-equals filter operation.

    This node represents a filter that checks if the length of a string does not equal
    the specified length value.

    Kwargs:
        "length": int - string lenght value
    """

    kind: ClassVar[TokenType] = TokenType.FILTER_STR_LEN_NE
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class FilterStrLenLt(BaseAstNode[KW_STR_LEN, ARGS_STR_LEN]):
    """AST node representing a string length less-than filter operation.

    This node represents a filter that checks if the length of a string is less than
    the specified length value.

    Kwargs:
        "length": int - string lenght value
    """

    kind: ClassVar[TokenType] = TokenType.FILTER_STR_LEN_LT
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class FilterStrLenLe(BaseAstNode[KW_STR_LEN, ARGS_STR_LEN]):
    """AST node representing a string length less-equals filter operation.

    This node represents a filter that checks if the length of a string is less than
    or equal to the specified length value.

    Kwargs:
        "length": int - string lenght value
    """

    kind: ClassVar[TokenType] = TokenType.FILTER_STR_LEN_LE
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class FilterStrLenGt(BaseAstNode[KW_STR_LEN, ARGS_STR_LEN]):
    """AST node representing a string length greater-than filter operation.

    This node represents a filter that checks if the length of a string is greater than
    the specified length value.

    Kwargs:
        "length": int - string lenght value
    """

    kind: ClassVar[TokenType] = TokenType.FILTER_STR_LEN_GT
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class FilterStrLenGe(BaseAstNode[KW_STR_LEN, ARGS_STR_LEN]):
    """AST node representing a string length greater-equals filter operation.

    This node represents a filter that checks if the length of a string is greater than
    or equal to the specified length value.

    Kwargs:
        "length": int - string lenght value
    """

    kind: ClassVar[TokenType] = TokenType.FILTER_STR_LEN_GE
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


# TODO: provide API for int, float, etc
KW_STR_EQ_OR_NE = TypedDict("KW_STR_EQ_OR_NE", {"values": tuple[str, ...]})
ARGS_STR_EQ_OR_NE = tuple[tuple[str, ...]]


@dataclass(kw_only=True)
class FilterEqual(BaseAstNode[KW_STR_EQ_OR_NE, ARGS_STR_EQ_OR_NE]):
    """AST node representing a string equality filter operation.

    This node represents a filter that checks if a string equals any of the
    specified values from a given tuple of possible values.

    Kwargs:
        "length": int - string lenght value
    """

    kind: ClassVar[TokenType] = TokenType.FILTER_EQ
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class FilterNotEqual(BaseAstNode[KW_STR_EQ_OR_NE, ARGS_STR_EQ_OR_NE]):
    """AST node representing a string not-equality filter operation.

    This node represents a filter that checks if a string does not equal any of the
    specified values from a given tuple of possible values.

    Kwargs:
        "length": int - string lenght value
    """

    kind: ClassVar[TokenType] = TokenType.FILTER_NE
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class ExprFilter(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    """AST node representing a general filter operation on a list of strings.

    This node represents a filter operation that filters elements in a list of strings,
    returning only those elements that match the filter criteria specified in the
    body of the node.
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_FILTER
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.LIST_STRING
    # TODO: typing body accept Filter-like nodes


# Elements filters
@dataclass(kw_only=True)
class ExprDocumentFilter(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    """AST node representing a filter operation on a list of documents.

    This node represents a filter operation that filters elements in a list of documents,
    returning only those documents that match the filter criteria specified in the
    body of the node.
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_DOC_FILTER
    accept_type: VariableType = VariableType.LIST_DOCUMENT
    ret_type: VariableType = VariableType.LIST_DOCUMENT


KW_FILTER_CSS_OR_XPATH = TypedDict("KW_FILTER_CSS", {"query": str})
ARGS_FILTER_CSS_OR_XPATH = tuple[str]


@dataclass(kw_only=True)
class FilterDocCss(
    BaseAstNode[KW_FILTER_CSS_OR_XPATH, ARGS_FILTER_CSS_OR_XPATH]
):
    """AST node representing a CSS selector filter operation on a document.

    This node represents a filter that uses a CSS selector query to filter
    elements within a document, returning only those elements that match
    the CSS selector pattern.

    Kwargs:
        "query": str - css query selector
    """

    kind: ClassVar[TokenType] = TokenType.FILTER_DOC_CSS
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT


@dataclass(kw_only=True)
class FilterDocXpath(
    BaseAstNode[KW_FILTER_CSS_OR_XPATH, ARGS_FILTER_CSS_OR_XPATH]
):
    """AST node representing an XPath selector filter operation on a document.

    This node represents a filter that uses an XPath query to filter
    elements within a document, returning only those elements that match
    the XPath expression.

    Kwargs:
        "query": str - xpath query selector
    """

    kind: ClassVar[TokenType] = TokenType.FILTER_DOC_XPATH
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT


KW_FILTER_HAS_TEXT = TypedDict(
    "KW_FILTER_HAS_TEXT", {"values": tuple[str, ...]}
)
ARGS_FILTER_HAS_TEXT = tuple[tuple[str, ...]]


@dataclass(kw_only=True)
class FilterDocHasText(BaseAstNode[KW_FILTER_HAS_TEXT, ARGS_FILTER_HAS_TEXT]):
    """AST node representing a document text filter operation.

    This node represents a filter that checks if a document contains any of the
    specified text values from a given tuple of possible text values.

    multiple values converts to logical OR

    Pseudocode Example:

    ```
    FE().has_text("foo") -> "foo" in element.textContent
    FE().has_text("bar", "foo") -> any(i in element.textContent for i in ("bar", "foo"))
    ```

    Kwargs:
        "values": tuple[str, ...] - text(s) where required contains in element
    """

    kind: ClassVar[TokenType] = TokenType.FILTER_DOC_HAS_TEXT
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT


@dataclass(kw_only=True)
class FilterDocHasRaw(BaseAstNode[KW_FILTER_HAS_TEXT, ARGS_FILTER_HAS_TEXT]):
    """AST node representing a document raw content filter operation.

    This node represents a filter that checks if a document contains any of the
    specified raw content values from a given tuple of possible raw content values.

    multiple values converts to logical OR

    Pseudocode Example:

    ```
    FE().has_raw("foo") -> "foo" in element.outerHTML
    FE().has_raw("bar", "foo") -> any(i in element.outerHTML for i in ("bar", "foo"))
    ```

    Kwargs:
        "values": tuple[str, ...] - text(s) where required contains in element
    """

    kind: ClassVar[TokenType] = TokenType.FILTER_DOC_HAS_RAW
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT


KW_FILTER_HAS_ATTR = TypedDict("KW_FILTER_HAS_ATTR", {"keys": tuple[str, ...]})
ARGS_FILTER_HAS_ATTR = tuple[tuple[str, ...]]


@dataclass(kw_only=True)
class FilterDocHasAttr(BaseAstNode[KW_FILTER_HAS_ATTR, ARGS_FILTER_HAS_ATTR]):
    """AST node representing a document attribute presence filter operation.

    This node represents a filter that checks if a document has any of the
    specified attributes from a given tuple of possible attribute keys.

    multiple values converts to logical OR

    Pseudocode Example:

    ```
    FE().has_attr("href") -> element.get("href")
    FE().has_attr("href", "src") -> any(element.hasAttribute(i) for i in ("href", "src"))
    ```

    Kwargs:
        "keys": tuple[str, ...] - attr key(s) where required in element
    """

    kind: ClassVar[TokenType] = TokenType.FILTER_DOC_HAS_ATTR
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT


KW_FILTER_ATTR = TypedDict(
    "KW_FILTER_ATTR", {"key": str, "values": tuple[str, ...]}
)
ARGS_FILTER_ATTR = tuple[str, tuple[str, ...]]


@dataclass(kw_only=True)
class FilterDocAttrEqual(BaseAstNode[KW_FILTER_ATTR, ARGS_FILTER_ATTR]):
    """AST node representing a document attribute equality filter operation.

    This node represents a filter that checks if a document's attribute equals
    any of the specified values for the given attribute key.

    multiple values converts to logical OR

    TIP:
        current ssc-gen implementation include auto add check key exists in element (FilterDocHasAttr node)

    Pseudocode Example:

    ```
    FE().attr_eq("href", "example.com") -> element["href"] == "example.com"
    FE().attr_eq("href", "foo", "bar") -> any(element["href"] == k for k in ("href", "foo", "bar"))
    ```

    Kwargs:
        "key": str - attribute key
        "values": tuple[str, ...] - attribute values
    """

    kind: ClassVar[TokenType] = TokenType.FILTER_DOC_ATTR_EQ
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT


@dataclass(kw_only=True)
class FilterDocAttrStarts(BaseAstNode[KW_FILTER_ATTR, ARGS_FILTER_ATTR]):
    """AST node representing a document attribute starts-with filter operation.

    This node represents a filter that checks if a document's attribute starts
    with any of the specified values for the given attribute key.

    multiple values converts to logical OR

    TIP:
        current ssc-gen implementation include auto add check key exists in element (FilterDocHasAttr node)

    Pseudocode Example:

    ```
    FE().attr_starts("href", "example.com") -> element["href"].startswith("example.com")
    FE().attr_starts("href", "foo", "bar") -> any(element["href"].startswith(k) for k in ("href", "foo", "bar"))
    ```

    Kwargs:
        "key": str - attribute key
        "values": tuple[str, ...] - attribute values
    """

    kind: ClassVar[TokenType] = TokenType.FILTER_DOC_ATTR_STARTS
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT


@dataclass(kw_only=True)
class FilterDocAttrEnds(BaseAstNode[KW_FILTER_ATTR, ARGS_FILTER_ATTR]):
    """AST node representing a document attribute ends-with filter operation.

    This node represents a filter that checks if a document's attribute ends
    with any of the specified values for the given attribute key.

    multiple values converts to logical OR

    TIP:
        current ssc-gen implementation include auto add check key exists in element (FilterDocHasAttr node)

    Pseudocode Example:

    ```
    FE().attr_starts("href", "example.com") -> element["href"].endswith("example.com")
    FE().attr_starts("href", "foo", "bar") -> any(element["href"].endswith(k) for k in ("href", "foo", "bar"))
    ```

    Kwargs:
        "key": str - attribute key
        "values": tuple[str, ...] - attribute values
    """

    kind: ClassVar[TokenType] = TokenType.FILTER_DOC_ATTR_ENDS
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT


@dataclass(kw_only=True)
class FilterDocAttrContains(BaseAstNode[KW_FILTER_ATTR, ARGS_FILTER_ATTR]):
    """AST node representing a document attribute contains filter operation.

    This node represents a filter that checks if a document's attribute
    contains any of the specified values for the given attribute key.

    multiple values converts to logical OR

    TIP:
        current ssc-gen implementation include auto add check key exists in element (FilterDocHasAttr node)

    Pseudocode Example:

    ```
    FE().attr_contains("href", "example.com") -> "example.com" in element["href"]
    FE().attr_starts("href", "foo", "bar") -> any(k in element["href"] for k in ("href", "foo", "bar"))
    ```

    Kwargs:
        "key": str - attribute key
        "values": tuple[str, ...] - attribute values
    """

    kind: ClassVar[TokenType] = TokenType.FILTER_DOC_ATTR_CONTAINS
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT


KW_FILTER_ATTR_RE = TypedDict(
    "KW_FILTER_ATTR", {"key": str, "pattern": str, "ignore_case": bool}
)
ARGS_FILTER_ATTR_RE = tuple[str, str, bool]


@dataclass(kw_only=True)
class FilterDocAttrRegex(BaseAstNode[KW_FILTER_ATTR_RE, ARGS_FILTER_ATTR_RE]):
    """AST node representing a document attribute regex filter operation.

    This node represents a filter that checks if a document's attribute matches
    a specified regular expression pattern for the given attribute key.

    TIP:
        current ssc-gen implementation include auto add check key exists in element (FilterDocHasAttr node)

    Kwargs:
        "key": str - attribute key
        "pattern": str - regex pattern
        "ignore_case": bool - add ignorecase flag
    """

    kind: ClassVar[TokenType] = TokenType.FILTER_DOC_ATTR_RE_MATCH
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT


KW_FILTER_IS_REGEX = TypedDict(
    "KW_FILTER_IS_REGEX", {"pattern": str, "ignore_case": bool}
)
ARGS_FILTER_IS_REGEX = tuple[str, bool]


@dataclass(kw_only=True)
class FilterDocIsRegexText(
    BaseAstNode[KW_FILTER_IS_REGEX, ARGS_FILTER_IS_REGEX]
):
    """AST node representing a document text regex filter operation.

    This node represents a filter that checks if the text content of a document
    matches a specified regular expression pattern.

    Kwargs:
        "pattern": str - regex pattern
        "ignore_case": bool - add ignorecase flag
    """

    kind: ClassVar[TokenType] = TokenType.FILTER_DOC_IS_RE_TEXT
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT


@dataclass(kw_only=True)
class FilterDocIsRegexRaw(
    BaseAstNode[KW_FILTER_IS_REGEX, ARGS_FILTER_IS_REGEX]
):
    """AST node representing a document raw content regex filter operation.

    This node represents a filter that checks if the raw content of a document
    matches a specified regular expression pattern.

    Kwargs:
        "pattern": str - regex pattern
        "ignore_case": bool - add ignorecase flag
    """

    kind: ClassVar[TokenType] = TokenType.FILTER_DOC_IS_RE_RAW
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT
