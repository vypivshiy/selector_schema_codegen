from typing import TYPE_CHECKING

from .ast_ssc import BaseExpression, IsCssExpression, IsXPathExpression, \
    HtmlCssExpression, HtmlXpathExpression, HtmlXpathAllExpression, HtmlCssAllExpression
from .selector_utils import css_to_xpath, xpath_to_css

if TYPE_CHECKING:
    from .document import BaseDocument


def convert_css_to_xpath(doc: "BaseDocument", prefix: str = "descendant-or-self::") -> "BaseDocument":
    old_stack = doc.stack.copy()
    new_stack: list[BaseExpression] = []

    for expr in old_stack:
        match expr.kind:
            case HtmlCssExpression.kind:
                expr: HtmlCssExpression
                new_expr = HtmlXpathExpression(
                    variable=expr.variable,
                    query=css_to_xpath(expr.query, prefix=prefix)
                )

            case HtmlCssAllExpression.kind:
                expr: HtmlCssAllExpression
                new_expr = HtmlXpathAllExpression(
                    variable=expr.variable,
                    query=css_to_xpath(expr.query, prefix=prefix)
                )
            case IsCssExpression.kind:
                expr: IsCssExpression
                new_expr = IsXPathExpression(
                    variable=expr.variable,
                    query=css_to_xpath(expr.query, prefix=prefix),
                    msg=expr.msg
                )
            case _:
                new_expr = expr
        new_stack.append(new_expr)
    doc._stack = new_stack
    return doc


def convert_xpath_to_css(doc: "BaseDocument") -> "BaseDocument":
    old_stack = doc.stack.copy()
    new_stack: list[BaseExpression] = []
    for expr in old_stack:
        match expr.kind:
            case HtmlXpathExpression.kind:
                expr: HtmlXpathExpression
                new_expr = HtmlCssExpression(
                    variable=expr.variable,
                    query=xpath_to_css(expr.query)
                )
            case HtmlXpathAllExpression.kind:
                expr: HtmlXpathAllExpression
                new_expr = HtmlCssAllExpression(
                    variable=expr.variable,
                    query=xpath_to_css(expr.query)
                )
            case IsXPathExpression.kind:
                expr: IsXPathExpression
                new_expr = IsCssExpression(
                    variable=expr.variable,
                    query=xpath_to_css(expr.query),
                    msg=expr.msg
                )
            case _:
                new_expr = expr
        new_stack.append(new_expr)
    doc._stack = new_stack
    return doc
