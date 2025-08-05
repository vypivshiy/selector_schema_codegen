"""Examples implement structure parsers

This docstring will be converted to target code too!
"""

import re
from ssc_codegen import (
    ItemSchema,
    DictSchema,
    ListSchema,
    FlatListSchema,
    AccUniqueListSchema,
    D,
    R,
)

# TIP: you can move to constants long/compex selectors
CSS_LINK_EXTRACTOR = """
a[href],img[src]::attr(href,src)
"""


class ItemData(ItemSchema):
    """Most common used structure

    returns format

        {field_name: parsed_value, ...}

    EXAMPLE:

    INPUT:

    ```html
    <title>Demo title</title>
    <body>
        <h1>hello</h1>
        <a href="url1">
        <img src="img1.png">
        <a href="url2">
        <img src="img2.png">
    </body>
    ```

    OUTPUT:

    ```
    {"title": "Demo title", "urls": ["url1", "img1.png", "url2", "img2.png"]}
    ```

    """

    title = D().css("title::text")
    # set default empty list if url-like tags is not exists
    urls = D([]).css_all(CSS_LINK_EXTRACTOR)


class ListData(ListSchema):
    """Second useful structure. useful for parse html like product cards

    Part doc by __SPLIT_DOC__ expression. Fields parse every selected element

    required create `__SPLIT_DOC__` field

    returns format

        [{field_name: parsed_value}, ...] data

    Example:

    INPUT:

    ```html
    <span> collection of items</span>
    <a href="not-captured.html">
    <div class="item">
        <span>item1</span>
        <a href="item1.html">
    </div>
    <div class="item">
        <span>item2</span>
        <a href="item2.html">
    </div>
    <div class="item">
        <span>item3</span>
        <a href="item3.html">
    </div>
    ```

    OUTPUT:

    ```
    [
        {"description": "item1", "url": "item1.html"},
        {"description": "item2", "url": "item2.html"},
        {"description": "item3", "url": "item3.html"},
    ]
    ```
    """

    # capture elements by `item` class
    __SPLIT_DOC__ = D().css_all(".item")

    description = D().css("span::text")
    url = D().css("a::attr(href)")


class DictData(DictSchema):
    """Situational data structure

    maybe used in cases, where required generic key

    its maybe `<table>` elements or attribute-by key.

    required create `__SPLIT_DOC__`, `__KEY__`, `__VALUE__` fields

    recommended override `__SIGNATURE__` for detalization docstring output


    __KEY__ field should be returns String
    returns format

        {<key1>: <value1>, ...}

    EXAMPLE:

    INPUT:

    (html code reference from https://en.wikipedia.org/wiki/Spider)

    ```html
    <table>
        <tr class="taxonrow">
            <td>Kingdom</td>
            <td>Animalia</td>
        </tr>
        <tr class="taxonrow">
            <td>Phylum</td>
            <td>Arthropoda</td>
        </tr>
        <tr class="taxonrow">
            <td>Subphylum</td>
            <td>Chelicerata</td>
        </tr>
        <tr class="taxonrow">
            <td>Class</td>
            <td>Arachnida</td>
        </tr>
    </table>
    ```

    OUTPUT:
    ```
    {
        "Kingdom": "Animalia",
        "Phylum": "Arthropoda",
        "Subphylum":"Chelicerata",
        "Class": "Arachnida"
    }
    ```
    """
    __SIGNATURE__ = {"useless": "wiki", "table": "info", "..."}

    __SPLIT_DOC__ = D().css_all("table tr")

    __KEY__ = D().css("td:nth-child(1)::text")
    __VALUE__ = D().css("td:nth-child(2)::text")


class FlatListData(FlatListSchema):
    """Situational data structure, create list data

    required create `__SPLIT_DOC__`, `__ITEM__` fields
    returns

        [item1, item2, ...]

    EXAMPLE:

    INPUT:

    ```html
    <div class="item">
        <span>item1</span>
        <a href="item1.html">
    </div>
    <div class="item">
        <span>item2</span>
        <a href="item2.html">
    </div>
    <div class="item">
        <span>item3</span>
        <a href="item3.html">
    </div>
    ```

    OUTPUT:

    ```
    ["item1.html", "item2.html", "item3.html"]
    ```
    """

    __SPLIT_DOC__ = D().css_all(".item")
    __ITEM__ = D().css("a::attr(href)")


class AccUniqueListData(AccUniqueListSchema):
    """Situational data structure, returns unique list of items.

    All fields should be returns  LIST_STRING type
    items order not be guaranteed.

     returns format

        [item1, ...]

    EXAMPLE:

    see example fields how to parse socials, contacts to one list from any html page
    """

    # TIP: use attribute selectors for increase accuracy select
    # https://developer.mozilla.org/en-US/docs/Web/CSS/Attribute_selectors#syntax

    # https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/a#href
    # URL scheme supported by browsers:
    # Telephone numbers with `tel:`` URLs
    # Email addresses with `mailto:`` URLs
    phone = D([]).css_all("a[href^=tel:]::attr(href)")
    email = D([]).css_all("a[href^=email:]::attr(href)")

    github = D([]).css_all(
        "a[href*=github.com],iframe[src*=github.com]::attr(href,src)"
    )

    # regex scan search (EG: maybe contains in text/script tags)
    github_re = R([]).re_all(
        re.compile(r"(https?://(?:www\.)github\.com/[-_A-Za-z0-9]+)")
    )
    # add other socials selectors


# create nested structure example
# you can combine many structures to one by `N` (Nested) shortcut

from ssc_codegen import N  # noqa (example code)


class NestedHeader(ItemSchema):
    title = D().css("title::text")
    styles = D([]).css_all("style[rel='stylesheet'][href]::attr(href)")


class NestedListItem(ListSchema):
    # example abstract selector
    __SPLIT_DOC__ = D().css_all("div.cls-container")

    urls = D([]).css_all("a[href]::attr(href)")
    raw_tag = R()
    text = D("").text()


class MainNestedItem(ItemSchema):
    """Demo howto create nested schema

    works with ItemSchema, ListSchema, FlatListSchema, DictSchema classes

    example signature output:

    {
        "header": 
            {"title": str, "styles": list[str]},
        "header_chunked": 
            {"title": str, "styles": list[str]},
        "list_items": 
            [
                {"urls": list[str], raw_tag: str, text: str}, ...
            ]
    }
    """

    header = N().sub_parser(NestedHeader)
    # optional: you can select element and pass chunk to schema
    header_chunked = N().css("head").sub_parser(NestedHeader)
    list_items = N().sub_parser(NestedListItem)
    # add other required fields
