"""code parts for go codegen"""

from typing import TYPE_CHECKING

from ssc_codegen.converters.utils import (
    find_callfn_field_node_by_name,
    find_field_nested_struct,
    find_tdef_field_node_by_name,
    to_upper_camel_case,
)
from ssc_codegen.tokens import StructType, TokenType, VariableType

from .utils import (
    TemplateBindings,
)

if TYPE_CHECKING:
    from ssc_codegen.ast_ssc import (
        StartParseFunction,
        StructFieldFunction,
        TypeDef,
    )


TYPES = {
    VariableType.STRING: "string",
    VariableType.LIST_STRING: "[]string",
    VariableType.OPTIONAL_STRING: "*string",
    VariableType.OPTIONAL_LIST_STRING: "*[]string",
    VariableType.NULL: "nil",
    VariableType.INT: "int",
    VariableType.OPTIONAL_INT: "*int",
    VariableType.LIST_INT: "[]int",
    VariableType.FLOAT: "float64",
    VariableType.OPTIONAL_FLOAT: "*float64",
    VariableType.LIST_FLOAT: "[]float64",
    VariableType.OPTIONAL_LIST_FLOAT: "*[]float64",
}


MAGIC_METHODS = {
    "__KEY__": "Key",
    "__VALUE__": "Value",
    "__ITEM__": "Item",
    "__PRE_VALIDATE__": "preValidate",
    "__SPLIT_DOC__": "splitDoc",
    "__START_PARSE__": "Parse",
}

# hardcoded undocumented template package placeholder
# in cli, set name as directory name
PACKAGE = "package $PACKAGE$"


BINDINGS_PRE = TemplateBindings()
BINDINGS_POST = TemplateBindings()


def _docstring(docstring: str) -> str:
    # todo: provide node for insert func/struct name
    return "\n".join("// " + line for line in docstring.split("\n"))


BINDINGS_PRE[TokenType.DOCSTRING] = _docstring

# TODO: add github.com/antchfx/htmlquery API (xpath)
# in current stage project support only goquery
BINDINGS_PRE[TokenType.IMPORTS] = """
import (
    "fmt"
    "regexp"
    "strings"
    "slices"
    "strconv"
    "github.com/PuerkitoBio/goquery"
)
"""

BRACKET_START = "{"
BRACKET_END = "}"

# try/catch effect realisation via anon defer func
# if code block throw exception - set default value
# example:
# // divide(10, 0) -> 9000
# // divide(10, 2) -> 5
# func divide(a, b int) (result int) {
# 	defer func() {
# 		if r := recover(); r != nil {result = 9000}
# 	}()
# 	return a / b
# }
BINDINGS_PRE[TokenType.EXPR_DEFAULT_START] = lambda value: (
    "defer func() "
    + BRACKET_START
    + "if r := recover(); r != nil"
    + BRACKET_START
    + f"result = {value}; "
    + BRACKET_END
    + BRACKET_END
    + "();"
)


def _part_doc_func(parent_name: str, is_err: bool = False) -> str:
    method_name = MAGIC_METHODS.get("__SPLIT_DOC__", "")
    if is_err:
        # func (p *{}) {}(value *goquery.Selection) (*goquery.Selection, error) {
        return (
            "func (p *"
            + parent_name
            + ") "
            + method_name
            + "(value *goquery.Selection) (*goquery.Selection, error) "
            + BRACKET_START
        )
    # func (p *{}) {}(value *goquery.Selection) (*goquery.Selection) {
    return (
        "func (p *"
        + parent_name
        + ") "
        + method_name
        + "(value *goquery.Selection) (*goquery.Selection)"
        + BRACKET_START
    )


BINDINGS_PRE[TokenType.STRUCT_PART_DOCUMENT] = _part_doc_func
BINDINGS_PRE[TokenType.TYPEDEF] = (
    lambda t_name: f"type {t_name} struct {BRACKET_START}"
)
BINDINGS_POST[TokenType.TYPEDEF] = lambda: BRACKET_END
BINDINGS_PRE[TokenType.TYPEDEF_FIELD] = (
    lambda name, t_type, json_anchor: f"{name} {t_type} {json_anchor}; "
)
"""FIELD_NAME TYPE JSON ANCHOR"""
BINDINGS_PRE[TokenType.STRUCT_PRE_VALIDATE] = lambda st_ptr: (
    f"func (p *{st_ptr}) {MAGIC_METHODS.get('__PRE_VALIDATE__', '')}(value *goquery.Selection) error {BRACKET_START}"
)


