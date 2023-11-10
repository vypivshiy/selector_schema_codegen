import re
from typing import Optional

from src.analyzer import VariableState
from src.codegen_tools import ABCExpressionTranslator, generate_code


class Translator(ABCExpressionTranslator):
    FIRST_VAR_ASSIGMENT = "val"
    VAR_NAME = "val"
    FIRST_ASSIGMENT = "="
    ASSIGMENT = "="
    DELIM_LINES = "\n"
    DELIM_DEFAULT_WRAPPER = "\n    "
    REGEX_IMPORT = "import re"
    SELECTOR_IMPORT = "from parsel import Selector"
    SELECTOR_TYPE = "Selector"

    def op_no_ret(self, state, i):
        return ""

    def op_ret(self, state, i):
        return f"return {self.VAR_NAME}"

    def op_wrap_code_with_default_value(
            self,
            state: Optional[VariableState],
            var_i: int,
            code: str,
            default_value: str,
    ) -> str:
        d = self.DELIM_DEFAULT_WRAPPER
        code = d.join([line for line in code.split(self.DELIM_LINES)])
        return f"try:{d}{code}{d}{self.op_ret(state, var_i)}\nexcept Exception:{d}return {default_value}"

    def op_wrap_code(
            self, state: Optional[VariableState], var_i: int, code: str
    ) -> str:
        d = self.DELIM_LINES
        return f"{code}{d}"

    def op_css(self, state: VariableState, var_i: int, query: str) -> str:
        return f".css({query})"

    def op_xpath(self, state: VariableState, var_i: int, query: str) -> str:
        return f".xpath({query})"

    def op_css_all(self, state: VariableState, var_i: int, query: str) -> str:
        return f".css({query})"

    def op_xpath_all(self, state: VariableState, var_i: int, query: str) -> str:
        return f".xpath({query})"

    def op_attr(self, state: VariableState, var_i: int, attr_name: str) -> str:
        return f".attrib[{attr_name}]"

    def op_text(self, state: VariableState, var_i: int) -> str:
        if state is VariableState.ARRAY:
            return f'.xpath("./text()").getall()'
        return f'.xpath("./text()").get()'

    def op_raw(self, state: VariableState, var_i: int) -> str:
        if state == VariableState.ARRAY:
            return f".getall()"
        return f".get()"

    def op_string_split(
            self, state: VariableState, var_i: int, substr: str, count=None
    ) -> str:
        if count and count not in ("-1", -1):
            return f".split({substr}, {count})"
        return f".split({substr})"

    def op_string_format(
            self, state: VariableState, var_i: int, substr: str
    ) -> str:
        f_string = re.sub(r"\{\{.*}}", "{}", substr)
        return f"{f_string}.format({self.VAR_NAME})"

    def op_string_trim(
            self, state: VariableState, var_i: int, substr: str
    ) -> str:
        return f".strip({substr})"

    def op_string_ltrim(
            self, state: VariableState, var_i: int, substr: str
    ) -> str:
        return f".lstrip({substr})"

    def op_string_rtrim(self, state: VariableState, var_i: int, substr) -> str:
        return f".rstrip({substr})"

    def op_string_replace(
            self, state: VariableState, var_i: int, old: str, new: str, count=None
    ) -> str:
        if count and count not in ("-1", -1):
            return f".replace({old}, {new}, {count})"
        return f".replace({old}, {new})"

    def op_string_join(
            self, state: VariableState, var_i: int, string: str
    ) -> str:
        return f"{string}.join({self.VAR_NAME})"

    def op_regex(self, state: VariableState, var_i: int, pattern: str) -> str:
        return f"re.search(r{pattern}, {self.VAR_NAME})[1]"

    def op_regex_all(
            self, state: VariableState, var_i: int, pattern: str
    ) -> str:
        return f"re.findall(r{pattern}, {self.VAR_NAME})"

    def op_regex_sub(
            self,
            state: VariableState,
            var_i: int,
            pattern: str,
            repl: str,
            count=None,
    ) -> str:
        if count:
            return f"re.sub(r{pattern}, {repl}, {self.VAR_NAME}, {count})"
        return f"re.sub(r{pattern}, {repl}, {self.VAR_NAME})"

    def op_slice(
            self, state: VariableState, var_i: int, start: str, end: str
    ) -> str:
        return f"[{start}, {end}]"

    def op_index(self, state: VariableState, var_i: int, index: str) -> str:
        return f"[{index}]"

    def op_first_index(self, state: VariableState, var_i: int):
        return f"[0]"

    def op_last_index(self, state: VariableState, var_i: int):
        return f"[-1]"

    def op_assert_equal(self, state: VariableState, var_i: int, substring: str):
        return f"assert {self.VAR_NAME} == {substring}"

    def op_assert_css(self, state: VariableState, var_i: int, query: str):
        return f"assert {self.VAR_NAME}{self.op_css(state, var_i, query)}"

    def op_assert_xpath(
            self, state: VariableState, var_i: int, query: str
    ) -> str:
        return f"assert {self.VAR_NAME}{self.op_xpath(state, var_i, query)}"

    def op_assert_re_match(
            self, state: VariableState, var_i: int, pattern: str
    ) -> str:
        return f"assert re.search(r{pattern}, {self.VAR_NAME})"

    def op_assert_starts_with(
            self, state: VariableState, var_i: int, prefix: str
    ) -> str:
        return f"assert {self.VAR_NAME}.startswith({prefix})"

    def op_assert_ends_with(
            self, state: VariableState, var_i: int, suffix: str
    ) -> str:
        return f"assert {self.VAR_NAME}.endswith({suffix})"

    def op_assert_contains(
            self, state: VariableState, var_i: int, substring: str
    ) -> str:
        return f"assert {substring} in {self.VAR_NAME}"


if __name__ == "__main__":
    from src.lexer import tokenize

    source = """
assertCss "head > title"

css "head > title"
text
assertContains "spam"
format "https://books.toscrape.com/catalogue/{{}}"
rstrip "https://"
replace "o" "a"
re "b[oa][oa]ks\."
reSub "\w+" "lol" 1
"""
    raw_tokens = tokenize(source)
    block = generate_code(raw_tokens, Translator())
    print(block.regex_import)
    print(block.selector_import)
    print()
    print(block.code)
