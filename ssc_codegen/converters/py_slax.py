"""
selectolax converter - inherits from base converter and overrides selectolax-specific APIs.
"""

from ssc_codegen.converters.base import ConverterContext
from ssc_codegen.converters.helpers import to_snake_case

from ssc_codegen.ast import VariableType as VT
import ssc_codegen.ast as a

from ssc_codegen.converters import py_bs4
from ssc_codegen.converters import py_helpers


PY_SLAX_CONVERTER = py_bs4.PY_BASE_CONVERTER.extend()
PY_TYPES = py_bs4.PY_TYPES.copy()

PY_TYPES[VT.DOCUMENT] = "Node"
PY_TYPES[VT.LIST_DOCUMENT] = "List[Node]"


@PY_SLAX_CONVERTER(a.Imports)
def pre_imports(node: a.Imports, ctx: ConverterContext):
    runtime = ctx.meta.get("runtime_module")
    if runtime:
        base_imports = [
            "import json",
            "import re",
            "import sys",
            "from dataclasses import dataclass",
            "from typing import TypedDict, Optional, Any, List, Dict, Union, Literal",
        ]
        base_imports.extend(py_helpers.NOT_REQUIRED_IMPORT)
    else:
        base_imports = [
            "import json",
            "import re",
            "import sys",
            "from dataclasses import dataclass",
            "from typing import TypedDict, Optional, Any, List, Dict, Union, Literal",
        ]
        if not py_helpers.module_is_rest_only(node):
            base_imports.append("from html import unescape as _html_unescape")
        base_imports.extend(py_helpers.NOT_REQUIRED_IMPORT)
        base_imports.extend(py_helpers.rest_imports(node))

    transform_imports = sorted(node.transform_imports.get("py", set()))

    return base_imports + transform_imports


@PY_SLAX_CONVERTER.post(a.Imports)
def post_imports(node: a.Imports, ctx: ConverterContext):
    lines = []
    if not py_helpers.module_is_rest_only(node):
        lines.append(
            "from selectolax.lexbor import LexborHTMLParser as HTMLParser, LexborNode as Node"
        )
    lines.extend(py_helpers.http_client_import(ctx))
    return lines


@PY_SLAX_CONVERTER(a.Utilities)
def pre_utilities(node: a.Utilities, ctx: ConverterContext):
    return py_bs4.pre_utilities(node, ctx)


@PY_SLAX_CONVERTER(a.Init)
def pre_init(node: a.Init, ctx: ConverterContext):
    if isinstance(node.parent, a.Struct) and node.parent.is_rest:
        return None
    init_node_names: list[str] = []
    for i in node.body:
        if isinstance(i, a.InitField):
            name = to_snake_case(i.name)
            init_node_names.append(name)
    code = [
        f"{ctx.indent}def __init__(self, document: Union[str, HTMLParser, Node]):",
        f"{ctx.indent * 2}if isinstance(document, str):",
        f"{ctx.indent * 3}self._doc = HTMLParser(document)",
        f"{ctx.indent * 2}else:",
        f"{ctx.indent * 3}self._doc = document",
    ]
    for name in init_node_names:
        code.append(
            f"{ctx.indent * 2}self._{name} = self._init_{name}(self._doc)"
        )
    return code


@PY_SLAX_CONVERTER(a.InitField)
def pre_init_field(node: a.InitField, ctx: ConverterContext):
    name = to_snake_case(node.name)
    ret_type = PY_TYPES.get(node.ret, "Any")
    return [
        f"    def _init_{name}(self, v: Union[HTMLParser, Node]) -> {ret_type}:"
    ]


@PY_SLAX_CONVERTER(a.Field)
def pre_struct_field(node: a.Field, ctx: ConverterContext):
    name = to_snake_case(node.name)
    ret_type = PY_TYPES.get(node.ret, "Any")

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
            f"    def _parse_{name}(self, v: Union[HTMLParser, Node]) -> Union[{ret_type}, _UnmatchedTableRow]:"
        ]
    return [
        f"    def _parse_{name}(self, v: Union[HTMLParser, Node]) -> {ret_type}:"
    ]


@PY_SLAX_CONVERTER(a.Key)
def pre_struct_key(node: a.Key, ctx: ConverterContext):
    return ["    def _parse_key(self, v: Union[HTMLParser, Node]) -> str:"]


@PY_SLAX_CONVERTER(a.Value)
def pre_struct_value(node: a.Value, ctx: ConverterContext):
    ret_type = PY_TYPES.get(node.ret, "Any")

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
        f"    def _parse_value(self, v: Union[HTMLParser, Node]) -> {ret_type}:"
    ]


