from __future__ import annotations

import json

from ssc_codegen.converters.base import ConverterContext, BaseConverter
from ssc_codegen.converters.helpers import to_pascal_case, to_camel_case

from ssc_codegen.ast import VariableType, StructType

from ssc_codegen.ast import (
    Docstring,
    Imports,
    Utilities,
    JsonDef,
    JsonDefField,
    TypeDef,
    TypeDefField,
    Struct,
    StructDocstring,
    StartParse,
)

from ssc_codegen.ast import (
    Field,
    Init,
    InitField,
    PreValidate,
    SplitDoc,
    TableConfig,
    TableMatchKey,
    TableRow,
    Key,
    Value,
)

from ssc_codegen.ast import (
    CssSelect,
    CssSelectAll,
    XpathSelect,
    XpathSelectAll,
    CssRemove,
    XpathRemove,
    Attr,
    Text,
    Raw,
)

from ssc_codegen.ast import (
    Trim,
    Ltrim,
    Rtrim,
    RmPrefix,
    RmSuffix,
    RmPrefixSuffix,
    Fmt,
    Repl,
    ReplMap,
    Lower,
    Upper,
    Split,
    Join,
    Unescape,
    NormalizeSpace,
)

from ssc_codegen.ast import Re, ReAll, ReSub
from ssc_codegen.ast import Index, Slice, Len, Unique
from ssc_codegen.ast import ToInt, ToFloat, ToBool, Jsonify, Nested
from ssc_codegen.ast import FallbackStart, FallbackEnd, Self, Return
from ssc_codegen.ast import (
    Filter,
    Assert,
    Match,
    LogicAnd,
    LogicNot,
    LogicOr,
)

from ssc_codegen.ast import (
    PredCss,
    PredContains,
    PredCountEq,
    PredCountGt,
    PredCountLt,
    PredCountNe,
    PredCountGe,
    PredCountLe,
    PredCountRange,
    PredEnds,
    PredEq,
    PredGe,
    PredGt,
    PredLe,
    PredHasAttr,
    PredIn,
    PredLt,
    PredNe,
    PredRange,
    PredRe,
    PredReAll,
    PredReAny,
    PredStarts,
    PredXpath,
    PredAttrContains,
    PredAttrEnds,
    PredAttrEq,
    PredAttrNe,
    PredAttrRe,
    PredAttrStarts,
    PredTextContains,
    PredTextEnds,
    PredTextRe,
    PredTextStarts,
)

from ssc_codegen.ast import TransformCall


class GoGoqueryConverter(BaseConverter):
    def convert_all(self, module_ast, **meta):
        files = super().convert_all(module_ast, **meta)
        package = meta.get("package") or "parser"
        token = "__SSC_PACKAGE__"
        for name, content in list(files.items()):
            files[name] = content.replace(token, package)
        return files


GO_GOQUERY_CONVERTER = GoGoqueryConverter(indent="\t")


