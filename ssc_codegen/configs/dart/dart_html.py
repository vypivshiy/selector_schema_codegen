"""https://pub.dev/packages/universal_html"""
# TODO ISSUES
# REGEX
# RAW STRINGS
import re
from typing import TYPE_CHECKING

from ssc_codegen.configs.codegen_tools import ABCExpressionTranslator
from ssc_codegen.objects import VariableState

if TYPE_CHECKING:
    from ssc_codegen.objects import Node


class Translator(ABCExpressionTranslator):
    METHOD_ARG_NAME = "part"
    VAR_NAME = "val"
    ASSIGMENT = "="
    DELIM_LINES = ";\n"
    DELIM_DEFAULT_WRAPPER = ";\n  "
    # don't needed import
    REGEX_IMPORT = ""
    SELECTOR_IMPORT = "import 'package:universal_html/html.dart' show Document;\nimport 'package:universal_html/parsing.dart' as html;"
    #######
    # types
    #######
    SELECTOR_TYPE = "Document"
    STRING_TYPE = "String"
    ELEMENT_TYPE = "var"  # TODO typing element
    LIST_OF_STRING_TYPE = "List<String>"
    LIST_OF_ELEMENTS_TYPE = "var"  # TODO typing list of elements
    AUTO_CONVERT_TO_CSS = True

    def _assign_nodes_expr(self, node: "Node") -> str:
        """var_node.id = var_node_prev.id"""
        return (
            f"{self._gen_var_name(node)} = {self._gen_var_name(node.prev_node)}"
        )

    def op_no_ret(self, node: "Node") -> str:
        return ""

    def op_ret(self, node: "Node") -> str:
        return f"return {self._VAR_P(node)};"

    def op_wrap_code_with_default_value(
        self, node: "Node", code: str, default_value: str
    ) -> str:
        return (
            f"try {{\n  {code} }} catch (e) {{\n  return {default_value};\n}}"
        )

    def op_wrap_code(self, node: "Node", code: str) -> str:
        return f"{code}{self.DELIM_LINES}"

    def op_css(self, node: "Node", query: str) -> str:
        return f"var {self._VAR(node)} = {self._VAR_P(node)}.querySelector({query})"

    def op_xpath(self, node: "Node", query: str) -> str:
        raise NotImplementedError

    def op_css_all(self, node: "Node", query: str) -> str:
        return f"var {self._VAR(node)} = {self._VAR_P(node)}.querySelectorAll({query})"

    def op_xpath_all(self, node: "Node", query: str) -> str:
        raise NotImplementedError

    def op_attr(self, node: "Node", attr_name: str) -> str:
        if node.var_state == VariableState.ARRAY:
            return f"List<String> {self._VAR(node)} = {self._VAR_P(node)}.map((el) => el.attributes[{attr_name}]).toList()"
        return f"String {self._VAR(node)} = {self._VAR_P(node)}.attributes[{attr_name}]"

    def op_text(self, node: "Node") -> str:
        if node.var_state == VariableState.ARRAY:
            return f"List<String> {self._VAR(node)} = {self._VAR_P(node)}.map((el) => el.text).toList()"
        return f'String {self._VAR(node)} = {self._VAR_P(node)}?.text ?? ""'

    def op_raw(self, node: "Node") -> str:
        if node.var_state == VariableState.ARRAY:
            return f"List<String> {self._VAR(node)} = {self._VAR_P(node)}.map((el) => el.innerHtml).toList()"
        return f"String {self._VAR(node)} = {self._VAR_P(node)}.innerHtml"

    def op_string_split(self, node: "Node", substr: str, count=None) -> str:
        if count is None or count in (-1, "-1"):
            return f"List<String> {self._VAR(node)} = {self._VAR_P(node)}.split({substr})"
        return (
            f"List<String> {self._VAR(node)} = {self._VAR_P(node)}.split({substr});\n"
            f"{self._VAR(node)} = {self._VAR(node)}.sublist(0, {count})"
        )

    def op_string_format(self, node: "Node", substr: str) -> str:
        substr = re.sub(r"\{\{.*}}", f"${self._VAR_P(node)}", substr, 1)
        return f"String {self._VAR(node)} = {substr}"

    def op_string_trim(self, node: "Node", substr: str) -> str:
        # https://stackoverflow.com/a/14107914
        substr = substr.strip('"')
        substr_left = "r" + repr(f"^{substr}")
        substr_right = "r" + repr(f"{substr}$")
        return (
            f'String {self._VAR(node)} = {self._VAR_P(node)}.replaceFirst(RegExp({substr_left}), "");\n'
            f'{self._VAR(node)} = {self._VAR(node)}.replaceFirst(RegExp({substr_right}), "")'
        )

    def op_string_ltrim(self, node: "Node", substr: str) -> str:
        # https://stackoverflow.com/a/14107914
        substr = substr.strip('"')
        substr_left = "r" + repr(f"^{substr}")
        return f'String {self._VAR(node)} = {self._VAR_P(node)}.replaceFirst(RegExp({substr_left}), "")'

    def op_string_rtrim(self, node: "Node", substr) -> str:
        # https://stackoverflow.com/a/14107914
        substr = substr.strip('"')
        substr_right = "r" + repr(f"{substr}$")
        return f'String {self._VAR(node)} = {self._VAR(node)}.replaceFirst(RegExp({substr_right}), "")'

    def op_string_replace(
        self, node: "Node", old: str, new: str, count=None
    ) -> str:
        # TODO add chars escape
        if count is None:
            return f"String {self._VAR(node)} = {self._VAR_P(node)}.replaceAll(RegExp({old}), {new})"
        return f"String {self._VAR(node)} = {self._VAR_P(node)}.replaceRange({count}, {old}, {new})"

    def op_string_join(self, node: "Node", string: str) -> str:
        return f"String {self._VAR(node)} = {self._VAR_P(node)}.join({string})"

    def op_regex(self, node: "Node", pattern: str) -> str:
        reg_var = f"regex_{node.id}"
        return (
            f"RegExp {reg_var} = RegExp(r{pattern});\n"
            # TODO add ? symbol ???
            f"String {self._VAR(node)} = {reg_var}.firstMatch({self._VAR_P(node)}).group(0)"
        )

    def op_regex_all(self, node: "Node", pattern: str) -> str:
        reg_var = f"regex_{node.id}"
        return (
            f"RegExp {reg_var} = RegExp(r{pattern});\n"
            f"List<String> {self._VAR(node)} = {reg_var}.allMatches({self._VAR_P(node)}).map((m) => m.group(0)!).toList())"
        )

    def op_regex_sub(
        self, node: "Node", pattern: str, repl: str, count=None
    ) -> str:
        if count is None or count in (-1, "-1"):
            return ""
        reg_var = f"regex_{node.id}"
        return (
            f"RegExp {reg_var} = RegExp(r{pattern});\n"
            f"String {self._VAR(node)} = {self._VAR_P(node)}.replaceAllMapped({reg_var}, (m) => {count}-- > 0) : match.group(0)!"
        )

    def op_limit(self, node: "Node", max_: str) -> str:
        return f"var {self._VAR(node)} = {self._VAR_P(node)}.sublist(0, {max_})"

    def op_index(self, node: "Node", index: str) -> str:
        return f"var {self._VAR(node)} = {self._VAR_P(node)}[{index}]"

    def op_first_index(self, node: "Node"):
        return f"var {self._VAR(node)} = {self._VAR_P(node)}.first"

    def op_last_index(self, node: "Node"):
        return f"var {self._VAR(node)} = {self._VAR_P(node)}.last"

    def op_assert_equal(self, node: "Node", substring: str):
        return f"assert({self._VAR(node)} == {substring})"

    def op_assert_css(self, node: "Node", query: str):
        return f"assert({self._VAR(node)}.querySelector({query}) != null)"

    def op_assert_xpath(self, node: "Node", query: str) -> str:
        raise NotImplementedError

    def op_assert_re_match(self, node: "Node", pattern: str) -> str:
        re_var = f"re_{node.num}"
        return (
            f"RegExp {re_var} = RegExp(r{pattern});\n"
            f"assert({re_var}.firstMatch({self._VAR(node)}) != null)"
        )

    def op_assert_starts_with(self, node: "Node", prefix: str) -> str:
        return f"assert({self._VAR(node)}.startsWith({prefix}))"

    def op_assert_ends_with(self, node: "Node", suffix: str) -> str:
        return f"assert({self._VAR(node)}.endsWith({suffix}))"

    def op_assert_contains(self, node: "Node", substring: str) -> str:
        return f"assert({self._VAR(node)}.contains({substring}))"

    def op_skip_pre_validate(self) -> str:
        return "null;"

    def op_skip_part_document(self) -> str:
        return f"return [{self.METHOD_ARG_NAME}];"
