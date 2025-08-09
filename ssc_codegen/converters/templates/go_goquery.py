from typing import Any, cast
from jinja2 import Template

from ssc_codegen.ast_.base import BaseAstNode
from ssc_codegen.ast_.nodes_core import (
    ExprCallStructClassVar,
    ExprCallStructMethod,
    ExprDefaultValueStart,
    StartParseMethod,
    StructParser,
)
from ssc_codegen.converters.helpers import (
    get_last_ret_type,
    get_struct_field_method_by_name,
    have_default_expr,
    is_last_var_no_ret,
    is_pre_validate_parent,
    prev_next_var,
)
from ssc_codegen.str_utils import to_lower_camel_case, to_upper_camel_case
from ssc_codegen.tokens import StructType, TokenType, VariableType

IMPORTS = """package $PACKAGE$

import (
    "fmt"
    "regexp"
    "strings"
    "slices"
    "strconv"
    "json"
    "github.com/tidwall/gjson"
    "github.com/PuerkitoBio/goquery"
)

"""
"""Default imports $PACKAGE$ varibale should be replaced to `main` or package folder"""


# poor golang syntax we are forced to make a collection of auxiliary functions
HELPER_FUNCTIONS = r"""
var (
    sscHexEntityRe  = regexp.MustCompile(`&#x([0-9a-fA-F]+);`)
    sscUnicodeEscRe = regexp.MustCompile(`\\u([0-9a-fA-F]{4})`)
    sscByteEscRe    = regexp.MustCompile(`\\x([0-9a-fA-F]{2})`)
    sscCharEscRe    = regexp.MustCompile(`\\([bfnrt])`)
    sscCharEscMap   = map[byte]string{'b': "\b", 'f': "\f", 'n': "\n", 'r': "\r", 't': "\t"}
    sscHtmlUnescMap = map[string]string{"&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": "\"", "&#039;": "'", "&#x2F;": "/", "&nbsp;": " "}
)

func mapStr(vs []string, f func(string) string) []string {
    r := make([]string, len(vs))
    for i, s := range vs {
        r[i] = f(s)
    }
    return r
}

func sscSliceStrFmt(v []string, t string) []string {
    return mapStr(v, func(s string) string { return fmt.Sprintf(t, s) })
}
func sscSliceStrTrim(v []string, c string) []string {
    return mapStr(v, func(s string) string { return strings.Trim(s, c) })
}
func sscSliceStrLTrim(v []string, c string) []string {
    return mapStr(v, func(s string) string { return strings.TrimLeft(s, c) })
}
func sscSliceStrRTrim(v []string, c string) []string {
    return mapStr(v, func(s string) string { return strings.TrimRight(s, c) })
}
func sscSliceStrRmPrefix(v []string, p string) []string {
    return mapStr(v, func(s string) string { return strings.TrimPrefix(s, p) })
}
func sscSliceStrRmSuffix(v []string, s string) []string {
    return mapStr(v, func(str string) string { return strings.TrimSuffix(str, s) })
}
func sscSliceStrReplace(v []string, o, n string) []string {
    return mapStr(v, func(s string) string { return strings.ReplaceAll(s, o, n) })
}

func sscSliceStrRmPrefixSuffix(v []string, p, s string) []string {
    return mapStr(v, func(str string) string { return strings.TrimSuffix(strings.TrimPrefix(str, p), s) })
}

func sscSliceStrReSub(v []string, re *regexp.Regexp, repl string) []string {
    return mapStr(v, func(s string) string { return re.ReplaceAllString(s, repl) })
}

func sscRegexMatch(v string, re *regexp.Regexp, g int) (string, error) {
    m := re.FindStringSubmatch(v)
    if m == nil {
        return "", fmt.Errorf("not found match %v", re)
    }
    return m[g], nil
}

func sscRegexFindAll(v string, re *regexp.Regexp) ([]string, error) {
    m := re.FindAllString(v, -1)
    if m == nil {
        return nil, fmt.Errorf("not found match %v", re)
    }
    return m, nil
}

func sscSliceStrToSliceInt(v []string) ([]int, error) {
    r := make([]int, 0, len(v))
    for _, s := range v {
        if i, err := strconv.Atoi(s); err != nil {
            return nil, err
        } else {
            r = append(r, i)
        }
    }
    return r, nil
}

func sscSliceStrToSliceFloat(v []string) ([]float64, error) {
    r := make([]float64, 0, len(v))
    for _, s := range v {
        if f, err := strconv.ParseFloat(s, 64); err != nil {
            return nil, err
        } else {
            r = append(r, f)
        }
    }
    return r, nil
}

func sscStrToInt(v string) (int, error)       { return strconv.Atoi(v) }
func sscStrToFloat(v string) (float64, error) { return strconv.ParseFloat(v, 64) }

func sscGetAttr(a *goquery.Selection, key string) (string, error) {
    if attr, ok := a.Attr(key); ok {
        return attr, nil
    }
    return "", fmt.Errorf("attr `%s` not exists", key)
}

func sscEachGetAttrs(a *goquery.Selection, key string) ([]string, error) {
    var r []string
    var err error
    a.Each(func(_ int, s *goquery.Selection) {
        if attr, ok := s.Attr(key); ok {
            r = append(r, attr)
        } else if err == nil {
            err = fmt.Errorf("attr `%s` not exists", key)
        }
    })
    return r, err
}

func sscGetManyAttrs(a *goquery.Selection, keys []string) []string {
    keys = []string{"a", "b", "c"}
    var r []string
    for _, k := range keys {
        if attr, ok := a.Attr(k); ok {
            r = append(r, attr)
        }
    }
    return r
}

func sscEachGetManyAttrs(a *goquery.Selection, keys []string) []string {
    var r []string
    a.Each(func(_ int, s *goquery.Selection) {
        for _, k := range keys {
            if attr, ok := s.Attr(k); ok {
                r = append(r, attr)
            }
        }
    })
    return r
}

func sscEachGetText(a *goquery.Selection) []string {
    var r []string
    a.Each(func(_ int, s *goquery.Selection) {
        r = append(r, s.Text())
    })
    return r
}

func sscUnescape(s string) string {
    s = strings.NewReplacer(
        "&amp;", "&", "&lt;", "<", "&gt;", ">", "&quot;", "\"",
        "&#039;", "'", "&#x2F;", "/", "&nbsp;", " ",
    ).Replace(s)

    s = sscHexEntityRe.ReplaceAllStringFunc(s, func(m string) string {
        if i, err := strconv.ParseInt(sscHexEntityRe.FindStringSubmatch(m)[1], 16, 64); err == nil {
            return string(rune(i))
        }
        return m
    })

    s = sscUnicodeEscRe.ReplaceAllStringFunc(s, func(m string) string {
        if i, err := strconv.ParseUint(sscUnicodeEscRe.FindStringSubmatch(m)[1], 16, 16); err == nil {
            return string(rune(i))
        }
        return m
    })

    s = sscByteEscRe.ReplaceAllStringFunc(s, func(m string) string {
        if i, err := strconv.ParseUint(sscByteEscRe.FindStringSubmatch(m)[1], 16, 8); err == nil {
            return string(byte(i))
        }
        return m
    })

    return sscCharEscRe.ReplaceAllStringFunc(s, func(m string) string {
        if repl, ok := sscCharEscMap[m[1]]; ok {
            return repl
        }
        return m
    })
}

func sscHtmlRawAll(a *goquery.Selection) ([]string, error) {
    var r []string
    var e error
    a.Each(func(_ int, s *goquery.Selection) {
        v, err := s.Html()
        if err != nil {
            e = err
            return
        }
        r = append(r, v)
    })
    if e != nil {
        return nil, e
    }
    return r, nil
}

func sscSliceUnescape(s []string) []string { return mapStr(s, sscUnescape) }

func sscAssertEqual[T comparable](v1, v2 T, msg string) error {
    if v1 != v2 {
        return fmt.Errorf(msg)
    }
    return nil
}

func sscAssertNotEqual[T comparable](v1, v2 T, msg string) error {
    if v1 == v2 {
        return fmt.Errorf(msg)
    }
    return nil
}

func sscAssertContains[S ~[]E, E comparable](v1 S, v2 E, msg string) error {
    if !(slices.Contains(v1, v2)) {
        return fmt.Errorf("%s", msg)
    }
    return nil
}

func sscAssertRegex(v string, re *regexp.Regexp, msg string) error {
    if !re.MatchString(v) {
        return fmt.Errorf(msg)
    }
    return nil
}

func sscAssertSliceAnyRegex(v []string, re *regexp.Regexp, msg string) error {
    for _, s := range v {
        if re.MatchString(s) {
            return nil
        }
    }
    return fmt.Errorf(msg)
}

func sscAssertSliceAllRegex(v []string, re *regexp.Regexp, msg string) error {
    for _, s := range v {
        if !re.MatchString(s) {
            return fmt.Errorf(msg)
        }
    }
    return nil
}

func sscAssertCss(v *goquery.Selection, query, msg string) error {
    found := false
    v.Find(query).EachWithBreak(func(_ int, _ *goquery.Selection) bool {
        found = true
        return false
    })
    if !found {
        return fmt.Errorf(msg)
    }
    return nil
}

func sscAssertHasAttr(v *goquery.Selection, key, msg string) error {
    if _, ok := v.Attr(key); !ok {
        return fmt.Errorf(msg)
    }
    return nil
}

func sscSliceStrUnique(v []string) []string {
    seen := make(map[string]bool, len(v))
    var r []string
    for _, s := range v {
        if !seen[s] {
            seen[s] = true
            r = append(r, s)
        }
    }
    return r
}

func sscStringReplaceWithMap(v string, p []string) string {
    return strings.NewReplacer(p...).Replace(v)
}

func sscSliceStringReplaceWithMap(v []string, p []string) []string {
    return mapStr(v, func(s string) string { return sscStringReplaceWithMap(s, p) })
}

func sscSliceStringFilter(v []string, f func(string) bool) []string {
    var r []string
    for _, s := range v {

        if f(s) {
            r = append(r, s)
        }
    }
    return r
}

func sscAnyStr(t []string, f func(string) bool) bool {
    for _, i := range t {
        if f(i) {
            return true
        }
    }
    return false
}

func sscAnyContainsSubstring(t string, s []string) bool {
    return sscAnyStr(s, func(s string) bool { return strings.Contains(t, s) })
}

func sscAnyStarts(t string, s []string) bool {
    return sscAnyStr(s, func(s string) bool { return strings.HasPrefix(t, s) })
}

func sscAnyEnds(t string, s []string) bool {
    return sscAnyStr(s, func(s string) bool { return strings.HasSuffix(t, s) })
}

func sscAnyEqual(t string, s []string) bool {
    return sscAnyStr(s, func(s string) bool { return t == s })
}

func sscAnyNotEqual(t string, s []string) bool {
    return sscAnyStr(s, func(s string) bool { return t != s })
}

func sscMapAttrs(a *goquery.Selection) []string {
    var r []string
    a.Each(func(_ int, s *goquery.Selection) {
        // parent node extract only
        for _, attr := range s.Nodes[0].Attr {
            r = append(r, attr.Val)
        }
    })
    return r
}
"""

