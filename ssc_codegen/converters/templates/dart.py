from typing import TYPE_CHECKING

from ssc_codegen.converters.templates.utils import TemplateBindings
from ssc_codegen.converters.utils import to_upper_camel_case
from ssc_codegen.tokens import VariableType, TokenType

if TYPE_CHECKING:
    from ssc_codegen.ast_ssc import StartParseFunction, TypeDef

TYPES = {
    VariableType.STRING: "String",
    VariableType.LIST_STRING: "List<String>",
    VariableType.OPTIONAL_STRING: "String?",
    VariableType.OPTIONAL_LIST_STRING: "List<String>?",
}

MAGIC_METHODS = {
    "__KEY__": "Key",
    "__VALUE__": "Value",
    "__ITEM__": "Item",
    "__PRE_VALIDATE__": "_preValidate",
    "__SPLIT_DOC__": "_splitDoc",
    "__START_PARSE__": "parse",
}

START_BRACKET = "{"
END_BRACKET = "}"

BINDINGS = TemplateBindings()
BINDINGS[TokenType.STRUCT] = "class {} "


def _cls_init(cls_name: str) -> str:  # noqa
    code = "late final Document selector;"
    code += (
            cls_name
            + "(String rawDocument) { selector = html.parseHtmlDocument(rawDocument); }"
    )
    code += (
            cls_name + ".fromDocument(Document document) {selector = document; }"
    )
    code += (
            cls_name
            + ".fromElement(LIElement element) { selector = html.parseHtmlDocument(element.innerHtml as String); }"
    )
    return code


BINDINGS[TokenType.STRUCT_INIT] = _cls_init
BINDINGS[TokenType.DOCSTRING] = lambda docstring: "\n".join(
    f"/// {line}" for line in docstring.split("\n")
)

# IN CURRENT LANGUAGE HAVE THIS STABLE PARSER LIB ONLY
BINDINGS[TokenType.IMPORTS] = (
        "import 'dart:core';\n"
        + "import 'package:universal_html/html.dart' show Document, LIElement;\n"
        + "import 'package:universal_html/parsing.dart' as html;"
)
BINDINGS[TokenType.EXPR_RETURN] = "return {};"
BINDINGS[TokenType.EXPR_NO_RETURN] = "return null;"


def _nested_expr(var_num: int, nxt: str, schema: str, prv: str) -> str:
    # first element as document type (naive)
    # first element always doc (if StructType.ITEM)
    if var_num == 0:
        return f"var {nxt} = {schema}.fromDocument({prv}).parse();"
    return f"var {nxt} = {schema}.fromElement({prv}).parse();"


BINDINGS[TokenType.EXPR_NESTED] = _nested_expr
BINDINGS[TokenType.STRUCT_PRE_VALIDATE] = "{}(value)"
BINDINGS[TokenType.STRUCT_PART_DOCUMENT] = "{}(value)"
BINDINGS[TokenType.STRUCT_FIELD] = "_parse{}({})"
BINDINGS[TokenType.STRUCT_PARSE_START] = "{} {}()"

