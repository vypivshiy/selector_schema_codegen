import re
from typing import Optional

from src.analyzer import VariableState
from src.codegen_tools import ABCExpressionTranslator, generate_code


class Translator(ABCExpressionTranslator):
    # variable name (be overwritten step-by-step)
    VAR_NAME = "val"
    # first variable assigment (if needed)
    FIRST_ASSIGMENT = "="
    # next assignments
    ASSIGMENT = "="
    # \n, ; for example
    DELIM_LINES = "\n"
    # delim for try\catch constructions
    DELIM_DEFAULT_WRAPPER = "\n\t"
    # imports
    REGEX_IMPORT = "import re"
    SELECTOR_IMPORT = "from bs4 import BeautifulSoup"
    # selector type
    SELECTOR_TYPE = "BeautifulSoup"

    ENUMERATE_VARS: bool = False  # TODO feature

    @classmethod
    def get_var_name(cls, index: int):
        return cls.VAR_NAME

    @classmethod
    def op_wrap_code_with_default_value(
        cls,
        state: Optional[VariableState],
        var_i: int,
        code: str,
        default_value: str,
    ) -> str:
        d = cls.DELIM_DEFAULT_WRAPPER
        code = d.join([line for line in code.split(cls.DELIM_LINES)])
        return f"try:{d}{code}\nexcept Exception:{d}return {default_value}"

    @classmethod
    def op_wrap_code(
        cls, state: Optional[VariableState], var_i: int, code: str
    ) -> str:
        d = cls.DELIM_LINES
        return f"{code}{d}return {cls.VAR_NAME}"

    @classmethod
    def op_css(cls, state: VariableState, var_i: int, query: str) -> str:
        var_name = cls.get_var_name(var_i)
        return f"{var_name}.select_one({query})"

    @classmethod
    def op_xpath(cls, state: VariableState, var_i: int, query: str) -> str:
        raise NotImplementedError("Bs4 not support xpath")

    @classmethod
    def op_css_all(cls, state: VariableState, var_i: int, query: str) -> str:
        var_name = cls.get_var_name(var_i)
        return f"{var_name}.select({query})"

    @classmethod
    def op_xpath_all(cls, state: VariableState, var_i: int, query: str) -> str:
        raise NotImplementedError("Bs4 not support xpath")

    @classmethod
    def op_attr(cls, state: VariableState, var_i: int, attr_name: str) -> str:
        var_name = cls.get_var_name(var_i)
        if state is VariableState.ARRAY:
            return f"{var_name}.get({attr_name})"
        return f"[i.get({attr_name}) for i {var_name}]"

    @classmethod
    def op_text(cls, state: VariableState, var_i: int) -> str:
        var_name = cls.get_var_name(var_i)
        if state is VariableState.ARRAY:
            return f"[i.get_text() for i in {var_name}]"
        return f"{var_name}.get_text()"

    @classmethod
    def op_raw(cls, state: VariableState, var_i: int) -> str:
        var_name = cls.get_var_name(var_i)
        if state is VariableState.ARRAY:
            return f"[i.__str__() for i {var_name}]"
        return f"{var_name}.__str__()"

    @classmethod
    def op_string_split(
        cls, state: VariableState, var_i: int, substr: str, count=None
    ) -> str:
        var_name = cls.get_var_name(var_i)
        if count and count not in ("-1", -1):
            return f"{var_name}.split({substr}, {count})"
        return f"{var_name}.split({substr})"

    @classmethod
    def op_string_format(
        cls, state: VariableState, var_i: int, substr: str
    ) -> str:
        var_name = cls.get_var_name(var_i)
        f_string = re.sub(r"\{\{.*}}", "{}", substr)
        return f"{f_string}.format({var_name})"

    @classmethod
    def op_string_trim(
        cls, state: VariableState, var_i: int, substr: str
    ) -> str:
        var_name = cls.get_var_name(var_i)
        return f"{var_name}.strip({substr})"

    @classmethod
    def op_string_ltrim(
        cls, state: VariableState, var_i: int, substr: str
    ) -> str:
        var_name = cls.get_var_name(var_i)
        return f"{var_name}.lstrip({substr})"

    @classmethod
    def op_string_rtrim(cls, state: VariableState, var_i: int, substr) -> str:
        var_name = cls.get_var_name(var_i)
        return f"{var_name}.rstrip({substr})"

    @classmethod
    def op_string_replace(
        cls, state: VariableState, var_i: int, old: str, new: str, count=None
    ) -> str:
        var_name = cls.get_var_name(var_i)
        if count and count not in ("-1", -1):
            return f"{var_name}.replace({old}, {new}, {count})"
        return f"{var_name}.replace({old}, {new})"

    @classmethod
    def op_string_join(
        cls, state: VariableState, var_i: int, string: str
    ) -> str:
        var_name = cls.get_var_name(var_i)
        return f"{string}.join({var_name})"

    @classmethod
    def op_regex(cls, state: VariableState, var_i: int, pattern: str) -> str:
        var_name = cls.get_var_name(var_i)
        return f"re.search(r{pattern}, {var_name})[1]"

    @classmethod
    def op_regex_all(
        cls, state: VariableState, var_i: int, pattern: str
    ) -> str:
        var_name = cls.get_var_name(var_i)
        return f"re.findall(r{pattern}, {var_name})"

    @classmethod
    def op_regex_sub(
        cls,
        state: VariableState,
        var_i: int,
        pattern: str,
        repl: str,
        count=None,
    ) -> str:
        var_name = cls.get_var_name(var_i)
        if count:
            return f"re.sub(r{pattern}, {repl}, {var_name}, {count})"
        return f"re.sub(r{pattern}, {repl}, {var_name})"

    @classmethod
    def op_slice(
        cls, state: VariableState, var_i: int, start: str, end: str
    ) -> str:
        var_name = cls.get_var_name(var_i)
        return f"{var_name}[{start}, {end}]"

    @classmethod
    def op_index(cls, state: VariableState, var_i: int, index: str) -> str:
        var_name = cls.get_var_name(var_i)
        return f"{var_name}[{index}]"

    @classmethod
    def op_first_index(cls, state: VariableState, var_i: int):
        var_name = cls.get_var_name(var_i)
        return f"{var_name}[0]"

    @classmethod
    def op_last_index(cls, state: VariableState, var_i: int):
        var_name = cls.get_var_name(var_i)
        return f"{var_name}[-1]"

    @classmethod
    def op_assert_equal(cls, state: VariableState, var_i: int, substring: str):
        var_name = cls.get_var_name(var_i)
        return f"assert {var_name} == {substring}"

    @classmethod
    def op_assert_css(cls, state: VariableState, var_i: int, query: str):
        return f"assert {cls.op_css(state, var_i, query)}"

    @classmethod
    def op_assert_xpath(
        cls, state: VariableState, var_i: int, query: str
    ) -> str:
        return f"assert {cls.op_xpath(state, var_i, query)}"

    @classmethod
    def op_assert_re_match(
        cls, state: VariableState, var_i: int, pattern: str
    ) -> str:
        return f"assert {cls.op_regex(state, var_i, pattern)}"

    @classmethod
    def op_assert_starts_with(
        cls, state: VariableState, var_i: int, prefix: str
    ) -> str:
        var_name = cls.get_var_name(var_i)
        return f"assert {var_name}.startswith({prefix})"

    @classmethod
    def op_assert_ends_with(
        cls, state: VariableState, var_i: int, suffix: str
    ) -> str:
        var_name = cls.get_var_name(var_i)
        return f"assert {var_name}.endswith({suffix})"

    @classmethod
    def op_assert_contains(
        cls, state: VariableState, var_i: int, substring: str
    ) -> str:
        var_name = cls.get_var_name(var_i)
        return f"assert {substring} in {var_name}"


if __name__ == "__main__":
    from src.lexer import tokenize

    source = """
assertCss "head > title"

css "head > title"
text
assertContains "spam"

format "https://books.toscrape.com/catalogue/{{}}"
"""
    raw_tokens = tokenize(source)
    block = generate_code(raw_tokens, Translator())
    print(block.selector_import)
    print(block.regex_import)
    print()
    print(block.code)