_CODE_PRE_VALIDATE_CALL = """_, err := p.preValidate(p.Document.Selection);
if err != nil{
return nil, err;
}
"""

J2_START_PARSE_ITEM_BODY = Template("""
{% for var_name, method_name in methods %}
{#- required drop star char for Nested and Json structures -#}
{{ var_name.lstrip('*') }}, err := p.parse{{ method_name }}(p.Document.Selection);
if err != nil {
    return nil, err;
}
{% endfor %}
item := T{{ struct_name }} {
{{ st_args|join(', ') }},
};
return &item, nil;
}
""")


def go_parse_item_body(node: StructParser) -> str:
    assert node.struct_type == StructType.ITEM

    # st_args - pushed to struct as arguments
    struct_name, *_ = node.unpack_args()
    st_args: list[str] = []
    # var_name, method_name, is_classvar
    methods: list[tuple[str, str]] = []
    start_parse_node: StartParseMethod = node.find_node_by_token(
        StartParseMethod.kind
    )
    for field in start_parse_node.body:
        # MAGIC_METHODS = {"__ITEM__": "Item", "__KEY__": "Key", "__VALUE__": "Value",
        if isinstance(field, ExprCallStructMethod) and not field.kwargs[
            "name"
        ].startswith("__"):
            field = cast(ExprCallStructMethod, field)
            var_name = to_lower_camel_case(field.kwargs["field_name"])
            method_name = to_upper_camel_case(field.kwargs["name"])
            # TokenType.STRUCT_CALL_FUNCTION
            # get return type by field['kwargs']['type']
            if field.kwargs["type"] in (VariableType.NESTED, VariableType.JSON):
                var_name = "*" + var_name
            # remove pointer (st_args contains var names and insert to struct)
            st_args.append(var_name)
            methods.append((var_name, method_name))
        elif isinstance(field, ExprCallStructClassVar):
            field = cast(ExprCallStructClassVar, field)
            # add only classvar reference
            var_name = (
                field.kwargs["struct_name"]
                + "Cfg."
                + to_upper_camel_case(field.kwargs["field_name"])
            )
            st_args.append(var_name)

    return J2_START_PARSE_ITEM_BODY.render(
        methods=methods, st_args=st_args, struct_name=struct_name
    )