def _return_expr(var: str | None = None, is_err: bool = False) -> str:
    # return value
    # return value, err
    # return value, nil
    if var is None:
        var = "nil"
    if is_err:
        return f"return {var}, nil; "
    return f"return {var}; "


BINDINGS_PRE[TokenType.EXPR_RETURN] = _return_expr
BINDINGS_PRE[TokenType.EXPR_NO_RETURN] = "return nil; "
BINDINGS_PRE[TokenType.EXPR_STRING_FORMAT] = (
    lambda nxt, fmt, prv: f"{nxt} := fmt.Sprintf({fmt}, {prv}); "
)


def _str_fmt_map(nxt: str, fmt: str, prv: str, arr_type: str) -> str:
    # https://stackoverflow.com/a/33726830
    #     <PREV ARRAY VAR> := []<T1>{1,2,3}
    #
    #     var <NEW ARRAY VAR> []<T2>
    #     for _, x := range <PREV ARRAY VAR> {
    #         <NEW ARRAY VAR> = append(<NEW ARRAY VAR>, <MAP_CODE>)
    #     }
    tmp_var = f"tmp{nxt.title()}"
    return (
        f"{nxt} := make({arr_type}, 0); "
        + f"for _, {tmp_var} := range {prv} "
        + BRACKET_START
        + f"{nxt} = append({nxt}, fmt. Sprintf({fmt}, {tmp_var})); "
        + BRACKET_END
    )


BINDINGS_PRE[TokenType.EXPR_LIST_STRING_FORMAT] = _str_fmt_map
BINDINGS_PRE[TokenType.EXPR_STRING_TRIM] = "{} := strings.Trim({}, {}); "


def _str_trim_map(nxt: str, chars: str, prv: str, arr_type: str) -> str:
    tmp_var = f"tmp{nxt.title()}"
    return (
        f"{nxt} := make({arr_type}, 0); "
        + f"for _, {tmp_var} := range {prv} "
        + BRACKET_START
        + f"{nxt} = append({nxt}, strings.Trim({tmp_var}, {chars})); "
        + BRACKET_END
    )


BINDINGS_PRE[TokenType.EXPR_LIST_STRING_TRIM] = _str_trim_map
BINDINGS_PRE[TokenType.EXPR_STRING_LTRIM] = "{} := strings.TrimLeft({}, {}); "


def _str_ltrim_map(nxt: str, chars: str, prv: str, arr_type: str) -> str:
    tmp_var = f"tmp{nxt.title()}"
    return (
        f"{nxt} := make({arr_type}, 0); "
        + f"for _, {tmp_var} := range {prv} "
        + BRACKET_START
        + f"{nxt} = append({nxt}, strings.TrimLeft({tmp_var}, {chars})); "
        + BRACKET_END
    )


BINDINGS_PRE[TokenType.EXPR_LIST_STRING_LTRIM] = _str_ltrim_map
BINDINGS_PRE[TokenType.EXPR_STRING_RTRIM] = "{} := strings.TrimRight({}, {}); "


def _str_rtrim_map(nxt: str, chars: str, prv: str, arr_type: str) -> str:
    tmp_var = f"tmp{nxt.title()}"
    return (
        f"{nxt} := make({arr_type}, 0); "
        + f"for _, {tmp_var} := range {prv} "
        + BRACKET_START
        + f"{nxt} = append({nxt}, strings.TrimRight({tmp_var}, {chars})); "
        + BRACKET_END
    )


BINDINGS_PRE[TokenType.EXPR_LIST_STRING_RTRIM] = _str_rtrim_map
BINDINGS_PRE[TokenType.EXPR_STRING_REPLACE] = (
    "{} := strings.Replace({}, {}, {}, -1); "
)


