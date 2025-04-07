"""high-level AST builder interface"""

import logging
from typing import Type, Pattern

from cssselect import SelectorSyntaxError
from typing_extensions import Self, assert_never

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
)
from ssc_codegen.document_utlis import (
    analyze_re_expression,
    unverbosify_regex,
    is_ignore_case_regex,
)
from ssc_codegen.pseudo_selectors import (
    parse_pseudo_xpath_query,
    parse_pseudo_css_query,
    PseudoAction,
)
from ssc_codegen.json_struct import Json
from ssc_codegen.schema import BaseSchema
from ssc_codegen.selector_utils import validate_css_query, validate_xpath_query
from ssc_codegen.tokens import VariableType

LOGGER = logging.getLogger("ssc_gen")


class BaseDocument:
    LOGGER = LOGGER

    def __init__(self) -> None:
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

    def __repr__(self) -> str:
        return (
            f"Document(count={self.count}, ret_type={self.stack_last_ret.name})"
        )


class DefaultDocument(BaseDocument):
    def default(self, value: str | int | float | list | None) -> Self:
        """Set default value. Accept string, int, float or None.
        Should be a first else raise SyntaxError

        - accept: DOCUMENT, return DOCUMENT
        """
        if self.count != 0:
            LOGGER.warning(
                "default(%s) expression should be a first pos, not %s",
                value,
                # human-readable style
                self.stack_last_index + 1,
            )
        self._add(ExprDefaultValueWrapper(kwargs={"value": value}))
        return self


