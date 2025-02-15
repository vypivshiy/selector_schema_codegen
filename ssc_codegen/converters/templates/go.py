"""code parts for go codegen"""

from typing import TYPE_CHECKING, Any

from ssc_codegen.str_utils import to_upper_camel_case
from ssc_codegen.tokens import (
    StructType,
    TokenType,
    VariableType,
    JsonVariableType,
)

from ssc_codegen.converters.ast_utils import (
    find_callfn_field_node_by_name,
    is_optional_variable,
    find_json_struct_instance,
)
from .template_bindings import (
    TemplateBindings,
)

if TYPE_CHECKING:
    from ssc_codegen.ast_ssc import (
        StartParseFunction,
        StructFieldFunction,
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

JSON_TYPES = {
    JsonVariableType.STRING: "string",
    JsonVariableType.BOOLEAN: "bool",
    JsonVariableType.NUMBER: "int",
    JsonVariableType.FLOAT: "float64",
    JsonVariableType.OPTIONAL_NUMBER: "*int",
    JsonVariableType.OPTIONAL_FLOAT: "*float64",
    JsonVariableType.OPTIONAL_BOOLEAN: "*bool",
    JsonVariableType.OPTIONAL_STRING: "*string",
    JsonVariableType.NULL: "*string",
}

# mocks for valid return errors
RETURN_ERR_TYPES = {
    VariableType.STRING: '""',
    VariableType.INT: "-1",
    VariableType.FLOAT: "-1.0",
    VariableType.LIST_STRING: "nil",
    VariableType.OPTIONAL_STRING: "nil",
    VariableType.OPTIONAL_LIST_STRING: "nil",
    VariableType.NULL: "nil",
    VariableType.OPTIONAL_INT: "nil",
    VariableType.LIST_INT: "nil",
    VariableType.OPTIONAL_FLOAT: "nil",
    VariableType.LIST_FLOAT: "nil",
    VariableType.OPTIONAL_LIST_FLOAT: "nil",
}


MAGIC_METHODS = {
    "__KEY__": "Key",
    "__VALUE__": "Value",
    "__ITEM__": "Item",
    "__PRE_VALIDATE__": "preValidate",
    "__SPLIT_DOC__": "splitDoc",
    "__START_PARSE__": "Parse",
}


BINDINGS_PRE = TemplateBindings()


def _docstring(docstring: str) -> str:
    # todo: provide node for insert func/struct name
    return "\n".join("// " + line for line in docstring.split("\n"))


BINDINGS_PRE[TokenType.DOCSTRING] = _docstring

# hardcoded undocumented template package placeholder
# in cli, set name as directory name
PACKAGE = "package $PACKAGE$"

# TODO: add github.com/antchfx/htmlquery API (xpath)
# in current stage project support only goquery
# for remove unused imports in generated code usage
# converter.tools.go_unimport_naive func
BINDINGS_PRE[TokenType.IMPORTS] = f"""
{PACKAGE}

import (
    "fmt"
    "regexp"
    "strings"
    "slices"
    "strconv"
    "encoding/json"
    "github.com/PuerkitoBio/goquery"
)
"""

BRACKET_START = "{"
BRACKET_END = "}"

# try/catch effect realisation via anon defer func
# if code block throw exception - set default value
# example:
# func divide(a, b int) (result int) {
# 	defer func() {
# 		if r := recover(); r != nil {result = 9000}
# 	}()
# 	return a / b
# }
#
# divide(10, 0) -> 9000
# divide(10, 2) -> 5

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


def _part_doc_func(parent_name: str, _is_err: bool = False) -> str:
    method_name = MAGIC_METHODS.get("__SPLIT_DOC__", "")
    return (
        "func (p *"
        + parent_name
        + ") "
        + method_name
        + "(value *goquery.Selection) (*goquery.Selection, error) "
        + BRACKET_START
    )


BINDINGS_PRE[TokenType.STRUCT_PART_DOCUMENT] = _part_doc_func
BINDINGS_PRE[TokenType.TYPEDEF] = (
    lambda t_name: f"type {t_name} struct {BRACKET_START}"
)
BINDINGS_PRE[TokenType.TYPEDEF_FIELD] = (
    lambda name, t_type, json_anchor: f"{name} {t_type} {json_anchor}; "
)
BINDINGS_PRE[TokenType.STRUCT_PRE_VALIDATE] = lambda st_ptr: (
    f"func (p *{st_ptr}) {MAGIC_METHODS.get('__PRE_VALIDATE__', '')}(value *goquery.Selection) (error, error) {BRACKET_START}"
)

BINDINGS_PRE[TokenType.EXPR_RETURN] = lambda var, _is_err: (
    "return " + var or "nil" + ", nil;"
)

# ret_header returns (T_VAR, error), im lazy write corner cases
BINDINGS_PRE[TokenType.EXPR_NO_RETURN] = "return nil, nil; "
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
        + ";"
    )


