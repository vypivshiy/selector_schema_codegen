
"""code parts for go codegen"""
from typing import TYPE_CHECKING

from ssc_codegen.converters.utils import have_assert_expr, find_st_field_fn_by_call_st_fn, to_upper_camel_case, \
    have_start_parse_assert_expr, have_call_expr_assert_expr, find_nested_associated_typedef_by_typedef_field
from ssc_codegen.tokens import VariableType

if TYPE_CHECKING:
    from ssc_codegen.ast_ssc import StartParseFunction, TypeDef

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

# TODO: provide package set API in CLI
PACKAGE = "package $PACKAGE$"

# TODO: add github.com/antchfx/htmlquery API (xpath)
IMPORT_HEAD = "import ("
IMPORT_FOOTER = ")"
BASE_IMPORTS = """
    "fmt"
    "regexp"
    "strings"
    "slices"
"""
BRACKET_START = "{"
BRACKET_END = "}"


def DOCSTRING(docstring: str) -> str:  # noqa
    return f'\n'.join('// ' + line for line in docstring.split('\n'))


# type {TNAME} struct {
# Foo `json:foo`
# BarBaz `json:bar_baz`
# Zaz struct {
#
# } `json: zaz`
# }


STRUCT_VALUE = "document"
STRUCT_HEAD = "type {} struct"
STRUCT_BODY = "document *goquery.Document"
JSON_ANCHOR = '`json:"{}"`'
TYPE_PREFIX = "T{}"
TYPE_DICT = "map[string]{}"
TYPE_LIST = "[]{}"
TYPE_FLAT_LIST = "[]{}"
SINGLE_TYPEDEF_ASSIGN = "type {} = {}; "
TYPE_ITEM_HEAD = "type {} struct"
TYPE_ITEM_FIELD = "{} {} {}; "
"""NAME TYPE JSON_ANCHOR"""

PRE_VALIDATE_HEAD = 'func (p *{}) {}(value *goquery.Selection) error'
RET = "return {}; "
RET_NIL_ERR = "return nil, err;"
RET_VAL_NIL_ERR = "return {}, nil; "
NO_RET = "return nil; "
E_NESTED_NEW_DOC = "doc{} := goquery.NewDocumentFromNode({}.Nodes[0]); "


def E_PARSE_NESTED_ST(var_num: int, schema_name: str) -> str:  # noqa
    return f"st{var_num} := {schema_name}{{ doc{var_num} }}; "


E_NESTED_PARSE_CALL = "{} := st{}.Parse(); "

PART_DOC_HEAD = "func (p *{}) {}(value *goquery.Selection) *goquery.Selection"
PART_DOC_HEAD_ERR = "func (p *{}) {}(value *goquery.Selection) (*goquery.Selection, error)"
FN_PARSE_HEAD = "func (p *{}) Parse{}(value *goquery.Selection) {} "
FN_PARSE_HEAD_RET_ERR = "(*{}, error)"
FN_START_PARSE_HEAD = "func (p *{}) {}() {}"
FN_CALL_PARSE = "p.Parse{}({});"
FN_CALL_DOC_ARG = "p.document.Selection"


def E_PARSE_NESTED_ST(var_num: int, schema_name: str) -> str:  # noqa
    return f"st{var_num} := {schema_name}{{ doc{var_num} }}; "


def START_PARSE_CALL_PRE_VALIDATE(node: "StartParseFunction") -> str:  # noqa
    name = MAGIC_METHODS.get('__PRE_VALIDATE__')
    return (f"err := p.{name}(p.document.Selection); "
            + "if err != nil " + BRACKET_START
            + RET_NIL_ERR + BRACKET_END  # T{node.parent.name}
            )


E_NXT_ARRAY = "{} := make({}, 0); "  # get from TYPES map
"""NXT_VAR, TYPE"""

E_FOR_RANGE_HEAD = "for _, {} := range {}"
"""I_VAR, PRV (ITER)"""

E_FOR_RANGE_MAP_CODE = "{} = append({}, {}); "
"""NXT, NXT, CODE"""