class HTMLDocument(BaseDocument):
    def css(self, query: str) -> Self:
        """Css query. returns first founded element

        - accept: DOCUMENT, return DOCUMENT
        """
        query = " ".join(query.splitlines())
        query, action = parse_pseudo_css_query(query)
        try:
            validate_css_query(query)
        except SelectorSyntaxError:
            LOGGER.warning("`%s` is not valid css query", query)
        # TODO: Remove ANY
        if self.stack_last_ret not in (VariableType.DOCUMENT, VariableType.ANY):
            LOGGER.warning(
                "Expected type %s, got %s",
                VariableType.DOCUMENT.name,
                self.stack_last_ret.name,
            )

        self._add(ExprCss(kwargs={"query": query}))
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
                    self.attr(action[1])  # type: ignore
                case _:
                    assert_never(action[0])

    def xpath(self, query: str) -> Self:
        """Xpath query. returns first founded element
        - accept: DOCUMENT, return DOCUMENT
        """
        query = " ".join(query.splitlines())
        query, action = parse_pseudo_xpath_query(query)
        try:
            validate_xpath_query(query)
        except SelectorSyntaxError:
            LOGGER.warning("`%s` is not valid xpath query", query)

        if self.stack_last_ret not in (VariableType.DOCUMENT, VariableType.ANY):
            LOGGER.warning(
                "Expected type(s) %s, got %s",
                VariableType.DOCUMENT.name,
                self.stack_last_ret.name,
            )
        self._add(ExprXpath(kwargs={"query": query}))
        self._pseudo_query_action_to_expr(action)
        return self

    def css_all(self, query: str) -> Self:
        """Css query. returns all founded elements
        - accept: DOCUMENT, return: LIST_DOCUMENT
        """
        query = " ".join(query.splitlines())
        query, action = parse_pseudo_css_query(query)
        try:
            validate_css_query(query)
        except SelectorSyntaxError:
            LOGGER.warning("`%s` is not valid css query", query)
        if self.stack_last_ret not in (VariableType.DOCUMENT, VariableType.ANY):
            LOGGER.warning(
                "Expected type(s) %s, got %s",
                VariableType.DOCUMENT.name,
                self.stack_last_ret.name,
            )
        self._add(ExprCssAll(kwargs={"query": query}))
        self._pseudo_query_action_to_expr(action)
        return self

    def xpath_all(self, query: str) -> Self:
        """Xpath query. returns all founded elements
        - accept: DOCUMENT, return: LIST_DOCUMENT
        """
        query = " ".join(query.splitlines())
        query, action = parse_pseudo_xpath_query(query)
        try:
            validate_xpath_query(query)
        except SelectorSyntaxError as e:
            LOGGER.warning("`%s` is not valid xpath query", query, exc_info=e)
        if self.stack_last_ret not in (VariableType.DOCUMENT, VariableType.ANY):
            LOGGER.warning(
                "Expected type(s) %s, got %s",
                VariableType.DOCUMENT.name,
                self.stack_last_ret.name,
            )
        self._add(ExprXpathAll(kwargs={"query": query}))
        self._pseudo_query_action_to_expr(action)
        return self

    def attr(self, key: str) -> Self:
        """Extract attribute value by name

        - accept DOCUMENT, return STRING
        - accept LIST_DOCUMENT, return LIST_STRING

        Note:
            in generated code, not check exists required name attribute and throw exception in runtime

        """
        match self.stack_last_ret:
            case VariableType.LIST_DOCUMENT:
                self._add(ExprGetHtmlAttrAll(kwargs={"key": key}))
            case VariableType.DOCUMENT:
                self._add(ExprGetHtmlAttr(kwargs={"key": key}))
            case _:
                LOGGER.warning(
                    "attr(%s): Expected type(s) %s got %s",
                    repr(key),
                    (
                        VariableType.DOCUMENT.name,
                        VariableType.LIST_DOCUMENT.name,
                    ),
                    self.stack_last_ret.name,
                )
                self._add(ExprGetHtmlAttr(kwargs={"key": key}))
        return self

    def text(self) -> Self:
        """extract text from current document/element.

        - accept DOCUMENT, return STRING
        - accept LIST_DOCUMENT, return LIST_STRING
        """
        match self.stack_last_ret:
            case VariableType.LIST_DOCUMENT:
                self._add(ExprGetHtmlTextAll())
            case VariableType.DOCUMENT:
                self._add(ExprGetHtmlText())
            case _:
                LOGGER.warning(
                    "text(): Expected type(s) %s got %s",
                    (
                        VariableType.DOCUMENT.name,
                        VariableType.LIST_DOCUMENT.name,
                    ),
                    self.stack_last_ret.name,
                )
                self._add(ExprGetHtmlText())
        return self

    def raw(self) -> Self:
        """extract raw html from current document/element.

        - accept DOCUMENT, return STRING
        - accept LIST_DOCUMENT, return LIST_STRING
        """
        match self.stack_last_ret:
            case VariableType.LIST_DOCUMENT:
                self._add(ExprGetHtmlRawAll())
            case VariableType.DOCUMENT:
                self._add(ExprGetHtmlRaw())
            case _:
                LOGGER.warning(
                    "raw(): Expected type(s) %s got %s",
                    (
                        VariableType.DOCUMENT.name,
                        VariableType.LIST_DOCUMENT.name,
                    ),
                    self.stack_last_ret.name,
                )
                self._add(ExprGetHtmlRaw())
        return self


