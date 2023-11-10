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
    SELECTOR_IMPORT = "from bs4 import BeautifulSoup"

    SELECTOR_TYPE = "BeautifulSoup"

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
        return f"try:{d}{code}{d}{self.op_ret(state, var_i)}{self.DELIM_LINES}except Exception:{d}return {default_value}"

    def op_wrap_code(
            self, state: Optional[VariableState], var_i: int, code: str
    ) -> str:
        d = self.DELIM_LINES
        return f"{code}{d}"

    def op_css(self, state: VariableState, var_i: int, query: str) -> str:
        return f".select_one({query})"

    def op_xpath(self, state: VariableState, var_i: int, query: str) -> str:
        raise NotImplementedError("Bs4 not support xpath")

    def op_css_all(self, state: VariableState, var_i: int, query: str) -> str:
        return f".select({query})"

    def op_xpath_all(self, state: VariableState, var_i: int, query: str) -> str:
        raise NotImplementedError("Bs4 not support xpath")

    def op_attr(self, state: VariableState, var_i: int, attr_name: str) -> str:
        if state is VariableState.ARRAY:
            if self.FLUENT_OPTIMISATION:
                return f"{self.DELIM_LINES}{self.VAR_NAME} {self.ASSIGMENT} [i.get({attr_name}) for i {self.VAR_NAME}]"
            return f"[i.get({attr_name}) for i {self.VAR_NAME}]"
        return f".get({attr_name})"

    def op_text(self, state: VariableState, var_i: int) -> str:
        if state is VariableState.ARRAY:
            if self.FLUENT_OPTIMISATION:
                return f"{self.DELIM_LINES}{self.VAR_NAME} {self.ASSIGMENT} [i.get_text() for i in {self.VAR_NAME}]"
            return f"[i.get_text() for i in {self.VAR_NAME}]"
        return f".get_text()"

    def op_raw(self, state: VariableState, var_i: int) -> str:
        if state is VariableState.ARRAY:
            if self.FLUENT_OPTIMISATION:
                return f"{self.DELIM_LINES}{self.VAR_NAME} {self.ASSIGMENT} [i.__str__() for i {self.VAR_NAME}]"
            return f"[i.__str__() for i {self.VAR_NAME}]"
        return f"{self.VAR_NAME}.__str__()"

    def op_string_split(
            self, state: VariableState, var_i: int, substr: str, count=None
    ) -> str:
        if count and count not in ("-1", -1):
            return f"{self.VAR_NAME}.split({substr}, {count})"
        return f"{self.VAR_NAME}.split({substr})"

    def op_string_format(
            self, state: VariableState, var_i: int, substr: str
    ) -> str:
        f_string = re.sub(r"\{\{.*}}", "{}", substr)
        return f"{f_string}.format({self.VAR_NAME})"

    def op_string_trim(
            self, state: VariableState, var_i: int, substr: str
    ) -> str:
        return f"{self.VAR_NAME}.strip({substr})"

    def op_string_ltrim(
            self, state: VariableState, var_i: int, substr: str
    ) -> str:
        return f"{self.VAR_NAME}.lstrip({substr})"

    def op_string_rtrim(self, state: VariableState, var_i: int, substr) -> str:
        return f"{self.VAR_NAME}.rstrip({substr})"

    def op_string_replace(
            self, state: VariableState, var_i: int, old: str, new: str, count=None
    ) -> str:
        if count and count not in ("-1", -1):
            return f"{self.VAR_NAME}.replace({old}, {new}, {count})"
        return f"{self.VAR_NAME}.replace({old}, {new})"

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
        return f"assert {self.VAR_NAME}{self.op_regex(state, var_i, pattern)}"

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
