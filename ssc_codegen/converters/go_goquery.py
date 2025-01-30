from ..ast_ssc import (
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
    IndexDocumentExpression,
    IndexStringExpression,
    IsContainsExpression,
    IsCssExpression,
    IsEqualExpression,
    IsNotEqualExpression,
    IsRegexMatchExpression,
    JoinExpression,
    LTrimExpression,
    MapFormatExpression,
    MapLTrimExpression,
    MapRegexSubExpression,
    MapReplaceExpression,
    MapRTrimExpression,
    MapTrimExpression,
    ModuleImports,
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
    StructParser,
    ToFloat,
    ToInteger,
    ToListFloat,
    ToListInteger,
    TrimExpression,
    TypeDef,
)
from ..tokens import StructType, TokenType, VariableType
from .base import BaseCodeConverter, left_right_var_names
from .templates import go
from .utils import (
    to_upper_camel_case,
    wrap_backtick,
    wrap_double_quotes,
)

converter = BaseCodeConverter()


@converter.pre(TokenType.TYPEDEF)
def tt_typedef(node: TypeDef) -> str:
    match node.struct_ref.type:
        case StructType.ITEM:
            code = go.gen_typedef_item(node)
        case StructType.DICT:
            code = go.gen_typedef_dict(node)
        case StructType.FLAT_LIST:
            code = go.gen_typedef_flat_list(node)
        case StructType.LIST:
            code = go.gen_typedef_list(node)
        case _:
            raise TypeError("Unknown struct type")
    return code


@converter.pre(TokenType.STRUCT)
def tt_struct(node: StructParser) -> str:
    # HACK: generate block code immediately, funcs attached by ptr
    return (
        f"type {node.name} struct "
        + go.BRACKET_START
        + "Document *goquery.Document; "
        + go.BRACKET_END
    )


@converter.pre(TokenType.DOCSTRING)
def tt_docstring(node: Docstring) -> str:
    if node.value:
        if node.parent and node.parent.kind == StructParser.kind:
            return go.BINDINGS_PRE[
                node.kind, f"{node.parent.name} {node.value}"
            ]
        return go.BINDINGS_PRE[node.kind, f"{node.value}"]
    return ""


@converter.pre(TokenType.IMPORTS)
def tt_imports(node: ModuleImports) -> str:
    # dependency variable $PACKAGE$
    return go.BINDINGS_PRE[node.kind]


@converter.pre(TokenType.STRUCT_PART_DOCUMENT)
def tt_part_doc(node: PartDocFunction) -> str:
    parent_name = node.parent.name
    # corner cases
    # 1. have assert expr (+ ret error/nil)
    # 2. normal mode
    if node.body[0].have_assert_expr():
        # func (p *{}) {}(value *goquery.Selection) (*goquery.Selection, error)
        return go.BINDINGS_PRE[node.kind, parent_name, True]
    return go.BINDINGS_PRE[node.kind, parent_name, False]


@converter.post(TokenType.STRUCT_PART_DOCUMENT)
def tt_part_doc_end(_) -> str:
    return go.BRACKET_END


@converter.pre(TokenType.STRUCT_FIELD)
def tt_function(node: StructFieldFunction) -> str:
    fn_name = to_upper_camel_case(go.MAGIC_METHODS.get(node.name, node.name))
    parent_name = node.parent.name
    ret_header = go.gen_struct_field_ret_header(node)
    return (
        "func (p *"
        + parent_name
        + ") "
        + f"parse{fn_name}(value *goquery.Selection) "
        + ret_header
        + go.BRACKET_START
    )


@converter.post(TokenType.STRUCT_FIELD)
def tt_function_end(_) -> str:
    return go.BRACKET_END


@converter.pre(TokenType.STRUCT_PRE_VALIDATE)
def tt_pre_validate(node: PreValidateFunction) -> str:
    # "func (p *{}) {}(value *goquery.Selection) error {"
    return go.BINDINGS_PRE[node.kind, node.parent.name]


