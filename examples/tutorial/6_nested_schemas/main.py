import pathlib
import pprint

from parser_schema import Main
import json

if __name__ == "__main__":
    body = pathlib.Path("index.html").read_text(encoding="utf-8")
    result = Main(body).parse()
    print(json.dumps(result, indent=4))
# {
#     "multi_nested": {
#         "item_rec2": {
#             "item_rec3": {
#                 "item_rec4": {
#                     "items": [
#                         "item41",
#                         "item42",
#                         "item43",
#                         "item44"
#                     ]
#                 },
#                 "items": [
#                     "item31"
#                 ],
#                 "b_text": "b_item3"
#             },
#             "items": [
#                 "item21",
#                 "item22"
#             ],
#             "href": "/items2"
#         },
#         "items": [
#             "item11",
#             "item12",
#             "item13"
#         ],
#         "href": "/items1"
#     },
#     "item1": {
#         "items": [
#             "item11",
#             "item12",
#             "item13"
#         ],
#         "href": "/items1"
#     },
#     "item2": {
#         "items": [
#             "item21",
#             "item22"
#         ],
#         "href": "/items2"
#     },
#     "item3": {
#         "items": [
#             "item31"
#         ],
#         "b_text": "b_item3"
#     },
#     "item4": {
#         "items": [
#             "item41",
#             "item42",
#             "item43",
#             "item44"
#         ]
#     }
# }