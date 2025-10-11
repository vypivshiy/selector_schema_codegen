"""high-level AST builder interface"""

from functools import wraps
import logging
from typing import Any, Callable, Type, Pattern, Sequence, TypeVar, Union
from re import Pattern as RePattern

from cssselect import SelectorSyntaxError
from typing_extensions import ParamSpec, Self, assert_never

from ssc_codegen.ast_ import (
    BaseAstNode,
    ExprDefaultValueWrapper,
    ExprCss,
    ExprCssAll,
    ExprXpathAll,
    ExprGetHtmlAttr,
    ExprGetHtmlText,
    ExprGetHtmlAttrAll,
    ExprGetHtmlTextAll,
    ExprGetHtmlRaw,
    ExprGetHtmlRawAll,
    ExprIndex,
    ExprListStringJoin,
    ExprToListLength,
    ExprStringTrim,
    ExprListStringTrim,
    ExprStringLeftTrim,
    ExprListStringLeftTrim,
    ExprListStringRightTrim,
    ExprStringRightTrim,
    ExprStringSplit,
    ExprListStringFormat,
    ExprStringFormat,
    ExprListStringReplace,
    ExprStringReplace,
    ExprStringRegex,
    ExprStringRegexAll,
    ExprListStringRegexSub,
    ExprStringRegexSub,
    ExprIsCss,
    ExprIsXpath,
    ExprIsEqual,
    ExprIsNotEqual,
    ExprIsContains,
    ExprStringIsRegex,
    ExprNested,
    ExprToInt,
    ExprToListInt,
    ExprToFloat,
    ExprToListFloat,
    ExprToBool,
    ExprJsonify,
    ExprXpath,
    ExprStringRmPrefix,
    ExprStringRmSuffix,
    ExprListStringRmSuffix,
    ExprStringRmPrefixAndSuffix,
    ExprListStringRmPrefixAndSuffix,
    ExprListStringAllRegex,
    ExprListStringAnyRegex,
    ExprHasAttr,
    ExprListHasAttr,
    ExprFilter,
    FilterEqual,
    FilterNotEqual,
    FilterStrStarts,
    FilterStrEnds,
    FilterStrIn,
    FilterStrRe,
    FilterAnd,
    FilterOr,
    FilterNot,
    FilterStrLenEq,
    FilterStrLenNe,
    FilterStrLenLt,
    FilterStrLenLe,
    FilterStrLenGt,
    FilterStrLenGe,
    ExprListUnique,
    ExprListStringMapReplace,
    ExprStringMapReplace,
)
from ssc_codegen.ast_.nodes_cast import ExprJsonifyDynamic
from ssc_codegen.ast_.nodes_core import ExprClassVar
from ssc_codegen.ast_.nodes_filter import (
    ExprDocumentFilter,
    FilterDocAttrContains,
    FilterDocAttrEnds,
    FilterDocAttrEqual,
    FilterDocAttrRegex,
    FilterDocAttrStarts,
    FilterDocCss,
    FilterDocHasAttr,
    FilterDocHasRaw,
    FilterDocHasText,
    FilterDocIsRegexRaw,
    FilterDocIsRegexText,
    FilterDocXpath,
)
from ssc_codegen.ast_.nodes_selectors import (
    ExprCssElementRemove,
    ExprMapAttrs,
    ExprMapAttrsAll,
    ExprXpathElementRemove,
)
from ssc_codegen.ast_.nodes_string import (
    ExprListStringRmPrefix,
    ExprListStringUnescape,
    ExprStringUnescape,
)
from ssc_codegen.document_utlis import (
    add_inline_regex_flags,
    analyze_re_expression,
    is_dotall_case_regex,
    unverbosify_regex,
    is_ignore_case_regex,
)
from ssc_codegen.json_struct import Json
from ssc_codegen.pseudo_selectors import (
    parse_pseudo_xpath_query,
    parse_pseudo_css_query,
    PseudoAction,
)
from ssc_codegen.schema import BaseSchema
from ssc_codegen.selector_utils import validate_css_query, validate_xpath_query
from ssc_codegen.tokens import TokenType, VariableType

LOGGER = logging.getLogger("ssc_gen")

T = TypeVar("T", bound="BaseDocument")
P = ParamSpec("P")
R = TypeVar("R")


