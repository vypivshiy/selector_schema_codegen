# TODO: required enchant, not tested
from functools import partial

from .templates import dart
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
    ToInteger,
    ToFloat,
    ToListInteger,
)
from ..tokens import TokenType, StructType

converter = BaseCodeConverter()

lr_var_names = partial(left_right_var_names, name="value")

TYPES = dart.TYPES
MAGIC_METHODS = dart.MAGIC_METHODS


@converter.pre(TokenType.TYPEDEF)
def tt_typedef(node: TypeDef):
    # used records from dart 3v
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
            # FIXME: typing as List<ITEM>
            code = dart.typedef_list_record(node)
        case _:
            raise TypeError("Unknown struct type")
    return code


# dart API
@converter.pre(TokenType.STRUCT)
def tt_struct(node: StructParser) -> str:
    return dart.BINDINGS[node.kind, node.name] + " " + dart.START_BRACKET


@converter.post(TokenType.STRUCT)
def tt_struct(_: StructParser) -> str:
    return dart.END_BRACKET


@converter.pre(TokenType.STRUCT_INIT)
def tt_init(node: StructInit) -> str:
    return dart.BINDINGS[node.kind, node.name]


@converter.pre(TokenType.DOCSTRING)
def tt_docstring(node: Docstring) -> str:
    return dart.BINDINGS[node.kind, node.value]


@converter.pre(TokenType.IMPORTS)
def tt_imports(node: ModuleImports) -> str:
    return dart.BINDINGS[node.kind]


