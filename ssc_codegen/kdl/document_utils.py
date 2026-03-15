from __future__ import annotations

from typing import Iterable
from typing_extensions import assert_never

from ssc_codegen.kdl.ast import (
    CssSelect,
    CssSelectAll,
    CssRemove,
    XpathSelect,
    XpathSelectAll,
    XpathRemove,
    PredCss,
    PredXpath,
)
from ssc_codegen.kdl.pseudo_selectors import (
    parse_pseudo_css_query,
    pseudo_action_to_pseudo_css,
)
from ssc_codegen.kdl.selector_utils import css_to_xpath


def convert_css_to_xpath(
    nodes: Iterable[object], prefix: str = "descendant-or-self::"
):
    """Replace CSS expressions to XPATH in AST nodes list."""
    new_nodes: list[object] = []

    for expr in nodes:
        if not isinstance(
            expr,
            (CssSelect, CssSelectAll, CssRemove, PredCss),
        ):
            new_nodes.append(expr)
            continue

        query = expr.query
        query, pseudo_action = parse_pseudo_css_query(query)
        new_query = css_to_xpath(query, prefix=prefix)
        if pseudo_action[0]:
            new_query += pseudo_action_to_pseudo_css(*pseudo_action)

        if isinstance(expr, CssSelect):
            new_nodes.append(
                XpathSelect(
                    parent=expr.parent,
                    query=new_query,
                    accept=expr.accept,
                    ret=expr.ret,
                )
            )
        elif isinstance(expr, CssSelectAll):
            new_nodes.append(
                XpathSelectAll(
                    parent=expr.parent,
                    query=new_query,
                    accept=expr.accept,
                    ret=expr.ret,
                )
            )
        elif isinstance(expr, CssRemove):
            new_nodes.append(
                XpathRemove(
                    parent=expr.parent,
                    query=new_query,
                    accept=expr.accept,
                    ret=expr.ret,
                )
            )
        elif isinstance(expr, PredCss):
            new_nodes.append(
                PredXpath(
                    parent=expr.parent,
                    query=new_query,
                    accept=expr.accept,
                    ret=expr.ret,
                )
            )
        else:
            assert_never(expr)

    return new_nodes


def convert_css_to_xpath_module(
    module: object, prefix: str = "descendant-or-self::"
) -> None:
    """Recursively convert CSS selector nodes inside a Module AST."""
    if not getattr(module, "body", None):
        return
    module.body = convert_css_to_xpath(module.body, prefix=prefix)
    for node in module.body:
        if getattr(node, "body", None):
            convert_css_to_xpath_module(node, prefix=prefix)
