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


class SlaxDomSpelling(DomSpelling):
    """selectolax.lexbor DOM extraction spelling."""

    # === DATA ===
    parser_imports = (
        "from selectolax.lexbor import "
        "LexborHTMLParser as HTMLParser, LexborNode as Node",
    )
    document_type = "Node"
    document_array_type = "List[Node]"
    init_arg_type = "Union[str, HTMLParser, Node]"
    init_from_str_expr = "HTMLParser(document)"
    extra_utilities: tuple[str, ...] = ()
    supports_xpath = False

    # === EXPRESSIONS ===

    def css_select(self, ctx: ConverterContext, node: CssSelect) -> list[str]:
        if len(node.queries) == 1:
            q = repr(node.queries[0])
            return [f"{ctx.indent}{ctx.nxt} = {ctx.prv}.css_first({q})"]
        self._builder.require_std(
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
                    result = []
                    for q in queries:
                        result = tag.css(q)
                        if result:
                            return result
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
                    [e.decompose() for e in tag.css(q)]
                    return tag
            """,
        )
        return [f"{ctx.indent}{ctx.nxt} = std_select_remove({ctx.prv}, {q})"]

    def xpath_select(
        self, ctx: ConverterContext, node: XpathSelect
    ) -> list[str]:
        raise NotImplementedError

    def xpath_select_all(
        self, ctx: ConverterContext, node: XpathSelectAll
    ) -> list[str]:
        raise NotImplementedError

    def xpath_remove(
        self, ctx: ConverterContext, node: XpathRemove
    ) -> list[str]:
        raise NotImplementedError

    def text(self, ctx: ConverterContext, node: Text) -> list[str]:
        if node.accept_type_info.is_array:
            return [f"{ctx.indent}{ctx.nxt} = [i.text() for i in {ctx.prv}]"]
        return [f"{ctx.indent}{ctx.nxt} = {ctx.prv}.text()"]

    def raw(self, ctx: ConverterContext, node: Raw) -> list[str]:
        if node.accept_type_info.is_array:
            return [f"{ctx.indent}{ctx.nxt} = [i.html for i in {ctx.prv}]"]
        return [f"{ctx.indent}{ctx.nxt} = {ctx.prv}.html"]

    def attr(self, ctx: ConverterContext, node: Attr) -> list[str]:
        keys = node.keys
        if not node.accept_type_info.is_array:
            if len(keys) == 1:
                return [
                    f"{ctx.indent}{ctx.nxt} = {ctx.prv}.attributes[{keys[0]!r}]"
                ]
            return [
                f"{ctx.indent}{ctx.nxt} = [{ctx.prv}.attributes[k] for k in {keys!r} if {ctx.prv}.attributes.get(k)]"
            ]
        if len(keys) == 1:
            return [
                f"{ctx.indent}{ctx.nxt} = [e.attributes[{keys[0]!r}] for e in {ctx.prv}]"
            ]
        return [
            f"{ctx.indent}{ctx.nxt} = [e.attributes[k] for e in {ctx.prv} for k in {keys!r} if e.attributes.get(k)]"
        ]

    def to_bool(self, ctx: ConverterContext, node: ToBool) -> list[str]:
        return [f"{ctx.indent}{ctx.nxt} = bool({ctx.prv})"]

    # === PREDICATES ===

    def pred_css(self, node: PredCss) -> str:
        query = repr(node.query)
        return f"bool(i.css_first({query}))"

    def pred_xpath(self, node: PredXpath) -> str:
        raise NotImplementedError

    def pred_has_attr(self, node: PredHasAttr) -> str:
        attrs = node.attrs
        if len(attrs) == 1:
            return f"{attrs[0]!r} in i.attributes"
        return f"any(attr in i.attributes for attr in {attrs!r})"

    def pred_attr_eq(self, node: PredAttrEq) -> str:
        name = node.name
        values = node.values
        if len(values) == 1:
            return f"i.attributes.get({name!r}, '') == {values[0]!r}"
        return f"i.attributes.get({name!r}, '') in {values!r}"

    def pred_attr_ne(self, node: PredAttrNe) -> str:
        name = node.name
        values = node.values
        if len(values) == 1:
            return f"i.attributes.get({name!r}, '') != {values[0]!r}"
        return f"i.attributes.get({name!r}, '') not in {values!r}"

    def pred_attr_starts(self, node: PredAttrStarts) -> str:
        name = node.name
        values = node.values
        if len(values) == 1:
            return f"i.attributes.get({name!r}, '').startswith({values[0]!r})"
        return f"any(i.attributes.get({name!r}, '').startswith(v) for v in {values!r})"

    def pred_attr_ends(self, node: PredAttrEnds) -> str:
        name = node.name
        values = node.values
        if len(values) == 1:
            return f"i.attributes.get({name!r}, '').endswith({values[0]!r})"
        return f"any(i.attributes.get({name!r}, '').endswith(v) for v in {values!r})"

    def pred_attr_contains(self, node: PredAttrContains) -> str:
        name = node.name
        values = node.values
        if len(values) == 1:
            return f"{values[0]!r} in i.attributes.get({name!r}, '')"
        return f"any(v in i.attributes.get({name!r}, '') for v in {values!r})"

    def pred_attr_re(self, node: PredAttrRe) -> str:
        name = node.name
        pat = repr(node.pattern)
        return f"bool(re.search({pat}, i.attributes.get({name!r}, '')))"

    def pred_text_contains(self, node: PredTextContains) -> str:
        values = node.values
        if len(values) == 1:
            return f"{values[0]!r} in i.text()"
        return f"any(v in i.text() for v in {values!r})"

    def pred_text_starts(self, node: PredTextStarts) -> str:
        values = node.values
        if len(values) == 1:
            return f"i.text().startswith({values[0]!r})"
        return f"any(i.text().startswith(v) for v in {values!r})"

    def pred_text_ends(self, node: PredTextEnds) -> str:
        values = node.values
        if len(values) == 1:
            return f"i.text().endswith({values[0]!r})"
        return f"any(i.text().endswith(v) for v in {values!r})"

    def pred_text_re(self, node: PredTextRe) -> str:
        pat = repr(node.pattern)
        return f"bool(re.search({pat}, i.text()))"
