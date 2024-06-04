import pytest
from ssc_codegen import D, R


@pytest.mark.parametrize(
    'expr',
    [
        D().assert_css('a'),
        D().assert_xpath('//a'),
        R().assert_eq(''),
        R().split(' ').assert_in(''),
        R().assert_re('')
    ])
def test_assert_expr(expr):
    pass