@converter.post(TokenType.STRUCT_PRE_VALIDATE)
def tt_pre_validate_end(_) -> str:
    return go.BRACKET_END


@converter.pre(TokenType.STRUCT_PARSE_START)
def tt_start_parse(node: StartParseFunction) -> str:
    # name = go.MAGIC_METHODS.get(node.name)
    name = "Parse"
    if node.type == StructType.LIST:
        ret_type = f"*T{node.parent.name}ITEMS"
    else:
        ret_type = f"*T{node.parent.name}"
    ret_header = f"({ret_type}, error)"
    fn_header = (
        f"func (p *{node.parent.name}) {name}() {ret_header} "
        + go.BRACKET_START
    )
    return fn_header  # todo


@converter.post(TokenType.STRUCT_PARSE_START)
def tt_start_parse_post(node: StartParseFunction) -> str:
    code = ""
    if any(e.name == "__PRE_VALIDATE__" for e in node.body):
        code += (
            "err := p.preValidate(p.Document.Selection); "
            + "if err != nil "
            + go.BRACKET_START
            + "panic(err); "
            + go.BRACKET_END
        )
    match node.type:
        case StructType.ITEM:
            body = go.gen_start_parse_item(node)
        case StructType.DICT:
            body = go.gen_start_parse_dict(node)
        case StructType.FLAT_LIST:
            body = go.gen_start_parse_flat_list(node)
        case StructType.LIST:
            body = go.gen_start_parse_list(node)
        case _:
            msg = f"Unknown StructType type {node.type.name}"
            raise TypeError(msg)
    return code + body + go.BRACKET_END


@converter.pre(TokenType.EXPR_RETURN)
def tt_ret(node: ReturnExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)

    # cases
    # 1. normal
    # 2. assert (value + err)
    # 3. default (result, nil)
    # 4. nested
    # 5. str cast to int, float...

    if node.have_assert_expr() and node.have_default_expr():
        return f"result = {prv}; " + "return result, nil;"

    if node.have_default_expr():
        return f"result = {prv}; " + "return result, nil;"

    elif node.have_assert_expr():
        if node.ret_type == VariableType.NESTED:
            return f"return *{nxt}, nil; "
        return f"return {nxt}, nil; "
    elif node.ret_type == VariableType.NESTED:
        return f"return *{nxt}, nil; "
    return f"return {nxt}; "


#
@converter.pre(TokenType.EXPR_NO_RETURN)
def tt_no_ret(_: NoReturnExpression) -> str:
    # in current stage project used only in __PRE_VALIDATE__
    # its return nil or throw error
    return "return nil;"


