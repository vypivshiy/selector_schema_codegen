"""code parts for python codegen"""

from typing import TYPE_CHECKING

from ssc_codegen.tokens import (
    StructType,
    TokenType,
    VariableType,
    JsonVariableType,
)

from .template_bindings import (
    TemplateBindings,
    TemplateTypeBindings,
)

if TYPE_CHECKING:
    from ssc_codegen.ast_ssc import BaseExpression, StartParseFunction

TYPES = {
    VariableType.ANY: "Any",
    VariableType.STRING: "str",
    VariableType.LIST_STRING: "List[str]",
    VariableType.OPTIONAL_STRING: "Optional[str]",
    VariableType.OPTIONAL_LIST_STRING: "Optional[List[str]]",
    VariableType.OPTIONAL_INT: "Optional[int]",
    VariableType.OPTIONAL_LIST_INT: "Optional[List[int]]",
    VariableType.OPTIONAL_FLOAT: "Optional[float]",
    VariableType.OPTIONAL_LIST_FLOAT: "Optional[List[float]]",
    VariableType.INT: "int",
    VariableType.FLOAT: "float",
    VariableType.LIST_INT: "List[int]",
    VariableType.LIST_FLOAT: "List[float]",
}

JSON_TYPES = {
    JsonVariableType.BOOLEAN: "bool",
    JsonVariableType.STRING: "str",
    JsonVariableType.NUMBER: "int",
    JsonVariableType.FLOAT: "float",
    JsonVariableType.NULL: "NoneType",
    JsonVariableType.OPTIONAL_STRING: "Optional[str]",
    JsonVariableType.OPTIONAL_NUMBER: "Optional[int]",
    JsonVariableType.OPTIONAL_FLOAT: "Optional[float]",
    JsonVariableType.OPTIONAL_BOOLEAN: "Optional[bool]",
}

MAGIC_METHODS_NAME = {
    "__KEY__": "key",
    "__VALUE__": "value",
    "__ITEM__": "item",
    "__PRE_VALIDATE__": "_pre_validate",
    "__SPLIT_DOC__": "_split_doc",
    "__START_PARSE__": "parse",
}


BINDINGS = TemplateBindings()
# build-ins
BINDINGS[TokenType.DOCSTRING] = '"""{}"""'  # value
BINDINGS[TokenType.IMPORTS] = (
    "from __future__ import annotations\n"
    + "import re\n"
    + "import json\n"  # TODO: add choice for another backends
    + "from typing import List, Dict, TypedDict, Union, Optional\n"
    + "from contextlib import suppress\n"
    + "import sys\n"
    + "if sys.version_info >= (3, 10):\n"
    + "    from types import NoneType\n"
    + "else:\n"
    + "    NoneType = type(None)\n"
)

BINDINGS[TokenType.EXPR_RETURN] = "return {}"  # nxt val
BINDINGS[TokenType.EXPR_NO_RETURN] = "return"
BINDINGS[TokenType.STRUCT] = "class {}:"
BINDINGS[TokenType.STRUCT_INIT] = "def __init__(self, document: {}) -> None:"
BINDINGS[TokenType.EXPR_NESTED] = "{} = {}({}).parse()"
BINDINGS[TokenType.STRUCT_PRE_VALIDATE] = "def {}(self, value: {}) -> None:"
BINDINGS[TokenType.STRUCT_PARSE_START] = "def {}(self) -> {}:"
BINDINGS[TokenType.STRUCT_FIELD] = "def _parse_{}(self, value: {}) -> {}:"
BINDINGS[TokenType.STRUCT_PART_DOCUMENT] = "def {}(self, value: {}) -> {}:"

BINDINGS[TokenType.EXPR_DEFAULT_START] = "with suppress(Exception):"
BINDINGS[TokenType.EXPR_DEFAULT_END] = "return {}"  # same as EXPR_RET

# string operations
BINDINGS[TokenType.EXPR_STRING_FORMAT] = (
    "{} = {}.format({}) if {} else {}"  # nxt = prv, template, prv, prv
)
BINDINGS[TokenType.EXPR_LIST_STRING_FORMAT] = (
    "{} = [{}.format(e) for e in {} if e]"
)
BINDINGS[TokenType.EXPR_STRING_TRIM] = "{} = {}.strip({})"
BINDINGS[TokenType.EXPR_LIST_STRING_TRIM] = "{} = [e.strip({}) for e in {}]"
BINDINGS[TokenType.EXPR_STRING_LTRIM] = "{} = {}.lstrip({})"
BINDINGS[TokenType.EXPR_LIST_STRING_LTRIM] = "{} = [e.lstrip({}) for e in {}]"
BINDINGS[TokenType.EXPR_STRING_RTRIM] = "{} = {}.rstrip({})"
BINDINGS[TokenType.EXPR_LIST_STRING_RTRIM] = "{} = [e.rstrip({}) for e in {}]"
BINDINGS[TokenType.EXPR_STRING_REPLACE] = "{} = {}.replace({}, {})"
BINDINGS[TokenType.EXPR_LIST_STRING_REPLACE] = (
    "{} = [e.replace({}, {}) for e in {}]"
)
BINDINGS[TokenType.EXPR_STRING_SPLIT] = "{} = {}.split({})"
# regex
BINDINGS[TokenType.EXPR_REGEX] = "{} = re.search({}, {})[{}]"
BINDINGS[TokenType.EXPR_REGEX_ALL] = "{} = re.findall({}, {})"
BINDINGS[TokenType.EXPR_REGEX_SUB] = "{} = re.sub({}, {}, {})"
BINDINGS[TokenType.EXPR_LIST_REGEX_SUB] = "{} = [re.sub({}, {}, e) for e in {}]"

