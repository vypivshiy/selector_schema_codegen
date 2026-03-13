from __future__ import annotations

from cssselect import HTMLTranslator


def css_to_xpath(query: str, prefix: str = "descendant-or-self::") -> str:
    """Convert CSS selector to XPath query."""
    return HTMLTranslator().css_to_xpath(query, prefix=prefix)
