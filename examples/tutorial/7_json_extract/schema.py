from ssc_codegen import ItemSchema, R, Json, D


# new special marker for json serializations
class Attributes(Json):
    spam: float
    eggs: str
    default: str | None

class Content(Json):
    a: list[str]
    # can be nested
    attributes: Attributes


class Main(ItemSchema):
    jsn = (D()
           .css('script').text()
            # not allowed modify later
            # accept string only
           .jsonify(Content))