BINDINGS_PRE[TokenType.EXPR_LIST_REGEX_SUB] = _str_re_sub_map
BINDINGS_PRE[TokenType.EXPR_LIST_STRING_INDEX] = "{} := {}[{}]; "
BINDINGS_PRE[TokenType.EXPR_LIST_DOCUMENT_INDEX] = "{} := {}[{}]; "
BINDINGS_PRE[TokenType.EXPR_LIST_JOIN] = "{} := strings.Join({}, {}); "


def _assert_eq(
    prv: str,
    value: Any,
    msg: str,
    is_pre_validate: bool = False,
    is_default: bool = False,
    ret_type: VariableType = VariableType.NULL,
) -> str:
    if is_default:
        return (
            f"if !({prv} == {value})"
            + BRACKET_START
            + f"panic(fmt.Errorf({msg})); "
            + BRACKET_END
            + ";"
        )
    if is_pre_validate:
        return (
            f"if !({prv} == {value})"
            + BRACKET_START
            + f"return nil, fmt.Errorf({msg}); "
            + BRACKET_END
            + ";"
        )
    type_ = RETURN_ERR_TYPES.get(ret_type, "nil")
    return (
        f"if !({prv} == {value})"
        + BRACKET_START
        + f"return {type_}, fmt.Errorf({msg}); "
        + BRACKET_END
        + ";"
    )


BINDINGS_PRE[TokenType.IS_EQUAL] = _assert_eq


def _assert_ne(
    prv: str,
    value: str,
    msg: str,
    is_pre_validate: bool = False,
    is_default: bool = False,
    ret_type: VariableType = VariableType.NULL,
) -> str:
    if is_default:
        return (
            f"if {prv} == {value}"
            + BRACKET_START
            + f"panic(fmt.Errorf({msg})); "
            + BRACKET_END
            + ";"
        )
    if is_pre_validate:
        return (
            f"if {prv} == {value}"
            + BRACKET_START
            + f"return nil, fmt.Errorf({msg}); "
            + BRACKET_END
            + ";"
        )
    type_ = RETURN_ERR_TYPES.get(ret_type, "nil")
    return (
        f"if {prv} == {value}"
        + BRACKET_START
        + f"return {type_}, fmt.Errorf({msg}); "
        + BRACKET_END
        + ";"
    )


BINDINGS_PRE[TokenType.IS_NOT_EQUAL] = _assert_ne


def _assert_in(
    prv: str,
    item: str,
    msg: str,
    is_pre_validate: bool = False,
    is_default: bool = False,
    ret_type: VariableType = VariableType.NULL,
) -> str:
    if is_default:
        return (
            f"if !(slices.Contains({prv}, {item}))"
            + BRACKET_START
            + f"panic(fmt.Errorf({msg})); "
            + BRACKET_END
            + ";"
        )
    if is_pre_validate:
        return (
            f"if !(slices.Contains({prv}, {item}))"
            + BRACKET_START
            + f"return nil, fmt.Errorf({msg}); "
            + BRACKET_END
            + ";"
        )
    type_ = RETURN_ERR_TYPES.get(ret_type, "nil")
    return (
        f"if !(slices.Contains({prv}, {item}))"
        + BRACKET_START
        + f"return {type_}, fmt.Errorf({msg}); "
        + BRACKET_END
        + ";"
    )