def _str_repl_map(nxt: str, prv: str, old: str, new: str, arr_type: str) -> str:
    tmp_var = f"tmp{nxt.title()}"
    return (
        f"{nxt} := make({arr_type}, 0); "
        + f"for _, {tmp_var} := range {prv} "
        + BRACKET_START
        + f"{nxt} = append({nxt}, strings.Replace({tmp_var}, {old}, {new}, -1); "
        + BRACKET_END
    )


BINDINGS_PRE[TokenType.EXPR_STRING_SPLIT] = "{} := strings.Split({}, {}); "
BINDINGS_PRE[TokenType.EXPR_REGEX] = (
    "{} := regexp.MustCompile({}).FindStringSubmatch({})[{}]; "
)
BINDINGS_PRE[TokenType.EXPR_REGEX_ALL] = (
    "{} := regexp.MustCompile({}).FindStringSubmatch({}); "
)
BINDINGS_PRE[TokenType.EXPR_REGEX_SUB] = (
    "{} := string(regexp.MustCompile({}).ReplaceAll([]byte({}), []byte({})));"
)


def _str_re_sub_map(
    nxt: str, pattern: str, prv: str, repl: str, arr_type: str
) -> str:
    tmp_var = f"tmp{nxt.title()}"
    return (
        f"{nxt} := make({arr_type}, 0); "
        + f"for _, {tmp_var} := range {prv} "
        + BRACKET_START
        + f"{nxt} = append({nxt}, string(regexp.MustCompile({pattern}).ReplaceAll([]byte({prv}), []byte({repl}))); "
        + BRACKET_END
    )


BINDINGS_PRE[TokenType.EXPR_LIST_REGEX_SUB] = _str_re_sub_map
BINDINGS_PRE[TokenType.EXPR_LIST_STRING_INDEX] = "{} := {}[{}]; "
BINDINGS_PRE[TokenType.EXPR_LIST_DOCUMENT_INDEX] = "{} := {}[{}]; "
BINDINGS_PRE[TokenType.EXPR_LIST_JOIN] = "{} := strings.Join({}, {}); "


def _assert_eq(
    prv: str, value: str, msg: str, is_pre_validate: bool = False
) -> str:
    if is_pre_validate:
        return (
            f"if !({prv} == {value})"
            + BRACKET_START
            + f"panic(fmt.Errorf({msg})); "
            + BRACKET_END
        )
    return (
        f"if !({prv} == {value})"
        + BRACKET_START
        + f"panic(fmt.Errorf({msg})); "
        + BRACKET_END
    )


BINDINGS_PRE[TokenType.IS_EQUAL] = _assert_eq


def _assert_ne(
    prv: str, value: str, msg: str, is_pre_validate: bool = False
) -> str:
    if is_pre_validate:
        return (
            f"if {prv} == {value}"
            + BRACKET_START
            + f"panic(fmt.Errorf({msg})); "
            + BRACKET_END
        )
    return (
        f"if {prv} == {value}"
        + BRACKET_START
        + f"panic(fmt.Errorf({msg})); "
        + BRACKET_END
    )


BINDINGS_PRE[TokenType.IS_NOT_EQUAL] = _assert_ne


def _assert_in(
    prv: str, item: str, msg: str, is_pre_validate: bool = False
) -> str:
    if is_pre_validate:
        return (
            f"if !(slices.Contains({prv}, {item}))"
            + BRACKET_START
            + f"panic(fmt.Errorf({msg})); "
            + BRACKET_END
        )
    return (
        f"if !(slices.Contains({prv}, {item}))"
        + BRACKET_START
        + f"panic(fmt.Errorf({msg})); "
        + BRACKET_END
    )


BINDINGS_PRE[TokenType.IS_CONTAINS] = _assert_in


def _is_regex_match(
    prv: str, pattern: str, msg: str, is_pre_validate: bool = False
) -> str:
    err_var = f"err{prv.title()}"
    if is_pre_validate:
        return (
            f"_, {err_var} := regexp.Match({pattern}, [] byte({prv})); "
            + f"if {err_var} != nil"
            + BRACKET_START
            + f"panic(fmt.Errorf({msg})); "
            + BRACKET_END
        )
    return (
        f"_, {err_var} := regexp.Match({pattern}, [] byte({prv})); "
        + f"if {err_var} != nil"
        + BRACKET_START
        + f"panic(fmt.Errorf({msg})); "
        + BRACKET_END
    )


