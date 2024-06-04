import pytest

from ssc_codegen import D, N, R, ItemSchema
from ssc_codegen.type_state import TypeVariableState


def test_fail_str_format():
    with pytest.raises(SyntaxError):
        R().fmt('wow')


@pytest.mark.parametrize(
    'expr',
    [
        R().split(' ').index(0),
        R().trim(''),
        R().ltrim(''),
        R().rtrim(''),
        R().repl('', ''),
        R().fmt('{{}}'),
    ]
)
def test_string_expr(expr):
    assert expr.last_var_type == TypeVariableState.STRING
