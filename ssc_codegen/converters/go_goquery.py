# FIXME Nested return ARRAY
# FIXME assert return type + err
# FIXME docstring indent (naive imp)
from .base import BaseCodeConverter, left_right_var_names
from .utils import to_upper_camel_case as up_camel, wrap_double_quotes as wrap_dq, wrap_backtick, \
    find_nested_associated_typedef_by_typedef_field, find_nested_associated_typedef_by_st_field_fn, have_assert_expr, \
    find_st_field_fn_by_call_st_fn, have_start_parse_assert_expr, have_call_expr_assert_expr
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
    VariableType.STRING: "string",
    VariableType.LIST_STRING: "[]string",
    VariableType.OPTIONAL_STRING: "*string",
    VariableType.OPTIONAL_LIST_STRING: "*[]string"
}

MAGIC_METHODS = {"__KEY__": "Key",
                 "__VALUE__": "Value",
                 "__ITEM__": "Item",
                 "__PRE_VALIDATE__": "preValidate",
                 "__SPLIT_DOC__": "splitDoc",
                 "__START_PARSE__": "Parse"
                 }


@converter.pre(TokenType.TYPEDEF)
def tt_typedef(node: TypeDef):
    head = f"type T{node.name} struct " + '{\n'
    body = ""
    for field in node.body:
        name = up_camel(MAGIC_METHODS.get(field.name, field.name))
        if field.type == VariableType.NESTED:
            associated_typedef = find_nested_associated_typedef_by_typedef_field(field)
            if associated_typedef.struct.type in (StructType.FLAT_LIST, StructType.LIST, StructType.DICT):
                type_ = f"[]T{associated_typedef.name}"  # noqa
            else:
                type_ = f"T{associated_typedef.name}"  # noqa
            body += f'{name} {type_}'
        else:
            body += f'{name} {TYPES.get(field.type)}'
        body += '\n'
    return head + body + '\n}'


@converter.pre(TokenType.STRUCT)
def tt_struct(node: StructParser) -> str:
    return f'type {node.name} struct {{ doc *goquery.Document }}'


@converter.pre(TokenType.STRUCT_INIT)
def tt_struct_init(node: StructInit) -> str:
    return ''


@converter.pre(TokenType.DOCSTRING)
def tt_docstring(node: Docstring) -> str:
    if node.value:
        return f'\n'.join('// ' + line for line in node.value.split('\n'))
    return ''


@converter.pre(TokenType.IMPORTS)
def tt_imports(_: ModuleImports) -> str:
    buildin_imports = 'package sscCodegen\n\n'  # TODO: provide package name API
    buildin_imports += 'import (\n'
    buildin_imports += '"fmt"\n'
    buildin_imports += '"regexp"\n'
    buildin_imports += '"strings"\n'
    buildin_imports += '"slices"\n'
    buildin_imports += '"github.com/PuerkitoBio/goquery"\n'
    buildin_imports += ')'
    return buildin_imports


@converter.pre(TokenType.EXPR_RETURN)
def tt_ret(node: ReturnExpression) -> str:
    _, nxt = left_right_var_names("value", node.variable)
    if have_assert_expr(node.parent):
        return f"return {nxt}, nil "
    return f"return {nxt} "


@converter.pre(TokenType.EXPR_NO_RETURN)
def tt_no_ret(_: NoReturnExpression) -> str:
    return "return nil; "


