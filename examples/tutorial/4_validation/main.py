import pathlib
import pprint

from parser_schema import Main

if __name__ == "__main__":
    body = pathlib.Path("index.html").read_text(encoding="utf-8")
    result = Main(body).parse()
    # OK
    pprint.pprint(result, compact=True, sort_dicts=False)
    # ERROR
    body_fail = pathlib.Path("bad_index.html").read_text(encoding="utf-8")
    try:
        Main(body_fail).parse()
    except AssertionError:
        print("bad_index.html: this page not passed validation!")
# {'title': 'Demo page', 'title_rescue_assert': 'I SAY ITS DEMO PAGE'}
# bad_index.html: this page not passed validation!