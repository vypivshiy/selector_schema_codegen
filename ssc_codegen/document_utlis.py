import re
from typing import TYPE_CHECKING

from .ast_ssc import (
    BaseExpression,
    HtmlCssAllExpression,
    HtmlCssExpression,
    HtmlXpathAllExpression,
    HtmlXpathExpression,
    IsCssExpression,
    IsXPathExpression,
)
from .selector_utils import css_to_xpath, xpath_to_css

if TYPE_CHECKING:
    from .document import BaseDocument


def check_re_expression(pattern: str) -> None:
    if pattern == "":
        raise SyntaxError("Empty pattern expression")
    try:
        re.compile(pattern)
        # todo: pattern group check
    except re.error as e:
        raise SyntaxError("Wrong regex pattern") from e


def convert_css_to_xpath(
    doc: "BaseDocument", prefix: str = "descendant-or-self::"
) -> "BaseDocument":
    """replace CSS expressions to XPATH"""
    old_stack = doc.stack.copy()
    new_stack: list[BaseExpression] = []

    for expr in old_stack:
        match expr.kind:
            case HtmlCssExpression.kind:
                new_expr = HtmlXpathExpression(  # type: ignore[assignment]
                    variable=expr.variable,
                    query=css_to_xpath(expr.query, prefix=prefix),  # type: ignore[attr-defined]
                )
            case HtmlCssAllExpression.kind:
                new_expr = HtmlXpathAllExpression(  # type: ignore[assignment]
                    variable=expr.variable,
                    query=css_to_xpath(expr.query, prefix=prefix),  # type: ignore[attr-defined]
                )
            case IsCssExpression.kind:
                new_expr = IsXPathExpression(  # type: ignore[assignment]
                    variable=expr.variable,
                    query=css_to_xpath(expr.query, prefix=prefix),  # type: ignore[attr-defined]
                    msg=expr.msg,  # type: ignore[attr-defined]
                )
            case _:
                new_expr = expr  # type:ignore[assignment]
        new_stack.append(new_expr)
    doc._stack = new_stack
    return doc


def convert_xpath_to_css(doc: "BaseDocument") -> "BaseDocument":
    old_stack = doc.stack.copy()
    new_stack: list[BaseExpression] = []
    for expr in old_stack:
        match expr.kind:
            case HtmlXpathExpression.kind:
                new_expr = HtmlCssExpression(  # type: ignore[assignment]
                    variable=expr.variable,
                    query=xpath_to_css(expr.query),  # type: ignore[attr-defined]
                )
            case HtmlXpathAllExpression.kind:
                new_expr = HtmlCssAllExpression(  # type: ignore[assignment]
                    variable=expr.variable,
                    query=xpath_to_css(expr.query),  # type: ignore[attr-defined]
                )
            case IsXPathExpression.kind:
                new_expr = IsCssExpression(  # type: ignore[assignment]
                    variable=expr.variable,
                    query=xpath_to_css(expr.query),  # type: ignore[attr-defined]
                    msg=expr.msg,  # type: ignore[attr-defined]
                )
            case _:
                new_expr = expr  # type: ignore[assignment]
        new_stack.append(new_expr)
    doc._stack = new_stack
    return doc
