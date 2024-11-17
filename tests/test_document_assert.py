import pytest
from ssc_codegen import D, R


@pytest.mark.parametrize(
    "expr",
    [
        D().is_css("a"),
        D().is_xpath("//a"),
        R().is_equal(""),
        R().split(" ").is_contains(""),
        R().is_regex(""),
    ],
)
def test_assert_expr(expr):
    pass
