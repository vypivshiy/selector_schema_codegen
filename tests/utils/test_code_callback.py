from ssc_codegen.cli.code_callbacks import BaseCodeCallback
import pytest


@pytest.mark.parametrize(
    "callback,code,expected",
    [
        (BaseCodeCallback(), [""], ""),
        # Actual   :'foo\n\n\n\nbar'
        (BaseCodeCallback(), ["foo", "", "", "bar"], "foo\n\n\nbar"),
        (
            BaseCodeCallback(remove_empty_lines=True),
            ["foo", "", "", "bar"],
            "foo\nbar",
        ),
        (BaseCodeCallback(join_sep=";"), ["foo", "", "", "bar"], "foo;;;bar"),
        (
            BaseCodeCallback(remove_empty_lines=True, join_sep=";"),
            ["foo", "", "", "bar"],
            "foo;bar",
        ),
        (
            BaseCodeCallback(lambda c: c.replace("foo", "FOO")),
            ["foo", "bar"],
            "FOO\nbar",
        ),
        (
            BaseCodeCallback(
                lambda c: c.replace("foo", "FOO"),
                lambda c: c.replace("bar", "raB"),
                lambda c: c.replace("FOO", "FoF"),
            ),
            ["foo", "bar"],
            "FoF\nraB",
        ),
    ],
)
def test_code_callback(
    callback: BaseCodeCallback, code: list[str], expected: str
) -> None:
    out = callback(code)
    assert out == expected