@PY_SLAX_CONVERTER(a.PreValidate)
def pre_struct_pre_validate(node: a.PreValidate, ctx: ConverterContext):
    return ["    def _pre_validate(self, v: Union[HTMLParser, Node]) -> None:"]


@PY_SLAX_CONVERTER(a.SplitDoc)
def pre_struct_split_doc(node: a.SplitDoc, ctx: ConverterContext):
    return [
        "    def _split_doc(self, v: Union[HTMLParser, Node]) -> List[Node]:"
    ]


@PY_SLAX_CONVERTER(a.TableConfig)
def pre_struct_table_config(node: a.TableConfig, ctx: ConverterContext):
    return ["    def _table_config(self, v: Union[HTMLParser, Node]) -> Node:"]


@PY_SLAX_CONVERTER(a.TableMatchKey)
def pre_struct_table_match_key(node: a.TableMatchKey, ctx: ConverterContext):
    return [
        "    def _table_match_key(self, v: Union[HTMLParser, Node]) -> str:"
    ]


@PY_SLAX_CONVERTER(a.TableRow)
def pre_struct_table_row(node: a.TableRow, ctx: ConverterContext):
    return [
        "    def _parse_table_rows(self, v: Union[HTMLParser, Node]) -> List[Node]:"
    ]


@PY_SLAX_CONVERTER(a.CssSelect)
def pre_expr_css_select(node: a.CssSelect, ctx: ConverterContext):
    if node.queries:
        lines: list[str] = []
        for i, query in enumerate(node.queries):
            q = repr(query)
            if i == 0:
                lines.append(
                    f"{ctx.indent}{ctx.nxt} = {ctx.prv}.css_first({q})"
                )
            else:
                lines.append(f"{ctx.indent}if {ctx.nxt} is None:")
                lines.append(
                    f"{ctx.indent}    {ctx.nxt} = {ctx.prv}.css_first({q})"
                )
        return lines
    query = repr(node.query)
    return f"{ctx.indent}{ctx.nxt} = {ctx.prv}.css_first({query})"


@PY_SLAX_CONVERTER(a.CssSelectAll)
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


@PY_SLAX_CONVERTER(a.XpathSelect)
def pre_expr_xpath_select(node: a.XpathSelect, ctx: ConverterContext):
    raise NotImplementedError("selectolax not support xpath")


@PY_SLAX_CONVERTER(a.XpathSelectAll)
def pre_expr_xpath_select_all(node: a.XpathSelectAll, ctx: ConverterContext):
    raise NotImplementedError("selectolax not support xpath")


@PY_SLAX_CONVERTER(a.CssRemove)
def pre_expr_css_remove(node: a.CssRemove, ctx: ConverterContext):
    query = repr(node.query)
    return [
        f"{ctx.indent}[e.decompose() for e in {ctx.prv}.css({query})]",
        f"{ctx.indent}{ctx.nxt} = {ctx.prv}",
    ]


@PY_SLAX_CONVERTER(a.XpathRemove)
def pre_expr_xpath_remove(node: a.XpathRemove, ctx: ConverterContext):
    raise NotImplementedError("selectolax not support xpath")


@PY_SLAX_CONVERTER(a.Text)
def pre_expr_text(node: a.Text, ctx: ConverterContext):
    if node.accept == VT.DOCUMENT:
        return f"{ctx.indent}{ctx.nxt} = {ctx.prv}.text()"
    return f"{ctx.indent}{ctx.nxt} = [i.text() for i in {ctx.prv}]"


@PY_SLAX_CONVERTER(a.Raw)
def pre_expr_raw(node: a.Raw, ctx: ConverterContext):
    if node.accept == VT.DOCUMENT:
        return f"{ctx.indent}{ctx.nxt} = {ctx.prv}.html"
    return f"{ctx.indent}{ctx.nxt} = [i.html for i in {ctx.prv}]"


@PY_SLAX_CONVERTER(a.Attr)
def pre_expr_attr(node: a.Attr, ctx: ConverterContext):
    keys = node.keys
    if node.accept == VT.DOCUMENT:
        if len(keys) == 1:
            return f"{ctx.indent}{ctx.nxt} = {ctx.prv}.attributes[{keys[0]!r}]"
        return f"{ctx.indent}{ctx.nxt} = [{ctx.prv}.attributes[k] for k in {keys} if {ctx.prv}.attributes.get(k)]"
    if len(keys) == 1:
        return f"{ctx.indent}{ctx.nxt} = [e.attributes[{keys[0]!r}] for e in {ctx.prv}]"
    return f"{ctx.indent}{ctx.nxt} = [e.attributes[k] for e in {ctx.prv} for k in {keys} if e.attributes.get(k)]"