BINDINGS[TokenType.EXPR_DEFAULT_START] = lambda: "try {"
BINDINGS[TokenType.EXPR_DEFAULT_END] = lambda value: "} catch(_){\n" + f"return {value};" + "}"
# string
BINDINGS[TokenType.EXPR_STRING_FORMAT] = "var {} = {};"
BINDINGS[TokenType.EXPR_LIST_STRING_FORMAT] = "var {} = {}.map((e) => {});"
BINDINGS[TokenType.EXPR_STRING_TRIM] = "var {} = {}.replaceFirst(RegExp({}), "").replaceFirst(RegExp({}), "");"
BINDINGS[TokenType.EXPR_LIST_STRING_TRIM] = (
        'var {} = {}.map((e) => e.replaceFirst(RegExp({}), ""'
        + ').replaceFirst(RegExp({}), ""));'
)
BINDINGS[TokenType.EXPR_STRING_LTRIM] = "var {} = {}.replaceFirst(RegExp({}), "");"
BINDINGS[TokenType.EXPR_LIST_STRING_LTRIM] = "var {} = {}.map((e) => e.replaceFirst(RegExp({}), ""));"
BINDINGS[TokenType.EXPR_STRING_RTRIM] = "var {} = {}.replaceFirst(RegExp({}), "");"
BINDINGS[TokenType.EXPR_LIST_STRING_RTRIM] = "var {} = {}.map((e) => e.replaceFirst(RegExp({}), ""));"
BINDINGS[TokenType.EXPR_STRING_REPLACE] = "var {} = {}.replaceAll({}, {});"
BINDINGS[TokenType.EXPR_LIST_STRING_REPLACE] = "var {} = {}.map((e) => e.replaceAll({}, {}));"
BINDINGS[TokenType.EXPR_STRING_SPLIT] = "var {} = {}.split({});"
# regex
BINDINGS[TokenType.EXPR_REGEX] = "var {} = RegExp({}).firstMatch({})?.group({})!;"
BINDINGS[TokenType.EXPR_REGEX_ALL] = "var {} = RegExp({}).allMatches({}).map((e) => e.group(1)!).toList();"
BINDINGS[TokenType.EXPR_REGEX_SUB] = "var {} = {}.replaceAll(RegExp({}), {});"
BINDINGS[TokenType.EXPR_LIST_REGEX_SUB] = "var {} = {}.map((e) => e.replaceAll(RegExp({}), {})));"
BINDINGS[TokenType.EXPR_LIST_STRING_INDEX] = "var {} = {}[{}];"
BINDINGS[TokenType.EXPR_LIST_DOCUMENT_INDEX] = "var {} = {}[{}];"
BINDINGS[TokenType.EXPR_LIST_JOIN] = "var {} = {}.join({});"
# assert
BINDINGS[TokenType.IS_EQUAL] = "assert({} == {}, {});"
BINDINGS[TokenType.IS_NOT_EQUAL] = "assert({} != {}, {});"
BINDINGS[TokenType.IS_CONTAINS] = "assert({} != null && {}.contains({}), {});"
BINDINGS[TokenType.IS_REGEX_MATCH] = "assert({} != null && RegExp({}).firstMatch({}) != null, {});"

# universal html API
BINDINGS[TokenType.EXPR_CSS] = "var {} = {}.querySelector({});"
BINDINGS[TokenType.EXPR_CSS_ALL] = "var {} = {}.querySelectorAll({});"
BINDINGS[TokenType.EXPR_TEXT] = "var {} = {}.text;"
BINDINGS[TokenType.EXPR_TEXT_ALL] = "var {} = {}.map((e) => e.text).toList();"


def _expr_raw(var_num: int, nxt: str, prv: str) -> str:
    # HACK: document object not contains innerHtml property
    if var_num == 0:
        return f"var {nxt} = {prv}.querySelector('html').innerHtml;"
    return f"var {nxt} = {prv}.innerHtml;"

BINDINGS[TokenType.EXPR_RAW] = _expr_raw
BINDINGS[TokenType.EXPR_RAW_ALL] = "var {} = {}.map((e) => e.innerHtml).toList();"
BINDINGS[TokenType.EXPR_ATTR] = "var {} = {}.attributes[{}];"
BINDINGS[TokenType.EXPR_ATTR_ALL] = "var {} = {}.map((e) => e.attributes[{}]).toList();"
BINDINGS[TokenType.IS_CSS] = "assert({}.querySelector({}), {});"
TYPE_PREFIX = "T{}"
TYPEDEF = "typedef {} = {}; "
TYPE_DICT = "Map<String, {}>"
FLAT_LIST = "List<{}>"

PARSE_VAR = "selector"

E_ASSIGN = "var {} = {}; "  # used in assert cases


# used record types
# typedef TNestedStructO = List<List<String>>; flat list
# typedef TSubExampleStruct = ({String href, String text, TNestedStructO chars}); item
# typedef TExampleStruct = ({TSubExampleStruct urls}); # dict


def typedef_dict(node: "TypeDef") -> str:
    t_name = TYPE_PREFIX.format(node.name)
    value_ret = [f for f in node.body if f.name == "__VALUE__"][0].ret_type
    if node.body[-1].ret_type == VariableType.NESTED:
        type_ = TYPE_PREFIX.format(node.body[-1].nested_class)
    else:
        type_ = TYPES.get(value_ret)
    type_ = TYPE_DICT.format(type_)
    return TYPEDEF.format(t_name, type_)


