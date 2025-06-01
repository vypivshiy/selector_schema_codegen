from ssc_codegen import ItemSchema, D


class Contacts(ItemSchema):
    # simple extractor email and telephone
    # https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/a#href
    email = D([]).css_all("a[href^='mailto:']::attr(href)")
    phone = D([]).css_all("a[href^='tel:']::attr(href)")