BINDINGS_PRE[TokenType.IS_CONTAINS] = _assert_in


def _is_regex_match(
    prv: str,
    pattern: str,
    msg: str,
    is_pre_validate: bool = False,
    is_default: bool = False,
    ret_type: VariableType = VariableType.NULL,
) -> str:
    # TODO: err var return
    err_var = f"err{prv.title()}"
    if is_default:
        return (
            f"_, {err_var} := regexp.Match({pattern}, [] byte({prv})); "
            + f"if {err_var} != nil"
            + BRACKET_START
            + f"panic(fmt.Errorf({msg})); "
            + BRACKET_END
            + ";"
        )
    if is_pre_validate:
        return (
            f"_, {err_var} := regexp.Match({pattern}, [] byte({prv})); "
            + f"if {err_var} != nil"
            + BRACKET_START
            + f"return nil, fmt.Errorf({msg}); "
            + BRACKET_END
            + ";"
        )
    type_ = RETURN_ERR_TYPES.get(ret_type, "nil")
    return (
        f"_, {err_var} := regexp.Match({pattern}, [] byte({prv})); "
        + f"if {err_var} != nil"
        + BRACKET_START
        + f"return {type_}, fmt.Errorf({msg}); "
        + BRACKET_END
        + ";"
    )


BINDINGS_PRE[TokenType.IS_REGEX_MATCH] = _is_regex_match


def _to_int(
    nxt: str,
    prv: str,
    is_validate: bool = False,
    is_default: bool = False,
    ret_type: VariableType = VariableType.NULL,
) -> str:
    if is_default:
        return (
            f"{nxt}, err := strconv.Atoi({prv}); "
            + "if err != nil"
            + BRACKET_START
            + "panic(err); "
            + BRACKET_END
            + ";"
        )
    if is_validate:
        return (
            f"{nxt}, err := strconv.Atoi({prv}); "
            + "if err != nil"
            + BRACKET_START
            + "nil, err; "
            + BRACKET_END
            + ";"
        )
    type_ = RETURN_ERR_TYPES.get(ret_type, "nil")
    return (
        f"{nxt}, err := strconv.Atoi({prv}); "
        + "if err != nil"
        + BRACKET_START
        + f"{type_}, err; "
        + BRACKET_END
        + ";"
    )


BINDINGS_PRE[TokenType.TO_INT] = _to_int


def _to_map_int(
    nxt: str,
    prv: str,
    arr_type: str,
    is_validate: bool = False,
    is_default: bool = False,
    ret_type: VariableType = VariableType.NULL,
) -> str:
    tmp_var = f"tmp{nxt.title()}"
    each_var = f"i{nxt.title()}"
    code = (
        f"{nxt} := make({arr_type}, 0); "
        + f"for _, {tmp_var} := range {prv} "
        + BRACKET_START
        + f"{each_var}, err := strconv.Atoi({tmp_var}); "
        + "if err != nil"
        + BRACKET_START
    )
    if is_default:
        code += "panic(err); "
    elif is_validate:
        code += "return nil, err; "
    else:
        type_ = RETURN_ERR_TYPES.get(ret_type, "nil")
        code += f"return {type_}, err; "
    return (
        code
        + BRACKET_END
        + f"{nxt} = append({nxt}, {each_var}); "
        + BRACKET_END
    )


BINDINGS_PRE[TokenType.TO_INT_LIST] = _to_map_int


