from dataclasses import dataclass
from typing import TypedDict, ClassVar

from ssc_codegen.tokens import TokenType, VariableType
from ssc_codegen.ast_.base import BaseAstNode, T_EMPTY_KWARGS

KW_EXPR_SELECTOR_LIKE = TypedDict("KW_EXPR_SELECTOR_LIKE", {"query": str})
ARGS_EXPR_SELECTOR_LIKE = tuple[str]


@dataclass(kw_only=True)
class ExprCss(BaseAstNode[KW_EXPR_SELECTOR_LIKE, ARGS_EXPR_SELECTOR_LIKE]):
    """AST node representing a CSS selector expression.

    This node represents a CSS selector operation that selects a single element
    from a document using a CSS query. It accepts a document and returns a document
    containing the selected element.

    Kwargs:
        "query": str - css query selector
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_CSS
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT


@dataclass(kw_only=True)
class ExprCssAll(BaseAstNode[KW_EXPR_SELECTOR_LIKE, ARGS_EXPR_SELECTOR_LIKE]):
    """AST node representing a CSS selector expression for multiple elements.

    This node represents a CSS selector operation that selects all elements
    from a document using a CSS query. It accepts a document and returns a list
    of documents containing the selected elements.

    Kwargs:
        "query": str - css query selector
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_CSS_ALL
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.LIST_DOCUMENT


@dataclass(kw_only=True)
class ExprXpath(BaseAstNode[KW_EXPR_SELECTOR_LIKE, ARGS_EXPR_SELECTOR_LIKE]):
    """AST node representing an XPath selector expression.

    This node represents an XPath selector operation that selects a single element
    from a document using an XPath query. It accepts a document and returns a document
    containing the selected element.

    Kwargs:
        "query": str - xpath query selector
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_XPATH
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT


@dataclass(kw_only=True)
class ExprXpathAll(BaseAstNode[KW_EXPR_SELECTOR_LIKE, ARGS_EXPR_SELECTOR_LIKE]):
    """AST node representing an XPath selector expression for multiple elements.

    This node represents an XPath selector operation that selects all elements
    from a document using an XPath query. It accepts a document and returns a list
    of documents containing the selected elements.

    Kwargs:
        "query": str - xpath query selector
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_XPATH_ALL
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.LIST_DOCUMENT


KW_EXPR_ATTR = TypedDict("KW_EXPR_ATTR", {"key": tuple[str, ...]})
ARGS_EXPR_ATTR = tuple[tuple[str, ...]]


@dataclass(kw_only=True)
class ExprGetHtmlAttr(BaseAstNode[KW_EXPR_ATTR, ARGS_EXPR_ATTR]):
    """AST node representing an HTML attribute extraction expression.

    This node represents an operation that extracts the value of an HTML attribute
    from a document element. It accepts a document and returns the attribute value
    as a string.

    if single key passed - check as it and maybe throw exception, if key not exists
    if several keys passed - try extract all attributes by keys and returns array of strings

    Pseudocode example:

        ```
        D().css("a").attr("href")
        # v1 = v.css("a")
        # v2 = v1["href"] # maybe throw error!

        D().css("[href],[src],[onclick]").attr("href", "src", "onclick")
        # simplifed example for demo
        # v1 = v.css("[href],[src],[onclick]")
        # v2 = []
        # for a in ("href", "src", "onclick"):
        #    if v1.get(a):
        #        v2.append(v1[a])
        ```

    Kwargs:
        "key": tuple[str, ...] - arribute key(s)
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_ATTR
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class ExprGetHtmlAttrAll(BaseAstNode[KW_EXPR_ATTR, ARGS_EXPR_ATTR]):
    """AST node representing an HTML attribute extraction expression for multiple elements.

    This node represents an operation that extracts the values of an HTML attribute
    from all document elements in a list. It accepts a list of documents and returns
    a list of attribute values as strings.


    if single key passed - check as it and maybe throw exception, if key not exists
    if several keys passed - try extract all attributes by keys and returns array of strings

    Pseudocode example:

        ```
        D().css("a").attr("href")
        # v1 = v.css_all("a")
        # v2 = [i["href"] for i in v1]

        D().css("[href],[src],[onclick]").attr("href", "src", "onclick")
        # simplifed example for demo
        # v1 = v.css_all("[href],[src],[onclick]")
        # v2 = []
        # for i in v1:
        #   for a in ("href", "src", "onclick"):
        #       if i.get(a):
        #           v2.append(i[a])
        ```

    Kwargs:
        "key": tuple[str, ...] - arribute key(s)
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_ATTR_ALL
    accept_type: VariableType = VariableType.LIST_DOCUMENT
    ret_type: VariableType = VariableType.LIST_STRING


