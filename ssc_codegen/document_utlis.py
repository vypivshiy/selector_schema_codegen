import re
from typing import TYPE_CHECKING, Pattern

from ssc_codegen.ast_ssc import (
    BaseExpression,
    HtmlCssAllExpression,
    HtmlCssExpression,
    HtmlXpathAllExpression,
    HtmlXpathExpression,
    IsCssExpression,
    IsXPathExpression,
)
from ssc_codegen.selector_utils import css_to_xpath, xpath_to_css

if TYPE_CHECKING:
    from .document import BaseDocument


# https://stackoverflow.com/a/14919203
CM1_RX = r"(?m)(?<!\\)((\\{2})*)#.*$"
CM2_RX = r"(\\)?((\\{2})*)(#)"
WS_RX = r"(\\)?((\\{2})*)(\s)\s*"


def unverbosify_regex(pattern: str | Pattern) -> str:
    if isinstance(pattern, str):
        return pattern

    def strip_escapes(match):  # type: ignore
        ## if even slashes: delete space and retain slashes
        if match.group(1) is None:
            return match.group(2)
        ## if number of slashes is odd: delete slash and keep space (or 'comment')
        elif match.group(1) == "\\":
            return match.group(2) + match.group(4)
        ## error
        else:
            raise Exception

    if pattern.flags & re.X:
        not_verbose_regex = re.sub(
            WS_RX,
            strip_escapes,
            re.sub(
                CM2_RX, strip_escapes, re.sub(CM1_RX, "\\1", pattern.pattern)
            ),
        )

        return not_verbose_regex
    return pattern.pattern


def assert_re_expression(
    pattern: str, allow_empty_groups: bool = False, max_groups: int = -1
) -> None:
    """throw SyntaxError if pattern empty or cannot be compiled."""
    if not pattern:
        raise SyntaxError("Empty pattern expression")
    try:
        re_pattern = re.compile(pattern)
        if not allow_empty_groups and re_pattern.groups == 0:
            msg = f"`{re_pattern.pattern}` pattern groups is empty"
            raise SyntaxError(msg)
        elif max_groups != -1 and re_pattern.groups > max_groups:
            msg = f"`{re_pattern.pattern}` too many groups in pattern, expected {max_groups}"
            raise SyntaxError(msg)
    except re.error as e:
        raise SyntaxError("Wrong regex pattern") from e


def convert_css_to_xpath(
    doc: "BaseDocument", prefix: str = "descendant-or-self::"
) -> "BaseDocument":
    """replace CSS expressions to XPATH in Document object"""
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
    """replace xpath expressions to CSS in Document object"""
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