_J2_START_PARSE_LIST_BODY = Template(
    """
items := make([]T{{ struct_name }}, 0);
docParts, err := p.splitDoc(p.Document.Selection);
if err != nil {
    return nil, err;
}

for _, i := range docParts.EachIter() {
{% for var_name, method_name in methods %}
    {#- required drop star char for Nested and Json structures -#}
    {{ var_name.lstrip('*') }}, err := p.parse{{ method_name }}(i);
    if err != nil {
        return nil, err;
    }
{% endfor %}
    item := T{{ struct_name }} {
        {{ st_args|join(', ') }},
    };
    items = append(items, item);
}
return &items, nil;
}
"""
)


def go_parse_list_body(node: StructParser) -> str:
    assert node.struct_type == StructType.LIST

    struct_name, *_ = node.unpack_args()
    st_args: list[str] = []
    methods: list[tuple[str, str]] = []
    start_parse_node = node.find_node_by_token(TokenType.STRUCT_PARSE_START)

    for field in start_parse_node.body:
        field = cast(ExprCallStructMethod, field)
        # MAGIC_METHODS = {"__ITEM__": "Item", "__KEY__": "Key", "__VALUE__": "Value",
        if isinstance(field, ExprCallStructMethod) and not field.kwargs[
            "name"
        ].startswith("__"):
            method_name = to_upper_camel_case(field.kwargs["name"])
            var_name = to_lower_camel_case(method_name)
            if field.kwargs["type"] in (VariableType.NESTED, VariableType.JSON):
                var_name = "*" + var_name
            st_args.append(var_name)
            methods.append((var_name, method_name))
        elif isinstance(field, ExprCallStructClassVar):
            field = cast(ExprCallStructClassVar, field)
            # add only classvar reference
            var_name = (
                field.kwargs["struct_name"]
                + "Cfg."
                + to_upper_camel_case(field.kwargs["field_name"])
            )
            st_args.append(var_name)

    return _J2_START_PARSE_LIST_BODY.render(
        methods=methods, st_args=st_args, struct_name=struct_name
    )


