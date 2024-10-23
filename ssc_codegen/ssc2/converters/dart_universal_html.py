# TODO: required enchant, not tested
from .base import BaseCodeConverter, left_right_var_names
from .utils import to_upper_camel_case as up_camel, escape_str, wrap_double_quotes as wrap_q
from ..ast_ssc import (
    StructParser,
    ModuleImports,
    PreValidateFunction,
    StructFieldFunction,
    Docstring,
    StartParseFunction,
    DefaultValueWrapper,
    PartDocFunction,

    HtmlCssExpression, HtmlCssAllExpression,
    HtmlAttrExpression, HtmlAttrAllExpression,
    HtmlTextExpression, HtmlTextAllExpression,
    HtmlRawExpression, HtmlRawAllExpression,
    HtmlXpathExpression, HtmlXpathAllExpression,

    FormatExpression, MapFormatExpression,
    TrimExpression, MapTrimExpression,
    LTrimExpression, MapLTrimExpression,
    RTrimExpression, MapRTrimExpression,
    ReplaceExpression, MapReplaceExpression,
    SplitExpression,

    NestedExpression,
    RegexExpression, RegexSubExpression, MapRegexSubExpression, RegexAllExpression,

    ReturnExpression, NoReturnExpression,

    TypeDef,
    IndexDocumentExpression, IndexStringExpression, JoinExpression,

    IsCssExpression, IsXPathExpression, IsEqualExpression, IsContainsExpression,
    IsRegexMatchExpression, IsNotEqualExpression, StructInit
)
from ..consts import RESERVED_METHODS
from ..tokens import TokenType, StructType, VariableType

converter = BaseCodeConverter()

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


@converter.pre(TokenType.TYPEDEF)
def tt_typedef(node: TypeDef):
    t_name = f'class T{node.name}'

    code = f"{t_name}" + '{\n'
    if node.struct.type == StructType.DICT:
        # class TNAME {
        #   final String key;
        #   final TYPE value;
        #   TSubExampleStruct({required this.key, required this.value});
        #   Map<String, String> toMap() {return {key: value};}
        #   factory TNAME.fromMap(Map<String, dynamic> map) {
        #     return TNAME(key: map.keys.first, text: map.values.first,);}
        # }
        value_ret = [f for f in node.body if f.name == '__VALUE__'][0].type
        if node.body[-1].type == VariableType.NESTED:
            type_ = f"T{node.body[-1].nested_class}"
        else:
            type_ = TYPES.get(value_ret)
        code += f"final String key;\n"
        code += f"final {type_} value;\n"
        code += f"T{node.name}" + '({required this.key, required this.value});\n'
        code += f'Map<String, {type_}> toMap()' + '{ return {key: value}; }\n'
        code += f'factory T{node.name}.fromMap(Map<String, ' + type_ + '> map) { '
        code += f'return T{node.name}(key: map.keys.first, value: map.values.first);' + '}'

    elif node.struct.type in {StructType.ITEM, StructType.LIST}:
        constructor_code = f"T{node.name}(" + "{"
        to_map_code = "Map<String, dynamic> toMap() { return {"
        from_map_code = f"factory T{node.name}.fromMap(Map<String, dynamic> map) " + "{ return " + f"T{node.name}("
        for field in node.body:
            if field.name in RESERVED_METHODS:
                continue
            if field.type == VariableType.NESTED:
                type_ = f"T{node.body[-1].nested_class}"
            else:
                type_ = TYPES.get(field.type)
            code += f"final {type_} {field.name}; "
            constructor_code += f"required this.{field.name}, "
            to_map_code += f'"{field.name}": {field.name}, '
            from_map_code += f'{field.name}: map["{field.name}"], '
        constructor_code += '});'
        to_map_code += '};}'
        from_map_code += ');}'
        code += constructor_code + to_map_code + from_map_code

    elif node.struct.type == StructType.FLAT_LIST:
        value_ret = [f for f in node.body if f.name == '__ITEM__'][0].type
        if node.body[-1].type == VariableType.NESTED:
            type_ = f"T{node.body[-1].nested_class}"
        else:
            type_ = TYPES.get(value_ret)
        code = f'typedef T{node.name} = List<{type_}>; '
    return code


@converter.post(TokenType.TYPEDEF)
def tt_typedef(node: TypeDef):
    if node.struct.type != StructType.FLAT_LIST:
        return '}'
    return ''


# dart API
@converter.pre(TokenType.STRUCT)
def tt_struct(node: StructParser) -> str:
    return f"class {node.name}" + "{"


@converter.post(TokenType.STRUCT)
def tt_struct(_: StructParser) -> str:
    return "}"


