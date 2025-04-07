"""golang goquery implementation

Codegen notations:

- types, json implemented by type struct expr (json anchors include)
- typedef T{struct_name}
- json struct J{struct_name}
- vars have prefix `v{index}`, start argument names as `v`
- public methods auto convert to camelCase
- private methods auto convert to PascalCase



try/catch effect realisation via anon defer func.

if code block throw exception - set default value.

Example:

```go

func divide(a, b int) (result int) {
        defer func() {
                if r := recover(); r != nil {result = 9000}
        }()
        return a / b
}

divide(10, 0)  // 9000

divide(10, 2) // 5

```

map array types

# https://stackoverflow.com/a/33726830
<PREV ARRAY VAR> := []<T1>{1,2,3}

var <NEW ARRAY VAR> []<T2>

for _, x := range <PREV ARRAY VAR> {

    <NEW ARRAY VAR> = append(<NEW ARRAY VAR>, <MAP_CODE>)

}

SPECIAL METHODS NOTATIONS:

- field_name : Parse{Field_name} (add prefix `Parse` for every struct method parse)
- __KEY__ -> `key`, `parseKey`
- __VALUE__: `value`, `parseValue`
- __ITEM__: `item`, `parseItem`
- __PRE_VALIDATE__: `preValidate`,
- __SPLIT_DOC__: `splitDoc`,
- __START_PARSE__: `Parse`,
"""

from typing import cast

from typing_extensions import assert_never

from ssc_codegen.ast_ import (
    Docstring,
    StructParser,
    ExprReturn,
    ExprNoReturn,
    ExprNested,
    StructPreValidateMethod,
    StructFieldMethod,
    StartParseMethod,
    StructPartDocMethod,
    ExprStringFormat,
    ExprListStringFormat,
    ExprStringTrim,
    ExprListStringTrim,
    ExprStringLeftTrim,
    ExprListStringLeftTrim,
    ExprStringRightTrim,
    ExprListStringRightTrim,
    ExprStringSplit,
    ExprStringReplace,
    ExprListStringReplace,
    ExprStringRegex,
    ExprStringRegexAll,
    ExprStringRegexSub,
    ExprListStringRegexSub,
    ExprIndex,
    ExprListStringJoin,
    ExprIsEqual,
    ExprIsNotEqual,
    ExprIsContains,
    ExprStringIsRegex,
    ExprIsCss,
    ExprToInt,
    ExprToListInt,
    ExprToFloat,
    ExprToListFloat,
    ExprToListLength,
    ExprToBool,
    ExprJsonify,
    ExprCss,
    ExprCssAll,
    ExprXpath,
    ExprXpathAll,
    ExprGetHtmlAttr,
    ExprGetHtmlAttrAll,
    ExprGetHtmlText,
    ExprGetHtmlTextAll,
    ExprGetHtmlRaw,
    ExprGetHtmlRawAll,
    TypeDef,
    TypeDefField,
    ModuleImports,
    ExprDefaultValueStart,
    ExprCallStructMethod,
    JsonStruct,
    JsonStructField,
    ExprStringRmPrefix,
    ExprListStringRmPrefix,
    ExprStringRmSuffix,
    ExprListStringRmSuffix,
    ExprStringRmPrefixAndSuffix,
    ExprListStringRmPrefixAndSuffix,
    ExprListStringAnyRegex,
    ExprListStringAllRegex,
)
from ssc_codegen.converters.base import BaseCodeConverter
from ssc_codegen.converters.helpers import (
    prev_next_var,
    is_last_var_no_ret,
    have_default_expr,
    is_pre_validate_parent,
    get_last_ret_type,
    have_pre_validate_call,
    get_struct_field_method_by_name,
)
from ssc_codegen.converters.templates.go_goquery import (
    J2_PRE_NESTED,
    CODE_PRE_VALIDATE_CALL,
    J2_START_PARSE_ITEM_BODY,
    J2_START_PARSE_LIST_BODY,
    J2_START_PARSE_DICT_BODY,
    J2_START_PARSE_FLAT_LIST_BODY,
    J2_PRE_DEFAULT_START,
    J2_PRE_LIST_STR_FMT,
    J2_PRE_LIST_STR_TRIM,
    J2_PRE_LIST_STR_LEFT_TRIM,
    J2_PRE_LIST_STR_RIGHT_TRIM,
    J2_PRE_LIST_STR_REPLACE,
    J2_PRE_LIST_STR_REGEX_SUB,
    J2_PRE_IS_EQUAL,
    J2_PRE_IS_NOT_EQUAL,
    J2_PRE_IS_CONTAINS,
    J2_PRE_IS_REGEX,
    J2_PRE_IS_CSS,
    J2_PRE_TO_INT,
    J2_PRE_TO_LIST_INT,
    J2_PRE_TO_FLOAT,
    J2_PRE_TO_LIST_FLOAT,
    J2_PRE_HTML_ATTR,
    J2_PRE_HTML_ATTR_ALL,
    J2_PRE_HTML_RAW,
    J2_PRE_HTML_RAW_ALL,
    J2_PRE_STR_RM_PREFIX,
    J2_PRE_LIST_STR_RM_PREFIX,
    J2_PRE_STR_RM_SUFFIX,
    J2_PRE_LIST_STR_RM_SUFFIX,
    J2_PRE_STR_RM_PREFIX_AND_SUFFIX,
    J2_PRE_LIST_STR_RM_PREFIX_AND_SUFFIX,
    J2_PRE_LIST_STR_ANY_IS_RE,
    J2_PRE_LIST_STR_ALL_IS_RE,
)
from ssc_codegen.str_utils import (
    wrap_backtick,
    to_upper_camel_case,
    wrap_double_quotes,
    to_lower_camel_case,
)
from ssc_codegen.tokens import JsonVariableType, VariableType, StructType

