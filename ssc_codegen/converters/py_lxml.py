"""
lxml converter - inherits from py_bs4 and overrides selector methods.

Key differences from bs4:
- Uses lxml.html instead of BeautifulSoup
- .cssselect() instead of .select() / .select_one()
- .xpath() instead of custom xpath implementation
- .text_content() instead of .text
- .get() for attributes instead of .get_attribute_list()
"""

from ssc_codegen.converters.base import ConverterContext
from ssc_codegen.converters.helpers import to_snake_case

# Import all AST nodes (same as bs4)
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
)

from ssc_codegen.ast import (
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

# Import the bs4 converter to inherit from it
from ssc_codegen.converters import py_bs4

# Create new converter that extends bs4 (inherits all handlers)
PY_LXML_CONVERTER = py_bs4.PY_BASE_CONVERTER.extend()

# Override specific handlers for lxml


@PY_LXML_CONVERTER(Imports)
def pre_imports(node: Imports, _: ConverterContext):
    base_imports = [
        "import json",
        "import re",
        "import sys",
        "from typing import TypedDict, Optional, Any, List, Dict, Union",
        "from html import unescape as _html_unescape",
    ]

    # Get transform imports for Python (already collected during parsing)
    transform_imports = sorted(node.transform_imports.get("py", set()))

    return base_imports + transform_imports


@PY_LXML_CONVERTER.post(Imports)
def post_imports(node: Imports, _):
    return [
        "from lxml import html",
        "from lxml.html import HtmlElement",
    ]


@PY_LXML_CONVERTER(Utilities)
def pre_utilities(node: Utilities, _: ConverterContext):
    return [
        'FALLBACK_HTML_STR = "<html><body></body></html>"',
        "_RE_HEX_ENTITY = re.compile(r'&#x([0-9a-fA-F]+);')",
        "_RE_UNICODE_ENTITY = re.compile(r'\\\\u([0-9a-fA-F]{4})')",
        "_RE_BYTES_ENTITY = re.compile(r'\\\\x([0-9a-fA-F]{2})')",
        "_RE_CHARS_MAP = {'\\\\b': '\\\\b', '\\\\f': '\\\\f', '\\\\n': '\\\\n', '\\\\r': '\\\\r', '\\\\t': '\\\\t'}",
        "\n",
        "def repl_map(s: str, rmap: Dict[str, str]) -> str:",
        "    for k, v in rmap.items():",
        "        s = s.replace(k, v)",
        "    return s",
        "\n",
        "def normalize_text(text: str) -> str:",
        "    return ' '.join(text.split()) if text else \"\"",
        "\n",
        "class _UnmatchedTableRow:",
        "    pass",
        "\n",
        "def unescape_text(text: str) -> str:",
        "    s = _html_unescape(text)",
        "    s = _RE_HEX_ENTITY.sub(lambda m: chr(int(m.group(1), 16)), s)",
        "    s = _RE_UNICODE_ENTITY.sub(lambda m: chr(int(m.group(1), 16)), s)",
        "    s = _RE_BYTES_ENTITY.sub(lambda m: chr(int(m.group(1), 16)), s)",
        "    for ch, r in _RE_CHARS_MAP.items():",
        "        s = s.replace(ch, r)",
        "    return s",
        "\n",
        "if sys.version_info >= (3, 9):",
        "    def rm_prefix(s: str, p: str) -> str:",
        "        return s.removeprefix(p)",
        "\n",
        "    def rm_suffix(s: str, p: str) -> str:",
        "        return s.removesuffix(p)",
        "\n",
        "else:",
        "    def rm_prefix(s: str, p: str) -> str:",
        "        return s[len(p):] if s.startswith(p) else s",
        "\n",
        "    def rm_suffix(s: str, p: str) -> str:",
        "        return s[:-(len(p))] if s.endswith(p) else s",
        "\n\n",
        "UNMATCHED_TABLE_ROW = _UnmatchedTableRow()",
        "\n\n",
    ]


# Override struct __init__ to use lxml instead of BeautifulSoup
@PY_LXML_CONVERTER(Init)
def pre_init(node: Init, ctx: ConverterContext):
    init_node_names: list[str] = []
    for i in node.body:
        if isinstance(i, InitField):
            name = to_snake_case(i.name)
            init_node_names.append(name)
    code = [
        f"{ctx.indent}def __init__(self, document: Union[str, HtmlElement]):",
        f"{ctx.indent * 2}if isinstance(document, HtmlElement):",
        f"{ctx.indent * 3}self._doc = document",
        f"{ctx.indent * 2}elif isinstance(document, str):",
        f"{ctx.indent * 3}self._doc = html.fromstring(document.strip() or FALLBACK_HTML_STR)",
    ]
    for name in init_node_names:
        code.append(
            f"{ctx.indent * 2}self._{name} = self._init_{name}(self._doc)"
        )
    return code


@PY_LXML_CONVERTER(InitField)
def pre_init_field(node: InitField, ctx: ConverterContext):
    name = to_snake_case(node.name)
    ret_type = py_bs4.PY_TYPES.get(node.ret, "Any")
    return [f"    def _init_{name}(self, v: HtmlElement) -> {ret_type}:"]


@PY_LXML_CONVERTER(Field)
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
            f"    def _parse_{name}(self, v: HtmlElement) -> Union[{ret_type}, _UnmatchedTableRow]:"
        ]
    return [f"    def _parse_{name}(self, v: HtmlElement) -> {ret_type}:"]