@converter.pre(TokenType.STRUCT_INIT)
def tt_init(node: StructInit) -> str:
    code = "late final Document selector;"
    # main constructor (from string)
    code += node.name + "(String rawDocument) {"
    code += "selector = html.parseHtmlDocument(rawDocument); }"
    # from Document constructor
    code += node.name + ".fromDocument(Document document) {"
    code += "selector = document;"
    code += "}"
    # from element constructor
    code += node.name + ".fromElement(LIElement element) {"
    code += "selector = html.parseHtmlDocument(element.innerHtml as String);"
    code += "}"
    return code


@converter.pre(TokenType.DOCSTRING)
def tt_docstring(node: Docstring) -> str:
    if node.value:
        return '\n'.join('/// ' + line for line in node.value.split('\n'))
    return ''


@converter.pre(TokenType.IMPORTS)
def tt_imports(_: ModuleImports) -> str:
    buildin_imports = "import 'dart:core';\n"
    buildin_imports += "import 'package:universal_html/html.dart' show Document, LIElement;\n"
    buildin_imports += "import 'package:universal_html/parsing.dart' as html;\n"
    return buildin_imports


@converter.pre(TokenType.EXPR_RETURN)
def tt_ret(node: ReturnExpression) -> str:
    _, nxt = left_right_var_names("value", node.variable)
    return f"return {nxt};"


@converter.pre(TokenType.EXPR_NO_RETURN)
def tt_no_ret(_: NoReturnExpression) -> str:
    return "return null;"


