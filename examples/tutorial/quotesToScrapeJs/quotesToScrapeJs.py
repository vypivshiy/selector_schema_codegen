from ssc_codegen import Json, R, ItemSchema


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
    # most difficult step:
    # write correct regular expression for extract a valid json structure
    data = R().re(r'var\s+\w+\s*=\s*(\[[\s\S]*?\]);').jsonify(Quote)