_J2_START_PARSE_DICT_BODY = Template("""
items := make(T{{ struct_name }});
docParts, err := p.splitDoc(p.Document.Selection);
if err != nil {
    return nil, err;
}

for _, i := range docParts.EachIter() {
    key, err := p.parseKey(i);
    if err != nil {
        return nil, err;
    }

    {{ var_value }}, err := p.parseValue(i);
    if err != nil {
        return nil, err;
    }

    items[key] = {{ var_value }};
}

return &items, nil;
}
""")


def go_parse_dict_body(node: StructParser) -> str:
    assert node.struct_type == StructType.DICT

    struct_name, *_ = node.unpack_args()
    value_field = get_struct_field_method_by_name(node, "__VALUE__")
    default_is_nil = False
    if have_default_expr(value_field):
        expr_default = value_field.body[0]
        expr_default = cast(ExprDefaultValueStart, expr_default)
        default_is_nil = expr_default.kwargs["value"] is None
    var_value = "&value" if default_is_nil else "value"
    return _J2_START_PARSE_DICT_BODY.render(
        struct_name=struct_name, var_value=var_value
    )


_J2_START_PARSE_FLAT_LIST_BODY = Template(
    """
    items := make(T{{ struct_name }}, 0);
    docParts, err := p.splitDoc(p.Document.Selection);
    if err != nil {
        return nil, err;
    }

    for _, i := range docParts.EachIter() {
        {{ var }}, err := p.parseItem(i);
        if err != nil {
            return nil, err;
        }

        items = append(items, {{ var }});
    }

    return &items, nil;
    }
    """
)


def go_parse_flat_list_body(node: StructParser) -> str:
    assert node.struct_type == StructType.FLAT_LIST

    struct_name, *_ = node.unpack_args()
    item_field = get_struct_field_method_by_name(node, "__ITEM__")
    default_is_nil = False
    if have_default_expr(item_field):
        expr_default = item_field.body[0]
        expr_default = cast(ExprDefaultValueStart, expr_default)
        default_is_nil = expr_default.kwargs["value"] is None
    var = "&item" if default_is_nil else "item"
    return _J2_START_PARSE_FLAT_LIST_BODY.render(
        struct_name=struct_name, var=var
    )


