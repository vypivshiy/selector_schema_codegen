# json-struct: Autogenerated by ssc-gen
from ssc_codegen import Json
class Attributes(Json):
    spam: float
    eggs: str
    default: None

class Content(Json):
    a: list[str]
    attributes: Attributes