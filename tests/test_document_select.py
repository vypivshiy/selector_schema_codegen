import pytest

from ssc_codegen import D, N, R, ItemSchema
from ssc_codegen.type_state import TypeVariableState


@pytest.mark.parametrize(
    'expr',
    [D().css('a').css_all('b'),
     D().xpath('//a').xpath_all('//b'),
     D().css_all('a'),
     D().xpath_all('a'),
     ]
)
def test_document_to_list_document(expr):
    pass


@pytest.mark.parametrize(
    'expr',
    [
        D().raw(),
        D().text(),
        R(),
        D().attr('a'),
        D().css_all('a').index(0).text(),
        D().xpath_all('//a').text().index(0),

    ])
def test_doc_to_str(expr):
    assert expr.last_var_type == TypeVariableState.STRING


@pytest.mark.parametrize(
    'expr',
[
    D().css_all('a').text(),
    D().xpath_all('//a').text(),
    D().css_all('a').attr('href'),
    D().xpath_all('//a').attr('href'),
])
def test_do_to_list_str(expr):
    assert expr.last_var_type == TypeVariableState.LIST_STRING