def _to_float(
    prv: str,
    nxt: str,
    is_validate: bool = False,
    is_default: bool = False,
    ret_type: VariableType = VariableType.NULL,
) -> str:
    if is_default:
        return (
            f"{nxt}, err := strconv.ParseFloat({prv}, 64); "
            + "if err != nil"
            + BRACKET_START
            + "panic(err); "
            + BRACKET_END
        )
    elif is_validate:
        return (
            f"{nxt}, err := strconv.ParseFloat({prv}, 64); "
            + "if err != nil"
            + BRACKET_START
            + "return nil, err; "
            + BRACKET_END
        )
    type_ = RETURN_ERR_TYPES.get(ret_type, "nil")
    return (
        f"{nxt}, err := strconv.ParseFloat({prv}, 64); "
        + "if err != nil"
        + BRACKET_START
        + f"return {type_}, err; "
        + BRACKET_END
    )


BINDINGS_PRE[TokenType.TO_FLOAT] = _to_float


def _to_map_float(
    prv: str,
    nxt: str,
    arr_type: str,
    is_validate: bool = False,
    is_default: bool = False,
    ret_type: VariableType = VariableType.NULL,
) -> str:
    tmp_var = f"tmp{nxt.title()}"
    each_var = f"i{nxt.title()}"
    code = (
        f"{nxt} := make({arr_type}, 0); "
        + f"for _, {tmp_var} := range {prv} "
        + BRACKET_START
        + f"{each_var}, err := strconv.ParseFloat({prv}, 64); "
        + "if err != nil"
        + BRACKET_START
    )
    if is_default:
        code += "panic(err); "
    elif is_validate:
        code += "return nil, err; "
    else:
        type_ = RETURN_ERR_TYPES.get(ret_type, "nil")
        code += f"return {type_}, err; "
    return (
        code
        + BRACKET_END
        + f"{nxt} = append({nxt}, {each_var}); "
        + BRACKET_END
    )


BINDINGS_PRE[TokenType.TO_FLOAT_LIST] = _to_map_float


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


def _raw(
    nxt: str,
    prv: str,
    is_validate: bool = False,
    is_default: bool = False,
    ret_type: VariableType = VariableType.NULL,
) -> str:
    if is_default:
        return (
            f"{nxt}, err := {prv}.Html(); "
            + "if err != nil "
            + BRACKET_START
            + "panic(err); "
            + BRACKET_END
            + ";"
        )
    elif is_validate:
        return (
            f"{nxt}, err := {prv}.Html(); "
            + "if err != nil "
            + BRACKET_START
            + "return nil, err; "
            + BRACKET_END
            + ";"
        )
    type_ = RETURN_ERR_TYPES.get(ret_type, "nil")
    return (
        f"{nxt}, err := {prv}.Html(); "
        + "if err != nil "
        + BRACKET_START
        + f"return {type_}, err; "
        + BRACKET_END
        + ";"
    )


BINDINGS_PRE[TokenType.EXPR_RAW] = _raw


def _raw_map(
    nxt: str,
    prv: str,
    arr_type: str,
    is_validate: bool = False,
    is_default: bool = False,
    ret_type: VariableType = VariableType.NULL,
) -> str:
    tmp_var = f"tmp{nxt.title()}"
    raw_var = f"raw{nxt.title()}"

    code = (
        f"{nxt} := make({arr_type}, 0); "
        + f"for _, {tmp_var} := range {prv} "
        + BRACKET_START
        + f"{raw_var}, err := {tmp_var}.Html(); "
        + "if err != nil "
        + BRACKET_START
    )

    if is_default:
        code += "panic(err); "
    elif is_validate:
        code += "return nil, err; "
    else:
        type_ = RETURN_ERR_TYPES.get(ret_type, "nil")
        code += f"return {type_}, err; "
    return (
        code
        + BRACKET_END
        + ";"
        + f"{nxt} = append({nxt}, {raw_var}); "
        + BRACKET_END
    )


BINDINGS_PRE[TokenType.EXPR_RAW_ALL] = _raw_map


