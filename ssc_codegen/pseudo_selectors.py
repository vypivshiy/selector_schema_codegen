import re
from typing import Literal

PseudoAction = Literal["text", "raw", "attr"]


def parse_pseudo_css_query(
    query: str,
) -> tuple[str, tuple[PseudoAction | None, str | None]]:
    """parse css selector and extract pseudo class action"""
    query = query.strip()

    if query.endswith("::text"):
        return query[: -len("::text")], ("text", None)

    if query.endswith("::raw"):
        return query[: -len("::raw")], ("raw", None)

    if match := re.search(r"::attr\(([^)]+)\)$", query):
        return query[: match.start()], ("attr", match.group(1))

    return query, (None, None)


def parse_pseudo_xpath_query(
    query: str,
) -> tuple[str, tuple[PseudoAction | None, str | None]]:
    """parse xpath selector and extract pseudo class action"""
    query = query.strip()

    if query.endswith("/text()"):
        return query[: -len("/text()")], ("text", None)

    if query.endswith("/raw()"):
        return query[: -len("/raw()")], ("raw", None)

    if match := re.search(r"/@([\w:-]+)$", query):
        return query[: match.start()], ("attr", match.group(1))

    return query, (None, None)


def pseudo_action_to_pseudo_css(action: PseudoAction, arg: str | None) -> str:
    match action:
        case "text":
            return "::text"
        case "raw":
            return "::raw"
        case "attr":
            return f"::attr({arg})"
        case _:
            return ""


def pseudo_action_to_pseudo_xpath(action: PseudoAction, arg: str | None) -> str:
    match action:
        case "text":
            return "/text()"
        case "raw":
            return "/raw()"
        case "attr":
            return f"/@{arg}"
        case _:
            return ""
