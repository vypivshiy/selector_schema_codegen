import pathlib
import pprint

from parser_schema import Main

if __name__ == "__main__":
    body = pathlib.Path("index.html").read_text(encoding="utf-8")
    result = Main(body).parse()
    pprint.pprint(result, compact=True, sort_dicts=False)
# {'list_group': [{'p_tag': 'item1', 'a_href': '/link1'},
#                 {'p_tag': 'item2', 'a_href': '/link2'},
#                 {'p_tag': 'item3', 'a_href': '/link3'},
#                 {'p_tag': 'item4', 'a_href': '/link4'}],
#  'dict_group': {'key1': 'value1',
#                 'key2': 'value2',
#                 'key3': 'value3',
#                 'key4': 'value4'},
#  'flat_list_group': ['item1', 'item2', 'item3'],
#  'title': 'Demo page 2'}