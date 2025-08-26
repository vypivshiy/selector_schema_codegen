"""golang goquery implementation

Codegen notations:

- types, json implemented by type struct expr (json anchors include)
- typedef T{struct_name}
- json struct J{struct_name}
- vars have prefix `v{index}`, start argument names as `v`
- private methods auto convert to camelCase
- public methods auto convert to PascalCase
- classvars, if struct have parse methods - create a new class with prefix `{struct_name}Cfg` format


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

divide(10, 2) // 5

divide(10, 0)  // 9000

```

SPECIAL METHODS NOTATIONS:

- field_name : Parse{Field_name} (add prefix `Parse` for every struct method parse)
- __KEY__ -> `key`, `parseKey`
- __VALUE__: `value`, `parseValue`
- __ITEM__: `item`, `parseItem`
- __PRE_VALIDATE__: `preValidate`,
- __SPLIT_DOC__: `splitDoc`,
- __START_PARSE__: `Parse`,

see also templates.go_goquery for overview helper functions implementation
"""

from typing import ClassVar, cast

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
from ssc_codegen.ast_.nodes_array import ExprListUnique
from ssc_codegen.ast_.nodes_core import ExprClassVar
from ssc_codegen.ast_.nodes_filter import (
    ExprFilter,
    FilterAnd,
    FilterEqual,
    FilterNot,
    FilterNotEqual,
    FilterOr,
    FilterStrEnds,
    FilterStrIn,
    FilterStrLenEq,
    FilterStrLenGe,
    FilterStrLenGt,
    FilterStrLenLe,
    FilterStrLenLt,
    FilterStrLenNe,
    FilterStrRe,
    FilterStrStarts,
)
from ssc_codegen.ast_.nodes_selectors import (
    ExprCssElementRemove,
    ExprMapAttrs,
    ExprMapAttrsAll,
    ExprXpathElementRemove,
)
from ssc_codegen.ast_.nodes_string import (
    ExprListStringMapReplace,
    ExprListStringUnescape,
    ExprStringMapReplace,
    ExprStringUnescape,
)
from ssc_codegen.ast_.nodes_validate import (
    ExprHasAttr,
    ExprIsXpath,
    ExprListHasAttr,
)
from ssc_codegen.converters.base import BaseCodeConverter
from ssc_codegen.converters.helpers import (
    go_get_classvar_hook_or_value,
    is_first_node_cond,
    is_prev_node_atomic_cond,
    prev_next_var,
    have_default_expr,
    have_pre_validate_call,
)
from ssc_codegen.converters.templates.go_goquery import (
    HELPER_FUNCTIONS,
    IMPORTS,
    go_assert_func_add_error_check,
    go_default_value,
    go_func_add_error_check,
    go_nested_expr_call,
    go_parse_acc_unique_list_body,
    go_parse_dict_body,
    go_parse_flat_list_body,
    go_parse_item_body,
    go_parse_list_body,
    go_pre_validate_func_call,
)
from ssc_codegen.str_utils import (
    wrap_backtick,
    to_upper_camel_case,
    wrap_double_quotes,
)
from ssc_codegen.tokens import (
    JsonVariableType,
    TokenType,
    VariableType,
    StructType,
)

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


class GoConverter(BaseCodeConverter):
    # HACK: in golang, it is allowed to use functions in only one namespace without redefinition.
    PACKAGE: ClassVar[str] = "main"

    HELPER_FUNCS_IMPORTED: ClassVar[bool] = False
    """a special flag indicating that helper functions have been added. 
    golang does not support overloading, overwriting functions.
    
    After uploading, we set the `True` flag and do not load anymore.
    """


CONVERTER = GoConverter(debug_comment_prefix="// ")
CONVERTER.TEST_EXCLUDE_NODES.extend(
    [
        TokenType.STRUCT_INIT,  # defined inside a struct
        TokenType.EXPR_DEFAULT_END,  # emulated by defer func() + rescue
        TokenType.CLASSVAR,  # emulated by type ST struct{ f1: T1, f2: T2, ...}; var ST {f1=V1, f2=V2, ...};
    ]
)


def py_var_to_go_var(
    item: None | str | int | float | list | tuple,
    ret_type: VariableType | None = None,
) -> str | int | float:
    if item is None:
        item = "nil"
    elif isinstance(item, str):
        item = wrap_double_quotes(item)
    elif isinstance(item, bool):
        item = "true" if item else "false"
    elif isinstance(item, (list, tuple)):
        assert ret_type is not None
        # in AST static check step check if return type is
        # LIST_STRING, LIST_INT, LIST_FLOAT
        if ret_type == VariableType.LIST_STRING:
            item = (
                "[]string{"
                + ", ".join([wrap_double_quotes(i) for i in item])
                + "}"
            )
        elif ret_type == VariableType.LIST_INT:
            item = "[]int{" + ", ".join([i for i in item]) + "}"
        elif ret_type == VariableType.LIST_FLOAT:
            item = "[]float64{" + ", ".join([i for i in item]) + "}"
    return item


