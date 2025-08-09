from ssc_codegen.compiler import compile
from ssc_codegen.converters.py_bs4 import CONVERTER as BS4_CONVERTER
from ssc_codegen.converters.py_parsel import CONVERTER as PARSEL_CONVERTER
from ssc_codegen.converters.py_selectolax import CONVERTER as SLAX_CONVERTER
from ssc_codegen.converters.py_base import BasePyCodeConverter

import pytest

from ssc_codegen import ItemSchema, CV


class LiteralsSchema(ItemSchema):
    CV_NONE = CV(None)
    CV_INT = CV(100)
    CV_FLOAT = CV(3.14)
    CV_STR = CV("test")
    CV_LIST_STR = CV(["foo", "bar"])


@pytest.mark.parametrize(
    "converter", [BS4_CONVERTER, PARSEL_CONVERTER, SLAX_CONVERTER]
)
def test_classvars_literals(converter: BasePyCodeConverter):
    module = compile(LiteralsSchema, converter=converter)
    # print(module.LiteralsSchema)
    # assert module.LiteralsSchema.CV_NONE is None
