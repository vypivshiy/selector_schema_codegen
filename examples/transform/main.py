from ssc_codegen import ItemSchema, D
from .custom_transforms import UpperCaseTransform, ListUpperCaseTransform, Base64Transform


class Main(ItemSchema):
    upper_title = D().css("title::text").transform(UpperCaseTransform())
    upper_hrefs = D().css_all("a::attr(href)").transform(ListUpperCaseTransform())
    b64_title = D().css("title::text").transform(Base64Transform())
