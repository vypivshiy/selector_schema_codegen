import pathlib
import pprint

from parser_schema import Main
import json

if __name__ == "__main__":
    body = pathlib.Path("index.html").read_text(encoding="utf-8")
    result = Main(body).parse()
    print(json.dumps(result, indent=4))
# {
#     "jsn": {
#         "a": [
#             "b",
#             "c"
#         ],
#         "attributes": {
#             "spam": 1.0,
#             "eggs": "foobar",
#             "default": null
#         }
#     }
# }
#
# Process finished with exit code 0