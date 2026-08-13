from __future__ import annotations

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
from ssc_codegen.traversal.context import WalkContext as ConverterContext
from ssc_codegen.targets.python.html_libs.base import DomSpelling


class ParselDomSpelling(DomSpelling):
    """parsel.Selector DOM extraction spelling."""

    # === DATA ===
    parser_imports = ("from parsel import Selector, SelectorList",)
    document_type = "Selector"
    document_array_type = "SelectorList"
    init_arg_type = "Union[str, Selector, SelectorList]"
    init_from_str_expr = "Selector(document)"
    extra_utilities: tuple[str, ...] = ()
    supports_xpath = True

    # === EXPRESSIONS ===

    def css_select(self, ctx: ConverterContext, node: CssSelect) -> list[str]:
        if len(node.queries) == 1:
            q = repr(node.queries[0])
            return [f"{ctx.indent}{ctx.nxt} = {ctx.prv}.css({q})[0]"]
        self._builder.require_std(
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
        return [f"{ctx.indent}{ctx.nxt} = std_select_first({ctx.prv}, {args})"]

    def css_select_all(
        self, ctx: ConverterContext, node: CssSelectAll
    ) -> list[str]:
        if len(node.queries) == 1:
            q = repr(node.queries[0])
            return [f"{ctx.indent}{ctx.nxt} = {ctx.prv}.css({q})"]
        self._builder.require_std(
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
        return [
            f"{ctx.indent}{ctx.nxt} = std_select_all_first({ctx.prv}, {args})"
        ]

    def css_remove(self, ctx: ConverterContext, node: CssRemove) -> list[str]:
        q = repr(node.query)
        self._builder.require_std(
            "std_select_remove",
            code="""
                def std_select_remove(tag, q):
                    [e.root.getparent().remove(e.root) for e in tag.css(q) if e.root.getparent() is not None]
                    return tag
            """,
        )
        return [f"{ctx.indent}{ctx.nxt} = std_select_remove({ctx.prv}, {q})"]

    def xpath_select(
        self, ctx: ConverterContext, node: XpathSelect
    ) -> list[str]:
        if len(node.queries) == 1:
            q = repr(node.queries[0])
            return [f"{ctx.indent}{ctx.nxt} = {ctx.prv}.xpath({q})[0]"]
        self._builder.require_std(
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
        return [f"{ctx.indent}{ctx.nxt} = std_xpath_first({ctx.prv}, {args})"]

    def xpath_select_all(
        self, ctx: ConverterContext, node: XpathSelectAll
    ) -> list[str]:
        if len(node.queries) == 1:
            q = repr(node.queries[0])
            return [f"{ctx.indent}{ctx.nxt} = {ctx.prv}.xpath({q})"]
        self._builder.require_std(
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
        return [
            f"{ctx.indent}{ctx.nxt} = std_xpath_all_first({ctx.prv}, {args})"
        ]

    def xpath_remove(
        self, ctx: ConverterContext, node: XpathRemove
    ) -> list[str]:
        q = repr(node.query)
        self._builder.require_std(
            "std_xpath_remove",
            code="""
                def std_xpath_remove(tag, q):
                    [e.root.getparent().remove(e.root) for e in tag.xpath(q) if e.root.getparent() is not None]
                    return tag
            """,
        )
        return [f"{ctx.indent}{ctx.nxt} = std_xpath_remove({ctx.prv}, {q})"]

    def text(self, ctx: ConverterContext, node: Text) -> list[str]:
        if node.accept_type_info.is_array:
            return [
                f"{ctx.indent}{ctx.nxt} = [' '.join(i.xpath('.//text()').getall()) for i in {ctx.prv}]"
            ]
        return [
            f"{ctx.indent}{ctx.nxt} = ' '.join({ctx.prv}.xpath('.//text()').getall())"
        ]

    def raw(self, ctx: ConverterContext, node: Raw) -> list[str]:
        if node.mode == "inner":
            if node.accept_type_info.is_array:
                return [
                    f"{ctx.indent}{ctx.nxt} = [''.join(i.xpath('node()').getall()) for i in {ctx.prv}]"
                ]
            return [
                f"{ctx.indent}{ctx.nxt} = ''.join({ctx.prv}.xpath('node()').getall())"
            ]
        if node.accept_type_info.is_array:
            return [f"{ctx.indent}{ctx.nxt} = {ctx.prv}.getall()"]
        return [f"{ctx.indent}{ctx.nxt} = {ctx.prv}.get()"]

    def attr(self, ctx: ConverterContext, node: Attr) -> list[str]:
        keys = node.keys
        if not node.accept_type_info.is_array:
            if len(keys) == 1:
                return [
                    f"{ctx.indent}{ctx.nxt} = {ctx.prv}.attrib[{keys[0]!r}]"
                ]
            return [
                f"{ctx.indent}{ctx.nxt} = [{ctx.prv}.attrib[k] for k in {keys!r} if {ctx.prv}.attrib.get(k)]"
            ]
        if len(keys) == 1:
            return [
                f"{ctx.indent}{ctx.nxt} = [e.attrib[{keys[0]!r}] for e in {ctx.prv}]"
            ]
        return [
            f"{ctx.indent}{ctx.nxt} = [e.attrib[k] for e in {ctx.prv} for k in {keys!r} if e.attrib.get(k)]"
        ]

    def to_bool(self, ctx: ConverterContext, node: ToBool) -> list[str]:
        return [f"{ctx.indent}{ctx.nxt} = bool({ctx.prv})"]

    # === PREDICATES ===

    def pred_css(self, node: PredCss) -> str:
        query = repr(node.query)
        return f"bool(i.css({query}))"

    def pred_xpath(self, node: PredXpath) -> str:
        query = repr(node.query)
        return f"bool(i.xpath({query}))"

    def pred_has_attr(self, node: PredHasAttr) -> str:
        attrs = node.attrs
        if len(attrs) == 1:
            return f"{attrs[0]!r} in i.attrib"
        return f"any(attr in i.attrib for attr in {attrs!r})"

    def pred_attr_eq(self, node: PredAttrEq) -> str:
        name = node.name
        values = node.values
        if len(values) == 1:
            return f"i.attrib.get({name!r}, '') == {values[0]!r}"
        return f"i.attrib.get({name!r}, '') in {values!r}"

    def pred_attr_ne(self, node: PredAttrNe) -> str:
        name = node.name
        values = node.values
        if len(values) == 1:
            return f"i.attrib.get({name!r}, '') != {values[0]!r}"
        return f"i.attrib.get({name!r}, '') not in {values!r}"

    def pred_attr_starts(self, node: PredAttrStarts) -> str:
        name = node.name
        values = node.values
        if len(values) == 1:
            return f"i.attrib.get({name!r}, '').startswith({values[0]!r})"
        return (
            f"any(i.attrib.get({name!r}, '').startswith(v) for v in {values!r})"
        )

    def pred_attr_ends(self, node: PredAttrEnds) -> str:
        name = node.name
        values = node.values
        if len(values) == 1:
            return f"i.attrib.get({name!r}, '').endswith({values[0]!r})"
        return (
            f"any(i.attrib.get({name!r}, '').endswith(v) for v in {values!r})"
        )

    def pred_attr_contains(self, node: PredAttrContains) -> str:
        name = node.name
        values = node.values
        if len(values) == 1:
            return f"{values[0]!r} in i.attrib.get({name!r}, '')"
        return f"any(v in i.attrib.get({name!r}, '') for v in {values!r})"

    def pred_attr_re(self, node: PredAttrRe) -> str:
        name = node.name
        pat = repr(node.pattern)
        return f"bool(re.search({pat}, i.attrib.get({name!r}, '')))"

    def pred_text_contains(self, node: PredTextContains) -> str:
        values = node.values
        if len(values) == 1:
            return f"{values[0]!r} in ' '.join(i.xpath('.//text()').getall())"
        return f"any(v in ' '.join(i.xpath('.//text()').getall()) for v in {values!r})"

    def pred_text_starts(self, node: PredTextStarts) -> str:
        values = node.values
        if len(values) == 1:
            return f"' '.join(i.xpath('.//text()').getall()).startswith({values[0]!r})"
        return f"any(' '.join(i.xpath('.//text()').getall()).startswith(v) for v in {values!r})"

    def pred_text_ends(self, node: PredTextEnds) -> str:
        values = node.values
        if len(values) == 1:
            return f"' '.join(i.xpath('.//text()').getall()).endswith({values[0]!r})"
        return f"any(' '.join(i.xpath('.//text()').getall()).endswith(v) for v in {values!r})"

    def pred_text_re(self, node: PredTextRe) -> str:
        pat = repr(node.pattern)
        return (
            f"bool(re.search({pat}, ' '.join(i.xpath('.//text()').getall())))"
        )
