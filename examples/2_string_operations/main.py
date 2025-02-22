import pathlib
import pprint

from parser_schema import Main

if __name__ == "__main__":
    body = pathlib.Path("index.html").read_text(encoding="utf-8")
    result = Main(body).parse()
    pprint.pprint(result, compact=True, sort_dicts=False)
# {
#  'title_orig': '  vvvDemo page 1vvv   ',
#  'title_fmt': 'TITLE -   vvvDemo page 1vvv    - END.',
#  'title_trim': 'vvvDemo page 1vvv',
#  'title_trim2': 'Demo page 1',
#  'title_rtrim': '  vvvDemo page 1',
#  'title_ltrim': 'Demo page 1vvv   ',
#  'title_repl': '  vvvDemo page 1===',
#  'title_split': ['', '', 'vvvDemo', 'page', '1vvv', '', '', ''],
#  'title_split_fmt': ['(vvvDemo)', '(page)', '(1vvv)'],
#  'title_re': 'Demo page 1',
#  'title_re_sub': '  My Title   ',
#  'items_orig': ['__1 first__', '__2 second__', '__3 third__', '__4 four__'],
#  'items_str_operations': ['1 first', '2 second', '3 third', '4 four'],
#  'items_str_join': '__1 first__, __2 second__, __3 third__, __4 four__',
#  'items_str_digits': ['1', '2', '3', '4']
#  }
