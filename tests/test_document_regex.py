import re

import pytest
from ssc_codegen import D, R
from ssc_codegen.type_state import TypeVariableState


def test_fail_compile_regex():
    with pytest.raises(re.error):
        R().re(')')

    with pytest.raises(re.error):
        R().assert_re(')')


@pytest.mark.parametrize(
    'expr',
    [
        R().re_all('').index(0),
        R().re(''),
        R().re_sub('', '')
    ])
def test_assert_expr(expr):
    assert expr.last_var_type == TypeVariableState.STRING
