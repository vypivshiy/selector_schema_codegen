import pytest

from ssc_codegen.str_utils import (
    py_str_format_to_fstring,
    py_optimize_return_naive,
)


@pytest.mark.parametrize(
    "code,expected",
    [
        ("", ""),
        ('value = "{}".format(value1)', 'value = f"{value1}"'),
        ('value = "{}".format(value1) or None', 'value = f"{value1}" or None'),
    ],
)
def test_py_str_fmt_to_fstring(code: str, expected: str) -> None:
    out = py_str_format_to_fstring(code)
    assert out == expected


PY_RETURN_OPT_CASE_1 = (
    """
def _parseFoo(val):
    val1 = val.some_expr()
    return val1
""",
    """
def _parseFoo(val):
    return val.some_expr()
""",
)

PY_RETURN_OPT_CASE_2 = (
    """
def _parseFoo(val):
    return val
""",
    """
def _parseFoo(val):
    return val
""",
)

PY_RETURN_OPT_CASE_3 = (
    """
def _split_spam(var):
    var1 = var.foo()
    var2 = var1.bar()
    var3 = var2.baz()
    return var3
""",
    """
def _split_spam(var):
    var1 = var.foo()
    var2 = var1.bar()
    return var2.baz()
""",
)

PY_RETURN_OPT_CASE_4 = (
    """
class Spam:
    def __init__(self):
        pass

    def not_modify_me(self):
       var1 = self.foo
       var2 = var1.bar.baz
       return var2

    def _split_spam(var):
        var1 = var.foo()
        var2 = var1.bar()
        var3 = var2.baz()
        return var3

    def _parse_foo(val):
        var1 = val
        var2 = var1.super_mega_cast()
        return var2
""",
    """
class Spam:
    def __init__(self):
        pass

    def not_modify_me(self):
       var1 = self.foo
       var2 = var1.bar.baz
       return var2

    def _split_spam(var):
        var1 = var.foo()
        var2 = var1.bar()
        return var2.baz()

    def _parse_foo(val):
        var1 = val
        return var1.super_mega_cast()
""",
)


@pytest.mark.parametrize(
    "code,expected",
    [
        ("", ""),
        PY_RETURN_OPT_CASE_1,
        PY_RETURN_OPT_CASE_2,
        PY_RETURN_OPT_CASE_3,
        PY_RETURN_OPT_CASE_4,
    ],
)
def test_py_return_py_optimize_return(code: str, expected: str) -> None:
    out = py_optimize_return_naive(code)
    assert out == expected