MAGIC_METHODS = {
    "__ITEM__": "Item",
    "__KEY__": "Key",
    "__VALUE__": "Value",
}

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
    VariableType.BOOL: "bool",
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
    JsonVariableType.ARRAY_STRING: "[]string",
    JsonVariableType.ARRAY_FLOAT: "[]float64",
    JsonVariableType.ARRAY_BOOLEAN: "[]bool",
    JsonVariableType.ARRAY_NUMBER: "[]int",
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
    VariableType.BOOL: "false",
    VariableType.NESTED: "nil",
    VariableType.JSON: "nil",
}

# Constants are deliberately used to avoid missing a character in the visitor
BRACKET_START = "{"
BRACKET_END = "}"
END = "; "
DOCSTR = "// "
CONVERTER = BaseCodeConverter(debug_comment_prefix="// ")


def py_var_to_go_var(
    item: None | str | int | float | list, ret_type: VariableType
) -> str | int | float:
    if item is None:
        item = "nil"
    elif isinstance(item, str):
        item = wrap_double_quotes(item)
    elif isinstance(item, bool):
        item = "true" if item else "false"
    elif isinstance(item, list):
        # in AST static check step check if return type is
        # LIST_STRING, LIST_INT, LIST_FLOAT
        type_ = TYPES[ret_type]
        item = f"make({type_}, 0)"
    return item


def make_go_docstring(docstring: str, class_name: str = "") -> str:
    doc = "\n".join("// " + line for line in docstring.split("\n"))
    if class_name:
        doc = doc.replace("// ", f"// {class_name} ", 1)
    return doc


@CONVERTER(Docstring.kind)
def pre_docstring(node: Docstring) -> str:
    value = node.kwargs["value"]
    docstr = make_go_docstring(value)
    return docstr


@CONVERTER(ModuleImports.kind)
def pre_module_imports(_node: ModuleImports) -> str:
    # todo: doc templates variables
    return """
package $PACKAGE$

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


def get_typedef_field_by_name(node: TypeDef, field_name: str) -> str:
    value = [i for i in node.body if i.kwargs["name"] == field_name][0]
    value = cast(TypeDefField, value)
    if value.kwargs["type"] == VariableType.NESTED:
        type_ = f"T{value.kwargs['cls_nested']}"
        if value.kwargs["cls_nested_type"] == StructType.LIST:
            type_ = f"[]{type_}"
    elif value.kwargs["type"] == VariableType.JSON:
        type_ = f"J{value.kwargs['cls_nested']}"
        if value.kwargs["cls_nested_type"] == StructType.LIST:
            type_ = f"[]{type_}"
    else:
        type_ = TYPES[value.kwargs["type"]]
    return type_


@CONVERTER(JsonStruct.kind)
def pre_json_struct(node: JsonStruct) -> str:
    name, _is_array = node.unpack_args()
    return f"type J{name} struct " + BRACKET_START


@CONVERTER(JsonStruct.kind)
def post_json_struct(_: JsonStruct) -> str:
    return BRACKET_END


@CONVERTER(JsonStructField.kind)
def pre_json_struct_field(node: JsonStructField) -> str:
    name, field_type = node.unpack_args()
    if field_type.name:
        type_ = f"J{field_type.name}"
        if field_type.type == JsonVariableType.ARRAY_OBJECTS:
            type_ = f"[]{type_}"
    else:
        type_ = JSON_TYPES[field_type.type]
    field_name = to_upper_camel_case(name)
    return f'{field_name} {type_} `json:"{name}"`' + END


@CONVERTER(TypeDef.kind)
def pre_typedef(node: TypeDef) -> str:
    name, st_type = node.unpack_args()
    match st_type:
        case StructType.DICT:
            type_ = get_typedef_field_by_name(node, "__VALUE__")
            return f"type T{name} = map[string]{type_}" + END
        case StructType.FLAT_LIST:
            type_ = get_typedef_field_by_name(node, "__ITEM__")
            return f"type T{name} = []{type_}" + END
        case StructType.ITEM | StructType.LIST:
            return f"type T{node.name} struct {BRACKET_START}"
        case _:
            assert_never(st_type)
    raise NotImplementedError("unreachable")  # noqa


@CONVERTER.post(TypeDef.kind)
def post_typedef(node: TypeDef) -> str:
    name, st_type = node.unpack_args()
    match st_type:
        case StructType.DICT | StructType.FLAT_LIST:
            return ""
        case StructType.ITEM | StructType.LIST:
            return BRACKET_END + END
        case _:
            assert_never(st_type)
    raise NotImplementedError("unreachable")  # noqa


@CONVERTER(TypeDefField.kind)
def pre_typedef_field(node: TypeDefField) -> str:
    name, var_type, cls_nested, cls_nested_type = node.unpack_args()
    node.parent = cast(TypeDef, node.parent)
    if node.parent.struct_type in (StructType.DICT, StructType.FLAT_LIST):
        return ""

    elif name == "__KEY__":
        return ""

    elif var_type == VariableType.NESTED:
        type_ = f"T{cls_nested}"
        if cls_nested_type == StructType.LIST:
            type_ = f"[]{type_}"
    elif var_type == VariableType.JSON:
        type_ = f"J{cls_nested}"
        if cls_nested_type == StructType.LIST:
            type_ = f"[]{type_}"
    else:
        type_ = TYPES[var_type]
    field_name = to_upper_camel_case(name)
    return f'{field_name} {type_} `json:"{name}"`' + END


@CONVERTER(StructParser.kind)
def pre_struct_parser(node: StructParser) -> str:
    name = node.kwargs["name"]
    docstr = make_go_docstring(node.kwargs["docstring"], name)
    # generate block code immediately, funcs attached by ptr
    return f"""{docstr}
