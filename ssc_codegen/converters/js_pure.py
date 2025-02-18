from ssc_codegen.ast_ssc import (
    DefaultEnd,
    DefaultStart,
    Docstring,
    FormatExpression,
    HtmlAttrAllExpression,
    HtmlAttrExpression,
    HtmlCssAllExpression,
    HtmlCssExpression,
    HtmlRawAllExpression,
    HtmlRawExpression,
    HtmlTextAllExpression,
    HtmlTextExpression,
    HtmlXpathAllExpression,
    HtmlXpathExpression,
    IndexDocumentExpression,
    IndexStringExpression,
    IsContainsExpression,
    IsCssExpression,
    IsEqualExpression,
    IsNotEqualExpression,
    IsRegexMatchExpression,
    IsXPathExpression,
    JoinExpression,
    LTrimExpression,
    MapFormatExpression,
    MapLTrimExpression,
    MapRegexSubExpression,
    MapReplaceExpression,
    MapRTrimExpression,
    MapTrimExpression,
    NestedExpression,
    NoReturnExpression,
    PartDocFunction,
    PreValidateFunction,
    RegexAllExpression,
    RegexExpression,
    RegexSubExpression,
    ReplaceExpression,
    ReturnExpression,
    RTrimExpression,
    SplitExpression,
    StartParseFunction,
    StructFieldFunction,
    StructInit,
    StructParser,
    TrimExpression,
    ToInteger,
    ToListInteger,
    ToFloat,
    ToListFloat,
    ToJson,
)
from ssc_codegen.tokens import StructType, TokenType
from .base import BaseCodeConverter, left_right_var_names
from .templates import js
from ssc_codegen.str_utils import to_upper_camel_case, wrap_backtick

converter = BaseCodeConverter()


# pure js API
@converter.pre(TokenType.STRUCT)
def tt_struct(node: StructParser) -> str:
    return js.BINDINGS[node.kind, node.name] + js.BRACKET_START


@converter.post(TokenType.STRUCT)
def tt_struct_post(_: StructParser) -> str:
    return js.BRACKET_END


@converter.pre(TokenType.STRUCT_INIT)
def tt_init(node: StructInit) -> str:
    return js.BINDINGS[node.kind]


@converter.pre(TokenType.DOCSTRING)
def tt_docstring(node: Docstring) -> str:
    return js.BINDINGS[node.kind, node.value]