def py_regex_to_go_regex(
    pattern: str, ignore_case: bool = False, dotall: bool = False
) -> str:
    flags = ""
    if ignore_case:
        flags += "i"
    if dotall:
        flags += "s"
    if flags:
        flags = f"(?{flags})"
    return wrap_backtick(flags + pattern)


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
    # HACK:
    # golang not allowed override functions, check loaded helper functions by flag
    helper_functions = (
        HELPER_FUNCTIONS if not CONVERTER.HELPER_FUNCS_IMPORTED else ""
    )
    code = (
        # magic constant
        IMPORTS.replace("$PACKAGE$", CONVERTER.PACKAGE)
        # HACK: push helper functions to ModuleImports token:
        #       its generated second after module docstring
        + helper_functions
    )
    if not CONVERTER.HELPER_FUNCS_IMPORTED:
        CONVERTER.HELPER_FUNCS_IMPORTED = True
    return code


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


@CONVERTER(JsonStruct.kind, post_callback=lambda _: BRACKET_END)
def pre_json_struct(node: JsonStruct) -> str:
    name, _is_array = node.unpack_args()
    return f"type J{name} struct " + BRACKET_START


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

        case StructType.ACC_LIST:
            return f"type T{name} = []string" + END

        case StructType.ITEM | StructType.LIST:
            return f"type T{node.name} struct {BRACKET_START}"
        case _:
            assert_never(st_type)
    raise NotImplementedError("unreachable")  # noqa


@CONVERTER.post(TypeDef.kind)
def post_typedef(node: TypeDef) -> str:
    name, st_type = node.unpack_args()
    match st_type:
        case StructType.DICT | StructType.FLAT_LIST | StructType.ACC_LIST:
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
    if node.parent.struct_type in (
        StructType.DICT,
        StructType.FLAT_LIST,
        StructType.ACC_LIST,
    ):
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


def _struct_parser_gen_cfg(
    st_name: str, class_var_nodes: list[ExprClassVar]
) -> str:
    """helper function for generate classvar-like variables

    add suffix `Cfg` for class (struct) name
    """
    # more idiomatic in go syntax convert all variable names to UpperCamel
    return (
        f"var {st_name}Cfg = struct "
        + BRACKET_START
        + "\n"
        # FieldName T; ...
        f"{END} ".join(
            to_upper_camel_case(n.kwargs["field_name"]) + TYPES[n.ret_type]
            for n in class_var_nodes
        )
        + BRACKET_END
        # set values
        + BRACKET_START
        # FieldName VALUE
        + ",  ".join(
            to_upper_camel_case(n.kwargs["field_name"])
            + ": "
            # coverage corner case if value used in fmt expr
            + py_var_to_go_var(n.value.replace("{{}}", "%s", 1), n.ret_type)
            for n in class_var_nodes
        )
        + BRACKET_END
        + END
    )


@CONVERTER(StructParser.kind)
def pre_struct_parser(node: StructParser) -> str:
    # golang does not exists classvars features in struct{} types
    # create new struct with `Cfg` suffix and default values:
    # var type {struct_name}Cfg struct { VarName T; ... } { VarName {VALUE}; ... };
    # type {struct_name} struct { ... } + refs to {struct_name}Cfg.{VarName}
    classvars: list[ExprClassVar] = [
        i for i in node.body if i.kind == ExprClassVar.kind
    ]
    if classvars:
        cvars_code = (
            _struct_parser_gen_cfg(node.kwargs["name"], classvars) + "\n"
        )
    else:
        cvars_code = ""
    name = node.kwargs["name"]
    docstr = make_go_docstring(node.kwargs["docstring"], name)
    # generate block code immediately, funcs attached by ptr
    return f"""{cvars_code}{docstr}
type {name} struct {BRACKET_START}
Document *goquery.Document;
{BRACKET_END}
"""


@CONVERTER(ExprReturn.kind)
def pre_return(node: ExprReturn) -> str:
    prv, _ = prev_next_var(node)

    # nested not allowed default variable
    if node.ret_type == VariableType.NESTED:
        return f"return {prv}, nil; "

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
    sc_name, _sc_type = node.unpack_args()
    return go_nested_expr_call(nxt_var=nxt, prv_var=prv, schema_name=sc_name)


@CONVERTER(StructPreValidateMethod.kind, post_callback=lambda _: BRACKET_END)
def pre_pre_validate(node: StructPreValidateMethod) -> str:
    node.parent = cast(StructParser, node.parent)
    name = node.parent.kwargs["name"]
    # first ret type always nil, stub for avoid calculate return args in header
    return f"func (p *{name}) preValidate(v *goquery.Selection) (error, error) {BRACKET_START}"


@CONVERTER(StructPartDocMethod.kind, post_callback=lambda _: BRACKET_END)
def pre_part_doc(node: StructPartDocMethod) -> str:
    node.parent = cast(StructParser, node.parent)
    name = node.parent.kwargs["name"]
    return f"func (p *{name}) splitDoc(v *goquery.Selection) (*goquery.Selection, error) {BRACKET_START}"


@CONVERTER(StructFieldMethod.kind, post_callback=lambda _: BRACKET_END)
def pre_parse_field(node: StructFieldMethod) -> str:
    # ret_header cases
    # 0. for simplify generate return code - always return 2 variables
    #    if field expr is exclude errors handling - second value always a `nil`
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
        ret_type = "*" + ret_type
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
    _st_name, st_type, _docstr = parent.unpack_args()
    code = ""
    if have_pre_validate_call(node):
        code += go_pre_validate_func_call()
    match st_type:
        case StructType.ITEM:
            code = go_parse_item_body(parent)
        case StructType.LIST:
            code = go_parse_list_body(parent)
        case StructType.DICT:
            code = go_parse_dict_body(parent)
        case StructType.FLAT_LIST:
            code = go_parse_flat_list_body(parent)
        case StructType.ACC_LIST:
            code = go_parse_acc_unique_list_body(parent)
    return code