BINDINGS_PRE[TokenType.IS_REGEX_MATCH] = _is_regex_match
BINDINGS_PRE[TokenType.EXPR_CSS] = "{} := {}.Find({}).First(); "
BINDINGS_PRE[TokenType.EXPR_CSS_ALL] = "{} := {}.Find({}); "
BINDINGS_PRE[TokenType.EXPR_TEXT] = "{} := {}.Text(); "


def _text_map(nxt: str, prv: str, arr_type: str) -> str:
    tmp_var = f"tmp{nxt.title()}"
    return (
        f"{nxt} := make({arr_type}, 0); "
        + f"for _, {tmp_var} := range {prv} "
        + BRACKET_START
        + f"{nxt} = append({nxt}, {tmp_var}.Text()); "
        + BRACKET_END
    )


BINDINGS_PRE[TokenType.EXPR_TEXT_ALL] = _text_map
BINDINGS_PRE[TokenType.EXPR_RAW] = "{}, _ := {}.Html(); "


def _raw_map(nxt: str, prv: str, arr_type: str) -> str:
    tmp_var = f"tmp{nxt.title()}"
    raw_var = f"raw{nxt.title()}"
    return (
        f"{nxt} := make({arr_type}, 0); "
        + f"for _, {tmp_var} := range {prv} "
        + BRACKET_START
        + f"{raw_var}, _ := {tmp_var}.Html(); "
        + f"{nxt} = append({nxt}, {raw_var}); "
        + BRACKET_END
    )


BINDINGS_PRE[TokenType.EXPR_RAW_ALL] = _raw_map
BINDINGS_PRE[TokenType.EXPR_ATTR] = lambda nxt, prv, attr: (
f"{nxt}, isExists := {prv}.Attr({attr}); "
+ "if !isExists" + BRACKET_START
+ f'panic(fmt.Errorf("attr `%s` not exists in `%s`", {attr}, {prv})); '
+ BRACKET_END
)


def _attr_map(nxt: str, prv: str, attr: str, arr_type: str) -> str:
    tmp_var = f"tmp{nxt.title()}"
    raw_var = f"attr{nxt.title()}"
    return (
        f"{nxt} := make({arr_type}, 0); "
        + f"for _, {tmp_var} := range {prv} "
        + BRACKET_START
        + f"{raw_var}, isExists := {tmp_var}.Attr({attr}); "

        + "if !isExists"
        + BRACKET_START
        + f'panic(fmt.Errorf("attr `%s` not exists in `%s`", {attr}, {tmp_var})); '
        + BRACKET_END

        + f"{nxt} = append({nxt}, {raw_var}); "
        + BRACKET_END
    )


BINDINGS_PRE[TokenType.EXPR_ATTR_ALL] = _attr_map


def _is_css(
    prv: str, query: str, msg: str, is_pre_validate: bool = False
) -> str:
    if is_pre_validate:
        return (
            f"if {prv}.Find({query}).Length() == 0"
            + BRACKET_START
            + f"panic(fmt.Errorf({msg})); "
            + BRACKET_END
        )
    return (
        f"if {prv}.Find({query}).Length() == 0"
        + BRACKET_START
        + f"panic(fmt.Errorf({msg})); "
        + BRACKET_END
    )


BINDINGS_PRE[TokenType.IS_CSS] = _is_css


def gen_start_parse_list(node: "StartParseFunction") -> str:
    # later required for make structure
    st_args: list[str] = []
    body = (
        f"items := make(T{node.parent.name}ITEMS, 0); "
        + "for _, i := range p.splitDoc(p.Document.Selection).EachIter() "
        + BRACKET_START
    )

    for field in node.body:
        if field.name in MAGIC_METHODS:
            continue
        method_name = to_upper_camel_case(field.name)
        var_name = f"{method_name}Raw"
        # golang required manually handle errors
        if field.have_assert_expr() or field.ret_type == VariableType.NESTED:
            body += (
                f"{var_name}, err := p.parse{method_name}(i); "
                + "if err != nil "
                + BRACKET_START
                + "return nil, err; "
                + BRACKET_END
            )
            if field.ret_type == VariableType.NESTED:
                st_args.append(var_name)
            else:
                st_args.append("*" + var_name)

        elif field.have_default_expr():
            body += f"{var_name}, _ := p.parse{method_name}(i); "
            st_args.append(var_name)
        else:
            body += f"{var_name} := p.parse{method_name}(i); "
            st_args.append(var_name)
    body += (
        f"item := T{node.parent.name}"
        + BRACKET_START
        + ",".join(st_args)
        + BRACKET_END
        + ";"
        # close EachIter
        + "items = append(items, item)"
        + BRACKET_END
    )
    body += "return &items, nil; "
    return body


