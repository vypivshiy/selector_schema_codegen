from ssc_codegen import D, ItemSchema


class Main(ItemSchema):
    """string operations example

    USAGE:
        - pass index.html document from 2_string_operations folder
    """
    title_orig = D().css('title').text()
    # simple string operations
    # 1. format
    title_fmt = D().css('title').text().fmt("TITLE - {{}} - END.")
    # 2. trim operations (default - whitespaces
    title_trim = D().css('title').text().trim()
    title_trim2 = D().css('title').text().trim().trim('vvv')
    # 2.1. left or right trim only
    title_rtrim = D().css('title').text().rtrim('vvv   ')
    title_ltrim = D().css('title').text().ltrim('   vvv')
    # 3. replace operations
    title_repl = D().css('title').text().repl('vvv   ', '===').repl('   vvv', '===')
    # 4. split by parts
    title_split = D().css('title').text().split(' ')
    # 4.1 same string operations allowed
    title_split_fmt = D().css('title').text().split(' ').fmt("({{}})")
    # 5. regex:
    title_re = D().css('title').text().re('vvv(.*?)vvv')
    title_re_sub = D().css('title').text().re_sub('vvv(.*?)vvv', "My Title")

    # multiple values operations allowed
    items_orig = D().css_all('.items > li').text()
    items_str_operations = D().css_all('.items > li').text().repl('__', '')
    # convert sequence of str to str
    items_str_join = D().css_all('.items > li').text().join(', ')
    items_str_digits = D().css_all('.items > li').text().re_sub('\D+', '')