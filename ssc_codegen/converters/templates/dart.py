from ssc_codegen.converters.utils import to_upper_camel_case
from ssc_codegen.tokens import VariableType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ssc_codegen.ast_ssc import StartParseFunction, TypeDef

TYPES = {
    VariableType.STRING: "String",
    VariableType.LIST_STRING: "List<String>",
    VariableType.OPTIONAL_STRING: "String?",
    VariableType.OPTIONAL_LIST_STRING: "List<String>?"
}

MAGIC_METHODS = {"__KEY__": "Key",
                 "__VALUE__": "Value",
                 "__ITEM__": "Item",
                 "__PRE_VALIDATE__": "_preValidate",
                 "__SPLIT_DOC__": "_splitDoc",
                 "__START_PARSE__": "parse"
                 }


START_BRACKET = "{"
END_BRACKET = "}"
CLS_HEAD = 'class {} '
def CLS_INIT(cls_name: str) -> str: # noqa
    code = 'late final Document selector;'
    code += cls_name + '(String rawDocument) { selector = html.parseHtmlDocument(rawDocument); }'
    code += cls_name + ".fromDocument(Document document) {selector = document; }"
    code += cls_name + ".fromElement(LIElement element) { selector = html.parseHtmlDocument(element.innerHtml as String); }"
    return code

def CLS_DOCSTRING(docstring: str) -> str:  # noqa
    return '\n'.join('/// ' + line for line in docstring.split('\n'))


TYPE_PREFIX = "T{}"
TYPEDEF = "typedef {} = {}; "
TYPE_DICT = "Map<String, {}>"
FLAT_LIST = "List<{}>"
# IN CURRENT LANGUAGE HAVE THIS PARSER LIB ONLY
BASE_IMPORTS = """"import 'dart:core';
"import 'package:universal_html/html.dart' show Document, LIElement;
import 'package:universal_html/parsing.dart' as html;
"""
RET = "return {};"
NO_RET = "return null;"
# first element always doc (if StructType.ITEM)
NESTED_FROM_DOC = "var {} = {}.fromDocument({}).parse();"
NESTED_FROM_ELEMENT = "var {} = {}.fromElement({}).parse();"
PRE_VALIDATE_HEAD = "{}(value)"
PART_DOC_HEAD = PRE_VALIDATE_HEAD
FN_PRE_VALIDATE = "{}(selector); "
FN_PARSE = "_parse{}({})"
FN_PARSE_START = "{} {}()"
FN_PART_DOC = "{}({})"
E_DEFAULT_START = "try {"
def E_DEFAULT_END(value: str) -> str: # noqa
    return "} catch(_){\n" + f"return {value};" + '}'


def fmt_template(template: str, prv_variable: str):
    return template.replace('{{}}', f"${prv_variable}")

PARSE_VAR = 'selector'
E_STR_FMT = "var {} = {};"
E_STR_FMT_ALL = "var {} = {}' + nxt + ' = ' + f'{prv}.map((e) => {});"
E_STR_TRIM = "var {} = {}.replaceFirst(RegExp({}), "").replaceFirst(RegExp({}), "");"
E_STR_TRIM_ALL = "var {} = {}.map((e) => e.replaceFirst(RegExp({}), "").replaceFirst({}, ""));"
E_STR_LTRIM = "var {} = {}.replaceFirst(RegExp({}), "");"
E_STR_LTRIM_ALL = "var {} = {}.map((e) => e.replaceFirst(RegExp({}), ""));"
E_STR_RTRIM = E_STR_LTRIM
E_STR_RTRIM_ALL = E_STR_LTRIM_ALL
E_STR_REPL = "var {} = {}.replaceAll({}, {});"
E_STR_REPL_ALL = "var {} = {}.map((e) => e.replaceAll({}, {}));"
E_STR_SPLIT = "var {} = {}.split({});"
E_RE = "var {} = RegExp({}).firstMatch({})?.group({})!;"
E_RE_ALL = "var {} = RegExp({}).allMatches({}).map((e) => e.group(1)!).toList();"
E_RE_SUB = "var {} = {}.replaceAll(RegExp({}), {});"
E_RE_SUB_ALL = "var {} = {}.map((e) => e.replaceAll(RegExp({}), {})));"
E_INDEX = "var {} = {}[{}];"
E_JOIN = "var {} = {}.join({});"
E_EQ = "assert({} == {}, {});"
E_NE = "assert({} != {}, {});"
E_IN = "assert({} != null && {}.contains({}), {});"
E_IS_RE = "assert({} != null && RegExp({}).firstMatch({}) != null, {});"
E_CSS = "var {} = {}.querySelector({});"
E_CSS_ALL = "var {} = {}.querySelectorAll({});"
E_TEXT = "var {} = {}.text;"
E_TEXT_ALL = "var {} = {}.map((e) => e.text).toList();"
E_RAW = "var {} = {}.innerHtml;"
# HACK: document object not contains innerHtml property
E_DOC_RAW = "var {} = {}.querySelector('html').innerHtml;"
E_RAW_ALL = "var {} = {}.map((e) => e.innerHtml).toList();"
E_ATTR = "var {} = {}.attributes[{}];"
E_ATTR_ALL = "var {} = {}.map((e) => e.attributes[{}]).toList();"
E_IS_CSS = "assert({}.querySelector({}), {});"
E_ASSIGN = "var {} = {}; "  # used in assert cases
# used record types
# typedef TNestedStructO = List<List<String>>; flat list
# typedef TSubExampleStruct = ({String href, String text, TNestedStructO chars}); item
# typedef TExampleStruct = ({TSubExampleStruct urls}); # dict


