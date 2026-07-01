"""Python BeautifulSoup4 dialect (new Visitor API).

The dialect-agnostic codegen lives in ``PyHtmlBase`` (py_base.py); this module
only sets the bs4 config attributes and overrides the handful of expression
methods whose spelling genuinely differs across parser libraries (selectors,
text/raw/attr extraction, to_bool, document/attr/text predicates).

Std helpers are declared co-located with their caller via ``STD(name, code=,
imports=)``. Trivial one-liners are inlined directly; multi-statement helpers
(multi-query select, repl_map, unescape) use ``STD()`` so they dedupe and can
be extracted via ``-R``.
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


class PyBs4(PyHtmlBase):
    """BeautifulSoup4 dialect."""

    STD_MODULE_NAME = "ssc_std"

    PARSER_IMPORTS = ("from bs4 import BeautifulSoup, ResultSet, Tag",)
    DOCUMENT_TYPE = "Union[Tag, BeautifulSoup]"
    DOCUMENT_ARRAY_TYPE = "ResultSet[Tag]"
    INIT_ARG_TYPE = "Union[str, BeautifulSoup, Tag]"
    INIT_FROM_STR_EXPR = "BeautifulSoup(document, features=BS4_FEATURES)"
    EXTRA_UTILITIES = ("BS4_FEATURES = 'lxml'", "")

    # === selectors ===

    def visit_css_select(
        self, node: CssSelect, ctx: ConverterContext
    ) -> VisitStream:
        if len(node.queries) == 1:
            q = repr(node.queries[0])
            yield f"{ctx.indent}{ctx.nxt} = {ctx.prv}.select_one({q})"
        else:
            yield STD(
                "std_select_first",
                code="""
                    def std_select_first(tag, *queries):
                        for q in queries:
                            t = tag.select_one(q)
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
            yield f"{ctx.indent}{ctx.nxt} = {ctx.prv}.select({q})"
        else:
            yield STD(
                "std_select_all_first",
                code="""
                    def std_select_all_first(tag, *queries):
                        result = []
                        for q in queries:
                            result = tag.select(q)
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
        yield STD(
            "std_select_remove",
            code="""
                def std_select_remove(tag, q):
                    [_el.decompose() for _el in tag.select(q)]
                    return tag
        """,
        )
        yield f"{ctx.indent}{ctx.nxt} = std_select_remove({ctx.prv}, {q})"

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
            yield f"{ctx.indent}{ctx.nxt} = [i.text for i in {ctx.prv}]"
        else:
            yield f"{ctx.indent}{ctx.nxt} = {ctx.prv}.text"

    def visit_raw(self, node: Raw, ctx: ConverterContext) -> VisitStream:
        if node.accept_type_info.is_array:
            yield f"{ctx.indent}{ctx.nxt} = [str(i) for i in {ctx.prv}]"
        else:
            yield f"{ctx.indent}{ctx.nxt} = str({ctx.prv})"

    def visit_attr(self, node: Attr, ctx: ConverterContext) -> VisitStream:
        is_arr = node.accept_type_info.is_array
        if not is_arr:
            if len(node.keys) == 1:
                k = repr(node.keys[0])
                yield f"{ctx.indent}{ctx.nxt} = ' '.join({ctx.prv}.get_attribute_list({k}))"
            else:
                keys = repr(node.keys)
                yield f"{ctx.indent}{ctx.nxt} = [' '.join({ctx.prv}.get_attribute_list(k)) for k in {keys} if {ctx.prv}.get(k)]"
        else:
            if len(node.keys) == 1:
                k = repr(node.keys[0])
                yield f"{ctx.indent}{ctx.nxt} = [' '.join(i.get_attribute_list({k})) for i in {ctx.prv} if i.get({k})]"
            else:
                keys = repr(node.keys)
                yield f"{ctx.indent}{ctx.nxt} = [' '.join(i.get_attribute_list(k)) for i in {ctx.prv} for k in {keys} if i.get(k)]"

    # === casts (bs4-specific) ===

    def visit_to_bool(self, node: ToBool, ctx: ConverterContext) -> VisitStream:
        if node.accept_type_info.is_array:
            yield f"{ctx.indent}{ctx.nxt} = len({ctx.prv}) > 0"
        else:
            yield (
                f"{ctx.indent}{ctx.nxt} = not ({ctx.prv} is None or {ctx.prv} == '' "
                f"or (type({ctx.prv}) is int and {ctx.prv} == 0))"
            )

    # === document / attr / text predicates (bs4 spellings) ===

    def visit_predicate_css(
        self, node: PredCss, ctx: ConverterContext
    ) -> VisitStream:
        query = repr(node.query)
        yield self._pred_line(ctx, f"i.select_one({query})")

    def visit_predicate_xpath(
        self, node: PredXpath, ctx: ConverterContext
    ) -> VisitStream:
        raise NotImplementedError

    def visit_predicate_has_attr(
        self, node: PredHasAttr, ctx: ConverterContext
    ) -> VisitStream:
        keys = node.attrs
        if len(keys) == 1:
            cond = f"bool(i.get({keys[0]!r}, False))"
        else:
            cond = f"any(bool(i.get(k, False)) for k in {keys!r})"
        yield self._pred_line(ctx, cond)

    def visit_predicate_attr_contains(
        self, node: PredAttrContains, ctx: ConverterContext
    ) -> VisitStream:
        key = node.name
        vals = repr(node.values)
        cond = f"bool(i.get({key!r})) and any(v in ' '.join(i.get_attribute_list({key!r})) for v in {vals})"
        yield self._pred_line(ctx, cond)

    def visit_predicate_attr_starts(
        self, node: PredAttrStarts, ctx: ConverterContext
    ) -> VisitStream:
        key = node.name
        vals = repr(node.values)
        cond = f"bool(i.get({key!r})) and any(' '.join(i.get_attribute_list({key!r})).startswith(v) for v in {vals})"
        yield self._pred_line(ctx, cond)

    def visit_predicate_attr_ends(
        self, node: PredAttrEnds, ctx: ConverterContext
    ) -> VisitStream:
        key = node.name
        vals = repr(node.values)
        cond = f"bool(i.get({key!r})) and any(' '.join(i.get_attribute_list({key!r})).endswith(v) for v in {vals})"
        yield self._pred_line(ctx, cond)

    def visit_predicate_attr_eq(
        self, node: PredAttrEq, ctx: ConverterContext
    ) -> VisitStream:
        key = node.name
        vals = repr(node.values)
        cond = (
            f"bool(i.get({key!r})) and any(v == i.get({key!r}) for v in {vals})"
        )
        yield self._pred_line(ctx, cond)

    def visit_predicate_attr_ne(
        self, node: PredAttrNe, ctx: ConverterContext
    ) -> VisitStream:
        key = node.name
        vals = repr(node.values)
        cond = (
            f"bool(i.get({key!r})) and all(v != i.get({key!r}) for v in {vals})"
        )
        yield self._pred_line(ctx, cond)

    def visit_predicate_attr_re(
        self, node: PredAttrRe, ctx: ConverterContext
    ) -> VisitStream:
        key = node.name
        pat = repr(node.pattern)
        cond = (
            f"bool(i.get({key!r})) and bool(re.search({pat}, i.get({key!r})))"
        )
        yield self._pred_line(ctx, cond)

    def visit_predicate_text_contains(
        self, node: PredTextContains, ctx: ConverterContext
    ) -> VisitStream:
        vals = repr(node.values)
        yield self._pred_line(ctx, f"any(v in i.text for v in {vals})")

    def visit_predicate_text_starts(
        self, node: PredTextStarts, ctx: ConverterContext
    ) -> VisitStream:
        vals = repr(node.values)
        yield self._pred_line(ctx, f"i.text.startswith({vals})")

    def visit_predicate_text_ends(
        self, node: PredTextEnds, ctx: ConverterContext
    ) -> VisitStream:
        vals = repr(node.values)
        yield self._pred_line(ctx, f"i.text.endswith({vals})")

    def visit_predicate_text_re(
        self, node: PredTextRe, ctx: ConverterContext
    ) -> VisitStream:
        pat = repr(node.pattern)
        yield self._pred_line(ctx, f"bool(re.search({pat}, i.text))")


PY_BASE_CONVERTER = PyBs4()
