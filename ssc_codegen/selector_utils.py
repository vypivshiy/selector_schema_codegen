import re
from contextlib import suppress

from cssselect import HTMLTranslator, SelectorSyntaxError
from lxml import etree
from lxml.etree import XPathSyntaxError


def css_to_xpath(query: str, prefix: str = "descendant-or-self::") -> str:
    """convert css to XPATH selector"""
    xpath = HTMLTranslator().css_to_xpath(query, prefix=prefix)
    return xpath


def xpath_to_css(query: str) -> str:
    """this is the converter for simple xpath queries and exclude check operators like `contains`

    EG OK:

        //div[@class="product_price"]/p[@class="instock availability"]/i

        div[class="product_price"] > p[class="instock availability"] > i

    EG FAIL:
        //p[contains(@class, "star-rating")]

    """
    # https://stackoverflow.com/a/18421383
    css = re.sub(
        r"\[(\d+?)\]", lambda m: "[" + str(int(m.group(1)) - 1) + "]", query
    )
    css = re.sub(r"/{2}", "", css)
    css = re.sub(r"/+", " > ", css)
    css = css.replace("@", "")
    css = re.sub(r"\[(\d+)\]", lambda m: f":eq({m.group(1)})", css)
    css = re.sub(r"\[@(.*?)='(. *?)\]", r'[\1 = "\2"]', css)
    css = css.lstrip()

    return css


def validate_css_query(query: str) -> None:
    try:
        HTMLTranslator().css_to_xpath(query.strip('"'))
    except SelectorSyntaxError:
        # maybe is XPATH?
        with suppress(XPathSyntaxError):
            etree.XPath(query)  # type: ignore
            msg = f"`{query}` looks like XPATH query, not CSS"
            raise SelectorSyntaxError(msg)
        msg = f"`{query}` is not valid CSS selector"
        raise SelectorSyntaxError(msg)


def validate_xpath_query(query: str) -> None:
    try:
        etree.XPath(query.strip('"'))
        # etree.XPath accept CSS-like queries without throw exception, check it!
        is_css = False
        with suppress(SelectorSyntaxError):
            HTMLTranslator().css_to_xpath(query.strip('"'))
            is_css = True

        if is_css:
            msg = f"`{query}` looks like CSS query, not XPATH"
            raise SelectorSyntaxError(msg)
    except XPathSyntaxError:
        msg = f"`{query}` is not valid XPATH selector"
        raise SelectorSyntaxError(msg)
