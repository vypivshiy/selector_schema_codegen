from __future__ import annotations

from abc import ABC, abstractmethod

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
from ssc_codegen.generation.builder import ModuleBuilder


class DomSpelling(ABC):
    """Dialect-specific HTML extraction spelling (data + behavior).

    Holds a builder reference for registering std helpers and imports.

    Contract:
        - Expression methods return ``list[str]`` (complete codegen lines).
        - Predicate methods return ``str`` (condition fragment; the visitor
          wraps with ``_pred_line`` to produce the final formatted line).
    """

    def __init__(self, builder: ModuleBuilder) -> None:
        self._builder = builder

    @property
    def builder(self) -> ModuleBuilder:
        """Access the module builder for registering imports / std helpers."""
        return self._builder

    # === DATA (override in concrete subclasses) ===

    parser_imports: tuple[str, ...] = ()
    document_type: str = "Any"
    document_array_type: str = "List[Any]"
    init_arg_type: str = "Any"
    init_from_str_expr: str = "document"
    extra_utilities: tuple[str, ...] = ()
    supports_xpath: bool = False

    # === EXPRESSION BEHAVIOR (return list[str] — complete lines) ===

    @abstractmethod
    def css_select(
        self, ctx: ConverterContext, node: CssSelect
    ) -> list[str]: ...

    @abstractmethod
    def css_select_all(
        self, ctx: ConverterContext, node: CssSelectAll
    ) -> list[str]: ...

    @abstractmethod
    def css_remove(
        self, ctx: ConverterContext, node: CssRemove
    ) -> list[str]: ...

    @abstractmethod
    def xpath_select(
        self, ctx: ConverterContext, node: XpathSelect
    ) -> list[str]: ...

    @abstractmethod
    def xpath_select_all(
        self, ctx: ConverterContext, node: XpathSelectAll
    ) -> list[str]: ...

    @abstractmethod
    def xpath_remove(
        self, ctx: ConverterContext, node: XpathRemove
    ) -> list[str]: ...

    @abstractmethod
    def text(self, ctx: ConverterContext, node: Text) -> list[str]: ...

    @abstractmethod
    def raw(self, ctx: ConverterContext, node: Raw) -> list[str]: ...

    @abstractmethod
    def attr(self, ctx: ConverterContext, node: Attr) -> list[str]: ...

    @abstractmethod
    def to_bool(self, ctx: ConverterContext, node: ToBool) -> list[str]: ...

    # === PREDICATE BEHAVIOR (return str — condition fragment) ===

    @abstractmethod
    def pred_css(self, node: PredCss) -> str: ...

    @abstractmethod
    def pred_xpath(self, node: PredXpath) -> str: ...

    @abstractmethod
    def pred_has_attr(self, node: PredHasAttr) -> str: ...

    @abstractmethod
    def pred_attr_contains(self, node: PredAttrContains) -> str: ...

    @abstractmethod
    def pred_attr_starts(self, node: PredAttrStarts) -> str: ...

    @abstractmethod
    def pred_attr_ends(self, node: PredAttrEnds) -> str: ...

    @abstractmethod
    def pred_attr_eq(self, node: PredAttrEq) -> str: ...

    @abstractmethod
    def pred_attr_ne(self, node: PredAttrNe) -> str: ...

    @abstractmethod
    def pred_attr_re(self, node: PredAttrRe) -> str: ...

    @abstractmethod
    def pred_text_contains(self, node: PredTextContains) -> str: ...

    @abstractmethod
    def pred_text_starts(self, node: PredTextStarts) -> str: ...

    @abstractmethod
    def pred_text_ends(self, node: PredTextEnds) -> str: ...

    @abstractmethod
    def pred_text_re(self, node: PredTextRe) -> str: ...
