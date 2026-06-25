"""selectolax dialect (new Visitor API).

Inherits all dialect-agnostic logic from ``PyHtmlBase`` and only sets the
selectolax config attributes plus overrides the expression methods whose
spelling differs from bs4/lxml/parsel (``.css_first`` / ``.css`` /
``.text()`` / ``.html`` / ``.attributes``). Xpath is not supported by
selectolax and raises ``NotImplementedError``.
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


class PySlax(PyHtmlBase):
    """selectolax.lexbor dialect."""

    STD_MODULE_NAME = "ssc_std"

    PARSER_IMPORTS = (
        "from selectolax.lexbor import "
        "LexborHTMLParser as HTMLParser, LexborNode as Node",
    )
    DOCUMENT_TYPE = "Node"
    DOCUMENT_ARRAY_TYPE = "List[Node]"
    INIT_ARG_TYPE = "Union[str, HTMLParser, Node]"
    INIT_FROM_STR_EXPR = "HTMLParser(document)"
    EXTRA_UTILITIES: tuple[str, ...] = ()

    # === selectors ===

    def visit_css_select(
        self, node: CssSelect, ctx: ConverterContext
    ) -> VisitStream:
        if len(node.queries) == 1:
            q = repr(node.queries[0])
            yield f"{ctx.indent}{ctx.nxt} = {ctx.prv}.css_first({q})"
        else:
            yield STD(
                "std_select_first",
                code="""
                    def std_select_first(tag, *queries):
                        for q in queries:
                            t = tag.css_first(q)
                            if t:
                                return t
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
                        result = []
                        for q in queries:
                            result = tag.css(q)
                            if result:
                                return result
                        return []
                """,
            )
            args = ",".join(repr(q) for q in node.queries)
            yield f"{ctx.indent}{ctx.nxt} = std_select_all_first({ctx.prv}, {args})"

    def visit_css_remove(
        self, node: CssRemove, ctx: ConverterContext
    ) -> VisitStream:
        q = repr(node.query)
        yield f"{ctx.indent}[e.decompose() for e in {ctx.prv}.css({q})]"
        yield f"{ctx.indent}{ctx.nxt} = {ctx.prv}"

    def visit_xpath_select(
        self, node: XpathSelect, ctx: ConverterContext
    ) -> VisitStream:
        raise NotImplementedError

    def visit_xpath_select_all(
        self, node: XpathSelectAll, ctx: ConverterContext
    ) -> VisitStream:
        raise NotImplementedError

    def visit_xpath_remove(
        self, node: XpathRemove, ctx: ConverterContext
    ) -> VisitStream:
        raise NotImplementedError

    # === extract ===

    def visit_text(self, node: Text, ctx: ConverterContext) -> VisitStream:
        if node.accept_type_info.is_array:
            yield f"{ctx.indent}{ctx.nxt} = [i.text() for i in {ctx.prv}]"
        else:
            yield f"{ctx.indent}{ctx.nxt} = {ctx.prv}.text()"

    def visit_raw(self, node: Raw, ctx: ConverterContext) -> VisitStream:
        if node.accept_type_info.is_array:
            yield f"{ctx.indent}{ctx.nxt} = [i.html for i in {ctx.prv}]"
        else:
            yield f"{ctx.indent}{ctx.nxt} = {ctx.prv}.html"

    def visit_attr(self, node: Attr, ctx: ConverterContext) -> VisitStream:
        keys = node.keys
        if not node.accept_type_info.is_array:
            if len(keys) == 1:
                yield f"{ctx.indent}{ctx.nxt} = {ctx.prv}.attributes[{keys[0]!r}]"
            else:
                yield f"{ctx.indent}{ctx.nxt} = [{ctx.prv}.attributes[k] for k in {keys!r} if {ctx.prv}.attributes.get(k)]"
        else:
            if len(keys) == 1:
                yield f"{ctx.indent}{ctx.nxt} = [e.attributes[{keys[0]!r}] for e in {ctx.prv}]"
            else:
                yield f"{ctx.indent}{ctx.nxt} = [e.attributes[k] for e in {ctx.prv} for k in {keys!r} if e.attributes.get(k)]"

    # === casts (selectolax-specific) ===

    def visit_to_bool(self, node: ToBool, ctx: ConverterContext) -> VisitStream:
        # css_first returns None on miss; a valid LexborNode, empty string,
        # empty list and zero are all falsy under bool() — one check covers
        # every accept type.
        yield f"{ctx.indent}{ctx.nxt} = bool({ctx.prv})"

    # === document / attr / text predicates (selectolax spellings) ===

    def visit_predicate_css(
        self, node: PredCss, ctx: ConverterContext
    ) -> VisitStream:
        query = repr(node.query)
        yield self._pred_line(ctx, f"bool(i.css_first({query}))")

    def visit_predicate_xpath(
        self, node: PredXpath, ctx: ConverterContext
    ) -> VisitStream:
        raise NotImplementedError

    def visit_predicate_has_attr(
        self, node: PredHasAttr, ctx: ConverterContext
    ) -> VisitStream:
        attrs = node.attrs
        if len(attrs) == 1:
            cond = f"{attrs[0]!r} in i.attributes"
        else:
            cond = f"any(attr in i.attributes for attr in {attrs!r})"
        yield self._pred_line(ctx, cond)

    def visit_predicate_attr_eq(
        self, node: PredAttrEq, ctx: ConverterContext
    ) -> VisitStream:
        name = node.name
        values = node.values
        if len(values) == 1:
            cond = f"i.attributes.get({name!r}, '') == {values[0]!r}"
        else:
            cond = f"i.attributes.get({name!r}, '') in {values!r}"
        yield self._pred_line(ctx, cond)

    def visit_predicate_attr_ne(
        self, node: PredAttrNe, ctx: ConverterContext
    ) -> VisitStream:
        name = node.name
        values = node.values
        if len(values) == 1:
            cond = f"i.attributes.get({name!r}, '') != {values[0]!r}"
        else:
            cond = f"i.attributes.get({name!r}, '') not in {values!r}"
        yield self._pred_line(ctx, cond)

    def visit_predicate_attr_starts(
        self, node: PredAttrStarts, ctx: ConverterContext
    ) -> VisitStream:
        name = node.name
        values = node.values
        if len(values) == 1:
            cond = f"i.attributes.get({name!r}, '').startswith({values[0]!r})"
        else:
            cond = f"any(i.attributes.get({name!r}, '').startswith(v) for v in {values!r})"
        yield self._pred_line(ctx, cond)

    def visit_predicate_attr_ends(
        self, node: PredAttrEnds, ctx: ConverterContext
    ) -> VisitStream:
        name = node.name
        values = node.values
        if len(values) == 1:
            cond = f"i.attributes.get({name!r}, '').endswith({values[0]!r})"
        else:
            cond = f"any(i.attributes.get({name!r}, '').endswith(v) for v in {values!r})"
        yield self._pred_line(ctx, cond)

    def visit_predicate_attr_contains(
        self, node: PredAttrContains, ctx: ConverterContext
    ) -> VisitStream:
        name = node.name
        values = node.values
        if len(values) == 1:
            cond = f"{values[0]!r} in i.attributes.get({name!r}, '')"
        else:
            cond = (
                f"any(v in i.attributes.get({name!r}, '') for v in {values!r})"
            )
        yield self._pred_line(ctx, cond)

    def visit_predicate_attr_re(
        self, node: PredAttrRe, ctx: ConverterContext
    ) -> VisitStream:
        name = node.name
        pat = repr(node.pattern)
        yield self._pred_line(
            ctx, f"bool(re.search({pat}, i.attributes.get({name!r}, '')))"
        )

    def visit_predicate_text_contains(
        self, node: PredTextContains, ctx: ConverterContext
    ) -> VisitStream:
        values = node.values
        if len(values) == 1:
            cond = f"{values[0]!r} in i.text()"
        else:
            cond = f"any(v in i.text() for v in {values!r})"
        yield self._pred_line(ctx, cond)

    def visit_predicate_text_starts(
        self, node: PredTextStarts, ctx: ConverterContext
    ) -> VisitStream:
        values = node.values
        if len(values) == 1:
            cond = f"i.text().startswith({values[0]!r})"
        else:
            cond = f"any(i.text().startswith(v) for v in {values!r})"
        yield self._pred_line(ctx, cond)

    def visit_predicate_text_ends(
        self, node: PredTextEnds, ctx: ConverterContext
    ) -> VisitStream:
        values = node.values
        if len(values) == 1:
            cond = f"i.text().endswith({values[0]!r})"
        else:
            cond = f"any(i.text().endswith(v) for v in {values!r})"
        yield self._pred_line(ctx, cond)

    def visit_predicate_text_re(
        self, node: PredTextRe, ctx: ConverterContext
    ) -> VisitStream:
        pat = repr(node.pattern)
        yield self._pred_line(ctx, f"bool(re.search({pat}, i.text()))")


PY_SLAX_CONVERTER = PySlax()
