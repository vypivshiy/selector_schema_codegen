from typing import TYPE_CHECKING

from ssc_codegen.converters.utils import to_upper_camel_case

if TYPE_CHECKING:
    from ssc_codegen.ast_ssc import StartParseFunction

MAGIC_METHODS = {
    "__KEY__": "key",
    "__VALUE__": "value",
    "__ITEM__": "item",
    "__PRE_VALIDATE__": "_preValidate",
    "__SPLIT_DOC__": "_splitDoc",
    "__START_PARSE__": "parse",
}

BRACKET_START = "{"
BRACKET_END = "}"


CLS_HEAD = "class {}"
CLS_CONSTRUCTOR = (
    "constructor(doc)"
    + BRACKET_START
    + "this._doc = typeof document === 'string' ? new DOMParser().parseFromString(doc, 'text/html') : document;"
    + BRACKET_END
)


def DOCSTRING(value: str) -> str:  # noqa
    docstr_start = "/**"
    docstr_parts = "\n".join("* " + line for line in value.split("\n"))
    docstr_end = "*/"
    return docstr_start + "\n" + docstr_parts + "\n" + docstr_end


RET = "return {};"
NO_RET = "return null;"
EXPR_NESTED = "let {} = (new {}({})).parse();"
"""NEXT VAR, CLS_NAME, PREV_VAR"""

FUNC_HEAD = "{}(value)"
FUNC_PARSE_HEAD = "_parse{}(value)"
FUNC_PARSE_START_HEAD = "{}()"
PRE_VALIDATE_CALL = "this.{}(this._doc);"
DEFAULT_HEAD = "try " + BRACKET_START


def DEFAULT_FOOTER(val: str) -> str:  # noqa
    return "} catch(Error) {" + f"return {val};" + "}"


EXPR_STR_FMT = "let {} = {};"
"""VAR_NXT, TEMPLATE"""

EXPR_STR_FMT_ALL = "let {} = {}.map(e => {});"
"""VAR_NXT, PRV, TEMPLATE"""


# (function (str, chars) {
#     return str.replace(new RegExp(`^[${chars}]+|[${chars}]+$`, 'g'), '');
# });
def EXPR_STR_TRIM(nxt: str, prv: str, chars: str) -> str:
    return (
        f"let {nxt}"
        + " = "
        + "(function (str, chars){return str.replace(new RegExp(`^[${chars}]+|[${chars}]+$`, 'g'), '');})"
        + f"({prv}, {chars!r});"
    )


def EXPR_STR_TRIM_ALL(nxt: str, prv: str, chars: str) -> str:
    return (
        f"let {nxt}"
        + " = "
        + f"{prv}.map(e =>"
        + "(function (str, chars){return str.replace(new RegExp(`^[${chars}]+|[${chars}]+$`, 'g'), '');})"
        + f"(e, {chars!r})"
        + ");"
    )


# const ltrim = function (str, chars) {
#     return str.replace(new RegExp(`^[${chars}]+`, 'g'), '');
# };
def EXPR_STR_LTRIM(nxt: str, prv: str, chars: str) -> str:
    return (
        f"let {nxt}"
        + " = "
        + "(function (str, chars){return str.replace(new RegExp(`^[${chars}]+`, 'g'), '');})"
        + f"({prv}, {chars!r});"
    )


def EXPR_STR_LTRIM_ALL(nxt: str, prv: str, chars: str) -> str:
    return (
        f"let {nxt}"
        + " = "
        + f"{prv}.map(e =>"
        + "(function (str, chars){return str.replace(new RegExp(`^[${chars}]+`, 'g'), '');})"
        + f"(e, {chars!r})"
        + ");"
    )


# const rtrim = function (str, chars) {
#     return str.replace(new RegExp(`[${chars}]+$`, 'g'), '');
# };
#
def EXPR_STR_RTRIM(nxt: str, prv: str, chars: str) -> str:
    return (
        f"let {nxt}"
        + " = "
        + "(function (str, chars) {return str.replace(new RegExp(`^[${chars}]+`, 'g'), '');})"
        + f"({prv}, {chars!r}); "
    )


def EXPR_STR_RTRIM_ALL(nxt: str, prv: str, chars: str) -> str:
    return (
        f"let {nxt}"
        + " = "
        + f"{prv}.map(e =>"
        + "(function (str, chars){return str.replace(new RegExp(`[${chars}]+$`, 'g'), '');})"
        + f"(e, {chars!r})"
        + ");"
    )


