# TODO: required enchant, not tested
from functools import partial

from templates import dart
from .base import BaseCodeConverter, left_right_var_names
from .utils import (
    to_upper_camel_case as up_camel,
    escape_str,
    wrap_double_quotes as wrap_q,
)
from ..ast_ssc import (
    StructParser,
    ModuleImports,
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
    TypeDef,
    IndexDocumentExpression,
    IndexStringExpression,
    JoinExpression,
    IsCssExpression,
    IsXPathExpression,
    IsEqualExpression,
    IsContainsExpression,
    IsRegexMatchExpression,
    IsNotEqualExpression,
    StructInit,
)
from ..tokens import TokenType, StructType

converter = BaseCodeConverter()

lr_var_names = partial(left_right_var_names, name="value")

TYPES = dart.TYPES
MAGIC_METHODS = dart.MAGIC_METHODS


@converter.pre(TokenType.TYPEDEF)
def tt_typedef(node: TypeDef):
    # used records from dart 3
    code = ""
    match node.struct_ref.type:
        case StructType.DICT:
            # Map<String, T>
            code = dart.typedef_dict(node)
        case StructType.FLAT_LIST:
            # List<T>
            code = dart.typedef_flat_list(node)
        case StructType.ITEM:
            # record
            code = dart.typedef_item_record(node)
        case StructType.LIST:
            # record
            code = dart.typedef_list_record(node)
        case _:
            raise TypeError("Unknown struct type")
    return code


# dart API
@converter.pre(TokenType.STRUCT)
def tt_struct(node: StructParser) -> str:
    return dart.CLS_HEAD.format(node.name) + " " + dart.START_BRACKET


@converter.post(TokenType.STRUCT)
def tt_struct(_: StructParser) -> str:
    return dart.END_BRACKET


@converter.pre(TokenType.STRUCT_INIT)
def tt_init(node: StructInit) -> str:
    return dart.CLS_INIT(node.name)


@converter.pre(TokenType.DOCSTRING)
def tt_docstring(node: Docstring) -> str:
    if node.value:
        return dart.CLS_DOCSTRING(node.value)
    return ""


@converter.pre(TokenType.IMPORTS)
def tt_imports(_: ModuleImports) -> str:
    return dart.BASE_IMPORTS


@converter.pre(TokenType.EXPR_RETURN)
def tt_ret(node: ReturnExpression) -> str:
    _, nxt = lr_var_names(variable=node.variable)
    return dart.RET.format(nxt)


@converter.pre(TokenType.EXPR_NO_RETURN)
def tt_no_ret(_: NoReturnExpression) -> str:
    return dart.NO_RET