@PY_LXML_CONVERTER(Key)
def pre_struct_key(node: Key, ctx: ConverterContext):
    return ["    def _parse_key(self, v: HtmlElement) -> str:"]


@PY_LXML_CONVERTER(Value)
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

    return [f"    def _parse_value(self, v: HtmlElement) -> {ret_type}:"]


@PY_LXML_CONVERTER(PreValidate)
def pre_struct_pre_validate(node: PreValidate, ctx: ConverterContext):
    return ["    def _pre_validate(self, v: HtmlElement) -> None:"]


@PY_LXML_CONVERTER(SplitDoc)
def pre_struct_split_doc(node: SplitDoc, ctx: ConverterContext):
    return ["    def _split_doc(self, v: HtmlElement) -> List[HtmlElement]:"]


@PY_LXML_CONVERTER(TableConfig)
def pre_struct_table_config(node: TableConfig, ctx: ConverterContext):
    return ["    def _table_config(self, v: HtmlElement) -> HtmlElement:"]


@PY_LXML_CONVERTER(TableMatchKey)
def pre_struct_table_match_key(node: TableMatchKey, ctx: ConverterContext):
    return ["    def _table_match_key(self, v: HtmlElement) -> str:"]


@PY_LXML_CONVERTER(TableRow)
def pre_struct_table_row(node: TableRow, ctx: ConverterContext):
    return [
        "    def _parse_table_rows(self, v: HtmlElement) -> List[HtmlElement]:"
    ]


# SELECTORS - Main differences from bs4


@PY_LXML_CONVERTER(CssSelect)
def pre_expr_css_select(node: CssSelect, ctx: ConverterContext):
    query = repr(node.query)
    return f"{ctx.indent}{ctx.nxt} = {ctx.prv}.cssselect({query})[0]"


@PY_LXML_CONVERTER(CssSelectAll)
def pre_expr_css_select_all(node: CssSelectAll, ctx: ConverterContext):
    query = repr(node.query)
    return f"{ctx.indent}{ctx.nxt} = {ctx.prv}.cssselect({query})"


@PY_LXML_CONVERTER(XpathSelect)
def pre_expr_xpath_select(node: XpathSelect, ctx: ConverterContext):
    query = repr(node.query)
    return f"{ctx.indent}{ctx.nxt} = {ctx.prv}.xpath({query})[0]"


@PY_LXML_CONVERTER(XpathSelectAll)
def pre_expr_xpath_select_all(node: XpathSelectAll, ctx: ConverterContext):
    query = repr(node.query)
    return f"{ctx.indent}{ctx.nxt} = {ctx.prv}.xpath({query})"


@PY_LXML_CONVERTER(CssRemove)
def pre_expr_css_remove(node: CssRemove, ctx: ConverterContext):
    query = repr(node.query)
    return [
        f"{ctx.indent}[e.getparent().remove(e) for e in {ctx.prv}.cssselect({query}) if e.getparent() is not None]",
        f"{ctx.indent}{ctx.nxt} = {ctx.prv}",
    ]


@PY_LXML_CONVERTER(XpathRemove)
def pre_expr_xpath_remove(node: XpathRemove, ctx: ConverterContext):
    query = repr(node.query)
    return [
        f"{ctx.indent}[e.getparent().remove(e) for e in {ctx.prv}.xpath({query}) if e.getparent() is not None]",
        f"{ctx.indent}{ctx.nxt} = {ctx.prv}",
    ]


# EXTRACT - text, raw, attr


@PY_LXML_CONVERTER(Text)
def pre_expr_text(node: Text, ctx: ConverterContext):
    if node.accept == VariableType.DOCUMENT:
        return f"{ctx.indent}{ctx.nxt} = {ctx.prv}.text_content()"
    # LIST_DOCUMENT
    return f"{ctx.indent}{ctx.nxt} = [i.text_content() for i in {ctx.prv}]"


@PY_LXML_CONVERTER(Raw)
def pre_expr_raw(node: Raw, ctx: ConverterContext):
    if node.accept == VariableType.DOCUMENT:
        return f"{ctx.indent}{ctx.nxt} = html.tostring({ctx.prv}, encoding='unicode')"
    # LIST_DOCUMENT
    return f"{ctx.indent}{ctx.nxt} = [html.tostring(i, encoding='unicode') for i in {ctx.prv}]"