def gen_start_parse_item(node: "StartParseFunction") -> str:
    body = ""
    # later required for make structure
    st_args: list[str] = []
    for field in node.body:
        if field.name in MAGIC_METHODS:
            continue
        method_name = to_upper_camel_case(field.name)
        var_name = f"{method_name}Raw"
        # golang required manually handle errors
        if field.have_assert_expr() or field.ret_type == VariableType.NESTED:
            body += (
                f"{var_name}, err := p.parse{method_name}(p.Document.Selection); "
                + "if err != nil "
                + BRACKET_START
                + "return nil, err; "
                + BRACKET_END
            )
            if field.ret_type == VariableType.NESTED:
                st_args.append(var_name)
            else:
                st_args.append(var_name)
        else:
            body += (
                f"{var_name} := p.parse{method_name}(p.Document.Selection); "
            )
            st_args.append(var_name)
    body += (
        f"item := T{node.parent.name}"
        + BRACKET_START
        + ",".join(st_args)
        + BRACKET_END
        + "; "
    )
    body += "return &item, nil; "
    return body


def gen_start_parse_dict(node: "StartParseFunction") -> str:
    st_args: list[str] = []
    # check in ast build stage
    expr_key, expr_value = (
        find_callfn_field_node_by_name(node, "__KEY__"),  # type: ignore
        find_callfn_field_node_by_name(node, "__VALUE__"),  # type: ignore
    )
    body = (
        f"items := make(T{node.parent.name}); "
        + "for _, i := range p.splitDoc(p.Document.Selection).EachIter() "
        + BRACKET_START
    )
    if expr_key.have_assert_expr():
        body += (
            "keyRaw, err := p.parseKey(i); "
            + "if err != nil "
            + BRACKET_START
            + "return nil, err; "
            + BRACKET_END
        )
        st_args.append("*keyRaw")
    else:
        body += "keyRaw := p.parseKey(i); "
        st_args.append("keyRaw")
    if expr_value.have_assert_expr() or expr_value.ret_type == VariableType.NESTED:
        body += (
            "valueRaw, err := p.parseValue(i); "
            + "if err != nil "
            + BRACKET_START
            + "return nil, err; "
            + BRACKET_END
        )
        if expr_value.ret_type == VariableType.NESTED:
            st_args.append("valueRaw")
        else:
            st_args.append("*valueRaw")

    else:
        body += "valueRaw := p.parseValue(i); "
        st_args.append("valueRaw")
    body += (
        f"items[{st_args[0]}] = {st_args[1]}; "
        + BRACKET_END
        + ";"
        + "return &items, nil;"
    )
    return body


def gen_start_parse_flat_list(node: "StartParseFunction") -> str:
    # checked in ast build stage
    expr_item = find_callfn_field_node_by_name(node, "__ITEM__")  # type: ignore
    st_arg = "rawItem"
    body = (
        f"items := make(T{node.parent.name}, 0); "
        + "for _, i := range p.splitDoc(p.Document.Selection).EachIter() "
        + BRACKET_START
    )
    if expr_item.have_assert_expr() or expr_item.ret_type == VariableType.NESTED:
        body += (
            "rawItem, err := p.parseItem(i); "
            + "if err != nil "
            + BRACKET_START
            + "return nil, err; "
            + BRACKET_END
        )
        if expr_item.ret_type == VariableType.NESTED:
            st_arg = "rawItem"
        else:
            st_arg = "*rawItem"
    else:
        body += "rawItem := p.parseItem(i); "
    body += f"items = append(items, {st_arg}); " + BRACKET_END + ";"
    body += "return &items, nil;"
    return body