@CONVERTER(ExprDefaultValueStart.kind)
def pre_default_start(node: ExprDefaultValueStart) -> str:
    # implement default value via defer func(){ ... }() + recover();
    prv, nxt = prev_next_var(node)
    value = go_get_classvar_hook_or_value(node, "value")
    # ret_type = get_last_ret_type(node)

    return go_default_value(nxt_var=nxt, prv_var=prv, value=value)


@CONVERTER(ExprStringFormat.kind)
def pre_str_fmt(node: ExprStringFormat) -> str:
    prv, nxt = prev_next_var(node)
    # not to create another anonymous function,
    # we will repeat this replacement operation again if it returns a literal value.
    fmt = go_get_classvar_hook_or_value(node, "fmt")
    template = fmt.replace("{{}}", "%s")

    return f"{nxt} := fmt.Sprintf({template}, {prv}){END}"


@CONVERTER(ExprListStringFormat.kind)
def pre_list_str_fmt(node: ExprListStringFormat) -> str:
    prv, nxt = prev_next_var(node)
    fmt = go_get_classvar_hook_or_value(node, "fmt")
    template = fmt.replace("{{}}", "%s")
    # HELPER FUNC NAME: sscSliceStrFmt(v []string, t string)
    return f"{nxt} := sscSliceStrFmt({prv}, {template}){END}"


@CONVERTER(ExprStringTrim.kind)
def pre_str_trim(node: ExprStringTrim) -> str:
    prv, nxt = prev_next_var(node)
    substr = go_get_classvar_hook_or_value(node, "substr")
    return f"{nxt} := strings.Trim({prv}, {substr})" + END


@CONVERTER(ExprListStringTrim.kind)
def pre_list_str_trim(node: ExprListStringTrim) -> str:
    prv, nxt = prev_next_var(node)
    substr = go_get_classvar_hook_or_value(node, "substr")
    # helper func name: sscSliceStrTrim(v []string, c string) []string
    return f"{nxt} := sscSliceStrTrim({prv}, {substr}){END}"


@CONVERTER(ExprStringLeftTrim.kind)
def pre_str_left_trim(node: ExprStringLeftTrim) -> str:
    prv, nxt = prev_next_var(node)
    substr = go_get_classvar_hook_or_value(node, "substr")
    return f"{nxt} := strings.TrimLeft({prv}, {substr})" + END


@CONVERTER(ExprListStringLeftTrim.kind)
def pre_list_str_left_trim(node: ExprListStringLeftTrim) -> str:
    prv, nxt = prev_next_var(node)
    substr = go_get_classvar_hook_or_value(node, "substr")
    # helper func name: sscSliceStrLTrim(v []string, c string) []string
    return f"{nxt} := sscSliceStrLTrim({prv}, {substr}){END}"


@CONVERTER(ExprStringRightTrim.kind)
def pre_str_right_trim(node: ExprStringRightTrim) -> str:
    prv, nxt = prev_next_var(node)
    substr = go_get_classvar_hook_or_value(node, "substr")
    return f"{nxt} := strings.TrimRight({prv}, {substr})" + END


@CONVERTER(ExprListStringRightTrim.kind)
def pre_list_str_right_trim(node: ExprListStringRightTrim) -> str:
    prv, nxt = prev_next_var(node)
    substr = go_get_classvar_hook_or_value(node, "substr")
    # helper func name: sscSliceStrRTrim(v []string, c string) []string
    return f"{nxt} := sscSliceStrRTrim({prv}, {substr}){END}"


@CONVERTER(ExprStringSplit.kind)
def pre_str_split(node: ExprStringSplit) -> str:
    prv, nxt = prev_next_var(node)
    sep = go_get_classvar_hook_or_value(node, "sep")
    return f"{nxt} := strings.Split({prv}, {sep})" + END


@CONVERTER(ExprStringReplace.kind)
def pre_str_replace(node: ExprStringReplace) -> str:
    prv, nxt = prev_next_var(node)

    old = go_get_classvar_hook_or_value(node, "old")
    new = go_get_classvar_hook_or_value(node, "new")

    return f"{nxt} := strings.Replace({prv}, {old}, {new}, -1)" + END


@CONVERTER(ExprListStringReplace.kind)
def pre_list_str_replace(node: ExprListStringReplace) -> str:
    prv, nxt = prev_next_var(node)

    old = go_get_classvar_hook_or_value(node, "old")
    new = go_get_classvar_hook_or_value(node, "new")
    # helper func: sscSliceStrReplace(v []string, o, n string) []string
    return f"{nxt} := sscSliceStrReplace({prv}, {old}, {new}){END}"


