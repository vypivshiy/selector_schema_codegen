""" main docstring example
ssc-gen transpiles it at the beginning of the file
"""
from ssc_codegen import ItemSchema, D, N


class Contacts(ItemSchema):
    """Simple extract contacts from page by a[href] attribute. If field not founded - return None

    See also:
        https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/a#href
    """
    # Tip: To write efficient selectors and improve performance, it's recommended to learn CSS3 standard selectors:
    # https://www.w3schools.com/cssref/css_selectors.php
    # Helpful browser extensions:
    # SelectorGadget (Chrome)
    # ScrapeMate (Firefox)

    # NOTE:
    # [attribute^="value"] selector matches elements whose attribute value starts with a given string.
    # If an element is not found, the eval field will use a default fallback value.
    phone = D(default=None).css('a[href^="tel:"]').attr("href")
    # this alias shortcut
    email = D(None).css('a[href^="email:"]').attr("href")


class HelloWorld(ItemSchema):
    # Web-scraping involves the use of undocumented methods and selectors.
    # So in some cases it is recommended to document what needs to be
    # submitted for input and what problems may occur
    """Example demonstration documentation schema usage.

    Usage:

        GET any html page

    Issues:

        If <a> tags in target page not exists, it throw error!
    """
    title = D().css('title').text()
    a_hrefs = D().css_all('a').attr('href')
    contacts = N().sub_parser(Contacts)