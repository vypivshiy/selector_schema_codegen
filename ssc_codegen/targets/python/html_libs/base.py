"""Abstract base class and contract for Python HTML DOM extraction dialects."""

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
from ssc_codegen.generation.builder import ModuleBuilder
from ssc_codegen.traversal.context import WalkContext as ConverterContext


class DomSpelling(ABC):
    """Dialect-specific HTML extraction spelling strategy (data + behavior).

    Encapsulates all HTML library-specific differences (BeautifulSoup4,
    lxml.html, parsel, or selectolax/slax) so that `PythonVisitor` remains
    dialect-agnostic.

    Contract:
        - **Expression methods** return ``list[str]`` representing complete
          generated statements (e.g. ``v1 = v.select_one(...)``).
        - **Predicate methods** return ``str`` representing an unindented boolean
          condition fragment (e.g. ``bool(v.find(...))``); `PythonVisitor`
          wraps this fragment with control flow and indentation.
        - **Data attributes** declare parser imports, document type annotations,
          initialization expressions, and XPath capability flags.

    Attributes:
        parser_imports: Tuple of required top-level import statement lines.
        document_type: Type annotation string for a single parsed HTML element/document.
        document_array_type: Type annotation string for a collection of elements.
        init_arg_type: Type annotation string accepted by `__init__` (e.g. `Union[str, ...]`).
        init_extra_params: Optional keyword parameter signature fragment for `__init__`.
        init_return_type: Return type annotation for `__init__` (e.g. `" -> None"` or `""`).
        fn_extra_params: Optional keyword parameter signature fragment for function definitions.
        init_from_str_expr: Python expression parsing a string `document` into a DOM tree.
        extra_utilities: Module-level helper constants or definitions.
        supports_xpath: `True` if this DOM library supports XPath expressions natively.
    """

    def __init__(self, builder: ModuleBuilder) -> None:
        """Initialize the DOM spelling strategy with an accumulator builder.

        Args:
            builder: The `ModuleBuilder` for registering std helpers and imports.
        """
        self._builder = builder

    @property
    def builder(self) -> ModuleBuilder:
        """Access the module builder for registering imports and std helpers."""
        return self._builder

    # === DATA (override in concrete subclasses) ===

    parser_imports: tuple[str, ...] = ()
    document_type: str = "Any"
    document_array_type: str = "List[Any]"
    init_arg_type: str = "Any"
    init_extra_params: str = ""
    init_return_type: str = ""
    fn_extra_params: str = ""
    init_from_str_expr: str = "document"
    extra_utilities: tuple[str, ...] = ()
    supports_xpath: bool = False

    # === EXPRESSION BEHAVIOR (return list[str] — complete lines) ===

    @abstractmethod
    def css_select(self, ctx: ConverterContext, node: CssSelect) -> list[str]:
        """Generate code for selecting a single matching DOM node via CSS selector.

        Args:
            ctx: Current traversal context.
            node: `CssSelect` AST node.

        Returns:
            List of generated code lines.
        """
        ...

    @abstractmethod
    def css_select_all(
        self, ctx: ConverterContext, node: CssSelectAll
    ) -> list[str]:
        """Generate code for selecting all matching DOM nodes via CSS selector.

        Args:
            ctx: Current traversal context.
            node: `CssSelectAll` AST node.

        Returns:
            List of generated code lines.
        """
        ...

    @abstractmethod
    def css_remove(self, ctx: ConverterContext, node: CssRemove) -> list[str]:
        """Generate code for removing matched DOM elements in-place.

        Args:
            ctx: Current traversal context.
            node: `CssRemove` AST node.

        Returns:
            List of generated code lines.
        """
        ...

    @abstractmethod
    def xpath_select(
        self, ctx: ConverterContext, node: XpathSelect
    ) -> list[str]:
        """Generate code for selecting a single matching DOM node via XPath.

        Args:
            ctx: Current traversal context.
            node: `XpathSelect` AST node.

        Returns:
            List of generated code lines.
        """
        ...

    @abstractmethod
    def xpath_select_all(
        self, ctx: ConverterContext, node: XpathSelectAll
    ) -> list[str]:
        """Generate code for selecting all matching DOM nodes via XPath.

        Args:
            ctx: Current traversal context.
            node: `XpathSelectAll` AST node.

        Returns:
            List of generated code lines.
        """
        ...

    @abstractmethod
    def xpath_remove(
        self, ctx: ConverterContext, node: XpathRemove
    ) -> list[str]:
        """Generate code for removing matched XPath elements in-place.

        Args:
            ctx: Current traversal context.
            node: `XpathRemove` AST node.

        Returns:
            List of generated code lines.
        """
        ...

    @abstractmethod
    def text(self, ctx: ConverterContext, node: Text) -> list[str]:
        """Generate code for extracting combined text content from a DOM node.

        Args:
            ctx: Current traversal context.
            node: `Text` AST node.

        Returns:
            List of generated code lines.
        """
        ...

    @abstractmethod
    def raw(self, ctx: ConverterContext, node: Raw) -> list[str]:
        """Generate code for extracting raw inner/outer HTML markup from a DOM node.

        Args:
            ctx: Current traversal context.
            node: `Raw` AST node.

        Returns:
            List of generated code lines.
        """
        ...

    @abstractmethod
    def attr(self, ctx: ConverterContext, node: Attr) -> list[str]:
        """Generate code for extracting an HTML element attribute value.

        Args:
            ctx: Current traversal context.
            node: `Attr` AST node.

        Returns:
            List of generated code lines.
        """
        ...

    @abstractmethod
    def to_bool(self, ctx: ConverterContext, node: ToBool) -> list[str]:
        """Generate code for casting a DOM element or text value to boolean.

        Args:
            ctx: Current traversal context.
            node: `ToBool` AST node.

        Returns:
            List of generated code lines.
        """
        ...

    # === PREDICATE BEHAVIOR (return str — condition fragment) ===

    @abstractmethod
    def pred_css(self, node: PredCss) -> str:
        """Generate boolean condition checking if CSS selector matches.

        Args:
            node: `PredCss` AST node.

        Returns:
            Boolean condition string expression.
        """
        ...

    @abstractmethod
    def pred_xpath(self, node: PredXpath) -> str:
        """Generate boolean condition checking if XPath selector matches.

        Args:
            node: `PredXpath` AST node.

        Returns:
            Boolean condition string expression.
        """
        ...

    @abstractmethod
    def pred_has_attr(self, node: PredHasAttr) -> str:
        """Generate boolean condition checking if element has specified attribute.

        Args:
            node: `PredHasAttr` AST node.

        Returns:
            Boolean condition string expression.
        """
        ...

    @abstractmethod
    def pred_attr_contains(self, node: PredAttrContains) -> str:
        """Generate boolean condition checking if attribute contains substring.

        Args:
            node: `PredAttrContains` AST node.

        Returns:
            Boolean condition string expression.
        """
        ...

    @abstractmethod
    def pred_attr_starts(self, node: PredAttrStarts) -> str:
        """Generate boolean condition checking if attribute starts with prefix.

        Args:
            node: `PredAttrStarts` AST node.

        Returns:
            Boolean condition string expression.
        """
        ...

    @abstractmethod
    def pred_attr_ends(self, node: PredAttrEnds) -> str:
        """Generate boolean condition checking if attribute ends with suffix.

        Args:
            node: `PredAttrEnds` AST node.

        Returns:
            Boolean condition string expression.
        """
        ...

    @abstractmethod
    def pred_attr_eq(self, node: PredAttrEq) -> str:
        """Generate boolean condition checking if attribute equals expected value.

        Args:
            node: `PredAttrEq` AST node.

        Returns:
            Boolean condition string expression.
        """
        ...

    @abstractmethod
    def pred_attr_ne(self, node: PredAttrNe) -> str:
        """Generate boolean condition checking if attribute does not equal value.

        Args:
            node: `PredAttrNe` AST node.

        Returns:
            Boolean condition string expression.
        """
        ...

    @abstractmethod
    def pred_attr_re(self, node: PredAttrRe) -> str:
        """Generate boolean condition checking if attribute matches regular expression.

        Args:
            node: `PredAttrRe` AST node.

        Returns:
            Boolean condition string expression.
        """
        ...

    @abstractmethod
    def pred_text_contains(self, node: PredTextContains) -> str:
        """Generate boolean condition checking if text content contains substring.

        Args:
            node: `PredTextContains` AST node.

        Returns:
            Boolean condition string expression.
        """
        ...

    @abstractmethod
    def pred_text_starts(self, node: PredTextStarts) -> str:
        """Generate boolean condition checking if text content starts with prefix.

        Args:
            node: `PredTextStarts` AST node.

        Returns:
            Boolean condition string expression.
        """
        ...

    @abstractmethod
    def pred_text_ends(self, node: PredTextEnds) -> str:
        """Generate boolean condition checking if text content ends with suffix.

        Args:
            node: `PredTextEnds` AST node.

        Returns:
            Boolean condition string expression.
        """
        ...

    @abstractmethod
    def pred_text_re(self, node: PredTextRe) -> str:
        """Generate boolean condition checking if text content matches regex.

        Args:
            node: `PredTextRe` AST node.

        Returns:
            Boolean condition string expression.
        """
        ...