@CONVERTER(ExprStringRegex.kind)
def pre_str_regex(node: ExprStringRegex) -> str:
    prv, _ = prev_next_var(node)

    pattern, group, ignore_case, dotall = node.unpack_args()
    if node.classvar_hooks.get("pattern"):
        pattern = go_get_classvar_hook_or_value(node, "pattern")
    else:
        pattern = py_regex_to_go_regex(pattern, ignore_case, dotall)

    # sscRegexMatch(v string, re *regexp.Regexp, g int) (string, error)
    return go_func_add_error_check(
        node,
        call_func=f"sscRegexMatch({prv}, regexp.MustCompile({pattern}), {group})",
    )


@CONVERTER(ExprStringRegexAll.kind)
def pre_str_regex_all(node: ExprStringRegexAll) -> str:
    prv, _ = prev_next_var(node)
    if node.classvar_hooks.get("pattern"):
        pattern = go_get_classvar_hook_or_value(node, "pattern")
    else:
        pattern, ignore_case, dotall = node.unpack_args()
        pattern = py_regex_to_go_regex(pattern, ignore_case, dotall)
    # sscRegexFindAll(v string, re *regexp.Regexp) ([]string, error)
    return go_func_add_error_check(
        node, call_func=f"sscRegexFindAll({prv}, regexp.MustCompile({pattern}))"
    )


@CONVERTER(ExprStringRegexSub.kind)
def pre_str_regex_sub(node: ExprStringRegexSub) -> str:
    prv, nxt = prev_next_var(node)
    if node.classvar_hooks.get("pattern"):
        pattern = go_get_classvar_hook_or_value(node, "pattern")
    else:
        pattern, repl, ignore_case, dotall = node.unpack_args()
        pattern = py_regex_to_go_regex(pattern, ignore_case, dotall)
    repl = go_get_classvar_hook_or_value(node, "repl")
    return f"{nxt} := regexp.MustCompile({pattern}).ReplaceAllString({prv}, {repl})){END}"


@CONVERTER(ExprListStringRegexSub.kind)
def pre_list_str_regex_sub(node: ExprListStringRegexSub) -> str:
    prv, nxt = prev_next_var(node)
    if node.classvar_hooks.get("pattern"):
        pattern = go_get_classvar_hook_or_value(node, "pattern")
    else:
        pattern, repl, ignore_case, dotall = node.unpack_args()
        pattern = py_regex_to_go_regex(pattern, ignore_case, dotall)

    repl = go_get_classvar_hook_or_value(node, "repl")
    # sscSliceStrReSub(v []string, re *regexp.Regexp, repl string) []string
    return f"{nxt} := sscSliceStrReSub({prv}, regexp.MustCompile({pattern}), {repl}){END}"


@CONVERTER(ExprIndex.kind)
def pre_index(node: ExprIndex) -> str:
    prv, nxt = prev_next_var(node)
    index = go_get_classvar_hook_or_value(node, "index")
    return f"{nxt} := {prv}[{index}];"


@CONVERTER(ExprListStringJoin.kind)
def pre_list_str_join(node: ExprListStringJoin) -> str:
    prv, nxt = prev_next_var(node)
    sep = go_get_classvar_hook_or_value(node, "sep")
    return f"{nxt} := strings.Join({prv}, {sep}){END}"


@CONVERTER(ExprIsEqual.kind)
def pre_is_equal(node: ExprIsEqual) -> str:
    prv, _ = prev_next_var(node)
    item = go_get_classvar_hook_or_value(node, "item")
    msg = go_get_classvar_hook_or_value(node, "msg")

    # sscAssertEqual[T comparable](v1, v2 T, msg string) error
    return go_assert_func_add_error_check(
        node, call_func=f"sscAssertEqual({prv}, {item}, {msg})"
    )


@CONVERTER(ExprIsNotEqual.kind)
def pre_is_not_equal(node: ExprIsNotEqual) -> str:
    prv, _ = prev_next_var(node)
    item = go_get_classvar_hook_or_value(node, "item")
    msg = go_get_classvar_hook_or_value(node, "msg")

    # sscAssertNotEqual[T comparable](v1, v2 T, msg string) error
    return go_assert_func_add_error_check(
        node, call_func=f"sscAssertNotEqual({prv}, {item}, {msg})"
    )


@CONVERTER(ExprIsContains.kind)
def pre_is_contains(node: ExprIsContains) -> str:
    prv, _nxt = prev_next_var(node)
    item = go_get_classvar_hook_or_value(node, "item")
    msg = go_get_classvar_hook_or_value(node, "msg")

    # sscAssertContains[S ~[]E, E comparable](v1 S, v2 E, msg string) error
    return go_assert_func_add_error_check(
        node, call_func=f"sscAssertContains({prv}, {item}, {msg})"
    )


@CONVERTER(ExprStringIsRegex.kind)
def pre_is_regex(node: ExprStringIsRegex) -> str:
    prv, _ = prev_next_var(node)
    if node.classvar_hooks.get("pattern"):
        pattern = go_get_classvar_hook_or_value(node, "pattern")
    else:
        pattern, ignore_case, msg = node.unpack_args()
        pattern = py_regex_to_go_regex(pattern, ignore_case)

    msg = go_get_classvar_hook_or_value(node, "msg")
    # sscAssertRegex(v string, re *regexp.Regexp, msg string) error
    return go_assert_func_add_error_check(
        node,
        call_func=f"sscAssertRegex({prv}, regexp.MustCompile({pattern}), {msg})",
    )


