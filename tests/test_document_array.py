import pytest
from ssc_codegen import D, R
from ssc_codegen.type_state import TypeVariableState


@pytest.mark.parametrize(
    "expr",
    [
        D().css_all('a'),
        D().xpath_all('//a'),
        D().css_all('a').index(0).xpath_all('//a'),
    ])
def test_list_document(expr):
    assert expr.last_var_type == TypeVariableState.LIST_DOCUMENT


@pytest.mark.parametrize(
    "expr",
    [
        D().css_all('a').text(),
        D().xpath_all('//a').text(),
        D().css_all('a').attr('a'),
        D().xpath_all('//a').attr('a'),
        D().css_all('a').raw(),
        D().xpath_all('//a').raw(),
        R().split(' '),
        R().re_all('*'),
    ])
def test_list_str(expr):
    assert expr.last_var_type == TypeVariableState.LIST_STRING