def gen_typedef_item(node: "TypeDef") -> str:
    # type T{name} struct { field(camelUPEER) String `json:f1`; ... }
    code = f"type T{node.name} struct " + BRACKET_START
    for f in node.body:
        if f.name in MAGIC_METHODS:
            continue

        if f.ret_type == VariableType.NESTED:
            field_type = f"T{f.nested_class}"
            if find_field_nested_struct(f).struct_ref.type == StructType.LIST:  # type: ignore
                field_type = f"{field_type}ITEMS"
        else:
            field_type = TYPES.get(f.ret_type, "")
        fields_name = to_upper_camel_case(f.name)
        code += f'{fields_name} {field_type} `json:"{f.name}"`; '
    code += BRACKET_END
    return code


def gen_typedef_dict(node: "TypeDef") -> str:
    # type T{name} = map[{KEY_TYPE}]{VALUE_TYPE};
    field_key = find_tdef_field_node_by_name(node, "__KEY__")
    if not field_key:
        # in AST build step checked
        raise NotImplementedError  # noqa
    field_value = find_tdef_field_node_by_name(node, "__VALUE__")
    if not field_value:
        # in AST build step checked
        raise NotImplementedError  # noqa

    if field_value.ret_type == VariableType.NESTED:
        field_type = f"T{field_value.nested_class}"
        if (
            find_field_nested_struct(field_value).struct_ref.type  # type: ignore
            == StructType.LIST
        ):
            field_type = f"{field_type}ITEMS"
    else:
        field_type = TYPES.get(field_value.ret_type, "")
    code = (
        f"type T{node.name} = "
        + f"map[{TYPES.get(field_key.ret_type)}]"
        + f"{field_type}; "
    )
    return code


def gen_typedef_flat_list(node: "TypeDef") -> str:
    # type T{name} = []{ITEM_TYPE};
    field_item = find_tdef_field_node_by_name(node, "__ITEM__")
    if not field_item:
        # in AST build step checked
        raise NotImplementedError  # noqa

    if field_item.ret_type == VariableType.NESTED:
        field_type = f"T{field_item.nested_class}"
    else:
        field_type = TYPES.get(field_item.ret_type, "")
    code = f"type T{node.name} = []{field_type}; "
    return code


def gen_typedef_list(node: "TypeDef") -> str:
    # 1. simular generate struct as ST.ITEM
    # 2. add array type for this struct
    # type T{name} struct { F1 String `json:f1`; ... }
    # type T{name}ITEMS = []T{name}
    code = gen_typedef_item(node)
    code += f"type T{node.name}ITEMS = []T{node.name}; "
    return code


def gen_struct_field_ret_header(node: "StructFieldFunction") -> str:
    # "func (p *{}) parse{}(value *goquery.Selection) {} "
    # 1. is nested (default not included in this construction)
    if node.ret_type == VariableType.NESTED:
        ret_type = f"T{node.nested_schema_name()}"
        typedef = node.find_associated_typedef()
        if typedef.struct_ref.type == StructType.LIST:  # type: ignore
            ret_type = f"{ret_type}ITEMS"
        ret_header = f"({ret_type}, error)"
    # 2. assert + default
    elif node.have_assert_expr() and node.body[0].have_default_expr():
        ret_type = TYPES.get(node.ret_type, "")
        # first - default expr
        default_expr_val = node.body[0].value
        if default_expr_val == None:
            ret_header = f"(result *{ret_type}, err error)"
        else:
            ret_header = f"(result {ret_type}, err error)"
    # 3. default
    elif node.body[0].have_default_expr():
        ret_type = TYPES.get(node.ret_type, "")
        default_expr_val = node.body[0].value
        if default_expr_val == None:
            ret_header = f"(result *{ret_type}, err error)"
        else:
            ret_header = f"(result {ret_type}, err error)"
    # 4. assert
    elif node.have_assert_expr():
        ret_type = TYPES.get(node.ret_type, "")
        ret_header = f"({ret_type}, error)"
    # 5. normal
    else:
        ret_type = TYPES.get(node.ret_type, "")
        ret_header = f"({ret_type})"
    return ret_header