@CONVERTER(ExprListStringAnyRegex.kind)
def pre_list_str_any_is_regex(node: ExprListStringAnyRegex) -> str:
    prv, _ = prev_next_var(node)
    if node.classvar_hooks.get("pattern"):
        pattern = go_get_classvar_hook_or_value(node, "pattern")
    else:
        pattern, ignore_case, msg = node.unpack_args()
        pattern = py_regex_to_go_regex(pattern, ignore_case)
    msg = go_get_classvar_hook_or_value(node, "msg")
    # sscAssertSliceAnyRegex(v []string, re *regexp.Regexp, msg string) error
    return go_assert_func_add_error_check(
        node,
        call_func=f"sscAssertSliceAnyRegex({prv}, regexp.MustCompile({pattern}), {msg})",
    )


@CONVERTER(ExprListStringAllRegex.kind)
def pre_list_str_all_is_regex(node: ExprListStringAllRegex) -> str:
    prv, _ = prev_next_var(node)
    if node.classvar_hooks.get("pattern"):
        pattern = go_get_classvar_hook_or_value(node, "pattern")
    else:
        pattern, ignore_case, msg = node.unpack_args()
        pattern = py_regex_to_go_regex(pattern, ignore_case)
    msg = go_get_classvar_hook_or_value(node, "msg")

    # sscAssertSliceAllRegex(v []string, re *regexp.Regexp, msg string) error
    return go_assert_func_add_error_check(
        node,
        call_func=f"sscAssertSliceAllRegex({prv}, regexp.MustCompile({pattern}), {msg})",
    )


@CONVERTER(ExprIsCss.kind)
def pre_is_css(node: ExprIsCss) -> str:
    prv, _ = prev_next_var(node)
    query = go_get_classvar_hook_or_value(node, "query")
    msg = go_get_classvar_hook_or_value(node, "msg")

    # sscAssertCss(v *goquery.Selection, query, msg string) error
    return go_assert_func_add_error_check(
        node, call_func=f"sscAssertCss({prv}, {query}, {msg})"
    )


@CONVERTER(ExprIsXpath.kind)
def pre_is_xpath(_: ExprIsXpath) -> str:
    raise NotImplementedError("goquery not support xpath")


@CONVERTER(ExprHasAttr.kind)
def pre_has_attr(node: ExprHasAttr) -> str:
    prv, _ = prev_next_var(node)
    key = go_get_classvar_hook_or_value(node, "key")
    msg = go_get_classvar_hook_or_value(node, "msg")

    # sscAssertHasAttr(v *goquery.Selection, key, msg string) error
    return go_assert_func_add_error_check(
        node, call_func=f"sscAssertHasAttr({prv}, {key}, {msg})"
    )


@CONVERTER(ExprListHasAttr.kind)
def pre_list_has_attr(node: ExprListHasAttr) -> str:
    prv, _ = prev_next_var(node)
    key = go_get_classvar_hook_or_value(node, "key")
    msg = go_get_classvar_hook_or_value(node, "msg")

    # sscAssertHasAttr(v *goquery.Selection, key, msg string) error
    return go_assert_func_add_error_check(
        node, call_func=f"sscAssertHasAttr({prv}, {key}, {msg})"
    )


@CONVERTER(ExprToInt.kind)
def pre_to_int(node: ExprToInt) -> str:
    prv, _ = prev_next_var(node)
    # func sscStrToInt(v string) (int, error)
    return go_func_add_error_check(node, call_func=f"sscStrToInt({prv})")


@CONVERTER(ExprToListInt.kind)
def pre_to_list_int(node: ExprToListInt) -> str:
    prv, _ = prev_next_var(node)
    # sscSliceStrToSliceInt(v []string) ([]int, error)
    return go_func_add_error_check(
        node, call_func=f"sscSliceStrToSliceInt({prv})"
    )


@CONVERTER(ExprToFloat.kind)
def pre_to_float(node: ExprToFloat) -> str:
    prv, _ = prev_next_var(node)
    # sscStrToFloat(v string) (float64, error)
    return go_func_add_error_check(node, call_func=f"sscStrToFloat({prv})")


@CONVERTER(ExprToListFloat.kind)
def pre_to_list_float(node: ExprToListFloat) -> str:
    prv, nxt = prev_next_var(node)
    # sscSliceStrToSliceFloat(v []string) ([]float64, error)
    return go_func_add_error_check(
        node, call_func=f"sscSliceStrToSliceFloat({prv})"
    )


@CONVERTER(ExprToListLength.kind)
def pre_to_len(node: ExprToListLength) -> str:
    prv, nxt = prev_next_var(node)
    return f"let {nxt} = len({prv}){END}"


@CONVERTER(ExprToBool.kind)
def pre_to_bool(node: ExprToBool) -> str:
    prv, nxt = prev_next_var(node)
    match node.ret_type:
        # https://pkg.go.dev/gopkg.in/goquery.v1#Selection.Length
        case VariableType.DOCUMENT | VariableType.LIST_DOCUMENT:
            code = f"{nxt} := {prv} != nil && {prv}.Length() > 0; "

        case VariableType.STRING:
            code = f'{nxt} := {prv} != nil && {prv} != ""; '

        # `0` is true
        case VariableType.INT | VariableType.FLOAT:
            code = f"{nxt} := {prv} != nil; "

        # build-in array
        case (
            VariableType.LIST_STRING
            | VariableType.LIST_INT
            | VariableType.LIST_FLOAT
        ):
            code = f"{nxt} := {prv} != nil && len({prv}) > 0; "
        case _:
            assert_never(node.prev.ret_type)
    return code  # noqa