@dataclass(kw_only=True)
class ExprGetHtmlText(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    """AST node representing an HTML text extraction expression.

    This node represents an operation that extracts the text content from a document
    element. It accepts a document and returns the text content as a string.
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_TEXT
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class ExprGetHtmlTextAll(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    """AST node representing an HTML text extraction expression for multiple elements.

    This node represents an operation that extracts the text content from all
    document elements in a list. It accepts a list of documents and returns a
    list of text contents as strings.
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_TEXT_ALL
    accept_type: VariableType = VariableType.LIST_DOCUMENT
    ret_type: VariableType = VariableType.LIST_STRING


@dataclass(kw_only=True)
class ExprGetHtmlRaw(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    """AST node representing an HTML raw content extraction expression.

    This node represents an operation that extracts the raw HTML content from a
    document element. It accepts a document and returns the raw HTML content as a string.
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_RAW
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class ExprGetHtmlRawAll(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    """AST node representing an HTML raw content extraction expression for multiple elements.

    This node represents an operation that extracts the raw HTML content from all
    document elements in a list. It accepts a list of documents and returns a list
    of raw HTML contents as strings.
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_RAW_ALL
    accept_type: VariableType = VariableType.LIST_DOCUMENT
    ret_type: VariableType = VariableType.LIST_STRING


@dataclass(kw_only=True)
class ExprMapAttrs(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    """AST node representing an HTML attributes mapping expression.

    This node represents an operation that maps all HTML attributes from a
    document element to a list of strings. It accepts a document and returns
    a list of attribute values as strings.

    Pseudocode example:

        ```
        D().css("div").attrs_map()
        # v1 = v.css("div")
        # extract all attribute values
        # v2 = [i for i in v.attrs.values()]
        ```
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_MAP_ATTRS
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.LIST_STRING


@dataclass(kw_only=True)
class ExprMapAttrsAll(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    """AST node representing an HTML attributes mapping expression for multiple elements.

    This node represents an operation that maps all HTML attributes from all
    document elements in a list to a list of strings. It accepts a list of
    documents and returns a list of attribute values as strings.

        Pseudocode example:

        ```
        D().css_all("div").attrs_map()
        # v1 = v.css_all("div")
        # v2 = []
        # # extract all attribute values
        # for i in v1:
        #     for val in i.attr.values():
        #         v2.append(val)
        ```
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_MAP_ATTRS_ALL
    accept_type: VariableType = VariableType.LIST_DOCUMENT
    ret_type: VariableType = VariableType.LIST_STRING


KW_EXPR_SELECTOR_REMOVE = TypedDict("KW_EXPR_SELECTOR_REMOVE", {"query": str})
ARGS_EXPR_SELECTOR_REMOVE = tuple[str]


@dataclass(kw_only=True)
class ExprCssElementRemove(
    BaseAstNode[KW_EXPR_SELECTOR_REMOVE, ARGS_EXPR_SELECTOR_REMOVE]
):
    """AST node representing a CSS element removal expression.

    This node represents an operation that removes elements from a document
    using a CSS selector query. It accepts a document and returns a document
    with the matched elements removed.

    NOTE:
        - this operation add side effect and remove elements from original document instance wout create copy

    Kwargs:
        "query": str - css query selector
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_CSS_REMOVE
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT


@dataclass(kw_only=True)
class ExprXpathElementRemove(
    BaseAstNode[KW_EXPR_SELECTOR_REMOVE, ARGS_EXPR_SELECTOR_REMOVE]
):
    """AST node representing an XPath element removal expression.

    This node represents an operation that removes elements from a document
    using an XPath selector query. It accepts a document and returns a document
    with the matched elements removed.

    NOTE:
        - this operation add side effect and remove elements from original document instance wout create copy

    Kwargs:
        "query": str - xpath query selector
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_XPATH_REMOVE
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT
