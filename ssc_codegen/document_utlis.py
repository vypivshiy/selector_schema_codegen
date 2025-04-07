import logging
import re
from typing import TYPE_CHECKING, Pattern
from typing_extensions import assert_never

from ssc_codegen.ast_ import (
    BaseAstNode,
    ExprIsCss,
    ExprCss,
    ExprIsXpath,
    ExprXpathAll,
    ExprXpath,
    ExprCssAll,
)
from ssc_codegen.pseudo_selectors import (
    parse_pseudo_xpath_query,
    pseudo_action_to_pseudo_xpath,
    parse_pseudo_css_query,
    pseudo_action_to_pseudo_css,
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

RE_CAPTURED_GROUPS = re.compile(r"(?<!\()\((?!\?:)[^)]+\)")


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
            msg = f"`{re_pattern.pattern}` pattern groups is empty."
            msg += "\nTIP: maybe you remember wrap pattern to brackets `()`?"
            return AnalyzeResult.error(msg)
        elif max_groups != -1 and re_pattern.groups > max_groups:
            captured_groups = RE_CAPTURED_GROUPS.findall(re_pattern.pattern)
            msg = f"`{re_pattern.pattern}` too many groups in pattern, expected groups count: {max_groups}."
            msg += f"\nTIP: fix regular expression for extract {max_groups}:"
            msg += f"\nGroups founded: {captured_groups}"
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
        if expr.kind not in (ExprCss.kind, ExprCssAll.kind, ExprIsCss.kind):
            new_stack.append(expr)
            continue
        query = expr.kwargs["query"]
        query, pseudo_action = parse_pseudo_css_query(query)
        new_query = css_to_xpath(query, prefix=prefix)
        if pseudo_action[0]:
            new_query += pseudo_action_to_pseudo_css(*pseudo_action)
        match expr.kind:
            case ExprCss.kind:
                new_stack.append(ExprXpath(kwargs={"query": new_query}))
            case ExprCssAll.kind:
                new_stack.append(
                    ExprXpathAll(  # type: ignore[assignment]
                        kwargs={"query": new_query}
                    )
                )
            case ExprIsCss.kind:
                new_stack.append(
                    ExprIsXpath(  # type: ignore[assignment]
                        kwargs={
                            "query": new_query,
                            "msg": expr.kwargs["msg"],
                        }
                    )
                )
            case _:
                assert_never(expr.kind)
    doc._stack = new_stack
    return doc


def convert_xpath_to_css(doc: "BaseDocument") -> "BaseDocument":
    """replace xpath expressions to CSS in Document object"""
    old_stack = doc.stack.copy()
    new_stack: list[BaseAstNode] = []
    for expr in old_stack:
        if expr.kind not in (
            ExprXpath.kind,
            ExprXpathAll.kind,
            ExprIsXpath.kind,
        ):
            new_stack.append(expr)
            continue
        query = expr.kwargs["query"]
        query, pseudo_action = parse_pseudo_xpath_query(query)
        new_query = xpath_to_css(query)
        if pseudo_action[0]:
            new_query += pseudo_action_to_pseudo_xpath(*pseudo_action)
        match expr.kind:
            case ExprXpath.kind:
                new_stack.append(ExprCss(kwargs={"query": new_query}))
            case ExprXpathAll.kind:
                new_stack.append(ExprCssAll(kwargs={"query": new_query}))
            case ExprIsXpath.kind:
                new_stack.append(
                    ExprIsCss(
                        kwargs={
                            "query": new_query,
                            "msg": expr.kwargs["msg"],
                        }
                    )
                )
            case _:
                assert_never(expr.kind)
    doc._stack = new_stack
    return doc
