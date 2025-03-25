import pytest
from typing import Pattern
import re
from ssc_codegen.document_utlis import unverbosify_regex


@pytest.mark.parametrize(
    "pattern,expected",
    [
        ("", ""),
        ("abc", "abc"),
        (re.compile(r"abc"), "abc"),
        (re.compile(r"abc  # TEST", re.X), "abc"),
        (
            re.compile(
                r"""
        \w+\s*  # word
        \d+\s*  # digits
        # some consts
        abcdef
        ooooooo\#
        """,
                re.X,
            ),
            r"\w+\s*\d+\s*abcdefooooooo#",
        ),
    ],
)
def test_unverbosify_regex(pattern: str | Pattern, expected: str) -> None:
    assert unverbosify_regex(pattern) == expected
