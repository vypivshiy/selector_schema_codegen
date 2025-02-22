import pathlib
import pprint

from parser_schema import Main

if __name__ == "__main__":
    body = pathlib.Path("index.html").read_text(encoding="utf-8")
    result = Main(body).parse()
    pprint.pprint(result, compact=True, sort_dicts=False)
# {
#  'title_ok': 'Demo page with defaults',
#  'title_null': None,
#  'title_str_default': 'unknown',
#  'title_int_default': 1,
#  'title_float_default': 3.14
#  }