@CONVERTER(ExprJsonify.kind)
def pre_jsonify(node: ExprJsonify) -> str:
    prv, nxt = prev_next_var(node)
    name, is_array, query = node.unpack_args()
    name = f"J{name}"

    # we work with unstructured undocumented data
    # anonymous json structs will add too much complexity
    # use gjson lib for simplify extract json part
    if query:
        query = wrap_double_quotes(query)
        if is_array:
            expr = (
                f"{nxt} := []{name}"
                + "{};\n"
                + f"json.Unmarshal([]byte(result{nxt}.Raw), &{nxt}); "
            )
        else:
            expr = (
                f"{nxt} := {name}"
                + "{}; "
                + f"json.Unmarshal([]byte(result{nxt}.Raw), &{nxt});"
            )
        return (
            f"result{nxt} := gjson.Get({prv}, {query});\n"
            + f"if !result{nxt}.Exists() "
            + BRACKET_START
            + f'return nil, fmt.Errorf("not valid json %v", {prv});\n'
            + BRACKET_END
            + "\n"
            + expr
        )

    # or use standart json module (not required complex extract logic for full parse json-like string)
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
    query = go_get_classvar_hook_or_value(node, "query")
    return f"{nxt} := {prv}.Find({query}).First(); "


@CONVERTER(ExprCssAll.kind)
def pre_css_all(node: ExprCssAll) -> str:
    prv, nxt = prev_next_var(node)
    query = go_get_classvar_hook_or_value(node, "query")
    return f"{nxt} := {prv}.Find({query}); "


@CONVERTER(ExprXpath.kind)
def pre_xpath(_: ExprXpath) -> str:
    raise NotImplementedError("goquery not support xpath")


@CONVERTER(ExprXpathAll.kind)
def pre_xpath_all(_: ExprXpathAll) -> str:
    raise NotImplementedError("goquery not support xpath")


@CONVERTER(ExprXpathElementRemove.kind)
def pre_xpath_remove_element(node: ExprCssElementRemove):
    raise NotImplementedError("goquery not support xpath")


@CONVERTER(ExprGetHtmlAttr.kind)
def pre_html_attr(node: ExprGetHtmlAttr) -> str:
    prv, nxt = prev_next_var(node)
    keys = node.kwargs["key"]
    if len(keys) == 1:
        key = keys[0]
        # singe call
        # sscGetAttr(a *goquery.Selection, key string) (string, error)
        key = wrap_double_quotes(key)
        return go_func_add_error_check(
            node, call_func=f"sscGetAttr({prv}, {key})"
        )
    # sscGetManyAttrs(a *goquery.Selection, keys []string) []string
    key = py_var_to_go_var(keys, VariableType.LIST_STRING)
    return f"{nxt} := sscGetManyAttrs({prv}, {key}){END}"


@CONVERTER(ExprGetHtmlAttrAll.kind)
def pre_html_attr_all(node: ExprGetHtmlAttrAll) -> str:
    prv, nxt = prev_next_var(node)
    keys = node.kwargs["key"]
    if len(keys) == 1:
        # singe call
        key = keys[0]
        key = wrap_double_quotes(keys[0])
        # sscEachGetAttrs(a *goquery.Selection, key string) ([]string, error)
        return go_func_add_error_check(
            node, call_func=f"sscEachGetAttrs({prv}, {key})"
        )
    key = py_var_to_go_var(keys)
    # sscEachGetManyAttrs(a *goquery.Selection, keys []string) []string
    return f"{nxt} := sscEachGetManyAttrs({prv}, {key}){END}"


@CONVERTER(ExprMapAttrs.kind)
def pre_html_map_attr(node: ExprMapAttrs) -> str:
    prv, nxt = prev_next_var(node)
    # sscMapAttrs(a *goquery.Selection) []string
    # FIXME: untests API: maybe wrong works in types DOCUMENT and LIST_DOCUMENT
    return f"{nxt} := sscMapAttrs({prv}); "


@CONVERTER(ExprMapAttrsAll.kind)
def pre_html_map_attr_all(node: ExprMapAttrsAll) -> str:
    prv, nxt = prev_next_var(node)
    # sscMapAttrs(a *goquery.Selection) []string
    # FIXME: untests API: maybe wrong works in types DOCUMENT and LIST_DOCUMENT
    return f"{nxt} := sscMapAttrs({prv}); "


@CONVERTER(ExprGetHtmlText.kind)
def pre_html_text(node: ExprGetHtmlText) -> str:
    prv, nxt = prev_next_var(node)
    return f"{nxt} := {prv}.Text(){END}"


@CONVERTER(ExprGetHtmlTextAll.kind)
def pre_html_text_all(node: ExprGetHtmlTextAll) -> str:
    prv, nxt = prev_next_var(node)
    # sscEachGetText(a *goquery.Selection) []string
    return f"{nxt} := sscEachGetText({prv}){END}"


@CONVERTER(ExprGetHtmlRaw.kind)
def pre_html_raw(node: ExprGetHtmlRaw) -> str:
    prv, nxt = prev_next_var(node)
    return go_func_add_error_check(node, f"{prv}.Html()")


