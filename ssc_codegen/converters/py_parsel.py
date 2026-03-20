"""
parsel converter - inherits from py_bs4 and overrides selector/extract behaviors
using parsel.Selector/SelectorList API.
"""

from ssc_codegen.converters.base import ConverterContext
from ssc_codegen.converters.helpers import to_snake_case

from ssc_codegen.ast import VariableType
from ssc_codegen.ast import (
    Imports,
    Utilities,
    Field,
    Init,
    InitField,
    Key,
    Value,
    PreValidate,
    SplitDoc,
    TableConfig,
    TableMatchKey,
    TableRow,
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
    PredCss,
    PredXpath,
    PredHasAttr,
    PredAttrEq,
    PredAttrNe,
    PredAttrStarts,
    PredAttrEnds,
    PredAttrContains,
    PredAttrRe,
    PredTextStarts,
    PredTextEnds,
    PredTextContains,
    PredTextRe,
)

from ssc_codegen.ast import Nested


from ssc_codegen.converters import py_bs4


PY_PARSEL_CONVERTER = py_bs4.PY_BASE_CONVERTER.extend()


@PY_PARSEL_CONVERTER(Imports)
def pre_imports(node: Imports, _: ConverterContext):
    base_imports = [
        "import re",
        "import sys",
        "from typing import TypedDict, Optional, Any, List, Dict, Union",
        "from html import unescape as _html_unescape",
    ]

    transform_imports = sorted(node.transform_imports.get("py", set()))

    return base_imports + transform_imports


@PY_PARSEL_CONVERTER.post(Imports)
def post_imports(node: Imports, _):
    return ["from parsel import Selector, SelectorList"]


@PY_PARSEL_CONVERTER(Utilities)
def pre_utilities(node: Utilities, ctx: ConverterContext):
    return py_bs4.pre_utilities(node, ctx)


@PY_PARSEL_CONVERTER(Init)
def pre_init(node: Init, ctx: ConverterContext):
    init_node_names: list[str] = []
    for i in node.body:
        if isinstance(i, InitField):
            name = to_snake_case(i.name)
            init_node_names.append(name)
    code = [
        f"{ctx.indent}def __init__(self, document: Union[str, Selector, SelectorList]):",
        f"{ctx.indent * 2}if isinstance(document, str):",
        f"{ctx.indent * 3}self._doc = Selector(document)",
        f"{ctx.indent * 2}else:",
        f"{ctx.indent * 3}self._doc = document",
    ]
    for name in init_node_names:
        code.append(
            f"{ctx.indent * 2}self._{name} = self._init_{name}(self._doc)"
        )
    return code


@PY_PARSEL_CONVERTER(InitField)
def pre_init_field(node: InitField, ctx: ConverterContext):
    name = to_snake_case(node.name)
    ret_type = py_bs4.PY_TYPES.get(node.ret, "Any")
    return [
        f"    def _init_{name}(self, v: Union[Selector, SelectorList]) -> {ret_type}:"
    ]


@PY_PARSEL_CONVERTER(Field)
def pre_struct_field(node: Field, ctx: ConverterContext):
    name = to_snake_case(node.name)
    ret_type = py_bs4.PY_TYPES.get(node.ret, "Any")

    if node.ret == VariableType.JSON:
        from ssc_codegen.ast import Jsonify

        jsonify_node = [i for i in node.body if isinstance(i, Jsonify)][0]
        ret_type = ret_type.format(jsonify_node.schema_name)
        if jsonify_node.is_array:
            ret_type = f"List[{ret_type}]"
    elif node.ret == VariableType.NESTED:
        nested_node = [i for i in node.body if isinstance(i, Nested)][0]
        ret_type = ret_type.format(nested_node.struct_name)
        if nested_node.is_array:
            ret_type = f"List[{ret_type}]"

    if node.accept == VariableType.STRING:
        return [
            f"    def _parse_{name}(self, v: Union[Selector, SelectorList]) -> Union[{ret_type}, _UnmatchedTableRow]:"
        ]
    return [
        f"    def _parse_{name}(self, v: Union[Selector, SelectorList]) -> {ret_type}:"
    ]


@PY_PARSEL_CONVERTER(Key)
def pre_struct_key(node: Key, ctx: ConverterContext):
    return [
        "    def _parse_key(self, v: Union[Selector, SelectorList]) -> str:"
    ]


@PY_PARSEL_CONVERTER(Value)
def pre_struct_value(node: Value, ctx: ConverterContext):
    ret_type = py_bs4.PY_TYPES.get(node.ret, "Any")

    if node.ret == VariableType.JSON:
        from ssc_codegen.ast import Jsonify

        jsonify_node = [i for i in node.body if isinstance(i, Jsonify)][0]
        ret_type = ret_type.format(jsonify_node.schema_name)
        if jsonify_node.is_array:
            ret_type = f"List[{ret_type}]"
    elif node.ret == VariableType.NESTED:
        nested_node = [i for i in node.body if isinstance(i, Nested)][0]
        ret_type = ret_type.format(nested_node.struct_name)
        if nested_node.is_array:
            ret_type = f"List[{ret_type}]"

    return [
        f"    def _parse_value(self, v: Union[Selector, SelectorList]) -> {ret_type}:"
    ]


