from .base import BaseCodeConverter, left_right_var_names
from .utils import to_upper_camel_case, wrap_backtick
from ..ast_ssc import (
    StructParser,
    PreValidateFunction,
    StructFieldFunction,
    Docstring,
    StartParseFunction,
    DefaultValueWrapper,
    PartDocFunction,
    HtmlCssExpression,
    HtmlCssAllExpression,
    HtmlAttrExpression,
    HtmlAttrAllExpression,
    HtmlTextExpression,
    HtmlTextAllExpression,
    HtmlRawExpression,
    HtmlRawAllExpression,
    HtmlXpathExpression,
    HtmlXpathAllExpression,
    FormatExpression,
    MapFormatExpression,
    TrimExpression,
    MapTrimExpression,
    LTrimExpression,
    MapLTrimExpression,
    RTrimExpression,
    MapRTrimExpression,
    ReplaceExpression,
    MapReplaceExpression,
    SplitExpression,
    NestedExpression,
    RegexExpression,
    RegexSubExpression,
    MapRegexSubExpression,
    RegexAllExpression,
    ReturnExpression,
    NoReturnExpression,
    IndexDocumentExpression,
    IndexStringExpression,
    JoinExpression,
    IsCssExpression,
    IsXPathExpression,
    IsEqualExpression,
    IsContainsExpression,
    IsRegexMatchExpression,
    IsNotEqualExpression,
)
from ..tokens import TokenType, StructType, VariableType
from .templates import js

converter = BaseCodeConverter()

TYPES = {
    VariableType.STRING: "str",
    VariableType.LIST_STRING: "List[str]",
    VariableType.OPTIONAL_STRING: "Optional[str]",
    VariableType.OPTIONAL_LIST_STRING: "Optional[List[str]]",
}

MAGIC_METHODS = {
    "__KEY__": "key",
    "__VALUE__": "value",
    "__ITEM__": "item",
    "__PRE_VALIDATE__": "_preValidate",
    "__SPLIT_DOC__": "_splitDoc",
    "__START_PARSE__": "parse",
}


# pure js API
@converter.pre(TokenType.STRUCT)
def tt_struct(node: StructParser) -> str:
    return js.CLS_HEAD.format(node.name) + js.BRACKET_START


@converter.post(TokenType.STRUCT)
def tt_struct(_: StructParser) -> str:
    return js.BRACKET_END


@converter.pre(TokenType.STRUCT_INIT)
def tt_init(_) -> str:
    return js.CLS_CONSTRUCTOR


@converter.pre(TokenType.DOCSTRING)
def tt_docstring(node: Docstring) -> str:
    if node.value:
        return js.DOCSTRING(node.value)
    return ""


@converter.pre(TokenType.EXPR_RETURN)
def tt_ret(node: ReturnExpression) -> str:
    _, nxt = left_right_var_names("value", node.variable)
    return js.RET.format(nxt)


@converter.pre(TokenType.EXPR_NO_RETURN)
def tt_no_ret(_: NoReturnExpression) -> str:
    return js.NO_RET