# TODO: maybe conflict var and field names
_J2_START_PARSE_ACC_LIST_BODY = Template(
    """
__items := make(T{{ struct_name }}, 0);
{% for var_name, method_name in methods %}
{{ var_name }}, err := p.parse{{ method_name }}(p.Document.Selection);
if err != nil {
    return nil, err;
}
for _, i := range {{ var_name }} {
    __items = append(__items, i);
}
{% endfor %}
{# sscSliceStrUnique(v []string) []string #}
return &sscSliceStrUnique(__items), nil;
}
"""
)


def go_parse_acc_unique_list_body(node: StructParser) -> str:
    assert node.struct_type == StructType.ACC_LIST

    struct_name, *_ = node.unpack_args()
    st_args: list[str] = []
    methods: list[tuple[str, str]] = []
    start_parse_node = [
        i for i in node.body if i.kind == TokenType.STRUCT_PARSE_START
    ][0]

    for field in start_parse_node.body:
        field = cast(ExprCallStructMethod, field)
        # MAGIC_METHODS = {"__ITEM__": "Item", "__KEY__": "Key", "__VALUE__": "Value",
        if field.kwargs["name"].startswith("__"):
            continue
        method_name = to_upper_camel_case(field.kwargs["name"])
        var_name = to_lower_camel_case(method_name)
        st_args.append(var_name)
        methods.append((var_name, method_name))
    return _J2_START_PARSE_ACC_LIST_BODY.render(
        methods=methods, struct_name=struct_name
    )


_J2_PRE_NESTED = Template("""{{ tmp_doc }} := goquery.NewDocumentFromNode({{ prv }}.Nodes[0]);
{{ tmp_st }} := {{ sc_name }}{ {{ tmp_doc }} };
{{ nxt }}, err := {{ tmp_st }}.Parse();
if err != nil {
    return nil, err;
}
""")


RETURN_ERR_STUBS = {
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


def go_pre_validate_func_call() -> str:
    return _CODE_PRE_VALIDATE_CALL


def go_nested_expr_call(nxt_var: str, prv_var: str, schema_name: str) -> str:
    tmp_doc = f"{nxt_var}Doc"
    tmp_st = f"{nxt_var}St"
    return _J2_PRE_NESTED.render(
        tmp_doc=tmp_doc,
        tmp_st=tmp_st,
        nxt=nxt_var,
        prv=prv_var,
        sc_name=schema_name,
    )


J2_PRE_DEFAULT_START = Template("""defer func() {
    if r := recover(); r != nil {
{#- set err=nil if value == nil -#}
        err = nil;
        result = {{ value }};
    }
}()
{{ nxt }} := {{ prv }};
""")


def go_default_value(nxt_var: str, prv_var: str, value: Any) -> str:
    return J2_PRE_DEFAULT_START.render(nxt=nxt_var, prv=prv_var, value=value)


def go_func_add_error_check(
    node: BaseAstNode,
    call_func: str,
    err_var_stub: dict[VariableType, str] = RETURN_ERR_STUBS,
) -> str:
    """helper call function and generate error handle checks.
    Used for {{nxt_var}}, err := sscFunc(...) (T, error) functions

    - if node has default expr - add `panic(err)` (first expr rescue and set default value)
    - pre_validate function - add `return nil, err`
    - other - add stub error value from err_var_stub map

    """
    _, nxt_var = prev_next_var(node)
    expr = f"{nxt_var}, err := {call_func}; if err != nil " + "{ "
    if have_default_expr(node):
        expr += "panic(err); "
    elif is_pre_validate_parent(node):
        expr += "return nil, err; "
    else:
        ret_type = get_last_ret_type(node)
        value = err_var_stub.get(ret_type, "nil")
        expr += f"return {value}, err; "
    expr += "} "
    return expr


def go_assert_func_add_error_check(
    node: BaseAstNode,
    call_func: str,
    err_var_stub: dict[VariableType, str] = RETURN_ERR_STUBS,
) -> str:
    """helper call assert function and generate error handle checks.
    Used for err := sscAssert(...) (error) functions

    - if node has default expr - add `panic(err)` (first expr rescue and set default value)
    - pre_validate function - add `return nil, err`
    - other - add stub error value from err_var_stub map

    auto set assign value if last node not returns `nil` value
    """
    prv_var, nxt_var = prev_next_var(node)
    expr = f"err := {call_func}; if err != nil " + "{ "
    if have_default_expr(node):
        expr += "panic(err); "
    elif is_pre_validate_parent(node):
        expr += "return nil, err; "
    else:
        ret_type = get_last_ret_type(node)
        value = err_var_stub.get(ret_type, "nil")
        expr += f"return {value}, err; "
    expr += "} "
    if not is_last_var_no_ret(node):
        expr += f"{nxt_var} := {prv_var}; "
    return expr
