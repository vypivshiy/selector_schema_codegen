"""AST nodes for DOM element data extraction.

This module defines nodes that extract strings and attributes from DOM document elements:
- `Text`: Extracts stripped, whitespace-collapsed textual content from elements.
- `Raw`: Extracts raw HTML markup (either `"outer"` including tag, or `"inner"` child nodes).
- `Attr`: Extracts one or more HTML element attribute values (e.g. `href`, `src`, `data-*`).
"""

from __future__ import annotations
from dataclasses import dataclass, field

from .base import Node
from .types import TypeInfo, VariableType


@dataclass
class Text(Node):
    """Extracts stripped text content from document elements.

    Supports map semantics: `DOCUMENT -> STRING`, `LIST_DOCUMENT -> LIST_STRING`.

    Examples:
        - KDL: `text`
        - Python (bs4): `v1 = v.get_text(strip=True)`
        - JavaScript: `const v1 = v.textContent.trim();`
        - Go: `v1 := strings.TrimSpace(v.Text())`
    """

    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )


@dataclass
class Raw(Node):
    """Extracts raw HTML string markup from document elements.

    Supports map semantics: `DOCUMENT -> STRING`, `LIST_DOCUMENT -> LIST_STRING`.

    Attributes:
        mode: Extraction mode (`"outer"` includes the element tag, `"inner"` extracts children only).

    Examples:
        - KDL: `raw`, `raw inner`
        - Python (bs4 outer): `v1 = str(v)`
        - Python (bs4 inner): `v1 = "".join(str(c) for c in v.children)`
        - JavaScript: `const v1 = v.outerHTML;` / `const v1 = v.innerHTML;`
        - Go: `v1, _ := goquery.OuterHtml(v)` / `v1, _ := v.Html()`
    """

    mode: str = "outer"
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )


@dataclass
class Attr(Node):
    """Extracts specified attribute value(s) from document elements.

    If a single key is specified: returns `STRING` (or raises error / returns empty string if missing).
    If multiple keys are specified: returns `LIST_STRING` containing existing attribute values.

    Attributes:
        keys: Tuple of attribute names to retrieve from the element.

    Examples:
        - KDL: `attr "href"`, `attr "data-id" "id"`
        - Python: `v1 = v.get("href", "")`
        - JavaScript: `const v1 = v.getAttribute("href") || "";`
        - Go: `v1, _ := v.Attr("href")`
    """

    keys: tuple[str, ...] = field(default_factory=tuple)
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.DOCUMENT)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )
