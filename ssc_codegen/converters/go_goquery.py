# default
# STRING_OPTIONAL:
# assingn as pointer *value2 = VAL
# last operator (penis) := replace as =
# return value without link
from .base import BaseCodeConverter, left_right_var_names
from .templates import go
from .utils import (
    to_upper_camel_case as up_camel,
    wrap_double_quotes as wrap_dq,
    wrap_backtick,
    contains_assert_expr_fn,
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
)
from ..tokens import TokenType, StructType, VariableType

converter = BaseCodeConverter()

TYPES = go.TYPES
MAGIC_METHODS = go.MAGIC_METHODS
GOQUERY_IMPORT = '"github.com/PuerkitoBio/goquery"'

E_GOQUERY_CSS = "{} := {}.Find({}).First(); "
E_GOQUERY_CSS_ALL = "{} := {}.Find({}); "
E_GOQUERY_TEXT = "{} := {}.Text(); "
E_GOQUERY_EACH_HEAD = "{}.Each(func(i int, {} *goquery.Selection)"
E_GOQUERY_EACH_FOOTER = go.BRACKET_END + ");"
E_GOQUERY_RAW = "{}, _ := {}.Html(); "
E_GOQUERY_ATTR = "{}, _ := {}.Attr({}); "
IS_CSS = "if {}.Find({}).Length() == 0"


@converter.pre(TokenType.TYPEDEF)
def tt_typedef(node: TypeDef):
    match node.struct_ref.type:
        case StructType.FLAT_LIST:
            # type T_NAME = []T;
            typedef = go.gen_flat_list_typedef(node)

        case StructType.DICT:
            # type T_NAME = map[String]T;
            typedef = go.gen_dict_typedef(node)
        case node.struct_ref.type if node.struct_ref.type in (
            StructType.ITEM,
            StructType.LIST,
        ):
            # type T_NAME struct { F1 String `json:f1`; ... }
            typedef = go.gen_struct_typedef(node)
        case _:
            raise TypeError("Unknown struct type")

    return typedef


@converter.pre(TokenType.STRUCT)
def tt_struct(node: StructParser) -> str:
    # HACK: generate block code immediately, funcs outer scope
    return (
        go.STRUCT_HEAD.format(node.name)
        + " "
        + go.BRACKET_START
        + go.STRUCT_BODY
        + " "
        + go.BRACKET_END
    )


@converter.pre(TokenType.DOCSTRING)
def tt_docstring(node: Docstring) -> str:
    if node.value:
        return go.DOCSTRING(node.value)
    return ""


@converter.pre(TokenType.IMPORTS)
def tt_imports(_: ModuleImports) -> str:
    # dependency variable $PACKAGE$
    return (
        go.PACKAGE
        + "\n"
        + go.IMPORT_HEAD
        + "\n"
        + go.BASE_IMPORTS
        + GOQUERY_IMPORT
        + "\n"
        + go.IMPORT_FOOTER
    )


@converter.pre(TokenType.EXPR_RETURN)
def tt_ret(node: ReturnExpression) -> str:
    _, nxt = left_right_var_names("value", node.variable)

    if node.have_assert_expr():
        return go.RET_VAL_NIL_ERR.format("&" + nxt)
    elif node.have_default_expr():
        # pointer type (naive)
        return go.RET.format(nxt)
    return go.RET.format(nxt)


@converter.pre(TokenType.EXPR_NO_RETURN)
def tt_no_ret(_: NoReturnExpression) -> str:
    return go.NO_RET


@converter.pre(TokenType.EXPR_NESTED)
def tt_nested(node: NestedExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    # HACK: make selection type as document

    code = f"doc{node.variable.num} := goquery.NewDocumentFromNode({prv}.Nodes[0]); "
    code += (
        f"st{node.variable.num} := {node.schema}{{ doc{node.variable.num} }}; "
    )
    code += f"{nxt} := st{node.variable.num}.Parse(); "
    return (
        go.E_NESTED_NEW_DOC.format(node.variable.num, prv)
        + go.E_PARSE_NESTED_ST(node.variable.num, node.schema)
        + go.E_NESTED_PARSE_CALL.format(nxt, node.variable.num)
    )


@converter.pre(TokenType.STRUCT_PRE_VALIDATE)
def tt_pre_validate(node: PreValidateFunction) -> str:
    name = go.MAGIC_METHODS.get(node.name)
    return (
        go.PRE_VALIDATE_HEAD.format(node.parent.name, name)
        + " "
        + go.BRACKET_START
    )


@converter.post(TokenType.STRUCT_PRE_VALIDATE)
def tt_pre_validate(_: PreValidateFunction) -> str:
    return go.BRACKET_END


@converter.pre(TokenType.STRUCT_PART_DOCUMENT)
def tt_part_document(node: PartDocFunction):
    name = MAGIC_METHODS.get(node.name)
    if contains_assert_expr_fn(node):
        return (
            go.PART_DOC_HEAD_ERR.format(node.parent.name, name)
            + " "
            + go.BRACKET_START
        )
    return (
        go.PART_DOC_HEAD.format(node.parent.name, name) + " " + go.BRACKET_START
    )


@converter.post(TokenType.STRUCT_PART_DOCUMENT)
def tt_part_document(_: PartDocFunction):
    return go.BRACKET_END


@converter.pre(TokenType.STRUCT_FIELD)
def tt_function(node: StructFieldFunction) -> str:
    name = up_camel(MAGIC_METHODS.get(node.name, node.name))
    if node.ret_type == VariableType.NESTED:
        # serialize all to structs
        # find associated typedef node by return nested schema name
        associated_typedef = node.find_associated_typedef()
        type_ = go.TYPE_PREFIX.format(node.nested_schema_name())
        st_type = associated_typedef.struct_ref.type
        if st_type == StructType.LIST:
            type_ = go.TYPE_LIST.format(type_)
    else:
        type_ = go.TYPES.get(node.ret_type)
    if node.have_default_expr():
        _, ret = left_right_var_names("value", node.body[-1].variable)
        if node.have_assert_expr():
            type_ = go.RET_DEFAULT_ERR.format(ret, type_)
        else:
            type_ = go.RET_DEFAULT.format(ret, type_)
    if node.have_assert_expr():
        type_ = go.FN_PARSE_HEAD_RET_ERR.format(type_)
    return (
        go.FN_PARSE_HEAD.format(node.parent.name, name, type_)
        + " "
        + go.BRACKET_START
    )


@converter.post(TokenType.STRUCT_FIELD)
def tt_function(_: StructFieldFunction) -> str:
    return go.BRACKET_END


@converter.pre(TokenType.STRUCT_PARSE_START)
def tt_start_parse(node: StartParseFunction) -> str:
    name = go.MAGIC_METHODS.get(node.name)

    type_ = go.TYPE_PREFIX.format(node.parent.name)
    if node.type == StructType.LIST:
        type_ = go.TYPE_LIST.format(type_)
    # try detect err return in first node
    # else scan all call functions
    if node.have_assert_expr():
        type_ = go.FN_PARSE_HEAD_RET_ERR.format(type_)
    elif any(
        fn.have_assert_expr()
        for fn in node.parent.body
        if fn.kind == TokenType.STRUCT_FIELD
    ):
        type_ = go.FN_PARSE_HEAD_RET_ERR.format(type_)
    return (
        go.FN_START_PARSE_HEAD.format(node.parent.name, name, type_)
        + " "
        + go.BRACKET_START
    )


@converter.post(TokenType.STRUCT_PARSE_START)
def tt_start_parse(node: StartParseFunction):
    code = ""
    if any(f.kind == TokenType.STRUCT_PRE_VALIDATE for f in node.body):
        code += go.START_PARSE_CALL_PRE_VALIDATE(node)
    match node.type:
        case StructType.ITEM:
            code += go.gen_item_body(node)
        case StructType.LIST:
            code += go.gen_list_body(node)
        case StructType.DICT:
            code += go.gen_dict_body(node)
        case StructType.FLAT_LIST:
            code += go.gen_flat_list_body(node)
        case _:
            raise NotImplementedError("Unknown struct type")
    return code + go.BRACKET_END


@converter.pre(TokenType.EXPR_DEFAULT)
def tt_default(node: DefaultValueWrapper) -> str:
    value = wrap_dq(node.value) if isinstance(node.value, str) else "nil"
    _, ret = left_right_var_names("value", node.parent.body[-1].variable)
    if node.value == None:
        return go.DEFAULT_HEAD + ret + "=" + value + go.DEFAULT_FOOTER
    return go.DEFAULT_HEAD + "*" + ret + "=" + value + go.DEFAULT_FOOTER


@converter.pre(TokenType.EXPR_STRING_FORMAT)
def tt_string_format(node: FormatExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    template = wrap_dq(node.fmt.replace("{{}}", "%s"))
    code = go.E_STR_FMT.format(nxt, template, prv)
    if node.have_default_expr() and node.next.kind == TokenType.EXPR_RETURN:
        return go.declaration_to_assign(code)
    return code


@converter.pre(TokenType.EXPR_LIST_STRING_FORMAT)
def tt_string_format_all(node: MapFormatExpression) -> str:
    # https://stackoverflow.com/a/33726830
    #     <PREV ARRAY VAR> := []<T1>{1,2,3}
    #
    #     var <NEW ARRAY VAR> []<T2>
    #     for _, x := range <PREV ARRAY VAR> {
    #         <NEW ARRAY VAR> = append(<NEW ARRAY VAR>, <MAP_CODE>)
    #     }
    prv, nxt = left_right_var_names("value", node.variable)
    template = wrap_dq(node.fmt.replace("{{}}", "%s"))
    i_var = f"i{node.variable.num}"
    map_code = go.E_STR_FMT_ALL.format(template, i_var)
    code = (
        go.E_NXT_ARRAY.format(nxt, TYPES.get(node.next.variable.type))
        + go.E_FOR_RANGE_HEAD.format(i_var, prv)
        + " "
        + go.BRACKET_START
        + go.E_FOR_RANGE_MAP_CODE.format(nxt, nxt, map_code)
        + go.BRACKET_END
    )
    return code


@converter.pre(TokenType.EXPR_STRING_TRIM)
def tt_string_trim(node: TrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = wrap_dq(node.value)
    code = go.E_STR_TRIM.format(nxt, prv, chars)
    if node.have_default_expr() and node.next.kind == TokenType.EXPR_RETURN:
        return go.declaration_to_assign(code)
    return code


@converter.pre(TokenType.EXPR_LIST_STRING_TRIM)
def tt_string_trim_all(node: MapTrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = wrap_dq(node.value)

    i_var = f"i{node.variable.num}"
    map_code = go.E_STR_TRIM_ALL.format(i_var, chars)
    code = (
        go.E_NXT_ARRAY.format(nxt, TYPES.get(node.next.variable.type))
        + go.E_FOR_RANGE_HEAD.format(i_var, prv)
        + " "
        + go.BRACKET_START
        + go.E_FOR_RANGE_MAP_CODE.format(nxt, nxt, map_code)
        + go.BRACKET_END
    )
    return code


@converter.pre(TokenType.EXPR_STRING_LTRIM)
def tt_string_ltrim(node: LTrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = wrap_dq(node.value)
    code = go.E_STR_LTRIM.format(nxt, prv, chars)
    if node.have_default_expr() and node.next.kind == TokenType.EXPR_RETURN:
        return go.declaration_to_assign(code)
    return code


@converter.pre(TokenType.EXPR_LIST_STRING_LTRIM)
def tt_string_ltrim_all(node: MapLTrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = wrap_dq(node.value)
    i_var = f"i{node.variable.num}"
    map_code = go.E_STR_LTRIM_ALL.format(i_var, chars)
    code = (
        go.E_NXT_ARRAY.format(nxt, TYPES.get(node.next.variable.type))
        + go.E_FOR_RANGE_HEAD.format(i_var, prv)
        + " "
        + go.BRACKET_START
        + go.E_FOR_RANGE_MAP_CODE.format(nxt, nxt, map_code)
        + go.BRACKET_END
    )
    return code


@converter.pre(TokenType.EXPR_STRING_RTRIM)
def tt_string_rtrim(node: RTrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = wrap_dq(node.value)
    code = go.E_STR_RTRIM.format(nxt, prv, chars)
    if node.have_default_expr() and node.next.kind == TokenType.EXPR_RETURN:
        return go.declaration_to_assign(code)
    return code


@converter.pre(TokenType.EXPR_LIST_STRING_RTRIM)
def tt_string_rtrim_all(node: MapRTrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = wrap_dq(node.value)
    i_var = f"i{node.variable.num}"
    map_code = go.E_STR_RTRIM_ALL.format(i_var, chars)
    code = (
        go.E_NXT_ARRAY.format(nxt, TYPES.get(node.next.variable.type))
        + go.E_FOR_RANGE_HEAD.format(i_var, prv)
        + " "
        + go.BRACKET_START
        + go.E_FOR_RANGE_MAP_CODE.format(nxt, nxt, map_code)
        + go.BRACKET_END
    )
    return code


@converter.pre(TokenType.EXPR_STRING_REPLACE)
def tt_string_replace(node: ReplaceExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    old, new = wrap_dq(node.old), wrap_dq(node.new)
    code = go.E_STR_REPL.format(nxt, prv, old, new)
    if node.have_default_expr() and node.next.kind == TokenType.EXPR_RETURN:
        return go.declaration_to_assign(code)
    return code


@converter.pre(TokenType.EXPR_LIST_STRING_REPLACE)
def tt_string_replace_all(node: MapReplaceExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    old, new = wrap_dq(node.old), wrap_dq(node.new)
    i_var = f"i{node.variable.num}"
    map_code = go.E_STR_REPL_ALL.format(i_var, old, new)
    code = (
        go.E_NXT_ARRAY.format(nxt, TYPES.get(node.next.variable.type))
        + go.E_FOR_RANGE_HEAD.format(i_var, prv)
        + " "
        + go.BRACKET_START
        + go.E_FOR_RANGE_MAP_CODE.format(nxt, nxt, map_code)
        + go.BRACKET_END
    )
    return code


@converter.pre(TokenType.EXPR_STRING_SPLIT)
def tt_string_split(node: SplitExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    sep = wrap_dq(node.sep)
    code = go.E_STR_SPLIT.format(nxt, prv, sep)
    if node.have_default_expr() and node.next.kind == TokenType.EXPR_RETURN:
        return go.declaration_to_assign(code)
    return code


@converter.pre(TokenType.EXPR_REGEX)
def tt_regex(node: RegexExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    pattern = wrap_backtick(node.pattern)
    group = node.group - 1
    code = go.E_RE.format(nxt, pattern, prv, group)
    if node.have_default_expr() and node.next.kind == TokenType.EXPR_RETURN:
        return go.declaration_to_assign(code)
    return code


@converter.pre(TokenType.EXPR_REGEX_ALL)
def tt_regex_all(node: RegexAllExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    pattern = wrap_backtick(node.pattern)
    code = go.E_RE_ALL.format(nxt, pattern, prv)
    if node.have_default_expr() and node.next.kind == TokenType.EXPR_RETURN:
        return go.declaration_to_assign(code)
    return code


@converter.pre(TokenType.EXPR_REGEX_SUB)
def tt_regex_sub(node: RegexSubExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    pattern = wrap_backtick(node.pattern)
    repl = wrap_dq(node.repl)
    code = go.E_RE_SUB.format(nxt, pattern, prv, repl)
    if node.have_default_expr() and node.next.kind == TokenType.EXPR_RETURN:
        return go.declaration_to_assign(code)
    return code


@converter.pre(TokenType.EXPR_LIST_REGEX_SUB)
def tt_regex_sub_all(node: MapRegexSubExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    pattern = wrap_backtick(node.pattern)
    repl = wrap_dq(node.repl)
    i_var = f"i{node.variable.num}"
    map_code = go.E_RE_SUB_ALL.format(pattern, i_var, repl)
    code = (
        go.E_NXT_ARRAY.format(nxt, TYPES.get(node.next.variable.type))
        + go.E_FOR_RANGE_HEAD.format(i_var, prv)
        + " "
        + go.BRACKET_START
        + go.E_FOR_RANGE_MAP_CODE.format(nxt, nxt, map_code)
        + go.BRACKET_END
    )
    return code


@converter.pre(TokenType.EXPR_LIST_STRING_INDEX)
def tt_string_index(node: IndexStringExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    code = go.E_INDEX.format(nxt, prv, node.value)
    if node.have_default_expr() and node.next.kind == TokenType.EXPR_RETURN:
        return go.declaration_to_assign(code)
    return code


@converter.pre(TokenType.EXPR_LIST_DOCUMENT_INDEX)
def tt_doc_index(node: IndexDocumentExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    code = go.E_INDEX.format(nxt, prv, node.value)
    if node.have_default_expr() and node.next.kind == TokenType.EXPR_RETURN:
        return go.declaration_to_assign(code)
    return code


@converter.pre(TokenType.EXPR_LIST_JOIN)
def tt_join(node: JoinExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    sep = wrap_dq(node.sep)
    code = go.E_JOIN.format(nxt, prv, sep)
    if node.have_default_expr() and node.next.kind == TokenType.EXPR_RETURN:
        return go.declaration_to_assign(code)
    return code


@converter.pre(TokenType.IS_EQUAL)
def tt_is_equal(node: IsEqualExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    value = wrap_dq(node.value)
    msg = wrap_dq(node.msg)
    ret = (
        go.RET_FMT_ERR.format(msg)
        if node.parent.kind == TokenType.STRUCT_PRE_VALIDATE
        else go.RET_NIL_FMT_ERR.format(msg)
    )
    code = (
        go.E_EQ.format(prv, value)
        + " "
        + go.BRACKET_START
        + ret
        + go.BRACKET_END
    )

    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += go.E_ASSIGN.format(nxt, prv)
    return code


@converter.pre(TokenType.IS_NOT_EQUAL)
def tt_is_not_equal(node: IsNotEqualExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    value = wrap_dq(node.value)
    msg = wrap_dq(node.msg)
    ret = (
        go.RET_FMT_ERR.format(msg)
        if node.parent.kind == TokenType.STRUCT_PRE_VALIDATE
        else go.RET_NIL_FMT_ERR.format(msg)
    )

    code = (
        go.E_NE.format(prv, value)
        + " "
        + go.BRACKET_START
        + ret
        + go.BRACKET_END
    )
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += go.E_ASSIGN.format(nxt, prv)
    return code


@converter.pre(TokenType.IS_CONTAINS)
def tt_is_contains(node: IsContainsExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    item = wrap_dq(node.item)
    msg = wrap_dq(node.msg)
    ret = (
        go.RET_FMT_ERR.format(msg)
        if node.parent.kind == TokenType.STRUCT_PRE_VALIDATE
        else go.RET_NIL_FMT_ERR.format(msg)
    )

    code = (
        go.E_IN.format(prv, item)
        + " "
        + go.BRACKET_START
        + ret
        + go.BRACKET_END
    )
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += go.E_ASSIGN.format(nxt, prv)
    return code


@converter.pre(TokenType.IS_REGEX_MATCH)
def tt_is_regex(node: IsRegexMatchExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    pattern = wrap_backtick(node.pattern)
    msg = wrap_dq(node.msg)
    err_var = f"err{node.variable.num}"
    ret = (
        go.RET_FMT_ERR.format(msg)
        if node.parent.kind == TokenType.STRUCT_PRE_VALIDATE
        else go.RET_NIL_FMT_ERR.format(msg)
    )
    code = (
        go.E_IS_RE_ASSIGN.format(err_var, pattern, prv)
        + go.E_IS_RE.format(err_var)
        + go.BRACKET_START
        + ret
        + go.BRACKET_END
    )

    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += go.E_ASSIGN.format(nxt, prv)
    return code


# goquery API
@converter.pre(TokenType.EXPR_CSS)
def tt_css(node: HtmlCssExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    q = wrap_dq(node.query)
    return E_GOQUERY_CSS.format(nxt, prv, q)


@converter.pre(TokenType.EXPR_CSS_ALL)
def tt_css_all(node: HtmlCssAllExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    q = wrap_dq(node.query)
    return E_GOQUERY_CSS_ALL.format(nxt, prv, q)


@converter.pre(TokenType.EXPR_TEXT)
def tt_text(node: HtmlTextExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    code = E_GOQUERY_TEXT.format(nxt, prv)
    if node.have_default_expr() and node.next.kind == TokenType.EXPR_RETURN:
        return go.declaration_to_assign(code)
    return code


@converter.pre(TokenType.EXPR_TEXT_ALL)
def tt_text_all(node: HtmlTextAllExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    i_var = f"e{node.variable.num}"
    map_code = f"{i_var}.Text()"

    code = (
        go.E_NXT_ARRAY.format(nxt, go.TYPES.get(node.next.variable.type))
        + E_GOQUERY_EACH_HEAD.format(prv, i_var)
        + " "
        + go.BRACKET_START
        + go.E_FOR_RANGE_MAP_CODE.format(nxt, nxt, map_code)
        + E_GOQUERY_EACH_FOOTER
    )
    return code


@converter.pre(TokenType.EXPR_RAW)
def tt_raw(node: HtmlRawExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)

    code = E_GOQUERY_RAW.format(nxt, prv)
    if node.have_default_expr() and node.next.kind == TokenType.EXPR_RETURN:
        return go.declaration_to_assign(code)
    return code


@converter.pre(TokenType.EXPR_RAW_ALL)
def tt_raw_all(node: HtmlRawAllExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    i_var = f"e{node.variable.num}"
    attr_var = f"attr{node.variable.num}"

    return (
        go.E_NXT_ARRAY.format(nxt, go.TYPES.get(node.next.variable.type))
        + E_GOQUERY_EACH_HEAD.format(prv, i_var)
        + " "
        + go.BRACKET_START
        + E_GOQUERY_RAW.format(attr_var, i_var)
        + go.E_FOR_RANGE_MAP_CODE.format(nxt, nxt, attr_var)
        + E_GOQUERY_EACH_FOOTER
    )


@converter.pre(TokenType.EXPR_ATTR)
def tt_attr(node: HtmlAttrExpression):
    n = wrap_dq(node.attr)
    prv, nxt = left_right_var_names("value", node.variable)
    code = E_GOQUERY_ATTR.format(nxt, prv, n)
    if node.have_default_expr() and node.next.kind == TokenType.EXPR_RETURN:
        return go.declaration_to_assign(code)
    return code


@converter.pre(TokenType.EXPR_ATTR_ALL)
def tt_attr_all(node: HtmlAttrAllExpression):
    n = wrap_dq(node.attr)
    prv, nxt = left_right_var_names("value", node.variable)
    attr_var = f"attr{node.variable.num}"
    i_var = f"e{node.variable.num}"
    # var NEXT []string
    # 	PREV.Each(func(i int, CB_VAR *goquery.Selection) {
    # 		ATTR_VAR, _ := sel.Attr(NAME)
    # 		attrs = append(attrs, ATTR_VAR)
    # 	})

    return (
        go.E_NXT_ARRAY.format(nxt, go.TYPES.get(node.next.variable.type))
        + E_GOQUERY_EACH_HEAD.format(prv, i_var)
        + " "
        + go.BRACKET_START
        + E_GOQUERY_ATTR.format(attr_var, i_var, n)
        + go.E_FOR_RANGE_MAP_CODE.format(nxt, nxt, attr_var)
        + E_GOQUERY_EACH_FOOTER
    )


@converter.pre(TokenType.IS_CSS)
def tt_is_css(node: IsCssExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    q = wrap_dq(node.query)
    msg = wrap_dq(node.msg)
    ret = (
        go.RET_FMT_ERR.format(msg)
        if node.parent.kind == TokenType.STRUCT_PRE_VALIDATE
        else go.RET_NIL_FMT_ERR.format(msg)
    )
    code = IS_CSS.format(prv, q) + " " + go.BRACKET_START + ret + go.BRACKET_END
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += go.E_ASSIGN.format(nxt, prv)
    return code


@converter.pre(TokenType.EXPR_XPATH)
def tt_xpath(_: HtmlXpathExpression) -> str:
    raise NotImplementedError("goquery not support xpath")


@converter.pre(TokenType.EXPR_XPATH_ALL)
def tt_xpath_all(_: HtmlXpathAllExpression) -> str:
    raise NotImplementedError("bs4 not support xpath")


@converter.pre(TokenType.IS_XPATH)
def tt_is_xpath(_: IsXPathExpression):
    raise NotImplementedError("goquery not support xpath")
