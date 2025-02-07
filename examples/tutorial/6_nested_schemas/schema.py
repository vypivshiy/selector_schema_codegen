# struct inside a struct of data inside a struct of data
from ssc_codegen import D, ItemSchema, N


class Item4(ItemSchema):
    items = D().css_all(".item4 > .item-value").text()


class Item3(ItemSchema):
    items = D().css_all(".item3 > .item-value").text()
    b_text = D().css(".item3 > b").text()


class Item2(ItemSchema):
    items = D().css_all(".item2 > .item-value").text()
    href = D().css(".item2 > a").attr("href")


class Item1(ItemSchema):
    items = D().css_all(".item > .item-value").text()
    href = D().css(".item > a").attr("href")


# inheirence fields allowed (schemas should be as same struct type)


class ItemRec3(Item3):
    item_rec4 = N().css(".item4").sub_parser(Item4)


class ItemRec2(Item2):
    item_rec3 = N().css(".item3").sub_parser(ItemRec3)


class ItemRec1(Item1):
    item_rec2 = N().css(".item2").sub_parser(ItemRec2)


class Main(ItemSchema):
    # NOTE: 'multi_nested' implemented just demonstration
    multi_nested = N().css(".main > .item").sub_parser(ItemRec1)
    # i real projects, recommended implement more flatten structs like this:
    item1 = N().css(".item").sub_parser(Item1)
    item2 = N().css(".item2").sub_parser(Item2)
    item3 = N().css(".item3").sub_parser(Item3)
    item4 = N().css(".item4").sub_parser(Item4)
