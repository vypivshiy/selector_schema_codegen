from ssc_codegen import ItemSchema, D

FMT_URL = "https://books.toscrape.com/catalogue/{{}}"
FMT_URL_CURRENT = "https://books.toscrape.com/catalogue/page-{{}}.html"

class MainCatalogue(ItemSchema):
    # steps:
    # 1. set default if teg will be not founded
    # 2. get tag by css query
    # 3. get [href] attribute
    # 4. ltrim, fmt - format to full url
    prev_page = D().default(None).css('.previous a').attr('href').ltrim('catalogue/').fmt(FMT_URL)
    next_page = D().default(None).css('.next a').attr('href').ltrim('catalogue/').fmt(FMT_URL)
    curr_page = D().css('.current').text().re(r'Page\s(\d+)').fmt(FMT_URL_CURRENT)