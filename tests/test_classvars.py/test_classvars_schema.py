from ssc_codegen.compiler import compile
from ssc_codegen.converters.py_bs4 import CONVERTER as BS4_CONVERTER
from ssc_codegen.converters.py_parsel import CONVERTER as PARSEL_CONVERTER
from ssc_codegen.converters.py_selectolax import CONVERTER as SLAX_CONVERTER
from ssc_codegen.converters.py_base import BasePyCodeConverter

import pytest

from ssc_codegen import ItemSchema, CV, D


class LiteralsSchema(ItemSchema):
    CV_NONE = CV(None)
    CV_INT = CV(100)
    CV_FLOAT = CV(3.14)
    CV_STR = CV("test")
    CV_LIST_STR = CV(["foo", "bar"])


class PrimarySchema(ItemSchema):
    # throw exc for every field and captupe classvar value
    RET_CV = CV(1, "PrimarySchema.RET_CV", returns=True)
    SELF_CV = CV([], "PrimarySchema.SELF_CV")

    f_none = D(LiteralsSchema.CV_NONE).is_css("x").css("x::text")
    f_int = (
        D(LiteralsSchema.CV_INT).is_css("x").css("x::text").fmt("{{}}").to_int()
    )
    f_str = D(LiteralsSchema.CV_STR).is_css("x").css("x::text").fmt("{{}}")
    f_float = (
        D(LiteralsSchema.CV_FLOAT)
        .is_css("x")
        .css("x::text")
        .fmt("{{}}")
        .to_float()
    )

    f_lst_str = D(SELF_CV).is_css("x[href]").css_all("x::text")


@pytest.mark.parametrize(
    "converter", [BS4_CONVERTER, PARSEL_CONVERTER, SLAX_CONVERTER]
)
def test_classvars_literals(converter: BasePyCodeConverter) -> None:
    module = compile(LiteralsSchema, converter=converter)
    assert module.LiteralsSchema.CV_NONE is None
    assert module.LiteralsSchema.CV_INT == 100
    assert module.LiteralsSchema.CV_FLOAT == 3.14
    assert module.LiteralsSchema.CV_STR == "test"
    assert module.LiteralsSchema.CV_LIST_STR == ["foo", "bar"]


@pytest.mark.parametrize(
    "converter", [BS4_CONVERTER, PARSEL_CONVERTER, SLAX_CONVERTER]
)
def test_usage_classvars_literal(converter: BasePyCodeConverter) -> None:
    module = compile(LiteralsSchema, PrimarySchema, converter=converter)

    assert module.PrimarySchema.RET_CV == 1
    assert module.PrimarySchema.SELF_CV == []

    result = module.PrimarySchema("").parse()
    assert result["RET_CV"] == 1

    assert result["f_none"] is None
    assert result["f_int"] == 100
    assert result["f_float"] == 3.14
    assert result["f_str"] == "test"
    assert result["f_lst_str"] == []

    # override classvars (compiled bytecode only)
    module.PrimarySchema.SELF_CV = ["a", "b", "c"]
    module.LiteralsSchema.CV_STR = "test passed"
    result2 = module.PrimarySchema("").parse()

    assert result2["f_str"] == "test passed"
    assert result2["f_lst_str"] == ["a", "b", "c"]
