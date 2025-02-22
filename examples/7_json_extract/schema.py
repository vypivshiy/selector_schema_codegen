# you can generate json template structs from original json:
#  ssc-gen json-gen raw_json.json -o template_json_schema.py
# from stdin:
# echo '{"a": ["b", "c"], "attributes": {"spam": 1.0, "eggs": "foobar", "default": null}}' | ssc-gen json-gen -o template_json_schema.py
from ssc_codegen import ItemSchema, Json, D


# new special marker for json serializations
class Attributes(Json):
    spam: float
    eggs: str
    default: None

class Content(Json):
    a: list[str]
    attributes: Attributes

class Main(ItemSchema):
    jsn = (D()
           .css('script').text()
            # not allowed to modify later
            # accept string
           .jsonify(Content))
