"""
parsel converter - inherits from py_bs4 and overrides selector/extract behaviors
using parsel.Selector/SelectorList API.
"""

from ssc_codegen.converters.base import ConverterContext
from ssc_codegen.converters.helpers import to_snake_case

from ssc_codegen.ast import VariableType as VT
import ssc_codegen.ast as a


from ssc_codegen.converters import py_bs4
from ssc_codegen.converters import py_helpers


PY_PARSEL_CONVERTER = py_bs4.PY_BASE_CONVERTER.extend()
PY_TYPES = py_bs4.PY_TYPES.copy()
PY_TYPES[VT.DOCUMENT] = "Selector"
PY_TYPES[VT.LIST_DOCUMENT] = "SelectorList"


@PY_PARSEL_CONVERTER(a.Imports)
def pre_imports(node: a.Imports, _: ConverterContext):
    base_imports = [
        "import re",
        "import sys",
        "from typing import TypedDict, Optional, Any, List, Dict, Union, Literal",
    ]
    if not py_helpers._module_is_rest_only(node):
        base_imports.append("from html import unescape as _html_unescape")
    base_imports.extend(py_helpers.rest_imports(node))

    transform_imports = sorted(node.transform_imports.get("py", set()))

    return base_imports + transform_imports


@PY_PARSEL_CONVERTER.post(a.Imports)
def post_imports(node: a.Imports, ctx: ConverterContext):
    lines = []
    if not py_helpers._module_is_rest_only(node):
        lines.append("from parsel import Selector, SelectorList")
    lines.extend(py_helpers.http_client_import(ctx))
    return lines


@PY_PARSEL_CONVERTER(a.Utilities)
def pre_utilities(node: a.Utilities, ctx: ConverterContext):
    return py_bs4.pre_utilities(node, ctx)


@PY_PARSEL_CONVERTER(a.Init)
def pre_init(node: a.Init, ctx: ConverterContext):
    init_node_names: list[str] = []
    for i in node.body:
        if isinstance(i, a.InitField):
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


@PY_PARSEL_CONVERTER(a.InitField)
def pre_init_field(node: a.InitField, ctx: ConverterContext):
    name = to_snake_case(node.name)
    ret_type = py_bs4.PY_TYPES.get(node.ret, "Any")
    return [
        f"    def _init_{name}(self, v: Union[Selector, SelectorList]) -> {ret_type}:"
    ]


@PY_PARSEL_CONVERTER(a.Field)
def pre_struct_field(node: a.Field, ctx: ConverterContext):
    name = to_snake_case(node.name)
    ret_type = py_bs4.PY_TYPES.get(node.ret, "Any")

    if node.ret == VT.JSON:
        jsonify_node = [i for i in node.body if isinstance(i, a.Jsonify)][0]
        ret_type = ret_type.format(jsonify_node.schema_name)
        if jsonify_node.is_array:
            ret_type = f"List[{ret_type}]"
    elif node.ret == VT.NESTED:
        nested_node = [i for i in node.body if isinstance(i, a.Nested)][0]
        ret_type = ret_type.format(nested_node.struct_name)
        if nested_node.is_array:
            ret_type = f"List[{ret_type}]"

    if node.accept == VT.STRING:
        return [
            f"    def _parse_{name}(self, v: Union[Selector, SelectorList]) -> Union[{ret_type}, _UnmatchedTableRow]:"
        ]
    return [
        f"    def _parse_{name}(self, v: Union[Selector, SelectorList]) -> {ret_type}:"
    ]


@PY_PARSEL_CONVERTER(a.Key)
def pre_struct_key(node: a.Key, ctx: ConverterContext):
    return [
        "    def _parse_key(self, v: Union[Selector, SelectorList]) -> str:"
    ]


@PY_PARSEL_CONVERTER(a.Value)
def pre_struct_value(node: a.Value, ctx: ConverterContext):
    ret_type = py_bs4.PY_TYPES.get(node.ret, "Any")

    if node.ret == VT.JSON:
        jsonify_node = [i for i in node.body if isinstance(i, a.Jsonify)][0]
        ret_type = ret_type.format(jsonify_node.schema_name)
        if jsonify_node.is_array:
            ret_type = f"List[{ret_type}]"
    elif node.ret == VT.NESTED:
        nested_node = [i for i in node.body if isinstance(i, a.Nested)][0]
        ret_type = ret_type.format(nested_node.struct_name)
        if nested_node.is_array:
            ret_type = f"List[{ret_type}]"

    return [
        f"    def _parse_value(self, v: Union[Selector, SelectorList]) -> {ret_type}:"
    ]


@PY_PARSEL_CONVERTER(a.PreValidate)
def pre_struct_pre_validate(node: a.PreValidate, ctx: ConverterContext):
    return [
        "    def _pre_validate(self, v: Union[Selector, SelectorList]) -> None:"
    ]


@PY_PARSEL_CONVERTER(a.SplitDoc)
def pre_struct_split_doc(node: a.SplitDoc, ctx: ConverterContext):
    return [
        "    def _split_doc(self, v: Union[Selector, SelectorList]) -> SelectorList:"
    ]


