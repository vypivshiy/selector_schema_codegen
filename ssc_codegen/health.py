"""Selector health verification against real HTML documents.

This module inspects AST structs, extracts all selector queries (CSS, CSS-all,
XPath, XPath-all, remove filters, fallback defaults), and evaluates them against
provided HTML to detect broken or fragile selectors without running code generation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Literal

from ssc_codegen.ast import (
    CssRemove,
    CssSelect,
    CssSelectAll,
    Fallback,
    Field,
    InitField,
    Key,
    Module,
    Nested,
    PreValidate,
    SplitDoc,
    Struct,
    StructBase,
    StructType,
    TableConfig,
    TableMatchKey,
    TableRows,
    Value,
    XpathRemove,
    XpathSelect,
    XpathSelectAll,
)
from ssc_codegen.ast.base import Node as AstNode

# selector types that expect exactly one match (or non-None)
_SINGLE_SELECTORS = (CssSelect, XpathSelect)
# selector types that expect >0 matches
_MULTI_SELECTORS = (CssSelectAll, XpathSelectAll)
# remove selectors — not finding anything is not an error
_REMOVE_SELECTORS = (CssRemove, XpathRemove)

_CSS_TYPES = (CssSelect, CssSelectAll, CssRemove)
_XPATH_TYPES = (XpathSelect, XpathSelectAll, XpathRemove)


@dataclass
class SelectorCheck:
    """Result of checking a single selector expression against HTML.

    Attributes:
        path: Dot-separated AST path of the selector (e.g. `"Book.title"`, `"Book.@split-doc"`).
        selector_type: Type descriptor of the selector (`"css"`, `"css-all"`, `"xpath"`, `"xpath-all"`).
        query: Raw selector query string.
        matches: Number of matching elements found in the document.
        status: Evaluation status (`"ok"`, `"fail"`, or `"warn"`).
        message: Informational message or reason for warning/failure.
        fallback_value: Representation of the fallback default value if present.
    """

    path: str
    selector_type: str
    query: str
    matches: int
    status: Literal["ok", "fail", "warn"]
    message: str = ""
    fallback_value: str | None = None

    def to_dict(self) -> dict:
        """Convert selector check result to a dictionary representation.

        Returns:
            Dictionary containing selector path, type, query, matches count, and status.
        """
        d = {
            "path": self.path,
            "selector_type": self.selector_type,
            "query": self.query,
            "matches": self.matches,
            "status": self.status,
            "message": self.message,
        }
        if self.fallback_value is not None:
            d["fallback"] = self.fallback_value
        return d


@dataclass
class HealthResult:
    """Aggregated health check result for a struct and its nested dependencies.

    Attributes:
        struct_name: Name of the checked root struct.
        checks: List of individual `SelectorCheck` records.

    Examples:
        ```python
        from ssc_codegen import check_struct_health, parse_module

        kdl_source = '''
        (item)struct Book {
            title "h1.title" { text }
            price ".price" { text }
        }
        '''
        ast, _ = parse_module(kdl_source)
        book_struct = ast.body[0]
        html = '<div class="book"><h1 class="title">Demo</h1></div>'

        result = check_struct_health(book_struct, html, module=ast)
        print(result.has_failures())  # True (price failed)
        print(result.format(fmt="text"))
        ```
    """

    struct_name: str
    checks: list[SelectorCheck] = field(default_factory=list)

    @property
    def failed(self) -> list[SelectorCheck]:
        """List of failed selector checks (0 matches without fallback)."""
        return [c for c in self.checks if c.status == "fail"]

    @property
    def warnings(self) -> list[SelectorCheck]:
        """List of warning selector checks (0 matches with fallback or remove selector)."""
        return [c for c in self.checks if c.status == "warn"]

    @property
    def ok(self) -> list[SelectorCheck]:
        """List of successful selector checks."""
        return [c for c in self.checks if c.status == "ok"]

    def has_failures(self) -> bool:
        """Return True if any selector check failed.

        Returns:
            True if failed checks exist, False otherwise.
        """
        return len(self.failed) > 0

    def format(self, fmt: Literal["text", "json"] = "text") -> str:
        """Format the health check summary as human-readable text or JSON.

        Args:
            fmt: Output formatting style, either `"text"` or `"json"`.

        Returns:
            Formatted string report.
        """
        if fmt == "json":
            return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)
        return self._format_text()

    def to_dict(self) -> dict:
        """Convert health results and summary metrics to a dictionary.

        Returns:
            Dictionary with struct name, checks list, total, ok, failed, and warning counts.
        """
        return {
            "struct": self.struct_name,
            "checks": [c.to_dict() for c in self.checks],
            "total": len(self.checks),
            "ok": len(self.ok),
            "failed": len(self.failed),
            "warnings": len(self.warnings),
        }

    def _format_text(self) -> str:
        if not self.checks:
            return f"{self.struct_name}: no selectors found"

        lines: list[str] = []
        max_path = max(len(c.path) for c in self.checks)
        max_type = max(len(c.selector_type) for c in self.checks)

        for c in self.checks:
            status_str = {
                "ok": "OK",
                "fail": "FAIL",
                "warn": "WARN",
            }[c.status]
            detail = (
                f"({c.matches} matches)"
                if c.status != "fail"
                else "(0 matches)"
            )
            if c.message:
                detail = c.message
            lines.append(
                f"  {c.path:<{max_path}}  {c.selector_type:<{max_type}}  "
                f"{c.query!r:<40}  {status_str}  {detail}"
            )

        total = len(self.checks)
        n_ok = len(self.ok)
        n_fail = len(self.failed)
        n_warn = len(self.warnings)
        summary_parts = []
        if n_ok:
            summary_parts.append(f"{n_ok} ok")
        if n_fail:
            summary_parts.append(f"{n_fail} failed")
        if n_warn:
            summary_parts.append(f"{n_warn} warnings")

        header = f"{self.struct_name}: {total} selectors checked — {', '.join(summary_parts)}"
        return header + "\n" + "\n".join(lines)


@dataclass
class _SelectorInfo:
    """Internal: a collected selector with its context."""

    path: str
    node: AstNode
    fallback_value: str | None = None


@dataclass
class _NestedRef:
    """Internal: a nested struct reference found in a pipeline."""

    path: str
    struct_name: str


def _find_fallback(node: AstNode) -> str | None:
    """Check if a pipeline node contains a Fallback and return its repr value."""
    for child in node.body:
        if isinstance(child, Fallback):
            return repr(child.value)
    return None


def _collect_selectors(
    node: AstNode, path_prefix: str, fallback: str | None = None
) -> tuple[list[_SelectorInfo], list[_NestedRef]]:
    """Walk AST node tree and collect all selector nodes and nested references."""
    selectors: list[_SelectorInfo] = []
    nested_refs: list[_NestedRef] = []

    for child in node.body:
        if isinstance(
            child, _SINGLE_SELECTORS + _MULTI_SELECTORS + _REMOVE_SELECTORS
        ):
            selectors.append(
                _SelectorInfo(
                    path=path_prefix, node=child, fallback_value=fallback
                )
            )
        elif isinstance(child, Nested):
            nested_refs.append(
                _NestedRef(path=path_prefix, struct_name=child.struct_name)
            )
        elif isinstance(child, (Field, InitField)):
            child_path = f"{path_prefix}.{child.name}"
            child_fallback = _find_fallback(child)
            child_sels, child_nested = _collect_selectors(
                child, child_path, child_fallback
            )
            selectors.extend(child_sels)
            nested_refs.extend(child_nested)
        elif isinstance(child, SplitDoc):
            s, n = _collect_selectors(child, f"{path_prefix}.@split-doc")
            selectors.extend(s)
            nested_refs.extend(n)
        elif isinstance(child, PreValidate):
            s, n = _collect_selectors(child, f"{path_prefix}.@pre-validate")
            selectors.extend(s)
            nested_refs.extend(n)
        elif isinstance(child, Key):
            s, n = _collect_selectors(child, f"{path_prefix}.@key")
            selectors.extend(s)
            nested_refs.extend(n)
        elif isinstance(child, Value):
            s, n = _collect_selectors(child, f"{path_prefix}.@value")
            selectors.extend(s)
            nested_refs.extend(n)
        elif isinstance(child, TableConfig):
            s, n = _collect_selectors(child, f"{path_prefix}.@table")
            selectors.extend(s)
            nested_refs.extend(n)
        elif isinstance(child, TableRows):
            s, n = _collect_selectors(child, f"{path_prefix}.@row")
            selectors.extend(s)
            nested_refs.extend(n)
        elif isinstance(child, TableMatchKey):
            s, n = _collect_selectors(child, f"{path_prefix}.@match")
            selectors.extend(s)
            nested_refs.extend(n)
        else:
            s, n = _collect_selectors(child, path_prefix, fallback)
            selectors.extend(s)
            nested_refs.extend(n)

    return selectors, nested_refs


def _selector_type_name(node: AstNode) -> str:
    type_names = {
        CssSelect: "css",
        CssSelectAll: "css-all",
        CssRemove: "css-remove",
        XpathSelect: "xpath",
        XpathSelectAll: "xpath-all",
        XpathRemove: "xpath-remove",
    }
    return type_names.get(type(node), "unknown")


def _check_css(html_soup, query: str) -> int:
    """Run CSS selector and return match count."""
    try:
        return len(html_soup.select(query))
    except Exception:
        return -1


def _check_xpath(html_tree, query: str) -> int:
    """Run XPath selector and return match count."""
    try:
        result = html_tree.xpath(query)
        if isinstance(result, list):
            return len(result)
        return 1 if result else 0
    except Exception:
        return -1


def check_struct_health(
    struct: StructBase, html: str, module: Module | None = None
) -> HealthResult:
    """Check all selectors in a struct (and recursively in nested structs) against HTML.

    Evaluates single selectors (requiring >= 1 match), multi selectors (requiring > 0
    matches), and removal selectors against parsed HTML using BeautifulSoup4 and lxml.
    Selectors with fallback defaults are downgraded from failure to warning if 0 matches occur.

    Args:
        struct: Root struct AST node whose selectors will be evaluated.
        html: Raw HTML string representing sample page content.
        module: Optional parent Module AST containing definitions of nested structs.

    Returns:
        HealthResult holding the list of all checked selectors, counts, and health status.

    Examples:
        ```python
        from ssc_codegen import check_struct_health, parse_module

        ast, _ = parse_module(
            '(item)struct Item { title "h1" { text }; price ".price" { text } }'
        )
        item_struct = ast.body[0]
        html = "<html><body><h1>Example Item</h1></body></html>"

        report = check_struct_health(item_struct, html, module=ast)
        print(f"Passed: {not report.has_failures()}")
        ```
    """
    from bs4 import BeautifulSoup

    struct_map: dict[str, StructBase] = {}
    if module is not None:
        struct_map = {
            s.name: s for s in module.body if isinstance(s, StructBase)
        }

    soup = BeautifulSoup(html, "lxml")
    result = HealthResult(struct_name=struct.name)

    # RAW structs have no HTML selectors — skip health-check entirely.
    if isinstance(struct, Struct) and struct.type == StructType.RAW:
        result.checks.append(
            SelectorCheck(
                path=struct.name,
                selector_type="raw",
                query="",
                matches=0,
                status="warn",
                message="(raw)struct has no HTML selectors to check",
            )
        )
        return result

    visited: set[str] = set()
    _check_struct_recursive(
        struct, struct.name, soup, html, struct_map, result, visited
    )

    return result


def _check_struct_recursive(
    struct: StructBase,
    path_prefix: str,
    soup,
    html: str,
    struct_map: dict[str, StructBase],
    result: HealthResult,
    visited: set[str],
) -> None:
    """Recursively check selectors in struct and its nested structs."""
    if struct.name in visited:
        return
    visited.add(struct.name)

    selectors, nested_refs = _collect_selectors(struct, path_prefix)

    has_xpath = any(isinstance(info.node, _XPATH_TYPES) for info in selectors)
    lxml_tree = None
    if has_xpath:
        try:
            from lxml import etree

            lxml_tree = etree.HTML(html)
        except ImportError:
            pass

    for info in selectors:
        sel_node = info.node
        queries = getattr(sel_node, "queries", [])
        query = queries[0] if queries else getattr(sel_node, "query", "")
        report_query = query
        sel_type = _selector_type_name(sel_node)

        if isinstance(sel_node, _CSS_TYPES):
            if queries:
                count = 0
                report_query = " || ".join(queries)
                for query in queries:
                    count = _check_css(soup, query)
                    if count == -1 or count > 0:
                        break
            else:
                count = _check_css(soup, query)
        elif isinstance(sel_node, _XPATH_TYPES):
            if lxml_tree is None:
                result.checks.append(
                    SelectorCheck(
                        path=info.path,
                        selector_type=sel_type,
                        query=query,
                        matches=0,
                        status="warn",
                        message="lxml not available for xpath check",
                    )
                )
                continue
            if queries:
                count = 0
                report_query = " || ".join(queries)
                for query in queries:
                    count = _check_xpath(lxml_tree, query)
                    if count == -1 or count > 0:
                        break
            else:
                count = _check_xpath(lxml_tree, query)
        else:
            continue

        if count == -1:
            result.checks.append(
                SelectorCheck(
                    path=info.path,
                    selector_type=sel_type,
                    query=report_query,
                    matches=0,
                    status="fail",
                    message="invalid selector syntax",
                )
            )
            continue

        if isinstance(sel_node, _REMOVE_SELECTORS):
            status: Literal["ok", "fail", "warn"] = (
                "ok" if count > 0 else "warn"
            )
        elif isinstance(sel_node, _SINGLE_SELECTORS):
            status = "ok" if count >= 1 else "fail"
        elif isinstance(sel_node, _MULTI_SELECTORS):
            status = "ok" if count > 0 else "fail"
        else:
            status = "ok" if count > 0 else "fail"

        fallback_value = info.fallback_value
        if status == "fail" and fallback_value is not None:
            status = "warn"

        if status == "ok":
            message = f"({count} matches)"
        elif status == "warn" and fallback_value is not None and count == 0:
            message = f"(0 matches, fallback={fallback_value})"
        elif status == "warn":
            message = f"({count} matches)"
        else:
            message = "(0 matches)"

        result.checks.append(
            SelectorCheck(
                path=info.path,
                selector_type=sel_type,
                query=report_query,
                matches=count,
                status=status,
                message=message,
                fallback_value=fallback_value if count == 0 else None,
            )
        )

    for ref in nested_refs:
        nested_struct = struct_map.get(ref.struct_name)
        if nested_struct is None:
            continue
        nested_path = f"{ref.path}[{ref.struct_name}]"
        _check_struct_recursive(
            nested_struct, nested_path, soup, html, struct_map, result, visited
        )
