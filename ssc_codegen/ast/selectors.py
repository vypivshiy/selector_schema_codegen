from __future__ import annotations
import warnings
from dataclasses import dataclass, field

from .base import Node
from .types import TypeInfo, VariableType


@dataclass
class CssSelect(Node):
    """Selects the first matching child element using CSS selectors.

    Attributes:
        queries: Ordered sequence of fallback CSS selector query strings.

    Examples:
        - KDL: `css ".title"`, `css "h1.heading" "h2.heading"`
        - Python (bs4): `v1 = v.select_one(".title")`
        - JavaScript: `const v1 = v.querySelector(".title");`
        - Go: `v1 := v.Find(".title").First()`
    """

    queries: list[str] = field(default_factory=list)
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )

    @property
    def query(self) -> str:
        """Deprecated property returning the first CSS query.

        Warning:
            Deprecated: Use `queries` instead.
        """
        warnings.warn(
            "CssSelect.query is deprecated; use CssSelect.queries instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.queries[0]


@dataclass
class CssSelectAll(Node):
    """Selects all matching child elements as a list using CSS selectors.

    Attributes:
        queries: Ordered sequence of fallback CSS selector query strings.

    Examples:
        - KDL: `css-all ".item"`
        - Python (bs4): `v1 = v.select(".item")`
        - JavaScript: `const v1 = Array.from(v.querySelectorAll(".item"));`
        - Go: `v1 := v.Find(".item")`
    """

    queries: list[str] = field(default_factory=list)
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(
            base=VariableType.DOCUMENT, is_array=True
        )
    )

    @property
    def query(self) -> str:
        """Deprecated property returning the first CSS query.

        Warning:
            Deprecated: Use `queries` instead.
        """
        warnings.warn(
            "CssSelectAll.query is deprecated; use CssSelectAll.queries instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.queries[0]


@dataclass
class XpathSelect(Node):
    """Selects the first matching child element using XPath expressions.

    Attributes:
        queries: Ordered sequence of fallback XPath query strings.

    Examples:
        - KDL: `xpath "//h1"`
        - Python (lxml): `v1 = v.xpath("//h1")[0]`
    """

    queries: list[str] = field(default_factory=list)
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )

    @property
    def query(self) -> str:
        """Deprecated property returning the first XPath query.

        Warning:
            Deprecated: Use `queries` instead.
        """
        warnings.warn(
            "XpathSelect.query is deprecated; use XpathSelect.queries instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.queries[0]


@dataclass
class XpathSelectAll(Node):
    """Selects all matching child elements as a list using XPath expressions.

    Attributes:
        queries: Ordered sequence of fallback XPath query strings.

    Examples:
        - KDL: `xpath-all "//a"`
        - Python (lxml): `v1 = v.xpath("//a")`
    """

    queries: list[str] = field(default_factory=list)
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(
            base=VariableType.DOCUMENT, is_array=True
        )
    )

    @property
    def query(self) -> str:
        """Deprecated property returning the first XPath query.

        Warning:
            Deprecated: Use `queries` instead.
        """
        warnings.warn(
            "XpathSelectAll.query is deprecated; use XpathSelectAll.queries instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.queries[0]


@dataclass
class CssRemove(Node):
    """Removes matching elements from the document in-place and passes the document forward.

    Attributes:
        query: CSS selector identifying elements to remove from the tree.

    Examples:
        - KDL: `css-remove ".ads"`
        - Python (bs4): `for el in v.select(".ads"): el.decompose()`
        - JavaScript: `v.querySelectorAll(".ads").forEach(e => e.remove());`
        - Go: `v.Find(".ads").Remove()`
    """

    query: str = ""
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )


@dataclass
class XpathRemove(Node):
    """Removes matching elements from the document in-place and passes the document forward.

    Attributes:
        query: XPath expression identifying elements to remove from the tree.

    Examples:
        - KDL: `xpath-remove "//script"`
        - Python: `for el in v.xpath("//script"): el.getparent().remove(el)`
    """

    query: str = ""
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )
