from ssc_codegen import D, ItemSchema


class Main(ItemSchema):
    # ssc-gen can transfer docstrings into the generated code.
    # this is useful for describing WHAT TO USE IT and issues that may occur
    """Hello, it my first docstring for useless synthetic html!

    USAGE:
        - pass index.html document from 1_basic folder

    """

    # simple extract text
    item_sc = D().css(".item-sc > p").text()
    # extract href attribute and format to full url
    a_href = D().css(".item-sc > a").attr("href").fmt("https://{{}}")
    # cast string example - remove all whitespaces
    a_text = D().css(".item-sc > a").text().trim()
    # simple convert to types (int, float)
    var_int = D().css(".item-sc > #int-item").text().to_int()
    var_float = D().css(".item-sc > #float-item").text().to_float()
    # extract data collection
    var_list = D().css_all(".item-sc > .list-items > li").text()
    # advanced: extract data collection and cast to into
    var_list_ints = (
        D()
        .css_all(".item-sc > .list-items > li")
        .text()
        # remove all non-digit symbols
        .re_sub(r"\D+", "")
        .to_int()
    )