EXPR_STR_REPL = "let {} = {}.replace({}, {});"
"""NXT, PRV, OLD, NEW"""
EXPR_STR_REPL_ALL = "let {} = {}.map(e => e.replace({}, {}));"
"""NXT, PRV, OLD, NEW"""
EXPR_STR_SPLIT = "let {} = {}.split({});"
EXPR_RE = "let {} = {}.match({})[{}];"
"""NXT PRV PATTERN GROUP"""
EXPR_RE_ALL = "let {} = {}.match({});"
EXPR_RE_SUB = "let {} = {}.replace({}, {});"
EXPR_RE_SUB_ALL = "let {} = {}.map(e => e.replace({}, {}));"
EXPR_INDEX = "let {} = {}[{}];"
EXPR_JOIN = "let {} = {}.join({});"
EXPR_ASSIGN = "let {} = {};"
E_EQ = "if ({} != {}) throw new Error({});"
E_NE = "if ({} == {}) throw new Error({});"
E_IN = "if (!({} in {})) throw new Error({});"
E_IS_RE = "if ({}.match({}) === null) throw new Error({});"

# PURE JS API
EXPR_CSS = "let {} = {}.querySelector({});"
EXPR_CSS_ALL = "let {} = {}.querySelectorAll({});"
# document.evaluate(xpath, element, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
EXPR_XPATH = "let {} = document.evaluate({}, {}, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;"


def EXPR_XPATH_ALL(nxt: str, prv: str, query: str) -> str:  # noqa
    xpath_eval = f"document.evaluate({query!r}, {prv}, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null)"
    return (
        f"let {nxt} = "
        + "Array.from({ length: result.snapshotLength }, (_, i) => "
        + xpath_eval
        + ".snapshotItem(i)"
        + ");"
    )


EXPR_DOC_TEXT = 'let {} = {}.querySelector("html").textContent;'
EXPR_TEXT = "let {} = {}.textContent;"
EXPR_TEXT_ALL = "let {} = {}.map(e => e.textContent);"
EXPR_DOC_RAW = 'let {} = {}.querySelector("html").innerHTML;'
EXPR_RAW = "let {} = {}.innerHTML;"
EXPR_RAW_ALL = "let {} = {}.map(e => e.innerHTML);"
EXPR_ATTR = "let {} = {}.getAttribute({});"
EXPR_ATTR_ALL = "let {} = {}.map(e => e.getAttribute({}));"
E_IS_CSS = "if (!{}.querySelector({})) throw new Error({});"
E_IS_XPATH = (
    "if("
    + "!document.evaluate({}, {}, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue"
    + ") throw new Error({});"
)


def gen_item_body(node: "StartParseFunction") -> str:
    # kv property
    # return { k1: this._parseK1(), k2: this._parseK2(), ...}
    return (
        "let item = "
        + BRACKET_START
        + ",".join(
            f"{f.name}: this._parse{to_upper_camel_case(f.name)}(this._doc)"
            for f in node.body
            if f.name not in MAGIC_METHODS
        )
        + BRACKET_END
        + ";"
        + RET.format("item")
    )


def gen_list_body(node: "StartParseFunction") -> str:
    # part_m = MAGIC_METHODS.get('__SPLIT_DOC__')
    kv_prop = (
        BRACKET_START
        + ",".join(
            f"{f.name}: this._parse{to_upper_camel_case(f.name)}(e)"
            for f in node.body
            if f.name not in MAGIC_METHODS
        )
        + BRACKET_END
    )
    return (
        "let items = [];"
        + "Array.from(this._splitDoc(this._doc))"  # todo: split doc const
        + ".forEach((e) =>"
        + BRACKET_START
        + "items.push("
        + kv_prop
        + ");"
        + BRACKET_END
        + ");"
        + RET.format("items")
    )


def gen_dict_body(_: "StartParseFunction") -> str:
    key_m = to_upper_camel_case(MAGIC_METHODS.get("__KEY__"))
    value_m = to_upper_camel_case(MAGIC_METHODS.get("__VALUE__"))
    # part_m = MAGIC_METHODS.get('__SPLIT_DOC__')
    return (
        "let item = {};"
        + "Array.from(this._splitDoc(this._doc))"  # todo: split doc const
        + ".forEach((e) =>"
        + BRACKET_START
        + f"let k = this._parse{key_m}(e);"
        + f"item[k] = this._parse{value_m}(e);"
        + BRACKET_END
        + ");"
        + RET.format("item")
    )


def gen_flat_list_body(_: "StartParseFunction") -> str:
    item_m = to_upper_camel_case(MAGIC_METHODS.get("__ITEM__"))
    # part_m = MAGIC_METHODS.get("__SPLIT_DOC__")
    return (
        f"let items = Array.from(this._splitDoc(this._doc)).map((e) => this._parse{item_m}(e));"
        + RET.format("items")
    )
