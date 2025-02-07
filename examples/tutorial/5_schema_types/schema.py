from ssc_codegen import D, N, ItemSchema, ListSchema, DictSchema, FlatListSchema

class ListGroup(ListSchema):
    # this schema required mark how to part elements for create list of dict structs
    # convert __SPLIT_DOC__ and custom number of fields

    # in real case used for get access to tags like product cards, etc
    __SPLIT_DOC__ = D().css_all('.list-group > .item')
    # now works with scope div.item tag
    p_tag = D().css('p').text()
    a_href = D().css('a').attr('href')


class DictGroup(DictSchema):
    # situate struct type for create dict struct
    # convert only __SPLIT_DOC__, __KEY__, __VALUE__
    __SPLIT_DOC__ = D().css_all('.dict-group > li')
    # optional override marks how to convert signature to docstrings
    # accepts list, dict, str
    __SIGNATURE__ = {"key1": "value1", "keyN": "valueN", "...": "..."}

    # SHOULD be a str type, else throw exception
    __KEY__ = D().attr('class')
    __VALUE__ = D().text()

class FlatListGroup(FlatListSchema):
    # situate struct type for create list struct
    # convert only __SPLIT_DOC__, __ITEM__
    __SPLIT_DOC__ = D().css_all('.flatlist-group > li')
    __SIGNATURE__ = ["item1", "itemN", "..."]

    __ITEM__ = D().text()

class Main(ItemSchema):
    # you can accumulate all structs to one ItemSchema
    # nested schemas marks as N() mark
    list_group = N().sub_parser(ListGroup)
    dict_group = N().sub_parser(DictGroup)
    flat_list_group = N().sub_parser(FlatListGroup)
    # add extra fields if needed
    title = D().css('title').text()