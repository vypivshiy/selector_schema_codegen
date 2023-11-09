import re

from cssselect import HTMLTranslator


def css_to_xpath(query: str, prefix: str = "descendant-or-self::") -> str:
    """convert css to XPATH selector"""
    xpath = HTMLTranslator().css_to_xpath(query, prefix=prefix)
    return xpath


def xpath_to_css(query: str) -> str:
    """this is converter for simple xpath queries and exclude check operators like `contains`

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