@CONVERTER(ExprGetHtmlRawAll.kind)
def pre_html_raw_all(node: ExprGetHtmlRawAll) -> str:
    prv, nxt = prev_next_var(node)
    # sscHtmlRawAll(a *goquery.Selection) ([]string, error)
    return go_func_add_error_check(node, f"sscHtmlRawAll({prv})")


@CONVERTER(ExprStringRmPrefix.kind)
def pre_str_rm_prefix(node: ExprStringRmPrefix) -> str:
    prv, nxt = prev_next_var(node)
    substr = go_get_classvar_hook_or_value(node, "substr")
    return f"{nxt} := strings.TrimPrefix({prv}, {substr}){END}"


@CONVERTER(ExprListStringRmPrefix.kind)
def pre_list_str_rm_prefix(node: ExprListStringRmPrefix) -> str:
    prv, nxt = prev_next_var(node)
    substr = go_get_classvar_hook_or_value(node, "substr")
    #  sscSliceStrRmPrefix(v []string, p string) []string
    return f"{nxt} := sscSliceStrRmPrefix({prv}, {substr}){END}"


@CONVERTER(ExprStringRmSuffix.kind)
def pre_str_rm_suffix(node: ExprStringRmSuffix) -> str:
    prv, nxt = prev_next_var(node)
    substr = go_get_classvar_hook_or_value(node, "substr")
    return f"{nxt} := strings.TrimSuffix({prv}, {substr}){END}"


@CONVERTER(ExprListStringRmSuffix.kind)
def pre_list_str_rm_suffix(node: ExprListStringRmSuffix) -> str:
    prv, nxt = prev_next_var(node)
    substr = go_get_classvar_hook_or_value(node, "substr")
    # sscSliceStrRmSuffix(v []string, s string) []string
    return f"{nxt} := sscSliceStrRmSuffix({prv}, {substr}){END}"


@CONVERTER(ExprStringRmPrefixAndSuffix.kind)
def pre_str_rm_prefix_and_suffix(node: ExprStringRmPrefixAndSuffix) -> str:
    prv, nxt = prev_next_var(node)
    substr = go_get_classvar_hook_or_value(node, "substr")
    return f"{nxt} := strings.TrimSuffix(strings.TrimPrefix({prv}, {substr}), {substr}){END}"


@CONVERTER(ExprListStringRmPrefixAndSuffix.kind)
def pre_list_str_rm_prefix_and_suffix(
    node: ExprListStringRmPrefixAndSuffix,
) -> str:
    prv, nxt = prev_next_var(node)
    substr = go_get_classvar_hook_or_value(node, "substr")
    # sscSliceStrRmPrefixSuffix(v []string, p, s string) []string
    return f"{nxt} := sscSliceStrRmPrefixSuffix({prv}, {substr}, {substr}){END}"


@CONVERTER(ExprListUnique.kind)
def pre_list_str_unique(node: ExprListUnique) -> str:
    prv, nxt = prev_next_var(node)
    # func sscSliceStrUnique(v []string) []string
    return f"{nxt} := sscSliceStrUnique({prv}){END}"


@CONVERTER(ExprStringMapReplace.kind)
def pre_str_repl_map(node: ExprStringMapReplace) -> str:
    prv, nxt = prev_next_var(node)
    olds, news = node.unpack_args()
    # accept array as [old1, new1, old2, new2, ...]
    repl_arr = []
    for old, new in zip(olds, news):
        repl_arr.append(old)
        repl_arr.append(new)
    repl_map = py_var_to_go_var(repl_arr, VariableType.LIST_STRING)
    # sscStringReplaceWithMap(v string, m []string) string
    return f"{nxt} := sscStringReplaceWithMap({prv}, {repl_map}){END}"


@CONVERTER(ExprListStringMapReplace.kind)
def pre_list_str_repl_map(node: ExprListStringMapReplace) -> str:
    prv, nxt = prev_next_var(node)
    olds, news = node.unpack_args()
    # accept array as [old1, new1, old2, new2, ...]
    repl_arr = []
    for old, new in zip(olds, news):
        repl_arr.append(old)
        repl_arr.append(new)
    repl_map = py_var_to_go_var(repl_arr, VariableType.LIST_STRING)
    # sscSliceStringReplaceWithMap(v []string, p []string) []string
    return f"{nxt} := sscSliceStringReplaceWithMap({prv}, {repl_map}){END}"


@CONVERTER(ExprStringUnescape.kind)
def pre_str_unescape(node: ExprStringUnescape) -> str:
    prv, nxt = prev_next_var(node)
    # sscUnescape(s string) string
    return f"{nxt} := sscUnescape({prv}){END}"


@CONVERTER(ExprListStringUnescape.kind)
def pre_list_str_unescape(node: ExprListStringUnescape) -> str:
    prv, nxt = prev_next_var(node)
    # sscSliceUnescape(s []string) []string
    return f"{nxt} := sscSliceUnescape({prv}){END}"


# FILTERS
@CONVERTER(
    ExprFilter.kind,
    # close anon function and expression
    post_callback=lambda _: "});",
)
def pre_expr_filter(node: ExprFilter) -> str:
    prv, nxt = prev_next_var(node)
    # sscSliceStringFilter(v []string, f func(string) bool) []string
    # build anonym function for helper function
    return (
        f"{nxt} := sscSliceStringFilter({prv}, "
        + "func(s string) string { return "
    )


