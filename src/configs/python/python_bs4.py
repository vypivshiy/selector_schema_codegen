"""python bs4 translator"""
import re
from typing import TYPE_CHECKING

from src.analyzer import VariableState
from src.configs.codegen_tools import ABCExpressionTranslator

if TYPE_CHECKING:
    from src.objects import Node


class Translator(ABCExpressionTranslator):
    METHOD_ARG_NAME = "part"
    # var prefix
    VAR_NAME = "val"
    # assignments
    FIRST_ASSIGMENT = "="
    ASSIGMENT = "="
    # delimeters
    DELIM_LINES = "\n"
    # try: <expr> except:
    DELIM_DEFAULT_WRAPPER = "\n    "
    # imports
    REGEX_IMPORT = "import re"
    SELECTOR_IMPORT = "from bs4 import BeautifulSoup, Tag"
    #######
    # types
    #######
    # SELECTOR
    SELECTOR_TYPE: str = "BeautifulSoup"
    ELEMENT_TYPE: str = "Tag"
    # SELECTOR_ARRAY
    LIST_OF_ELEMENTS_TYPE: str = "list[Tag]"
    # ARRAY
    LIST_OF_STRING_TYPE: str = "list[str]"
    # TEXT
    STRING_TYPE: str = "str"

    def _gen_var_name(self, node: "Node") -> str:
        """assert <name> <expr"""
        if node is None:
            return self.METHOD_ARG_NAME
        _id = node.id
        if _id is None:
            return self.METHOD_ARG_NAME
        return f"{self.VAR_NAME}_{_id}"

    def _assign_nodes_expr(self, node: "Node") -> str:
        """var_node.id = var_node_prev.id"""
        return f'{self._gen_var_name(node)} = {self._gen_var_name(node.prev_node)}'

    def op_no_ret(self, node: "Node"):
        return ""

    def op_ret(self, node: "Node"):
        return f"return {self._gen_var_name(node.prev_node)}"

    def op_wrap_code_with_default_value(
            self,
            node: "Node",
            code: str,
            default_value: str,
    ) -> str:
        d = self.DELIM_DEFAULT_WRAPPER
        code = d.join([line for line in code.split(self.DELIM_LINES)])
        return f"try:{d}{code}{d}\nexcept Exception:{d}return {default_value}"

    def op_wrap_code(
            self, node: "Node", code: str
    ) -> str:
        d = self.DELIM_LINES
        return f"{code}{d}"

    def op_css(self, node: "Node", query: str) -> str:
        return f"{self._assign_nodes_expr(node)}.select_one({query})"

    def op_xpath(self, node: "Node", query: str) -> str:
        raise NotImplementedError

    def op_css_all(self, node: "Node", query: str) -> str:
        return f"{self._assign_nodes_expr(node)}.select({query})"

    def op_xpath_all(self, node: "Node", query: str) -> str:
        raise NotImplementedError

    def op_attr(self, node: "Node", attr_name: str) -> str:
        return f"{self._assign_nodes_expr(node)}[{attr_name}]"

    def op_text(self, node: "Node") -> str:
        if node.var_state == VariableState.ARRAY:
            return f"{self._gen_var_name(node)} = [el.text() for el in {self._gen_var_name(node)}]"
        return f'{self._assign_nodes_expr(node)}.text()'

    def op_raw(self, node: "Node") -> str:
        if node.var_state == VariableState.ARRAY:
            return f"{self._gen_var_name(node)} = [el.__str__() for el in {self._gen_var_name(node)}]"
        return f"{self._assign_nodes_expr(node)}.__str__()"

    def op_string_split(
            self, node: "Node", substr: str, count=None
    ) -> str:
        if count and count not in ("-1", -1):
            return f"{self._assign_nodes_expr(node)}.split({substr}, {count})"
        return f"{self._assign_nodes_expr(node)}.split({substr})"

    def op_string_format(
            self, node: "Node", substr: str
    ) -> str:
        f_string = re.sub(r"\{\{.*}}", "{}", substr)
        return f"{self.VAR_NAME}_{node.id} = {f_string}.format({self.VAR_NAME}_{node.prev_node.id})"

    def op_string_trim(
            self, node: "Node", substr: str
    ) -> str:
        return f"{self._assign_nodes_expr(node)}.strip({substr})"

    def op_string_ltrim(
            self, node: "Node", substr: str
    ) -> str:
        return f"{self._assign_nodes_expr(node)}.lstrip({substr})"

    def op_string_rtrim(self, node: "Node", substr) -> str:
        return f"{self._assign_nodes_expr(node)}.rstrip({substr})"

    def op_string_replace(
            self, node: "Node", old: str, new: str, count=None
    ) -> str:
        if count and count not in ("-1", -1):
            return f"{self._assign_nodes_expr(node)}.replace({old}, {new}, {count})"
        return f"{self._assign_nodes_expr(node)}.replace({old}, {new})"

    def op_string_join(
            self, node: "Node", string: str
    ) -> str:
        return f"{self._gen_var_name(node)} = {string}.join({self._gen_var_name(node.prev_node)})"

    def op_regex(self, node: "Node", pattern: str) -> str:
        return f"{self._gen_var_name(node)} = re.search(r{pattern}, {self._gen_var_name(node.prev_node)})[1]"

    def op_regex_all(
            self, node: "Node", pattern: str
    ) -> str:
        return f"{self._gen_var_name(node)} = re.findall(r{pattern}, {self._gen_var_name(node.prev_node)})"

    def op_regex_sub(
            self,
            node: "Node",
            pattern: str,
            repl: str,
            count=None,
    ) -> str:
        if count:
            return f"{self._gen_var_name(node)} = re.sub(r{pattern}, {repl}, {self._gen_var_name(node.prev_node)}, {count})"
        return f"{self._gen_var_name(node)} = re.sub(r{pattern}, {repl}, {self._gen_var_name(node.prev_node)})"

    def op_slice(
            self, node: "Node", start: str, end: str
    ) -> str:
        return f"{self._assign_nodes_expr(node)}[{start}, {end}]"

    def op_index(self, node: "Node", index: str) -> str:
        return f"{self._assign_nodes_expr(node)}[{index}]"

    def op_first_index(self, node: "Node"):
        return f"{self._assign_nodes_expr(node)}[0]"

    def op_last_index(self, node: "Node"):
        return f"{self._assign_nodes_expr(node)}[-1]"

    def op_assert_equal(self, node: "Node", substring: str):
        return f"assert {self._gen_var_name(node)} == {substring}"

    def op_assert_css(self, node: "Node", query: str):
        return f"assert {self._gen_var_name(node)}.select_one({query})"

    def op_assert_xpath(
            self, node: "Node", query: str
    ) -> str:
        raise NotImplementedError

    def op_assert_re_match(
            self, node: "Node", pattern: str
    ) -> str:
        return f"assert re.search(r{pattern}, {self._gen_var_name(node)})"

    def op_assert_starts_with(
            self, node: "Node", prefix: str
    ) -> str:
        return f"assert {self._gen_var_name(node)}.startswith({prefix})"

    def op_assert_ends_with(
            self, node: "Node", suffix: str
    ) -> str:
        return f"assert {self._gen_var_name(node)}.endswith({suffix})"

    def op_assert_contains(
            self, node: "Node", substring: str
    ) -> str:
        return f"assert {substring} in {self._gen_var_name(node)}"


if __name__ == "__main__":
    from src.lexer import tokenize
    from src.configs.codegen_tools import generate_code
    source = """
assertCss "head > title"

css "head > title"
text
assertContains "spam"
format "https://books.toscrape.com/catalogue/{{}}"
rstrip "https://"
replace "o" "a" -1
re "b[oa][oa]ks\."
reSub "\w+" "lol" 1
"""
    raw_tokens = tokenize(source)
    block = generate_code(raw_tokens, Translator())
    print(*block, sep="\n")