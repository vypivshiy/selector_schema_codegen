import pytest

from ssc_codegen import D, R
from ssc_codegen.document import BaseDocument


@pytest.mark.parametrize(
    "expr",
    [
        D().is_css("a"),
        D().is_xpath("//a"),
        R().is_equal(""),
        R().to_int().is_equal(0),
        R().to_float().is_equal(0.1),
        R().is_not_equal(""),
        R().to_int().is_not_equal(1),
        R().to_float().is_not_equal(0.1),
        R().split(" ").is_contains(""),
        R().is_regex("k"),
        R().split(" ").to_int().is_contains(1),
        R().split(" ").to_float().is_contains(0.1),
    ],
)
def test_assert_expr(expr: BaseDocument) -> None:
    assert expr