@converter.pre(TokenType.EXPR_RETURN)
def tt_ret(node: ReturnExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    if node.have_default_expr():
        return js.BINDINGS[node.kind, prv]
    return js.BINDINGS[node.kind, nxt]


@converter.pre(TokenType.EXPR_NO_RETURN)
def tt_no_ret(node: NoReturnExpression) -> str:
    return js.BINDINGS[node.kind]


@converter.pre(TokenType.EXPR_NESTED)
def tt_nested(node: NestedExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    return js.BINDINGS[node.kind, nxt, node.schema, prv]


@converter.pre(TokenType.STRUCT_PRE_VALIDATE)
def tt_pre_validate(node: PreValidateFunction) -> str:
    name = js.MAGIC_METHODS.get(node.name)
    return js.BINDINGS[node.kind, name] + js.BRACKET_START


@converter.post(TokenType.STRUCT_PRE_VALIDATE)
def tt_pre_validate_post(_: PreValidateFunction) -> str:
    return js.BRACKET_END


@converter.pre(TokenType.STRUCT_PART_DOCUMENT)
def tt_part_document(node: PartDocFunction) -> str:
    name = js.MAGIC_METHODS.get(node.name)
    return js.BINDINGS[node.kind, name] + js.BRACKET_START


@converter.post(TokenType.STRUCT_PART_DOCUMENT)
def tt_part_document_post(_: PartDocFunction) -> str:
    return js.BRACKET_END


@converter.pre(TokenType.STRUCT_FIELD)
def tt_function(node: StructFieldFunction) -> str:
    name = js.MAGIC_METHODS.get(node.name, node.name)
    name = to_upper_camel_case(name)
    return js.BINDINGS[node.kind, name] + js.BRACKET_START


@converter.post(TokenType.STRUCT_FIELD)
def tt_function_post(_: StructFieldFunction) -> str:
    return js.BRACKET_END


@converter.pre(TokenType.STRUCT_PARSE_START)
def tt_start_parse(node: StartParseFunction) -> str:
    name = js.MAGIC_METHODS.get(node.name)
    return js.BINDINGS[node.kind, name] + js.BRACKET_START


@converter.post(TokenType.STRUCT_PARSE_START)
def tt_start_parse_post(node: StartParseFunction) -> str:
    code = ""
    if any(f.name == "__PRE_VALIDATE__" for f in node.body):
        name = js.MAGIC_METHODS.get("__PRE_VALIDATE__")
        # TODO: token for call
        code += f"this.{name}(this._doc);"
    match node.type:
        case StructType.ITEM:
            body = js.gen_item_body(node)
        case StructType.LIST:
            body = js.gen_list_body(node)
        case StructType.DICT:
            body = js.gen_dict_body(node)
        case StructType.FLAT_LIST:
            body = js.gen_flat_list_body(node)
        case _:
            raise NotImplementedError("Unknown struct type")
    return code + body + js.BRACKET_END


@converter.pre(TokenType.EXPR_DEFAULT_START)
def tt_default_start(node: DefaultStart) -> str:
    return js.BINDINGS[node.kind] + "let value1 = value;"


@converter.pre(TokenType.EXPR_DEFAULT_END)
def tt_default_end(node: DefaultEnd) -> str:
    if node.value is None:
        val = "null"
    elif isinstance(node.value, str):
        val = repr(node.value)
    else:
        val = node.value
    # TODO: default list types
    return js.BINDINGS[node.kind, val]


@converter.pre(TokenType.EXPR_STRING_FORMAT)
def tt_string_format(node: FormatExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    template = node.fmt.replace("{{}}", "${" + prv + "}")
    template = wrap_backtick(template)
    return js.BINDINGS[node.kind, nxt, template]


@converter.pre(TokenType.EXPR_LIST_STRING_FORMAT)
def tt_string_format_all(node: MapFormatExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    template = node.fmt.replace("{{}}", "${e}")
    template = wrap_backtick(template)
    return js.BINDINGS[node.kind, nxt, prv, template]


@converter.pre(TokenType.EXPR_STRING_TRIM)
def tt_string_trim(node: TrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = node.value
    return js.BINDINGS[node.kind, nxt, prv, chars]


@converter.pre(TokenType.EXPR_LIST_STRING_TRIM)
def tt_string_trim_all(node: MapTrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = node.value
    return js.BINDINGS[node.kind, nxt, prv, chars]


@converter.pre(TokenType.EXPR_STRING_LTRIM)
def tt_string_ltrim(node: LTrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = node.value
    return js.BINDINGS[node.kind, nxt, prv, chars]


@converter.pre(TokenType.EXPR_LIST_STRING_LTRIM)
def tt_string_ltrim_all(node: MapLTrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = node.value
    return js.BINDINGS[node.kind, nxt, prv, chars]


@converter.pre(TokenType.EXPR_STRING_RTRIM)
def tt_string_rtrim(node: RTrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = node.value
    return js.BINDINGS[node.kind, nxt, prv, chars]


@converter.pre(TokenType.EXPR_LIST_STRING_RTRIM)
def tt_string_rtrim_all(node: MapRTrimExpression) -> str:
    # const rtrim = function (str, chars) {
    #     return str.replace(new RegExp(`[${chars}]+$`, 'g'), '');
    # };
    #
    prv, nxt = left_right_var_names("value", node.variable)
    chars = node.value
    return js.BINDINGS[node.kind, nxt, prv, chars]


@converter.pre(TokenType.EXPR_STRING_REPLACE)
def tt_string_replace(node: ReplaceExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    old, new = repr(node.old), repr(node.new)
    return js.BINDINGS[node.kind, nxt, prv, old, new]


@converter.pre(TokenType.EXPR_LIST_STRING_REPLACE)
def tt_string_replace_all(node: MapReplaceExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    old, new = repr(node.old), repr(node.new)
    return js.BINDINGS[node.kind, nxt, prv, old, new]


@converter.pre(TokenType.EXPR_STRING_SPLIT)
def tt_string_split(node: SplitExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    sep = repr(node.sep)
    return js.BINDINGS[node.kind, nxt, prv, sep]


@converter.pre(TokenType.EXPR_REGEX)
def tt_regex(node: RegexExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    pattern = f"/{node.pattern}/g"
    group = node.group
    return js.BINDINGS[node.kind, nxt, pattern, prv, group]


@converter.pre(TokenType.EXPR_REGEX_ALL)
def tt_regex_all(node: RegexAllExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    pattern = f"/{node.pattern}/g"
    return js.BINDINGS[node.kind, nxt, pattern, prv]


@converter.pre(TokenType.EXPR_REGEX_SUB)
def tt_regex_sub(node: RegexSubExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    pattern = f"/{node.pattern}/g"
    repl = repr(node.repl)
    return js.BINDINGS[node.kind, nxt, prv, pattern, repl]


@converter.pre(TokenType.EXPR_LIST_REGEX_SUB)
def tt_regex_sub_all(node: MapRegexSubExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    pattern = f"/{node.pattern}/g"
    repl = repr(node.repl)
    return js.BINDINGS[node.kind, nxt, prv, pattern, repl]


@converter.pre(TokenType.EXPR_LIST_STRING_INDEX)
def tt_string_index(node: IndexStringExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    return js.BINDINGS[node.kind, nxt, prv, node.value]


@converter.pre(TokenType.EXPR_LIST_DOCUMENT_INDEX)
def tt_doc_index(node: IndexDocumentExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    return js.BINDINGS[node.kind, nxt, prv, node.value]


@converter.pre(TokenType.EXPR_LIST_JOIN)
def tt_join(node: JoinExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    sep = repr(node.sep)
    return js.BINDINGS[node.kind, nxt, prv, sep]


@converter.pre(TokenType.IS_EQUAL)
def tt_is_equal(node: IsEqualExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    value = repr(node.value) if isinstance(node.value, str) else node.value
    code = js.BINDINGS[node.kind, prv, value, repr(node.msg)]
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += js.EXPR_ASSIGN.format(nxt, prv)
    return code


@converter.pre(TokenType.IS_NOT_EQUAL)
def tt_is_not_equal(node: IsNotEqualExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    value = repr(node.value) if isinstance(node.value, str) else node.value
    code = js.BINDINGS[node.kind, prv, value, repr(node.msg)]
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += js.EXPR_ASSIGN.format(nxt, prv)
    return code


@converter.pre(TokenType.IS_CONTAINS)
def tt_is_contains(node: IsContainsExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    item = repr(node.item) if isinstance(node.item, str) else node.value
    code = js.BINDINGS[node.kind, item, prv, repr(node.msg)]
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += js.EXPR_ASSIGN.format(nxt, prv)
    return code


@converter.pre(TokenType.IS_REGEX_MATCH)
def tt_is_regex(node: IsRegexMatchExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    pattern = f"/{node.pattern}/"
    code = js.BINDINGS[node.kind, prv, pattern, repr(node.msg)]
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += js.EXPR_ASSIGN.format(nxt, prv)
    return code


# js pure API
@converter.pre(TokenType.EXPR_CSS)
def tt_css(node: HtmlCssExpression) -> str:
    q = repr(node.query)
    prv, nxt = left_right_var_names("value", node.variable)
    return js.BINDINGS[node.kind, nxt, prv, q]


@converter.pre(TokenType.EXPR_CSS_ALL)
def tt_css_all(node: HtmlCssAllExpression) -> str:
    q = repr(node.query)
    prv, nxt = left_right_var_names("value", node.variable)
    return js.BINDINGS[node.kind, nxt, prv, q]


@converter.pre(TokenType.EXPR_XPATH)
def tt_xpath(node: HtmlXpathExpression) -> str:
    q = repr(node.query)
    prv, nxt = left_right_var_names("value", node.variable)
    return js.BINDINGS[node.kind, nxt, q, prv]


@converter.pre(TokenType.EXPR_XPATH_ALL)
def tt_xpath_all(node: HtmlXpathAllExpression) -> str:
    q = node.query
    prv, nxt = left_right_var_names("value", node.variable)
    return js.BINDINGS[node.kind, nxt, prv, q]


@converter.pre(TokenType.EXPR_TEXT)
def tt_text(node: HtmlTextExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    # document object (naive)
    return js.BINDINGS[node.kind, node.variable.num, nxt, prv]


@converter.pre(TokenType.EXPR_TEXT_ALL)
def tt_text_all(node: HtmlTextAllExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    return js.BINDINGS[node.kind, nxt, prv]


@converter.pre(TokenType.EXPR_RAW)
def tt_raw(node: HtmlRawExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    # document object (naive)
    return js.BINDINGS[node.kind, node.variable.num, nxt, prv]


@converter.pre(TokenType.EXPR_RAW_ALL)
def tt_raw_all(node: HtmlRawAllExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    return js.BINDINGS[node.kind, nxt, prv]


@converter.pre(TokenType.EXPR_ATTR)
def tt_attr(node: HtmlAttrExpression) -> str:
    attr = repr(node.attr)
    prv, nxt = left_right_var_names("value", node.variable)
    return js.BINDINGS[node.kind, nxt, prv, attr]


@converter.pre(TokenType.EXPR_ATTR_ALL)
def tt_attr_all(node: HtmlAttrAllExpression) -> str:
    attr = repr(node.attr)
    prv, nxt = left_right_var_names("value", node.variable)
    return js.BINDINGS[node.kind, nxt, prv, attr]


@converter.pre(TokenType.IS_CSS)
def tt_is_css(node: IsCssExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    code = js.BINDINGS[node.kind, prv, repr(node.query), repr(node.msg)]
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += js.EXPR_ASSIGN.format(nxt, prv)
    return code


@converter.pre(TokenType.IS_XPATH)
def tt_is_xpath(node: IsXPathExpression) -> str:
    #   const result = document.evaluate(xpath, context || document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
    #     const node = result.singleNodeValue;
    prv, nxt = left_right_var_names("value", node.variable)
    code = js.BINDINGS[node.kind, repr(node.query), prv, repr(node.msg)]
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += js.EXPR_ASSIGN.format(nxt, prv)
    return code


@converter.pre(TokenType.TO_INT)
def tt_to_int(node: ToInteger) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    return f"let {nxt} = parseInt({prv}, 10); "


@converter.pre(TokenType.TO_INT_LIST)
def tt_to_list_int(node: ToListInteger) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    return f"let {nxt} = {prv}.map(i => parseInt(i, 10)); "


@converter.pre(TokenType.TO_FLOAT)
def tt_to_float(node: ToFloat) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    return f"let {nxt} = parseFloat({prv}, 64); "


@converter.pre(TokenType.TO_FLOAT_LIST)
def tt_to_list_float(node: ToListFloat) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    return f"let {nxt} = {prv}.map(i => parseFloat(i, 64)); "


@converter.pre(TokenType.TO_JSON)
def tt_to_json(node: ToJson) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    return f"let {nxt} = JSON.parse({prv}); "
