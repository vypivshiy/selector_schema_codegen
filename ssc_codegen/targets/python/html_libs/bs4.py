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


class Bs4DomSpelling(DomSpelling):
    """BeautifulSoup4 DOM extraction spelling."""

    # === DATA ===
    parser_imports = ("from bs4 import BeautifulSoup, ResultSet, Tag",)
    document_type = "Union[Tag, BeautifulSoup]"
    document_array_type = "ResultSet[Tag]"
    init_arg_type = "Union[str, BeautifulSoup, Tag]"
    init_from_str_expr = "BeautifulSoup(document, features=BS4_FEATURES)"
    extra_utilities = ("BS4_FEATURES = 'lxml'", "")
    supports_xpath = False

    # === EXPRESSIONS ===

    def css_select(self, ctx: ConverterContext, node: CssSelect) -> list[str]:
        if len(node.queries) == 1:
            q = repr(node.queries[0])
            return [f"{ctx.indent}{ctx.nxt} = {ctx.prv}.select_one({q})"]
        self._builder.require_std(
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
        return [f"{ctx.indent}{ctx.nxt} = std_select_first({ctx.prv}, {args})"]

    def css_select_all(
        self, ctx: ConverterContext, node: CssSelectAll
    ) -> list[str]:
        if len(node.queries) == 1:
            q = repr(node.queries[0])
            return [f"{ctx.indent}{ctx.nxt} = {ctx.prv}.select({q})"]
        self._builder.require_std(
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
        return [
            f"{ctx.indent}{ctx.nxt} = std_select_all_first({ctx.prv}, {args})"
        ]

    def css_remove(self, ctx: ConverterContext, node: CssRemove) -> list[str]:
        q = repr(node.query)
        self._builder.require_std(
            "std_select_remove",
            code="""
                def std_select_remove(tag, q):
                    [_el.decompose() for _el in tag.select(q)]
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
            return [f"{ctx.indent}{ctx.nxt} = [i.text for i in {ctx.prv}]"]
        return [f"{ctx.indent}{ctx.nxt} = {ctx.prv}.text"]

    def raw(self, ctx: ConverterContext, node: Raw) -> list[str]:
        if node.mode == "inner":
            if node.accept_type_info.is_array:
                return [
                    f"{ctx.indent}{ctx.nxt} = [i.decode_contents() for i in {ctx.prv}]"
                ]
            return [f"{ctx.indent}{ctx.nxt} = {ctx.prv}.decode_contents()"]
        if node.accept_type_info.is_array:
            return [f"{ctx.indent}{ctx.nxt} = [str(i) for i in {ctx.prv}]"]
        return [f"{ctx.indent}{ctx.nxt} = str({ctx.prv})"]

    def attr(self, ctx: ConverterContext, node: Attr) -> list[str]:
        is_arr = node.accept_type_info.is_array
        if not is_arr:
            if len(node.keys) == 1:
                k = repr(node.keys[0])
                return [
                    f"{ctx.indent}{ctx.nxt} = ' '.join({ctx.prv}.get_attribute_list({k}))"
                ]
            keys = repr(node.keys)
            return [
                f"{ctx.indent}{ctx.nxt} = [' '.join({ctx.prv}.get_attribute_list(k)) for k in {keys} if {ctx.prv}.get(k)]"
            ]
        if len(node.keys) == 1:
            k = repr(node.keys[0])
            return [
                f"{ctx.indent}{ctx.nxt} = [' '.join(i.get_attribute_list({k})) for i in {ctx.prv} if i.get({k})]"
            ]
        keys = repr(node.keys)
        return [
            f"{ctx.indent}{ctx.nxt} = [' '.join(i.get_attribute_list(k)) for i in {ctx.prv} for k in {keys} if i.get(k)]"
        ]

    def to_bool(self, ctx: ConverterContext, node: ToBool) -> list[str]:
        if node.accept_type_info.is_array:
            return [f"{ctx.indent}{ctx.nxt} = len({ctx.prv}) > 0"]
        return [
            f"{ctx.indent}{ctx.nxt} = not ({ctx.prv} is None or {ctx.prv} == '' "
            f"or (type({ctx.prv}) is int and {ctx.prv} == 0))"
        ]

    # === PREDICATES ===

    def pred_css(self, node: PredCss) -> str:
        query = repr(node.query)
        return f"i.select_one({query})"

    def pred_xpath(self, node: PredXpath) -> str:
        raise NotImplementedError

    def pred_has_attr(self, node: PredHasAttr) -> str:
        keys = node.attrs
        if len(keys) == 1:
            return f"bool(i.get({keys[0]!r}, False))"
        return f"any(bool(i.get(k, False)) for k in {keys!r})"

    def pred_attr_contains(self, node: PredAttrContains) -> str:
        key = node.name
        vals = repr(node.values)
        return f"bool(i.get({key!r})) and any(v in ' '.join(i.get_attribute_list({key!r})) for v in {vals})"

    def pred_attr_starts(self, node: PredAttrStarts) -> str:
        key = node.name
        vals = repr(node.values)
        return f"bool(i.get({key!r})) and any(' '.join(i.get_attribute_list({key!r})).startswith(v) for v in {vals})"

    def pred_attr_ends(self, node: PredAttrEnds) -> str:
        key = node.name
        vals = repr(node.values)
        return f"bool(i.get({key!r})) and any(' '.join(i.get_attribute_list({key!r})).endswith(v) for v in {vals})"

    def pred_attr_eq(self, node: PredAttrEq) -> str:
        key = node.name
        vals = repr(node.values)
        return (
            f"bool(i.get({key!r})) and any(v == i.get({key!r}) for v in {vals})"
        )

    def pred_attr_ne(self, node: PredAttrNe) -> str:
        key = node.name
        vals = repr(node.values)
        return (
            f"bool(i.get({key!r})) and all(v != i.get({key!r}) for v in {vals})"
        )

    def pred_attr_re(self, node: PredAttrRe) -> str:
        key = node.name
        pat = repr(node.pattern)
        return (
            f"bool(i.get({key!r})) and bool(re.search({pat}, i.get({key!r})))"
        )

    def pred_text_contains(self, node: PredTextContains) -> str:
        vals = repr(node.values)
        return f"any(v in i.text for v in {vals})"

    def pred_text_starts(self, node: PredTextStarts) -> str:
        vals = repr(node.values)
        return f"i.text.startswith({vals})"

    def pred_text_ends(self, node: PredTextEnds) -> str:
        vals = repr(node.values)
        return f"i.text.endswith({vals})"

    def pred_text_re(self, node: PredTextRe) -> str:
        pat = repr(node.pattern)
        return f"bool(re.search({pat}, i.text))"