# array
BINDINGS[TokenType.EXPR_LIST_STRING_INDEX] = "{} = {}[{}]"
BINDINGS[TokenType.EXPR_LIST_DOCUMENT_INDEX] = "{} = {}[{}]"
BINDINGS[TokenType.EXPR_LIST_JOIN] = "{} = {}.join({})"

# assert
BINDINGS[TokenType.IS_EQUAL] = "assert {} == {}, {}"
BINDINGS[TokenType.IS_NOT_EQUAL] = "assert {} != {}, {}"
BINDINGS[TokenType.IS_CONTAINS] = "assert {} in {}, {}"
BINDINGS[TokenType.IS_REGEX_MATCH] = "assert re.search({}, {}), {}"

# int, float converters
BINDINGS[TokenType.TO_INT] = "{} = int({})"
BINDINGS[TokenType.TO_INT_LIST] = "{} = [int(i) for i in {}]"
BINDINGS[TokenType.TO_FLOAT] = "{} = float({})"
BINDINGS[TokenType.TO_FLOAT_LIST] = "{} = [float(i) for i in {}]"


TYPE_BINDINGS = TemplateTypeBindings(type_prefix="T_")
TYPE_BINDINGS[StructType.LIST] = "{}"


TOKEN_TEMPLATES = {
    TokenType.DOCSTRING: '"""{}"""',
    TokenType.IMPORTS: (
        "from __future__ import annotations\n"
        + "import re\n"
        + "from typing import List, Dict, TypedDict, Union, Optional\n"
        + "from contextlib import suppress\n"
    ),
    TokenType.EXPR_RETURN: "return {}",
    TokenType.EXPR_NO_RETURN: "return",
}

INDENT_CH = " "
INDENT_METHOD = INDENT_CH * 4
INDENT_METHOD_BODY = INDENT_CH * (4 * 2)
INDENT_DEFAULT_BODY = INDENT_CH * (4 * 3)

TYPE_PREFIX = "T_{}"
TYPE_DICT = "Dict[str, {}]"
TYPE_LIST = "List[{}]"
TYPE_ITEM = "TypedDict({}, {})"
CLS_PART_DOC_HEAD = "def {}(self, value: {}) -> {}:"

E_CALL_METHOD = "self.{}({})"
E_CALL_PARSE = "self._parse_{}({})"


def suggest_indent(node: "BaseExpression") -> str:
    """helper function get current indent"""
    if node.have_default_expr():
        return INDENT_DEFAULT_BODY
    return INDENT_METHOD_BODY


def gen_item_body(node: "StartParseFunction") -> str:
    body = (
        "{"
        + ", ".join(
            [
                f'"{f.name}": ' + E_CALL_PARSE.format(f.name, "self._doc")
                for f in node.body
                if not MAGIC_METHODS_NAME.get(f.name)
            ]
        )
        + "}"
    )
    return body


def gen_list_body(node: "StartParseFunction") -> str:
    body = ", ".join(
        [
            f'"{f.name}": ' + E_CALL_PARSE.format(f.name, "e")
            for f in node.body
            if not MAGIC_METHODS_NAME.get(f.name)
        ]
    )
    body = "{" + body + "}"
    n = MAGIC_METHODS_NAME.get("__SPLIT_DOC__")
    return f"[{body} for e in self.{n}(self._doc)]\n"


def gen_dict_body(_: "StartParseFunction") -> str:
    key_m = E_CALL_PARSE.format(MAGIC_METHODS_NAME.get("__KEY__"), "e")
    value_m = E_CALL_PARSE.format(MAGIC_METHODS_NAME.get("__VALUE__"), "e")
    part_m = E_CALL_METHOD.format(
        MAGIC_METHODS_NAME.get("__SPLIT_DOC__"), "self._doc"
    )

    body = f"{{ {key_m}: {value_m} for e in {part_m} }}"
    return body


def get_flat_list_body(_: "StartParseFunction") -> str:
    item_m = E_CALL_PARSE.format(MAGIC_METHODS_NAME.get("__ITEM__"), "e")
    part_m = E_CALL_METHOD.format(
        MAGIC_METHODS_NAME.get("__SPLIT_DOC__"), "self._doc"
    )
    body = f"[{item_m} for e in {part_m}]"
    return body