@PY_SLAX_CONVERTER(a.PredCss)
def pre_expr_pred_css(node: a.PredCss, ctx: ConverterContext):
    query = repr(node.query)
    cond = f"bool(i.css_first({query}))"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_SLAX_CONVERTER(a.PredXpath)
def pre_expr_pred_xpath(node: a.PredXpath, ctx: ConverterContext):
    raise NotImplementedError("selectolax not support xpath")


@PY_SLAX_CONVERTER(a.PredHasAttr)
def pre_expr_pred_has_attr(node: a.PredHasAttr, ctx: ConverterContext):
    attrs = node.attrs
    if len(attrs) == 1:
        cond = f"{attrs[0]!r} in i.attributes"
    else:
        cond = f"any(attr in i.attributes for attr in {attrs!r})"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_SLAX_CONVERTER(a.PredAttrEq)
def pre_expr_pred_attr_eq(node: a.PredAttrEq, ctx: ConverterContext):
    name = node.name
    values = node.values
    if len(values) == 1:
        cond = f"i.attributes.get({name!r}, '') == {values[0]!r}"
    else:
        cond = f"i.attributes.get({name!r}, '') in {values!r}"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_SLAX_CONVERTER(a.PredAttrNe)
def pre_expr_pred_attr_ne(node: a.PredAttrNe, ctx: ConverterContext):
    name = node.name
    values = node.values
    if len(values) == 1:
        cond = f"i.attributes.get({name!r}, '') != {values[0]!r}"
    else:
        cond = f"i.attributes.get({name!r}, '') not in {values!r}"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_SLAX_CONVERTER(a.PredAttrStarts)
def pre_expr_pred_attr_starts(node: a.PredAttrStarts, ctx: ConverterContext):
    name = node.name
    values = node.values
    if len(values) == 1:
        cond = f"i.attributes.get({name!r}, '').startswith({values[0]!r})"
    else:
        cond = f"any(i.attributes.get({name!r}, '').startswith(v) for v in {values!r})"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_SLAX_CONVERTER(a.PredAttrEnds)
def pre_expr_pred_attr_ends(node: a.PredAttrEnds, ctx: ConverterContext):
    name = node.name
    values = node.values
    if len(values) == 1:
        cond = f"i.attributes.get({name!r}, '').endswith({values[0]!r})"
    else:
        cond = f"any(i.attributes.get({name!r}, '').endswith(v) for v in {values!r})"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_SLAX_CONVERTER(a.PredAttrContains)
def pre_expr_pred_attr_contains(
    node: a.PredAttrContains, ctx: ConverterContext
):
    name = node.name
    values = node.values
    if len(values) == 1:
        cond = f"{values[0]!r} in i.attributes.get({name!r}, '')"
    else:
        cond = f"any(v in i.attributes.get({name!r}, '') for v in {values!r})"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_SLAX_CONVERTER(a.PredAttrRe)
def pre_expr_pred_attr_re(node: a.PredAttrRe, ctx: ConverterContext):
    name = node.name
    pattern = repr(node.pattern)
    cond = f"bool(re.search({pattern}, i.attributes.get({name!r}, '')))"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_SLAX_CONVERTER(a.PredTextStarts)
def pre_expr_pred_text_starts(node: a.PredTextStarts, ctx: ConverterContext):
    values = node.values
    if len(values) == 1:
        cond = f"i.text().startswith({values[0]!r})"
    else:
        cond = f"any(i.text().startswith(v) for v in {values!r})"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_SLAX_CONVERTER(a.PredTextEnds)
def pre_expr_pred_text_ends(node: a.PredTextEnds, ctx: ConverterContext):
    values = node.values
    if len(values) == 1:
        cond = f"i.text().endswith({values[0]!r})"
    else:
        cond = f"any(i.text().endswith(v) for v in {values!r})"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_SLAX_CONVERTER(a.PredTextContains)
def pre_expr_pred_text_contains(
    node: a.PredTextContains, ctx: ConverterContext
):
    values = node.values
    if len(values) == 1:
        cond = f"{values[0]!r} in i.text()"
    else:
        cond = f"any(v in i.text() for v in {values!r})"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_SLAX_CONVERTER(a.PredTextRe)
def pre_expr_pred_text_re(node: a.PredTextRe, ctx: ConverterContext):
    pattern = repr(node.pattern)
    cond = f"bool(re.search({pattern}, i.text()))"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"
