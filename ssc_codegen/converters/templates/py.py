"""code parts for python codegen"""
from typing import TYPE_CHECKING

from ssc_codegen.tokens import VariableType

if TYPE_CHECKING:
    from ssc_codegen.ast_ssc import StartParseFunction

TYPES = {
    VariableType.STRING: "str",
    VariableType.LIST_STRING: "List[str]",
    VariableType.OPTIONAL_STRING: "Optional[str]",
    VariableType.OPTIONAL_LIST_STRING: "Optional[List[str]]",
    VariableType.INT: "int",
    VariableType.FLOAT: "float",
    VariableType.LIST_INT: "List[int]",
    VariableType.LIST_FLOAT: "List[float]",
}

MAGIC_METHODS = {
    "__KEY__": "key",
    "__VALUE__": "value",
    "__ITEM__": "item",
    "__PRE_VALIDATE__": "_pre_validate",
    "__SPLIT_DOC__": "_split_doc",
    "__START_PARSE__": "parse",
}

BASE_IMPORTS = """from __future__ import annotations
import re
from typing import List, Dict, TypedDict, Union, Optional
from contextlib import suppress
"""
INDENT_CH = " "
INDENT_METHOD = INDENT_CH * 4
INDENT_METHOD_BODY = INDENT_CH * (4 * 2)
INDENT_DEFAULT_BODY = INDENT_CH * (4 * 3)

TYPE_PREFIX = "T_{}"
TYPE_DICT = "Dict[str, {}]"
TYPE_LIST = "List[{}]"
TYPE_ITEM = "TypedDict({}, {})"
CLS_HEAD = "class {}:"
CLS_INIT_HEAD = "def __init__(self, document: {}):"
CLS_PRE_VALIDATE_HEAD = "def {}(self, value) -> None:"
CLS_PART_DOC_HEAD = "def {}(self, value: {}) -> {}:"
CLS_DOCSTRING = '"""{}"""'

RET = "return {}"
NO_RET = "return"
# f"def _parse_{name}(self, value: Union[BeautifulSoup, Tag]) -> {type_}:"
FN_PARSE = "def _parse_{}(self, value: {}) -> {}:"
FN_PARSE_START = "def {}(self) -> {}:"

E_PARSE_NESTED = "{} = {}({}).parse()"
E_CALL_METHOD = "self.{}({})"
E_CALL_PARSE = "self._parse_{}({})"
E_DEFAULT_WRAP = "with suppress(Exception):"
E_STR_FMT = "{} = {}.format({}) if {} else {}"
# nxt + ' = ' + f"[{template!r}.format(e) for e in {prv} if e]"
E_STR_FMT_ALL = "{} = [{}.format(e) for e in {} if e]"
E_STR_TRIM = "{} = {}.strip({})"
E_STR_LTRIM = "{} = {}.lstrip({})"
E_STR_RTRIM = "{} = {}.rstrip({})"
# f"{nxt} = [e.strip({chars!r}) for e in {prv}]"
E_STR_TRIM_ALL = "{} = [e.strip({}) for e in {}]"
E_STR_LTRIM_ALL = "{} = [e.lstrip({}) for e in {}]"
E_STR_RTRIM_ALL = "{} = [e.rstrip({}) for e in {}]"
# f"{nxt} = {prv}.replace({old!r}, {new!r})"
E_STR_REPL = "{} = {}.replace({}, {})"
# f"{nxt} = [e.replace({old!r}, {new!r}) for e in {prv}]"
E_STR_REPL_ALL = "{} = [e.replace({}, {}) for e in {}]"
E_STR_SPLIT = "{} = {}.split({})"
E_RE = "{} = re.search({}, {})[{}]"
E_RE_ALL = "{} = re.findall({}, {})"
E_RE_SUB = "{} = re.sub({}, {}, {})"
E_RE_SUB_ALL = "{} = [re.sub({}, {}, e) for e in {}]"
E_INDEX = "{} = {}[{}]"
E_JOIN = "{} = {}.join({})"
E_EQ = "assert {} == {}, {}"
E_NE = "assert {} != {}, {}"
E_IN = "assert {} in {}, {}"
E_IS_RE = "assert re.search({}, {}), {}"


def gen_item_body(node: "StartParseFunction") -> str:
    body = (
        "{"
        + ", ".join(
            [
                f'"{f.name}": ' + E_CALL_PARSE.format(f.name, "self._doc")
                for f in node.body
                if not MAGIC_METHODS.get(f.name)
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
            if not MAGIC_METHODS.get(f.name)
        ]
    )
    body = "{" + body + "}"
    n = MAGIC_METHODS.get("__SPLIT_DOC__")
    return f"[{body} for e in self.{n}(self._doc)]\n"


def gen_dict_body(_: "StartParseFunction") -> str:
    key_m = E_CALL_PARSE.format(MAGIC_METHODS.get("__KEY__"), "e")
    value_m = E_CALL_PARSE.format(MAGIC_METHODS.get("__VALUE__"), "e")
    part_m = E_CALL_METHOD.format(
        MAGIC_METHODS.get("__SPLIT_DOC__"), "self._doc"
    )

    body = f"{{ {key_m}: {value_m} for e in {part_m} }}"
    return body


def get_flat_list_body(_: "StartParseFunction") -> str:
    item_m = E_CALL_PARSE.format(MAGIC_METHODS.get("__ITEM__"), "e")
    part_m = E_CALL_METHOD.format(
        MAGIC_METHODS.get("__SPLIT_DOC__"), "self._doc"
    )
    body = f"[{item_m} for e in {part_m}]"
    return body