@converter.pre(TokenType.EXPR_RETURN)
def tt_ret(node: ReturnExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    if node.have_default_expr():
        return dart.BINDINGS[node.kind, prv]
    return dart.BINDINGS[node.kind, nxt]


@converter.pre(TokenType.EXPR_NO_RETURN)
def tt_no_ret(node: NoReturnExpression) -> str:
    return dart.BINDINGS[node.kind]


@converter.pre(TokenType.EXPR_NESTED)
def tt_nested(node: NestedExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    return dart.BINDINGS[node.kind, node.variable.num, nxt, node.schema, prv]


@converter.pre(TokenType.STRUCT_PRE_VALIDATE)
def tt_pre_validate(node: PreValidateFunction) -> str:
    name = MAGIC_METHODS.get(node.name)
    return dart.BINDINGS[node.kind, name] + " " + dart.START_BRACKET


@converter.post(TokenType.STRUCT_PRE_VALIDATE)
def tt_pre_validate(_: PreValidateFunction) -> str:
    return dart.END_BRACKET


@converter.pre(TokenType.STRUCT_PART_DOCUMENT)
def tt_part_document(node: PartDocFunction) -> str:
    name = MAGIC_METHODS.get(node.name)
    return dart.BINDINGS[node.kind, name] + " " + dart.START_BRACKET


@converter.post(TokenType.STRUCT_PART_DOCUMENT)
def tt_part_document(_: PartDocFunction) -> str:
    return dart.END_BRACKET


@converter.pre(TokenType.STRUCT_FIELD)
def tt_function(node: StructFieldFunction) -> str:
    name = MAGIC_METHODS.get(node.name, node.name)
    if name == node.name:
        name = up_camel(node.name)
    return dart.BINDINGS[node.kind, name, "value"] + " " + dart.START_BRACKET


@converter.post(TokenType.STRUCT_FIELD)
def tt_function(_: StructFieldFunction) -> str:
    return dart.END_BRACKET


@converter.pre(TokenType.STRUCT_PARSE_START)
def tt_start_parse(node: StartParseFunction) -> str:
    ret_type = dart.TYPE_PREFIX.format(node.parent.name)
    name = MAGIC_METHODS.get(node.name)
    code = dart.BINDINGS[node.kind, ret_type, name] + " " + dart.START_BRACKET
    if any(f.name == "__PRE_VALIDATE__" for f in node.body):
        name = MAGIC_METHODS.get("__PRE_VALIDATE__")
        # todo: move to templates consts
        code+=f"{name}(selector); "
        # code += dart.BINDINGS[TokenType.STRUCT_PRE_VALIDATE, name]

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
def tt_start_parse_(_: StartParseFunction) -> str:
    return dart.END_BRACKET


@converter.pre(TokenType.EXPR_DEFAULT_START)
def tt_default(node: DefaultValueWrapper) -> str:
    return dart.BINDINGS[node.kind]


@converter.post(TokenType.EXPR_DEFAULT_END)
def tt_default_(node: DefaultValueWrapper) -> str:
    # TODO: int, float, lists provide
    val = repr(node.value) if isinstance(node.value, str) else "null"
    return dart.BINDINGS[node.kind, val]


@converter.pre(TokenType.EXPR_STRING_FORMAT)
def tt_string_format(node: FormatExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    return dart.BINDINGS[node.kind, nxt, prv, node.fmt]


@converter.pre(TokenType.EXPR_LIST_STRING_FORMAT)
def tt_string_format_all(node: MapFormatExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    return dart.BINDINGS[node.kind, nxt, prv, node.fmt]


@converter.pre(TokenType.EXPR_STRING_TRIM)
def tt_string_trim(node: TrimExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    chars = node.value
    left = wrap_q("^" + escape_str(chars))
    right = wrap_q(escape_str(chars + "$"))
    return dart.BINDINGS[node.kind, nxt, prv, left, right]


@converter.pre(TokenType.EXPR_LIST_STRING_TRIM)
def tt_string_trim_all(node: MapTrimExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    chars = node.value
    left = wrap_q("^" + escape_str(chars))
    right = wrap_q(escape_str(chars + "$"))
    return dart.BINDINGS[node.kind, nxt, prv, left, right]


@converter.pre(TokenType.EXPR_STRING_LTRIM)
def tt_string_ltrim(node: LTrimExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    chars = node.value
    left = wrap_q("^" + escape_str(chars))
    return dart.BINDINGS[node.kind, nxt, prv, left]


@converter.pre(TokenType.EXPR_LIST_STRING_LTRIM)
def tt_string_ltrim_all(node: MapLTrimExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    chars = node.value
    left = wrap_q("^" + escape_str(chars))
    return dart.BINDINGS[node.kind, nxt, prv, left]


@converter.pre(TokenType.EXPR_STRING_RTRIM)
def tt_string_rtrim(node: RTrimExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    chars = node.value
    right = wrap_q(escape_str(chars + "$"))
    return dart.BINDINGS[node.kind, nxt, prv, right]


@converter.pre(TokenType.EXPR_LIST_STRING_RTRIM)
def tt_string_rtrim_all(node: MapRTrimExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    chars = node.value
    right = wrap_q(escape_str(chars + "$"))
    return dart.BINDINGS[node.kind, nxt, prv, right]


@converter.pre(TokenType.EXPR_STRING_REPLACE)
def tt_string_replace(node: ReplaceExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    old, new = repr(node.old), repr(node.new)
    return dart.BINDINGS[node.kind, nxt, prv, old, new]


@converter.pre(TokenType.EXPR_LIST_STRING_REPLACE)
def tt_string_replace_all(node: MapReplaceExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    old, new = repr(node.old), repr(node.new)
    return dart.BINDINGS[node.kind, nxt, prv, old, new]


@converter.pre(TokenType.EXPR_STRING_SPLIT)
def tt_string_split(node: SplitExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    sep = repr(node.sep)
    return dart.BINDINGS[node.kind, nxt, prv, sep]


@converter.pre(TokenType.EXPR_REGEX)
def tt_regex(node: RegexExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    pattern = repr(node.pattern)
    group = node.group
    return dart.BINDINGS[node.kind, nxt, pattern, prv, group]


@converter.pre(TokenType.EXPR_REGEX_ALL)
def tt_regex_all(node: RegexAllExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    pattern = repr(node.pattern)
    # RegExp(pattern).allMatches(s).map((e) => e.group(group)!).toList();
    return dart.BINDINGS[node.kind, nxt, pattern, prv]


@converter.pre(TokenType.EXPR_REGEX_SUB)
def tt_regex_sub(node: RegexSubExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    pattern = repr(node.pattern)
    # reserved DART symbol
    if '$' in pattern:
        pattern = pattern.replace('$', '\$')
    repl = repr(node.repl)
    return dart.BINDINGS[node.kind, nxt, prv, pattern, repl]


@converter.pre(TokenType.EXPR_LIST_REGEX_SUB)
def tt_regex_sub_all(node: MapRegexSubExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    pattern = repr(node.pattern)
    repl = repr(node.repl)
    return dart.BINDINGS[node.kind, nxt, prv, pattern, repl]


@converter.pre(TokenType.EXPR_LIST_STRING_INDEX)
def tt_string_index(node: IndexStringExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    return dart.BINDINGS[node.kind, nxt, prv, node.value]


@converter.pre(TokenType.EXPR_LIST_DOCUMENT_INDEX)
def tt_doc_index(node: IndexDocumentExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    return dart.BINDINGS[node.kind, nxt, prv, node.value]


@converter.pre(TokenType.EXPR_LIST_JOIN)
def tt_join(node: JoinExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    sep = repr(node.sep)
    return dart.BINDINGS[node.kind, nxt, prv, sep]


@converter.pre(TokenType.IS_EQUAL)
def tt_is_equal(node: IsEqualExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    value = repr(node.value)
    msg = repr(node.msg)
    code = dart.BINDINGS[node.kind, prv, value, msg]
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += dart.E_ASSIGN.format(nxt, prv)
    return code


@converter.pre(TokenType.IS_NOT_EQUAL)
def tt_is_not_equal(node: IsNotEqualExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    value = repr(node.value)
    msg = repr(node.msg)
    code = dart.BINDINGS[node.kind, prv, value, msg]
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += dart.E_ASSIGN.format(nxt, prv)
    return code


@converter.pre(TokenType.IS_CONTAINS)
def tt_is_contains(node: IsContainsExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    item = repr(node.item)
    msg = repr(node.msg)
    code = dart.BINDINGS[node.kind, prv, prv, item, msg]
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += dart.E_ASSIGN.format(nxt, prv)
    return code


@converter.pre(TokenType.IS_REGEX_MATCH)
def tt_is_regex(node: IsRegexMatchExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    pattern = repr(node.pattern)
    msg = repr(node.msg)
    code = dart.BINDINGS[node.kind, prv, pattern, prv, msg]
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += dart.E_ASSIGN.format(nxt, prv)
    return code


# universal html API
@converter.pre(TokenType.EXPR_CSS)
def tt_css(node: HtmlCssExpression) -> str:
    q = repr(node.query)
    prv, nxt = lr_var_names(variable=node.variable)
    return dart.BINDINGS[node.kind, nxt, prv, q]


@converter.pre(TokenType.EXPR_CSS_ALL)
def tt_css_all(node: HtmlCssAllExpression) -> str:
    q = repr(node.query)
    prv, nxt = lr_var_names(variable=node.variable)
    return dart.BINDINGS[node.kind, nxt, prv, q]


@converter.pre(TokenType.EXPR_TEXT)
def tt_text(node: HtmlTextExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    return dart.BINDINGS[node.kind, nxt, prv]


@converter.pre(TokenType.EXPR_TEXT_ALL)
def tt_text_all(node: HtmlTextAllExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    return dart.BINDINGS[node.kind, nxt, prv]


@converter.pre(TokenType.EXPR_RAW)
def tt_raw(node: HtmlRawExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    return dart.BINDINGS[node.variable.num, nxt, prv]


@converter.pre(TokenType.EXPR_RAW_ALL)
def tt_raw_all(node: HtmlRawAllExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    return dart.BINDINGS[node.kind, nxt, prv]


@converter.pre(TokenType.EXPR_ATTR)
def tt_attr(node: HtmlAttrExpression) -> str:
    n = repr(node.attr)
    prv, nxt = lr_var_names(variable=node.variable)
    return dart.BINDINGS[node.kind, nxt, prv, n]


@converter.pre(TokenType.EXPR_ATTR_ALL)
def tt_attr_all(node: HtmlAttrAllExpression) -> str:
    n = repr(node.attr)
    prv, nxt = lr_var_names(variable=node.variable)
    return dart.BINDINGS[node.kind, nxt, prv, n]


@converter.pre(TokenType.IS_CSS)
def tt_is_css(node: IsCssExpression):
    prv, nxt = lr_var_names(variable=node.variable)
    q = repr(node.query)
    msg = repr(node.msg)
    code = dart.BINDINGS[node.kind, prv, q, msg]
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


# numeric
@converter.pre(TokenType.TO_INT)
def tt_to_int(node: ToInteger) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    return dart.BINDINGS[node.kind, nxt, prv]


@converter.pre(TokenType.TO_INT_LIST)
def tt_to_list_int(node: ToListInteger) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    return dart.BINDINGS[node.kind, nxt, prv]


@converter.pre(TokenType.TO_FLOAT)
def tt_to_float(node: ToFloat) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    return dart.BINDINGS[node.kind, nxt, prv]


@converter.pre(TokenType.TO_FLOAT_LIST)
def tt_to_list_float(node: ToFloat) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    return dart.BINDINGS[node.kind, nxt, prv]