def typedef_flat_list(node: "TypeDef") -> str:
    t_name = TYPE_PREFIX.format(node.name)
    value_ret = [f for f in node.body if f.name == "__ITEM__"][0].ret_type
    if node.body[-1].ret_type == VariableType.NESTED:
        type_ = TYPE_PREFIX.format(node.body[-1].nested_class)
    else:
        type_ = TYPES.get(value_ret)
    type_ = FLAT_LIST.format(type_)
    return TYPEDEF.format(t_name, type_)


def typedef_item_record(node: "TypeDef") -> str:
    t_name = TYPE_PREFIX.format(node.name)
    record_body = {}
    for f in node.body:
        if f.name in MAGIC_METHODS:
            continue
        if f.ret_type == VariableType.NESTED:
            type_ = TYPE_PREFIX.format(node.body[-1].nested_class)
        else:
            type_ = TYPES.get(f.ret_type)
        record_body[f.name] = type_
    record_code = (
            "({" + ", ".join(f"{v} {k}" for k, v in record_body.items()) + "})"
    )
    return TYPEDEF.format(t_name, record_code)


def typedef_list_record(node: "TypeDef") -> str:
    t_name = TYPE_PREFIX.format(node.name)
    record_body = {}
    for field in node.body:
        if field.name in MAGIC_METHODS:
            continue
        if field.ret_type == VariableType.NESTED:
            type_ = TYPE_PREFIX.format(node.body[-1].nested_class)
        else:
            type_ = TYPES.get(field.ret_type)
    record_code = (
            "({" + ", ".join(f"{v} {k}" for k, v in record_body.items()) + "})"
    )
    return TYPEDEF.format(t_name, record_code)


def parse_item_code(node: "StartParseFunction") -> str:
    t_name = TYPE_PREFIX.format(node.parent.name)
    body = f"{t_name} item = ("
    body_fields = {}
    for f in node.body:
        if f.name in MAGIC_METHODS:
            continue
        name = to_upper_camel_case(f.name)
        body_fields[f.name] = FN_PARSE.format(name, PARSE_VAR)
    body = (
            f"{t_name} item = ("
            + ", ".join(f"{k}: {v}" for k, v in body_fields.items())
            + ");"
            + RET.format("item")
    )
    return body


def parse_list_code(node: "StartParseFunction") -> str:
    t_name = TYPE_PREFIX.format(node.parent.name)
    t_container = FLAT_LIST.format(t_name)
    body = f"{t_container} items = []; "
    part_call = FN_PART_DOC.format(
        MAGIC_METHODS.get("__SPLIT_DOC__"), PARSE_VAR
    )
    body += f"for (var e in {part_call})" + " " + START_BRACKET
    body_record = f"{t_name} item = ("
    body_fields = {}

    for f in node.body:
        if f.name in MAGIC_METHODS:
            continue
        name = to_upper_camel_case(f.name)
        body_fields[f.name] = FN_PARSE.format(name, "e")
    body_record += ", ".join(f"{k}: {v}" for k, v in body_fields.items()) + ");"
    body += body_record + "items.add(item); " + END_BRACKET
    body += RET.format("items")
    return body


def parse_dict_code(node: "StartParseFunction") -> str:
    t_name = TYPE_PREFIX.format(node.parent.name)

    part_m = MAGIC_METHODS.get("__SPLIT_DOC__")
    key_m = MAGIC_METHODS.get("__KEY__")
    value_m = MAGIC_METHODS.get("__VALUE__")

    part_call = FN_PART_DOC.format(part_m, PARSE_VAR)
    key_call = FN_PARSE.format(key_m, "e")
    value_call = FN_PARSE.format(value_m, "e")

    body = t_name + " items = {};"
    body += f"for (var e in {part_call})" + " {"
    body += f"items[{key_call}(e)] = items[{value_call}()e]; "
    body += END_BRACKET
    body += RET.format("items")
    return body


def parse_flat_list_code(node: "StartParseFunction") -> str:
    t_name = TYPE_PREFIX.format(node.parent.name)
    part_m = MAGIC_METHODS.get("__SPLIT_DOC__")
    item_m = MAGIC_METHODS.get("__ITEM__")

    return (t_name + " items = [];"
            + f"for (var e in {part_call}) " + START_BRACKET
        )

    part_call = f"{part_m}({PARSE_VAR})"
    item_call = FN_PARSE.format(item_m, "e")

    body = t_name + " items = [];"
    body += f"for (var e in {part_call}) " + START_BRACKET
    body += f"items.add({item_call}(e)); " + END_BRACKET
    body += RET.format("items")
    return body
