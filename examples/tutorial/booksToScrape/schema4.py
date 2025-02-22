from ssc_codegen import DictSchema, D



class ProductDescription(DictSchema):
    """parse product description from product page

    Response input examples:
        - https://books.toscrape.com/catalogue/in-her-wake_980/index.html
        - from catalogue page
    """
    __SPLIT_DOC__ = D().css_all("table tr")
    __SIGNATURE__ = {
        "UPC": "String",
        "Product Type": "Books",
        "Price (excl. tax)": "String",
        "Price (incl. tax)": "String",
        "Tax": "String",
        "Availability": "In stock (<count>)",
        "Number of reviews": "0 (always, its fiction shop lol)"
    }

    __KEY__ = D().css('th').text()
    __VALUE__ = D().css("td").text()
    # other defined fields do not compiled and throw warning
    # im_not_be_compiled = D().css("title").text()