@PY_PARSEL_CONVERTER(a.TableConfig)
def pre_struct_table_config(node: a.TableConfig, ctx: ConverterContext):
    return [
        "    def _table_config(self, v: Union[Selector, SelectorList]) -> Selector:"
    ]


@PY_PARSEL_CONVERTER(a.TableMatchKey)
def pre_struct_table_match_key(node: a.TableMatchKey, ctx: ConverterContext):
    return [
        "    def _table_match_key(self, v: Union[Selector, SelectorList]) -> str:"
    ]


@PY_PARSEL_CONVERTER(a.TableRow)
def pre_struct_table_row(node: a.TableRow, ctx: ConverterContext):
    return [
        "    def _parse_table_rows(self, v: Union[Selector, SelectorList]) -> SelectorList:"
    ]


@PY_PARSEL_CONVERTER(a.CssSelect)
def pre_expr_css_select(node: a.CssSelect, ctx: ConverterContext):
    if node.queries:
        lines: list[str] = []
        for i, query in enumerate(node.queries):
            q = repr(query)
            if i == 0:
                lines.append(f"{ctx.indent}{ctx.nxt} = {ctx.prv}.css({q})")
            else:
                lines.append(f"{ctx.indent}if not {ctx.nxt}:")
                lines.append(f"{ctx.indent}    {ctx.nxt} = {ctx.prv}.css({q})")
        return lines
    query = repr(node.query)
    return f"{ctx.indent}{ctx.nxt} = {ctx.prv}.css({query})"


@PY_PARSEL_CONVERTER(a.CssSelectAll)
def pre_expr_css_select_all(node: a.CssSelectAll, ctx: ConverterContext):
    if node.queries:
        lines: list[str] = []
        for i, query in enumerate(node.queries):
            q = repr(query)
            if i == 0:
                lines.append(f"{ctx.indent}{ctx.nxt} = {ctx.prv}.css({q})")
            else:
                lines.append(f"{ctx.indent}if not {ctx.nxt}:")
                lines.append(f"{ctx.indent}    {ctx.nxt} = {ctx.prv}.css({q})")
        return lines
    query = repr(node.query)
    return f"{ctx.indent}{ctx.nxt} = {ctx.prv}.css({query})"


@PY_PARSEL_CONVERTER(a.XpathSelect)
def pre_expr_xpath_select(node: a.XpathSelect, ctx: ConverterContext):
    if node.queries:
        lines: list[str] = []
        for i, query in enumerate(node.queries):
            q = repr(query)
            if i == 0:
                lines.append(f"{ctx.indent}{ctx.nxt} = {ctx.prv}.xpath({q})")
            else:
                lines.append(f"{ctx.indent}if not {ctx.nxt}:")
                lines.append(
                    f"{ctx.indent}    {ctx.nxt} = {ctx.prv}.xpath({q})"
                )
        return lines
    query = repr(node.query)
    return f"{ctx.indent}{ctx.nxt} = {ctx.prv}.xpath({query})"


@PY_PARSEL_CONVERTER(a.XpathSelectAll)
def pre_expr_xpath_select_all(node: a.XpathSelectAll, ctx: ConverterContext):
    if node.queries:
        lines: list[str] = []
        for i, query in enumerate(node.queries):
            q = repr(query)
            if i == 0:
                lines.append(f"{ctx.indent}{ctx.nxt} = {ctx.prv}.xpath({q})")
            else:
                lines.append(f"{ctx.indent}if not {ctx.nxt}:")
                lines.append(
                    f"{ctx.indent}    {ctx.nxt} = {ctx.prv}.xpath({q})"
                )
        return lines
    query = repr(node.query)
    return f"{ctx.indent}{ctx.nxt} = {ctx.prv}.xpath({query})"


@PY_PARSEL_CONVERTER(a.CssRemove)
def pre_expr_css_remove(node: a.CssRemove, ctx: ConverterContext):
    query = repr(node.query)
    return [
        f"{ctx.indent}[i.root.getparent().remove(i.root) for i in {ctx.prv}.css({query}) if i.root.getparent() is not None]",
        f"{ctx.indent}{ctx.nxt} = {ctx.prv}",
    ]


@PY_PARSEL_CONVERTER(a.XpathRemove)
def pre_expr_xpath_remove(node: a.XpathRemove, ctx: ConverterContext):
    query = repr(node.query)
    return [
        f"{ctx.indent}[i.root.getparent().remove(i.root) for i in {ctx.prv}.xpath({query}) if i.root.getparent() is not None]",
        f"{ctx.indent}{ctx.nxt} = {ctx.prv}",
    ]


@PY_PARSEL_CONVERTER(a.Text)
def pre_expr_text(node: a.Text, ctx: ConverterContext):
    if node.accept == VT.DOCUMENT:
        return f"{ctx.indent}{ctx.nxt} = ' '.join({ctx.prv}.xpath('.//text()').getall())"
    return f"{ctx.indent}{ctx.nxt} = [' '.join(i.xpath('.//text()').getall()) for i in {ctx.prv}]"