def typedef_dict(node: 'TypeDef') -> str:
    t_name = TYPE_PREFIX.format(node.name)
    value_ret = [f for f in node.body if f.name == '__VALUE__'][0].type
    if node.body[-1].type == VariableType.NESTED:
        type_ = TYPE_PREFIX.format(node.body[-1].nested_class)
    else:
        type_ = TYPES.get(value_ret)
    type_ = TYPE_DICT.format(type_)
    return TYPEDEF.format(t_name, type_)


def typedef_flat_list(node: 'TypeDef') -> str:
    t_name = TYPE_PREFIX.format(node.name)
    value_ret = [f for f in node.body if f.name == '__ITEM__'][0].type
    if node.body[-1].type == VariableType.NESTED:
        type_ = TYPE_PREFIX.format(node.body[-1].nested_class)
    else:
        type_ = TYPES.get(value_ret)
    type_ = FLAT_LIST.format(type_)
    return TYPEDEF.format(t_name, type_)


def typedef_item_record(node: 'TypeDef') -> str:
    t_name = TYPE_PREFIX.format(node.name)
    record_body = {}
    for f in node.body:
        if f.name in MAGIC_METHODS:
            continue
        if f.type == VariableType.NESTED:
            type_ = TYPE_PREFIX.format(node.body[-1].nested_class)
        else:
            type_ = TYPES.get(f.type)
        record_body[f.name] = type_
    record_code = "({" + ', '.join(f"{v} {k}" for k, v in record_body.items()) + '})'
    return TYPEDEF.format(t_name, record_code)


def typedef_list_record(node: 'TypeDef') -> str:
    t_name = TYPE_PREFIX.format(node.name)
    record_body = {}
    for field in node.body:
        if field.name in MAGIC_METHODS:
            continue
        if field.type == VariableType.NESTED:
            type_ = TYPE_PREFIX.format(node.body[-1].nested_class)
        else:
            type_ = TYPES.get(field.type)
    record_code = "({" + ', '.join(f"{v} {k}" for k, v in record_body.items()) + '})'
    return TYPEDEF.format(t_name, record_code)


def parse_item_code(node: 'StartParseFunction') -> str:
    t_name = TYPE_PREFIX.format(node.parent.name)
    body = f"{t_name} item = ("
    body_fields = {}
    for f in node.body:
        if f.name in MAGIC_METHODS:
            continue
        name = to_upper_camel_case(f.name)
        body_fields[f.name] = FN_PARSE.format(name, PARSE_VAR)
    body += ', '.join(f'{k}: {v}' for k,v in body_fields.items()) + ');'
    body += RET.format('item')
    return body


def parse_list_code(node: 'StartParseFunction') -> str:
    t_name = TYPE_PREFIX.format(node.parent.name)
    t_container = FLAT_LIST.format(t_name)
    body = f"{t_container} items = []; "
    part_call = FN_PART_DOC.format(MAGIC_METHODS.get('__SPLIT_DOC__'), PARSE_VAR)
    body += f"for (var e in {part_call})" + ' ' + START_BRACKET
    body_record = f'{t_name} item = ('
    body_fields = {}

    for f in node.body:
        if f.name in MAGIC_METHODS:
            continue
        name = to_upper_camel_case(f.name)
        body_fields[f.name] = FN_PARSE.format(name, 'e')
    body_record += ', '.join(f'{k}: {v}' for k,v in body_fields.items()) + ');'
    body += body_record + 'items.add(item); ' + END_BRACKET
    body += RET.format('items')
    return body


def parse_dict_code(node: 'StartParseFunction') -> str:
    t_name = TYPE_PREFIX.format(node.parent.name)

    part_m = MAGIC_METHODS.get('__SPLIT_DOC__')
    key_m = MAGIC_METHODS.get('__KEY__')
    value_m = MAGIC_METHODS.get('__VALUE__')

    part_call = FN_PART_DOC.format(part_m, PARSE_VAR)
    key_call = FN_PARSE.format(key_m, 'e')
    value_call = FN_PARSE.format(value_m, 'e')

    body = t_name + " items = {};"
    body += f'for (var e in {part_call})' + ' {'
    body += f"items[{key_call}(e)] = items[{value_call}()e]; "
    body += END_BRACKET
    body += RET.format('items')
    return body


def parse_flat_list_code(node: 'StartParseFunction') -> str:
    t_name = TYPE_PREFIX.format(node.parent.name)
    part_m = MAGIC_METHODS.get('__SPLIT_DOC__')
    item_m = MAGIC_METHODS.get('__ITEM__')

    part_call = FN_PART_DOC.format(part_m, PARSE_VAR)
    item_call = FN_PARSE.format(item_m, 'e')

    body = t_name + " items = [];"
    body += f'for (var e in {part_call}) ' + START_BRACKET
    body += f"items.add({item_call}(e)); " + END_BRACKET
    body += RET.format('items')
    return body