@PY_LXML_CONVERTER(Attr)
def pre_expr_attr(node: Attr, ctx: ConverterContext):
    keys = node.keys
    if node.accept == VariableType.DOCUMENT:
        if len(keys) == 1:
            return f"{ctx.indent}{ctx.nxt} = {ctx.prv}.get({keys[0]!r}, '')"
        # Multiple attributes: concatenate with space
        attrs = " + ' ' + ".join(f"{ctx.prv}.get({k!r}, '')" for k in keys)
        return f"{ctx.indent}{ctx.nxt} = {attrs}"
    # LIST_DOCUMENT
    if len(keys) == 1:
        return f"{ctx.indent}{ctx.nxt} = [i.get({keys[0]!r}, '') for i in {ctx.prv}]"
    # Multiple attributes
    attrs = " + ' ' + ".join(f"i.get({k!r}, '')" for k in keys)
    return f"{ctx.indent}{ctx.nxt} = [{attrs} for i in {ctx.prv}]"


# PREDICATES - CSS and XPath


@PY_LXML_CONVERTER(PredCss)
def pre_expr_pred_css(node: PredCss, ctx: ConverterContext):
    query = repr(node.query)
    cond = f"bool(i.cssselect({query}))"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_LXML_CONVERTER(PredXpath)
def pre_expr_pred_xpath(node: PredXpath, ctx: ConverterContext):
    query = repr(node.query)
    cond = f"bool(i.xpath({query}))"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_LXML_CONVERTER(PredHasAttr)
def pre_expr_pred_has_attr(node: PredHasAttr, ctx: ConverterContext):
    attrs = node.attrs
    if len(attrs) == 1:
        cond = f"{attrs[0]!r} in i.attrib"
    else:
        cond = f"any(attr in i.attrib for attr in {attrs!r})"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_LXML_CONVERTER(PredAttrEq)
def pre_expr_pred_attr_eq(node: PredAttrEq, ctx: ConverterContext):
    name = node.name
    values = node.values
    if len(values) == 1:
        cond = f"i.get({name!r}, '') == {values[0]!r}"
    else:
        cond = f"i.get({name!r}, '') in {values!r}"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_LXML_CONVERTER(PredAttrNe)
def pre_expr_pred_attr_ne(node: PredAttrNe, ctx: ConverterContext):
    name = node.name
    values = node.values
    if len(values) == 1:
        cond = f"i.get({name!r}, '') != {values[0]!r}"
    else:
        cond = f"i.get({name!r}, '') not in {values!r}"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_LXML_CONVERTER(PredAttrStarts)
def pre_expr_pred_attr_starts(node: PredAttrStarts, ctx: ConverterContext):
    name = node.name
    values = node.values
    if len(values) == 1:
        cond = f"i.get({name!r}, '').startswith({values[0]!r})"
    else:
        cond = f"any(i.get({name!r}, '').startswith(v) for v in {values!r})"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_LXML_CONVERTER(PredAttrEnds)
def pre_expr_pred_attr_ends(node: PredAttrEnds, ctx: ConverterContext):
    name = node.name
    values = node.values
    if len(values) == 1:
        cond = f"i.get({name!r}, '').endswith({values[0]!r})"
    else:
        cond = f"any(i.get({name!r}, '').endswith(v) for v in {values!r})"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_LXML_CONVERTER(PredAttrContains)
def pre_expr_pred_attr_contains(node: PredAttrContains, ctx: ConverterContext):
    name = node.name
    values = node.values
    if len(values) == 1:
        cond = f"{values[0]!r} in i.get({name!r}, '')"
    else:
        cond = f"any(v in i.get({name!r}, '') for v in {values!r})"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_LXML_CONVERTER(PredAttrRe)
def pre_expr_pred_attr_re(node: PredAttrRe, ctx: ConverterContext):
    name = node.name
    pattern = repr(node.pattern)
    cond = f"bool(re.search({pattern}, i.get({name!r}, '')))"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_LXML_CONVERTER(PredTextStarts)
def pre_expr_pred_text_starts(node: PredTextStarts, ctx: ConverterContext):
    values = node.values
    if len(values) == 1:
        cond = f"i.text_content().startswith({values[0]!r})"
    else:
        cond = f"any(i.text_content().startswith(v) for v in {values!r})"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_LXML_CONVERTER(PredTextEnds)
def pre_expr_pred_text_ends(node: PredTextEnds, ctx: ConverterContext):
    values = node.values
    if len(values) == 1:
        cond = f"i.text_content().endswith({values[0]!r})"
    else:
        cond = f"any(i.text_content().endswith(v) for v in {values!r})"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_LXML_CONVERTER(PredTextContains)
def pre_expr_pred_text_contains(node: PredTextContains, ctx: ConverterContext):
    values = node.values
    if len(values) == 1:
        cond = f"{values[0]!r} in i.text_content()"
    else:
        cond = f"any(v in i.text_content() for v in {values!r})"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_LXML_CONVERTER(PredTextRe)
def pre_expr_pred_text_re(node: PredTextRe, ctx: ConverterContext):
    pattern = repr(node.pattern)
    cond = f"bool(re.search({pattern}, i.text_content()))"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"
