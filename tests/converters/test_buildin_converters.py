"""helper function helps check converter implementation"""

import pytest
from helpers_converters import (
    CSS_TOKENS_IMPL,
    REQUIRED_TOKENS_CONVERT_IMPL,
    TYPING_TOKENS_CONVERT_IMPL,
    XPATH_TOKENS_IMPL,
    new_converter_check,
)

from ssc_codegen.converters.base import BaseCodeConverter

# dart
from ssc_codegen.converters.dart_universal_html import (
    converter as dart_universal_html,
)

# go
from ssc_codegen.converters.go_goquery import converter as go_goquery

# js
from ssc_codegen.converters.js_pure import converter as js_pure

# python
from ssc_codegen.converters.py_bs4 import converter as py_bs4
from ssc_codegen.converters.py_parsel import converter as py_parsel
from ssc_codegen.converters.py_scrapy import converter as py_scrapy
from ssc_codegen.converters.py_selectolax import converter as py_selectolax
from ssc_codegen.tokens import TokenType

_TEST_BS4 = new_converter_check(
    "py_bs4",
    converter=py_bs4,
    include=REQUIRED_TOKENS_CONVERT_IMPL
    | CSS_TOKENS_IMPL
    | TYPING_TOKENS_CONVERT_IMPL,
    exclude={TokenType.JSON_FIELD},
)

_TEST_PARSEL = new_converter_check(
    "py_parsel",
    converter=py_parsel,
    include=REQUIRED_TOKENS_CONVERT_IMPL
    | CSS_TOKENS_IMPL
    | XPATH_TOKENS_IMPL
    | TYPING_TOKENS_CONVERT_IMPL,
    exclude={TokenType.JSON_FIELD},
)

_TEST_SELECTOLAX = new_converter_check(
    "py_selectolax",
    converter=py_selectolax,
    include=REQUIRED_TOKENS_CONVERT_IMPL
    | CSS_TOKENS_IMPL
    | TYPING_TOKENS_CONVERT_IMPL,
    exclude={TokenType.JSON_FIELD},
)
_TEST_SCRAPY = new_converter_check(
    "py_scrapy",
    converter=py_scrapy,
    include=REQUIRED_TOKENS_CONVERT_IMPL
    | CSS_TOKENS_IMPL
    | XPATH_TOKENS_IMPL
    | TYPING_TOKENS_CONVERT_IMPL,
    exclude={TokenType.JSON_FIELD},
)
_TEST_DART = new_converter_check(
    "dart_universal_html",
    converter=dart_universal_html,
    include=REQUIRED_TOKENS_CONVERT_IMPL
    | CSS_TOKENS_IMPL
    | TYPING_TOKENS_CONVERT_IMPL,
    exclude={TokenType.JSON_FIELD},
)

_TEST_GO_GOQUERY = new_converter_check(
    "go_goquery",
    converter=go_goquery,
    include=REQUIRED_TOKENS_CONVERT_IMPL
    | CSS_TOKENS_IMPL
    | TYPING_TOKENS_CONVERT_IMPL,
    # 1. go structs don't need init constructor
    # 2. try/catch (default) operation
    #    realized by defer func() + rescue
    exclude={
        TokenType.STRUCT_INIT,
        TokenType.EXPR_DEFAULT_END,
        TokenType.JSON_FIELD,
    },
)

_TEST_JS_PURE = new_converter_check(
    "js_pure",
    converter=js_pure,
    include=REQUIRED_TOKENS_CONVERT_IMPL | CSS_TOKENS_IMPL | XPATH_TOKENS_IMPL,
    # pure js dont need imports
    # not need json serialize
    exclude={TokenType.IMPORTS, TokenType.JSON_FIELD, TokenType.JSON_STRUCT},
)


@pytest.mark.parametrize(
    "name,converter,tokens_include,tokens_exclude",
    [
        _TEST_BS4,
        _TEST_PARSEL,
        _TEST_SELECTOLAX,
        _TEST_SCRAPY,
        _TEST_DART,
        _TEST_GO_GOQUERY,
        _TEST_JS_PURE,
    ],
)
def test_converter_impl(
    name: str,
    converter: BaseCodeConverter,
    tokens_include: set[TokenType],
    tokens_exclude: set[TokenType],
) -> None:
    def _any_token_impl(token: TokenType) -> bool:
        """return True if convert token configured"""
        return converter.pre_definitions.get(
            token, False
        ) or converter.post_definitions.get(token, False)  # type: ignore

    for t in tokens_include:
        if t in tokens_exclude:
            continue
        assert _any_token_impl(t), (
            f"{name}: Token TokenType.{t.name} not implemented"
        )
