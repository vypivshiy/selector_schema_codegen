"""lxml dialect (new Visitor API).

Inherits all dialect-agnostic logic from ``PyHtmlBase`` and only sets the
lxml config attributes plus overrides the expression methods whose spelling
differs from bs4 (``.cssselect`` / ``.xpath`` / ``.text_content`` / ``.get`` /
``html.tostring``). No ``visit_module`` hack, no ``STD_LIBS`` mutation, no
``_resolve_py_type`` override — the base reads lxml config attrs directly.
"""

from ssc_codegen.ast.cast import ToBool
from ssc_codegen.ast.extract import Attr, Raw, Text
from ssc_codegen.ast.predicate_ops import (
    PredAttrContains,
    PredAttrEnds,
    PredAttrEq,
    PredAttrNe,
    PredAttrRe,
    PredAttrStarts,
    PredCss,
    PredHasAttr,
    PredTextContains,
    PredTextEnds,
    PredTextRe,
    PredTextStarts,
    PredXpath,
)
from ssc_codegen.ast.selectors import (
    CssRemove,
    CssSelect,
    CssSelectAll,
    XpathRemove,
    XpathSelect,
    XpathSelectAll,
)
from ssc_codegen.converters.base import ConverterContext
from ssc_codegen.converters.py_base import PyHtmlBase
from ssc_codegen.converters.visitor import STD, VisitStream