@CONVERTER(FilterOr.kind, post_callback=lambda _: ")")
def pre_filter_or(_node: FilterOr) -> str:
    return " || ("


@CONVERTER(FilterAnd.kind, post_callback=lambda _: ")")
def pre_filter_and(_node: FilterAnd) -> str:
    return " && ("


@CONVERTER(FilterNot.kind, post_callback=lambda _: ")")
def pre_filter_not(_node: FilterNot) -> str:  # type: ignore
    return "!("


@CONVERTER(FilterStrIn.kind)
def pre_filter_in(node: FilterStrIn) -> str:
    values, *_ = node.unpack_args()
    if len(values) == 1:
        value = py_var_to_go_var(values[0])
        expr = f"strings.Contains(s, {value})"
    else:
        value = py_var_to_go_var(values, VariableType.LIST_STRING)
        # sscAnyContainsSubstring(t string, s []string) bool
        expr = f"sscAnyContainsSubstring(s, {value})"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" && {expr}"
    return expr


@CONVERTER(FilterStrStarts.kind)
def pre_filter_starts_with(node: FilterStrStarts) -> str:
    values, *_ = node.unpack_args()
    if len(values) == 1:
        value = py_var_to_go_var(values[0])
        expr = f"strings.HasPrefix(s, {value})"
    else:
        value = py_var_to_go_var(values, VariableType.LIST_STRING)
        # func sscAnyStarts(t string, s []string) bool
        expr = f"sscAnyStarts(s, {value})"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" && {expr}"
    return expr


@CONVERTER(FilterStrEnds.kind)
def pre_filter_ends_with(node: FilterStrEnds) -> str:
    values, *_ = node.unpack_args()
    if len(values) == 1:
        value = py_var_to_go_var(values[0])
        expr = f"strings.HasSuffix(s, {value})"
    else:
        value = py_var_to_go_var(values)
        # func sscAnyEnds(t string, s []string) bool
        expr = f"sscAnyEnds(s, {value})"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" && {expr}"
    return expr


@CONVERTER(FilterStrRe.kind)
def pre_filter_re(node: FilterStrRe) -> str:
    pattern, ignore_case = node.unpack_args()
    if node.classvar_hooks.get("pattern"):
        pattern = go_get_classvar_hook_or_value(node, "pattern")
    else:
        pattern = py_regex_to_go_regex(pattern, ignore_case)

    expr = f"regexp.MustCompile({pattern}).MatchString(s)"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" && {expr}"
    return expr


@CONVERTER(FilterEqual.kind)
def pre_filter_eq(node: FilterEqual) -> str:
    values, *_ = node.unpack_args()
    if len(values) == 1:
        value = py_var_to_go_var(values[0])
        expr = f"s == {value}"
    else:
        value = py_var_to_go_var(values, VariableType.LIST_STRING)
        # func sscAnyEqual(t string, s []string) bool
        expr = f"sscAnyEqual(s, {value})"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" && {expr}"
    return expr


@CONVERTER(FilterNotEqual.kind)
def pre_filter_ne(node: FilterNotEqual) -> str:
    values, *_ = node.unpack_args()
    if len(values) == 1:
        value = py_var_to_go_var(values[0])
        expr = f"s != {value}"
    else:
        value = py_var_to_go_var(values)
        # sscAnyNotEqual(t string, s []string) bool
        expr = f"sscAnyNotEqual(s, {value})"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" && {expr}"
    return expr


@CONVERTER(FilterStrLenEq.kind)
def pre_filter_str_len_eq(node: FilterStrLenEq) -> str:
    length, *_ = node.unpack_args()
    expr = f"len(s) == {length}"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" && {expr}"
    return expr


@CONVERTER(FilterStrLenNe.kind)
def pre_filter_str_len_ne(node: FilterStrLenNe) -> str:
    length, *_ = node.unpack_args()
    expr = f"len(s) != {length}"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" && {expr}"
    return expr


@CONVERTER(FilterStrLenLt.kind)
def pre_filter_str_len_lt(node: FilterStrLenLt) -> str:
    length, *_ = node.unpack_args()
    expr = f"len(s) < {length}"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" && {expr}"
    return expr


@CONVERTER(FilterStrLenLe.kind)
def pre_filter_str_len_le(node: FilterStrLenLe) -> str:
    length, *_ = node.unpack_args()
    expr = f"len(s) <= {length}"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" && {expr}"
    return expr


@CONVERTER(FilterStrLenGt.kind)
def pre_filter_str_len_gt(node: FilterStrLenGt) -> str:
    length, *_ = node.unpack_args()
    expr = f"len(s) > {length}"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" && {expr}"
    return expr


@CONVERTER(FilterStrLenGe.kind)
def pre_filter_str_len_ge(node: FilterStrLenGe) -> str:
    length, *_ = node.unpack_args()
    expr = f"len(s) >= {length}"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return f" && {expr}"
    return expr


@CONVERTER(ExprCssElementRemove.kind)
def pre_css_remove_element(node: ExprCssElementRemove):
    prv, nxt = prev_next_var(node)
    query = go_get_classvar_hook_or_value(node, "query")
    return f"{prv}.RemoveFiltered({query}); {nxt} := {prv}; "