class ArrayDocument(BaseDocument):
    def first(self) -> Self:
        """alias index(0)"""
        return self.index(0)

    def last(self) -> Self:
        """alias index(-1). NOTE: several languages does not support get last index"""
        return self.index(-1)

    def index(self, i: int) -> Self:
        """Extract item from sequence

        - accept LIST_DOCUMENT, return DOCUMENT
        - accept LIST_STRING, return STRING
        - accept LIST_INT, return INT
        - accept LIST_FLOAT, return FLOAT
        """
        match self.stack_last_ret:
            case VariableType.LIST_ANY:
                self._add(
                    ExprIndex(
                        kwargs={"index": i},
                        accept_type=VariableType.LIST_ANY,
                        ret_type=VariableType.ANY,
                    )
                )
            case VariableType.LIST_DOCUMENT:
                self._add(
                    ExprIndex(
                        kwargs={"index": i},
                        accept_type=VariableType.LIST_DOCUMENT,
                        ret_type=VariableType.DOCUMENT,
                    )
                )
            case VariableType.LIST_STRING:
                self._add(
                    ExprIndex(
                        kwargs={"index": i},
                        accept_type=VariableType.LIST_STRING,
                        ret_type=VariableType.STRING,
                    )
                )
            case VariableType.LIST_INT:
                self._add(
                    ExprIndex(
                        kwargs={"index": i},
                        accept_type=VariableType.LIST_INT,
                        ret_type=VariableType.INT,
                    )
                )
            case VariableType.LIST_FLOAT:
                self._add(
                    ExprIndex(
                        kwargs={"index": i},
                        accept_type=VariableType.LIST_FLOAT,
                        ret_type=VariableType.FLOAT,
                    )
                )
            case VariableType.OPTIONAL_LIST_STRING:
                self._add(
                    ExprIndex(
                        kwargs={"index": i},
                        accept_type=VariableType.LIST_STRING,
                        ret_type=VariableType.STRING,
                    )
                )
            case VariableType.OPTIONAL_LIST_INT:
                self._add(
                    ExprIndex(
                        kwargs={"index": i},
                        accept_type=VariableType.LIST_INT,
                        ret_type=VariableType.INT,
                    )
                )
            case VariableType.OPTIONAL_LIST_FLOAT:
                self._add(
                    ExprIndex(
                        kwargs={"index": i},
                        accept_type=VariableType.LIST_FLOAT,
                        ret_type=VariableType.FLOAT,
                    )
                )
            case _:
                LOGGER.warning(
                    "index(%s): Expected type(s) %s got %s",
                    i,
                    (
                        VariableType.LIST_DOCUMENT.name,
                        VariableType.LIST_STRING.name,
                        VariableType.LIST_INT.name,
                        VariableType.LIST_FLOAT.name,
                        VariableType.LIST_ANY.name,
                    ),
                    self.stack_last_ret,
                )
                self._add(
                    ExprIndex(
                        kwargs={"index": i},
                    )
                )
        return self

    def join(self, s: str) -> Self:
        """concatenate sequence of string to one by char

        - accept LIST_STRING, return STRING
        """
        match self.stack_last_ret:
            case VariableType.LIST_STRING:
                self._add(ExprListStringJoin(kwargs={"sep": s}))
            case _:
                # side effect
                LOGGER.warning(
                    "join(%s): Expected type(s) %s got %s",
                    s,
                    VariableType.LIST_STRING.name,
                    self.stack_last_ret.name,
                )
                self._add(ExprListStringJoin(kwargs={"sep": s}))
        return self

    def to_len(self) -> Self:
        """Get length of items in array object

        - accept LIST_STRING | LIST_DOCUMENT | LIST_INT | LIST_FLOAT, return INT

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
            LOGGER.warning(
                "to_len(): Expected type(s) %s got %s",
                (
                    VariableType.LIST_DOCUMENT.name,
                    VariableType.LIST_STRING.name,
                    VariableType.LIST_INT,
                    VariableType.LIST_FLOAT,
                ),
                self.stack_last_ret.name,
            )
        self._add(ExprToListLength(accept_type=expected_type))
        return self


class StringDocument(BaseDocument):
    def rm_prefix(self, substr: str) -> Self:
        """remove prefix from string by substr

        - accept STRING, return STRING
        - accept LIST_STRING, return LIST_STRING
        """
        match self.stack_last_ret:
            case VariableType.LIST_STRING:
                self._add(ExprListStringTrim(kwargs={"substr": substr}))
            case VariableType.STRING:
                self._add(ExprStringRmPrefix(kwargs={"substr": substr}))
            case _:
                LOGGER.warning(
                    "rm_prefix(%s): Expected type(s) %s got %s",
                    repr(substr),
                    (VariableType.LIST_STRING.name, VariableType.STRING.name),
                    self.stack_last_ret.name,
                )
                self._add(ExprStringRmPrefix(kwargs={"substr": substr}))
        return self

    def rm_suffix(self, substr: str) -> Self:
        """remove suffix from string by substr

        - accept STRING, return STRING
        - accept LIST_STRING, return LIST_STRING
        """
        match self.stack_last_ret:
            case VariableType.LIST_STRING:
                self._add(ExprListStringRmSuffix(kwargs={"substr": substr}))
            case VariableType.STRING:
                self._add(ExprStringRmSuffix(kwargs={"substr": substr}))
            case _:
                LOGGER.warning(
                    "rm_suffix(%s): Expected type(s) %s got %s",
                    repr(substr),
                    (VariableType.LIST_STRING.name, VariableType.STRING.name),
                    self.stack_last_ret.name,
                )
                self._add(ExprStringRmSuffix(kwargs={"substr": substr}))
        return self

    def rm_prefix_suffix(self, substr: str) -> Self:
        """remove prefix and suffix from string by substr

        - accept STRING, return STRING
        - accept LIST_STRING, return LIST_STRING
        """
        match self.stack_last_ret:
            case VariableType.LIST_STRING:
                self._add(
                    ExprListStringRmPrefixAndSuffix(kwargs={"substr": substr})
                )
            case VariableType.STRING:
                self._add(
                    ExprStringRmPrefixAndSuffix(kwargs={"substr": substr})
                )
            case _:
                LOGGER.warning(
                    "rm_prefix_suffix(%s): Expected type(s) %s got %s",
                    repr(substr),
                    (VariableType.LIST_STRING.name, VariableType.STRING.name),
                    self.stack_last_ret.name,
                )
                self._add(
                    ExprStringRmPrefixAndSuffix(kwargs={"substr": substr})
                )
        return self

    def trim(self, substr: str = " ") -> Self:
        """trim LEFT and RIGHT chars string by substr

        - accept STRING, return STRING
        - accept LIST_STRING, return LIST_STRING
        """
        match self.stack_last_ret:
            case VariableType.LIST_STRING:
                self._add(ExprListStringTrim(kwargs={"substr": substr}))
            case VariableType.STRING:
                self._add(ExprStringTrim(kwargs={"substr": substr}))
            case _:
                LOGGER.warning(
                    "trim(%s): Expected type(s) %s got %s",
                    repr(substr),
                    (VariableType.LIST_STRING.name, VariableType.STRING.name),
                    self.stack_last_ret.name,
                )
                self._add(ExprStringTrim(kwargs={"substr": substr}))
        return self

    def ltrim(self, substr: str = " ") -> Self:
        """trim LEFT by substr

        - accept STRING, return STRING
        - accept LIST_STRING, return LIST_STRING
        """
        match self.stack_last_ret:
            case VariableType.LIST_STRING:
                self._add(ExprListStringLeftTrim(kwargs={"substr": substr}))
            case VariableType.STRING:
                self._add(ExprStringLeftTrim(kwargs={"substr": substr}))
            case _:
                LOGGER.warning(
                    "ltrim(%s): Expected type(s) %s got %s",
                    repr(substr),
                    (VariableType.LIST_STRING.name, VariableType.STRING.name),
                    self.stack_last_ret.name,
                )
                self._add(ExprStringLeftTrim(kwargs={"substr": substr}))
        return self

    def rtrim(self, substr: str = " ") -> Self:
        """trim RIGHT by substr

        - accept STRING, return STRING
        - accept LIST_STRING, return LIST_STRING
        """
        match self.stack_last_ret:
            case VariableType.LIST_STRING:
                self._add(ExprListStringRightTrim(kwargs={"substr": substr}))
            case VariableType.STRING:
                self._add(ExprStringRightTrim(kwargs={"substr": substr}))
            case _:
                LOGGER.warning(
                    "rtrim(%s): Expected type(s) %s got %s",
                    repr(substr),
                    (VariableType.LIST_STRING.name, VariableType.STRING.name),
                    self.stack_last_ret.name,
                )
                self._add(ExprStringRightTrim(kwargs={"substr": substr}))
        return self

    def split(self, sep: str) -> Self:
        """split string by sep

        - accept STRING, return LIST_STRING
        """
        if self.stack_last_ret != VariableType.STRING:
            LOGGER.warning(
                "split(%s): Expected type(s) %s got %s",
                repr(sep),
                VariableType.STRING.name,
                self.stack_last_ret.name,
            )
            ...
        self._add(ExprStringSplit(kwargs={"sep": sep}))
        return self

    def fmt(self, fmt_string: str) -> Self:
        """Format string by template.
        Template placeholder should be included `{{}}` marker

        - accept STRING, return STRING
        - accept LIST_STRING, return LIST_STRING
        """
        if "{{}}" not in fmt_string:
            LOGGER.warning(
                "fmt(%s) missing placeholder char `{{}}`, set to end string",
                repr(fmt_string),
            )
            fmt_string += "{{}}"

        match self.stack_last_ret:
            case VariableType.LIST_STRING:
                self._add(ExprListStringFormat(kwargs={"fmt": fmt_string}))
            case VariableType.STRING:
                self._add(ExprStringFormat(kwargs={"fmt": fmt_string}))
            case _:
                LOGGER.warning(
                    "fmt(%s): Expected type(s) %s got %s",
                    repr(fmt_string),
                    (VariableType.LIST_STRING.name, VariableType.STRING.name),
                    self.stack_last_ret.name,
                )
                self._add(ExprStringFormat(kwargs={"fmt": fmt_string}))
        return self

    def repl(self, old: str, new: str) -> Self:
        """Replace all `old` substring with `new` in current string.

        - accept STRING, return STRING
        - accept LIST_STRING, return LIST_STRING
        """
        match self.stack_last_ret:
            case VariableType.LIST_STRING:
                self._add(
                    ExprListStringReplace(kwargs={"old": old, "new": new})
                )
            case VariableType.STRING:
                self._add(ExprStringReplace(kwargs={"old": old, "new": new}))
            case _:
                LOGGER.warning(
                    "repl(%s, %s): Expected type(s) %s got %s",
                    repr(old),
                    repr(new),
                    (VariableType.LIST_STRING.name, VariableType.STRING.name),
                    self.stack_last_ret.name,
                )
                self._add(ExprStringReplace(kwargs={"old": old, "new": new}))
        return self

    def re(
        self, pattern: str | Pattern, group: int = 1, ignore_case: bool = False
    ) -> Self:
        """extract first regex result.

        NOTE:
            if result not founded - generated code output throw exception (group not founded)

        - accept STRING, return STRING
        """
        if not isinstance(pattern, str):
            ignore_case = is_ignore_case_regex(pattern)

        pattern = unverbosify_regex(pattern)
        result = analyze_re_expression(pattern, max_groups=1)
        if not result:
            LOGGER.warning(result.msg)
        if self.stack_last_ret != VariableType.STRING:
            LOGGER.warning(
                "re(%s): Expected type(s) %s got %s",
                repr(pattern),
                VariableType.STRING.name,
                self.stack_last_ret.name,
            )
        self._add(
            ExprStringRegex(
                kwargs={
                    "pattern": pattern,
                    "group": group,
                    "ignore_case": ignore_case,
                }
            )
        )
        return self

    def re_all(self, pattern: str | Pattern, ignore_case: bool = False) -> Self:
        """extract all regex results.

        - accept STRING, return LIST_STRING
        """
        if not isinstance(pattern, str):
            ignore_case = is_ignore_case_regex(pattern)

        pattern = unverbosify_regex(pattern)
        result = analyze_re_expression(pattern, max_groups=1)
        if not result:
            LOGGER.warning(result.msg)

        if self.stack_last_ret != VariableType.STRING:
            LOGGER.warning(
                "re_all(%s): Expected type(s) %s got %s",
                repr(pattern),
                VariableType.STRING.name,
                self.stack_last_ret.name,
            )
        self._add(
            ExprStringRegexAll(
                kwargs={"pattern": pattern, "ignore_case": ignore_case}
            )
        )
        return self

    def re_sub(self, pattern: str | Pattern, repl: str = "") -> Self:
        """Replace substring by `pattern` to `repl`.

        - accept STRING, return STRING
        - accept LIST_STRING, return LIST_STRING
        """
        pattern = unverbosify_regex(pattern)
        result = analyze_re_expression(pattern, allow_empty_groups=True)
        if not result:
            LOGGER.warning(result.msg)

        match self.stack_last_ret:
            case VariableType.LIST_STRING:
                self._add(
                    ExprListStringRegexSub(
                        kwargs={"pattern": pattern, "repl": repl}
                    )
                )
            case VariableType.STRING:
                self._add(
                    ExprStringRegexSub(
                        kwargs={"pattern": pattern, "repl": repl}
                    )
                )
            case _:
                LOGGER.warning(
                    "re_sub(%s): Expected type(s) %s got %s",
                    repr(pattern),
                    (VariableType.STRING.name, VariableType.LIST_STRING.name),
                    self.stack_last_ret.name,
                )
                self._add(
                    ExprStringRegexSub(
                        kwargs={"pattern": pattern, "repl": repl}
                    )
                )
        return self

    def re_trim(self, pattern: str = r"/s*") -> Self:
        """shortcut of re_sub('^' + pattern).re_sub(pattern + '$')

        as default, trim LEFT and RIGHT whitespace chars by regular expression.

        - accept STRING, return STRING
        - accept LIST_STRING, return LIST_STRING
        """
        self.re_sub(f"^{pattern}")
        self.re_sub(f"{pattern}$")
        return self


class AssertDocument(BaseDocument):
    def is_css(self, query: str, msg: str = "") -> Self:
        """assert css query found element. If in generated code check failed - throw exception

        EXPR DO NOT MODIFY variable

        - accept DOCUMENT, return DOCUMENT
        """
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
        if self.stack_last_ret != VariableType.DOCUMENT:
            LOGGER.warning(
                "is_css(%s): Expected type(s) %s got %s",
                repr(query),
                VariableType.DOCUMENT.name,
                self.stack_last_ret.name,
            )
        self._add(ExprIsCss(kwargs={"query": query, "msg": msg}))
        return self

    def is_xpath(self, query: str, msg: str = "") -> Self:
        """assert xpath query found element. If in generated code check failed - throw exception with passed msg

        EXPR DO NOT MODIFY variable

        - accept DOCUMENT, return DOCUMENT
        """
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
        if self.stack_last_ret != VariableType.DOCUMENT:
            LOGGER.warning(
                "is_xpath(%s): Expected type(s) %s got %s",
                repr(query),
                VariableType.DOCUMENT.name,
                self.stack_last_ret.name,
            )
        self._add(ExprIsXpath(kwargs={"query": query, "msg": msg}))
        return self

    def is_equal(self, value: str | int | float, msg: str = "") -> Self:
        """assert equal by string, int or float value. If in generated code check failed - throw exception with passed msg

        EXPR DO NOT MODIFY variable

        - accept STRING, return STRING
        - accept INT, return INT
        - accept FLOAT return FLOAT
        """

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
            LOGGER.warning(
                "is_equal(%s): Not support variable type `%s`",
                repr(value),
                type(value).__name__,
            )

        if self.stack_last_ret != expected_type:
            LOGGER.warning(
                "is_equal(%s): Expected type(s) %s got %s",
                repr(value),
                expected_type,
                self.stack_last_ret.name,
            )
        self._add(
            ExprIsEqual(
                kwargs={"item": value, "msg": msg},
                accept_type=expected_type,
                ret_type=expected_type,
            )
        )
        return self

    def is_not_equal(self, value: str | int | float, msg: str = "") -> Self:
        """assert not equal by string value. If in generated code check failed - throw exception with passed msg

        EXPR DO NOT MODIFY variable

        - accept STRING, return STRING
        - accept INT, return INT
        - accept FLOAT, return FLOAT
        """
        # warn segment
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
            LOGGER.warning(
                "is_not_equal(%s): Not support variable type `%s`",
                repr(value),
                type(value).__name__,
            )

        if self.stack_last_ret != expected_type:
            LOGGER.warning(
                "is_not_equal(%s): Expected type(s) %s got %s",
                repr(value),
                expected_type,
                self.stack_last_ret.name,
            )
        self._add(
            ExprIsNotEqual(
                kwargs={"item": value, "msg": msg},
                accept_type=expected_type,
                ret_type=expected_type,
            )
        )
        return self

    def is_contains(self, item: str | int | float, msg: str = "") -> Self:
        """assert value contains in sequence. If in generated code check failed - throw exception with passed msg

        EXPR DO NOT MODIFY variable

        - accept LIST_STRING, return LIST_STRING
        """
        # warn
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
            LOGGER.warning(
                "is_contains(%s): Not support variable type `%s`",
                repr(item),
                type(item).__name__,
            )

        if expected_type != self.stack_last_ret:
            LOGGER.warning(
                "is_contains(%s): Expected type(s) %s got %s",
                repr(item),
                expected_type,
                self.stack_last_ret.name,
            )
        self._add(
            ExprIsContains(
                kwargs={"item": item, "msg": msg},
                accept_type=expected_type,
                ret_type=expected_type,
            )
        )
        return self

    def any_is_re(
        self, pattern: str | Pattern, msg: str = "", ignore_case: bool = False
    ) -> Self:
        """assert any value matched in array of strings by regex.
        If in generated code check failed - throw exception with passed msg

        EXPR DO NOT MODIFY variable

        - accept LIST_STRING, return LIST_STRING
        """
        if not isinstance(pattern, str):
            ignore_case = is_ignore_case_regex(pattern)
        pattern = unverbosify_regex(pattern)
        analyze_re_expression(pattern, allow_empty_groups=True)
        if self.stack_last_ret != VariableType.LIST_STRING:
            LOGGER.warning(
                "any_is_re(%s): Expected type(s) %s got %s",
                repr(pattern),
                VariableType.LIST_STRING.name,
                self.stack_last_ret.name,
            )

        self._add(
            ExprListStringAnyRegex(
                kwargs={
                    "pattern": pattern,
                    "ignore_case": ignore_case,
                    "msg": msg,
                }
            )
        )
        return self

    def all_is_re(
        self, pattern: str | Pattern, msg: str = "", ignore_case: bool = False
    ) -> Self:
        """assert all value matched in array of strings by regex.
        If in generated code check failed - throw exception with passed msg

        EXPR DO NOT MODIFY variable

        - accept LIST_STRING, return LIST_STRING
        """
        if not isinstance(pattern, str):
            ignore_case = is_ignore_case_regex(pattern)
        pattern = unverbosify_regex(pattern)
        analyze_re_expression(pattern, allow_empty_groups=True)
        if self.stack_last_ret != VariableType.LIST_STRING:
            LOGGER.warning(
                "all_is_re(%s): Expected type(s) %s got %s",
                repr(pattern),
                VariableType.LIST_STRING.name,
                self.stack_last_ret.name,
            )

        self._add(
            ExprListStringAllRegex(
                kwargs={
                    "pattern": pattern,
                    "ignore_case": ignore_case,
                    "msg": msg,
                }
            )
        )
        return self

    def is_re(
        self, pattern: str | Pattern, msg: str = "", ignore_case: bool = False
    ) -> Self:
        """shortcut of is_regex() method"""
        return self.is_regex(pattern, msg, ignore_case)

    def is_regex(
        self, pattern: str | Pattern, msg: str = "", ignore_case: bool = False
    ) -> Self:
        """assert value matched by regex. If in generated code check failed - throw exception with passed msg

        EXPR DO NOT MODIFY variable

        - accept STRING, return STRING
        """
        if not isinstance(pattern, str):
            ignore_case = is_ignore_case_regex(pattern)
        pattern = unverbosify_regex(pattern)
        analyze_re_expression(pattern, allow_empty_groups=True)

        if self.stack_last_ret != VariableType.STRING:
            LOGGER.warning(
                "is_regex(%s): Expected type(s) %s got %s",
                repr(pattern),
                VariableType.STRING.name,
                self.stack_last_ret.name,
            )

        self._add(
            ExprStringIsRegex(
                kwargs={
                    "pattern": pattern,
                    "ignore_case": ignore_case,
                    "msg": msg,
                }
            )
        )
        return self

    def has_attr(self, key: str, msg: str = "") -> Self:
        """assert document has attribute key. If in generated code check failed - throw exception with passed msg

        EXPR DO NOT MODIFY variable

        - accept DOCUMENT, return DOCUMENT
        - accept LIST_DOCUMENT, return LIST_DOCUMENT
        """
        if self.stack_last_ret == VariableType.DOCUMENT:
            self._add(ExprHasAttr(kwargs={"key": key, "msg": msg}))
        elif self.stack_last_ret == VariableType.LIST_DOCUMENT:
            self._add(ExprListHasAttr(kwargs={"key": key, "msg": msg}))
        else:
            LOGGER.warning(
                "has_attr(%s): Expected type(s) %s got %s",
                repr(key),
                (VariableType.DOCUMENT.name, VariableType.LIST_DOCUMENT.name),
                self.stack_last_ret.name,
            )
            self._add(
                ExprHasAttr(
                    kwargs={"key": key, "msg": msg},
                    ret_type=self.stack_last_ret,
                )
            )
        return self


class NestedDocument(BaseDocument):
    def sub_parser(self, schema: Type["BaseSchema"]) -> Self:
        """mark parse by `schema` config.

        - accept DOCUMENT, return NESTED
        """
        if self.stack_last_ret == VariableType.NESTED:
            LOGGER.warning(
                "sub_parser(%s) not allowed expressions", schema.__name__
            )
        elif self.stack_last_ret != VariableType.DOCUMENT:
            LOGGER.warning(
                "sub_parser(%s) required %s type",
                schema.__name__,
                VariableType.DOCUMENT.name,
            )
        # HACK: store to class instance for generate docstring signature
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
    def to_int(self) -> Self:
        """convert string or sequence of string to integer.

        - accept STRING, return FLOAT
        - accept LIST_STRING, return LIST_FLOAT
        """
        match self.stack_last_ret:
            case VariableType.STRING:
                self._add(ExprToInt())
            case VariableType.LIST_STRING:
                self._add(ExprToListInt())
            case _:
                LOGGER.warning(
                    "to_int(): Expected type(s) %s got %s",
                    (VariableType.STRING.name, VariableType.LIST_STRING.name),
                    self.stack_last_ret.name,
                )
                self._add(ExprToInt())
        return self

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
                LOGGER.warning(
                    "to_float(): Expected type(s) %s got %s",
                    (VariableType.STRING.name, VariableType.LIST_STRING.name),
                    self.stack_last_ret.name,
                )
                self._add(ExprToFloat())
        return self


class BooleanDocument(BaseDocument):
    def to_bool(self) -> Self:
        """convert current value to bool. Accept any type

        value returns false if:

        - None
        - empty sequence
        - empty string

        other - true

        """
        # not required checks
        self._add(ExprToBool())
        return self


class JsonDocument(BaseDocument):
    def jsonify(self, struct: Type[Json]) -> Self:
        """marshal json string to object

        - accept STRING, return JSON
        """
        if self.stack_last_ret != VariableType.STRING:
            LOGGER.warning(
                "jsonify(%s): Expected type(s) %s got %s",
                struct.__name__,
                VariableType.STRING.name,
                self.stack_last_ret.name,
            )
        elif self.stack_last_ret == VariableType.JSON:
            LOGGER.warning(
                "jsonify(%s): not allowed expressions",
                struct.__name__,
                VariableType.STRING.name,
                self.stack_last_ret.name,
            )
        self._add(
            ExprJsonify(
                kwargs={
                    "json_struct_name": struct.__name__,
                    "is_array": struct.__IS_ARRAY__,
                }
            )
        )
        # HACK: store to class instance for generate docstring signature
        BaseSchema.__JSON_SCHEMAS__[struct.__name__] = struct  # type: ignore
        return self