@PY_PARSEL_CONVERTER(a.Raw)
def pre_expr_raw(node: a.Raw, ctx: ConverterContext):
    if node.accept == VT.DOCUMENT:
        return f"{ctx.indent}{ctx.nxt} = {ctx.prv}.get()"
    return f"{ctx.indent}{ctx.nxt} = {ctx.prv}.getall()"


@PY_PARSEL_CONVERTER(a.Attr)
def pre_expr_attr(node: a.Attr, ctx: ConverterContext):
    keys = node.keys
    if node.accept == VT.DOCUMENT:
        if len(keys) == 1:
            return f"{ctx.indent}{ctx.nxt} = {ctx.prv}.attrib[{keys[0]!r}]"
        return f"{ctx.indent}{ctx.nxt} = [{ctx.prv}.attrib[k] for k in {keys} if {ctx.prv}.attrib.get(k)]"
    if len(keys) == 1:
        return f"{ctx.indent}{ctx.nxt} = [e.attrib[{keys[0]!r}] for e in {ctx.prv}]"
    return f"{ctx.indent}{ctx.nxt} = [e.attrib[k] for e in {ctx.prv} for k in {keys} if e.attrib.get(k)]"


@PY_PARSEL_CONVERTER(a.PredCss)
def pre_expr_pred_css(node: a.PredCss, ctx: ConverterContext):
    query = repr(node.query)
    cond = f"bool(i.css({query}))"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_PARSEL_CONVERTER(a.PredXpath)
def pre_expr_pred_xpath(node: a.PredXpath, ctx: ConverterContext):
    query = repr(node.query)
    cond = f"bool(i.xpath({query}))"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_PARSEL_CONVERTER(a.PredHasAttr)
def pre_expr_pred_has_attr(node: a.PredHasAttr, ctx: ConverterContext):
    attrs = node.attrs
    if len(attrs) == 1:
        cond = f"{attrs[0]!r} in i.attrib"
    else:
        cond = f"any(attr in i.attrib for attr in {attrs!r})"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_PARSEL_CONVERTER(a.PredAttrEq)
def pre_expr_pred_attr_eq(node: a.PredAttrEq, ctx: ConverterContext):
    name = node.name
    values = node.values
    if len(values) == 1:
        cond = f"i.attrib.get({name!r}, '') == {values[0]!r}"
    else:
        cond = f"i.attrib.get({name!r}, '') in {values!r}"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_PARSEL_CONVERTER(a.PredAttrNe)
def pre_expr_pred_attr_ne(node: a.PredAttrNe, ctx: ConverterContext):
    name = node.name
    values = node.values
    if len(values) == 1:
        cond = f"i.attrib.get({name!r}, '') != {values[0]!r}"
    else:
        cond = f"i.attrib.get({name!r}, '') not in {values!r}"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_PARSEL_CONVERTER(a.PredAttrStarts)
def pre_expr_pred_attr_starts(node: a.PredAttrStarts, ctx: ConverterContext):
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


@PY_PARSEL_CONVERTER(a.PredAttrEnds)
def pre_expr_pred_attr_ends(node: a.PredAttrEnds, ctx: ConverterContext):
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


@PY_PARSEL_CONVERTER(a.PredAttrContains)
def pre_expr_pred_attr_contains(
    node: a.PredAttrContains, ctx: ConverterContext
):
    name = node.name
    values = node.values
    if len(values) == 1:
        cond = f"{values[0]!r} in i.attrib.get({name!r}, '')"
    else:
        cond = f"any(v in i.attrib.get({name!r}, '') for v in {values!r})"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_PARSEL_CONVERTER(a.PredAttrRe)
def pre_expr_pred_attr_re(node: a.PredAttrRe, ctx: ConverterContext):
    name = node.name
    pattern = repr(node.pattern)
    cond = f"bool(re.search({pattern}, i.attrib.get({name!r}, '')))"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_PARSEL_CONVERTER(a.PredTextStarts)
def pre_expr_pred_text_starts(node: a.PredTextStarts, ctx: ConverterContext):
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


@PY_PARSEL_CONVERTER(a.PredTextEnds)
def pre_expr_pred_text_ends(node: a.PredTextEnds, ctx: ConverterContext):
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


@PY_PARSEL_CONVERTER(a.PredTextContains)
def pre_expr_pred_text_contains(
    node: a.PredTextContains, ctx: ConverterContext
):
    values = node.values
    if len(values) == 1:
        cond = f"{values[0]!r} in ' '.join(i.xpath('.//text()').getall())"
    else:
        cond = f"any(v in ' '.join(i.xpath('.//text()').getall()) for v in {values!r})"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_PARSEL_CONVERTER(a.PredTextRe)
def pre_expr_pred_text_re(node: a.PredTextRe, ctx: ConverterContext):
    pattern = repr(node.pattern)
    cond = (
        f"bool(re.search({pattern}, ' '.join(i.xpath('.//text()').getall())))"
    )
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"