class PyLxml(PyHtmlBase):
    """lxml.html dialect."""

    STD_MODULE_NAME = "ssc_std"

    PARSER_IMPORTS = (
        "from lxml import html",
        "from lxml.html import HtmlElement",
    )
    DOCUMENT_TYPE = "HtmlElement"
    DOCUMENT_ARRAY_TYPE = "List[HtmlElement]"
    INIT_ARG_TYPE = "Union[str, HtmlElement]"
    INIT_FROM_STR_EXPR = (
        "html.fromstring(document.strip() or FALLBACK_HTML_STR)"
    )
    EXTRA_UTILITIES = (
        'FALLBACK_HTML_STR = "<html><body></body></html>"',
        "",
    )

    # === selectors ===

    def visit_css_select(
        self, node: CssSelect, ctx: ConverterContext
    ) -> VisitStream:
        if len(node.queries) == 1:
            q = repr(node.queries[0])
            yield f"{ctx.indent}{ctx.nxt} = {ctx.prv}.cssselect({q})[0]"
        else:
            yield STD(
                "std_select_first",
                code="""
                    def std_select_first(tag, *queries):
                        for q in queries:
                            t = tag.cssselect(q)
                            if t:
                                return t[0]
                """,
            )
            args = ",".join(repr(q) for q in node.queries)
            yield f"{ctx.indent}{ctx.nxt} = std_select_first({ctx.prv}, {args})"

    def visit_css_select_all(
        self, node: CssSelectAll, ctx: ConverterContext
    ) -> VisitStream:
        if len(node.queries) == 1:
            q = repr(node.queries[0])
            yield f"{ctx.indent}{ctx.nxt} = {ctx.prv}.cssselect({q})"
        else:
            yield STD(
                "std_select_all_first",
                code="""
                    def std_select_all_first(tag, *queries):
                        for q in queries:
                            t = tag.cssselect(q)
                            if t:
                                return t
                        return []
                """,
            )
            args = ",".join(repr(q) for q in node.queries)
            yield f"{ctx.indent}{ctx.nxt} = std_select_all_first({ctx.prv}, {args})"

    def visit_css_remove(
        self, node: CssRemove, ctx: ConverterContext
    ) -> VisitStream:
        q = repr(node.query)
        yield STD(
            "std_select_remove",
            code="""
                def std_select_remove(tag, q):
                    [_el.getparent().remove(_el) for _el in tag.cssselect(q) if _el.getparent() is not None]
                    return tag
                """,
        )
        yield f"{ctx.indent}{ctx.nxt} = std_select_remove({ctx.prv}, {q})"

    def visit_xpath_select(
        self, node: XpathSelect, ctx: ConverterContext
    ) -> VisitStream:
        if len(node.queries) == 1:
            q = repr(node.queries[0])
            yield f"{ctx.indent}{ctx.nxt} = {ctx.prv}.xpath({q})[0]"
        else:
            yield STD(
                "std_xpath_first",
                code="""
                    def std_xpath_first(tag, *queries):
                        for q in queries:
                            t = tag.xpath(q)
                            if t:
                                return t[0]
                """,
            )
            args = ",".join(repr(q) for q in node.queries)
            yield f"{ctx.indent}{ctx.nxt} = std_xpath_first({ctx.prv}, {args})"

    def visit_xpath_select_all(
        self, node: XpathSelectAll, ctx: ConverterContext
    ) -> VisitStream:
        if len(node.queries) == 1:
            q = repr(node.queries[0])
            yield f"{ctx.indent}{ctx.nxt} = {ctx.prv}.xpath({q})"
        else:
            yield STD(
                "std_xpath_all_first",
                code="""
                    def std_xpath_all_first(tag, *queries):
                        for q in queries:
                            t = tag.xpath(q)
                            if t:
                                return t
                        return []
                """,
            )
            args = ",".join(repr(q) for q in node.queries)
            yield f"{ctx.indent}{ctx.nxt} = std_xpath_all_first({ctx.prv}, {args})"

    def visit_xpath_remove(
        self, node: XpathRemove, ctx: ConverterContext
    ) -> VisitStream:
        q = repr(node.query)
        yield STD(
            "std_xpath_remove",
            code="""
                def std_xpath_remove(tag, q):
                    [_el.getparent().remove(_el) for _el in tag.xpath(q) if _el.getparent() is not None]
                    return tag
                """,
        )
        yield f"{ctx.indent}{ctx.nxt} = std_xpath_remove({ctx.prv}, {q})"

    # === extract ===

    def visit_text(self, node: Text, ctx: ConverterContext) -> VisitStream:
        if node.accept_type_info.is_array:
            yield f"{ctx.indent}{ctx.nxt} = [i.text_content() for i in {ctx.prv}]"
        else:
            yield f"{ctx.indent}{ctx.nxt} = {ctx.prv}.text_content()"

    def visit_raw(self, node: Raw, ctx: ConverterContext) -> VisitStream:
        if node.accept_type_info.is_array:
            yield f"{ctx.indent}{ctx.nxt} = [html.tostring(i, encoding='unicode') for i in {ctx.prv}]"
        else:
            yield f"{ctx.indent}{ctx.nxt} = html.tostring({ctx.prv}, encoding='unicode')"

    def visit_attr(self, node: Attr, ctx: ConverterContext) -> VisitStream:
        keys = node.keys
        if not node.accept_type_info.is_array:
            if len(keys) == 1:
                yield f"{ctx.indent}{ctx.nxt} = {ctx.prv}.get({keys[0]!r}, '')"
            else:
                yield f"{ctx.indent}{ctx.nxt} = [{ctx.prv}.get(k) for k in {keys!r} if {ctx.prv}.get(k)]"
        else:
            if len(keys) == 1:
                yield f"{ctx.indent}{ctx.nxt} = [i.get({keys[0]!r}, '') for i in {ctx.prv}]"
            else:
                yield f"{ctx.indent}{ctx.nxt} = [i.get(k) for i in {ctx.prv} for k in {keys!r} if i.get(k)]"

    # === casts (lxml-specific) ===

    def visit_to_bool(self, node: ToBool, ctx: ConverterContext) -> VisitStream:
        # lxml HtmlElement.__bool__ returns len(self), which is False for leaf
        # elements — so the scalar case must test against None explicitly.
        if node.accept_type_info.is_array:
            yield f"{ctx.indent}{ctx.nxt} = len({ctx.prv}) > 0"
        else:
            yield f"{ctx.indent}{ctx.nxt} = {ctx.prv} is not None or {ctx.prv} != '' or {ctx.prv} != 0"

    # === document / attr / text predicates (lxml spellings) ===

    def visit_predicate_css(
        self, node: PredCss, ctx: ConverterContext
    ) -> VisitStream:
        query = repr(node.query)
        yield self._pred_line(ctx, f"bool(i.cssselect({query}))")

    def visit_predicate_xpath(
        self, node: PredXpath, ctx: ConverterContext
    ) -> VisitStream:
        query = repr(node.query)
        yield self._pred_line(ctx, f"bool(i.xpath({query}))")

    def visit_predicate_has_attr(
        self, node: PredHasAttr, ctx: ConverterContext
    ) -> VisitStream:
        attrs = node.attrs
        if len(attrs) == 1:
            cond = f"{attrs[0]!r} in i.attrib"
        else:
            cond = f"any(attr in i.attrib for attr in {attrs!r})"
        yield self._pred_line(ctx, cond)

    def visit_predicate_attr_eq(
        self, node: PredAttrEq, ctx: ConverterContext
    ) -> VisitStream:
        name = node.name
        values = node.values
        if len(values) == 1:
            cond = f"i.get({name!r}, '') == {values[0]!r}"
        else:
            cond = f"i.get({name!r}, '') in {values!r}"
        yield self._pred_line(ctx, cond)

    def visit_predicate_attr_ne(
        self, node: PredAttrNe, ctx: ConverterContext
    ) -> VisitStream:
        name = node.name
        values = node.values
        if len(values) == 1:
            cond = f"i.get({name!r}, '') != {values[0]!r}"
        else:
            cond = f"i.get({name!r}, '') not in {values!r}"
        yield self._pred_line(ctx, cond)

    def visit_predicate_attr_starts(
        self, node: PredAttrStarts, ctx: ConverterContext
    ) -> VisitStream:
        name = node.name
        values = node.values
        if len(values) == 1:
            cond = f"i.get({name!r}, '').startswith({values[0]!r})"
        else:
            cond = f"any(i.get({name!r}, '').startswith(v) for v in {values!r})"
        yield self._pred_line(ctx, cond)

    def visit_predicate_attr_ends(
        self, node: PredAttrEnds, ctx: ConverterContext
    ) -> VisitStream:
        name = node.name
        values = node.values
        if len(values) == 1:
            cond = f"i.get({name!r}, '').endswith({values[0]!r})"
        else:
            cond = f"any(i.get({name!r}, '').endswith(v) for v in {values!r})"
        yield self._pred_line(ctx, cond)

    def visit_predicate_attr_contains(
        self, node: PredAttrContains, ctx: ConverterContext
    ) -> VisitStream:
        name = node.name
        values = node.values
        if len(values) == 1:
            cond = f"{values[0]!r} in i.get({name!r}, '')"
        else:
            cond = f"any(v in i.get({name!r}, '') for v in {values!r})"
        yield self._pred_line(ctx, cond)

    def visit_predicate_attr_re(
        self, node: PredAttrRe, ctx: ConverterContext
    ) -> VisitStream:
        name = node.name
        pat = repr(node.pattern)
        yield self._pred_line(
            ctx, f"bool(re.search({pat}, i.get({name!r}, '')))"
        )

    def visit_predicate_text_contains(
        self, node: PredTextContains, ctx: ConverterContext
    ) -> VisitStream:
        values = node.values
        if len(values) == 1:
            cond = f"{values[0]!r} in i.text_content()"
        else:
            cond = f"any(v in i.text_content() for v in {values!r})"
        yield self._pred_line(ctx, cond)

    def visit_predicate_text_starts(
        self, node: PredTextStarts, ctx: ConverterContext
    ) -> VisitStream:
        values = node.values
        if len(values) == 1:
            cond = f"i.text_content().startswith({values[0]!r})"
        else:
            cond = f"any(i.text_content().startswith(v) for v in {values!r})"
        yield self._pred_line(ctx, cond)

    def visit_predicate_text_ends(
        self, node: PredTextEnds, ctx: ConverterContext
    ) -> VisitStream:
        values = node.values
        if len(values) == 1:
            cond = f"i.text_content().endswith({values[0]!r})"
        else:
            cond = f"any(i.text_content().endswith(v) for v in {values!r})"
        yield self._pred_line(ctx, cond)

    def visit_predicate_text_re(
        self, node: PredTextRe, ctx: ConverterContext
    ) -> VisitStream:
        pat = repr(node.pattern)
        yield self._pred_line(ctx, f"bool(re.search({pat}, i.text_content()))")


PY_LXML_CONVERTER = PyLxml()
