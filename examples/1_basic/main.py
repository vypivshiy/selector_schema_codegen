import pathlib
import pprint

from parser_schema import Main

if __name__ == "__main__":
    body = pathlib.Path("index.html").read_text(encoding="utf-8")
    result = Main(body).parse()
    pprint.pprint(result, compact=True, sort_dicts=False)
# {'item_sc': 'item sc',
#  'a_href': 'https://example.com',
#  'a_text': 'example page',
#  'var_int': 100,
#  'var_float': 3.14,
#  'var_list': ['1 first', '2 second', '3 third', '4 four'],
#  'var_list_ints': [1, 2, 3, 4]}