@PY_PARSEL_CONVERTER(PreValidate)
def pre_struct_pre_validate(node: PreValidate, ctx: ConverterContext):
    return [
        "    def _pre_validate(self, v: Union[Selector, SelectorList]) -> None:"
    ]


@PY_PARSEL_CONVERTER(SplitDoc)
def pre_struct_split_doc(node: SplitDoc, ctx: ConverterContext):
    return [
        "    def _split_doc(self, v: Union[Selector, SelectorList]) -> SelectorList:"
    ]


@PY_PARSEL_CONVERTER(TableConfig)
def pre_struct_table_config(node: TableConfig, ctx: ConverterContext):
    return [
        "    def _table_config(self, v: Union[Selector, SelectorList]) -> Selector:"
    ]


@PY_PARSEL_CONVERTER(TableMatchKey)
def pre_struct_table_match_key(node: TableMatchKey, ctx: ConverterContext):
    return [
        "    def _table_match_key(self, v: Union[Selector, SelectorList]) -> str:"
    ]


@PY_PARSEL_CONVERTER(TableRow)
def pre_struct_table_row(node: TableRow, ctx: ConverterContext):
    return [
        "    def _parse_table_rows(self, v: Union[Selector, SelectorList]) -> SelectorList:"
    ]


@PY_PARSEL_CONVERTER(CssSelect)
def pre_expr_css_select(node: CssSelect, ctx: ConverterContext):
    query = repr(node.query)
    return f"{ctx.indent}{ctx.nxt} = {ctx.prv}.css({query})"


@PY_PARSEL_CONVERTER(CssSelectAll)
def pre_expr_css_select_all(node: CssSelectAll, ctx: ConverterContext):
    query = repr(node.query)
    return f"{ctx.indent}{ctx.nxt} = {ctx.prv}.css({query})"


@PY_PARSEL_CONVERTER(XpathSelect)
def pre_expr_xpath_select(node: XpathSelect, ctx: ConverterContext):
    query = repr(node.query)
    return f"{ctx.indent}{ctx.nxt} = {ctx.prv}.xpath({query})"


@PY_PARSEL_CONVERTER(XpathSelectAll)
def pre_expr_xpath_select_all(node: XpathSelectAll, ctx: ConverterContext):
    query = repr(node.query)
    return f"{ctx.indent}{ctx.nxt} = {ctx.prv}.xpath({query})"


@PY_PARSEL_CONVERTER(CssRemove)
def pre_expr_css_remove(node: CssRemove, ctx: ConverterContext):
    query = repr(node.query)
    return [
        f"{ctx.indent}[i.root.getparent().remove(i.root) for i in {ctx.prv}.css({query}) if i.root.getparent() is not None]",
        f"{ctx.indent}{ctx.nxt} = {ctx.prv}",
    ]


@PY_PARSEL_CONVERTER(XpathRemove)
def pre_expr_xpath_remove(node: XpathRemove, ctx: ConverterContext):
    query = repr(node.query)
    return [
        f"{ctx.indent}[i.root.getparent().remove(i.root) for i in {ctx.prv}.xpath({query}) if i.root.getparent() is not None]",
        f"{ctx.indent}{ctx.nxt} = {ctx.prv}",
    ]


@PY_PARSEL_CONVERTER(Text)
def pre_expr_text(node: Text, ctx: ConverterContext):
    if node.accept == VariableType.DOCUMENT:
        return f"{ctx.indent}{ctx.nxt} = ' '.join({ctx.prv}.xpath('.//text()').getall())"
    return f"{ctx.indent}{ctx.nxt} = [' '.join(i.xpath('.//text()').getall()) for i in {ctx.prv}]"


@PY_PARSEL_CONVERTER(Raw)
def pre_expr_raw(node: Raw, ctx: ConverterContext):
    if node.accept == VariableType.DOCUMENT:
        return f"{ctx.indent}{ctx.nxt} = {ctx.prv}.get()"
    return f"{ctx.indent}{ctx.nxt} = {ctx.prv}.getall()"


@PY_PARSEL_CONVERTER(Attr)
def pre_expr_attr(node: Attr, ctx: ConverterContext):
    keys = node.keys
    if node.accept == VariableType.DOCUMENT:
        if len(keys) == 1:
            return f"{ctx.indent}{ctx.nxt} = {ctx.prv}.attrib[{keys[0]!r}]"
        return f"{ctx.indent}{ctx.nxt} = [{ctx.prv}.attrib[k] for k in {keys} if {ctx.prv}.attrib.get(k)]"
    if len(keys) == 1:
        return f"{ctx.indent}{ctx.nxt} = [e.attrib[{keys[0]!r}] for e in {ctx.prv}]"
    return f"{ctx.indent}{ctx.nxt} = [e.attrib[k] for e in {ctx.prv} for k in {keys} if e.attrib.get(k)]"


