import json

import pytest


@pytest.fixture
def html_doc():
    with open('demo.html') as f:
        d = f.read()
    return d


@pytest.fixture
def json_result():
    with open('jsn.txt') as f:
        jsn = f.read()
    return jsn


def test_bs4(html_doc, json_result):
    from parsers.bs4config import MainSchema
    o = MainSchema(html_doc).parse()
    assert json.dumps(o) == json_result


def test_parsel(html_doc, json_result):
    from parsers.parselconfig import MainSchema
    o = MainSchema(html_doc).parse()
    assert json.dumps(o) == json_result


def test_slax(html_doc, json_result):
    from parsers.slaxconfig import MainSchema
    o = MainSchema(html_doc).parse()
    assert json.dumps(o) == json_result