E_STR_FMT = "{} := fmt.Sprintf({}, {}); "
E_STR_FMT_ALL = "fmt.Sprintf({}, {})"
"""TEMPLATE, I_VAR"""
E_STR_TRIM = "{} := strings.Trim({}, {});"
E_STR_TRIM_ALL = "strings.Trim({}, {})"
E_STR_LTRIM = "{} := strings.TrimLeft({}, {}); "
E_STR_LTRIM_ALL = "strings.TrimLeft({}, {})"
E_STR_RTRIM = "{} := strings.TrimRight({}, {});"
E_STR_RTRIM_ALL = "strings.TrimRight({}, {})"
E_STR_REPL = '{} := strings.Replace({}, {}, {}, -1); '
"""NXT PRV OLD NEW"""
E_STR_REPL_ALL = "strings.Replace({}, {}, {}, -1)"
"""IVAR OLD NEW"""
E_STR_SPLIT = "{} := strings.Split({}, {}); "
E_RE = "{} := regexp.MustCompile({}).FindStringSubmatch({})[{}]; "
E_RE_ALL = "{} := regexp.MustCompile({}).FindStringSubmatch({}); "
E_RE_SUB = "{} := string(regexp.MustCompile({}).ReplaceAll([]byte({}), []byte({}))); "
E_RE_SUB_ALL = "regexp.MustCompile({}).ReplaceAll({}, {})"
E_INDEX = "{} := {}[{}]; "
E_JOIN = "{} := strings.Join({}, {}); "
RET_NIL_FMT_ERR = "return nil, fmt.Errorf({}); "
RET_FMT_ERR = "return fmt.Errorf({}); "
E_EQ = "if !({} == {})"
E_ASSIGN = "{} := {}; "
E_NE = "if !({} != {})"
E_IN = "if !(slices.Contains({}, {}))"
E_IS_RE_ASSIGN = "_, {} := regexp.Match({}, []byte({})); "
"""ERR_VAR, PATTERN, PRV"""
E_IS_RE = "if {} != nil"
"""ERR_VAR"""


def gen_item_body(node: "StartParseFunction") -> str:
    body = ""
    st_args = []
    for field in node.body:
        if field.name in MAGIC_METHODS:
            continue
        # golang required manually handle errors
        method_name = to_upper_camel_case(field.name)
        var_name = f"{method_name}Raw"
        st_args.append(var_name)
        if have_assert_expr(find_st_field_fn_by_call_st_fn(field)):
            body += (
                    f"{var_name}, err := "
                    + FN_CALL_PARSE.format(method_name, FN_CALL_DOC_ARG)
                    + "if err != nil " + BRACKET_START
                    + RET_NIL_ERR
                    + BRACKET_END)
        else:
            body += (f"{var_name}"
                     + " := "
                     + FN_CALL_PARSE.format(method_name, FN_CALL_DOC_ARG))
    body += ("item := "
             + TYPE_PREFIX.format(node.parent.name) + BRACKET_START
             + ', '.join(st_args)
             + BRACKET_END + ';')
    body += RET_VAL_NIL_ERR.format("item") if have_start_parse_assert_expr(node) else RET.format("item")
    return body


def gen_list_body(node: "StartParseFunction") -> str:
    part_m = MAGIC_METHODS.get('__SPLIT_DOC__')
    st_args = []
    body = (f"items := make([]T{node.parent.name}, 0); "
            + f'for _, i := range p.{part_m}({FN_CALL_DOC_ARG}).EachIter() '
            + BRACKET_START
            )
    for field in node.body:
        if field.name in MAGIC_METHODS:
            continue
        method_name = to_upper_camel_case(field.name)
        var_name = f"{method_name}Raw"
        st_args.append(var_name)
        if have_assert_expr(find_st_field_fn_by_call_st_fn(field)):
            body += (f"{var_name}, err := "
                     + FN_CALL_PARSE.format(method_name, 'i')
                     + "if err != nil " + BRACKET_START
                     + RET_NIL_ERR + BRACKET_END)
        else:
            body += (var_name
                     + " := "
                     + FN_CALL_PARSE.format(method_name, 'i'))
    body += ("item := "
             + TYPE_PREFIX.format(node.parent.name) + BRACKET_START
             + ', '.join(st_args)
             + BRACKET_END + ';')
    body += ('items = append(items, item); '
             + BRACKET_END)
    body += RET_VAL_NIL_ERR.format("items") if have_start_parse_assert_expr(node) else RET.format("items")
    return body