type {name} struct {BRACKET_START}
Document *goquery.Document;
{BRACKET_END}
"""


@CONVERTER(ExprReturn.kind)
def pre_return(node: ExprReturn) -> str:
    prv, _ = prev_next_var(node)

    if node.ret_type == VariableType.NESTED:
        return f"return *{prv}, nil; "

    elif have_default_expr(node):
        # OPTIONAL TYPE
        node.parent = cast(StructParser, node.parent)
        if node.parent.body[0].kwargs["value"] is None:
            return f"result = &{prv}; return result, nil;"

        return f"result = {prv}; return result, nil;"
    return f"return {prv}, nil;"


@CONVERTER(ExprNoReturn.kind)
def pre_no_return(_node: ExprReturn) -> str:
    # HACK: for simplify functions header gen, return two variables
    return "return nil, nil;"


@CONVERTER(ExprNested.kind)
def pre_nested(node: ExprNested) -> str:
    prv, nxt = prev_next_var(node)
    sc_name, sc_type = node.unpack_args()
    # make selection type as document
    tmp_doc, tmp_st = f"doc{nxt}", f"st{nxt}"
    return J2_PRE_NESTED.render(
        tmp_doc=tmp_doc, tmp_st=tmp_st, prv=prv, nxt=nxt, sc_name=sc_name
    )


@CONVERTER(StructPreValidateMethod.kind)
def pre_pre_validate(node: StructPreValidateMethod) -> str:
    node.parent = cast(StructParser, node.parent)
    name = node.parent.kwargs["name"]
    # first ret type always nil, stub for avoid calculate return args
    return f"func (p *{name}) preValidate(v *goquery.Selection) (error, error) {BRACKET_START}"


@CONVERTER.post(StructPreValidateMethod.kind)
def post_pre_validate(_node: StructPreValidateMethod) -> str:
    return BRACKET_END


@CONVERTER(StructPartDocMethod.kind)
def pre_part_doc(node: StructPartDocMethod) -> str:
    node.parent = cast(StructParser, node.parent)
    name = node.parent.kwargs["name"]
    return f"func (p *{name}) splitDoc(v *goquery.Selection) (*goquery.Selection, error) {BRACKET_START}"


@CONVERTER.post(StructPartDocMethod.kind)
def post_part_doc(_node: StructPartDocMethod) -> str:
    return BRACKET_END


@CONVERTER(StructFieldMethod.kind)
def pre_parse_field(node: StructFieldMethod) -> str:
    # ret header cases
    # 1. Nested -> T{st_name}, error
    # 2. Nested (array) -> []T{st_name}, error
    # 3. Json -> J{st_name}, error
    # 4. Json (array) -> []J{st_name}, error
    # 5. default expr -> result {ret_type}, error
    # 6. normal -> {ret_type}, error
    node.parent = cast(StructParser, node.parent)
    st_name = node.parent.kwargs["name"]
    name = MAGIC_METHODS.get(node.kwargs["name"], node.kwargs["name"])
    fn_name = "parse" + to_upper_camel_case(name)
    if node.body[-1].ret_type == VariableType.NESTED:
        nested_expr = node.body[-2]
        nested_expr = cast(ExprNested, nested_expr)
        sc_name, sc_type = nested_expr.unpack_args()
        ret_type = f"T{sc_name}"
        if sc_type == StructType.LIST:
            ret_type = f"[]{ret_type}"
    elif node.body[-1].ret_type == VariableType.JSON:
        json_expr = node.body[-2]
        json_expr = cast(ExprJsonify, json_expr)
        st_name, is_array = json_expr.unpack_args()
        ret_type = f"J{st_name}"
        if is_array:
            ret_type = f"[]{ret_type}"
    elif have_default_expr(node.body[0]):
        ret_type = TYPES[node.body[-1].ret_type]
        ret_type = f"result {ret_type}"
    else:
        ret_type = TYPES[node.body[-1].ret_type]

    if have_default_expr(node.body[0]):
        ret_header = f"({ret_type}, err error)"
    else:
        ret_header = f"({ret_type}, error)"

    return f"func (p *{st_name}) {fn_name}(v *goquery.Selection) {ret_header} {BRACKET_START}"


@CONVERTER.post(StructFieldMethod.kind)
def post_parse_field(_node: StructFieldMethod) -> str:
    return BRACKET_END


@CONVERTER(StartParseMethod.kind)
def pre_start_parse_method(node: StartParseMethod) -> str:
    parent = node.parent
    parent = cast(StructParser, parent)
    name, st_type, _ = parent.unpack_args()
    ret_type = f"T{name}"
    if st_type == StructType.LIST:
        ret_type = f"[]{ret_type}"
    return f"func (p *{name}) Parse() (*{ret_type}, error) {BRACKET_START}"


@CONVERTER.post(StartParseMethod.kind)
def post_start_parse_method(node: StartParseMethod) -> str:
    parent = node.parent
    parent = cast(StructParser, parent)
    name, st_type, _ = parent.unpack_args()
    code = ""
    if have_pre_validate_call(node):
        code += CODE_PRE_VALIDATE_CALL
    match st_type:
        case StructType.ITEM:
            # acc variables name for pass to struct
            st_args, methods = [], []
            for field in node.body:
                field = cast(ExprCallStructMethod, field)
                if field.kwargs["name"] in MAGIC_METHODS or field.kwargs[
                    "name"
                ].startswith("__"):
                    continue
                method_name = to_upper_camel_case(field.kwargs["name"])
                var_name = to_lower_camel_case(method_name)
                st_args.append(var_name)
                methods.append((var_name, method_name))
            code = J2_START_PARSE_ITEM_BODY.render(
                name=name, methods=methods, st_args=st_args
            )
        case StructType.LIST:
            # acc variables name for pass to struct
            st_args, methods = [], []
            for field in node.body:
                field = cast(ExprCallStructMethod, field)
                if field.kwargs["name"] in MAGIC_METHODS or field.kwargs[
                    "name"
                ].startswith("__"):
                    continue
                method_name = to_upper_camel_case(field.name)
                var_name = to_lower_camel_case(method_name)
                st_args.append(var_name)
                methods.append((var_name, method_name))
            code = J2_START_PARSE_LIST_BODY.render(
                name=name, methods=methods, st_args=st_args
            )
        case StructType.DICT:
            value_field = get_struct_field_method_by_name(parent, "__VALUE__")
            default_is_nil = False
            if have_default_expr(value_field):
                expr_default = value_field.body[0]
                expr_default = cast(ExprDefaultValueStart, expr_default)
                default_is_nil = expr_default.kwargs["value"] is None
            var_value = "&value" if default_is_nil else "value"
            code = J2_START_PARSE_DICT_BODY.render(
                name=name, var_value=var_value
            )
        case StructType.FLAT_LIST:
            item_field = get_struct_field_method_by_name(parent, "__ITEM__")
            default_is_nil = False
            if have_default_expr(item_field):
                expr_default = item_field.body[0]
                expr_default = cast(ExprDefaultValueStart, expr_default)
                default_is_nil = expr_default.kwargs["value"] is None
            var = "&item" if default_is_nil else "item"
            code = J2_START_PARSE_FLAT_LIST_BODY.render(name=name, var=var)
    return code


@CONVERTER(ExprDefaultValueStart.kind)
def pre_default_start(node: ExprDefaultValueStart) -> str:
    prv, nxt = prev_next_var(node)
    value = node.kwargs["value"]
    ret_type = get_last_ret_type(node)
    value = py_var_to_go_var(value, ret_type)
    return J2_PRE_DEFAULT_START.render(prv=prv, nxt=nxt, value=value)


@CONVERTER(ExprStringFormat.kind)
def pre_str_fmt(node: ExprStringFormat) -> str:
    prv, nxt = prev_next_var(node)
    fmt = node.kwargs["fmt"]
    template = wrap_double_quotes(fmt.replace("{{}}", "%s"))
    return f"{nxt} := fmt.Sprintf({template}, {prv})" + END


@CONVERTER(ExprListStringFormat.kind)
def pre_list_str_fmt(node: ExprListStringFormat) -> str:
    prv, nxt = prev_next_var(node)
    fmt = node.kwargs["fmt"]
    template = wrap_double_quotes(fmt.replace("{{}}", "%s"))
    tmp_var = f"tmp{nxt}"
    arr_type = TYPES.get(node.body[node.index_next].ret_type)

    return J2_PRE_LIST_STR_FMT.render(
        nxt=nxt, arr_type=arr_type, tmp_var=tmp_var, prv=prv, template=template
    )


@CONVERTER(ExprStringTrim.kind)
def pre_str_trim(node: ExprStringTrim) -> str:
    prv, nxt = prev_next_var(node)
    substr = wrap_double_quotes(node.kwargs["substr"])
    return f"{nxt} := strings.Trim({prv}, {substr})" + END


@CONVERTER(ExprListStringTrim.kind)
def pre_list_str_trim(node: ExprListStringTrim) -> str:
    prv, nxt = prev_next_var(node)
    substr = wrap_double_quotes(node.kwargs["substr"])
    tmp_var = f"tmp{nxt}"
    arr_type = TYPES.get(node.body[node.index_next].ret_type)
    return J2_PRE_LIST_STR_TRIM.render(
        nxt=nxt, arr_type=arr_type, tmp_var=tmp_var, prv=prv, substr=substr
    )


@CONVERTER(ExprStringLeftTrim.kind)
def pre_str_left_trim(node: ExprStringLeftTrim) -> str:
    prv, nxt = prev_next_var(node)
    substr = wrap_double_quotes(node.kwargs["substr"])
    return f"{nxt} := strings.TrimLeft({prv}, {substr})" + END


@CONVERTER(ExprListStringLeftTrim.kind)
def pre_list_str_left_trim(node: ExprListStringLeftTrim) -> str:
    prv, nxt = prev_next_var(node)
    substr = wrap_double_quotes(node.kwargs["substr"])
    tmp_var = f"tmp{nxt}"
    arr_type = TYPES.get(node.body[node.index_next].ret_type)
    return J2_PRE_LIST_STR_LEFT_TRIM.render(
        nxt=nxt, arr_type=arr_type, tmp_var=tmp_var, prv=prv, substr=substr
    )


@CONVERTER(ExprStringRightTrim.kind)
def pre_str_right_trim(node: ExprStringRightTrim) -> str:
    prv, nxt = prev_next_var(node)
    substr = wrap_double_quotes(node.kwargs["substr"])
    return f"{nxt} := strings.TrimRight({prv}, {substr})" + END


@CONVERTER(ExprListStringRightTrim.kind)
def pre_list_str_right_trim(node: ExprListStringRightTrim) -> str:
    prv, nxt = prev_next_var(node)
    substr = wrap_double_quotes(node.kwargs["substr"])
    tmp_var = f"tmp{nxt}"
    arr_type = TYPES.get(node.body[node.index_next].ret_type)

    return J2_PRE_LIST_STR_RIGHT_TRIM.render(
        nxt=nxt, arr_type=arr_type, tmp_var=tmp_var, prv=prv, substr=substr
    )


@CONVERTER(ExprStringSplit.kind)
def pre_str_split(node: ExprStringSplit) -> str:
    prv, nxt = prev_next_var(node)
    sep = wrap_double_quotes(node.kwargs["sep"])
    return f"{nxt} := strings.Split({prv}, {sep})" + END


@CONVERTER(ExprStringReplace.kind)
def pre_str_replace(node: ExprStringReplace) -> str:
    prv, nxt = prev_next_var(node)
    old, new = node.unpack_args()
    old = wrap_double_quotes(old)
    new = wrap_double_quotes(new)

    return f"{nxt} := strings.Replace({prv}, {old}, {new}, -1)" + END


@CONVERTER(ExprListStringReplace.kind)
def pre_list_str_replace(node: ExprListStringReplace) -> str:
    prv, nxt = prev_next_var(node)
    old, new = node.unpack_args()

    old = wrap_double_quotes(old)
    new = wrap_double_quotes(new)
    arr_type = TYPES.get(node.body[node.index_next].ret_type)
    tmp_var = f"tmp{nxt}"

    return J2_PRE_LIST_STR_REPLACE.render(
        nxt=nxt, arr_type=arr_type, tmp_var=tmp_var, prv=prv, old=old, new=new
    )


@CONVERTER(ExprStringRegex.kind)
def pre_str_regex(node: ExprStringRegex) -> str:
    prv, nxt = prev_next_var(node)
    pattern, group, ignore_case = node.unpack_args()
    tmp_var = f"tmp{nxt}"
    err_type = RETURN_ERR_TYPES[get_last_ret_type(node)]
    is_default = have_default_expr(node)
    is_pre_validate = is_pre_validate_parent(node)

    if ignore_case:
        go_pattern = wrap_backtick("(?i)" + node.pattern)
    else:
        go_pattern = wrap_backtick(pattern)

    if is_default:
        return (
            f"{tmp_var} := regexp.MustCompile({go_pattern}).FindStringSubmatch({prv});"
            + f"if len({tmp_var}) == 0 "
            + BRACKET_START
            + f'panic(fmt.Errorf("{pattern!r} not match result"));'
            + BRACKET_END
            + END
            + f"{nxt} := {tmp_var}[{group}];"
        )
    elif is_pre_validate:
        return (
            f"{tmp_var} := regexp.MustCompile({go_pattern}).FindStringSubmatch({prv});"
            + f"if len({tmp_var}) == 0 "
            + BRACKET_START
            + f'return nil, fmt.Errorf("{pattern!r} not match result");'
            + BRACKET_END
            + END
            + f"{nxt} := {tmp_var}[{group}];"
        )
    return (
        f"{tmp_var} := regexp.MustCompile({go_pattern}).FindStringSubmatch({prv});"
        + f"if len({tmp_var}) == 0 "
        + BRACKET_START
        + f'return {err_type}, fmt.Errorf("{pattern!r} not match result");'
        + BRACKET_END
        + END
        + f"{nxt} := {tmp_var}[{group}];"
    )


@CONVERTER(ExprStringRegexAll.kind)
def pre_str_regex_all(node: ExprStringRegexAll) -> str:
    prv, nxt = prev_next_var(node)
    pattern, ignore_case = node.unpack_args()

    if ignore_case:
        pattern = wrap_backtick("(?i)" + node.pattern)
    else:
        pattern = wrap_backtick(pattern)
    return f"{nxt} := regexp.MustCompile({pattern}).FindStringSubmatch({prv});"


@CONVERTER(ExprStringRegexSub.kind)
def pre_str_regex_sub(node: ExprStringRegexSub) -> str:
    prv, nxt = prev_next_var(node)
    pattern, repl = node.unpack_args()
    pattern = wrap_backtick(pattern)
    repl = wrap_double_quotes(repl)
    return (
        f"{nxt} := string(regexp.MustCompile({pattern}).ReplaceAll([]byte({prv}), []byte({repl})))"
        + END
    )


@CONVERTER(ExprListStringRegexSub.kind)
def pre_list_str_regex_sub(node: ExprListStringRegexSub) -> str:
    prv, nxt = prev_next_var(node)
    pattern, repl = node.unpack_args()

    pattern = wrap_backtick(pattern)
    repl = wrap_double_quotes(repl)
    arr_type = TYPES.get(node.body[node.index_next].ret_type)
    tmp_var = f"tmp{nxt}"
    return J2_PRE_LIST_STR_REGEX_SUB.render(
        nxt=nxt,
        arr_type=arr_type,
        tmp_var=tmp_var,
        prv=prv,
        pattern=pattern,
        repl=repl,
    )


@CONVERTER(ExprIndex.kind)
def pre_index(node: ExprIndex) -> str:
    prv, nxt = prev_next_var(node)
    index, *_ = node.unpack_args()
    return f"{nxt} := {prv}[{index}];"


@CONVERTER(ExprListStringJoin.kind)
def pre_list_str_join(node: ExprListStringJoin) -> str:
    prv, nxt = prev_next_var(node)
    sep = node.kwargs["sep"]
    sep = wrap_double_quotes(sep)
    return f"{nxt} := strings.Join({prv}, {sep})" + END


@CONVERTER(ExprIsEqual.kind)
def pre_is_equal(node: ExprIsEqual) -> str:
    prv, nxt = prev_next_var(node)
    item, msg = node.unpack_args()

    msg = wrap_double_quotes(msg)
    ret_type = get_last_ret_type(node)
    item = py_var_to_go_var(item, ret_type)

    context = {
        "prv": prv,
        "nxt": nxt,
        "item": item,
        "msg": msg,
        "have_default_expr": have_default_expr(node),
        "is_pre_validate_parent": is_pre_validate_parent(node),
        "is_last_var_no_ret": is_last_var_no_ret(node),
        "return_type": RETURN_ERR_TYPES.get(get_last_ret_type(node), "nil"),
    }

    return J2_PRE_IS_EQUAL.render(**context)


@CONVERTER(ExprIsNotEqual.kind)
def pre_is_not_equal(node: ExprIsNotEqual) -> str:
    prv, nxt = prev_next_var(node)
    item, msg = node.unpack_args()

    msg = wrap_double_quotes(msg) if msg else '""'
    ret_type = get_last_ret_type(node)
    item = py_var_to_go_var(item, ret_type)

    context = {
        "prv": prv,
        "nxt": nxt,
        "item": item,
        "msg": msg,
        "have_default_expr": have_default_expr(node),
        "is_pre_validate_parent": is_pre_validate_parent(node),
        "is_last_var_no_ret": is_last_var_no_ret(node),
        "return_type": RETURN_ERR_TYPES.get(get_last_ret_type(node), "nil"),
    }

    return J2_PRE_IS_NOT_EQUAL.render(**context)


@CONVERTER(ExprIsContains.kind)
def pre_is_contains(node: ExprIsContains) -> str:
    prv, nxt = prev_next_var(node)
    item, msg = node.unpack_args()

    msg = wrap_double_quotes(msg) if msg else '""'
    ret_type = get_last_ret_type(node)
    item = py_var_to_go_var(item, ret_type)

    context = {
        "prv": prv,
        "nxt": nxt,
        "item": item,
        "msg": msg,
        "have_default_expr": have_default_expr(node),
        "is_pre_validate_parent": is_pre_validate_parent(node),
        "is_last_var_no_ret": is_last_var_no_ret(node),
        "return_type": RETURN_ERR_TYPES.get(get_last_ret_type(node), "nil"),
    }

    return J2_PRE_IS_CONTAINS.render(**context)


@CONVERTER(ExprStringIsRegex.kind)
def pre_is_regex(node: ExprStringIsRegex) -> str:
    prv, nxt = prev_next_var(node)
    pattern, ignore_case, msg = node.unpack_args()

    # Handle ignore_case in function before template rendering
    if ignore_case:
        pattern = f"(?i){pattern}"
    pattern = wrap_backtick(pattern)
    msg = wrap_double_quotes(msg)
    err_var = f"err{nxt}"

    context = {
        "prv": prv,
        "nxt": nxt,
        "pattern": pattern,  # Already processed with ignore_case and backticks
        "msg": msg,
        "err_var": err_var,
        "have_default_expr": have_default_expr(node),
        "is_pre_validate_parent": is_pre_validate_parent(node),
        "is_last_var_no_ret": is_last_var_no_ret(node),
        "return_type": RETURN_ERR_TYPES.get(get_last_ret_type(node), "nil"),
    }

    return J2_PRE_IS_REGEX.render(**context)


@CONVERTER(ExprListStringAnyRegex.kind)
def pre_list_str_any_is_regex(node: ExprListStringAnyRegex) -> str:
    prv, nxt = prev_next_var(node)
    pattern, ignore_case, msg = node.unpack_args()
    if ignore_case:
        pattern = f"(?i){pattern}"
    pattern = wrap_backtick(pattern)
    msg = wrap_double_quotes(msg)
    context = {
        "prv": prv,
        "nxt": nxt,
        "pattern": pattern,  # Already processed with ignore_case and backticks
        "msg": msg,
        "have_default_expr": have_default_expr(node),
        "is_pre_validate_parent": is_pre_validate_parent(node),
        "is_last_var_no_ret": is_last_var_no_ret(node),
        "return_type": RETURN_ERR_TYPES.get(get_last_ret_type(node), "nil"),
    }
    return J2_PRE_LIST_STR_ANY_IS_RE.render(**context)


@CONVERTER(ExprListStringAllRegex.kind)
def pre_list_str_all_is_regex(node: ExprListStringAllRegex) -> str:
    prv, nxt = prev_next_var(node)
    pattern, ignore_case, msg = node.unpack_args()
    if ignore_case:
        pattern = f"(?i){pattern}"
    pattern = wrap_backtick(pattern)
    msg = wrap_double_quotes(msg)
    context = {
        "prv": prv,
        "nxt": nxt,
        "pattern": pattern,  # Already processed with ignore_case and backticks
        "msg": msg,
        "have_default_expr": have_default_expr(node),
        "is_pre_validate_parent": is_pre_validate_parent(node),
        "is_last_var_no_ret": is_last_var_no_ret(node),
        "return_type": RETURN_ERR_TYPES.get(get_last_ret_type(node), "nil"),
    }
    return J2_PRE_LIST_STR_ALL_IS_RE.render(**context)


@CONVERTER(ExprIsCss.kind)
def pre_is_css(node: ExprIsCss) -> str:
    prv, nxt = prev_next_var(node)
    query, msg = node.unpack_args()

    query = wrap_double_quotes(query)
    msg = wrap_double_quotes(msg)
    context = {
        "prv": prv,
        "nxt": nxt,
        "query": query,
        "msg": msg,
        "have_default_expr": have_default_expr(node),
        "is_pre_validate_parent": is_pre_validate_parent(node),
        "is_last_var_no_ret": is_last_var_no_ret(node),
        "return_type": RETURN_ERR_TYPES.get(get_last_ret_type(node), "nil"),
    }

    return J2_PRE_IS_CSS.render(**context)


@CONVERTER(ExprToInt.kind)
def pre_to_int(node: ExprToInt) -> str:
    prv, nxt = prev_next_var(node)

    context = {
        "prv": prv,
        "nxt": nxt,
        "have_default_expr": have_default_expr(node),
        "is_pre_validate_parent": is_pre_validate_parent(node),
        "return_type": RETURN_ERR_TYPES.get(get_last_ret_type(node), "nil"),
    }

    return J2_PRE_TO_INT.render(**context)


@CONVERTER(ExprToListInt.kind)
def pre_to_list_int(node: ExprToListInt) -> str:
    prv, nxt = prev_next_var(node)
    tmp_var = f"tmp{nxt}"
    each_var = f"i{nxt}"
    arr_type = TYPES.get(node.body[node.index_next].ret_type)

    context = {
        "prv": prv,
        "nxt": nxt,
        "tmp_var": tmp_var,
        "each_var": each_var,
        "arr_type": arr_type,
        "have_default_expr": have_default_expr(node),
        "is_pre_validate_parent": is_pre_validate_parent(node),
        "return_type": RETURN_ERR_TYPES.get(get_last_ret_type(node), "nil"),
    }

    return J2_PRE_TO_LIST_INT.render(**context)


@CONVERTER(ExprToFloat.kind)
def pre_to_float(node: ExprToFloat) -> str:
    prv, nxt = prev_next_var(node)

    context = {
        "prv": prv,
        "nxt": nxt,
        "have_default_expr": have_default_expr(node),
        "is_pre_validate_parent": is_pre_validate_parent(node),
        "return_type": RETURN_ERR_TYPES.get(get_last_ret_type(node), "nil"),
    }

    return J2_PRE_TO_FLOAT.render(**context)


@CONVERTER(ExprToListFloat.kind)
def pre_to_list_float(node: ExprToListFloat) -> str:
    prv, nxt = prev_next_var(node)
    tmp_var = f"tmp{nxt}"
    each_var = f"i{nxt}"
    arr_type = TYPES.get(node.body[node.index_next].ret_type)

    context = {
        "prv": prv,
        "nxt": nxt,
        "tmp_var": tmp_var,
        "each_var": each_var,
        "arr_type": arr_type,
        "have_default_expr": have_default_expr(node),
        "is_pre_validate_parent": is_pre_validate_parent(node),
        "return_type": RETURN_ERR_TYPES.get(get_last_ret_type(node), "nil"),
    }

    return J2_PRE_TO_LIST_FLOAT.render(**context)


@CONVERTER(ExprToListLength.kind)
def pre_to_len(node: ExprToListLength) -> str:
    prv, nxt = prev_next_var(node)
    return f"let {nxt} = len({prv})" + END


@CONVERTER(ExprToBool.kind)
def pre_to_bool(node: ExprToBool) -> str:
    prv, nxt = prev_next_var(node)
    match node.ret_type:
        # https://pkg.go.dev/gopkg.in/goquery.v1#Selection.Length
        case VariableType.DOCUMENT:
            code = f"{nxt} := {prv} != nil && {prv}.Length() > 0; "
        case VariableType.LIST_DOCUMENT:
            code = f"{nxt} := {prv} != nil && {prv}.Length() > 0; "

        case VariableType.STRING:
            code = f'{nxt} := {prv} != nil && {prv} != ""; '

        # `0` is true
        case VariableType.INT:
            code = f"{nxt} := {prv} != nil; "
        case VariableType.FLOAT:
            code = f"{nxt} := {prv} != nil; "

        # build-in array
        case VariableType.LIST_STRING:
            code = f"{nxt} := {prv} != nil && len({prv}) > 0; "
        case VariableType.LIST_INT:
            code = f"{nxt} := {prv} != nil && len({prv}) > 0; "
        case VariableType.LIST_FLOAT:
            code = f"{nxt} := {prv} != nil && len({prv}) > 0; "
        case _:
            assert_never(node.prev.ret_type)
    return code  # noqa


@CONVERTER(ExprJsonify.kind)
def pre_jsonify(node: ExprJsonify) -> str:
    prv, nxt = prev_next_var(node)
    name, is_array = node.unpack_args()
    name = f"J{name}"
    if is_array:
        return (
            f"{nxt} := []{name}"
            + "{}; "
            + f"json.Unmarshal([]byte({prv}), &{nxt});"
        )
    return (
        f"{nxt} := {name}" + "{}; " + f"json.Unmarshal([]byte({prv}), &{nxt});"
    )


@CONVERTER(ExprCss.kind)
def pre_css(node: ExprCss) -> str:
    prv, nxt = prev_next_var(node)
    query = wrap_double_quotes(node.kwargs["query"])
    return f"{nxt} := {prv}.Find({query}).First(); "


@CONVERTER(ExprCssAll.kind)
def pre_css_all(node: ExprCssAll) -> str:
    prv, nxt = prev_next_var(node)
    query = wrap_double_quotes(node.kwargs["query"])
    return f"{nxt} := {prv}.Find({query}); "


@CONVERTER(ExprXpath.kind)
def pre_xpath(_: ExprXpath) -> str:
    raise NotImplementedError("goquery not support xpath")


@CONVERTER(ExprXpathAll.kind)
def pre_xpath_all(_: ExprXpathAll) -> str:
    raise NotImplementedError("goquery not support xpath")


@CONVERTER(ExprGetHtmlAttr.kind)
def pre_html_attr(node: ExprGetHtmlAttr) -> str:
    prv, nxt = prev_next_var(node)
    key = wrap_double_quotes(node.kwargs["key"])

    context = {
        "prv": prv,
        "nxt": nxt,
        "key": key,
        "have_default_expr": have_default_expr(node),
        "is_pre_validate_parent": is_pre_validate_parent(node),
        "return_type": RETURN_ERR_TYPES.get(get_last_ret_type(node), "nil"),
    }

    return J2_PRE_HTML_ATTR.render(**context)


@CONVERTER(ExprGetHtmlAttrAll.kind)
def pre_html_attr_all(node: ExprGetHtmlAttrAll) -> str:
    prv, nxt = prev_next_var(node)
    key = wrap_double_quotes(node.kwargs["key"])
    tmp_var = f"tmp{nxt.title()}"
    raw_var = f"attr{nxt.title()}"
    arr_type = TYPES.get(node.body[node.index_next].ret_type)

    context = {
        "prv": prv,
        "nxt": nxt,
        "key": key,
        "tmp_var": tmp_var,
        "raw_var": raw_var,
        "arr_type": arr_type,
        "have_default_expr": have_default_expr(node),
        "is_pre_validate_parent": is_pre_validate_parent(node),
        "return_type": RETURN_ERR_TYPES.get(get_last_ret_type(node), "nil"),
    }

    return J2_PRE_HTML_ATTR_ALL.render(**context)


@CONVERTER(ExprGetHtmlText.kind)
def pre_html_text(node: ExprGetHtmlText) -> str:
    prv, nxt = prev_next_var(node)
    return f"{nxt} := {prv}.Text(); "


@CONVERTER(ExprGetHtmlTextAll.kind)
def pre_html_text_all(node: ExprGetHtmlTextAll) -> str:
    prv, nxt = prev_next_var(node)
    tmp_var = f"tmp{nxt.title()}"
    arr_type = TYPES.get(node.body[node.index_next].ret_type)
    return (
        f"{nxt} := make({arr_type}, 0)"
        + END
        + f"for _, {tmp_var} := range {prv} "
        + BRACKET_START
        + f"{nxt} = append({nxt}, {tmp_var}.Text())"
        + END
        + BRACKET_END
    )


@CONVERTER(ExprGetHtmlRaw.kind)
def pre_html_raw(node: ExprGetHtmlRaw) -> str:
    prv, nxt = prev_next_var(node)

    context = {
        "prv": prv,
        "nxt": nxt,
        "have_default_expr": have_default_expr(node),
        "is_pre_validate_parent": is_pre_validate_parent(node),
        "return_type": RETURN_ERR_TYPES.get(get_last_ret_type(node), "nil"),
    }

    return J2_PRE_HTML_RAW.render(**context)


@CONVERTER(ExprGetHtmlRawAll.kind)
def pre_html_raw_all(node: ExprGetHtmlRawAll) -> str:
    prv, nxt = prev_next_var(node)
    tmp_var = f"tmp{nxt.title()}"
    raw_var = f"raw{nxt.title()}"
    arr_type = TYPES.get(node.body[node.index_next].ret_type)

    context = {
        "prv": prv,
        "nxt": nxt,
        "tmp_var": tmp_var,
        "raw_var": raw_var,
        "arr_type": arr_type,
        "have_default_expr": have_default_expr(node),
        "is_pre_validate_parent": is_pre_validate_parent(node),
        "return_type": RETURN_ERR_TYPES.get(get_last_ret_type(node), "nil"),
    }

    return J2_PRE_HTML_RAW_ALL.render(**context)


@CONVERTER(ExprStringRmPrefix.kind)
def pre_str_rm_prefix(node: ExprStringRmPrefix) -> str:
    prv, nxt = prev_next_var(node)
    substr = wrap_double_quotes(node.kwargs["substr"])
    return J2_PRE_STR_RM_PREFIX.render(prv=prv, nxt=nxt, substr=substr)


@CONVERTER(ExprListStringRmPrefix.kind)
def pre_list_str_rm_prefix(node: ExprListStringRmPrefix) -> str:
    prv, nxt = prev_next_var(node)
    substr = wrap_double_quotes(node.kwargs["substr"])
    tmp_var = f"i{nxt}"
    return J2_PRE_LIST_STR_RM_PREFIX.render(
        prv=prv, nxt=nxt, substr=substr, tmp_var=tmp_var
    )


@CONVERTER(ExprStringRmSuffix.kind)
def pre_str_rm_suffix(node: ExprStringRmSuffix) -> str:
    prv, nxt = prev_next_var(node)
    substr = wrap_double_quotes(node.kwargs["substr"])
    return J2_PRE_STR_RM_SUFFIX.render(prv=prv, nxt=nxt, substr=substr)


@CONVERTER(ExprListStringRmSuffix.kind)
def pre_list_str_rm_suffix(node: ExprListStringRmSuffix) -> str:
    prv, nxt = prev_next_var(node)
    substr = wrap_double_quotes(node.kwargs["substr"])
    tmp_var = f"i{nxt}"
    return J2_PRE_LIST_STR_RM_SUFFIX.render(
        prv=prv, nxt=nxt, substr=substr, tmp_var=tmp_var
    )


@CONVERTER(ExprStringRmPrefixAndSuffix.kind)
def pre_str_rm_prefix_and_suffix(node: ExprStringRmPrefixAndSuffix) -> str:
    prv, nxt = prev_next_var(node)
    substr = wrap_double_quotes(node.kwargs["substr"])
    tmp_var = f"i{nxt}"
    return J2_PRE_STR_RM_PREFIX_AND_SUFFIX.render(
        prv=prv, nxt=nxt, substr=substr, tmp_var=tmp_var
    )


@CONVERTER(ExprListStringRmPrefixAndSuffix.kind)
def pre_list_str_rm_prefix_and_suffix(
    node: ExprListStringRmPrefixAndSuffix,
) -> str:
    prv, nxt = prev_next_var(node)
    substr = wrap_double_quotes(node.kwargs["substr"])
    tmp_var = f"i{nxt}"
    return J2_PRE_LIST_STR_RM_PREFIX_AND_SUFFIX.render(
        prv=prv, nxt=nxt, substr=substr, tmp_var=tmp_var
    )


# TODO impl ExprHasAttr, ExprListHasAttr
