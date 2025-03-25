import re
from typing import TYPE_CHECKING, Pattern
import logging
from ssc_codegen.ast_ import (
    BaseAstNode,
    ExprIsCss,
    ExprCss,
    ExprIsXpath,
    ExprXpathAll,
    ExprXpath,
    ExprCssAll,
)
from ssc_codegen.selector_utils import css_to_xpath, xpath_to_css
from ssc_codegen.static_checker.base import AnalyzeResult

LOGGER = logging.getLogger("ssc_gen")

if TYPE_CHECKING:
    from .document import BaseDocument


# https://stackoverflow.com/a/14919203
CM1_RX = r"(?m)(?<!\\)((\\{2})*)#.*$"
CM2_RX = r"(\\)?((\\{2})*)(#)"
WS_RX = r"(\\)?((\\{2})*)(\s)\s*"


def is_ignore_case_regex(pattern: str | Pattern) -> bool:
    if isinstance(pattern, str):
        return False
    return bool(pattern.flags & re.IGNORECASE)


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


def analyze_re_expression(
    pattern: str, allow_empty_groups: bool = False, max_groups: int = -1
) -> AnalyzeResult:
    """throw SyntaxError if pattern empty or cannot be compiled."""
    # TODO: move to static_checkers
    if not pattern:
        return AnalyzeResult.error("Empty pattern expression")
    try:
        re_pattern = re.compile(pattern)
        if not allow_empty_groups and re_pattern.groups == 0:
            msg = f"`{re_pattern.pattern}` pattern groups is empty"
            return AnalyzeResult.error(msg)
        elif max_groups != -1 and re_pattern.groups > max_groups:
            msg = f"`{re_pattern.pattern}` too many groups in pattern, expected {max_groups}"
            return AnalyzeResult.error(msg)
    except re.error as e:
        msg = f"`{pattern}` wrong regex pattern syntax: {e!r}"
        return AnalyzeResult.error(msg)
    return AnalyzeResult.ok()


def convert_css_to_xpath(
    doc: "BaseDocument", prefix: str = "descendant-or-self::"
) -> "BaseDocument":
    """replace CSS expressions to XPATH in Document object"""
    old_stack = doc.stack.copy()
    new_stack: list[BaseAstNode] = []

    for expr in old_stack:
        match expr.kind:
            case ExprCss.kind:
                new_expr = ExprXpath(  # type: ignore[assignment]
                    kwargs={
                        "query": css_to_xpath(
                            expr.kwargs["query"], prefix=prefix
                        )
                    }
                )
            case ExprCssAll.kind:
                new_expr = ExprXpathAll(  # type: ignore[assignment]
                    kwargs={
                        "query": css_to_xpath(
                            expr.kwargs["query"], prefix=prefix
                        )
                    }
                )
            case ExprIsCss.kind:
                new_expr = ExprIsXpath(  # type: ignore[assignment]
                    kwargs={
                        "query": css_to_xpath(
                            expr.kwargs["query"], prefix=prefix
                        ),
                        "msg": expr.kwargs["msg"],
                    }
                )
            case _:
                new_expr = expr  # type: ignore[assignment]
        new_stack.append(new_expr)
    doc._stack = new_stack
    return doc


def convert_xpath_to_css(doc: "BaseDocument") -> "BaseDocument":
    """replace xpath expressions to CSS in Document object"""
    old_stack = doc.stack.copy()
    new_stack: list[BaseAstNode] = []
    for expr in old_stack:
        match expr.kind:
            case ExprXpath.kind:
                new_expr = ExprCss(
                    kwargs={"query": xpath_to_css(expr.kwargs["query"])}
                )
            case ExprXpathAll.kind:
                new_expr = ExprCssAll(  # type: ignore[assignment]
                    kwargs={"query": xpath_to_css(expr.kwargs["query"])}
                )
            case ExprIsXpath.kind:
                new_expr = ExprIsCss(  # type: ignore[assignment]
                    kwargs={
                        "query": xpath_to_css(expr.kwargs["query"]),
                        "msg": expr.kwargs["msg"],
                    }
                )
            case _:
                new_expr = expr  # type: ignore[assignment]
        new_stack.append(new_expr)
    doc._stack = new_stack
    return doc
