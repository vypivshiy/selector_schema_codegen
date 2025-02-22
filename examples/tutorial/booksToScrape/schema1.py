from ssc_codegen import ItemSchema, D

class MainCatalogue(ItemSchema):
    # in start pagination not exists this tag, set None
    prev_page = D().default(None).css('.previous a').attr('href')
    # in end pagination not exists this tag, set None
    next_page = D().default(None).css('.next a').attr('href')