@converter.pre(TokenType.EXPR_NESTED)
def tt_nested(node: NestedExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    # HACK: make selection type as document
    code = f"doc{node.variable.num} := goquery.NewDocumentFromNode({prv}.Nodes[0]); "
    code += f"st{node.variable.num} := {node.schema}{{ doc{node.variable.num} }}; "
    return code + f"{nxt} := st{node.variable.num}.Parse(); "


@converter.pre(TokenType.STRUCT_PRE_VALIDATE)
def tt_pre_validate(node: PreValidateFunction) -> str:
    return f"func (p *{node.parent.name}) {MAGIC_METHODS.get(node.name)}(value *goquery.Selection) error {{"


@converter.post(TokenType.STRUCT_PRE_VALIDATE)
def tt_pre_validate(_: PreValidateFunction) -> str:
    return '}'


@converter.pre(TokenType.STRUCT_PART_DOCUMENT)
def tt_part_document(node: PartDocFunction):
    # check if need return error
    if have_assert_expr(node):
        code = f"func (p *{node.parent.name}) {MAGIC_METHODS.get(node.name)}(value *goquery.Selection)"
        code += '(*goquery.Selection, error) {'
        return code
    return (f"func (p *{node.parent.name}) {MAGIC_METHODS.get(node.name)}(value *goquery.Selection) *goquery.Selection"
            + ' {')


@converter.post(TokenType.STRUCT_PART_DOCUMENT)
def tt_part_document(_: PartDocFunction):
    return '}'


@converter.pre(TokenType.STRUCT_FIELD)
def tt_function(node: StructFieldFunction) -> str:
    name = up_camel(MAGIC_METHODS.get(node.name, node.name))
    if node.ret_type == VariableType.NESTED:
        # serialize all to structs
        # find associated typedef node by return nested schema name
        associated_typedef: TypeDef = find_nested_associated_typedef_by_st_field_fn(node)
        if associated_typedef.struct.type in (StructType.FLAT_LIST, StructType.LIST, StructType.DICT):
            type_ = f"[]T{node.body[-2].schema}"  # noqa
        else:
            type_ = f"T{node.body[-2].schema}"  # noqa
    else:
        type_ = TYPES.get(node.ret_type)

    # check if need return error
    ret_type = f"({type_}, error)" if have_assert_expr(node) else type_
    return f"func (p *{node.parent.name}) Parse{name}(value *goquery.Selection) {ret_type} " + '{'


@converter.post(TokenType.STRUCT_FIELD)
def tt_function(_: StructFieldFunction) -> str:
    return '}'


@converter.pre(TokenType.STRUCT_PARSE_START)
def tt_start_parse(node: StartParseFunction) -> str:
    # TODO base struct provide name API
    head = f"func (p *{node.parent.name}) {MAGIC_METHODS.get(node.name)}() "
    if node.type in (StructType.LIST, StructType.FLAT_LIST, StructType.DICT):
        type_ = f"[]T{node.parent.name}"
    else:
        type_ = f"T{node.parent.name}"

    if node.name == '__START_PARSE__' and have_start_parse_assert_expr(node):
        type_ = f"{head} ({type_}, error) {{"
    elif any(have_assert_expr(fn) for fn in node.parent.body if fn.kind == TokenType.STRUCT_FIELD):
        return f"{head} ({type_}, error) {{"
    return f"{head} {type_} {{"


@converter.post(TokenType.STRUCT_PARSE_START)
def tt_start_parse(node: StartParseFunction):
    code = ""
    if any(f.name == '__PRE_VALIDATE__' for f in node.body):
        n = MAGIC_METHODS.get('__PRE_VALIDATE__')
        code += f"err := p.{n}(p.doc.Selection); "
        code += f'if err != nil {{ return, T{node.parent.name} err; }}'
    match node.type:
        case StructType.ITEM:
            body = ""
            for field in node.body:
                if field.name in RESERVED_METHODS:
                    continue
                # golang required manually handle errors

                if node.name not in RESERVED_METHODS and have_assert_expr(find_st_field_fn_by_call_st_fn(field)):
                    body += f"{field.name}Raw, err := p.Parse{up_camel(field.name)}(p.doc.Selection); "
                    body += f"if err != nil {{ return T{node.parent.name}, err; }}"
                else:
                    body += f"{field.name}Raw := p.Parse{up_camel(field.name)}(p.doc.Selection); "
            st_code = f"item := T{node.parent.name}{{"
            st_code += ', '.join(f'{f.name}Raw' for f in node.body if f.name not in RESERVED_METHODS) + '}; '
            if have_start_parse_assert_expr(node):
                body += st_code + 'return item, nil; }'
            else:
                body += st_code + 'return item; }'

        case StructType.LIST:
            part_m = MAGIC_METHODS.get('__SPLIT_DOC__')

            body = f"items :=  make([]T{node.parent.name}, 0); "
            body += f'for _, i := range p.{part_m}(p.doc.Selection).EachIter() {{ '

            for field in node.body:
                if field.name in RESERVED_METHODS:
                    continue
                # golang required manually handle errors
                if field.name not in RESERVED_METHODS and have_assert_expr(find_st_field_fn_by_call_st_fn(field)):
                    body += f"{field.name}Raw, err := p.Parse{up_camel(field.name)}(i); "
                    body += f"if err != nil {{ return T{node.parent.name}, err; }}"
                else:
                    body += f"{field.name}Raw := p.Parse{up_camel(field.name)}(i); "
            st_code = f"item := T{node.parent.name}{{"
            st_code += ', '.join(f'{f.name}Raw' for f in node.body if f.name not in RESERVED_METHODS) + '}; '
            body += "append(items, item); "
            if have_start_parse_assert_expr(node):
                body += st_code + '} return item, nil; }'
            else:
                body += st_code + '} return item; }'
        case StructType.DICT:
            key_m = MAGIC_METHODS.get('__KEY__')
            value_m = MAGIC_METHODS.get('__VALUE__')
            part_m = MAGIC_METHODS.get('__SPLIT_DOC__')
            fn_key = [fn for fn in node.body if fn.name == "__KEY__"][0]
            fn_value = [fn for fn in node.body if fn.name == "__VALUE__"][0]

            body = f"items := make([]T{node.parent.name}, 0); "
            body += f'for _, i := range p.{part_m}(p.doc.Selection).EachIter() {{ '
            if have_call_expr_assert_expr(fn_key):
                body += f"raw_key, err := p.Parse{key_m}(i); "
                body += f"if err != nil {{ return T{node.parent.name}, err; }}"
            else:
                body += f"raw_key := p.Parse{key_m}(i); "
            if have_call_expr_assert_expr(fn_value):
                body += f"raw_value, err := p.Parse{key_m}(i); "
                body += f"if err != nil {{ return T{node.parent.name}, err; }}"
            else:
                body += f"raw_value := p.Parse{value_m}(i); "

            body += f"item := T{node.parent.name}{{raw_key, raw_value }}; "
            body += 'items = append(items, item); '
            body += '}'
            if have_start_parse_assert_expr(node):
                body += "return items, nil; }"
            else:
                body += 'return items; }'
        case StructType.FLAT_LIST:
            item_m = MAGIC_METHODS.get('__ITEM__')
            part_m = MAGIC_METHODS.get('__SPLIT_DOC__')
            fn_item = [fn for fn in node.body if fn.name == "__ITEM__"][0]

            body = f"items := make([]T{node.parent.name}, 0); "
            body += f'for _, i := range p.{part_m}(p.doc.Selection).EachIter() {{ '
            if have_call_expr_assert_expr(fn_item):
                body += f'rawItem, err := p.Parse{item_m}(i); '
                body += f"if err != nil {{ return T{node.parent.name}, err; }}"
            else:
                body += f'rawItem := p.Parse{item_m}(i); '

            body += f'item := T{node.parent.name}{{ rawItem }}; '
            body += f'items = append(items, item); '
            body += '} return items; }'
        case _:
            raise NotImplementedError("Unknown struct type")
    return code + body


@converter.pre(TokenType.EXPR_DEFAULT)
def tt_default(node: DefaultValueWrapper) -> str:
    return "// TODO DEFAULT IMPL"


@converter.post(TokenType.EXPR_DEFAULT)
def tt_default(node: DefaultValueWrapper) -> str:
    val = wrap_dq(node.value) if isinstance(node.value, str) else 'nil'
    return f"return {val}; "


@converter.pre(TokenType.EXPR_STRING_FORMAT)
def tt_string_format(node: FormatExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    template = node.fmt.replace('{{}}', "%s")
    template = wrap_dq(template)
    return nxt + f' := fmt.Sprintf({template}, {prv}); '


@converter.pre(TokenType.EXPR_LIST_STRING_FORMAT)
def tt_string_format_all(node: MapFormatExpression) -> str:
    # https://stackoverflow.com/a/33726830
    #     list := []int{1,2,3}
    #
    #     var list2 []string
    #     for _, x := range list {
    #         list2 = append(list2, strconv.Itoa(x * 2))
    #     }
    prv, nxt = left_right_var_names("value", node.variable)
    code = f"{nxt} := []{TYPES.get(node.next.variable.type)}{{}}; "

    template = wrap_dq(node.fmt.replace('{{}}', "%s"))
    i_var = f"i{node.variable.num}"
    map_code = f"fmt.Sprintf({template}, {i_var})"

    code += f"for {i_var} := range {prv}" + '{' + f"{nxt} = append({nxt}, {map_code});" + '}'
    return code


@converter.pre(TokenType.EXPR_STRING_TRIM)
def tt_string_trim(node: TrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = wrap_dq(node.value)
    return f"{nxt} := strings.Trim({prv}, {chars})"


@converter.pre(TokenType.EXPR_LIST_STRING_TRIM)
def tt_string_trim_all(node: MapTrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = wrap_dq(node.value)

    code = f"{nxt} := []{TYPES.get(node.next.variable.type)}" + "{}; "
    i_var = f"i{node.variable.num}"
    map_code = f"strings.Trim({i_var}, {chars})"

    code += f"for {i_var} := range {prv}" + '{' + f"{nxt} = append({nxt}, {map_code});" + '}'
    return code


@converter.pre(TokenType.EXPR_STRING_LTRIM)
def tt_string_ltrim(node: LTrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = wrap_dq(node.value)
    return f"{nxt} := strings.TrimLeft({prv}, {chars}); "


@converter.pre(TokenType.EXPR_LIST_STRING_LTRIM)
def tt_string_ltrim_all(node: MapLTrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = wrap_dq(node.value)

    code = f"{nxt} := []{TYPES.get(node.next.variable.type)}" + "{}; "
    i_var = f"i{node.variable.num}"
    map_code = f"strings.TrimLeft({i_var}, {chars})"

    code += f"for {i_var} := range {prv}" + '{' + f"{nxt} = append({nxt}, {map_code});" + '}'
    return code


@converter.pre(TokenType.EXPR_STRING_RTRIM)
def tt_string_rtrim(node: RTrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = wrap_dq(node.value)
    return f"{nxt} := strings.TrimRight({prv}, {chars}); "


@converter.pre(TokenType.EXPR_LIST_STRING_RTRIM)
def tt_string_rtrim_all(node: MapRTrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = wrap_dq(node.value)

    code = f"{nxt} := []{TYPES.get(node.next.variable.type)}" + "{}; "
    i_var = f"i{node.variable.num}"
    map_code = f"strings.TrimRight({i_var}, {chars})"

    code += f"for {i_var} := range {prv}" + '{' + f"{nxt} = append({nxt}, {map_code});" + '}'
    return code


@converter.pre(TokenType.EXPR_STRING_REPLACE)
def tt_string_replace(node: ReplaceExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    old, new = wrap_dq(node.old), wrap_dq(node.new)
    return f"{nxt} := strings.Replace({prv}, {old}, {new}, -1); "


@converter.pre(TokenType.EXPR_LIST_STRING_REPLACE)
def tt_string_replace_all(node: MapReplaceExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    old, new = wrap_dq(node.old), wrap_dq(node.new)

    code = f"{nxt} := []{TYPES.get(node.next.variable.type)}" + "{}; "
    i_var = f"i{node.variable.num}"
    map_code = f"strings.Replace({i_var}, {old}, {new}, -1)"

    code += f"for {i_var} := range {prv}" + '{' + f"{nxt} = append({nxt}, {map_code});" + '}'
    return code


@converter.pre(TokenType.EXPR_STRING_SPLIT)
def tt_string_split(node: SplitExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    sep = wrap_dq(node.sep)
    return f"{nxt} := strings.Split({prv}, {sep});  "


@converter.pre(TokenType.EXPR_REGEX)
def tt_regex(node: RegexExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    pattern = wrap_backtick(node.pattern)
    group = node.group - 1
    return f'{nxt} := regexp.MustCompile({pattern}).FindStringSubmatch({prv})[{group}]; '


@converter.pre(TokenType.EXPR_REGEX_ALL)
def tt_regex_all(node: RegexAllExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    pattern = wrap_backtick(node.pattern)

    return f"{nxt} := regexp.MustCompile({pattern}).FindStringSubmatch({prv}); "


@converter.pre(TokenType.EXPR_REGEX_SUB)
def tt_regex_sub(node: RegexSubExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    pattern = wrap_backtick(node.pattern)
    repl = wrap_dq(node.repl)
    return f"{nxt} := regexp.MustCompile({pattern}).ReplaceAll({prv}, {repl}); "


@converter.pre(TokenType.EXPR_LIST_REGEX_SUB)
def tt_regex_sub_all(node: MapRegexSubExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    pattern = wrap_backtick(node.pattern)
    repl = wrap_dq(node.repl)

    code = f"{nxt} := []{TYPES.get(node.next.variable.type)}" + "{}; "
    i_var = f"i{node.variable.num}"
    map_code = f"regexp.MustCompile({pattern}).ReplaceAll({i_var}, {repl})"
    code += f"for {i_var} := range {prv}" + '{' + f"{nxt} = append({nxt}, {map_code});" + '}'

    return code


@converter.pre(TokenType.EXPR_LIST_STRING_INDEX)
def tt_string_index(node: IndexStringExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    return f"{nxt} := {prv}[{node.value}]; "


@converter.pre(TokenType.EXPR_LIST_DOCUMENT_INDEX)
def tt_doc_index(node: IndexDocumentExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    return f"{nxt} := {prv}[{node.value}]; "


@converter.pre(TokenType.EXPR_LIST_JOIN)
def tt_join(node: JoinExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    sep = wrap_dq(node.sep)
    return f"{nxt} := strings.Join({prv}, {sep}); "


@converter.pre(TokenType.IS_EQUAL)
def tt_is_equal(node: IsEqualExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    value = wrap_dq(node.value)
    msg = wrap_dq(node.msg)
    code = f'if !({prv} == {value}){{return T{node.parent.name}{{}}, fmt.Errorf({msg});}}'
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += f'{nxt} := {prv}; '
    return code


@converter.pre(TokenType.IS_NOT_EQUAL)
def tt_is_not_equal(node: IsNotEqualExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    value = wrap_dq(node.value)
    msg = wrap_dq(node.msg)

    code = f'if !({prv} != {value}){{return T{node.parent.name}{{}}, fmt.Errorf({msg});}} '
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += f'{nxt} := {prv}; '
    return code


@converter.pre(TokenType.IS_CONTAINS)
def tt_is_contains(node: IsContainsExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    item = wrap_dq(node.item)
    msg = wrap_dq(node.msg)

    code = f'if !(slices.Contains({prv}, {item})){{return T{node.parent.parent.name}{{}}, fmt.Errorf({msg});}}'
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += f"{nxt} := {prv}; "
    return code


@converter.pre(TokenType.IS_REGEX_MATCH)
def tt_is_regex(node: IsRegexMatchExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    pattern = wrap_backtick(node.pattern)
    msg = wrap_dq(node.msg)

    err_var = f"err{node.variable.num}"
    code = f"_, {err_var} := regexp.Match({pattern}, []byte({prv})); "
    code += f"if {err_var} != nil{{ return T{node.parent.parent.name}{{}}, "
    code += f', fmt.Errorf("%s, %q", {err_var}, {msg}); }}'
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += f"{nxt} := {prv}; "
    return code


# BS4 API
@converter.pre(TokenType.EXPR_CSS)
def tt_css(node: HtmlCssExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)

    q = wrap_dq(node.query)
    code = f"{nxt} := {prv}.Find({q}).First(); "
    return code


@converter.pre(TokenType.EXPR_CSS_ALL)
def tt_css_all(node: HtmlCssAllExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    q = wrap_dq(node.query)
    code = f"{nxt} := {prv}.Find({q}); "

    return code


@converter.pre(TokenType.EXPR_XPATH)
def tt_xpath(_: HtmlXpathExpression) -> str:
    raise NotImplementedError("goquery not support xpath")


@converter.pre(TokenType.EXPR_XPATH_ALL)
def tt_xpath_all(_: HtmlXpathAllExpression) -> str:
    raise NotImplementedError("bs4 not support xpath")


@converter.pre(TokenType.EXPR_TEXT)
def tt_text(node: HtmlTextExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    return f"{nxt} := {prv}.Text(); "


@converter.pre(TokenType.EXPR_TEXT_ALL)
def tt_text_all(node: HtmlTextAllExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    cb_var = f"e{node.variable.num}"

    code = f"var {nxt} []string; "
    code += f"{prv}.Each((func(i int, {cb_var} *goquery.Selection) " + "{"
    code += f'{nxt} = append({nxt}, {cb_var}.Text()); ' + "}); "
    return code


@converter.pre(TokenType.EXPR_RAW)
def tt_raw(node: HtmlRawExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)

    return f"{nxt}, _ := {prv}.Html(); "


@converter.pre(TokenType.EXPR_RAW_ALL)
def tt_raw_all(node: HtmlRawAllExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    cb_var = f"e{node.variable.num}"
    attr_var = f"attr{node.variable.num}"

    code = f"var {nxt} []string; "
    code += f'{prv}.Each((func(i int, ' + cb_var + " *goquery.Selection { "
    code += f"{attr_var}, _ := " + cb_var + '.Html(); '
    code += f"{nxt} = append({nxt}, {attr_var}); "
    code += '}); '
    # 	var raws []string
    # 	el.Each(func(i int, sel *goquery.Selection) {
    # 		html, _ := sel.Html()
    # 		raws = append(raws, html)
    # 	})
    return code


@converter.pre(TokenType.EXPR_ATTR)
def tt_attr(node: HtmlAttrExpression):
    n = wrap_dq(node.attr)
    prv, nxt = left_right_var_names("value", node.variable)
    return f"{nxt}, _ := {prv}.Attr({n}); "


@converter.pre(TokenType.EXPR_ATTR_ALL)
def tt_attr_all(node: HtmlAttrAllExpression):
    n = wrap_dq(node.attr)
    prv, nxt = left_right_var_names("value", node.variable)
    attr_var = f"attr{node.variable.num}"
    cb_var = f"e{node.variable.num}"

    code = f'var {nxt} []string; '
    code += prv + ".Each(func(i int, " + cb_var + " *goquery.Selection) { "
    code += attr_var + ', _ := ' + cb_var + f".Attr({n}); "
    code += nxt + ' = ' + f'append({prv}, {attr_var})' + '}); '
    # var NEXT []string
    # 	PREV.Each(func(i int, CB_VAR *goquery.Selection) {
    # 		ATTR_VAR, _ := sel.Attr(NAME)
    # 		attrs = append(attrs, ATTR_VAR)
    # 	})
    return code


@converter.pre(TokenType.IS_CSS)
def tt_is_css(node: IsCssExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    q = wrap_dq(node.query)
    msg = wrap_dq(node.msg)

    code = f"if {prv}.Find({q}).Length() == 0 {{ return T{node.parent.parent.name}{{}}, fmt.Errorf({msg}); }} "
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += f"{nxt} := {prv}; "
    return code


@converter.pre(TokenType.IS_XPATH)
def tt_is_xpath(_: IsXPathExpression):
    raise NotImplementedError("goquery not support xpath")