def _go_str(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _go_literal(value) -> str:
    if value is None:
        return "nil"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return _go_str(value)
    return str(value)


def _go_str_slice(values) -> str:
    body = ", ".join(_go_str(v) for v in values)
    return f"[]string{{{body}}}"


def _go_method(name: str) -> str:
    c = to_camel_case(name)
    return c[0].upper() + c[1:] if c else "X"


def _go_pred(cond: str, ctx: ConverterContext) -> str:
    if ctx.index == 0:
        return f"{ctx.indent}{cond}"
    return f"{ctx.indent}&& {cond}"


def _go_json_tag(name: str, *, omitempty: bool = False) -> str:
    suffix = ",omitempty" if omitempty else ""
    return f'`json:"{name}{suffix}"`'


def _go_type_from_jsondef_field(node: JsonDefField) -> str:
    prim = {
        "str": "string",
        "int": "int",
        "float": "float64",
        "bool": "bool",
        "any": "any",
    }
    if node.ref_name:
        type_ = f"{to_pascal_case(node.ref_name)}Json"
    else:
        type_ = prim.get(node.type_name, "any")
    if node.is_array:
        type_ = f"[]{type_}"
    elif node.is_optional:
        type_ = f"*{type_}"
    return type_


def _go_type_from_typedef_field(node: TypeDefField) -> str:
    basic = {
        VariableType.STRING: "string",
        VariableType.BOOL: "bool",
        VariableType.INT: "int",
        VariableType.FLOAT: "float64",
        VariableType.NULL: "any",
        VariableType.LIST_STRING: "[]string",
        VariableType.LIST_INT: "[]int",
        VariableType.LIST_FLOAT: "[]float64",
        VariableType.OPT_STRING: "*string",
        VariableType.OPT_INT: "*int",
        VariableType.OPT_FLOAT: "*float64",
    }
    if node.ret == VariableType.JSON:
        type_ = "any"
        if node.json_ref:
            type_ = f"{to_pascal_case(node.json_ref)}Json"
        if node.is_array:
            return f"[]{type_}"
        return type_
    if node.ret == VariableType.NESTED:
        type_ = "any"
        if node.nested_ref:
            type_ = f"{to_pascal_case(node.nested_ref)}Type"
        if node.is_array:
            return f"[]{type_}"
        return type_
    return basic.get(node.ret, "any")


def _go_ret_info_from_pipeline_node(node: Field | Value) -> tuple[str, bool]:
    """Return (go_type, is_optional_pointer) for parser output nodes."""
    if node.ret == VariableType.JSON:
        schema_name = None
        is_array = False
        for op in node.body:
            if isinstance(op, Jsonify):
                schema_name = op.schema_name
                is_array = op.is_array
                break
        base = f"{to_pascal_case(schema_name)}Json" if schema_name else "any"
        return (f"[]{base}" if is_array else base, False)
    if node.ret == VariableType.NESTED:
        struct_name = None
        is_array = False
        for op in node.body:
            if isinstance(op, Nested):
                struct_name = op.struct_name
                is_array = op.is_array
                break
        base = f"{to_pascal_case(struct_name)}Type" if struct_name else "any"
        return (f"[]{base}" if is_array else base, False)

    match node.ret:
        case VariableType.STRING:
            return ("string", False)
        case VariableType.BOOL:
            return ("bool", False)
        case VariableType.INT:
            return ("int", False)
        case VariableType.FLOAT:
            return ("float64", False)
        case VariableType.LIST_STRING:
            return ("[]string", False)
        case VariableType.LIST_INT:
            return ("[]int", False)
        case VariableType.LIST_FLOAT:
            return ("[]float64", False)
        case VariableType.OPT_STRING:
            return ("*string", True)
        case VariableType.OPT_INT:
            return ("*int", True)
        case VariableType.OPT_FLOAT:
            return ("*float64", True)
        case VariableType.NULL:
            return ("any", False)
        case _:
            return ("any", False)


def _go_cast_expr(node: Field | Value, expr: str) -> str:
    type_, _is_optional = _go_ret_info_from_pipeline_node(node)
    if type_ == "string":
        return f"_sscAsString({expr})"
    if type_ == "[]string":
        return f"_sscAsStringSlice({expr})"
    if type_ == "int":
        return f"{expr}.(int)"
    if type_ == "[]int":
        return f"{expr}.([]int)"
    if type_ == "float64":
        return f"{expr}.(float64)"
    if type_ == "[]float64":
        return f"{expr}.([]float64)"
    if type_ == "bool":
        return f"{expr}.(bool)"
    if type_ == "*string":
        return f"_sscAsOptionalString({expr})"
    if type_ == "*int":
        return f"_sscAsOptionalInt({expr})"
    if type_ == "*float64":
        return f"_sscAsOptionalFloat({expr})"
    if type_.endswith("Json") or type_.startswith("[]") and type_.endswith("Json"):
        return f"_sscDecodeJSONAs[{type_}]({expr})"
    if type_.endswith("Type") or type_.startswith("[]") and type_.endswith("Type"):
        return expr
    return expr


def _go_type_from_var(vt: VariableType) -> str:
    mapping = {
        VariableType.STRING: "string",
        VariableType.BOOL: "bool",
        VariableType.INT: "int",
        VariableType.FLOAT: "float64",
        VariableType.NULL: "any",
        VariableType.LIST_STRING: "[]string",
        VariableType.LIST_INT: "[]int",
        VariableType.LIST_FLOAT: "[]float64",
        VariableType.DOCUMENT: "*SSelection",
        VariableType.LIST_DOCUMENT: "[]*SSelection",
        VariableType.OPT_STRING: "*string",
        VariableType.OPT_INT: "*int",
        VariableType.OPT_FLOAT: "*float64",
    }
    return mapping.get(vt, "any")


def _pipeline_owner(node) -> object | None:
    cur = getattr(node, "parent", None)
    while cur is not None:
        if isinstance(
            cur,
            (
                Field,
                InitField,
                Key,
                Value,
                SplitDoc,
                TableConfig,
                TableMatchKey,
                TableRow,
                PreValidate,
            ),
        ):
            return cur
        cur = getattr(cur, "parent", None)
    return None


@GO_GOQUERY_CONVERTER.file("sscgen_core.go")
def go_core(module, meta):
    package = meta.get("package") or "parser"

    go_imports = sorted(module.imports.transform_imports.get("go", set()))
    extra_imports = ""
    if go_imports:
        extra_imports = "\n" + "\n".join(f"\t{_go_str(line)}" for line in go_imports)

    return f'''package {package}

import (
\t"encoding/json"
\t"fmt"
\t"html"
\t"regexp"
\t"strconv"
\t"strings"
\n\t"github.com/PuerkitoBio/goquery"{extra_imports}
)

type SSelection = goquery.Selection

type _unmatchedTableRow struct{{}}

var UNMATCHED_TABLE_ROW = _unmatchedTableRow{{}}

func _sscNewRoot(document string) *SSelection {{
\tdoc, err := goquery.NewDocumentFromReader(strings.NewReader(document))
\tif err != nil {{
\t\tpanic(err)
\t}}
\treturn doc.Selection
}}

func _sscAsSelection(v any) *SSelection {{
\ts, ok := v.(*SSelection)
\tif !ok {{
\t\tpanic(fmt.Sprintf("expected *goquery.Selection, got %T", v))
\t}}
\treturn s
}}

func _sscAsSelectionSlice(v any) []*SSelection {{
\tif xs, ok := v.([]*SSelection); ok {{
\t\treturn xs
\t}}
\tpanic(fmt.Sprintf("expected []*goquery.Selection, got %T", v))
}}

func _sscAsString(v any) string {{
\ts, ok := v.(string)
\tif !ok {{
\t\tpanic(fmt.Sprintf("expected string, got %T", v))
\t}}
\treturn s
}}

func _sscAsStringSlice(v any) []string {{
\tif xs, ok := v.([]string); ok {{
\t\treturn xs
\t}}
\tpanic(fmt.Sprintf("expected []string, got %T", v))
}}

func _sscAsOptionalString(v any) *string {{
\tif v == nil {{
\t\treturn nil
\t}}
\ts := _sscAsString(v)
\treturn &s
}}

func _sscAsOptionalInt(v any) *int {{
\tif v == nil {{
\t\treturn nil
\t}}
\tn := v.(int)
\treturn &n
}}

func _sscAsOptionalFloat(v any) *float64 {{
\tif v == nil {{
\t\treturn nil
\t}}
\tn := v.(float64)
\treturn &n
}}

func _sscDecodeJSONAs[T any](v any) T {{
\traw, err := json.Marshal(v)
\tif err != nil {{
\t\tpanic(err)
\t}}
\tvar out T
\tif err := json.Unmarshal(raw, &out); err != nil {{
\t\tpanic(err)
\t}}
\treturn out
}}

func _sscCss(v any, query string) any {{
\treturn _sscAsSelection(v).Find(query).First()
}}

func _sscCssAll(v any, query string) any {{
\tsel := _sscAsSelection(v)
\tout := make([]*SSelection, 0)
\tsel.Find(query).Each(func(_ int, s *goquery.Selection) {{
\t\tout = append(out, s)
\t}})
\treturn out
}}

func _sscCssRemove(v any, query string) any {{
\t_sscAsSelection(v).Find(query).Each(func(_ int, s *goquery.Selection) {{
\t\ts.Remove()
\t}})
\treturn v
}}

func _sscAttr(v any, keys []string) any {{
\tif len(keys) == 0 {{
\t\tpanic("attr keys must not be empty")
\t}}
\tswitch t := v.(type) {{
\tcase *SSelection:
\t\tif len(keys) == 1 {{
\t\t\tval, _ := t.Attr(keys[0])
\t\t\treturn val
\t\t}}
\t\tout := make([]string, 0, len(keys))
\t\tfor _, k := range keys {{
\t\t\tif val, ok := t.Attr(k); ok {{
\t\t\t\tout = append(out, val)
\t\t\t}}
\t\t}}
\t\treturn out
\tcase []*SSelection:
\t\tout := make([]string, 0)
\t\tfor _, s := range t {{
\t\t\tfor _, k := range keys {{
\t\t\t\tif val, ok := s.Attr(k); ok {{
\t\t\t\t\tout = append(out, val)
\t\t\t\t\tif len(keys) == 1 {{
\t\t\t\t\t\tbreak
\t\t\t\t\t}}
\t\t\t\t}}
\t\t\t}}
\t\t}}
\t\treturn out
\tdefault:
\t\tpanic(fmt.Sprintf("attr expected selection or selection list, got %T", v))
\t}}
}}

func _sscText(v any) any {{
\tswitch t := v.(type) {{
\tcase *SSelection:
\t\treturn t.Text()
\tcase []*SSelection:
\t\tout := make([]string, 0, len(t))
\t\tfor _, s := range t {{
\t\t\tout = append(out, s.Text())
\t\t}}
\t\treturn out
\tdefault:
\t\tpanic(fmt.Sprintf("text expected selection or selection list, got %T", v))
\t}}
}}

func _sscRaw(v any) any {{
\tswitch t := v.(type) {{
\tcase *SSelection:
\t\th, err := goquery.OuterHtml(t)
\t\tif err != nil {{
\t\t\tpanic(err)
\t\t}}
\t\treturn h
\tcase []*SSelection:
\t\tout := make([]string, 0, len(t))
\t\tfor _, s := range t {{
\t\t\th, err := goquery.OuterHtml(s)
\t\t\tif err != nil {{
\t\t\t\tpanic(err)
\t\t\t}}
\t\t\tout = append(out, h)
\t\t}}
\t\treturn out
\tdefault:
\t\tpanic(fmt.Sprintf("raw expected selection or selection list, got %T", v))
\t}}
}}

func _sscMapString(v any, fn func(string) string) any {{
\tswitch t := v.(type) {{
\tcase string:
\t\treturn fn(t)
\tcase []string:
\t\tout := make([]string, len(t))
\t\tfor i, s := range t {{
\t\t\tout[i] = fn(s)
\t\t}}
\t\treturn out
\tdefault:
\t\tpanic(fmt.Sprintf("expected string or []string, got %T", v))
\t}}
}}

func _sscRe(pattern string, v any) any {{
\trx := regexp.MustCompile(pattern)
\tif s, ok := v.(string); ok {{
\t\tm := rx.FindStringSubmatch(s)
\t\tif len(m) < 2 {{
\t\t\tpanic("regex has no capture group match")
\t\t}}
\t\treturn m[1]
\t}}
\txs := _sscAsStringSlice(v)
\tout := make([]string, 0, len(xs))
\tfor _, s := range xs {{
\t\tm := rx.FindStringSubmatch(s)
\t\tif len(m) < 2 {{
\t\t\tpanic("regex has no capture group match")
\t\t}}
\t\tout = append(out, m[1])
\t}}
\treturn out
}}

func _sscReAll(pattern string, s string) []string {{
\trx := regexp.MustCompile(pattern)
\tmatches := rx.FindAllStringSubmatch(s, -1)
\tout := make([]string, 0, len(matches))
\tfor _, m := range matches {{
\t\tif len(m) > 1 {{
\t\t\tout = append(out, m[1])
\t\t}}
\t}}
\treturn out
}}

func _sscReSub(pattern, repl string, v any) any {{
\trx := regexp.MustCompile(pattern)
\treturn _sscMapString(v, func(s string) string {{
\t\treturn rx.ReplaceAllString(s, repl)
\t}})
}}

func _sscToInt(v any) any {{
\tif s, ok := v.(string); ok {{
\t\tn, err := strconv.Atoi(strings.TrimSpace(s))
\t\tif err != nil {{
\t\t\tpanic(err)
\t\t}}
\t\treturn n
\t}}
\txs := _sscAsStringSlice(v)
\tout := make([]int, len(xs))
\tfor i, s := range xs {{
\t\tn, err := strconv.Atoi(strings.TrimSpace(s))
\t\tif err != nil {{
\t\t\tpanic(err)
\t\t}}
\t\tout[i] = n
\t}}
\treturn out
}}

func _sscToFloat(v any) any {{
\tif s, ok := v.(string); ok {{
\t\tn, err := strconv.ParseFloat(strings.TrimSpace(s), 64)
\t\tif err != nil {{
\t\t\tpanic(err)
\t\t}}
\t\treturn n
\t}}
\txs := _sscAsStringSlice(v)
\tout := make([]float64, len(xs))
\tfor i, s := range xs {{
\t\tn, err := strconv.ParseFloat(strings.TrimSpace(s), 64)
\t\tif err != nil {{
\t\t\tpanic(err)
\t\t}}
\t\tout[i] = n
\t}}
\treturn out
}}

func _sscToBool(v any) bool {{
\tswitch t := v.(type) {{
\tcase bool:
\t\treturn t
\tcase string:
\t\treturn strings.TrimSpace(t) != ""
\tcase int:
\t\treturn t != 0
\tcase float64:
\t\treturn t != 0
\tcase []string:
\t\treturn len(t) > 0
\tcase []*SSelection:
\t\treturn len(t) > 0
\tdefault:
\t\treturn v != nil
\t}}
}}

func _sscFilter(v any, fn func(any) bool) any {{
\tswitch t := v.(type) {{
\tcase []string:
\t\tout := make([]string, 0, len(t))
\t\tfor _, i := range t {{
\t\t\tif fn(i) {{
\t\t\t\tout = append(out, i)
\t\t\t}}
\t\t}}
\t\treturn out
\tcase []*SSelection:
\t\tout := make([]*SSelection, 0, len(t))
\t\tfor _, i := range t {{
\t\t\tif fn(i) {{
\t\t\t\tout = append(out, i)
\t\t\t}}
\t\t}}
\t\treturn out
\tdefault:
\t\tpanic(fmt.Sprintf("filter expects list, got %T", v))
\t}}
}}

func _sscLen(v any) int {{
\tswitch t := v.(type) {{
\tcase []string:
\t\treturn len(t)
\tcase []*SSelection:
\t\treturn len(t)
\tcase []int:
\t\treturn len(t)
\tcase []float64:
\t\treturn len(t)
\tdefault:
\t\tpanic(fmt.Sprintf("len expects list, got %T", v))
\t}}
}}

func _sscIndex(v any, i int) any {{
\tswitch t := v.(type) {{
\tcase []string:
\t\tif i < 0 {{
\t\t\ti = len(t) + i
\t\t}}
\t\treturn t[i]
\tcase []*SSelection:
\t\tif i < 0 {{
\t\t\ti = len(t) + i
\t\t}}
\t\treturn t[i]
\tdefault:
\t\tpanic(fmt.Sprintf("index expects list, got %T", v))
\t}}
}}

func _sscSlice(v any, start, end int) any {{
\tswitch t := v.(type) {{
\tcase []string:
\t\tif start < 0 {{
\t\t\tstart = len(t) + start
\t\t}}
\t\tif end < 0 {{
\t\t\tend = len(t) + end
\t\t}}
\t\treturn t[start:end]
\tcase []*SSelection:
\t\tif start < 0 {{
\t\t\tstart = len(t) + start
\t\t}}
\t\tif end < 0 {{
\t\t\tend = len(t) + end
\t\t}}
\t\treturn t[start:end]
\tdefault:
\t\tpanic(fmt.Sprintf("slice expects list, got %T", v))
\t}}
}}

func _sscUnique(v any) any {{
\txs := _sscAsStringSlice(v)
\tseen := map[string]struct{{}}{{}}
\tout := make([]string, 0, len(xs))
\tfor _, s := range xs {{
\t\tif _, ok := seen[s]; !ok {{
\t\t\tseen[s] = struct{{}}{{}}
\t\t\tout = append(out, s)
\t\t}}
\t}}
\treturn out
}}

func _sscJSON(v any) any {{
\tvar out any
\tif err := json.Unmarshal([]byte(_sscAsString(v)), &out); err != nil {{
\t\tpanic(err)
\t}}
\treturn out
}}

func _sscJSONPath(v any, path []any) any {{
\tcur := _sscJSON(v)
\tfor _, p := range path {{
\t\tswitch idx := p.(type) {{
\t\tcase int:
\t\t\tcur = cur.([]any)[idx]
\t\tcase string:
\t\t\tcur = cur.(map[string]any)[idx]
\t\tdefault:
\t\t\tpanic(fmt.Sprintf("unsupported json path segment %T", p))
\t\t}}
\t}}
\treturn cur
}}

func _sscStrContains(v any, values []string) bool {{
\ts := _sscAsString(v)
\tfor _, x := range values {{
\t\tif strings.Contains(s, x) {{
\t\t\treturn true
\t\t}}
\t}}
\treturn false
}}

func _sscStrStarts(v any, values []string) bool {{
\ts := _sscAsString(v)
\tfor _, x := range values {{
\t\tif strings.HasPrefix(s, x) {{
\t\t\treturn true
\t\t}}
\t}}
\treturn false
}}

func _sscStrEnds(v any, values []string) bool {{
\ts := _sscAsString(v)
\tfor _, x := range values {{
\t\tif strings.HasSuffix(s, x) {{
\t\t\treturn true
\t\t}}
\t}}
\treturn false
}}

func _sscPredCss(v any, query string) bool {{
\treturn _sscAsSelection(v).Find(query).Length() > 0
}}

func _sscPredHasAttr(v any, attrs []string) bool {{
\ts := _sscAsSelection(v)
\tfor _, k := range attrs {{
\t\tif _, ok := s.Attr(k); !ok {{
\t\t\treturn false
\t\t}}
\t}}
\treturn true
}}

func _sscPredAttr(v any, name string) string {{
\tval, _ := _sscAsSelection(v).Attr(name)
\treturn val
}}

func _sscPredText(v any) string {{
\treturn _sscAsSelection(v).Text()
}}
'''


@GO_GOQUERY_CONVERTER(Docstring)
def pre_docstring(node: Docstring, _):
    if not node.value:
        return "// autogenerated by ssc-gen. DO NOT EDIT"
    lines = ["// autogenerated by ssc-gen. DO NOT EDIT"]
    for line in node.value.splitlines():
        lines.append(f"// {line}" if line else "//")
    return lines


@GO_GOQUERY_CONVERTER(Imports)
def pre_imports(node: Imports, _):
    return [
        "package __SSC_PACKAGE__",
        "",
        "import (",
        '\t"html"',
        '\t"regexp"',
        '\t"strings"',
        ")",
        "",
        "var (",
        "\t_ = html.UnescapeString",
        "\t_ = regexp.MustCompile",
        "\t_ = strings.TrimSpace",
        ")",
        "",
    ]


@GO_GOQUERY_CONVERTER(Utilities)
def pre_utilities(node: Utilities, _):
    return None


@GO_GOQUERY_CONVERTER(JsonDef)
def pre_json_def(node: JsonDef, _):
    name = to_pascal_case(node.name)
    return [f"type {name}Json struct {{"]


@GO_GOQUERY_CONVERTER(JsonDefField)
def pre_json_def_field(node: JsonDefField, _):
    field_name = _go_method(node.name)
    json_name = node.alias or node.name
    type_ = _go_type_from_jsondef_field(node)
    return f"\t{field_name} {type_} {_go_json_tag(json_name, omitempty=node.is_optional)}"


@GO_GOQUERY_CONVERTER.post(JsonDef)
def post_json_def(node: JsonDef, _):
    return ["}", ""]


@GO_GOQUERY_CONVERTER(TypeDef)
def pre_type_def(node: TypeDef, _):
    name = to_pascal_case(node.name)
    if node.struct_type == StructType.DICT:
        value_field = next(
            (f for f in node.fields if to_camel_case(f.name) == "value"),
            None,
        )
        value_type = (
            _go_type_from_typedef_field(value_field) if value_field else "any"
        )
        return [f"type {name}Type map[string]{value_type}", ""]
    if node.struct_type == StructType.FLAT:
        return [f"type {name}Type []string", ""]
    return [f"type {name}Type struct {{"]


@GO_GOQUERY_CONVERTER(TypeDefField)
def pre_type_def_field(node: TypeDefField, _):
    if node.typedef.struct_type in (StructType.DICT, StructType.FLAT):
        return None
    field_name = _go_method(node.name)
    json_name = to_camel_case(node.name)
    type_ = _go_type_from_typedef_field(node)
    omitempty = node.ret in (
        VariableType.OPT_STRING,
        VariableType.OPT_INT,
        VariableType.OPT_FLOAT,
    )
    return f"\t{field_name} {type_} {_go_json_tag(json_name, omitempty=omitempty)}"


@GO_GOQUERY_CONVERTER.post(TypeDef)
def post_type_def(node: TypeDef, _):
    if node.struct_type in (StructType.DICT, StructType.FLAT):
        return None
    return ["}", ""]


@GO_GOQUERY_CONVERTER(Struct)
def pre_struct(node: Struct, _):
    name = to_pascal_case(node.name)
    init = next((n for n in node.body if isinstance(n, Init)), None)
    lines = [f"type {name} struct {{", "\tdoc *SSelection"]
    if init:
        for child in init.body:
            if isinstance(child, InitField):
                lines.append(f"\t_{to_camel_case(child.name)} any")
    lines += ["}", ""]
    return lines


@GO_GOQUERY_CONVERTER(StructDocstring)
def pre_struct_docstring(node: StructDocstring, _):
    return None


@GO_GOQUERY_CONVERTER(Init)
def pre_init(node: Init, ctx: ConverterContext):
    struct_name = to_pascal_case(node.parent.name)
    recv = to_camel_case(struct_name)
    lines = [
        f"func New{struct_name}(document string) *{struct_name} {{",
        f"\t{recv} := &{struct_name}{{doc: _sscNewRoot(document)}}",
    ]
    for child in node.body:
        if isinstance(child, InitField):
            method = _go_method(child.name)
            field = to_camel_case(child.name)
            lines.append(f"\t{recv}._{field} = {recv}._init{method}({recv}.doc)")
    lines += [f"\treturn {recv}", "}", "", f"func new{struct_name}FromSelection(sel *SSelection) *{struct_name} {{", f"\t{recv} := &{struct_name}{{doc: sel}}"]
    for child in node.body:
        if isinstance(child, InitField):
            method = _go_method(child.name)
            field = to_camel_case(child.name)
            lines.append(f"\t{recv}._{field} = {recv}._init{method}({recv}.doc)")
    lines += [f"\treturn {recv}", "}"]
    return lines


@GO_GOQUERY_CONVERTER(InitField)
def pre_init_field(node: InitField, _):
    struct_name = to_pascal_case(node.parent.parent.name)
    method = _go_method(node.name)
    recv = to_camel_case(struct_name)
    ret_type = _go_type_from_var(node.ret)
    return [f"func ({recv} *{struct_name}) _init{method}(v any) {ret_type} {{"]


@GO_GOQUERY_CONVERTER.post(InitField)
def post_init_field(node: InitField, _):
    return ["}"]


@GO_GOQUERY_CONVERTER(Field)
def pre_field(node: Field, _):
    struct_name = to_pascal_case(node.parent.name)
    method = _go_method(node.name)
    recv = to_camel_case(struct_name)
    ret_type = "any"
    if node.accept != VariableType.STRING:
        ret_type, _ = _go_ret_info_from_pipeline_node(node)
    return [f"func ({recv} *{struct_name}) _parse{method}(v any) {ret_type} {{"]


@GO_GOQUERY_CONVERTER.post(Field)
def post_field(node: Field, _):
    return ["}"]


@GO_GOQUERY_CONVERTER(PreValidate)
def pre_pre_validate(node: PreValidate, _):
    struct_name = to_pascal_case(node.parent.name)
    recv = to_camel_case(struct_name)
    return [f"func ({recv} *{struct_name}) _preValidate(v any) {{"]


@GO_GOQUERY_CONVERTER.post(PreValidate)
def post_pre_validate(node: PreValidate, _):
    return ["}"]


@GO_GOQUERY_CONVERTER(SplitDoc)
def pre_split_doc(node: SplitDoc, _):
    struct_name = to_pascal_case(node.parent.name)
    recv = to_camel_case(struct_name)
    return [f"func ({recv} *{struct_name}) _splitDoc(v any) []*SSelection {{"]


@GO_GOQUERY_CONVERTER.post(SplitDoc)
def post_split_doc(node: SplitDoc, _):
    return ["}"]


@GO_GOQUERY_CONVERTER(Key)
def pre_key(node: Key, _):
    struct_name = to_pascal_case(node.parent.name)
    recv = to_camel_case(struct_name)
    return [f"func ({recv} *{struct_name}) _parseKey(v any) string {{"]


@GO_GOQUERY_CONVERTER.post(Key)
def post_key(node: Key, _):
    return ["}"]


@GO_GOQUERY_CONVERTER(Value)
def pre_value(node: Value, _):
    struct_name = to_pascal_case(node.parent.name)
    recv = to_camel_case(struct_name)
    ret_type, _ = _go_ret_info_from_pipeline_node(node)
    return [f"func ({recv} *{struct_name}) _parseValue(v any) {ret_type} {{"]


@GO_GOQUERY_CONVERTER.post(Value)
def post_value(node: Value, _):
    return ["}"]


@GO_GOQUERY_CONVERTER(TableConfig)
def pre_table_config(node: TableConfig, _):
    struct_name = to_pascal_case(node.parent.name)
    recv = to_camel_case(struct_name)
    return [f"func ({recv} *{struct_name}) _tableConfig(v any) *SSelection {{"]


@GO_GOQUERY_CONVERTER.post(TableConfig)
def post_table_config(node: TableConfig, _):
    return ["}"]


@GO_GOQUERY_CONVERTER(TableMatchKey)
def pre_table_match(node: TableMatchKey, _):
    struct_name = to_pascal_case(node.parent.name)
    recv = to_camel_case(struct_name)
    return [f"func ({recv} *{struct_name}) _tableMatchKey(v any) string {{"]


@GO_GOQUERY_CONVERTER.post(TableMatchKey)
def post_table_match(node: TableMatchKey, _):
    return ["}"]


@GO_GOQUERY_CONVERTER(TableRow)
def pre_table_rows(node: TableRow, _):
    struct_name = to_pascal_case(node.parent.name)
    recv = to_camel_case(struct_name)
    return [f"func ({recv} *{struct_name}) _tableRows(v any) []*SSelection {{"]


@GO_GOQUERY_CONVERTER.post(TableRow)
def post_table_rows(node: TableRow, _):
    return ["}"]


@GO_GOQUERY_CONVERTER(StartParse)
def pre_start_parse(node: StartParse, _):
    struct_name = to_pascal_case(node.struct.name)
    recv = to_camel_case(struct_name)
    ret_type = f"{struct_name}Type"
    if node.struct_type == StructType.LIST:
        ret_type = f"[]{ret_type}"
    return [f"func ({recv} *{struct_name}) Parse() {ret_type} {{"]


@GO_GOQUERY_CONVERTER.post(StartParse)
def post_start_parse(node: StartParse, ctx: ConverterContext):
    struct_name = to_pascal_case(node.struct.name)
    recv = to_camel_case(struct_name)
    out_type = f"{struct_name}Type"

    def _pmethod(field_name: str) -> str:
        return f"_parse{_go_method(field_name)}"

    lines = []
    if node.use_pre_validate:
        lines.append(f"\t{recv}._preValidate({recv}.doc)")

    match node.struct_type:
        case StructType.ITEM:
            lines.append(f"\tresult := {out_type}{{")
            for f in node.fields:
                key = _go_method(f.name)
                val = _go_cast_expr(f, f"{recv}.{_pmethod(f.name)}({recv}.doc)")
                lines.append(f"\t\t{key}: {val},")
            lines += ["\t}", "\treturn result"]
        case StructType.LIST:
            lines += [
                f"\tout := make([]{out_type}, 0)",
                f"\tfor _, i := range _sscAsSelectionSlice({recv}._splitDoc({recv}.doc)) {{",
                f"\t\trow := {out_type}{{",
            ]
            for f in node.fields:
                key = _go_method(f.name)
                val = _go_cast_expr(f, f"{recv}.{_pmethod(f.name)}(i)")
                lines.append(f"\t\t\t{key}: {val},")
            lines += ["\t\t}", "\t\tout = append(out, row)", "\t}", "\treturn out"]
        case StructType.DICT:
            _, value_field = node.fields_dict
            lines += [
                f"\tout := {out_type}{{}}",
                f"\tfor _, i := range _sscAsSelectionSlice({recv}._splitDoc({recv}.doc)) {{",
                (
                    f"\t\tout[_sscAsString({recv}._parseKey(i))] = "
                    f"{_go_cast_expr(value_field, f'{recv}._parseValue(i)')}"
                ),
                "\t}",
                "\treturn out",
            ]
        case StructType.FLAT:
            lines.append("\tout := make([]string, 0)")
            for f in node.fields:
                method = _pmethod(f.name)
                if f.ret == VariableType.STRING:
                    lines.append(f"\tout = append(out, _sscAsString({recv}.{method}({recv}.doc)))")
                else:
                    lines.append(f"\tout = append(out, _sscAsStringSlice({recv}.{method}({recv}.doc))...)")
            if node.struct.keep_order:
                lines += [f"\treturn {out_type}(_sscAsStringSlice(_sscUnique(out)))"]
            else:
                lines += [f"\treturn {out_type}(_sscAsStringSlice(_sscUnique(out)))"]
        case StructType.TABLE:
            lines += [
                f"\tresult := {out_type}{{}}",
                "\tseen := map[string]bool{}",
                f"\ttable := {recv}._tableConfig({recv}.doc)",
                f"\tfor _, row := range _sscAsSelectionSlice({recv}._tableRows(table)) {{",
            ]
            for f in node.fields:
                n = to_camel_case(f.name)
                method = _pmethod(f.name)
                lines.append(f"\t\tv_{n} := {recv}.{method}(row)")
                key = _go_method(f.name)
                val = _go_cast_expr(f, f"v_{n}")
                lines.append(
                    (
                        f"\t\tif v_{n} != UNMATCHED_TABLE_ROW && !seen[{_go_str(n)}] {{ "
                        f"result.{key} = {val}; seen[{_go_str(n)}] = true }}"
                    )
                )
            lines += ["\t}", "\treturn result"]
        case _:
            lines.append(f"\treturn {out_type}{{}}")

    lines.append("}")
    return lines


@GO_GOQUERY_CONVERTER(CssSelect)
def expr_css(node: CssSelect, ctx: ConverterContext):
    if node.queries:
        lines = [f"{ctx.indent}{ctx.nxt} := _sscCss({ctx.prv}, {_go_str(node.queries[0])})"]
        for q in node.queries[1:]:
            lines.append(f"{ctx.indent}if _sscAsSelection({ctx.nxt}).Length() == 0 {{")
            lines.append(f"{ctx.indent}\t{ctx.nxt} = _sscCss({ctx.prv}, {_go_str(q)})")
            lines.append(f"{ctx.indent}}}")
        return lines
    return f"{ctx.indent}{ctx.nxt} := _sscCss({ctx.prv}, {_go_str(node.query)})"


@GO_GOQUERY_CONVERTER(CssSelectAll)
def expr_css_all(node: CssSelectAll, ctx: ConverterContext):
    if node.queries:
        lines = [f"{ctx.indent}{ctx.nxt} := _sscCssAll({ctx.prv}, {_go_str(node.queries[0])})"]
        for q in node.queries[1:]:
            lines.append(f"{ctx.indent}if len(_sscAsSelectionSlice({ctx.nxt})) == 0 {{")
            lines.append(f"{ctx.indent}\t{ctx.nxt} = _sscCssAll({ctx.prv}, {_go_str(q)})")
            lines.append(f"{ctx.indent}}}")
        return lines
    return f"{ctx.indent}{ctx.nxt} := _sscCssAll({ctx.prv}, {_go_str(node.query)})"


@GO_GOQUERY_CONVERTER(XpathSelect)
def expr_xpath(node: XpathSelect, ctx: ConverterContext):
    raise NotImplementedError("go-goquery does not support xpath")


@GO_GOQUERY_CONVERTER(XpathSelectAll)
def expr_xpath_all(node: XpathSelectAll, ctx: ConverterContext):
    raise NotImplementedError("go-goquery does not support xpath")


@GO_GOQUERY_CONVERTER(CssRemove)
def expr_css_remove(node: CssRemove, ctx: ConverterContext):
    return f"{ctx.indent}{ctx.nxt} := _sscCssRemove({ctx.prv}, {_go_str(node.query)})"


@GO_GOQUERY_CONVERTER(XpathRemove)
def expr_xpath_remove(node: XpathRemove, ctx: ConverterContext):
    raise NotImplementedError("go-goquery does not support xpath")


@GO_GOQUERY_CONVERTER(Attr)
def expr_attr(node: Attr, ctx: ConverterContext):
    return f"{ctx.indent}{ctx.nxt} := _sscAttr({ctx.prv}, {_go_str_slice(node.keys)})"


@GO_GOQUERY_CONVERTER(Text)
def expr_text(node: Text, ctx: ConverterContext):
    return f"{ctx.indent}{ctx.nxt} := _sscText({ctx.prv})"


@GO_GOQUERY_CONVERTER(Raw)
def expr_raw(node: Raw, ctx: ConverterContext):
    return f"{ctx.indent}{ctx.nxt} := _sscRaw({ctx.prv})"


@GO_GOQUERY_CONVERTER(Trim)
def expr_trim(node: Trim, ctx: ConverterContext):
    sub = _go_str(node.substr) if node.substr is not None else '""'
    return f"{ctx.indent}{ctx.nxt} := _sscMapString({ctx.prv}, func(s string) string {{ return strings.Trim(s, {sub}) }})"


@GO_GOQUERY_CONVERTER(Ltrim)
def expr_ltrim(node: Ltrim, ctx: ConverterContext):
    sub = _go_str(node.substr) if node.substr is not None else '" \t\n\r"'
    return f"{ctx.indent}{ctx.nxt} := _sscMapString({ctx.prv}, func(s string) string {{ return strings.TrimLeft(s, {sub}) }})"


@GO_GOQUERY_CONVERTER(Rtrim)
def expr_rtrim(node: Rtrim, ctx: ConverterContext):
    sub = _go_str(node.substr) if node.substr is not None else '" \t\n\r"'
    return f"{ctx.indent}{ctx.nxt} := _sscMapString({ctx.prv}, func(s string) string {{ return strings.TrimRight(s, {sub}) }})"


@GO_GOQUERY_CONVERTER(NormalizeSpace)
def expr_normalize(node: NormalizeSpace, ctx: ConverterContext):
    return f"{ctx.indent}{ctx.nxt} := _sscMapString({ctx.prv}, func(s string) string {{ return strings.Join(strings.Fields(s), \" \") }})"


@GO_GOQUERY_CONVERTER(Lower)
def expr_lower(node: Lower, ctx: ConverterContext):
    return f"{ctx.indent}{ctx.nxt} := _sscMapString({ctx.prv}, strings.ToLower)"


@GO_GOQUERY_CONVERTER(Upper)
def expr_upper(node: Upper, ctx: ConverterContext):
    return f"{ctx.indent}{ctx.nxt} := _sscMapString({ctx.prv}, strings.ToUpper)"


@GO_GOQUERY_CONVERTER(RmPrefix)
def expr_rm_prefix(node: RmPrefix, ctx: ConverterContext):
    return f"{ctx.indent}{ctx.nxt} := _sscMapString({ctx.prv}, func(s string) string {{ return strings.TrimPrefix(s, {_go_str(node.substr)}) }})"


@GO_GOQUERY_CONVERTER(RmSuffix)
def expr_rm_suffix(node: RmSuffix, ctx: ConverterContext):
    return f"{ctx.indent}{ctx.nxt} := _sscMapString({ctx.prv}, func(s string) string {{ return strings.TrimSuffix(s, {_go_str(node.substr)}) }})"


@GO_GOQUERY_CONVERTER(RmPrefixSuffix)
def expr_rm_prefix_suffix(node: RmPrefixSuffix, ctx: ConverterContext):
    v = _go_str(node.substr)
    return f"{ctx.indent}{ctx.nxt} := _sscMapString({ctx.prv}, func(s string) string {{ return strings.TrimSuffix(strings.TrimPrefix(s, {v}), {v}) }})"


@GO_GOQUERY_CONVERTER(Fmt)
def expr_fmt(node: Fmt, ctx: ConverterContext):
    tmpl = _go_str(node.template)
    return f"{ctx.indent}{ctx.nxt} := _sscMapString({ctx.prv}, func(s string) string {{ return strings.ReplaceAll({tmpl}, \"{{{{}}}}\", s) }})"


@GO_GOQUERY_CONVERTER(Repl)
def expr_repl(node: Repl, ctx: ConverterContext):
    return f"{ctx.indent}{ctx.nxt} := _sscMapString({ctx.prv}, func(s string) string {{ return strings.ReplaceAll(s, {_go_str(node.old)}, {_go_str(node.new)}) }})"


@GO_GOQUERY_CONVERTER(ReplMap)
def expr_repl_map(node: ReplMap, ctx: ConverterContext):
    lines = [f"{ctx.indent}{ctx.nxt} := _sscMapString({ctx.prv}, func(s string) string {{"]
    for old, new in node.replacements:
        lines.append(f"{ctx.indent}\ts = strings.ReplaceAll(s, {_go_str(old)}, {_go_str(new)})")
    lines.append(f"{ctx.indent}\treturn s")
    lines.append(f"{ctx.indent}}})")
    return lines


@GO_GOQUERY_CONVERTER(Split)
def expr_split(node: Split, ctx: ConverterContext):
    return f"{ctx.indent}{ctx.nxt} := strings.Split(_sscAsString({ctx.prv}), {_go_str(node.sep)})"


@GO_GOQUERY_CONVERTER(Join)
def expr_join(node: Join, ctx: ConverterContext):
    return f"{ctx.indent}{ctx.nxt} := strings.Join(_sscAsStringSlice({ctx.prv}), {_go_str(node.sep)})"


@GO_GOQUERY_CONVERTER(Unescape)
def expr_unescape(node: Unescape, ctx: ConverterContext):
    return f"{ctx.indent}{ctx.nxt} := _sscMapString({ctx.prv}, html.UnescapeString)"


@GO_GOQUERY_CONVERTER(Re)
def expr_re(node: Re, ctx: ConverterContext):
    return f"{ctx.indent}{ctx.nxt} := _sscRe({_go_str(node.pattern)}, {ctx.prv})"


@GO_GOQUERY_CONVERTER(ReAll)
def expr_re_all(node: ReAll, ctx: ConverterContext):
    return f"{ctx.indent}{ctx.nxt} := _sscReAll({_go_str(node.pattern)}, _sscAsString({ctx.prv}))"


@GO_GOQUERY_CONVERTER(ReSub)
def expr_re_sub(node: ReSub, ctx: ConverterContext):
    return f"{ctx.indent}{ctx.nxt} := _sscReSub({_go_str(node.pattern)}, {_go_str(node.repl)}, {ctx.prv})"


@GO_GOQUERY_CONVERTER(Index)
def expr_index(node: Index, ctx: ConverterContext):
    return f"{ctx.indent}{ctx.nxt} := _sscIndex({ctx.prv}, {node.i})"


@GO_GOQUERY_CONVERTER(Slice)
def expr_slice(node: Slice, ctx: ConverterContext):
    return f"{ctx.indent}{ctx.nxt} := _sscSlice({ctx.prv}, {node.start}, {node.end})"


@GO_GOQUERY_CONVERTER(Len)
def expr_len(node: Len, ctx: ConverterContext):
    return f"{ctx.indent}{ctx.nxt} := _sscLen({ctx.prv})"


@GO_GOQUERY_CONVERTER(Unique)
def expr_unique(node: Unique, ctx: ConverterContext):
    return f"{ctx.indent}{ctx.nxt} := _sscUnique({ctx.prv})"


@GO_GOQUERY_CONVERTER(ToInt)
def expr_to_int(node: ToInt, ctx: ConverterContext):
    return f"{ctx.indent}{ctx.nxt} := _sscToInt({ctx.prv})"


@GO_GOQUERY_CONVERTER(ToFloat)
def expr_to_float(node: ToFloat, ctx: ConverterContext):
    return f"{ctx.indent}{ctx.nxt} := _sscToFloat({ctx.prv})"


@GO_GOQUERY_CONVERTER(ToBool)
def expr_to_bool(node: ToBool, ctx: ConverterContext):
    return f"{ctx.indent}{ctx.nxt} := _sscToBool({ctx.prv})"


@GO_GOQUERY_CONVERTER(Jsonify)
def expr_jsonify(node: Jsonify, ctx: ConverterContext):
    if not node.path:
        return f"{ctx.indent}{ctx.nxt} := _sscJSON({ctx.prv})"
    parts = []
    for part in node.path.split('.'):
        if part.lstrip('-').isdigit():
            parts.append(part)
        else:
            parts.append(_go_str(part))
    return f"{ctx.indent}{ctx.nxt} := _sscJSONPath({ctx.prv}, []any{{{', '.join(parts)}}})"


@GO_GOQUERY_CONVERTER(Nested)
def expr_nested(node: Nested, ctx: ConverterContext):
    name = to_pascal_case(node.struct_name)
    return f"{ctx.indent}{ctx.nxt} := new{name}FromSelection(_sscAsSelection({ctx.prv})).Parse()"


@GO_GOQUERY_CONVERTER(Self)
def expr_self(node: Self, ctx: ConverterContext):
    struct_name = to_pascal_case(node.parent.parent.name)
    recv = to_camel_case(struct_name)
    return f"{ctx.indent}{ctx.nxt} := {recv}._{to_camel_case(node.name)}"


@GO_GOQUERY_CONVERTER(TransformCall)
def expr_transform(node: TransformCall, ctx: ConverterContext):
    if not node.transform_def:
        raise ValueError(f"TransformCall '{node.name}': transform_def is None")

    go_target = None
    for target in node.transform_def.body:
        if target.lang == "go":
            go_target = target
            break

    if not go_target:
        raise ValueError(
            f"TransformCall '{node.name}': no 'go' implementation found"
        )

    lines = []
    for code_line in go_target.code:
        code_line = code_line.replace("{{PRV}}", ctx.prv)
        code_line = code_line.replace("{{NXT}}", ctx.nxt)
        lines.append(f"{ctx.indent}{code_line}")
    return lines


@GO_GOQUERY_CONVERTER(Return)
def expr_return(node: Return, ctx: ConverterContext):
    if isinstance(node.parent, PreValidate):
        return f"{ctx.indent}return"
    owner = _pipeline_owner(node)
    if isinstance(owner, Field):
        return f"{ctx.indent}return {_go_cast_expr(owner, ctx.prv)}"
    if isinstance(owner, Value):
        return f"{ctx.indent}return {_go_cast_expr(owner, ctx.prv)}"
    if isinstance(owner, InitField):
        ret_type = _go_type_from_var(owner.ret)
        if ret_type == "string":
            return f"{ctx.indent}return _sscAsString({ctx.prv})"
        if ret_type == "[]string":
            return f"{ctx.indent}return _sscAsStringSlice({ctx.prv})"
        if ret_type == "int":
            return f"{ctx.indent}return {ctx.prv}.(int)"
        if ret_type == "[]int":
            return f"{ctx.indent}return {ctx.prv}.([]int)"
        if ret_type == "float64":
            return f"{ctx.indent}return {ctx.prv}.(float64)"
        if ret_type == "[]float64":
            return f"{ctx.indent}return {ctx.prv}.([]float64)"
        if ret_type == "bool":
            return f"{ctx.indent}return {ctx.prv}.(bool)"
        if ret_type == "*string":
            return f"{ctx.indent}return _sscAsOptionalString({ctx.prv})"
        if ret_type == "*int":
            return f"{ctx.indent}return _sscAsOptionalInt({ctx.prv})"
        if ret_type == "*float64":
            return f"{ctx.indent}return _sscAsOptionalFloat({ctx.prv})"
        if ret_type == "*SSelection":
            return f"{ctx.indent}return _sscAsSelection({ctx.prv})"
        if ret_type == "[]*SSelection":
            return f"{ctx.indent}return _sscAsSelectionSlice({ctx.prv})"
    if isinstance(owner, Key):
        return f"{ctx.indent}return _sscAsString({ctx.prv})"
    if isinstance(owner, SplitDoc):
        return f"{ctx.indent}return _sscAsSelectionSlice({ctx.prv})"
    if isinstance(owner, TableConfig):
        return f"{ctx.indent}return _sscAsSelection({ctx.prv})"
    if isinstance(owner, TableMatchKey):
        return f"{ctx.indent}return _sscAsString({ctx.prv})"
    if isinstance(owner, TableRow):
        return f"{ctx.indent}return _sscAsSelectionSlice({ctx.prv})"
    return f"{ctx.indent}return {ctx.prv}"


@GO_GOQUERY_CONVERTER(FallbackStart)
def expr_fallback_start(node: FallbackStart, ctx: ConverterContext):
    return [f"{ctx.indent}var {ctx.nxt} any", f"{ctx.indent}func() {{", f"{ctx.indent}\tdefer func() {{", f"{ctx.indent}\t\tif recover() != nil {{", f"{ctx.indent}\t\t\t{ctx.nxt} = {_go_literal(getattr(node, 'value', None))}", f"{ctx.indent}\t\t}}", f"{ctx.indent}\t}}()"]


@GO_GOQUERY_CONVERTER(FallbackEnd)
def expr_fallback_end(node: FallbackEnd, ctx: ConverterContext):
    return [f"{ctx.indent}}}()"]


@GO_GOQUERY_CONVERTER(Filter, post_callback=lambda _, ctx: f"{ctx.indent}}})")
def expr_filter(node: Filter, ctx: ConverterContext):
    return f"{ctx.indent}{ctx.nxt} := _sscFilter({ctx.prv}, func(i any) bool {{ return"


@GO_GOQUERY_CONVERTER(Assert)
def expr_assert(node: Assert, ctx: ConverterContext):
    return [f"{ctx.indent}i := {ctx.prv}", f"{ctx.indent}if !("]


@GO_GOQUERY_CONVERTER.post(Assert)
def post_assert(node: Assert, ctx: ConverterContext):
    return [f"{ctx.indent}) {{", f"{ctx.indent}\tpanic(\"assertion failed\")", f"{ctx.indent}}}", f"{ctx.indent}{ctx.nxt} := {ctx.prv}"]


@GO_GOQUERY_CONVERTER(Match)
def expr_match(node: Match, ctx: ConverterContext):
    return [f"{ctx.indent}i := _sscAsString({to_camel_case(to_pascal_case(node.parent.parent.name))}._tableMatchKey({ctx.prv}))", f"{ctx.indent}if !("]


@GO_GOQUERY_CONVERTER.post(Match)
def post_match(node: Match, ctx: ConverterContext):
    struct_name = to_pascal_case(node.parent.parent.name)
    recv = to_camel_case(struct_name)
    return [f"{ctx.indent}) {{", f"{ctx.indent}\treturn UNMATCHED_TABLE_ROW", f"{ctx.indent}}}", f"{ctx.indent}{ctx.nxt} := {recv}._parseValue({ctx.prv})"]


@GO_GOQUERY_CONVERTER(LogicAnd, post_callback=lambda _, ctx: f"{ctx.indent})")
def expr_logic_and(node: LogicAnd, ctx: ConverterContext):
    if ctx.index == 0:
        return f"{ctx.indent}("
    return f"{ctx.indent}&& ("


@GO_GOQUERY_CONVERTER(LogicOr, post_callback=lambda _, ctx: f"{ctx.indent})")
def expr_logic_or(node: LogicOr, ctx: ConverterContext):
    if ctx.index == 0:
        return f"{ctx.indent}("
    return f"{ctx.indent}|| ("


@GO_GOQUERY_CONVERTER(LogicNot, post_callback=lambda _, ctx: f"{ctx.indent})")
def expr_logic_not(node: LogicNot, ctx: ConverterContext):
    if ctx.index == 0:
        return f"{ctx.indent}!("
    return f"{ctx.indent}&& !("


@GO_GOQUERY_CONVERTER(PredCss)
def pred_css(node: PredCss, ctx: ConverterContext):
    return _go_pred(f"_sscPredCss(i, {_go_str(node.query)})", ctx)


@GO_GOQUERY_CONVERTER(PredXpath)
def pred_xpath(node: PredXpath, ctx: ConverterContext):
    raise NotImplementedError("go-goquery does not support xpath")


@GO_GOQUERY_CONVERTER(PredContains)
def pred_contains(node: PredContains, ctx: ConverterContext):
    return _go_pred(f"_sscStrContains(i, {_go_str_slice(node.values)})", ctx)


@GO_GOQUERY_CONVERTER(PredStarts)
def pred_starts(node: PredStarts, ctx: ConverterContext):
    return _go_pred(f"_sscStrStarts(i, {_go_str_slice(node.values)})", ctx)


@GO_GOQUERY_CONVERTER(PredEnds)
def pred_ends(node: PredEnds, ctx: ConverterContext):
    return _go_pred(f"_sscStrEnds(i, {_go_str_slice(node.values)})", ctx)


@GO_GOQUERY_CONVERTER(PredEq)
def pred_eq(node: PredEq, ctx: ConverterContext):
    if isinstance(node.values[0], int):
        return _go_pred(f"len(i) == {node.values[0]}", ctx)
    if len(node.values) == 1:
        return _go_pred(f"i == {_go_str(node.values[0])}", ctx)
    return _go_pred("(" + " || ".join([f"i == {_go_str(v)}" for v in node.values]) + ")", ctx)


@GO_GOQUERY_CONVERTER(PredNe)
def pred_ne(node: PredNe, ctx: ConverterContext):
    if isinstance(node.values[0], int):
        return _go_pred(f"len(i) != {node.values[0]}", ctx)
    if len(node.values) == 1:
        return _go_pred(f"i != {_go_str(node.values[0])}", ctx)
    return _go_pred("(" + " && ".join([f"i != {_go_str(v)}" for v in node.values]) + ")", ctx)


@GO_GOQUERY_CONVERTER(PredIn)
def pred_in(node: PredIn, ctx: ConverterContext):
    return _go_pred(f"_sscStrContains({_go_str(node.value)}, []string{{i}})", ctx)


@GO_GOQUERY_CONVERTER(PredRe)
def pred_re(node: PredRe, ctx: ConverterContext):
    return _go_pred(f"regexp.MustCompile({_go_str(node.pattern)}).MatchString(i)", ctx)


@GO_GOQUERY_CONVERTER(PredReAny)
def pred_re_any(node: PredReAny, ctx: ConverterContext):
    return _go_pred(f"regexp.MustCompile({_go_str(node.pattern)}).MatchString(i)", ctx)


@GO_GOQUERY_CONVERTER(PredReAll)
def pred_re_all(node: PredReAll, ctx: ConverterContext):
    return _go_pred(f"len(regexp.MustCompile({_go_str(node.pattern)}).FindAllStringSubmatch(i, -1)) > 0", ctx)


@GO_GOQUERY_CONVERTER(PredHasAttr)
def pred_has_attr(node: PredHasAttr, ctx: ConverterContext):
    return _go_pred(f"_sscPredHasAttr(i, {_go_str_slice(node.attrs)})", ctx)


@GO_GOQUERY_CONVERTER(PredAttrEq)
def pred_attr_eq(node: PredAttrEq, ctx: ConverterContext):
    if len(node.values) == 1:
        return _go_pred(f"_sscPredAttr(i, {_go_str(node.attr_name)}) == {_go_str(node.values[0])}", ctx)
    return _go_pred("(" + " || ".join([f"_sscPredAttr(i, {_go_str(node.attr_name)}) == {_go_str(v)}" for v in node.values]) + ")", ctx)


@GO_GOQUERY_CONVERTER(PredAttrNe)
def pred_attr_ne(node: PredAttrNe, ctx: ConverterContext):
    if len(node.values) == 1:
        return _go_pred(f"_sscPredAttr(i, {_go_str(node.attr_name)}) != {_go_str(node.values[0])}", ctx)
    return _go_pred("(" + " && ".join([f"_sscPredAttr(i, {_go_str(node.attr_name)}) != {_go_str(v)}" for v in node.values]) + ")", ctx)


@GO_GOQUERY_CONVERTER(PredAttrStarts)
def pred_attr_starts(node: PredAttrStarts, ctx: ConverterContext):
    return _go_pred("(" + " || ".join([f"strings.HasPrefix(_sscPredAttr(i, {_go_str(node.attr_name)}), {_go_str(v)})" for v in node.values]) + ")", ctx)


@GO_GOQUERY_CONVERTER(PredAttrEnds)
def pred_attr_ends(node: PredAttrEnds, ctx: ConverterContext):
    return _go_pred("(" + " || ".join([f"strings.HasSuffix(_sscPredAttr(i, {_go_str(node.attr_name)}), {_go_str(v)})" for v in node.values]) + ")", ctx)


@GO_GOQUERY_CONVERTER(PredAttrContains)
def pred_attr_contains(node: PredAttrContains, ctx: ConverterContext):
    return _go_pred("(" + " || ".join([f"strings.Contains(_sscPredAttr(i, {_go_str(node.attr_name)}), {_go_str(v)})" for v in node.values]) + ")", ctx)


@GO_GOQUERY_CONVERTER(PredAttrRe)
def pred_attr_re(node: PredAttrRe, ctx: ConverterContext):
    return _go_pred(f"regexp.MustCompile({_go_str(node.pattern)}).MatchString(_sscPredAttr(i, {_go_str(node.attr_name)}))", ctx)


@GO_GOQUERY_CONVERTER(PredTextStarts)
def pred_text_starts(node: PredTextStarts, ctx: ConverterContext):
    return _go_pred("(" + " || ".join([f"strings.HasPrefix(_sscPredText(i), {_go_str(v)})" for v in node.values]) + ")", ctx)


@GO_GOQUERY_CONVERTER(PredTextEnds)
def pred_text_ends(node: PredTextEnds, ctx: ConverterContext):
    return _go_pred("(" + " || ".join([f"strings.HasSuffix(_sscPredText(i), {_go_str(v)})" for v in node.values]) + ")", ctx)


@GO_GOQUERY_CONVERTER(PredTextContains)
def pred_text_contains(node: PredTextContains, ctx: ConverterContext):
    return _go_pred("(" + " || ".join([f"strings.Contains(_sscPredText(i), {_go_str(v)})" for v in node.values]) + ")", ctx)


@GO_GOQUERY_CONVERTER(PredTextRe)
def pred_text_re(node: PredTextRe, ctx: ConverterContext):
    return _go_pred(f"regexp.MustCompile({_go_str(node.pattern)}).MatchString(_sscPredText(i))", ctx)


@GO_GOQUERY_CONVERTER(PredCountEq)
def pred_count_eq(node: PredCountEq, ctx: ConverterContext):
    return _go_pred(f"len(i) == {node.value}", ctx)


@GO_GOQUERY_CONVERTER(PredCountGt)
def pred_count_gt(node: PredCountGt, ctx: ConverterContext):
    return _go_pred(f"len(i) > {node.value}", ctx)


@GO_GOQUERY_CONVERTER(PredCountLt)
def pred_count_lt(node: PredCountLt, ctx: ConverterContext):
    return _go_pred(f"len(i) < {node.value}", ctx)


@GO_GOQUERY_CONVERTER(PredCountNe)
def pred_count_ne(node: PredCountNe, ctx: ConverterContext):
    return _go_pred(f"len(i) != {node.value}", ctx)


@GO_GOQUERY_CONVERTER(PredCountGe)
def pred_count_ge(node: PredCountGe, ctx: ConverterContext):
    return _go_pred(f"len(i) >= {node.value}", ctx)


@GO_GOQUERY_CONVERTER(PredCountLe)
def pred_count_le(node: PredCountLe, ctx: ConverterContext):
    return _go_pred(f"len(i) <= {node.value}", ctx)


@GO_GOQUERY_CONVERTER(PredCountRange)
def pred_count_range(node: PredCountRange, ctx: ConverterContext):
    return _go_pred(f"len(i) >= {node.min_count} && len(i) <= {node.max_count}", ctx)


@GO_GOQUERY_CONVERTER(PredGt)
def pred_gt(node: PredGt, ctx: ConverterContext):
    return _go_pred(f"i > {node.value}", ctx)


@GO_GOQUERY_CONVERTER(PredLt)
def pred_lt(node: PredLt, ctx: ConverterContext):
    return _go_pred(f"i < {node.value}", ctx)


@GO_GOQUERY_CONVERTER(PredGe)
def pred_ge(node: PredGe, ctx: ConverterContext):
    return _go_pred(f"i >= {node.value}", ctx)


@GO_GOQUERY_CONVERTER(PredLe)
def pred_le(node: PredLe, ctx: ConverterContext):
    return _go_pred(f"i <= {node.value}", ctx)


@GO_GOQUERY_CONVERTER(PredRange)
def pred_range(node: PredRange, ctx: ConverterContext):
    return _go_pred(f"i >= {node.min_value} && i <= {node.max_value}", ctx)
