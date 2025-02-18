from typing import TYPE_CHECKING

from .template_bindings import TemplateBindings
from ssc_codegen.str_utils import to_upper_camel_case
from ssc_codegen.tokens import TokenType

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


def _make_docstring(value: str) -> str:
    if not value:
        return ""
    docstr_start = "/**"
    docstr_parts = "\n".join("* " + line for line in value.split("\n"))
    docstr_end = "*/"
    return docstr_start + "\n" + docstr_parts + "\n" + docstr_end


BINDINGS = TemplateBindings()
BINDINGS[TokenType.STRUCT] = "class {}"
BINDINGS[TokenType.STRUCT_INIT] = lambda: (
    "constructor(doc)"
    + BRACKET_START
    + "if (typeof doc === 'string') "
    + BRACKET_START
    + "this._doc = new DOMParser().parseFromString(doc, 'text/html');"
    + BRACKET_END
    + "else if (doc instanceof Document || doc instanceof Element)"
    + BRACKET_START
    + "this._doc = doc;"
    + BRACKET_END
    + "else"
    + BRACKET_START
    + ' throw new Error("Invalid input: Expected a Document, Element, or string");'
    + BRACKET_END
    + BRACKET_END
)
BINDINGS[TokenType.DOCSTRING] = _make_docstring
BINDINGS[TokenType.EXPR_RETURN] = "return {};"
BINDINGS[TokenType.EXPR_NO_RETURN] = "return null;"
BINDINGS[TokenType.EXPR_NESTED] = "let {} = (new {}({})).parse();"
BINDINGS[TokenType.STRUCT_PRE_VALIDATE] = "{}(value)"
BINDINGS[TokenType.STRUCT_PART_DOCUMENT] = "{}(value)"
BINDINGS[TokenType.STRUCT_FIELD] = "_parse{}(value)"
BINDINGS[TokenType.STRUCT_PARSE_START] = "{}()"
BINDINGS[TokenType.EXPR_DEFAULT_START] = lambda: "try {"
BINDINGS[TokenType.EXPR_DEFAULT_END] = (
    lambda val: "} catch(Error) {" + f"return {val};" + "}"
)

# string
BINDINGS[TokenType.EXPR_STRING_FORMAT] = "let {} = {};"
BINDINGS[TokenType.EXPR_LIST_STRING_FORMAT] = "let {} = {}.map(e => {});"


def _expr_str_trim(nxt: str, prv: str, chars: str):
    return (
        f"let {nxt}"
        + " = "
        + "(function (str, chars){return str.replace(new RegExp(`^[${chars}]+|[${chars}]+$`, 'g'), '');})"
        + f"({prv}, {chars!r});"
    )


BINDINGS[TokenType.EXPR_STRING_TRIM] = _expr_str_trim


def _expr_str_trim_all(nxt: str, prv: str, chars: str) -> str:
    return (
        f"let {nxt}"
        + " = "
        + f"{prv}.map(e =>"
        + "(function (str, chars){return str.replace(new RegExp(`^[${chars}]+|[${chars}]+$`, 'g'), '');})"
        + f"(e, {chars!r})"
        + ");"
    )


BINDINGS[TokenType.EXPR_LIST_STRING_TRIM] = _expr_str_trim_all


# const ltrim = function (str, chars) {
#     return str.replace(new RegExp(`^[${chars}]+`, 'g'), '');
# };
def _expr_str_ltrim(nxt: str, prv: str, chars: str) -> str:
    return (
        f"let {nxt}"
        + " = "
        + "(function (str, chars){return str.replace(new RegExp(`^[${chars}]+`, 'g'), '');})"
        + f"({prv}, {chars!r});"
    )


BINDINGS[TokenType.EXPR_STRING_LTRIM] = _expr_str_ltrim


def _expr_str_ltrim_all(nxt: str, prv: str, chars: str) -> str:
    return (
        f"let {nxt}"
        + " = "
        + f"{prv}.map(e =>"
        + "(function (str, chars){return str.replace(new RegExp(`^[${chars}]+`, 'g'), '');})"
        + f"(e, {chars!r})"
        + ");"
    )


BINDINGS[TokenType.EXPR_LIST_STRING_TRIM] = _expr_str_ltrim_all


# const rtrim = function (str, chars) {
#     return str.replace(new RegExp(`[${chars}]+$`, 'g'), '');
# };
#
def _expr_str_rtrim(nxt: str, prv: str, chars: str) -> str:
    return (
        f"let {nxt}"
        + " = "
        + "(function (str, chars) {return str.replace(new RegExp(`^[${chars}]+`, 'g'), '');})"
        + f"({prv}, {chars!r}); "
    )


BINDINGS[TokenType.EXPR_STRING_RTRIM] = _expr_str_rtrim


def _expr_str_rtrim_all(nxt: str, prv: str, chars: str) -> str:
    return (
        f"let {nxt}"
        + " = "
        + f"{prv}.map(e =>"
        + "(function (str, chars){return str.replace(new RegExp(`[${chars}]+$`, 'g'), '');})"
        + f"(e, {chars!r})"
        + ");"
    )


