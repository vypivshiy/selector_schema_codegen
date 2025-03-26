import re

from ssc_codegen import Json, R, ItemSchema

# most difficult step:
# write correct regular expression for extract a valid json structure

# allow pass patterns in verbose mode
# codegen automatically convert to normal pattern
JSON_PATTERN = re.compile(
    r"""
var\s+\w+\s*=\s*     # var data =
(\[[\s\S]*?\])       # json content
;                    # END
""",
    re.X,
)


class Author(Json):
    name: str
    goodreads_links: str
    slug: str


class Quote(Json):
    # mark as array entrypoint
    # if object (map/dict) contains in document - do not add it
    __IS_ARRAY__ = True

    tags: list[str]
    author: Author
    text: str


class Main(ItemSchema):
    data = R().re(JSON_PATTERN).jsonify(Quote)