@converter.pre(TokenType.EXPR_NESTED)
def tt_nested(node: NestedExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    # first element as document type naive
    if node.variable.num == 0:
        return f"var {nxt} = {node.schema}.fromDocument({prv}).parse();"
    return f"var {nxt} = {node.schema}.fromElement({prv}).parse();"


@converter.pre(TokenType.STRUCT_PRE_VALIDATE)
def tt_pre_validate(node: PreValidateFunction) -> str:
    return f"{MAGIC_METHODS.get(node.name)}(value)" + "{"


@converter.post(TokenType.STRUCT_PRE_VALIDATE)
def tt_pre_validate(_: PreValidateFunction) -> str:
    return "}"


@converter.pre(TokenType.STRUCT_PART_DOCUMENT)
def tt_part_document(_: PartDocFunction):
    return f"{MAGIC_METHODS.get('__SPLIT_DOC__')}(value)" + '{'


@converter.post(TokenType.STRUCT_PART_DOCUMENT)
def tt_part_document(_: PartDocFunction):
    return '}'


@converter.pre(TokenType.STRUCT_FIELD)
def tt_function(node: StructFieldFunction) -> str:
    name = MAGIC_METHODS.get(node.name, node.name)
    if name == node.name:
        name = up_camel(node.name)
    return f"_parse{name}(value)" + ' {'


@converter.post(TokenType.STRUCT_FIELD)
def tt_function(_: StructFieldFunction) -> str:
    return '}'


@converter.pre(TokenType.STRUCT_PARSE_START)
def tt_start_parse(node: StartParseFunction) -> str:
    code = f"T{node.parent.name} {MAGIC_METHODS.get(node.name)}() " + '{\n'
    if any(f.name == '__PRE_VALIDATE__' for f in node.body):
        n = MAGIC_METHODS.get('__PRE_VALIDATE__')
        code += f"{n}(selector);\n"
    # TODO: typing
    match node.type:
        case StructType.ITEM:
            body = 'Map<String, dynamic> items = {};\n'
            for f in node.body:
                if f.name in RESERVED_METHODS:
                    continue
                name = up_camel(f.name)
                body += f'items[{f.name!r}] = _parse{name}(selector);\n'
            return code + body + f'return T{node.parent.name}.fromMap(items);'
        case StructType.LIST:
            # old signature: 'List<Map<String, dynamic>> items = [];\n'
            body = f'List<T{node.name}> items = [];\n'
            n = MAGIC_METHODS.get('__SPLIT_DOC__')
            body += f'for (var e in {n}(selector)) ' + '{\n'
            body += 'Map<String, dynamic> tmpItem = {};\n'
            for f in node.body:
                if f.name in RESERVED_METHODS:
                    continue
                name = up_camel(f.name)
                body += f'tmpItem[{f.name!r}] = _parse{name}(e);\n'
            body += f'items.add(T{node.parent.name}.fromMap(tmpItem)); ' + '}'
            return code + body + 'return items;'
        case StructType.DICT:
            body = "Map<String, dynamic> items = {};\n"

            part_m = MAGIC_METHODS.get('__SPLIT_DOC__')
            key_m = MAGIC_METHODS.get('__KEY__')
            value_m = MAGIC_METHODS.get('__VALUE__')
            body += f'for (var e in {part_m}(selector))' + '{'
            body += f'items[{key_m}(e)] = _parse{value_m}(e);'
            body += '}\n'
            body += f'return T{node.parent.name}.fromMap(items);'
            return code + body
        case StructType.FLAT_LIST:
            body = f'T{node.parent.name} items = [];\n'
            item_m = MAGIC_METHODS.get('__ITEM__')
            part_m = MAGIC_METHODS.get('__SPLIT_DOC__')
            body += f'for (var e in {part_m}(selector))' + '{\n'
            body += "Map<String, dynamic> tmpItem = {};\n"
            body += f'items.add(_parse{item_m}(e));\n'
            body += '}\n'
            return code + body + 'return items;'
        case _:
            raise NotImplementedError("Unknown struct type")


@converter.post(TokenType.STRUCT_PARSE_START)
def tt_start_parse(_: StartParseFunction) -> str:
    return '}'


@converter.pre(TokenType.EXPR_DEFAULT)
def tt_default(node: DefaultValueWrapper) -> str:
    return "try {"


@converter.post(TokenType.EXPR_DEFAULT)
def tt_default(node: DefaultValueWrapper) -> str:
    val = repr(node.value) if isinstance(node.value, str) else 'null'
    return "} catch(_){\n" + f"return {val};" + '}'


@converter.pre(TokenType.EXPR_STRING_FORMAT)
def tt_string_format(node: FormatExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    template = node.fmt.replace('{{}}', f"${prv}")
    return 'var ' + nxt + ' = ' + f"{template};"


@converter.pre(TokenType.EXPR_LIST_STRING_FORMAT)
def tt_string_format_all(node: MapFormatExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    template = node.fmt.replace('{{}}', "$e")
    return 'var ' + nxt + ' = ' + f'{prv}.map((e) => {template!r});'


@converter.pre(TokenType.EXPR_STRING_TRIM)
def tt_string_trim(node: TrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = node.value
    left = wrap_q('^' + escape_str(chars))
    right = wrap_q(escape_str(chars + '$'))
    return f'var {nxt} = {prv}.replaceFirst(RegExp({left}), "").replaceFirst(RegExp({right}), "");'


@converter.pre(TokenType.EXPR_LIST_STRING_TRIM)
def tt_string_trim_all(node: MapTrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = node.value
    left = wrap_q('^' + escape_str(chars))
    right = wrap_q(escape_str(chars + '$'))
    return f'var {nxt} = {prv}.map((e) => e.replaceFirst(RegExp({left}), "").replaceFirst({right}, ""));'


@converter.pre(TokenType.EXPR_STRING_LTRIM)
def tt_string_ltrim(node: LTrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = node.value
    left = wrap_q('^' + escape_str(chars))

    return f'var {nxt} = {prv}.replaceFirst(RegExp({left}), "");'


@converter.pre(TokenType.EXPR_LIST_STRING_LTRIM)
def tt_string_ltrim_all(node: MapLTrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = node.value
    left = wrap_q('^' + escape_str(chars))

    return f'var {nxt} = {prv}.map((e) => e.replaceFirst(RegExp({left}), ""));'


@converter.pre(TokenType.EXPR_STRING_RTRIM)
def tt_string_rtrim(node: RTrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = node.value
    right = wrap_q(escape_str(chars + '$'))

    return f'var {nxt} = {prv}.replaceFirst(RegExp({right}), "");'


@converter.pre(TokenType.EXPR_LIST_STRING_RTRIM)
def tt_string_rtrim_all(node: MapRTrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = node.value
    right = wrap_q(escape_str(chars + '$'))

    return f'var {nxt} = {prv}.map((e) => e.replaceFirst(RegExp({right}), ""));'


@converter.pre(TokenType.EXPR_STRING_REPLACE)
def tt_string_replace(node: ReplaceExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    old, new = node.old, node.new
    return f"var {nxt} = {prv}.replaceAll({old!r}, {new!r});"


@converter.pre(TokenType.EXPR_LIST_STRING_REPLACE)
def tt_string_replace_all(node: MapReplaceExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    old, new = node.old, node.new
    return f"var {nxt} = {prv}.map((e) => e.replaceAll({old!r}, {new!r}));"


@converter.pre(TokenType.EXPR_STRING_SPLIT)
def tt_string_split(node: SplitExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    sep = node.sep
    return f"var {nxt} = {prv}.split({sep!r});"


@converter.pre(TokenType.EXPR_REGEX)
def tt_regex(node: RegexExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    pattern = node.pattern
    group = node.group
    return f"var {nxt} = RegExp({pattern!r}).firstMatch({prv})?.group({group})!;"


@converter.pre(TokenType.EXPR_REGEX_ALL)
def tt_regex_all(node: RegexAllExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    pattern = node.pattern
    # RegExp(pattern).allMatches(s).map((e) => e.group(group)!).toList();
    return f"var {nxt} = RegExp({pattern!r}).allMatches({prv}).map((e) => e.group(1)!).toList();"


@converter.pre(TokenType.EXPR_REGEX_SUB)
def tt_regex_sub(node: RegexSubExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    pattern = node.pattern
    repl = node.repl
    return f"var {nxt} = {prv}.replaceAll(RegExp({pattern!r}), {repl!r});"


@converter.pre(TokenType.EXPR_LIST_REGEX_SUB)
def tt_regex_sub_all(node: MapRegexSubExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    pattern = node.pattern
    repl = node.repl
    return f"var {nxt} = {prv}.map((e) => e.replaceAll(RegExp({pattern!r}), {repl!r})));"


@converter.pre(TokenType.EXPR_LIST_STRING_INDEX)
def tt_string_index(node: IndexStringExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    return f"var {nxt} = {prv}[{node.value}];"


@converter.pre(TokenType.EXPR_LIST_DOCUMENT_INDEX)
def tt_doc_index(node: IndexDocumentExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    return f"var {nxt} = {prv}[{node.value}];"


@converter.pre(TokenType.EXPR_LIST_JOIN)
def tt_join(node: JoinExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    sep = node.sep
    return f"{nxt} = {prv}.join({sep!r});"


@converter.pre(TokenType.IS_EQUAL)
def tt_is_equal(node: IsEqualExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    code = f"assert({prv} == {node.value}, {node.msg!r});\n"
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += f"var {nxt} = {prv};"
    return code


@converter.pre(TokenType.IS_NOT_EQUAL)
def tt_is_not_equal(node: IsNotEqualExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    code = f"assert({prv} != {node.value}, {node.msg!r});\n"
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += f"var {nxt} = {prv};"
    return code


@converter.pre(TokenType.IS_CONTAINS)
def tt_is_contains(node: IsContainsExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    code = f"assert({prv} != null && {prv}.contains({node.item!r}), {node.msg!r});\n"
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += f"var {nxt} = {prv};"
    return code


@converter.pre(TokenType.IS_REGEX_MATCH)
def tt_is_regex(node: IsRegexMatchExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    code = f"assert({prv} != null && RegExp({node.pattern!r}).firstMatch({prv}) != null, {node.msg!r});\n"
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += f"var {nxt} = {prv};"
    return code


# universal html API
@converter.pre(TokenType.EXPR_CSS)
def tt_css(node: HtmlCssExpression) -> str:
    q = node.query
    prv, nxt = left_right_var_names("value", node.variable)
    return f"var {nxt} = {prv}.querySelector({q!r});"


@converter.pre(TokenType.EXPR_CSS_ALL)
def tt_css_all(node: HtmlCssAllExpression) -> str:
    q = node.query
    prv, nxt = left_right_var_names("value", node.variable)
    return f"var {nxt} = {prv}.querySelectorAll({q!r});"


@converter.pre(TokenType.EXPR_XPATH)
def tt_xpath(_: HtmlXpathExpression) -> str:
    raise NotImplementedError("universal_html not support xpath")


@converter.pre(TokenType.EXPR_XPATH_ALL)
def tt_xpath_all(_: HtmlXpathAllExpression) -> str:
    raise NotImplementedError("universal_html not support xpath")


@converter.pre(TokenType.EXPR_TEXT)
def tt_text(node: HtmlTextExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    return f"var {nxt} = {prv}.text;"


@converter.pre(TokenType.EXPR_TEXT_ALL)
def tt_text_all(node: HtmlTextAllExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    return f"var {nxt} = {prv}.map((e) => e.text).toList();"


@converter.pre(TokenType.EXPR_RAW)
def tt_raw(node: HtmlRawExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    return f"var {nxt} = {prv}.innerHtml;"


@converter.pre(TokenType.EXPR_RAW_ALL)
def tt_raw_all(node: HtmlRawAllExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    return f"var {nxt} = {prv}.map((e) => e.innerHtml).toList();"


@converter.pre(TokenType.EXPR_ATTR)
def tt_attr(node: HtmlAttrExpression):
    n = node.attr
    prv, nxt = left_right_var_names("value", node.variable)
    return f"var {nxt} = {prv}.attributes[{n!r}];"


@converter.pre(TokenType.EXPR_ATTR_ALL)
def tt_attr_all(node: HtmlAttrAllExpression):
    n = node.attr
    prv, nxt = left_right_var_names("value", node.variable)
    return f"var {nxt} = {prv}.map((e) => e.attributes[{n!r}]).toList();"


@converter.pre(TokenType.IS_CSS)
def tt_is_css(node: IsCssExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    code = f"assert({prv}.querySelector({node.query!r}), {node.msg!r});"
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += f"\nvar {nxt} = {prv};"
    return code


@converter.pre(TokenType.IS_XPATH)
def tt_is_xpath(_: IsXPathExpression):
    raise NotImplementedError("dart universal_html not support xpath")