@converter.pre(TokenType.EXPR_NESTED)
def tt_nested(node: NestedExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    return js.EXPR_NESTED.format(nxt, node.schema, prv)


@converter.pre(TokenType.STRUCT_PRE_VALIDATE)
def tt_pre_validate(node: PreValidateFunction) -> str:
    name = js.MAGIC_METHODS.get(node.name)
    return js.FUNC_HEAD.format(name) + js.BRACKET_START


@converter.post(TokenType.STRUCT_PRE_VALIDATE)
def tt_pre_validate(_: PreValidateFunction) -> str:
    return js.BRACKET_END


@converter.pre(TokenType.STRUCT_PART_DOCUMENT)
def tt_part_document(node: PartDocFunction):
    name = js.MAGIC_METHODS.get(node.name)
    return js.FUNC_HEAD.format(name) + js.BRACKET_START


@converter.post(TokenType.STRUCT_PART_DOCUMENT)
def tt_part_document(_: PartDocFunction) -> str:
    return js.BRACKET_END


@converter.pre(TokenType.STRUCT_FIELD)
def tt_function(node: StructFieldFunction) -> str:
    name = MAGIC_METHODS.get(node.name, node.name)
    name = to_upper_camel_case(name)
    return js.FUNC_PARSE_HEAD.format(name) + js.BRACKET_START


@converter.post(TokenType.STRUCT_FIELD)
def tt_function(_: StructFieldFunction) -> str:
    return js.BRACKET_END


@converter.pre(TokenType.STRUCT_PARSE_START)
def tt_start_parse(node: StartParseFunction) -> str:
    name = MAGIC_METHODS.get(node.name)
    return js.FUNC_PARSE_START_HEAD.format(name) + js.BRACKET_START


@converter.post(TokenType.STRUCT_PARSE_START)
def tt_start_parse(node: StartParseFunction):
    code = ""
    if any(f.name == "__PRE_VALIDATE__" for f in node.body):
        n = MAGIC_METHODS.get("__PRE_VALIDATE__")
        code += js.PRE_VALIDATE_CALL.format(n)

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


@converter.pre(TokenType.EXPR_DEFAULT)
def tt_default(_: DefaultValueWrapper) -> str:
    return js.DEFAULT_HEAD


@converter.post(TokenType.EXPR_DEFAULT)
def tt_default(node: DefaultValueWrapper) -> str:
    val = repr(node.value) if isinstance(node.value, str) else "null"
    return js.DEFAULT_FOOTER(val)


@converter.pre(TokenType.EXPR_STRING_FORMAT)
def tt_string_format(node: FormatExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    template = node.fmt.replace("{{}}", "${" + prv + "}")
    return js.EXPR_STR_FMT(nxt, wrap_backtick(template))


@converter.pre(TokenType.EXPR_LIST_STRING_FORMAT)
def tt_string_format_all(node: MapFormatExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    template = node.fmt.replace("{{}}", "${e}")
    return js.EXPR_STR_FMT_ALL.format(nxt, prv, wrap_backtick(template))


@converter.pre(TokenType.EXPR_STRING_TRIM)
def tt_string_trim(node: TrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = node.value
    return js.EXPR_STR_TRIM(nxt, prv, chars)


@converter.pre(TokenType.EXPR_LIST_STRING_TRIM)
def tt_string_trim_all(node: MapTrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = node.value
    return js.EXPR_STR_TRIM_ALL(nxt, prv, chars)


@converter.pre(TokenType.EXPR_STRING_LTRIM)
def tt_string_ltrim(node: LTrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = node.value
    return js.EXPR_STR_LTRIM(nxt, prv, chars)


@converter.pre(TokenType.EXPR_LIST_STRING_LTRIM)
def tt_string_ltrim_all(node: MapLTrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = node.value
    return js.EXPR_STR_LTRIM_ALL(nxt, prv, chars)


@converter.pre(TokenType.EXPR_STRING_RTRIM)
def tt_string_rtrim(node: RTrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = node.value
    return js.EXPR_STR_RTRIM(nxt, prv, chars)


@converter.pre(TokenType.EXPR_LIST_STRING_RTRIM)
def tt_string_rtrim_all(node: MapRTrimExpression) -> str:
    # const rtrim = function (str, chars) {
    #     return str.replace(new RegExp(`[${chars}]+$`, 'g'), '');
    # };
    #
    prv, nxt = left_right_var_names("value", node.variable)
    chars = node.value
    return js.EXPR_STR_RTRIM_ALL(nxt, prv, chars)


@converter.pre(TokenType.EXPR_STRING_REPLACE)
def tt_string_replace(node: ReplaceExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    old, new = repr(node.old), repr(node.new)
    return js.EXPR_STR_REPL.format(nxt, prv, old, new)


@converter.pre(TokenType.EXPR_LIST_STRING_REPLACE)
def tt_string_replace_all(node: MapReplaceExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    old, new = repr(node.old), repr(node.new)
    return js.EXPR_STR_REPL_ALL.format(nxt, prv, old, new)


@converter.pre(TokenType.EXPR_STRING_SPLIT)
def tt_string_split(node: SplitExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    sep = repr(node.sep)
    return js.EXPR_STR_SPLIT.format(nxt, prv, sep)


@converter.pre(TokenType.EXPR_REGEX)
def tt_regex(node: RegexExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    pattern = "/" + node.pattern + "/g"
    group = node.group - 1
    return js.EXPR_RE.format(nxt, prv, pattern, group)


@converter.pre(TokenType.EXPR_REGEX_ALL)
def tt_regex_all(node: RegexAllExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    pattern = "/" + node.pattern + "/g"
    return js.EXPR_RE_ALL.format(nxt, prv, pattern)


@converter.pre(TokenType.EXPR_REGEX_SUB)
def tt_regex_sub(node: RegexSubExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    pattern = "/" + node.pattern + "/g"
    repl = repr(node.repl)
    return js.EXPR_RE_SUB.format(nxt, prv, pattern, repl)


@converter.pre(TokenType.EXPR_LIST_REGEX_SUB)
def tt_regex_sub_all(node: MapRegexSubExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    pattern = "/" + node.pattern + "/g"
    repl = repr(node.repl)
    return js.EXPR_RE_SUB_ALL.format(nxt, prv, pattern, repl)


@converter.pre(TokenType.EXPR_LIST_STRING_INDEX)
def tt_string_index(node: IndexStringExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    return js.EXPR_INDEX.format(nxt, prv, node.value)


@converter.pre(TokenType.EXPR_LIST_DOCUMENT_INDEX)
def tt_doc_index(node: IndexDocumentExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    return js.EXPR_INDEX.format(nxt, prv, node.value)


@converter.pre(TokenType.EXPR_LIST_JOIN)
def tt_join(node: JoinExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    sep = repr(node.sep)
    return js.EXPR_JOIN.format(nxt, prv, sep)


@converter.pre(TokenType.IS_EQUAL)
def tt_is_equal(node: IsEqualExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    code = js.E_EQ.format(prv, repr(node.value), repr(node.msg))
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += js.EXPR_ASSIGN.format(nxt, prv)
    return code


@converter.pre(TokenType.IS_NOT_EQUAL)
def tt_is_not_equal(node: IsNotEqualExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    code = js.E_NE.format(prv, repr(node.value), repr(node.msg))
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += js.EXPR_ASSIGN.format(nxt, prv)
    return code


@converter.pre(TokenType.IS_CONTAINS)
def tt_is_contains(node: IsContainsExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    code = js.E_IN.format(repr(node.item), prv, repr(node.msg))
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += js.EXPR_ASSIGN.format(nxt, prv)
    return code


@converter.pre(TokenType.IS_REGEX_MATCH)
def tt_is_regex(node: IsRegexMatchExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    pattern = "/" + node.pattern + "/"
    code = js.E_IS_RE.format(prv, pattern, repr(node.msg))
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += js.EXPR_ASSIGN.format(nxt, prv)
    return code


# js pure API
@converter.pre(TokenType.EXPR_CSS)
def tt_css(node: HtmlCssExpression) -> str:
    q = repr(node.query)
    prv, nxt = left_right_var_names("value", node.variable)
    return js.EXPR_CSS.format(nxt, prv, q)


@converter.pre(TokenType.EXPR_CSS_ALL)
def tt_css_all(node: HtmlCssAllExpression) -> str:
    q = repr(node.query)
    prv, nxt = left_right_var_names("value", node.variable)
    return js.EXPR_CSS_ALL.format(nxt, prv, q)


@converter.pre(TokenType.EXPR_XPATH)
def tt_xpath(node: HtmlXpathExpression) -> str:
    q = repr(node.query)
    prv, nxt = left_right_var_names("value", node.variable)
    return js.EXPR_XPATH.format(nxt, q, prv)


@converter.pre(TokenType.EXPR_XPATH_ALL)
def tt_xpath_all(node: HtmlXpathAllExpression) -> str:
    q = node.query
    prv, nxt = left_right_var_names("value", node.variable)
    return js.EXPR_XPATH_ALL(nxt, prv, q)


@converter.pre(TokenType.EXPR_TEXT)
def tt_text(node: HtmlTextExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    # document object (naive)
    if node.variable.num == 0:
        return js.EXPR_DOC_TEXT.format(nxt, prv)
    return js.EXPR_TEXT.format(nxt, prv)


@converter.pre(TokenType.EXPR_TEXT_ALL)
def tt_text_all(node: HtmlTextAllExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    return js.EXPR_TEXT_ALL.format(nxt, prv)


@converter.pre(TokenType.EXPR_RAW)
def tt_raw(node: HtmlRawExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    # document object (naive)
    if node.variable.num == 0:
        return js.EXPR_DOC_RAW.format(nxt, prv)
    return js.EXPR_RAW.format(nxt, prv)


@converter.pre(TokenType.EXPR_RAW_ALL)
def tt_raw_all(node: HtmlRawAllExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    return js.EXPR_RAW_ALL.format(nxt, prv)


@converter.pre(TokenType.EXPR_ATTR)
def tt_attr(node: HtmlAttrExpression):
    attr = repr(node.attr)
    prv, nxt = left_right_var_names("value", node.variable)
    return js.EXPR_ATTR.format(nxt, prv, attr)


@converter.pre(TokenType.EXPR_ATTR_ALL)
def tt_attr_all(node: HtmlAttrAllExpression):
    attr = repr(node.attr)
    prv, nxt = left_right_var_names("value", node.variable)
    return js.EXPR_ATTR_ALL.format(nxt, prv, attr)


@converter.pre(TokenType.IS_CSS)
def tt_is_css(node: IsCssExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    code = js.E_IS_CSS.format(prv, repr(node.query), repr(node.msg))
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += js.EXPR_ASSIGN.format(nxt, prv)
    return code


@converter.pre(TokenType.IS_XPATH)
def tt_is_xpath(node: IsXPathExpression):
    #   const result = document.evaluate(xpath, context || document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
    #     const node = result.singleNodeValue;
    prv, nxt = left_right_var_names("value", node.variable)
    code = js.E_IS_XPATH.format(repr(node.query), prv, repr(node.msg))
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += js.EXPR_ASSIGN.format(nxt, prv)
    return code
