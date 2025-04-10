from ssc_codegen import ItemSchema, F, D


# base logic operators
# | - OR
# & - AND
# ~ - NOT

class FilterSchema(ItemSchema):
    urls = D().css_all("a[href]::attr(href)").filter(
        # value ends .js suffix
        # OR NOT EQUAL collections of substrings
        # AND NOT starts '#'
        F().ends(".js")
        # same as `F().ne('', '#', "/")`
        # syntax sugar: allowed pass str or sequence of str
        # don't remember to wrap it in parens
        # v---------------------v
        | (F() != ('', '#', "/"))
        & ~F().starts("#")
    )

    urls_by_len = D().css_all("a[href]::attr(href)").filter(
        F() >= 12)