def _expr_attr(
    nxt: str,
    prv: str,
    attr: str,
    is_validate: bool = False,
    is_default: bool = False,
    ret_type: VariableType = VariableType.NULL,
) -> str:
    if is_default:
        return (
            f"{nxt}, isExists := {prv}.Attr({attr}); "
            + "if !isExists"
            + BRACKET_START
            + f'panic(fmt.Errorf("attr `%s` not exists in `%s`", {attr}, {prv}));'
            + BRACKET_END
            + ";"
        )
    elif is_validate:
        return (
            f"{nxt}, isExists := {prv}.Attr({attr}); "
            + "if !isExists"
            + BRACKET_START
            + f'return nil, fmt.Errorf("attr `%s` not exists in `%s`", {attr}, {prv});'
            + BRACKET_END
            + ";"
        )

    type_ = RETURN_ERR_TYPES.get(ret_type, "nil")
    return (
        f"{nxt}, isExists := {prv}.Attr({attr}); "
        + "if !isExists"
        + BRACKET_START
        + f'return {type_}, fmt.Errorf("attr `%s` not exists in `%s`", {attr}, {prv});'
        + BRACKET_END
        + ";"
    )


BINDINGS_PRE[TokenType.EXPR_ATTR] = _expr_attr


def _attr_map(
    nxt: str,
    prv: str,
    attr: str,
    arr_type: str,
    is_validate: bool = False,
    is_default: bool = False,
    ret_type: VariableType = VariableType.NULL,
) -> str:
    tmp_var = f"tmp{nxt.title()}"
    raw_var = f"attr{nxt.title()}"

    code = (
        f"{nxt} := make({arr_type}, 0); "
        + f"for _, {tmp_var} := range {prv} "
        + BRACKET_START
        + f"{raw_var}, isExists := {tmp_var}.Attr({attr}); "
        + "if !isExists"
        + BRACKET_START
    )
    if is_default:
        code += f'panic(fmt.Errorf("attr `%s` not exists in `%v`", {attr}, {tmp_var})); '
    elif is_validate:
        code += f'return nil, fmt.Errorf("attr `%s` not exists in `%v`", {attr}, {tmp_var}); '
    else:
        type_ = RETURN_ERR_TYPES.get(ret_type, "nil")
        code += f'return {type_}, fmt.Errorf("attr `%s` not exists in `%v`", {attr}, {tmp_var}); '
    return (
        code
        + BRACKET_END
        + ";"
        + f"{nxt} = append({nxt}, {raw_var}); "
        + BRACKET_END
    )


BINDINGS_PRE[TokenType.EXPR_ATTR_ALL] = _attr_map


def _is_css(
    prv: str,
    query: str,
    msg: str,
    is_validate: bool = False,
    is_default: bool = False,
    ret_type: VariableType = VariableType.NULL,
) -> str:
    if is_default:
        return (
            f"if {prv}.Find({query}).Length() == 0"
            + BRACKET_START
            + f"panic(fmt.Errorf({msg}));"
            + BRACKET_END
            + ";"
        )
    if is_validate:
        return (
            f"if {prv}.Find({query}).Length() == 0"
            + BRACKET_START
            + f"return nil, fmt.Errorf({msg});"
            + BRACKET_END
            + ";"
        )
    type_ = RETURN_ERR_TYPES.get(ret_type, "nil")
    return (
        f"if {prv}.Find({query}).Length() == 0"
        + BRACKET_START
        + f"return {type_}, fmt.Errorf({msg});"
        + BRACKET_END
        + ";"
    )


BINDINGS_PRE[TokenType.IS_CSS] = _is_css