@converter.pre(TokenType.EXPR_NESTED)
def tt_nested(node: NestedExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    # first element as document type (naive)
    if node.variable.num == 0:
        return dart.NESTED_FROM_DOC(nxt, node.schema, prv)
    return dart.NESTED_FROM_ELEMENT(nxt, node.schema, prv)


@converter.pre(TokenType.STRUCT_PRE_VALIDATE)
def tt_pre_validate(node: PreValidateFunction) -> str:
    name = MAGIC_METHODS.get(node.name)
    return dart.PRE_VALIDATE_HEAD.format(name) + " " + dart.START_BRACKET


@converter.post(TokenType.STRUCT_PRE_VALIDATE)
def tt_pre_validate(_: PreValidateFunction) -> str:
    return dart.END_BRACKET


@converter.pre(TokenType.STRUCT_PART_DOCUMENT)
def tt_part_document(node: PartDocFunction):
    name = MAGIC_METHODS.get(node.name)
    return dart.PART_DOC_HEAD.format(name) + " " + dart.START_BRACKET


@converter.post(TokenType.STRUCT_PART_DOCUMENT)
def tt_part_document(_: PartDocFunction):
    return dart.END_BRACKET


@converter.pre(TokenType.STRUCT_FIELD)
def tt_function(node: StructFieldFunction) -> str:
    name = MAGIC_METHODS.get(node.name, node.name)
    if name == node.name:
        name = up_camel(node.name)
    return dart.FN_PARSE.format(name, "value") + " " + dart.START_BRACKET


@converter.post(TokenType.STRUCT_FIELD)
def tt_function(_: StructFieldFunction) -> str:
    return dart.END_BRACKET


@converter.pre(TokenType.STRUCT_PARSE_START)
def tt_start_parse(node: StartParseFunction) -> str:
    ret_t = dart.TYPE_PREFIX.format(node.parent.name)
    name = MAGIC_METHODS.get(node.name)
    code = dart.FN_PARSE_START.format(ret_t, name) + " " + dart.START_BRACKET
    if any(f.name == "__PRE_VALIDATE__" for f in node.body):
        pre_val = MAGIC_METHODS.get("__PRE_VALIDATE__")
        code += dart.FN_PRE_VALIDATE.format(pre_val)
    match node.type:
        case StructType.ITEM:
            body = dart.parse_item_code(node)
            return code + body
        case StructType.LIST:
            body = dart.parse_list_code(node)
            return code + body
        case StructType.DICT:
            body = dart.parse_dict_code(node)
            return code + body
        case StructType.FLAT_LIST:
            body = dart.parse_flat_list_code(node)
            return code + body
        case _:
            raise NotImplementedError("Unknown struct type")


@converter.post(TokenType.STRUCT_PARSE_START)
def tt_start_parse(_: StartParseFunction) -> str:
    return dart.END_BRACKET


@converter.pre(TokenType.EXPR_DEFAULT)
def tt_default(_: DefaultValueWrapper) -> str:
    return dart.E_DEFAULT_START


@converter.post(TokenType.EXPR_DEFAULT)
def tt_default(node: DefaultValueWrapper) -> str:
    val = repr(node.value) if isinstance(node.value, str) else "null"
    return dart.E_DEFAULT_END(val)


@converter.pre(TokenType.EXPR_STRING_FORMAT)
def tt_string_format(node: FormatExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    template = dart.fmt_template(node.fmt, prv)
    return dart.E_STR_FMT.format(nxt, repr(template))


@converter.pre(TokenType.EXPR_LIST_STRING_FORMAT)
def tt_string_format_all(node: MapFormatExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    template = dart.fmt_template(node.fmt, "e")
    return dart.E_STR_FMT_ALL.format(nxt, prv, repr(template))


@converter.pre(TokenType.EXPR_STRING_TRIM)
def tt_string_trim(node: TrimExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    chars = node.value
    left = wrap_q("^" + escape_str(chars))
    right = wrap_q(escape_str(chars + "$"))
    return dart.E_STR_TRIM(nxt, prv, left, right)


@converter.pre(TokenType.EXPR_LIST_STRING_TRIM)
def tt_string_trim_all(node: MapTrimExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    chars = node.value
    left = wrap_q("^" + escape_str(chars))
    right = wrap_q(escape_str(chars + "$"))
    return dart.E_STR_TRIM_ALL.format(nxt, prv, left, right)


@converter.pre(TokenType.EXPR_STRING_LTRIM)
def tt_string_ltrim(node: LTrimExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    chars = node.value
    left = wrap_q("^" + escape_str(chars))
    return dart.E_STR_LTRIM.format(nxt, prv, left)


@converter.pre(TokenType.EXPR_LIST_STRING_LTRIM)
def tt_string_ltrim_all(node: MapLTrimExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    chars = node.value
    left = wrap_q("^" + escape_str(chars))
    return dart.E_STR_LTRIM_ALL.format(nxt, prv, left)


@converter.pre(TokenType.EXPR_STRING_RTRIM)
def tt_string_rtrim(node: RTrimExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    chars = node.value
    right = wrap_q(escape_str(chars + "$"))
    return dart.E_STR_RTRIM.format(nxt, prv, right)


@converter.pre(TokenType.EXPR_LIST_STRING_RTRIM)
def tt_string_rtrim_all(node: MapRTrimExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    chars = node.value
    right = wrap_q(escape_str(chars + "$"))
    return dart.E_STR_RTRIM_ALL.format(nxt, prv, right)


@converter.pre(TokenType.EXPR_STRING_REPLACE)
def tt_string_replace(node: ReplaceExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    old, new = repr(node.old), repr(node.new)
    return dart.E_STR_REPL(nxt, prv, old, new)


@converter.pre(TokenType.EXPR_LIST_STRING_REPLACE)
def tt_string_replace_all(node: MapReplaceExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    old, new = repr(node.old), repr(node.new)
    return dart.E_STR_REPL_ALL.format(nxt, prv, old, new)


@converter.pre(TokenType.EXPR_STRING_SPLIT)
def tt_string_split(node: SplitExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    sep = repr(node.sep)
    return dart.E_STR_SPLIT.format(nxt, prv, sep)


@converter.pre(TokenType.EXPR_REGEX)
def tt_regex(node: RegexExpression):
    prv, nxt = lr_var_names(variable=node.variable)
    pattern = repr(node.pattern)
    group = node.group
    return dart.E_RE.format(nxt, pattern, prv, group)


@converter.pre(TokenType.EXPR_REGEX_ALL)
def tt_regex_all(node: RegexAllExpression):
    prv, nxt = lr_var_names(variable=node.variable)
    pattern = repr(node.pattern)
    # RegExp(pattern).allMatches(s).map((e) => e.group(group)!).toList();
    return dart.E_RE_ALL.format(nxt, pattern, prv)


@converter.pre(TokenType.EXPR_REGEX_SUB)
def tt_regex_sub(node: RegexSubExpression):
    prv, nxt = lr_var_names(variable=node.variable)
    pattern = repr(node.pattern)
    repl = repr(node.repl)
    return dart.E_RE_SUB.format(nxt, prv, pattern, repl)


@converter.pre(TokenType.EXPR_LIST_REGEX_SUB)
def tt_regex_sub_all(node: MapRegexSubExpression):
    prv, nxt = lr_var_names(variable=node.variable)
    pattern = repr(node.pattern)
    repl = repr(node.repl)
    return dart.E_RE_SUB_ALL.format(nxt, prv, pattern, repl)


@converter.pre(TokenType.EXPR_LIST_STRING_INDEX)
def tt_string_index(node: IndexStringExpression):
    prv, nxt = lr_var_names(variable=node.variable)
    return dart.E_INDEX.format(nxt, prv, node.value)


@converter.pre(TokenType.EXPR_LIST_DOCUMENT_INDEX)
def tt_doc_index(node: IndexDocumentExpression):
    prv, nxt = lr_var_names(variable=node.variable)
    return dart.E_INDEX.format(nxt, prv, node.value)


@converter.pre(TokenType.EXPR_LIST_JOIN)
def tt_join(node: JoinExpression):
    prv, nxt = lr_var_names(variable=node.variable)
    sep = repr(node.sep)
    return dart.E_JOIN.format(nxt, prv, sep)


@converter.pre(TokenType.IS_EQUAL)
def tt_is_equal(node: IsEqualExpression):
    prv, nxt = lr_var_names(variable=node.variable)
    value = repr(node.value)
    msg = repr(node.msg)
    code = dart.E_EQ.format(prv, value, msg)
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += dart.E_ASSIGN.format(nxt, prv)
    return code


@converter.pre(TokenType.IS_NOT_EQUAL)
def tt_is_not_equal(node: IsNotEqualExpression):
    prv, nxt = lr_var_names(variable=node.variable)
    value = repr(node.value)
    msg = repr(node.msg)
    code = dart.E_NE.format(prv, value, msg)
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += dart.E_ASSIGN.format(nxt, prv)
    return code


@converter.pre(TokenType.IS_CONTAINS)
def tt_is_contains(node: IsContainsExpression):
    prv, nxt = lr_var_names(variable=node.variable)
    item = repr(node.item)
    msg = repr(node.msg)
    code = dart.E_IN(prv, prv, item, msg)
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += dart.E_ASSIGN.format(nxt, prv)
    return code


@converter.pre(TokenType.IS_REGEX_MATCH)
def tt_is_regex(node: IsRegexMatchExpression):
    prv, nxt = lr_var_names(variable=node.variable)
    pattern = repr(node.pattern)
    msg = repr(node.msg)

    code = dart.E_IS_RE.format(prv, pattern, prv, msg)
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += dart.E_ASSIGN.format(nxt, prv)
    return code


# universal html API
@converter.pre(TokenType.EXPR_CSS)
def tt_css(node: HtmlCssExpression) -> str:
    q = repr(node.query)
    prv, nxt = lr_var_names(variable=node.variable)
    return dart.E_CSS.format(nxt, prv, q)


@converter.pre(TokenType.EXPR_CSS_ALL)
def tt_css_all(node: HtmlCssAllExpression) -> str:
    q = repr(node.query)
    prv, nxt = lr_var_names(variable=node.variable)
    return dart.E_CSS_ALL.format(nxt, prv, q)


@converter.pre(TokenType.EXPR_TEXT)
def tt_text(node: HtmlTextExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    return dart.E_TEXT.format(nxt, prv)


@converter.pre(TokenType.EXPR_TEXT_ALL)
def tt_text_all(node: HtmlTextAllExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    return dart.E_TEXT_ALL.format(nxt, prv)


@converter.pre(TokenType.EXPR_RAW)
def tt_raw(node: HtmlRawExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    # document object not contains innerHtml property
    if node.variable.num == 0:
        return dart.E_DOC_RAW.format(nxt, prv)
    return dart.E_RAW.format(nxt, prv)


@converter.pre(TokenType.EXPR_RAW_ALL)
def tt_raw_all(node: HtmlRawAllExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    return dart.E_RAW_ALL.format(nxt, prv)


@converter.pre(TokenType.EXPR_ATTR)
def tt_attr(node: HtmlAttrExpression):
    n = repr(node.attr)
    prv, nxt = lr_var_names(variable=node.variable)
    return dart.E_ATTR.format(nxt, prv, n)


@converter.pre(TokenType.EXPR_ATTR_ALL)
def tt_attr_all(node: HtmlAttrAllExpression):
    n = repr(node.attr)
    prv, nxt = lr_var_names(variable=node.variable)
    return dart.E_ATTR_ALL.format(nxt, prv, n)


@converter.pre(TokenType.IS_CSS)
def tt_is_css(node: IsCssExpression):
    prv, nxt = lr_var_names(variable=node.variable)
    q = repr(node.query)
    msg = repr(node.msg)
    code = dart.E_IS_CSS.format(prv, q, msg)
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += dart.E_ASSIGN.format(nxt, prv)
    return code


@converter.pre(TokenType.EXPR_XPATH)
def tt_xpath(_: HtmlXpathExpression) -> str:
    raise NotImplementedError("universal_html not support xpath")


@converter.pre(TokenType.EXPR_XPATH_ALL)
def tt_xpath_all(_: HtmlXpathAllExpression) -> str:
    raise NotImplementedError("universal_html not support xpath")


@converter.pre(TokenType.IS_XPATH)
def tt_is_xpath(_: IsXPathExpression):
    raise NotImplementedError("dart universal_html not support xpath")