# helper decorators
def validate_types(
    *expected_types: VariableType,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """decorator for validation types in nodes

    pass expected types for checks
    """

    def decorator(doc_method: Callable[P, R]) -> Callable[P, R]:
        @wraps(doc_method)
        def wrapper(self: BaseDocument, *args: P.args, **kwargs: P.kwargs) -> R:
            current_type = self.stack_last_ret
            if (
                current_type not in expected_types
                and current_type != VariableType.ANY
            ):
                LOGGER.warning(
                    "%s(): Expected type(s) %s, got %s",
                    doc_method.__name__,
                    [t.name for t in expected_types],
                    current_type.name,
                )
            return doc_method(self, *args, **kwargs)

        return wrapper

    return decorator


class BaseDocument:
    LOGGER = LOGGER

    def __init__(self, *_args, **_kwargs) -> None:
        self._stack: list[BaseAstNode] = []

    @property
    def stack(self) -> list[BaseAstNode]:
        """return current stack of expressions"""
        return self._stack

    @property
    def count(self) -> int:
        """return stack length"""
        return len(self._stack)

    @property
    def stack_last_index(self) -> int:
        """return last index stack. if stack empty - return 0"""
        return len(self._stack) - 1 if self._stack else 0

    @property
    def stack_last_ret(self) -> VariableType:
        """return last expression ret type"""
        if len(self._stack) == 0:
            # always Document or Element type
            return VariableType.DOCUMENT
        return self.stack[-1].ret_type

    def _add(self, expr: BaseAstNode) -> None:
        self._stack.append(expr)

    @staticmethod
    def _new_literal_hook(name: str, value: Any) -> dict[str, ExprClassVar]:
        if isinstance(value, ExprClassVar) and value.kind == TokenType.CLASSVAR:
            return {name: value}
        # corner case self-used expr eg:
        # class A(ItemSchema):
        #     LIT_1 = L("SPLT")
        #     items = D().css("p::text").split(LIT_1)
        elif getattr(value, "__IS_LITERAL_DOC__", False):
            return value.expr()
        return {}

    def _resolve_literal_hook(
        self, name: str, value: ExprClassVar | Any
    ) -> tuple[Any, dict[str, ExprClassVar]]:
        """shortcut unpack variable if passed ExprLiteral"""
        literal_hook = self._new_literal_hook(name, value)
        if literal_hook and not isinstance(literal_hook, dict):
            return literal_hook.value, {name: literal_hook}
        return value, {}

    def __repr__(self) -> str:
        return (
            f"Document(count={self.count}, ret_type={self.stack_last_ret.name})"
        )


class DefaultDocument(BaseDocument):
    def default(
        self, value: str | int | float | list | None | list | ExprClassVar
    ) -> Self:
        """Set default value. Accept string, int, float, None or empty list
        Should be a first else raise SyntaxError

        - accept: DOCUMENT, return DOCUMENT
        """
        value, literal_hooks = self._resolve_literal_hook("value", value)

        if isinstance(value, list) and len(value) != 0:
            LOGGER.warning(
                "default(%s) expression value allowed only empty list",
                value,
                # human-readable style
                self.stack_last_index + 1,
            )

        if self.count != 0:
            LOGGER.warning(
                "default(%s) expression should be a first pos, not %s",
                value,
                self.stack_last_index + 1,
            )
        self._add(
            ExprDefaultValueWrapper(
                kwargs={"value": value}, classvar_hooks=literal_hooks
            )
        )
        return self


class HTMLDocument(BaseDocument):
    @validate_types(VariableType.DOCUMENT, VariableType.ANY)
    def css(self, query: str | ExprClassVar) -> Self:
        """Css query. returns first founded element

        - accept: DOCUMENT, return DOCUMENT
        """
        query, literal_hooks = self._resolve_literal_hook("query", query)

        query = " ".join(query.splitlines())
        query, action = parse_pseudo_css_query(query)
        # used only pseudo selector, skip add css expr
        if not query:
            self._pseudo_query_action_to_expr(action)
            return self
        try:
            validate_css_query(query)
        except SelectorSyntaxError:
            LOGGER.warning("`%s` is not valid css query", query)

        if literal_hooks.get("query"):
            literal_hooks["query"].value = query
        self._add(
            ExprCss(kwargs={"query": query}, classvar_hooks=literal_hooks)
        )
        self._pseudo_query_action_to_expr(action)
        return self

    def _pseudo_query_action_to_expr(
        self, action: tuple[PseudoAction | None, str | None]
    ) -> None:
        if action[0]:
            match action[0]:
                case "text":
                    self.text()
                case "raw":
                    self.raw()
                case "attr":
                    self.attr(*action[1])  # type: ignore
                case _:
                    assert_never(action[0])

    @validate_types(VariableType.DOCUMENT, VariableType.ANY)
    def xpath(self, query: str | ExprClassVar) -> Self:
        """Xpath query. returns first founded element
        - accept: DOCUMENT, return DOCUMENT
        """
        query, literal_hooks = self._resolve_literal_hook("query", query)

        query = " ".join(query.splitlines())
        query, action = parse_pseudo_xpath_query(query)
        if not query:
            self._pseudo_query_action_to_expr(action)
            return self

        try:
            validate_xpath_query(query)
        except SelectorSyntaxError:
            LOGGER.warning("`%s` is not valid xpath query", query)
        if literal_hooks.get("query"):
            literal_hooks["query"].value = query
        self._add(
            ExprXpath(kwargs={"query": query}, classvar_hooks=literal_hooks)
        )
        self._pseudo_query_action_to_expr(action)
        return self

    @validate_types(VariableType.DOCUMENT, VariableType.ANY)
    def css_all(self, query: str | ExprClassVar) -> Self:
        """Css query. returns all founded elements
        - accept: DOCUMENT, return: LIST_DOCUMENT
        """
        query, literal_hooks = self._resolve_literal_hook("query", query)
        query = " ".join(query.splitlines())
        query, action = parse_pseudo_css_query(query)
        if not query:
            self._pseudo_query_action_to_expr(action)
            return self
        try:
            validate_css_query(query)
        except SelectorSyntaxError:
            LOGGER.warning("`%s` is not valid css query", query)
        if literal_hooks.get("query"):
            literal_hooks["query"].value = query
        self._add(
            ExprCssAll(kwargs={"query": query}, classvar_hooks=literal_hooks)
        )
        self._pseudo_query_action_to_expr(action)
        return self

    @validate_types(VariableType.DOCUMENT, VariableType.ANY)
    def xpath_all(self, query: str | ExprClassVar) -> Self:
        """Xpath query. returns all founded elements
        - accept: DOCUMENT, return: LIST_DOCUMENT
        """
        query, literal_hooks = self._resolve_literal_hook("query", query)

        query = " ".join(query.splitlines())
        query, action = parse_pseudo_xpath_query(query)
        if not query:
            self._pseudo_query_action_to_expr(action)
            return self
        try:
            validate_xpath_query(query)
        except SelectorSyntaxError as e:
            LOGGER.warning("`%s` is not valid xpath query", query, exc_info=e)

        if literal_hooks.get("query"):
            literal_hooks["query"].value = query
        self._add(
            ExprXpathAll(kwargs={"query": query}, classvar_hooks=literal_hooks)
        )
        self._pseudo_query_action_to_expr(action)
        return self

    @validate_types(VariableType.DOCUMENT, VariableType.LIST_DOCUMENT)
    def attr(self, *keys: str) -> Self:
        """Extract attribute value by name

        - accept DOCUMENT, return STRING
        - accept LIST_DOCUMENT, return LIST_STRING


        CSS has pseudo selector `::attr(*keys)` alias:

        D().css("a::attr(href)") == D().css("a").attr("href")
        D().css_all("a::attr(href)") == D().css_all("a").attr("href")

        XPATH has pseudo selector `/@key` alias:

        D().xpath("//a/@href") == D().xpath("//a").attr("href")
        D().xpath_all("//a/@href") == D().xpath_all("//a").attr("href")

        Note:
            in generated code, not check exists required name attribute and throw exception in runtime

        """
        match self.stack_last_ret:
            case VariableType.LIST_DOCUMENT:
                self._add(ExprGetHtmlAttrAll(kwargs={"key": keys}))
            case VariableType.DOCUMENT:
                if len(keys) == 1:
                    self._add(ExprGetHtmlAttr(kwargs={"key": keys}))
                else:
                    self._add(
                        ExprGetHtmlAttr(
                            kwargs={"key": keys},
                            ret_type=VariableType.LIST_STRING,
                        )
                    )
            # next - stub node. Later static checker catch it and throw exception
            case _:
                self._add(ExprGetHtmlAttr(kwargs={"key": keys}))
        return self

    @validate_types(VariableType.DOCUMENT, VariableType.LIST_DOCUMENT)
    def text(self) -> Self:
        """extract text from current document/element.

        - accept DOCUMENT, return STRING
        - accept LIST_DOCUMENT, return LIST_STRING

        CSS has pseudo selector `::text` alias:

        D().css("p::text") == D().css("p").text()
        D().css_all("p::text") == D().css_all("p").text()

        XPATH has pseudo selector `/text()` alias:

        D().xpath("//p/text()") == D().xpath("//p").text()
        D().xpath_all("//p/text()") == D().xpath_all("//p").text()
        """
        match self.stack_last_ret:
            case VariableType.LIST_DOCUMENT:
                self._add(ExprGetHtmlTextAll())
            case VariableType.DOCUMENT:
                self._add(ExprGetHtmlText())
            case _:
                self._add(ExprGetHtmlText())
        return self

    @validate_types(VariableType.DOCUMENT, VariableType.LIST_DOCUMENT)
    def raw(self) -> Self:
        """extract raw html from current document/element.

        - accept DOCUMENT, return STRING
        - accept LIST_DOCUMENT, return LIST_STRING

         CSS has pseudo selector `::raw` alias:

        D().css("p::raw") == D().css("p").raw()
        D().css_all("p::raw") == D().css_all("p").raw()

        XPATH has pseudo selector `/raw()` alias:

        D().xpath("//p/raw()") == D().xpath("//p").raw()
        D().xpath_all("//p/raw()") == D().xpath_all("//p").raw()
        """
        match self.stack_last_ret:
            case VariableType.LIST_DOCUMENT:
                self._add(ExprGetHtmlRawAll())
            case VariableType.DOCUMENT:
                self._add(ExprGetHtmlRaw())
            case _:
                self._add(ExprGetHtmlRaw())
        return self

    @validate_types(VariableType.DOCUMENT, VariableType.LIST_DOCUMENT)
    def attrs_map(self) -> Self:
        """extract all attributes from current tag or list of tags
        - accept DOCUMENT, return LIST_STRING
        - accept LIST_DOCUMENT, return LIST_STRING
        """
        match self.stack_last_ret:
            case VariableType.DOCUMENT:
                self._add(ExprMapAttrs())
            case VariableType.LIST_DOCUMENT:
                self._add(ExprMapAttrsAll())
            case _:
                self._add(ExprMapAttrs())
        return self

    @validate_types(VariableType.DOCUMENT)
    def css_remove(self, query: str | ExprClassVar):
        """remove elements with childs by css query

        WARNING: have side effect, this method permanently remove elements from virtual DOM

        Added for regex search optimization and drop unnecessary elements like <svg>, <script> etc

        - accept DOCUMENT, return DOCUMENT
        """
        query, literal_hooks = self._resolve_literal_hook("query", query)
        query = " ".join(query.splitlines())
        query, action = parse_pseudo_css_query(query)
        if action:
            LOGGER.warning(
                "css_remove(%s) not allowed pseudoclasses, ignore", repr(query)
            )
        if literal_hooks.get("query"):
            literal_hooks["query"].value = query

        match self.stack_last_ret:
            case VariableType.DOCUMENT:
                self._add(
                    ExprCssElementRemove(
                        kwargs={"query": query}, classvar_hooks=literal_hooks
                    )
                )
            case _:
                self._add(ExprCssElementRemove())
        return self

    @validate_types(VariableType.DOCUMENT)
    def xpath_remove(self, query: str) -> Self:
        """remove elements with childs by xpath query

        WARNING: have side effect, this method permanently remove elements from virtual DOM.

        Added for regex search optimization and drop unnecessary elements like <svg>, <script> etc

        - accept DOCUMENT, return DOCUMENT
        """
        query, literal_hooks = self._resolve_literal_hook("query", query)

        query, action = parse_pseudo_xpath_query(query)

        if action:
            LOGGER.warning(
                "xpath_remove(%s) not allowed pseudoselectors, ignore",
                repr(query),
            )
        if literal_hooks.get("query"):
            literal_hooks["query"].value = query
        match self.stack_last_ret:
            case VariableType.DOCUMENT:
                self._add(
                    ExprXpathElementRemove(
                        kwargs={"query": query}, classvar_hooks=literal_hooks
                    )
                )
            case _:
                self._add(ExprCssElementRemove())
        return self


class ArrayDocument(BaseDocument):
    def first(self) -> Self:
        """alias index(0)"""
        return self.index(0)

    def last(self) -> Self:
        """alias index(-1). NOTE: several languages does not support get last index"""
        return self.index(-1)

    @validate_types(
        VariableType.LIST_STRING,
        VariableType.LIST_DOCUMENT,
        VariableType.LIST_INT,
        VariableType.LIST_FLOAT,
        VariableType.OPTIONAL_LIST_STRING,
        VariableType.OPTIONAL_LIST_INT,
        VariableType.OPTIONAL_LIST_FLOAT,
        VariableType.LIST_ANY,
    )
    def index(self, i: int | ExprClassVar) -> Self:
        """Extract item from sequence

        - accept LIST_DOCUMENT, return DOCUMENT
        - accept LIST_STRING, return STRING
        - accept LIST_INT, return INT
        - accept LIST_FLOAT, return FLOAT

        NOTE:
            - if target backend supports next selectors - recommended use Structural pseudo-classes:
                - :nth-child(n)
                - :nth-last-child(n)
                - :nth-of-type(n)
                - :nth-last-of-type(n)
                - :first-child
                - :last-child
            - first elements starts by 0. if target language index starts by 1 - ssc-gen auto convert it
            - If i < 0, it takes the index from the end of the array. If the target language doesn't support this feature, ssc-gen automatically converts it
        """
        i, literal_hooks = self._resolve_literal_hook("index", i)
        match self.stack_last_ret:
            case VariableType.LIST_ANY:
                self._add(
                    ExprIndex(
                        kwargs={"index": i},
                        accept_type=VariableType.LIST_ANY,
                        ret_type=VariableType.ANY,
                        classvar_hooks=literal_hooks,
                    )
                )
            case VariableType.LIST_DOCUMENT:
                self._add(
                    ExprIndex(
                        kwargs={"index": i},
                        accept_type=VariableType.LIST_DOCUMENT,
                        ret_type=VariableType.DOCUMENT,
                        classvar_hooks=literal_hooks,
                    )
                )
            case VariableType.LIST_STRING:
                self._add(
                    ExprIndex(
                        kwargs={"index": i},
                        accept_type=VariableType.LIST_STRING,
                        ret_type=VariableType.STRING,
                        classvar_hooks=literal_hooks,
                    )
                )
            case VariableType.LIST_INT:
                self._add(
                    ExprIndex(
                        kwargs={"index": i},
                        accept_type=VariableType.LIST_INT,
                        ret_type=VariableType.INT,
                        classvar_hooks=literal_hooks,
                    )
                )
            case VariableType.LIST_FLOAT:
                self._add(
                    ExprIndex(
                        kwargs={"index": i},
                        accept_type=VariableType.LIST_FLOAT,
                        ret_type=VariableType.FLOAT,
                        classvar_hooks=literal_hooks,
                    )
                )
            case VariableType.OPTIONAL_LIST_STRING:
                self._add(
                    ExprIndex(
                        kwargs={"index": i},
                        accept_type=VariableType.LIST_STRING,
                        ret_type=VariableType.STRING,
                        classvar_hooks=literal_hooks,
                    )
                )
            case VariableType.OPTIONAL_LIST_INT:
                self._add(
                    ExprIndex(
                        kwargs={"index": i},
                        accept_type=VariableType.LIST_INT,
                        ret_type=VariableType.INT,
                        classvar_hooks=literal_hooks,
                    )
                )
            case VariableType.OPTIONAL_LIST_FLOAT:
                self._add(
                    ExprIndex(
                        kwargs={"index": i},
                        accept_type=VariableType.LIST_FLOAT,
                        ret_type=VariableType.FLOAT,
                        classvar_hooks=literal_hooks,
                    )
                )
            case _:
                self._add(
                    ExprIndex(
                        kwargs={"index": i},
                    )
                )
        return self

    @validate_types(VariableType.LIST_STRING)
    def join(self, sep: str | ExprClassVar) -> Self:
        """concatenate sequence of string to one by char

        - accept LIST_STRING, return STRING
        """
        sep, literal_hooks = self._resolve_literal_hook("sep", sep)
        match self.stack_last_ret:
            case VariableType.LIST_STRING:
                self._add(
                    ExprListStringJoin(
                        kwargs={"sep": sep}, classvar_hooks=literal_hooks
                    )
                )
            case _:
                LOGGER.warning(
                    "join(%s): Expected type(s) %s got %s",
                    sep,
                    VariableType.LIST_STRING.name,
                    self.stack_last_ret.name,
                )
                self._add(
                    ExprListStringJoin(
                        kwargs={"sep": sep}, classvar_hooks=literal_hooks
                    )
                )
        return self

    @validate_types(
        VariableType.LIST_STRING,
        VariableType.LIST_DOCUMENT,
        VariableType.LIST_INT,
        VariableType.LIST_FLOAT,
        VariableType.OPTIONAL_LIST_STRING,
        VariableType.OPTIONAL_LIST_INT,
        VariableType.OPTIONAL_LIST_FLOAT,
        VariableType.LIST_ANY,
    )
    def to_len(self) -> Self:
        """Get length of items in array object

        - accept LIST_STRING | LIST_DOCUMENT | LIST_INT | LIST_FLOAT,
        - return INT

        """
        if self.stack_last_ret in (
            VariableType.LIST_STRING,
            VariableType.LIST_DOCUMENT,
            VariableType.LIST_INT,
            VariableType.LIST_FLOAT,
        ):
            expected_type = self.stack_last_ret
        else:
            expected_type = VariableType.LIST_ANY
        self._add(ExprToListLength(accept_type=expected_type))
        return self

    @validate_types(VariableType.LIST_STRING, VariableType.LIST_DOCUMENT)
    def filter(
        self, expr: Union["DocumentFilter", "DocumentElementsFilter"]
    ) -> Self:
        """filter array of strings by F() expr
        or array of elements by FE() expr

        - accept LIST_STRING, return LIST_STRING
        - accept LIST_DOCUMENT, return LIST_DOCUMENT
        """
        if isinstance(expr, DocumentElementsFilter):
            self._add(ExprDocumentFilter(body=expr.stack))
        else:
            self._add(ExprFilter(body=expr.stack))
        return self

    @validate_types(VariableType.LIST_STRING)
    def unique(self, *, keep_order: bool = False) -> Self:
        """Remove duplicates from array-like object

        - keep_order - guarantee the order of elements

        - accept LIST_STRING, return LIST_STRING
        """
        self._add(ExprListUnique(kwargs={"keep_order": keep_order}))
        return self


class StringDocument(BaseDocument):
    @validate_types(VariableType.STRING, VariableType.LIST_STRING)
    def rm_prefix(self, substr: str | ExprClassVar) -> Self:
        """remove prefix from string by substr

        - accept STRING, return STRING
        - accept LIST_STRING, return LIST_STRING
        """
        substr, literal_hooks = self._resolve_literal_hook("substr", substr)

        match self.stack_last_ret:
            case VariableType.LIST_STRING:
                self._add(
                    ExprListStringRmPrefix(
                        kwargs={"substr": substr}, classvar_hooks=literal_hooks
                    )
                )
            case VariableType.STRING:
                self._add(
                    ExprStringRmPrefix(
                        kwargs={"substr": substr}, classvar_hooks=literal_hooks
                    )
                )
            case _:
                self._add(ExprStringRmPrefix(kwargs={"substr": substr}))
        return self

    @validate_types(VariableType.STRING, VariableType.LIST_STRING)
    def rm_suffix(self, substr: str | ExprClassVar) -> Self:
        """remove suffix from string by substr

        - accept STRING, return STRING
        - accept LIST_STRING, return LIST_STRING
        """
        substr, literal_hooks = self._resolve_literal_hook("substr", substr)

        match self.stack_last_ret:
            case VariableType.LIST_STRING:
                self._add(
                    ExprListStringRmSuffix(
                        kwargs={"substr": substr}, classvar_hooks=literal_hooks
                    )
                )
            case VariableType.STRING:
                self._add(
                    ExprStringRmSuffix(
                        kwargs={"substr": substr}, classvar_hooks=literal_hooks
                    )
                )
            case _:
                LOGGER.warning(
                    "rm_suffix(%s): Expected type(s) %s got %s",
                    repr(substr),
                    (VariableType.LIST_STRING.name, VariableType.STRING.name),
                    self.stack_last_ret.name,
                )
                self._add(ExprStringRmSuffix(kwargs={"substr": substr}))
        return self

    @validate_types(VariableType.STRING, VariableType.LIST_STRING)
    def rm_prefix_suffix(self, substr: str | ExprClassVar) -> Self:
        """remove prefix and suffix from string by substr

        - accept STRING, return STRING
        - accept LIST_STRING, return LIST_STRING
        """
        substr, literal_hooks = self._resolve_literal_hook("substr", substr)

        match self.stack_last_ret:
            case VariableType.LIST_STRING:
                self._add(
                    ExprListStringRmPrefixAndSuffix(
                        kwargs={"substr": substr}, classvar_hooks=literal_hooks
                    )
                )
            case VariableType.STRING:
                self._add(
                    ExprStringRmPrefixAndSuffix(
                        kwargs={"substr": substr}, classvar_hooks=literal_hooks
                    )
                )
            case _:
                self._add(
                    ExprStringRmPrefixAndSuffix(kwargs={"substr": substr})
                )
        return self

    @validate_types(VariableType.STRING, VariableType.LIST_STRING)
    def trim(self, substr: str | ExprClassVar = " ") -> Self:
        """trim LEFT and RIGHT chars string by substr

        - accept STRING, return STRING
        - accept LIST_STRING, return LIST_STRING
        """
        substr, literal_hooks = self._resolve_literal_hook("substr", substr)

        match self.stack_last_ret:
            case VariableType.LIST_STRING:
                self._add(
                    ExprListStringTrim(
                        kwargs={"substr": substr}, classvar_hooks=literal_hooks
                    )
                )
            case VariableType.STRING:
                self._add(
                    ExprStringTrim(
                        kwargs={"substr": substr}, classvar_hooks=literal_hooks
                    )
                )
            case _:
                self._add(ExprStringTrim(kwargs={"substr": substr}))
        return self

    @validate_types(VariableType.STRING, VariableType.LIST_STRING)
    def ltrim(self, substr: str | ExprClassVar = " ") -> Self:
        """trim LEFT by substr

        - accept STRING, return STRING
        - accept LIST_STRING, return LIST_STRING
        """
        substr, literal_hooks = self._resolve_literal_hook("substr", substr)

        match self.stack_last_ret:
            case VariableType.LIST_STRING:
                self._add(
                    ExprListStringLeftTrim(
                        kwargs={"substr": substr}, classvar_hooks=literal_hooks
                    )
                )
            case VariableType.STRING:
                self._add(
                    ExprStringLeftTrim(
                        kwargs={"substr": substr}, classvar_hooks=literal_hooks
                    )
                )
            case _:
                self._add(ExprStringLeftTrim(kwargs={"substr": substr}))
        return self

    @validate_types(VariableType.STRING, VariableType.LIST_STRING)
    def rtrim(self, substr: str | ExprClassVar = " ") -> Self:
        """trim RIGHT by substr

        - accept STRING, return STRING
        - accept LIST_STRING, return LIST_STRING
        """
        substr, literal_hooks = self._resolve_literal_hook("substr", substr)

        match self.stack_last_ret:
            case VariableType.LIST_STRING:
                self._add(
                    ExprListStringRightTrim(
                        kwargs={"substr": substr}, classvar_hooks=literal_hooks
                    )
                )
            case VariableType.STRING:
                self._add(
                    ExprStringRightTrim(
                        kwargs={"substr": substr}, classvar_hooks=literal_hooks
                    )
                )
            case _:
                self._add(ExprStringRightTrim(kwargs={"substr": substr}))
        return self

    @validate_types(VariableType.STRING)
    def split(self, sep: str | ExprClassVar) -> Self:
        """split string by sep

        - accept STRING, return LIST_STRING
        """
        sep, literal_hooks = self._resolve_literal_hook("sep", sep)
        self._add(
            ExprStringSplit(kwargs={"sep": sep}, classvar_hooks=literal_hooks)
        )
        return self

    @validate_types(VariableType.STRING, VariableType.LIST_STRING)
    def fmt(self, fmt_string: str | ExprClassVar) -> Self:
        """Format string by template.
        Template placeholder should be include `{{}}` marker

        - accept STRING, return STRING
        - accept LIST_STRING, return LIST_STRING
        """
        fmt_string, literal_hooks = self._resolve_literal_hook(
            "fmt", fmt_string
        )
        if "{{}}" not in fmt_string:
            LOGGER.warning(
                "fmt(%s) missing placeholder char `{{}}`, set to end string",
                repr(fmt_string),
            )
            fmt_string += "{{}}"

        match self.stack_last_ret:
            case VariableType.LIST_STRING:
                self._add(
                    ExprListStringFormat(
                        kwargs={"fmt": fmt_string}, classvar_hooks=literal_hooks
                    )
                )
            case VariableType.STRING:
                self._add(
                    ExprStringFormat(
                        kwargs={"fmt": fmt_string}, classvar_hooks=literal_hooks
                    )
                )
            case _:
                self._add(
                    ExprStringFormat(
                        kwargs={"fmt": fmt_string}, classvar_hooks=literal_hooks
                    )
                )
        return self

    @validate_types(VariableType.STRING, VariableType.LIST_STRING)
    def repl(self, old: str | ExprClassVar, new: str | ExprClassVar) -> Self:
        """Replace all `old` substring with `new` in current string.

        - accept STRING, return STRING
        - accept LIST_STRING, return LIST_STRING
        """
        old, literal_hooks1 = self._resolve_literal_hook("old", old)
        new, literal_hooks2 = self._resolve_literal_hook("new", new)
        literal_hooks = literal_hooks1 | literal_hooks2

        match self.stack_last_ret:
            case VariableType.LIST_STRING:
                self._add(
                    ExprListStringReplace(
                        kwargs={"old": old, "new": new},
                        classvar_hooks=literal_hooks,
                    )
                )
            case VariableType.STRING:
                self._add(
                    ExprStringReplace(
                        kwargs={"old": old, "new": new},
                        classvar_hooks=literal_hooks,
                    )
                )
            case _:
                self._add(ExprStringReplace(kwargs={"old": old, "new": new}))
        return self

    @validate_types(VariableType.STRING, VariableType.LIST_STRING)
    def repl_map(self, replace_table: dict[str, str]) -> Self:
        """Replace all `old` substring with `new` in current string by dict table.

        - accept STRING, return STRING
        - accept LIST_STRING, return LIST_STRING
        """
        old_args = tuple(replace_table.keys())
        new_args = tuple(replace_table.values())

        match self.stack_last_ret:
            case VariableType.LIST_STRING:
                self._add(
                    ExprListStringMapReplace(
                        kwargs={"old": old_args, "new": new_args}
                    )
                )
            case VariableType.STRING:
                self._add(
                    ExprStringMapReplace(
                        kwargs={"old": old_args, "new": new_args}
                    )
                )
            case _:
                self._add(
                    ExprStringMapReplace(
                        kwargs={"old": old_args, "new": new_args}
                    )
                )
        return self

    @validate_types(VariableType.STRING)
    def re(
        self,
        pattern: str | Pattern | ExprClassVar,
        group: int = 1,
        ignore_case: bool = False,
        dotall: bool = False,
    ) -> Self:
        """extract first regex result.

        - accept STRING, return STRING

        NOTE:
            - if result not founded - generated code output throw exception (group not founded)
            - support capture one group only
            - allow use re.S, re.I flags
        """

        pattern, literal_hooks = self._resolve_literal_hook("pattern", pattern)

        if not isinstance(pattern, str):
            ignore_case = is_ignore_case_regex(pattern)
            dotall = is_dotall_case_regex(pattern)

        pattern = unverbosify_regex(pattern)
        result = analyze_re_expression(pattern, max_groups=1)
        if not result:
            LOGGER.warning(result.msg)
        # use inline flags for simplify handling literal variabls
        if literal_hooks.get("pattern"):
            literal_hooks["pattern"].value = add_inline_regex_flags(
                pattern, ignore_case, dotall
            )

        self._add(
            ExprStringRegex(
                kwargs={
                    "pattern": pattern,
                    "group": group,
                    "ignore_case": ignore_case,
                    "dotall": dotall,
                },
                classvar_hooks=literal_hooks,
            )
        )
        return self

    @validate_types(VariableType.STRING)
    def re_all(
        self,
        pattern: str | Pattern | ExprClassVar,
        ignore_case: bool = False,
        dotall: bool = False,
    ) -> Self:
        """extract all regex results from captured group.

        - accept STRING, return LIST_STRING

        NOTE:
            - support capture one group only
            - allow use re.S, re.I flags
        """

        pattern, literal_hooks = self._resolve_literal_hook("pattern", pattern)

        if not isinstance(pattern, str):
            ignore_case = is_ignore_case_regex(pattern)
            dotall = is_dotall_case_regex(pattern)

        pattern = unverbosify_regex(pattern)
        result = analyze_re_expression(pattern, max_groups=1)
        if not result:
            LOGGER.warning(result.msg)

        # use inline flags for simplify handling literal variabls
        if literal_hooks.get("pattern"):
            literal_hooks["pattern"].value = add_inline_regex_flags(
                pattern, ignore_case, dotall
            )
        self._add(
            ExprStringRegexAll(
                kwargs={
                    "pattern": pattern,
                    "ignore_case": ignore_case,
                    "dotall": dotall,
                },
                classvar_hooks=literal_hooks,
            )
        )
        return self

    @validate_types(VariableType.STRING, VariableType.LIST_STRING)
    def re_sub(
        self,
        pattern: str | Pattern | ExprClassVar,
        repl: str | ExprClassVar = "",
        ignore_case: bool = False,
        dotall: bool = False,
    ) -> Self:
        """Replace substring by `pattern` to `repl`.

        - accept STRING, return STRING
        - accept LIST_STRING, return LIST_STRING

        NOTE:
            - support capture 0 or 1 group only
            - allow use re.S, re.I flags
        """
        pattern, literal_hooks1 = self._resolve_literal_hook("pattern", pattern)
        repl, literal_hooks2 = self._resolve_literal_hook("repl", repl)
        literal_hooks = literal_hooks1 | literal_hooks2

        if not isinstance(pattern, str):
            ignore_case = is_ignore_case_regex(pattern)
            dotall = is_dotall_case_regex(pattern)
        pattern = unverbosify_regex(pattern)  # type: ignore
        result = analyze_re_expression(pattern, allow_empty_groups=True)
        if not result:
            LOGGER.warning(result.msg)

        # use inline flags for simplify handling literal variabls
        if literal_hooks.get("pattern"):
            literal_hooks["pattern"].value = add_inline_regex_flags(
                pattern, ignore_case, dotall
            )

        match self.stack_last_ret:
            case VariableType.LIST_STRING:
                self._add(
                    ExprListStringRegexSub(
                        kwargs={
                            "pattern": pattern,
                            "repl": repl,
                            "ignore_case": ignore_case,
                            "dotall": dotall,
                        },
                        classvar_hooks=literal_hooks,
                    )
                )
            case VariableType.STRING:
                self._add(
                    ExprStringRegexSub(
                        kwargs={
                            "pattern": pattern,
                            "repl": repl,
                            "ignore_case": ignore_case,
                            "dotall": dotall,
                        },
                        classvar_hooks=literal_hooks,
                    )
                )
            case _:
                self._add(
                    ExprStringRegexSub(
                        kwargs={
                            "pattern": pattern,
                            "repl": repl,
                            "dotall": dotall,
                            "ignore_case": ignore_case,
                        }
                    )
                )
        return self

    def re_trim(self, pattern: str = r"(?:^\s+)|(?:\s+$)") -> Self:
        """shortcut of re_sub(r'(?:^\s+)|(?:\s+$)')

        as default, trim LEFT and RIGHT whitespace chars by regular expression.

        - accept STRING, return STRING
        - accept LIST_STRING, return LIST_STRING
        """
        if isinstance(pattern, ExprClassVar):
            LOGGER.warning(
                "re_trim() not allowed ExprLiteral. Use direct re_sub() instead"
            )
            pattern = pattern.value

        self.re_sub(pattern)
        return self

    @validate_types(VariableType.STRING, VariableType.LIST_STRING)
    def unescape(self) -> Self:
        """unescape string output

        - accept STRING, return STRING
        - accept LIST_STRING, return LIST_STRING
        """
        match self.stack_last_ret:
            case VariableType.STRING:
                self._add(ExprStringUnescape())
            case VariableType.LIST_STRING:
                self._add(ExprListStringUnescape())
            case _:
                self._add(ExprStringUnescape())
        return self


class AssertDocument(BaseDocument):
    @validate_types(VariableType.DOCUMENT)
    def is_css(
        self, query: str | ExprClassVar, msg: str | ExprClassVar = ""
    ) -> Self:
        """assert css query found element. If in generated code check failed - throw exception

        EXPR DO NOT MODIFY variable

        - accept DOCUMENT, return DOCUMENT
        """
        query, literal_hooks1 = self._resolve_literal_hook("query", query)
        msg, literal_hooks2 = self._resolve_literal_hook("msg", msg)
        literal_hooks = literal_hooks1 | literal_hooks2

        query = " ".join(query.splitlines())
        new_query, action = parse_pseudo_css_query(query)
        if action[0]:
            LOGGER.warning(
                "is_css(%s) not support pseudo parse classes, skip", repr(query)
            )
            query = new_query
        try:
            validate_css_query(query)
        except SelectorSyntaxError:
            LOGGER.warning("is_css `%s` is not valid css query", query)

        if literal_hooks.get("query"):
            literal_hooks["query"].value = query
        self._add(
            ExprIsCss(
                kwargs={"query": query, "msg": msg},
                classvar_hooks=literal_hooks,
            )
        )
        return self

    @validate_types(VariableType.DOCUMENT)
    def is_xpath(
        self, query: str | ExprClassVar, msg: str | ExprClassVar = ""
    ) -> Self:
        """assert xpath query found element. If in generated code check failed - throw exception with passed msg

        EXPR DO NOT MODIFY variable

        - accept DOCUMENT, return DOCUMENT
        """
        query, literal_hooks1 = self._resolve_literal_hook("query", query)
        msg, literal_hooks2 = self._resolve_literal_hook("msg", msg)
        literal_hooks = literal_hooks1 | literal_hooks2

        query = " ".join(query.splitlines())
        new_query, action = parse_pseudo_xpath_query(query)
        if action[0]:
            LOGGER.warning(
                "is_xpath(%s) not support pseudo parse classes, skip",
                repr(query),
            )
            query = new_query
        try:
            validate_xpath_query(query)
        except SelectorSyntaxError:
            LOGGER.warning("is_xpath `%s` is not valid xpath query", query)

        if literal_hooks.get("query"):
            literal_hooks["query"].value = query
        self._add(
            ExprIsXpath(
                kwargs={"query": query, "msg": msg},
                classvar_hooks=literal_hooks,
            )
        )
        return self

    @validate_types(
        VariableType.STRING,
        VariableType.INT,
        VariableType.FLOAT,
        VariableType.BOOL,
    )
    def is_equal(
        self,
        value: str | int | float | ExprClassVar,
        msg: str | ExprClassVar = "",
    ) -> Self:
        """assert equal by string, int or float value. If in generated code check failed - throw exception with passed msg

        EXPR DO NOT MODIFY variable

        - accept STRING, return STRING
        - accept INT, return INT
        - accept FLOAT return FLOAT
        """
        value, literal_hooks1 = self._resolve_literal_hook("item", value)
        msg, literal_hooks2 = self._resolve_literal_hook("msg", msg)

        literal_hooks = literal_hooks1 | literal_hooks2

        if (
            isinstance(value, str)
            and self.stack_last_ret != VariableType.STRING
        ):
            expected_type = VariableType.STRING
        elif (
            isinstance(value, bool) and self.stack_last_ret != VariableType.BOOL
        ):
            expected_type = VariableType.BOOL
        elif (
            isinstance(value, float)
            and self.stack_last_ret != VariableType.FLOAT
        ):
            expected_type = VariableType.FLOAT

        elif isinstance(value, int) and self.stack_last_ret != VariableType.INT:
            expected_type = VariableType.INT
        else:
            expected_type = VariableType.ANY
        self._add(
            ExprIsEqual(
                kwargs={"item": value, "msg": msg},
                accept_type=expected_type,
                ret_type=expected_type,
                classvar_hooks=literal_hooks,
            )
        )
        return self

    @validate_types(
        VariableType.STRING,
        VariableType.INT,
        VariableType.FLOAT,
        VariableType.BOOL,
    )
    def is_not_equal(
        self,
        value: str | int | float | ExprClassVar,
        msg: str | ExprClassVar = "",
    ) -> Self:
        """assert not equal by string value. If in generated code check failed - throw exception with passed msg

        EXPR DO NOT MODIFY variable

        - accept STRING, return STRING
        - accept INT, return INT
        - accept FLOAT, return FLOAT
        """
        value, literal_hooks1 = self._resolve_literal_hook("item", value)
        msg, literal_hooks2 = self._resolve_literal_hook("msg", msg)
        literal_hooks = literal_hooks1 | literal_hooks2

        if (
            isinstance(value, str)
            and self.stack_last_ret != VariableType.STRING
        ):
            expected_type = VariableType.STRING
        elif (
            isinstance(value, bool) and self.stack_last_ret != VariableType.BOOL
        ):
            expected_type = VariableType.BOOL

        elif (
            isinstance(value, float)
            and self.stack_last_ret != VariableType.FLOAT
        ):
            expected_type = VariableType.FLOAT

        elif isinstance(value, int) and self.stack_last_ret != VariableType.INT:
            expected_type = VariableType.INT

        else:
            expected_type = VariableType.ANY

        self._add(
            ExprIsNotEqual(
                kwargs={"item": value, "msg": msg},
                accept_type=expected_type,
                ret_type=expected_type,
                classvar_hooks=literal_hooks,
            )
        )
        return self

    @validate_types(
        VariableType.LIST_STRING, VariableType.LIST_INT, VariableType.LIST_FLOAT
    )
    def is_contains(
        self,
        item: str | int | float | ExprClassVar,
        msg: str | ExprClassVar = "",
    ) -> Self:
        """assert value contains in sequence. If in generated code check failed - throw exception with passed msg

        EXPR DO NOT MODIFY variable

        - accept LIST_STRING, return LIST_STRING
        - accept LIST_INT, return LIST_INT
        - accept LIST_FLOAT, return LIST_FLOAT
        """
        item, literal_hooks1 = self._resolve_literal_hook("item", item)
        msg, literal_hooks2 = self._resolve_literal_hook("msg", msg)
        literal_hooks = literal_hooks1 | literal_hooks2

        if (
            isinstance(item, str)
            and self.stack_last_ret != VariableType.LIST_STRING
        ):
            expected_type = VariableType.LIST_STRING
        elif (
            isinstance(item, int)
            and self.stack_last_ret != VariableType.LIST_INT
        ):
            expected_type = VariableType.LIST_INT
        elif (
            isinstance(item, float)
            and self.stack_last_ret != VariableType.LIST_FLOAT
        ):
            expected_type = VariableType.LIST_FLOAT
        else:
            expected_type = VariableType.LIST_ANY

        self._add(
            ExprIsContains(
                kwargs={"item": item, "msg": msg},
                accept_type=expected_type,
                ret_type=expected_type,
                classvar_hooks=literal_hooks,
            )
        )
        return self

    @validate_types(VariableType.LIST_STRING)
    def any_is_re(
        self,
        pattern: str | Pattern | ExprClassVar,
        msg: str | ExprClassVar = "",
        ignore_case: bool = False,
    ) -> Self:
        """assert any value matched in array of strings by regex.
        If in generated code check failed - throw exception with passed msg

        EXPR DO NOT MODIFY variable

        - accept LIST_STRING, return LIST_STRING
        """
        pattern, literal_hooks1 = self._resolve_literal_hook("pattern", pattern)
        msg, literal_hooks2 = self._resolve_literal_hook("msg", msg)
        literal_hooks = literal_hooks1 | literal_hooks2

        if not isinstance(pattern, str):
            ignore_case = is_ignore_case_regex(pattern)
        pattern = unverbosify_regex(pattern)
        analyze_re_expression(pattern, allow_empty_groups=True)

        # use inline flags for simplify handling literal variabls
        if literal_hooks.get("pattern"):
            literal_hooks["pattern"].value = add_inline_regex_flags(
                pattern, ignore_case
            )
        self._add(
            ExprListStringAnyRegex(
                kwargs={
                    "pattern": pattern,
                    "ignore_case": ignore_case,
                    "msg": msg,
                },
                classvar_hooks=literal_hooks,
            )
        )
        return self

    @validate_types(VariableType.LIST_STRING)
    def all_is_re(
        self,
        pattern: str | Pattern | ExprClassVar,
        msg: str | ExprClassVar = "",
        ignore_case: bool = False,
    ) -> Self:
        """assert all value matched in array of strings by regex.
        If in generated code check failed - throw exception with passed msg

        EXPR DO NOT MODIFY variable

        - accept LIST_STRING, return LIST_STRING
        """
        pattern, literal_hooks1 = self._resolve_literal_hook("pattern", pattern)
        msg, literal_hooks2 = self._resolve_literal_hook("msg", msg)
        literal_hooks = literal_hooks1 | literal_hooks2

        if not isinstance(pattern, str):
            ignore_case = is_ignore_case_regex(pattern)
        pattern = unverbosify_regex(pattern)
        analyze_re_expression(pattern, allow_empty_groups=True)

        if literal_hooks.get("pattern"):
            literal_hooks["pattern"].value = add_inline_regex_flags(
                pattern, ignore_case
            )
        self._add(
            ExprListStringAllRegex(
                kwargs={
                    "pattern": pattern,
                    "ignore_case": ignore_case,
                    "msg": msg,
                },
                classvar_hooks=literal_hooks,
            )
        )
        return self

    def is_re(
        self,
        pattern: str | Pattern | ExprClassVar,
        msg: str | ExprClassVar = "",
        ignore_case: bool = False,
    ) -> Self:
        """shortcut of is_regex() method"""
        return self.is_regex(pattern, msg, ignore_case)

    @validate_types(VariableType.STRING)
    def is_regex(
        self,
        pattern: str | Pattern | ExprClassVar,
        msg: str | ExprClassVar = "",
        ignore_case: bool = False,
    ) -> Self:
        """assert value matched by regex. If in generated code check failed - throw exception with passed msg

        EXPR DO NOT MODIFY variable

        - accept STRING, return STRING
        """
        pattern, literal_hooks1 = self._resolve_literal_hook("pattern", pattern)
        msg, literal_hooks2 = self._resolve_literal_hook("msg", msg)
        literal_hooks = literal_hooks1 | literal_hooks2

        if not isinstance(pattern, str):
            ignore_case = is_ignore_case_regex(pattern)
        pattern = unverbosify_regex(pattern)
        analyze_re_expression(pattern, allow_empty_groups=True)

        if literal_hooks.get("pattern"):
            literal_hooks["pattern"].value = add_inline_regex_flags(
                pattern, ignore_case
            )
        self._add(
            ExprStringIsRegex(
                kwargs={
                    "pattern": pattern,
                    "ignore_case": ignore_case,
                    "msg": msg,
                },
                classvar_hooks=literal_hooks,
            )
        )
        return self

    @validate_types(VariableType.DOCUMENT, VariableType.LIST_DOCUMENT)
    def has_attr(
        self, key: str | ExprClassVar, msg: str | ExprClassVar = ""
    ) -> Self:
        """assert document has attribute key. If in generated code check failed - throw exception with passed msg

        EXPR DO NOT MODIFY variable

        - accept DOCUMENT, return DOCUMENT
        - accept LIST_DOCUMENT, return LIST_DOCUMENT
        """
        key, literal_hooks1 = self._resolve_literal_hook("key", key)
        msg, literal_hooks2 = self._resolve_literal_hook("msg", msg)
        literal_hooks = literal_hooks1 | literal_hooks2

        if self.stack_last_ret == VariableType.DOCUMENT:
            self._add(
                ExprHasAttr(
                    kwargs={"key": key, "msg": msg},
                    classvar_hooks=literal_hooks,
                )
            )
        elif self.stack_last_ret == VariableType.LIST_DOCUMENT:
            self._add(
                ExprListHasAttr(
                    kwargs={"key": key, "msg": msg},
                    classvar_hooks=literal_hooks,
                )
            )
        else:
            self._add(
                ExprHasAttr(
                    kwargs={"key": key, "msg": msg},
                    ret_type=self.stack_last_ret,
                )
            )
        return self


class NestedDocument(BaseDocument):
    @validate_types(VariableType.DOCUMENT)
    def sub_parser(self, schema: Type["BaseSchema"]) -> Self:
        """mark parse by `schema` config.

        - accept DOCUMENT, return NESTED
        """
        # HACK: store to class instance for a correct generate docstring signature
        schema.__NESTED_SCHEMAS__[schema.__name__] = schema
        self._add(
            ExprNested(
                kwargs={
                    "schema_name": schema.__name__,
                    "schema_type": schema.__SCHEMA_TYPE__,
                }
            )
        )
        return self


class NumericDocument(BaseDocument):
    @validate_types(VariableType.STRING, VariableType.LIST_STRING)
    def to_int(self) -> Self:
        """convert string or sequence of string to integer.

        - accept STRING, return INTEGER
        - accept LIST_STRING, return LIST_INTEGER
        """
        match self.stack_last_ret:
            case VariableType.STRING:
                self._add(ExprToInt())
            case VariableType.LIST_STRING:
                self._add(ExprToListInt())
            case _:
                self._add(ExprToInt())
        return self

    @validate_types(VariableType.STRING, VariableType.LIST_STRING)
    def to_float(self) -> Self:
        """convert string or sequence of string to float64 or double.

        - accept STRING, return FLOAT
        - accept LIST_STRING, return LIST_FLOAT
        """
        match self.stack_last_ret:
            case VariableType.STRING:
                self._add(ExprToFloat())
            case VariableType.LIST_STRING:
                self._add(ExprToListFloat())
            case _:
                self._add(ExprToFloat())
        return self


class BooleanDocument(BaseDocument):
    def to_bool(self) -> Self:
        """convert current value to bool. Accept any type

        value returns false if previous value:

        - None
        - empty sequence
        - empty string

        other - true

        """
        # not required checks
        self._add(ExprToBool())
        return self


class JsonDocument(BaseDocument):
    @validate_types(VariableType.STRING, VariableType.LIST_STRING)
    def jsonify_dynamic(self, start_query: str = "") -> Self:
        """marshal json to dynamic object wout annotated type/struct

        - accept STRING, return ANY
        - accept LIST_STRING, return ANY

        json query syntax examples:

            start_query="key" - extract json data from ["key"]
            start_query="key.value" - extract json data from ["key"]["value"]
            start_query="0.key" - extract json data from [0]["key"]
            start_query="key.value.1" - extract json data from ["key"]["value"][1]
        """
        self._add(
            ExprJsonifyDynamic(
                kwargs={
                    "query": start_query,
                }
            )
        )
        return self

    @validate_types(VariableType.STRING)
    def jsonify(self, struct: Type[Json], start_query: str = "") -> Self:
        """marshal json string to object.

        if start_query passed - extract data by path before serialize

        - accept STRING, return JSON
        json query syntax examples (slighty):

            start_query="key" - extract json data from ["key"]
            start_query="key.value" - extract json data from ["key"]["value"]
            start_query="0.key" - extract json data from [0]["key"]
            start_query="key.value.1" - extract json data from ["key"]["value"][1]
        """
        self._add(
            ExprJsonify(
                kwargs={
                    "json_struct_name": struct.__name__,
                    "is_array": struct.__IS_ARRAY__,
                    "query": start_query,
                }
            )
        )
        # HACK: store to class instance for generate docstring signature
        BaseSchema.__JSON_SCHEMAS__[struct.__name__] = struct  # type: ignore
        return self


class DocumentFilter(BaseDocument):
    """Special filter marker collections for .filter() argument (type: LIST_STRING)"""

    def eq(self, *values: str) -> Self:
        """check if value equal

        multiple values converts to logical OR (simular as SQL `value IN ("bar", "foo")`)

        pseudocode example:

            F().eq("foo") -> value == "foo"

            F().eq("bar", "foo") -> (value == "bar" | value == "foo")
        """

        # FIXME: replace series str to OR operator
        self._add(FilterEqual(kwargs={"values": values}))
        return self

    def ne(self, *values: str) -> Self:
        """check if value not equal

        multiple values converts to logical AND (simular as SQL `value NOT IN ("bar", "foo")`)

        pseudocode example:

            F().eq("foo") -> value == "foo"

            F().eq("bar", "foo") -> (value != "bar" & value != "foo")
        """

        # FIXME: replace series str to OR operator
        self._add(FilterNotEqual(kwargs={"values": values}))
        return self

    def starts(self, *values: str) -> Self:
        """check if value starts by substring

        multiple values converts to logical OR

        pseudocode example:

            F().eq("foo") -> value == "foo"

            F().eq("foo", "bar") -> (value.starts_with("bar") || value.starts_with("foo"))
        """
        self._add(FilterStrStarts(kwargs={"substr": values}))
        return self

    def ends(self, *values: str) -> Self:
        """check if value starts by substring

        multiple values converts to logical OR

        pseudocode example:

            F().eq("foo") -> value == "foo"

            F().eq("foo", "bar") -> (value.ends_with("bar") || value.ends_with("foo"))
        """
        self._add(FilterStrEnds(kwargs={"substr": values}))
        return self

    def contains(self, *values: str) -> Self:
        """check if value contains by substring

        multiple values converts to logical OR

        pseudocode example:

            F().eq("foo") -> value == "foo"

            F().eq("foo", "bar") -> (value.include("bar") || value.include("foo"))
        """
        self._add(FilterStrIn(kwargs={"substr": values}))
        return self

    def re(
        self,
        pattern: str | Pattern[str] | ExprClassVar,
        ignore_case: bool = False,
    ) -> Self:
        """check if pattern matched result in value"""
        pattern, literal_hooks = self._resolve_literal_hook("pattern", pattern)

        if not isinstance(pattern, str):
            ignore_case = is_ignore_case_regex(pattern)  # type: ignore

        pattern = unverbosify_regex(pattern)  # type: ignore
        result = analyze_re_expression(pattern, allow_empty_groups=True)
        if not result:
            LOGGER.warning(result.msg)

        if literal_hooks.get("pattern"):
            literal_hooks["pattern"].value = pattern
        self._add(
            FilterStrRe(
                kwargs={"pattern": pattern, "ignore_case": ignore_case},
                classvar_hooks=literal_hooks,
            )
        )
        return self

    def and_(self, filter_expr: "DocumentFilter") -> Self:
        if self.stack[0].kind in (FilterAnd.kind, FilterOr.kind):
            LOGGER.warning(
                "logic AND: first node is `%s`", self.stack[0].kind.name
            )
        tmp_stack = filter_expr.stack.copy()
        self._add(FilterAnd(body=tmp_stack))
        return self

    def or_(self, filter_expr: "DocumentFilter") -> Self:
        if self.stack[0].kind in (FilterAnd.kind, FilterOr.kind):
            LOGGER.warning(
                "logic OR: first node is `%s`", self.stack[0].kind.name
            )
        tmp_stack = filter_expr.stack.copy()
        self._add(FilterOr(body=tmp_stack))
        return self

    def len_eq(self, value: int) -> Self:
        self._add(FilterStrLenEq(kwargs={"length": value}))
        return self

    def len_ne(self, value: int) -> Self:
        self._add(FilterStrLenNe(kwargs={"length": value}))
        return self

    def len_lt(self, value: int) -> Self:
        self._add(FilterStrLenLt(kwargs={"length": value}))
        return self

    def len_le(self, value: int) -> Self:
        self._add(FilterStrLenLe(kwargs={"length": value}))
        return self

    def len_gt(self, value: int) -> Self:
        self._add(FilterStrLenGt(kwargs={"length": value}))
        return self

    def len_ge(self, value: int) -> Self:
        self._add(FilterStrLenGe(kwargs={"length": value}))
        return self

    def not_(self, filter_expr: "DocumentFilter") -> Self:
        tmp_stack = filter_expr.stack.copy()
        self._add(FilterNot(body=tmp_stack))
        return self

    def __or__(self, other: "DocumentFilter") -> "DocumentFilter":
        """syntax suger F().or_(...)"""
        new_filter = DocumentFilter()
        new_filter.stack.extend(self.stack)
        return new_filter.or_(other)

    def __and__(self, other: "DocumentFilter") -> "DocumentFilter":
        """syntax sugar F().and_(...)"""
        new_filter = DocumentFilter()
        new_filter.stack.extend(self.stack)
        return new_filter.and_(other)

    def __invert__(self) -> "DocumentFilter":
        """syntax sugar F().not_(...)"""
        new_filter = DocumentFilter()
        new_filter.stack.extend(self.stack)
        return DocumentFilter().not_(new_filter)

    # ignoring Liskov substitution principle for the sake of filter DSL expressiveness
    def __eq__(self, other: int | str | Sequence[str]) -> "DocumentFilter":  # type: ignore[override]
        """syntax sugar F().eq(...)"""
        new_filter = DocumentFilter()
        new_filter.stack.extend(self.stack)
        if isinstance(other, int):
            return new_filter.len_eq(other)

        if isinstance(other, str):
            other = (other,)
        return new_filter.eq(*other)

    def __ne__(self, other: int | str | Sequence[str]) -> "DocumentFilter":  # type: ignore[override]
        """syntax sugar F().ne(...)"""
        new_filter = DocumentFilter()
        new_filter.stack.extend(self.stack)
        if isinstance(other, int):
            return new_filter.len_ne(other)

        if isinstance(other, str):
            other = (other,)
        return new_filter.ne(*other)

    def __lt__(self, other: int) -> "DocumentFilter":
        new_filter = DocumentFilter()
        new_filter.stack.extend(self.stack)
        return new_filter.len_lt(other)

    def __le__(self, other: int) -> "DocumentFilter":
        new_filter = DocumentFilter()
        new_filter.stack.extend(self.stack)
        return new_filter.len_le(other)

    def __gt__(self, other: int) -> "DocumentFilter":
        new_filter = DocumentFilter()
        new_filter.stack.extend(self.stack)
        return new_filter.len_gt(other)

    def __ge__(self, other: int) -> "DocumentFilter":
        new_filter = DocumentFilter()
        new_filter.stack.extend(self.stack)
        return new_filter.len_ge(other)


class ClassVarDocument(BaseDocument):
    __IS_LITERAL_DOC__ = True
    """special document type for define classvar-literal variables

    it can be helps create a config-like structures, fields
    """

    def __init__(
        self,
        val: str | int | float | RePattern[str] | list[str] | None,
        self_cls: str | None = None,
        parse_returns: bool = False,
        is_regex: bool = False,
    ):
        super().__init__()
        self._is_regex = False

        if not (
            val is None or isinstance(val, (str, int, float, RePattern, list))
        ):
            raise TypeError(
                "Literals expected (None, int, str, float, re.Pattern, list[str]) types"
            )

        if val is None:
            type_ = VariableType.NULL
        # regex pattern input required check in re, re_all, re_sub exprs
        #  1. shold be converts later in coverter
        #  2. flags converts to inline: (?i) (?s), (?si) etc
        elif isinstance(val, (str, RePattern)):
            type_ = VariableType.STRING
            self._is_regex = True
        elif isinstance(val, bool):
            type_ = VariableType.BOOL
        elif isinstance(val, float):
            type_ = VariableType.FLOAT
        elif isinstance(val, int):
            type_ = VariableType.INT
        # list string only supports this DSL impl
        # elemets will be converts later
        elif isinstance(val, list):
            type_ = VariableType.LIST_STRING

        if isinstance(val, RePattern):
            self._is_regex = self._is_regex or is_regex

        self._value = val
        self._type = type_
        self._parse_returns = parse_returns
        # if self-init classvar need manually pass path
        self.use_self_cls = bool(self_cls)
        if self.use_self_cls and isinstance(self_cls, str):
            cls, name = self_cls.split(".")
            self.struct_name = cls  # type: ignore
            self.field_name = name  # type: ignore
        # late init by __init_subclass__ in BaseSchema class
        else:
            self.struct_name: str | None = None  # type: ignore
            self.field_name: str | None = None  # type: ignore

    @property
    def stack_last_ret(self) -> VariableType:
        return self.expr().ret_type

    @property
    def is_regex(self) -> bool:
        return self._is_regex

    @is_regex.setter
    def is_regex(self, val: bool) -> None:
        self._is_regex = val

    def expr(self) -> ExprClassVar:
        return ExprClassVar(
            kwargs={
                "value": self._value,
                "struct_name": self.struct_name,
                "field_name": self.field_name,
                "parse_returns": self._parse_returns,
                "is_regex": self._is_regex,
            },
            accept_type=self._type,
            ret_type=self._type,
        )

    def __repr__(self) -> str:
        if self.struct_name and self.field_name:
            return f"ClassVar({self.struct_name}.{self.field_name} = {self._value!r}, returns = {self._parse_returns})"
        return f"ClassVar({self._value!r}, returns = {self._parse_returns})"


class DocumentElementsFilter(BaseDocument):
    """Special filter marker collections for .filter() argument (type: LIST_DOCUMENT)"""

    def css(self, query: str) -> Self:
        self._add(FilterDocCss(kwargs={"query": query}))
        return self

    def xpath(self, query: str) -> Self:
        self._add(FilterDocXpath(kwargs={"query": query}))
        return self

    def has_text(self, *values: str) -> Self:
        """check if element contains value in text element  Node

        multiple values converts to logical OR

        pseudocode example:

            FE().has_text("foo") -> "foo" in element.textContent

            FE().has_text("bar", "foo") -> ("bar" in element.textContent | "foo" in element.textContent)
        """
        self._add(FilterDocHasText(kwargs={"values": values}))
        return self

    def has_raw(self, *values: str) -> Self:
        """check if element contains value in raw element Node

        multiple values converts to logical OR

        pseudocode example:

            FE().has_raw("foo") -> "foo" in element.outerHTML

            FE().has_raw("bar", "foo") -> ("bar" in element.outerHTML | "foo" in element.outerHTML)
        """
        self._add(FilterDocHasRaw(kwargs={"values": values}))
        return self

    def re_text(
        self,
        pattern: str | RePattern[str],
        ignore_case: bool = False,
    ) -> Self:
        """check if element text matched by regex

        pseudocode example:
            FE().text_re(r"foo") -> in element.textContent.match(r"foo")
        """
        if not isinstance(pattern, str):
            ignore_case = is_ignore_case_regex(pattern)  # type: ignore

        pattern = unverbosify_regex(pattern)  # type: ignore
        result = analyze_re_expression(pattern, allow_empty_groups=True)
        if not result:
            LOGGER.warning(result.msg)
        self._add(
            FilterDocIsRegexText(
                kwargs={"pattern": pattern, "ignore_case": ignore_case}
            )
        )

    def re_raw(
        self, pattern: str | RePattern[str], ignore_case: bool = False
    ) -> Self:
        """check if element text matched by regex

        pseudocode example:
            FE().text_re(r"foo") -> in element.outerHTML.match(r"foo")
        """
        if not isinstance(pattern, str):
            ignore_case = is_ignore_case_regex(pattern)  # type: ignore

        pattern = unverbosify_regex(pattern)  # type: ignore
        result = analyze_re_expression(pattern, allow_empty_groups=True)
        if not result:
            LOGGER.warning(result.msg)
        self._add(
            FilterDocIsRegexRaw(
                kwargs={"pattern": pattern, "ignore_case": ignore_case}
            )
        )
        return self

    def has_attr(self, *keys: str) -> Self:
        """check if element contains attribure by key

        multiple values converts to logical OR

        pseudocode example:

            FE().has_attr("href") -> element.hasAttribute("href")
            FE().has_attr("href", "src") -> element.hasAttribute("href") || element.hasAttribute("src")
        """
        self._add(FilterDocHasAttr(kwargs={"keys": keys}))
        return self

    def attr_eq(self, key: str, *values: str) -> Self:
        """check if element attribure equal by value

        multiple values converts to logical OR

        pseudocode example:

            FE().attr_eq("href", "example.com") -> element.hasAttribute("href") && element["href"] == "example.com"
            FE().attr_eq("href", "foo", "bar") -> element.hasAttribute("href") && (element["href"] == "foo" || element["href"] == "bar")
        """
        # check first attribute check for generate more stable expr
        # if has_attr exists - skip else add it
        for expr in self.stack:
            if (
                expr.kind == FilterDocHasAttr.kind
                and key in expr.kwargs["keys"]
            ):
                break
        else:
            self.has_attr(key)
        self._add(FilterDocAttrEqual(kwargs={"key": key, "values": values}))
        return self

    def attr_starts(self, key: str, *values: str) -> Self:
        """check if element attribure starts by value

        multiple values converts to logical OR

        pseudocode example:

            FE().attr_eq("href", "http") -> element.hasAttribute("href") && element["href"].starts("http")
            FE().attr_eq("href", "foo", "bar") -> element.hasAttribute("href") && (element["href"].starts("foo") || element["href"].starts("bar"))
        """
        for expr in self.stack:
            if (
                expr.kind == FilterDocHasAttr.kind
                and key in expr.kwargs["keys"]
            ):
                break
        else:
            self.has_attr(key)
        self._add(FilterDocAttrStarts(kwargs={"key": key, "values": values}))
        return self

    def attr_ends(self, key: str, *values: str) -> Self:
        """check if element attribure ends by value

        multiple values converts to logical OR

        pseudocode example:

            FE().attr_eq("href", "/api") -> element.hasAttribute("href") && element["href"].ends("/api")
            FE().attr_eq("href", "foo", "bar") -> element.hasAttribute("href") && (element["href"].ends("foo") || element["href"].ends("bar"))
        """
        for expr in self.stack:
            if (
                expr.kind == FilterDocHasAttr.kind
                and key in expr.kwargs["keys"]
            ):
                break
        else:
            self.has_attr(key)
        self._add(FilterDocAttrEnds(kwargs={"key": key, "values": values}))
        return self

    def attr_contains(self, key: str, *values: str) -> Self:
        """check if element attribure contains by value

        multiple values converts to logical OR

        pseudocode example:

            FE().attr_eq("href", "user=") -> element.hasAttribute("href") && "user=" in element["href"]
            FE().attr_eq("href", "foo", "bar") -> element.hasAttribute("href") && ("foo" in element["href"] || "bar" in element["href"])
        """
        for expr in self.stack:
            if (
                expr.kind == FilterDocHasAttr.kind
                and key in expr.kwargs["keys"]
            ):
                break
        else:
            self.has_attr(key)
        self._add(FilterDocAttrContains(kwargs={"key": key, "values": values}))
        return self

    def attr_re(
        self, key: str, pattern: str | Pattern[str], ignore_case: bool = False
    ) -> Self:
        """check if element attribure matched by regex

        multiple values converts to logical OR

        pseudocode example:

            FE().attr_eq("href", "\d+") -> element.hasAttribute("href") && element["href"].match(\d+)
            FE().attr_eq("href", "foo", "bar") -> element.hasAttribute("href") && (element["href"].match("foo") || element["href"].match("foo"))
        """
        if not isinstance(pattern, str):
            ignore_case = is_ignore_case_regex(pattern)  # type: ignore

        pattern = unverbosify_regex(pattern)  # type: ignore
        result = analyze_re_expression(pattern, allow_empty_groups=True)
        if not result:
            LOGGER.warning(result.msg)
        for expr in self.stack:
            if (
                expr.kind == FilterDocHasAttr.kind
                and key in expr.kwargs["keys"]
            ):
                break
        else:
            self.has_attr(key)
        self._add(
            FilterDocAttrRegex(
                kwargs={
                    "key": key,
                    "pattern": pattern,
                    "ignore_case": ignore_case,
                }
            )
        )
        return self

    def and_(self, filter_expr: "DocumentElementsFilter") -> Self:
        if self.stack[0].kind in (FilterAnd.kind, FilterOr.kind):
            LOGGER.warning(
                "logic AND: first node is `%s`", self.stack[0].kind.name
            )
        tmp_stack = filter_expr.stack.copy()
        self._add(FilterAnd(body=tmp_stack))
        return self

    def or_(self, filter_expr: "DocumentElementsFilter") -> Self:
        if self.stack[0].kind in (FilterAnd.kind, FilterOr.kind):
            LOGGER.warning(
                "logic AND: first node is `%s`", self.stack[0].kind.name
            )
        tmp_stack = filter_expr.stack.copy()
        self._add(FilterOr(body=tmp_stack))
        return self

    def not_(self, filter_expr: "DocumentElementsFilter"):
        tmp_stack = filter_expr.stack.copy()
        self._add(FilterNot(body=tmp_stack))
        return self

    def __or__(
        self, other: "DocumentElementsFilter"
    ) -> "DocumentElementsFilter":
        """syntax sugar F().or_(expr)"""
        new_filter = DocumentElementsFilter()
        new_filter.stack.extend(self.stack)
        return new_filter.or_(other)

    def __and__(
        self, other: "DocumentElementsFilter"
    ) -> "DocumentElementsFilter":
        """syntax sugar F().and_(expr)"""
        new_filter = DocumentElementsFilter()
        new_filter.stack.extend(self.stack)
        return new_filter.or_(other)

    def __invert__(self) -> "DocumentElementsFilter":
        """syntax sugar F().not_(expr)"""
        new_filter = DocumentElementsFilter()
        new_filter.stack.extend(self.stack)
        return DocumentElementsFilter().not_(new_filter)
