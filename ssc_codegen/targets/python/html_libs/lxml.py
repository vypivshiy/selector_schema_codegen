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


class LxmlDomSpelling(DomSpelling):
    """lxml.html DOM extraction spelling."""

    # === DATA ===
    parser_imports = (
        "from lxml import html",
        "from lxml.html import HtmlElement",
    )
    document_type = "HtmlElement"
    document_array_type = "List[HtmlElement]"
    init_arg_type = "Union[str, HtmlElement]"
    init_from_str_expr = (
        "html.fromstring(document.strip() or FALLBACK_HTML_STR)"
    )
    extra_utilities = (
        'FALLBACK_HTML_STR = "<html><body></body></html>"',
        "",
    )
    supports_xpath = True

    # === EXPRESSIONS ===

    def css_select(self, ctx: ConverterContext, node: CssSelect) -> list[str]:
        if len(node.queries) == 1:
            q = repr(node.queries[0])
            return [f"{ctx.indent}{ctx.nxt} = {ctx.prv}.cssselect({q})[0]"]
        self._builder.require_std(
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
        return [f"{ctx.indent}{ctx.nxt} = std_select_first({ctx.prv}, {args})"]

    def css_select_all(
        self, ctx: ConverterContext, node: CssSelectAll
    ) -> list[str]:
        if len(node.queries) == 1:
            q = repr(node.queries[0])
            return [f"{ctx.indent}{ctx.nxt} = {ctx.prv}.cssselect({q})"]
        self._builder.require_std(
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
        return [
            f"{ctx.indent}{ctx.nxt} = std_select_all_first({ctx.prv}, {args})"
        ]

    def css_remove(self, ctx: ConverterContext, node: CssRemove) -> list[str]:
        q = repr(node.query)
        self._builder.require_std(
            "std_select_remove",
            code="""
                def std_select_remove(tag, q):
                    [_el.getparent().remove(_el) for _el in tag.cssselect(q) if _el.getparent() is not None]
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
                    [_el.getparent().remove(_el) for _el in tag.xpath(q) if _el.getparent() is not None]
                    return tag
            """,
        )
        return [f"{ctx.indent}{ctx.nxt} = std_xpath_remove({ctx.prv}, {q})"]

    def text(self, ctx: ConverterContext, node: Text) -> list[str]:
        if node.accept_type_info.is_array:
            return [
                f"{ctx.indent}{ctx.nxt} = [i.text_content() for i in {ctx.prv}]"
            ]
        return [f"{ctx.indent}{ctx.nxt} = {ctx.prv}.text_content()"]

    def raw(self, ctx: ConverterContext, node: Raw) -> list[str]:
        if node.mode == "inner":
            self._builder.require_std(
                "std_inner_html",
                code="""
                    def std_inner_html(el):
                        parts = [el.text or ""]
                        for child in el.iterchildren():
                            parts.append(html.tostring(child, encoding="unicode"))
                        return "".join(parts)
                """,
            )
            if node.accept_type_info.is_array:
                return [
                    f"{ctx.indent}{ctx.nxt} = [std_inner_html(i) for i in {ctx.prv}]"
                ]
            return [f"{ctx.indent}{ctx.nxt} = std_inner_html({ctx.prv})"]
        if node.accept_type_info.is_array:
            return [
                f"{ctx.indent}{ctx.nxt} = [html.tostring(i, encoding='unicode') for i in {ctx.prv}]"
            ]
        return [
            f"{ctx.indent}{ctx.nxt} = html.tostring({ctx.prv}, encoding='unicode')"
        ]

    def attr(self, ctx: ConverterContext, node: Attr) -> list[str]:
        keys = node.keys
        if not node.accept_type_info.is_array:
            if len(keys) == 1:
                return [
                    f"{ctx.indent}{ctx.nxt} = {ctx.prv}.get({keys[0]!r}, '')"
                ]
            return [
                f"{ctx.indent}{ctx.nxt} = [{ctx.prv}.get(k) for k in {keys!r} if {ctx.prv}.get(k)]"
            ]
        if len(keys) == 1:
            return [
                f"{ctx.indent}{ctx.nxt} = [i.get({keys[0]!r}, '') for i in {ctx.prv}]"
            ]
        return [
            f"{ctx.indent}{ctx.nxt} = [i.get(k) for i in {ctx.prv} for k in {keys!r} if i.get(k)]"
        ]

    def to_bool(self, ctx: ConverterContext, node: ToBool) -> list[str]:
        if node.accept_type_info.is_array:
            return [f"{ctx.indent}{ctx.nxt} = len({ctx.prv}) > 0"]
        return [
            f"{ctx.indent}{ctx.nxt} = {ctx.prv} is not None or {ctx.prv} != '' or {ctx.prv} != 0"
        ]

    # === PREDICATES ===

    def pred_css(self, node: PredCss) -> str:
        query = repr(node.query)
        return f"bool(i.cssselect({query}))"

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
            return f"i.get({name!r}, '') == {values[0]!r}"
        return f"i.get({name!r}, '') in {values!r}"

    def pred_attr_ne(self, node: PredAttrNe) -> str:
        name = node.name
        values = node.values
        if len(values) == 1:
            return f"i.get({name!r}, '') != {values[0]!r}"
        return f"i.get({name!r}, '') not in {values!r}"

    def pred_attr_starts(self, node: PredAttrStarts) -> str:
        name = node.name
        values = node.values
        if len(values) == 1:
            return f"i.get({name!r}, '').startswith({values[0]!r})"
        return f"any(i.get({name!r}, '').startswith(v) for v in {values!r})"

    def pred_attr_ends(self, node: PredAttrEnds) -> str:
        name = node.name
        values = node.values
        if len(values) == 1:
            return f"i.get({name!r}, '').endswith({values[0]!r})"
        return f"any(i.get({name!r}, '').endswith(v) for v in {values!r})"

    def pred_attr_contains(self, node: PredAttrContains) -> str:
        name = node.name
        values = node.values
        if len(values) == 1:
            return f"{values[0]!r} in i.get({name!r}, '')"
        return f"any(v in i.get({name!r}, '') for v in {values!r})"

    def pred_attr_re(self, node: PredAttrRe) -> str:
        name = node.name
        pat = repr(node.pattern)
        return f"bool(re.search({pat}, i.get({name!r}, '')))"

    def pred_text_contains(self, node: PredTextContains) -> str:
        values = node.values
        if len(values) == 1:
            return f"{values[0]!r} in i.text_content()"
        return f"any(v in i.text_content() for v in {values!r})"

    def pred_text_starts(self, node: PredTextStarts) -> str:
        values = node.values
        if len(values) == 1:
            return f"i.text_content().startswith({values[0]!r})"
        return f"any(i.text_content().startswith(v) for v in {values!r})"

    def pred_text_ends(self, node: PredTextEnds) -> str:
        values = node.values
        if len(values) == 1:
            return f"i.text_content().endswith({values[0]!r})"
        return f"any(i.text_content().endswith(v) for v in {values!r})"

    def pred_text_re(self, node: PredTextRe) -> str:
        pat = repr(node.pattern)
        return f"bool(re.search({pat}, i.text_content()))"
