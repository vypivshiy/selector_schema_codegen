from ssc_codegen import ItemSchema, R, F, D


class FilterSchema(ItemSchema):
    js_hrefs = R().re_all(r"((?:https?:)/?/[^>]+\.js)").filter(
        F().starts("https").re("abc") & ~F().re('.*?')
    )
    title = D().css("title::text")