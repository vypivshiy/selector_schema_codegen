from typing import Optional
import re

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
    SELECTOR_IMPORT = "from parsel import Selector"
    # selector type
    SELECTOR_TYPE = "Selector"

    @classmethod
    def op_wrap_code_with_default_value(cls, state: Optional[VariableState],
                                        var_i: int, code: str, default_value: str) -> str:
        d = cls.DELIM_DEFAULT_WRAPPER
        code = d.join([line for line in code.split(cls.DELIM_LINES)])
        return f"try:{d}{code}\nexcept Exception:{d}return {default_value}"

    @classmethod
    def op_wrap_code(cls, state: Optional[VariableState], var_i: int, code: str) -> str:
        d = cls.DELIM_LINES
        return f'{code}{d}return {cls.VAR_NAME}'

    @classmethod
    def op_css(cls, state: VariableState, var_i: int, query: str) -> str:
        return f"{cls.VAR_NAME}.css({query!r})"

    @classmethod
    def op_xpath(cls, state: VariableState, var_i: int,  query: str) -> str:
        return f"{cls.VAR_NAME}.xpath({query!r})"

    @classmethod
    def op_css_all(cls, state: VariableState, var_i: int,  query: str) -> str:
        return f"{cls.VAR_NAME}.css({query!r})"

    @classmethod
    def op_xpath_all(cls, state: VariableState, var_i: int,  query: str) -> str:
        return f"{cls.VAR_NAME}.xpath({query!r})"

    @classmethod
    def op_attr(cls, state: VariableState, var_i: int,  attr_name: str) -> str:
        return f"{cls.VAR_NAME}.attrib[{attr_name!r}]"

    @classmethod
    def op_text(cls, state: VariableState, var_i: int) -> str:
        if state is VariableState.ARRAY:
            return f'{cls.VAR_NAME}.xpath("//text()").getall()'
        return f'{cls.VAR_NAME}.xpath("//text()").get()'

    @classmethod
    def op_raw(cls, state: VariableState, var_i: int) -> str:
        return f'{cls.VAR_NAME}.get()'

    @classmethod
    def op_string_split(cls, state: VariableState, var_i: int,  substr: str, count=None) -> str:
        if count and count not in ("-1", -1):
            return f"{cls.VAR_NAME}.split({substr!r}, {count})"
        return f"{cls.VAR_NAME}.split({substr!r})"

    @classmethod
    def op_string_format(cls, state: VariableState, var_i: int,  substr: str) -> str:
        f_string = re.sub(r'\{\{.*}}', '{}', substr)
        return f"{f_string}.format({cls.VAR_NAME})"

    @classmethod
    def op_string_trim(cls, state: VariableState, var_i: int,  substr: str) -> str:
        return f"{cls.VAR_NAME}.strip({substr!r})"

    @classmethod
    def op_string_ltrim(cls, state: VariableState, var_i: int,  substr: str) -> str:
        return f"{cls.VAR_NAME}.lstrip({substr!r})"

    @classmethod
    def op_string_rtrim(cls, state: VariableState, var_i: int,  substr) -> str:
        return f"{cls.VAR_NAME}.rstrip({substr!r})"

    @classmethod
    def op_string_replace(cls, state: VariableState, var_i: int,  old: str, new: str, count=None) -> str:
        if count and count not in ("-1", -1):
            return f"{cls.VAR_NAME}.replace({old!r}, {new!r}, {count})"
        return f"{cls.VAR_NAME}.replace({old!r}, {new!r})"

    @classmethod
    def op_string_join(cls, state: VariableState, var_i: int,  string: str) -> str:
        return f"{string!r}.join({cls.VAR_NAME})"

    @classmethod
    def op_regex(cls, state: VariableState, var_i: int,  pattern: str) -> str:
        return f"re.search({pattern!r}, {cls.VAR_NAME})[1]"

    @classmethod
    def op_regex_all(cls, state: VariableState, var_i: int,  pattern: str) -> str:
        return f"re.findall({pattern!r}, {cls.VAR_NAME})"

    @classmethod
    def op_regex_sub(cls, state: VariableState, var_i: int,  pattern: str, repl: str, count=None) -> str:
        if count:
            return f"re.sub({pattern!r}, {repl!r}, {cls.VAR_NAME}, {count})"
        return f"re.sub({pattern!r}, {repl!r}, {cls.VAR_NAME})"

    @classmethod
    def op_slice(cls, state: VariableState, var_i: int,  start: str, end: str) -> str:
        return f"{cls.VAR_NAME}[{start}, {end}]"

    @classmethod
    def op_index(cls, state: VariableState, var_i: int,  index: str) -> str:
        return f"{cls.VAR_NAME}[{index}]"

    @classmethod
    def op_first_index(cls, state: VariableState, var_i: int):
        return f"{cls.VAR_NAME}[0]"

    @classmethod
    def op_last_index(cls, state: VariableState, var_i: int):
        return f"{cls.VAR_NAME}[-1]"

    @classmethod
    def op_assert_equal(cls, state: VariableState, var_i: int,  substring: str):
        return f"assert {cls.VAR_NAME} == {substring!r}"

    @classmethod
    def op_assert_css(cls, state: VariableState, var_i: int,  query: str):
        return f"assert {cls.op_css(state, var_i, query)}"

    @classmethod
    def op_assert_xpath(cls, state: VariableState, var_i: int,  query: str) -> str:
        return f"assert {cls.op_xpath(state, var_i, query)}"

    @classmethod
    def op_assert_re_match(cls, state: VariableState, var_i: int,  pattern: str) -> str:
        return f"assert {cls.op_regex(state, var_i, pattern)}"

    @classmethod
    def op_assert_starts_with(cls, state: VariableState, var_i: int,  prefix: str) -> str:
        return f"assert {cls.VAR_NAME}.startswith({prefix!r})"

    @classmethod
    def op_assert_ends_with(cls, state: VariableState, var_i: int,  suffix: str) -> str:
        return f"assert {cls.VAR_NAME}.endswith({suffix!r})"

    @classmethod
    def op_assert_contains(cls, state: VariableState, var_i: int,  substring: str) -> str:
        return f"assert {substring!r} in {cls.VAR_NAME}"


if __name__ == '__main__':
    from src.lexer import tokenize

    source = """
assertCss "head > title"

css 'head > title'
//attr "href"
text
assertContains "spam"
//slice 0 2
format 'https://books.toscrape.com/catalogue/{{VAR}}'
rstrip "https://"
replace "o" "a"
re "b[oa][oa]ks."
reSub '\w+' 'stub' 1
"""
    raw_tokens = tokenize(source)
    block = generate_code(raw_tokens, Translator())
    print(block.regex_import)
    print(block.selector_import)

    print(block.code)
