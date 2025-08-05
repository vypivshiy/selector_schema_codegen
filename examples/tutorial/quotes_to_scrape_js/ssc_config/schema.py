"""Example how to parse json-like data from plain HTML

"""
from ssc_codegen import Json, R, ItemSchema
import re

# most difficult step:
# write correct regular expression for extract a valid json structure

# allow write patterns in verbose mode for simplify documentation
# codegen automatically convert it to normal pattern
JSON_PATTERN = re.compile(
    r"""
    var\s+data\s*=\s*     # START ANCHOR var data =
    (
        \[                # START ARRAY
        .*                # JSON DATA
        \]                # END ARRAY
    )
    ;\s+for              # END ANCHOR
""",
    # verbose + re.DOTALL mode
    # NOTE: javascript ES6 standart does not support this flag
    re.X | re.S,
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
