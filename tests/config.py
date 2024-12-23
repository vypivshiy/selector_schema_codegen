"""EXAMPLE MODULE DOCUMENTATION!!!"""
from ssc_codegen import ItemSchema, D, N, FlatListSchema, ListSchema, DictSchema


class NestedItem(ItemSchema):
    """SUBstructure DOCSTRING"""
    item_attr = D().css('a').attr('href')
    item_text = D().css('a').text()
    item_attr_many = D().css_all('a').attr('href')
    item_text_many = D().css_all('p').text()
    item_raw = D().css('p').raw()
    item_raw_many = D().css_all('p').raw()

    str_fmt = D().css('p').text().fmt('FMT: {{}}')
    str_fmt_many = D().css_all('p').text().fmt('FMT: {{}}')


class FlatListItem(FlatListSchema):
    __SPLIT_DOC__ = D().css_all('a')

    __ITEM__ = D().attr('href')


class DictItem(DictSchema):
    __SPLIT_DOC__ = D().css_all('a')

    __KEY__ = D().attr('href')
    __VALUE__ = D().text()


class ListItem(ListSchema):
    __SPLIT_DOC__ = D().css_all('.klass')

    item_default_null = D().default(None).css('ddd > .whatisit').raw()
    # NOTE: default value sets if expr throw error
    # in bottom case return None
    # item_default_val = D().default("EMPTY").css('ddd > .whatisit').raw()
    item_default_val = D().default("EMPTY").css('ddd > .whatisit').raw().split('TTT').index(0)
    item_attr = D().css('a').attr('href')
    item_text = D().css('a').text()
    item_attr_many = D().css_all('a').attr('href')
    item_text_many = D().css_all('a').text()
    item_raw = D().css('a').raw()
    item_raw_many = D().css_all('a').raw()
    str_fmt = D().css('p').text().fmt('FMT: {{}}')
    str_fmt_many = D().css_all('p').text().fmt('FMT: {{}}')

    item_re = D().css('p').text().re('(\d)')
    item_re_all = D().css('p').text().re_all('(\d)')
    item_re_sub = D().css('p').text().re_sub('raw', 'sub')
    item_re_sub_many = D().css_all('p').text().re_sub('raw', 'sub')

    item_trim = D().css('p').text().trim('r')
    item_trim_many = D().css_all('p').text().trim('r')
    item_rtrim = D().css('p').text().rtrim('r')
    item_rtrim_many = D().css_all('p').text().rtrim('r')
    item_ltrim = D().css('p').text().ltrim('r')
    item_ltrim_many = D().css_all('p').text().ltrim('p')
    item_repl = D().css('p').text().repl('raw', 'repl')
    item_repl_many = D().css_all('p').text().repl('raw', 'repl')
    item_join = D().css_all('p').text().join(', ')


class MainSchema(ItemSchema):
    """example structure DOCSTRING"""
    __PRE_VALIDATE__ = (D().is_css('title').css('title').text()
                        .is_regex('.*', 'regex assert')
                        .is_equal("OK", 'eq assert')
                        .is_not_equal("ERR", 'ne assert')
                        )
    nested_item = N().is_css('body').css('body').sub_parser(NestedItem)
    nested_flat_list = N().sub_parser(FlatListItem)
    nested_dict_item = N().sub_parser(DictItem)
    nested_list_item = N().sub_parser(ListItem)

    item_default_null = D().default(None).css('ddd > .whatisit').raw()
    item_default_val = D().default("DEFAULT").css('ddd > .whatisit').raw()
    item_attr = D().css('a').attr('href')
    item_text = D().css('a').text()
    item_attr_many = D().css_all('a').attr('href')
    item_text_many = D().css_all('a').text()
    item_raw = D().css('p').raw()
    item_raw_many = D().css_all('p').raw()
    item_str_fmt = D().css('a').attr('href').fmt('FMT {{}}')
    item_str_fmt_many = D().css_all('a').attr('href').fmt('FMT {{}}')

    item_re = D().css('p').raw().re('(\d)')
    item_re_all = D().css('p').text().re_all('r')
    item_re_sub = D().css('p').text().re_sub('raw', 'sub')
    item_re_sub_many = D().css_all('p').text().re_sub('raw', 'sub')

    item_trim = D().css('p').text().trim('r')
    item_trim_many = D().css_all('p').text().trim('r')
    item_rtrim = D().css('p').text().rtrim('r')
    item_rtrim_many = D().css_all('p').text().rtrim('r')
    item_ltrim = D().css('p').text().ltrim('r')
    item_ltrim_many = D().css_all('p').text().ltrim('r')
    item_repl = D().css('p').text().repl('raw', 'repl')
    item_repl_many = D().css_all('p').text().repl('raw', 'repl')
    item_join = D().css_all('p').text().join(', ')