def gen_start_parse_list(node: "StartParseFunction") -> str:
    # later required for make structure
    st_args: list[str] = []
    body = (
        f"items := make([]T{node.parent.name}, 0); "
        + "docParts, err := p.splitDoc(p.Document.Selection);"
        + "if err != nil"
        + BRACKET_START
        + "return nil, err; "
        + BRACKET_END
        + ";"
        + "for _, i := range docParts.EachIter() "
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
                + ";"
            )
            if field.ret_type == VariableType.NESTED:
                st_args.append(var_name)
            else:
                st_args.append("*" + var_name)

        elif field.have_default_expr():
            # default value in error arg always returns nil
            body += f"{var_name}, _ := p.parse{method_name}(i); "
            st_args.append(var_name)
        else:
            body += (
                f"{var_name}, err := p.parse{method_name}(i); "
                + "if err != nil "
                + BRACKET_START
                + "return nil, err; "
                + BRACKET_END
                + ";"
            )
            st_args.append(var_name)
    body += (
        f"item := T{node.parent.name}"
        + BRACKET_START
        + ",".join(st_args)
        + BRACKET_END
        + ";"
        # close EachIter
        + "items = append(items, item); "
        + BRACKET_END
        + ";"
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
        body += (
            f"{var_name}, err := p.parse{method_name}(p.Document.Selection); "
            + "if err != nil "
            + BRACKET_START
            + "return nil, err; "
            + BRACKET_END
            + ";"
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
    expr_key, expr_value = (
        find_callfn_field_node_by_name(node, "__KEY__"),  # type: ignore
        find_callfn_field_node_by_name(node, "__VALUE__"),  # type: ignore
    )
    var_key = "&keyRaw" if is_optional_variable(expr_key.ret_type) else "keyRaw"  # type: ignore
    var_value = (
        "&valueRaw" if is_optional_variable(expr_value.ret_type) else "valueRaw"
    )  # type: ignore
    body = (
        f"items := make(T{node.parent.name}); "
        + "docParts, err := p.splitDoc(p.Document.Selection);"
        + "if err != nil"
        + BRACKET_START
        + "return nil, err; "
        + BRACKET_END
        + ";"
        + "for _, i := range docParts.EachIter() "
        + BRACKET_START
        + "keyRaw, err := p.parseKey(i); "
        + "if err != nil "
        + BRACKET_START
        + "return nil, err; "
        + BRACKET_END
        + ";"
        + "valueRaw, err := p.parseValue(i); "
        + "if err != nil "
        + BRACKET_START
        + "return nil, err; "
        + BRACKET_END
        + ";"
        + f"items[{var_key}] = {var_value};"
        + BRACKET_END
        + ";"
        + "return &items, nil;"
    )
    return body


def gen_start_parse_flat_list(node: "StartParseFunction") -> str:
    # checked in ast build stage
    expr_item = find_callfn_field_node_by_name(node, "__ITEM__")  # type: ignore

    var = "&rawItem" if is_optional_variable(expr_item.ret_type) else "rawItem"

    body = (
        f"items := make(T{node.parent.name}, 0); "
        + "docParts, err := p.splitDoc(p.Document.Selection);"
        + "if err != nil"
        + BRACKET_START
        + "return nil, err; "
        + BRACKET_END
        + ";"
        + "for _, i := range docParts.EachIter() "
        + BRACKET_START
        + "rawItem, err := p.parseItem(i); "
        + "if err != nil "
        + BRACKET_START
        + "return nil, err; "
        + BRACKET_END
        + ";"
        + f"items = append(items, {var}); "
        + BRACKET_END
        + ";"
        + "return &items, nil;"
    )
    return body


def gen_struct_field_ret_header(node: "StructFieldFunction") -> str:
    # "func (p *{}) parse{}(value *goquery.Selection) {} "
    if node.ret_type == VariableType.NESTED:
        ret_type = f"T{node.nested_schema_name()}"
        typedef = node.find_associated_typedef()
        if typedef.struct_ref.type == StructType.LIST:  # type: ignore
            ret_type = f"[]{ret_type}"
        return f"({ret_type}, error)"
    elif node.ret_type == VariableType.JSON:
        jsn_obj = find_json_struct_instance(node)
        ret_type = f"J{jsn_obj.__name__}"
        if jsn_obj.__IS_ARRAY__:
            ret_type = f"[]{ret_type}"

        return f"({ret_type}, error)"
    elif node.body[0].have_default_expr():
        ret_type = TYPES.get(node.ret_type, "")
        return f"(result {ret_type}, err error)"
    else:
        ret_type = TYPES.get(node.ret_type, "")
        return f"({ret_type}, error)"
