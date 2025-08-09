from ssc_codegen import ItemSchema, D


class Main(ItemSchema):
    title = D().css("title::text")
    urls = D().css_all("a[href]::attr(href)")