@PY_PARSEL_CONVERTER(PredCss)
def pre_expr_pred_css(node: PredCss, ctx: ConverterContext):
    query = repr(node.query)
    cond = f"bool(i.css({query}))"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_PARSEL_CONVERTER(PredXpath)
def pre_expr_pred_xpath(node: PredXpath, ctx: ConverterContext):
    query = repr(node.query)
    cond = f"bool(i.xpath({query}))"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_PARSEL_CONVERTER(PredHasAttr)
def pre_expr_pred_has_attr(node: PredHasAttr, ctx: ConverterContext):
    attrs = node.attrs
    if len(attrs) == 1:
        cond = f"{attrs[0]!r} in i.attrib"
    else:
        cond = f"any(attr in i.attrib for attr in {attrs!r})"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_PARSEL_CONVERTER(PredAttrEq)
def pre_expr_pred_attr_eq(node: PredAttrEq, ctx: ConverterContext):
    name = node.name
    values = node.values
    if len(values) == 1:
        cond = f"i.attrib.get({name!r}, '') == {values[0]!r}"
    else:
        cond = f"i.attrib.get({name!r}, '') in {values!r}"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_PARSEL_CONVERTER(PredAttrNe)
def pre_expr_pred_attr_ne(node: PredAttrNe, ctx: ConverterContext):
    name = node.name
    values = node.values
    if len(values) == 1:
        cond = f"i.attrib.get({name!r}, '') != {values[0]!r}"
    else:
        cond = f"i.attrib.get({name!r}, '') not in {values!r}"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_PARSEL_CONVERTER(PredAttrStarts)
def pre_expr_pred_attr_starts(node: PredAttrStarts, ctx: ConverterContext):
    name = node.name
    values = node.values
    if len(values) == 1:
        cond = f"i.attrib.get({name!r}, '').startswith({values[0]!r})"
    else:
        cond = (
            f"any(i.attrib.get({name!r}, '').startswith(v) for v in {values!r})"
        )
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_PARSEL_CONVERTER(PredAttrEnds)
def pre_expr_pred_attr_ends(node: PredAttrEnds, ctx: ConverterContext):
    name = node.name
    values = node.values
    if len(values) == 1:
        cond = f"i.attrib.get({name!r}, '').endswith({values[0]!r})"
    else:
        cond = (
            f"any(i.attrib.get({name!r}, '').endswith(v) for v in {values!r})"
        )
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_PARSEL_CONVERTER(PredAttrContains)
def pre_expr_pred_attr_contains(node: PredAttrContains, ctx: ConverterContext):
    name = node.name
    values = node.values
    if len(values) == 1:
        cond = f"{values[0]!r} in i.attrib.get({name!r}, '')"
    else:
        cond = f"any(v in i.attrib.get({name!r}, '') for v in {values!r})"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_PARSEL_CONVERTER(PredAttrRe)
def pre_expr_pred_attr_re(node: PredAttrRe, ctx: ConverterContext):
    name = node.name
    pattern = repr(node.pattern)
    cond = f"bool(re.search({pattern}, i.attrib.get({name!r}, '')))"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_PARSEL_CONVERTER(PredTextStarts)
def pre_expr_pred_text_starts(node: PredTextStarts, ctx: ConverterContext):
    values = node.values
    if len(values) == 1:
        cond = (
            f"' '.join(i.xpath('.//text()').getall()).startswith({values[0]!r})"
        )
    else:
        cond = f"any(' '.join(i.xpath('.//text()').getall()).startswith(v) for v in {values!r})"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_PARSEL_CONVERTER(PredTextEnds)
def pre_expr_pred_text_ends(node: PredTextEnds, ctx: ConverterContext):
    values = node.values
    if len(values) == 1:
        cond = (
            f"' '.join(i.xpath('.//text()').getall()).endswith({values[0]!r})"
        )
    else:
        cond = f"any(' '.join(i.xpath('.//text()').getall()).endswith(v) for v in {values!r})"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_PARSEL_CONVERTER(PredTextContains)
def pre_expr_pred_text_contains(node: PredTextContains, ctx: ConverterContext):
    values = node.values
    if len(values) == 1:
        cond = f"{values[0]!r} in ' '.join(i.xpath('.//text()').getall())"
    else:
        cond = f"any(v in ' '.join(i.xpath('.//text()').getall()) for v in {values!r})"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_PARSEL_CONVERTER(PredTextRe)
def pre_expr_pred_text_re(node: PredTextRe, ctx: ConverterContext):
    pattern = repr(node.pattern)
    cond = (
        f"bool(re.search({pattern}, ' '.join(i.xpath('.//text()').getall())))"
    )
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"
