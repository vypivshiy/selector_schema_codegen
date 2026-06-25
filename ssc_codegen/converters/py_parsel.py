"""parsel dialect (new Visitor API).

Inherits all dialect-agnostic logic from ``PyHtmlBase`` and only sets the
parsel config attributes plus overrides the expression methods whose spelling
differs from bs4/lxml (``.css`` / ``.xpath`` / ``.get`` / ``.getall`` /
``.attrib`` / text via ``xpath('.//text()').getall()``).
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


class PyParsel(PyHtmlBase):
    """parsel.Selector dialect."""

    STD_MODULE_NAME = "ssc_std"

    PARSER_IMPORTS = ("from parsel import Selector, SelectorList",)
    DOCUMENT_TYPE = "Selector"
    DOCUMENT_ARRAY_TYPE = "SelectorList"
    INIT_ARG_TYPE = "Union[str, Selector, SelectorList]"
    INIT_FROM_STR_EXPR = "Selector(document)"
    EXTRA_UTILITIES: tuple[str, ...] = ()

    # === selectors ===

    def visit_css_select(
        self, node: CssSelect, ctx: ConverterContext
    ) -> VisitStream:
        if len(node.queries) == 1:
            q = repr(node.queries[0])
            yield f"{ctx.indent}{ctx.nxt} = {ctx.prv}.css({q})[0]"
        else:
            yield STD(
                "std_select_first",
                code="""
                    def std_select_first(tag, *queries):
                        for q in queries:
                            t = tag.css(q)
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
            yield f"{ctx.indent}{ctx.nxt} = {ctx.prv}.css({q})"
        else:
            yield STD(
                "std_select_all_first",
                code="""
                    def std_select_all_first(tag, *queries):
                        for q in queries:
                            t = tag.css(q)
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
        yield f"{ctx.indent}[_el.root.getparent().remove(_el.root) for _el in {ctx.prv}.css({q}) if _el.root.getparent() is not None]"
        yield f"{ctx.indent}{ctx.nxt} = {ctx.prv}"

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
        yield f"{ctx.indent}[_el.root.getparent().remove(_el.root) for _el in {ctx.prv}.xpath({q}) if _el.root.getparent() is not None]"
        yield f"{ctx.indent}{ctx.nxt} = {ctx.prv}"

    # === extract ===

    def visit_text(self, node: Text, ctx: ConverterContext) -> VisitStream:
        if node.accept_type_info.is_array:
            yield f"{ctx.indent}{ctx.nxt} = [' '.join(i.xpath('.//text()').getall()) for i in {ctx.prv}]"
        else:
            yield f"{ctx.indent}{ctx.nxt} = ' '.join({ctx.prv}.xpath('.//text()').getall())"

    def visit_raw(self, node: Raw, ctx: ConverterContext) -> VisitStream:
        if node.accept_type_info.is_array:
            yield f"{ctx.indent}{ctx.nxt} = {ctx.prv}.getall()"
        else:
            yield f"{ctx.indent}{ctx.nxt} = {ctx.prv}.get()"

    def visit_attr(self, node: Attr, ctx: ConverterContext) -> VisitStream:
        keys = node.keys
        if not node.accept_type_info.is_array:
            if len(keys) == 1:
                yield f"{ctx.indent}{ctx.nxt} = {ctx.prv}.attrib[{keys[0]!r}]"
            else:
                yield f"{ctx.indent}{ctx.nxt} = [{ctx.prv}.attrib[k] for k in {keys!r} if {ctx.prv}.attrib.get(k)]"
        else:
            if len(keys) == 1:
                yield f"{ctx.indent}{ctx.nxt} = [e.attrib[{keys[0]!r}] for e in {ctx.prv}]"
            else:
                yield f"{ctx.indent}{ctx.nxt} = [e.attrib[k] for e in {ctx.prv} for k in {keys!r} if e.attrib.get(k)]"

    # === casts (parsel-specific) ===

    def visit_to_bool(self, node: ToBool, ctx: ConverterContext) -> VisitStream:
        # parsel SelectorList is truthy when non-empty; a Selector is truthy
        # when it wraps an element — `bool()` covers both cases uniformly.
        yield f"{ctx.indent}{ctx.nxt} = bool({ctx.prv})"

    # === document / attr / text predicates (parsel spellings) ===

    def visit_predicate_css(
        self, node: PredCss, ctx: ConverterContext
    ) -> VisitStream:
        query = repr(node.query)
        yield self._pred_line(ctx, f"bool(i.css({query}))")

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
            cond = f"i.attrib.get({name!r}, '') == {values[0]!r}"
        else:
            cond = f"i.attrib.get({name!r}, '') in {values!r}"
        yield self._pred_line(ctx, cond)

    def visit_predicate_attr_ne(
        self, node: PredAttrNe, ctx: ConverterContext
    ) -> VisitStream:
        name = node.name
        values = node.values
        if len(values) == 1:
            cond = f"i.attrib.get({name!r}, '') != {values[0]!r}"
        else:
            cond = f"i.attrib.get({name!r}, '') not in {values!r}"
        yield self._pred_line(ctx, cond)

    def visit_predicate_attr_starts(
        self, node: PredAttrStarts, ctx: ConverterContext
    ) -> VisitStream:
        name = node.name
        values = node.values
        if len(values) == 1:
            cond = f"i.attrib.get({name!r}, '').startswith({values[0]!r})"
        else:
            cond = f"any(i.attrib.get({name!r}, '').startswith(v) for v in {values!r})"
        yield self._pred_line(ctx, cond)

    def visit_predicate_attr_ends(
        self, node: PredAttrEnds, ctx: ConverterContext
    ) -> VisitStream:
        name = node.name
        values = node.values
        if len(values) == 1:
            cond = f"i.attrib.get({name!r}, '').endswith({values[0]!r})"
        else:
            cond = f"any(i.attrib.get({name!r}, '').endswith(v) for v in {values!r})"
        yield self._pred_line(ctx, cond)

    def visit_predicate_attr_contains(
        self, node: PredAttrContains, ctx: ConverterContext
    ) -> VisitStream:
        name = node.name
        values = node.values
        if len(values) == 1:
            cond = f"{values[0]!r} in i.attrib.get({name!r}, '')"
        else:
            cond = f"any(v in i.attrib.get({name!r}, '') for v in {values!r})"
        yield self._pred_line(ctx, cond)

    def visit_predicate_attr_re(
        self, node: PredAttrRe, ctx: ConverterContext
    ) -> VisitStream:
        name = node.name
        pat = repr(node.pattern)
        yield self._pred_line(
            ctx, f"bool(re.search({pat}, i.attrib.get({name!r}, '')))"
        )

    def visit_predicate_text_contains(
        self, node: PredTextContains, ctx: ConverterContext
    ) -> VisitStream:
        values = node.values
        if len(values) == 1:
            cond = f"{values[0]!r} in ' '.join(i.xpath('.//text()').getall())"
        else:
            cond = f"any(v in ' '.join(i.xpath('.//text()').getall()) for v in {values!r})"
        yield self._pred_line(ctx, cond)

    def visit_predicate_text_starts(
        self, node: PredTextStarts, ctx: ConverterContext
    ) -> VisitStream:
        values = node.values
        if len(values) == 1:
            cond = f"' '.join(i.xpath('.//text()').getall()).startswith({values[0]!r})"
        else:
            cond = f"any(' '.join(i.xpath('.//text()').getall()).startswith(v) for v in {values!r})"
        yield self._pred_line(ctx, cond)

    def visit_predicate_text_ends(
        self, node: PredTextEnds, ctx: ConverterContext
    ) -> VisitStream:
        values = node.values
        if len(values) == 1:
            cond = f"' '.join(i.xpath('.//text()').getall()).endswith({values[0]!r})"
        else:
            cond = f"any(' '.join(i.xpath('.//text()').getall()).endswith(v) for v in {values!r})"
        yield self._pred_line(ctx, cond)

    def visit_predicate_text_re(
        self, node: PredTextRe, ctx: ConverterContext
    ) -> VisitStream:
        pat = repr(node.pattern)
        yield self._pred_line(
            ctx,
            f"bool(re.search({pat}, ' '.join(i.xpath('.//text()').getall())))",
        )


PY_PARSEL_CONVERTER = PyParsel()