BINDINGS[TokenType.EXPR_LIST_STRING_RTRIM] = _expr_str_rtrim_all
BINDINGS[TokenType.EXPR_STRING_REPLACE] = "let {} = {}.replace({}, {});"
BINDINGS[TokenType.EXPR_LIST_STRING_REPLACE] = (
    "let {} = {}.map(e => e.replace({}, {}));"
)
BINDINGS[TokenType.EXPR_STRING_SPLIT] = "let {} = {}.split({});"
BINDINGS[TokenType.EXPR_REGEX] = "let {} = (new RegExp({})).exec({})[{}];"
BINDINGS[TokenType.EXPR_REGEX_ALL] = "let {} = (new RegExp({})).exec({});"
BINDINGS[TokenType.EXPR_REGEX_SUB] = "let {} = {}.replace({}, {});"
BINDINGS[TokenType.EXPR_LIST_REGEX_SUB] = (
    "let {} = {}.map(e => e.replace({}, {}));"
)
BINDINGS[TokenType.EXPR_LIST_STRING_INDEX] = "let {} = {}[{}];"
BINDINGS[TokenType.EXPR_LIST_DOCUMENT_INDEX] = "let {} = {}[{}];"
BINDINGS[TokenType.EXPR_LIST_JOIN] = "let {} = {}.join({});"
BINDINGS[TokenType.IS_EQUAL] = "if ({} != {}) throw new Error({});"
BINDINGS[TokenType.IS_NOT_EQUAL] = "if ({} == {}) throw new Error({});"
BINDINGS[TokenType.IS_CONTAINS] = "if (!({} in {})) throw new Error({});"
BINDINGS[TokenType.IS_REGEX_MATCH] = (
    "if ({}.match({}) === null) throw new Error({});"
)

EXPR_ASSIGN = "let {} = {};"

# PURE JS API
BINDINGS[TokenType.EXPR_CSS] = "let {} = {}.querySelector({});"
BINDINGS[TokenType.EXPR_CSS_ALL] = (
    "let {} = Array.from({}.querySelectorAll({}));"
)
# document.evaluate(xpath, element, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
BINDINGS[TokenType.EXPR_XPATH] = (
    "let {} = document.evaluate("
    + "{}, {}, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null"
    + ").singleNodeValue;"
)


def _expr_xpath_all(nxt: str, prv: str, query: str) -> str:  # noqa
    snapshot_var = f"s{nxt}"
    return (
        f'let {snapshot_var} = {prv}.evaluate("{query}", document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null); '
        + f"let {nxt} = "
        + "Array.from({ length: "
        + f"{snapshot_var}.snapshotLength"
        + "}, (_, i) =>"
        + f"{snapshot_var}.snapshotItem(i)"
        + ");"
    )


BINDINGS[TokenType.EXPR_XPATH_ALL] = _expr_xpath_all


# todo: remove _var_num param
def _expr_text_doc(_var_num: int, nxt: str, prv: str) -> str:
    return f'let {nxt} = typeof {prv}.textContent === "undefined" ? {prv}.documentElement.textContent : {prv}.textContent; '


BINDINGS[TokenType.EXPR_TEXT] = _expr_text_doc
BINDINGS[TokenType.EXPR_TEXT_ALL] = "let {} = {}.map(e => e.textContent);"


def _expr_raw(var_num: int, nxt: str, prv: str) -> str:
    return f'let {nxt} = typeof {prv}.outerHTML === "undefined" ? {prv}.documentElement.outerHTML : {prv}.outerHTML; '


BINDINGS[TokenType.EXPR_RAW] = _expr_raw

BINDINGS[TokenType.EXPR_RAW_ALL] = "let {} = {}.map(e => e.outerHTML);"
BINDINGS[TokenType.EXPR_ATTR] = "let {} = {}.getAttribute({});"
BINDINGS[TokenType.EXPR_ATTR_ALL] = "let {} = {}.map(e => e.getAttribute({}));"
BINDINGS[TokenType.IS_CSS] = "if (!{}.querySelector({})) throw new Error({});"
BINDINGS[TokenType.IS_XPATH] = (
    "if("
    + "!document.evaluate("
    + "{}, {}, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue"
    + ") throw new Error({});"
)


def gen_item_body(node: "StartParseFunction") -> str:
    # kv property
    # return { k1: this._parseK1(), k2: this._parseK2(), ...}
    return (
        "return "
        + BRACKET_START
        + ",".join(
            f"{f.name}: this._parse{to_upper_camel_case(f.name)}(this._doc)"
            for f in node.body
            if f.name not in MAGIC_METHODS
        )
        + BRACKET_END
        + ";"
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
    # return Array.from(this._splitDoc(this._doc)).map(e => ({
    #     f1: this.m1(e), ...
    #   }));
    return (
        "return "
        + "Array.from(this._splitDoc(this._doc)).map(e => ("
        + kv_prop
        + "));"
    )


def gen_dict_body(_: "StartParseFunction") -> str:
    key_m = to_upper_camel_case(MAGIC_METHODS.get("__KEY__"))
    value_m = to_upper_camel_case(MAGIC_METHODS.get("__VALUE__"))
    # parse() {
    #
    # }
    return (
        "return Array.from(this._splitDoc(this._doc)).reduce((item, e)"
        + f"=> (item[this._parse{key_m}(e)] = this._parse{value_m}(e), item)"
        + ", {});"
    )


def gen_flat_list_body(_: "StartParseFunction") -> str:
    item_m = to_upper_camel_case(MAGIC_METHODS.get("__ITEM__"))
    return f"return Array.from(this._splitDoc(this._doc)).map((e) => this._parse{item_m}(e));"
