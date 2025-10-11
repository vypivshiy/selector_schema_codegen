"""helper function helps check converter implementation"""

import pytest

from ssc_codegen.converters.base import BaseCodeConverter


# go
from ssc_codegen.converters.go_goquery import CONVERTER as go_goquery

# js
from ssc_codegen.converters.js_pure import CONVERTER as js_pure

# python
from ssc_codegen.converters.py_bs4 import CONVERTER as py_bs4
from ssc_codegen.converters.py_parsel import CONVERTER as py_parsel
from ssc_codegen.converters.py_selectolax import CONVERTER as py_selectolax

# lua
from ssc_codegen.converters.lua_htmlparser import CONVERTER as lua_htmlparser

from ssc_codegen.tokens import TokenType


@pytest.mark.parametrize(
    "name,converter",
    [
        ("py_bs4", py_bs4),
        ("py_parsel", py_parsel),
        ("py_selectolax", py_selectolax),
        ("go_goquery", go_goquery),
        ("js_pure", js_pure),
        ("lua_htmlparser", lua_htmlparser),
    ],
)
def test_converter_impl(
    name: str,
    converter: BaseCodeConverter,
) -> None:
    def _any_token_impl(token: TokenType) -> bool:
        """return True if convert token configured"""
        if (
            token in converter.pre_definitions
            or token in converter.post_definitions
        ):
            return True

        for pre_def in converter.pre_definitions:
            if isinstance(pre_def, tuple) and token == pre_def[0]:
                return True
        for post_def in converter.post_definitions:
            if isinstance(post_def, tuple) and token == post_def[0]:
                return True

    not_implemented: list[TokenType] = []
    for token in TokenType:
        if token in converter.TEST_EXCLUDE_NODES:
            continue
        if not _any_token_impl(token):
            not_implemented.append(token)
    if not_implemented:
        msg = (
            ", ".join(f"`{t.name}`" for t in not_implemented)
            + " not implemented exprs"
        )
        assert not not_implemented, msg