@converter.pre(TokenType.EXPR_NESTED)
def tt_nested(node: NestedExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    # HACK: make selection type as document
    code = (
        f"doc{node.variable.num} := goquery.NewDocumentFromNode({prv}.Nodes[0]); "
        + f"st{node.variable.num} := {node.schema}{{ doc{node.variable.num} }}; "
        + f"{nxt}, err := st{node.variable.num}.Parse(); "
        + "if err != nil"
        + go.BRACKET_START
        + "panic(err); "
        + go.BRACKET_END
    )
    return code


@converter.pre(TokenType.EXPR_DEFAULT_START)
def tt_default(node: DefaultStart) -> str:
    # defer func() wrapper, set default value if code throw error
    if isinstance(node.value, str):
        value = wrap_double_quotes(node.value)
    elif isinstance(node.value, (int, float)):
        value = node.value
    else:
        value = "nil"
    prv, nxt = left_right_var_names("value", node.variable)
    return go.BINDINGS_PRE[node.kind, value] + f"{nxt} := {prv};"


@converter.pre(TokenType.EXPR_STRING_FORMAT)
def tt_string_format(node: FormatExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    template = wrap_double_quotes(node.fmt.replace("{{}}", "%s"))
    return go.BINDINGS_PRE[TokenType.EXPR_STRING_FORMAT, nxt, template, prv]


#
@converter.pre(TokenType.EXPR_LIST_STRING_FORMAT)
def tt_string_format_all(node: MapFormatExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    template = wrap_double_quotes(node.fmt.replace("{{}}", "%s"))
    arr_type = go.TYPES.get(node.next.ret_type, "")
    return go.BINDINGS_PRE[node.kind, nxt, template, prv, arr_type]


@converter.pre(TokenType.EXPR_STRING_TRIM)
def tt_string_trim(node: TrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = wrap_double_quotes(node.value)
    return go.BINDINGS_PRE[node.kind, nxt, chars, prv]


@converter.pre(TokenType.EXPR_LIST_STRING_TRIM)
def tt_string_trim_all(node: MapTrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = wrap_double_quotes(node.value)
    arr_type = go.TYPES.get(node.next.ret_type, "")

    return go.BINDINGS_PRE[node.kind, nxt, chars, arr_type]


@converter.pre(TokenType.EXPR_STRING_LTRIM)
def tt_string_ltrim(node: LTrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = wrap_double_quotes(node.value)
    return go.BINDINGS_PRE[node.kind, nxt, prv, chars]


@converter.pre(TokenType.EXPR_LIST_STRING_LTRIM)
def tt_string_ltrim_all(node: MapLTrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = wrap_double_quotes(node.value)
    arr_type = go.TYPES.get(node.next.variable.type)
    return go.BINDINGS_PRE[node.kind, nxt, chars, prv, arr_type]


@converter.pre(TokenType.EXPR_STRING_RTRIM)
def tt_string_rtrim(node: RTrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = wrap_double_quotes(node.value)
    return go.BINDINGS_PRE[node.kind, nxt, prv, chars]


@converter.pre(TokenType.EXPR_LIST_STRING_RTRIM)
def tt_string_rtrim_all(node: MapRTrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = wrap_double_quotes(node.value)
    arr_type = go.TYPES.get(node.next.variable.type)

    return go.BINDINGS_PRE[node.kind, nxt, chars, prv, arr_type]


@converter.pre(TokenType.EXPR_STRING_REPLACE)
def tt_string_replace(node: ReplaceExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    old, new = wrap_double_quotes(node.old), wrap_double_quotes(node.new)

    return go.BINDINGS_PRE[node.kind, nxt, prv, old, new]


@converter.pre(TokenType.EXPR_LIST_STRING_REPLACE)
def tt_string_replace_all(node: MapReplaceExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    old, new = wrap_double_quotes(node.old), wrap_double_quotes(node.new)
    arr_type = go.TYPES.get(node.next.variable.type, "")
    return go.BINDINGS_PRE[node.kind, nxt, prv, old, new, arr_type]


@converter.pre(TokenType.EXPR_STRING_SPLIT)
def tt_string_split(node: SplitExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    sep = wrap_double_quotes(node.sep)
    return go.BINDINGS_PRE[node.kind, nxt, prv, sep]


@converter.pre(TokenType.EXPR_REGEX)
def tt_regex(node: RegexExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    pattern = wrap_backtick(node.pattern)
    group = node.group - 1  # group starts at 0
    return go.BINDINGS_PRE[node.kind, nxt, pattern, prv, group]


@converter.pre(TokenType.EXPR_REGEX_ALL)
def tt_regex_all(node: RegexAllExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    pattern = wrap_backtick(node.pattern)
    return go.BINDINGS_PRE[node.kind, nxt, pattern, prv]


@converter.pre(TokenType.EXPR_REGEX_SUB)
def tt_regex_sub(node: RegexSubExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    pattern = wrap_backtick(node.pattern)
    repl = wrap_double_quotes(node.repl)
    return go.BINDINGS_PRE[node.kind, nxt, pattern, prv, repl]


@converter.pre(TokenType.EXPR_LIST_REGEX_SUB)
def tt_regex_sub_all(node: MapRegexSubExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    pattern = wrap_backtick(node.pattern)
    repl = wrap_double_quotes(node.repl)
    arr_type = go.TYPES.get(node.next.variable.type, "")
    return go.BINDINGS_PRE[node.kind, nxt, pattern, prv, repl, arr_type]


@converter.pre(TokenType.EXPR_LIST_STRING_INDEX)
def tt_string_index(node: IndexStringExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    return go.BINDINGS_PRE[node.kind, nxt, prv, node.value]


@converter.pre(TokenType.EXPR_LIST_DOCUMENT_INDEX)
def tt_doc_index(node: IndexDocumentExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    return go.BINDINGS_PRE[node.kind, nxt, prv, node.value]


@converter.pre(TokenType.EXPR_LIST_JOIN)
def tt_join(node: JoinExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    sep = wrap_double_quotes(node.sep)
    return go.BINDINGS_PRE[node.kind, nxt, prv, sep]


@converter.pre(TokenType.IS_EQUAL)
def tt_is_equal(node: IsEqualExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    value = wrap_double_quotes(node.value)
    msg = wrap_double_quotes(node.msg)
    is_validate = node.parent.kind == TokenType.STRUCT_PRE_VALIDATE
    code = go.BINDINGS_PRE[node.kind, prv, value, msg, is_validate]
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    return code + f"{nxt} := {prv}; "


@converter.pre(TokenType.IS_NOT_EQUAL)
def tt_is_not_equal(node: IsNotEqualExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    value = wrap_double_quotes(node.value)
    msg = wrap_double_quotes(node.msg)
    is_validate = node.parent.kind == TokenType.STRUCT_PRE_VALIDATE

    code = go.BINDINGS_PRE[node.kind, prv, value, msg, is_validate]
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    return code + f"{nxt} := {prv}; "


@converter.pre(TokenType.IS_CONTAINS)
def tt_is_contains(node: IsContainsExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    item = wrap_double_quotes(node.item)
    msg = wrap_double_quotes(node.msg)
    is_validate = node.parent.kind == TokenType.STRUCT_PRE_VALIDATE

    code = go.BINDINGS_PRE[node.kind, prv, item, msg, is_validate]
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    return code + f"{nxt} := {prv}; "


@converter.pre(TokenType.IS_REGEX_MATCH)
def tt_is_regex(node: IsRegexMatchExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    pattern = wrap_backtick(node.pattern)
    msg = wrap_double_quotes(node.msg)
    is_validate = node.parent.kind == TokenType.STRUCT_PRE_VALIDATE
    code = go.BINDINGS_PRE[node.kind, prv, pattern, msg, is_validate]
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    return code + f"{nxt} := {prv}; "


@converter.pre(TokenType.TO_INT)
def tt_to_int(node: ToInteger) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    return (
        f"{nxt}, err := strconv.Atoi({prv}); "
        + "if err != nil"
        + go.BRACKET_START
        + "panic(err); "
        + go.BRACKET_END
    )


@converter.pre(TokenType.TO_INT_LIST)
def tt_to_list_int(node: ToListInteger) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    tmp_var = f"tmp{nxt.title()}"
    each_var = f"i{nxt.title()}"
    arr_type = go.TYPES.get(node.next.variable.type, "")
    return (
        f"{nxt} := make({arr_type}, 0); "
        + f"for _, {tmp_var} := range {prv} "
        + go.BRACKET_START
        + f"{each_var}, err := strconv.Atoi({tmp_var}); "
        + "if err != nil"
        + go.BRACKET_START
        + "panic(err); "
        + go.BRACKET_END
        + f"{nxt} = append({nxt}, {each_var}); "
        + go.BRACKET_END
    )


@converter.pre(TokenType.TO_FLOAT)
def tt_to_float(node: ToFloat) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    return (
        f"{nxt}, err := strconv.ParseFloat({prv}, 64); "
        # todo: return ERR to main?
        + "if err != nil"
        + go.BRACKET_START
        + "panic(err); "
        + go.BRACKET_END
    )


@converter.pre(TokenType.TO_FLOAT_LIST)
def tt_to_list_float(node: ToListFloat) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    tmp_var = f"tmp{nxt.title()}"
    each_var = f"i{nxt.title()}"
    arr_type = go.TYPES.get(node.next.variable.type, "")
    return (
        f"{nxt} := make({arr_type}, 0); "
        + f"for _, {tmp_var} := range {prv} "
        + go.BRACKET_START
        + f"{each_var}, err := strconv.ParseFloat({prv}, 64); "
        # todo: return ERR to main?
        + "if err != nil"
        + go.BRACKET_START
        + "panic(err); "
        + go.BRACKET_END
        + f"{nxt} = append({nxt}, {each_var}); "
        + go.BRACKET_END
    )


# # goquery API
@converter.pre(TokenType.EXPR_CSS)
def tt_css(node: HtmlCssExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    q = wrap_double_quotes(node.query)
    return go.BINDINGS_PRE[node.kind, nxt, prv, q]


@converter.pre(TokenType.EXPR_CSS_ALL)
def tt_css_all(node: HtmlCssAllExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    q = wrap_double_quotes(node.query)
    return go.BINDINGS_PRE[node.kind, nxt, prv, q]


@converter.pre(TokenType.EXPR_TEXT)
def tt_text(node: HtmlTextExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    return go.BINDINGS_PRE[node.kind, nxt, prv]


@converter.pre(TokenType.EXPR_TEXT_ALL)
def tt_text_all(node: HtmlTextAllExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    arr_type = go.TYPES.get(node.next.ret_type, "")
    return go.BINDINGS_PRE[node.kind, nxt, prv, arr_type]


@converter.pre(TokenType.EXPR_RAW)
def tt_raw(node: HtmlRawExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    return go.BINDINGS_PRE[node.kind, nxt, prv]


@converter.pre(TokenType.EXPR_RAW_ALL)
def tt_raw_all(node: HtmlRawAllExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    arr_type = go.TYPES.get(node.next.ret_type, "")
    return go.BINDINGS_PRE[node.kind, nxt, prv, arr_type]


@converter.pre(TokenType.EXPR_ATTR)
def tt_attr(node: HtmlAttrExpression) -> str:
    n = wrap_double_quotes(node.attr)
    prv, nxt = left_right_var_names("value", node.variable)
    return go.BINDINGS_PRE[node.kind, nxt, prv, n]


@converter.pre(TokenType.EXPR_ATTR_ALL)
def tt_attr_all(node: HtmlAttrAllExpression) -> str:
    n = wrap_double_quotes(node.attr)
    prv, nxt = left_right_var_names("value", node.variable)
    return go.BINDINGS_PRE[node.kind, nxt, prv, n]


@converter.pre(TokenType.IS_CSS)
def tt_is_css(node: IsCssExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    q = wrap_double_quotes(node.query)
    msg = wrap_double_quotes(node.msg)
    is_validate = node.parent.kind == TokenType.STRUCT_PRE_VALIDATE

    code = go.BINDINGS_PRE[node.kind, prv, q, msg, is_validate]
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    return code + f"{nxt} := {prv}; "


@converter.pre(TokenType.EXPR_XPATH)
def tt_xpath(_):
    raise NotImplementedError("goquery not support xpath")


@converter.pre(TokenType.EXPR_XPATH_ALL)
def tt_xpath_all(_):
    raise NotImplementedError("goquery not support xpath")


@converter.pre(TokenType.IS_XPATH)
def tt_is_xpath(_):
    raise NotImplementedError("goquery not support xpath")