def gen_dict_body(node: "StartParseFunction") -> str:
    key_m = MAGIC_METHODS.get('__KEY__')
    value_m = MAGIC_METHODS.get('__VALUE__')
    part_m = MAGIC_METHODS.get('__SPLIT_DOC__')
    fn_key = [fn for fn in node.body if fn.name == "__KEY__"][0]
    fn_value = [fn for fn in node.body if fn.name == "__VALUE__"][0]
    var_key = f"{key_m}Raw"
    var_value = f"{value_m}Raw"

    body = (f"items := make([]T{node.parent.name}, 0); "
            + f'for _, i := range p.{part_m}(p.doc.Selection).EachIter() ' + BRACKET_START
            )
    if have_call_expr_assert_expr(fn_key):
        body += (f"{var_key}, err := "
                 + FN_CALL_PARSE.format(key_m, 'i')
                 + "if err != nil " + BRACKET_START
                 + RET_NIL_ERR + BRACKET_END
                 )
    else:
        body += f"{var_key} := {FN_CALL_PARSE.format(key_m, 'i')}"
    if have_call_expr_assert_expr(fn_value):
        body += (f"{var_value}, err := "
                 + FN_CALL_PARSE.format(value_m, 'i')
                 + "if err != nil " + BRACKET_START
                 + RET_NIL_ERR + BRACKET_END
                 )
    else:
        body += f"{var_value} := {FN_CALL_PARSE.format(value_m, 'i')}"
    body += (f'items[{var_key}] = {var_value}; '
             + BRACKET_END)
    body += RET_VAL_NIL_ERR.format("items") if have_start_parse_assert_expr(node) else RET.format("items")
    return body


def gen_flat_list_body(node: "StartParseFunction") -> str:
    item_m = MAGIC_METHODS.get('__ITEM__')
    part_m = MAGIC_METHODS.get('__SPLIT_DOC__')
    fn_item = [fn for fn in node.body if fn.name == "__ITEM__"][0]
    # fixme: type template
    body = (f"items := make([]T{node.parent.name}, 0); "
            + f'for _, i := range p.{part_m}({FN_CALL_DOC_ARG}).EachIter()'
            + BRACKET_START)
    if have_call_expr_assert_expr(fn_item):
        body += (
                f"rawItem, err := {FN_CALL_PARSE.format(item_m, 'i')}"
                + "if err != nil" + BRACKET_START
                + RET_VAL_NIL_ERR + BRACKET_END
        )
    else:
        body += f"rawItem := {FN_CALL_PARSE.format(item_m, 'i')}"
    # fixme ITEM
    body += ('items = append(items, rawItem); '
             + BRACKET_END)
    body += RET_VAL_NIL_ERR.format("items") if have_start_parse_assert_expr(node) else RET.format("items")
    return body


def gen_flat_list_typedef(node: 'TypeDef') -> str:
    # type T_NAME = []T;
    t_name = TYPE_PREFIX.format(node.name)
    item_field = [i for i in node.body if i.name == "__ITEM__"][0]
    if item_field.type == VariableType.NESTED:
        associated_typedef = find_nested_associated_typedef_by_typedef_field(item_field)
        type_ = TYPE_PREFIX.format(associated_typedef.name)
    else:
        type_ = TYPES.get(item_field.type)
    type_ = TYPE_FLAT_LIST.format(type_)
    return SINGLE_TYPEDEF_ASSIGN.format(t_name, type_)


def gen_dict_typedef(node: 'TypeDef') -> str:
    # type T_NAME = map[String]T;
    t_name = TYPE_PREFIX.format(node.name)
    value_field = [i for i in node.body if i.name == "__VALUE__"][0]
    if value_field.type == VariableType.NESTED:
        associated_typedef = find_nested_associated_typedef_by_typedef_field(value_field)
        type_ = TYPE_PREFIX.format(associated_typedef.name)
    else:
        type_ = TYPES.get(value_field.type)
    type_ = TYPE_DICT.format(type_)
    return SINGLE_TYPEDEF_ASSIGN.format(t_name, type_)


def gen_struct_typedef(node: 'TypeDef') -> str:
    # type T_NAME struct { F1 String `json:f1`; ... }
    t_name = TYPE_PREFIX.format(node.name)
    typedef = TYPE_ITEM_HEAD.format(t_name) + ' ' + BRACKET_START
    for field in node.body:
        name = to_upper_camel_case(MAGIC_METHODS.get(field.name, field.name))
        if field.type == VariableType.NESTED:
            associated_typedef = find_nested_associated_typedef_by_typedef_field(field)
            type_ = TYPE_PREFIX.format(associated_typedef.name)
        else:
            type_ = TYPES.get(field.type)
        typedef += TYPE_ITEM_FIELD.format(name, type_, JSON_ANCHOR.format(field.name))
    typedef += ' ' + BRACKET_END
    return typedef
