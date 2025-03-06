"""high-level AST builder interface"""

from typing import Type, Pattern

from typing_extensions import Self

from .json_struct import Json
from .ast_ssc import (
    BaseExpression,
    DefaultValueWrapper,
    FormatExpression,
    HtmlAttrAllExpression,
    HtmlAttrExpression,
    HtmlCssAllExpression,
    HtmlCssExpression,
    HtmlRawAllExpression,
    HtmlRawExpression,
    HtmlTextAllExpression,
    HtmlTextExpression,
    HtmlXpathAllExpression,
    HtmlXpathExpression,
    IndexDocumentExpression,
    IndexStringExpression,
    IsContainsExpression,
    IsCssExpression,
    IsEqualExpression,
    IsNotEqualExpression,
    IsRegexMatchExpression,
    IsXPathExpression,
    JoinExpression,
    LTrimExpression,
    MapFormatExpression,
    MapLTrimExpression,
    MapRegexSubExpression,
    MapReplaceExpression,
    MapRTrimExpression,
    MapTrimExpression,
    NestedExpression,
    RegexAllExpression,
    RegexExpression,
    RegexSubExpression,
    ReplaceExpression,
    RTrimExpression,
    SplitExpression,
    ToFloat,
    ToInteger,
    ToListFloat,
    ToListInteger,
    TrimExpression,
    ToJson,
    ToBool,
    ArrayLengthExpression,
)
from .document_utlis import assert_re_expression, unverbosify_regex
from .schema import BaseSchema
from .selector_utils import validate_css_query, validate_xpath_query
from .tokens import VariableType


class BaseDocument:
    def __init__(self) -> None:
        self._stack: list[BaseExpression] = []

    @property
    def stack(self) -> list[BaseExpression]:
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
        """return last expression type"""
        if len(self._stack) == 0:
            # always Document or Element type
            return VariableType.DOCUMENT
        return self.stack[-1].ret_type

    @staticmethod
    def _raise_wrong_type_error(
        type_: VariableType, *expected: VariableType
    ) -> None:
        fmt_types = "(" + ",".join(i.name for i in expected) + ")"
        msg = f"Expected type(s): {fmt_types}, got {type_.name}"
        raise SyntaxError(msg)

    def _add(self, expr: BaseExpression) -> None:
        self._stack.append(expr)

    def __repr__(self) -> str:
        return (
            f"Document(count={self.count}, ret_type={self.stack_last_ret.name})"
        )


class DefaultDocument(BaseDocument):
    def default(self, value: str | int | float | None) -> Self:
        """Set default value. Accept string, int, float or None.
        Should be a first else raise SyntaxError

        - accept: DOCUMENT, return DOCUMENT
        """
        if self.count != 0:
            raise SyntaxError("default expression should be a first")
        self._add(DefaultValueWrapper(value=value))
        return self


class HTMLDocument(BaseDocument):
    def css(self, query: str) -> Self:
        """Css query. returns first founded element

        - accept: DOCUMENT, return DOCUMENT
        """
        validate_css_query(query)
        match self.stack_last_ret:
            case VariableType.DOCUMENT:
                self._add(HtmlCssExpression(query=query))
            case VariableType.ANY:
                self._add(HtmlCssExpression(query=query))
            case _:
                self._raise_wrong_type_error(
                    self.stack_last_ret, VariableType.DOCUMENT
                )
        return self

    def xpath(self, query: str) -> Self:
        """Xpath query. returns first founded element
        - accept: DOCUMENT, return DOCUMENT
        """
        validate_xpath_query(query)
        match self.stack_last_ret:
            case VariableType.DOCUMENT:
                self._add(HtmlXpathExpression(query=query))
            case VariableType.ANY:
                self._add(HtmlXpathExpression(query=query))
            case _:
                self._raise_wrong_type_error(
                    self.stack_last_ret, VariableType.DOCUMENT
                )
        return self

    def css_all(self, query: str) -> Self:
        """Css query. returns all founded elements
        - accept: DOCUMENT, return: LIST_DOCUMENT
        """
        validate_css_query(query)
        match self.stack_last_ret:
            case VariableType.DOCUMENT:
                self._add(HtmlCssAllExpression(query=query))
            case VariableType.ANY:
                self._add(HtmlCssAllExpression(query=query))
            case _:
                self._raise_wrong_type_error(
                    self.stack_last_ret, VariableType.DOCUMENT
                )
        return self

    def xpath_all(self, query: str) -> Self:
        """Xpath query. returns all founded elements
        - accept: DOCUMENT, return: LIST_DOCUMENT
        """
        validate_xpath_query(query)
        match self.stack_last_ret:
            case VariableType.DOCUMENT:
                self._add(HtmlXpathAllExpression(query=query))
            case VariableType.ANY:
                self._add(HtmlXpathAllExpression(query=query))
            case _:
                self._raise_wrong_type_error(
                    self.stack_last_ret, VariableType.DOCUMENT
                )
        return self

    def attr(self, name: str) -> Self:
        """Extract attribute value by name

        - accept DOCUMENT, return STRING
        - accept LIST_DOCUMENT, return LIST_STRING

        Note:
            in generated code, not check exists required name attribute and throw exception in runtime

        """
        match self.stack_last_ret:
            case VariableType.DOCUMENT:
                self._add(HtmlAttrExpression(attr=name))
            case VariableType.ANY:
                self._add(HtmlAttrExpression(attr=name))
            case VariableType.LIST_DOCUMENT:
                self._add(HtmlAttrAllExpression(attr=name))
            case _:
                self._raise_wrong_type_error(
                    self.stack_last_ret,
                    VariableType.DOCUMENT,
                    VariableType.LIST_DOCUMENT,
                )
        return self

    def text(self) -> Self:
        """extract text from current document/element.

        - accept DOCUMENT, return STRING
        - accept LIST_DOCUMENT, return LIST_STRING
        """
        match self.stack_last_ret:
            case VariableType.DOCUMENT:
                self._add(HtmlTextExpression())
            case VariableType.ANY:
                self._add(HtmlTextExpression())

            case VariableType.LIST_DOCUMENT:
                self._add(HtmlTextAllExpression())
            case _:
                self._raise_wrong_type_error(
                    self.stack_last_ret,
                    VariableType.DOCUMENT,
                    VariableType.LIST_DOCUMENT,
                )
        return self

    def raw(self) -> Self:
        """extract raw html from current document/element.

        - accept DOCUMENT, return STRING
        - accept LIST_DOCUMENT, return LIST_STRING
        """
        match self.stack_last_ret:
            case VariableType.DOCUMENT:
                self._add(HtmlRawExpression())
            case VariableType.ANY:
                self._add(HtmlRawExpression())
            case VariableType.LIST_DOCUMENT:
                self._add(HtmlRawAllExpression())
            case _:
                self._raise_wrong_type_error(
                    self.stack_last_ret,
                    VariableType.DOCUMENT,
                    VariableType.LIST_DOCUMENT,
                )
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
        if self.stack == 0:
            raise SyntaxError("Empty expressions stack")

        match self.stack_last_ret:
            case VariableType.LIST_DOCUMENT:
                self._add(
                    IndexDocumentExpression(
                        value=i, ret_type=VariableType.DOCUMENT
                    )
                )
            case VariableType.LIST_STRING:
                self._add(
                    IndexStringExpression(value=i, ret_type=VariableType.STRING)
                )
            case VariableType.LIST_INT:
                self._add(
                    IndexStringExpression(value=i, ret_type=VariableType.INT)
                )
            case VariableType.LIST_FLOAT:
                self._add(
                    IndexStringExpression(value=i, ret_type=VariableType.FLOAT)
                )
            case VariableType.OPTIONAL_LIST_STRING:
                self._add(
                    IndexStringExpression(value=i, ret_type=VariableType.STRING)
                )
            case VariableType.OPTIONAL_LIST_INT:
                self._add(
                    IndexStringExpression(value=i, ret_type=VariableType.INT)
                )
            case VariableType.OPTIONAL_LIST_FLOAT:
                self._add(
                    IndexStringExpression(value=i, ret_type=VariableType.FLOAT)
                )
            case _:
                self._raise_wrong_type_error(
                    self.stack_last_ret,
                    VariableType.LIST_STRING,
                    VariableType.LIST_DOCUMENT,
                )
        return self

    def join(self, s: str) -> Self:
        """concatenate sequence of string to one by char

        - accept LIST_STRING, return STRING
        """
        match self.stack_last_ret:
            case VariableType.LIST_STRING:
                self._add(JoinExpression(sep=s))
            case _:
                self._raise_wrong_type_error(
                    self.stack_last_ret,
                    VariableType.LIST_STRING,
                )
        return self

    def to_len(self) -> Self:
        """Get length of items in array object

        - accept LIST_STRING | LIST_DOCUMENT | LIST_INT | LIST_FLOAT, return INT

        """
        match self.stack_last_ret:
            case VariableType.LIST_STRING:
                pass
            case VariableType.LIST_DOCUMENT:
                pass
            case VariableType.LIST_INT:
                pass
            case VariableType.LIST_FLOAT:
                pass
            case _:
                self._raise_wrong_type_error(
                    self.stack_last_ret,
                    VariableType.LIST_STRING,
                    VariableType.LIST_DOCUMENT,
                    VariableType.LIST_INT,
                    VariableType.LIST_FLOAT,
                )
        self._add(ArrayLengthExpression())
        return self


class StringDocument(BaseDocument):
    def trim(self, substr: str = " ") -> Self:
        """trim LEFT and RIGHT chars string by substr

        - accept STRING, return STRING
        - accept LIST_STRING, return LIST_STRING
        """
        match self.stack_last_ret:
            case VariableType.LIST_STRING:
                self._add(MapTrimExpression(value=substr))
            case VariableType.STRING:
                self._add(TrimExpression(value=substr))
            case _:
                self._raise_wrong_type_error(
                    self.stack_last_ret,
                    VariableType.STRING,
                    VariableType.LIST_STRING,
                )
        return self

    def ltrim(self, substr: str = " ") -> Self:
        """trim LEFT by substr

        - accept STRING, return STRING
        - accept LIST_STRING, return LIST_STRING
        """
        match self.stack_last_ret:
            case VariableType.LIST_STRING:
                self._add(MapLTrimExpression(value=substr))
            case VariableType.STRING:
                self._add(LTrimExpression(value=substr))
            case _:
                self._raise_wrong_type_error(
                    self.stack_last_ret,
                    VariableType.STRING,
                    VariableType.LIST_STRING,
                )
        return self

    def rtrim(self, substr: str = " ") -> Self:
        """trim RIGHT by substr

        - accept STRING, return STRING
        - accept LIST_STRING, return LIST_STRING
        """
        match self.stack_last_ret:
            case VariableType.LIST_STRING:
                self._add(MapRTrimExpression(value=substr))
            case VariableType.STRING:
                self._add(RTrimExpression(value=substr))
            case _:
                self._raise_wrong_type_error(
                    self.stack_last_ret,
                    VariableType.STRING,
                    VariableType.LIST_STRING,
                )
        return self

    def split(self, sep: str) -> Self:
        """split string by sep

        - accept STRING, return LIST_STRING
        """
        self._add(SplitExpression(sep=sep))
        return self

    def fmt(self, fmt_string: str) -> Self:
        """Format string by template.
        Template placeholder should be included `{{}}` marker

        - accept STRING, return STRING
        - accept LIST_STRING, return LIST_STRING
        """
        if "{{}}" not in fmt_string:
            raise SyntaxError("Missing `{{}}` mark in template argument")

        match self.stack_last_ret:
            case VariableType.LIST_STRING:
                self._add(MapFormatExpression(fmt=fmt_string))
            case VariableType.STRING:
                self._add(FormatExpression(fmt=fmt_string))
            case _:
                self._raise_wrong_type_error(
                    self.stack_last_ret,
                    VariableType.STRING,
                    VariableType.LIST_STRING,
                )
        return self

    def repl(self, old: str, new: str) -> Self:
        """Replace all `old` substring with `new` in current string.

        - accept STRING, return STRING
        - accept LIST_STRING, return LIST_STRING
        """
        match self.stack_last_ret:
            case VariableType.LIST_STRING:
                self._add(MapReplaceExpression(old=old, new=new))
            case VariableType.STRING:
                self._add(ReplaceExpression(old=old, new=new))
            case _:
                self._raise_wrong_type_error(
                    self.stack_last_ret,
                    VariableType.STRING,
                    VariableType.LIST_STRING,
                )
        return self

    def re(self, pattern: str | Pattern, group: int = 1) -> Self:
        """extract first regex result.

        NOTE:
            if result not founded - generated code output throw exception (group not founded)

        - accept STRING, return STRING
        """
        pattern = unverbosify_regex(pattern)
        assert_re_expression(pattern)

        if self.stack_last_ret != VariableType.STRING:
            self._raise_wrong_type_error(
                self.stack_last_ret, VariableType.STRING
            )
        self._add(RegexExpression(pattern=pattern, group=group))
        return self

    def re_all(self, pattern: str | Pattern) -> Self:
        """extract all regex results.

        - accept STRING, return LIST_STRING
        """
        pattern = unverbosify_regex(pattern)
        assert_re_expression(pattern, max_groups=1)
        if self.stack_last_ret != VariableType.STRING:
            self._raise_wrong_type_error(
                self.stack_last_ret, VariableType.STRING
            )
        self._add(RegexAllExpression(pattern=pattern))
        return self

    def re_sub(self, pattern: str | Pattern, repl: str = "") -> Self:
        """Replace substring by `pattern` to `repl`.

        - accept STRING, return STRING
        - accept LIST_STRING, return LIST_STRING
        """
        pattern = unverbosify_regex(pattern)
        assert_re_expression(pattern, allow_empty_groups=True)

        match self.stack_last_ret:
            case VariableType.LIST_STRING:
                self._add(MapRegexSubExpression(pattern=pattern, repl=repl))
            case VariableType.STRING:
                self._add(RegexSubExpression(pattern=pattern, repl=repl))
            case _:
                self._raise_wrong_type_error(
                    self.stack_last_ret,
                    VariableType.STRING,
                    VariableType.LIST_STRING,
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
        if self.stack_last_ret != VariableType.DOCUMENT:
            self._raise_wrong_type_error(
                self.stack_last_ret, VariableType.DOCUMENT
            )
        self._add(IsCssExpression(query=query, msg=msg))
        return self

    def is_xpath(self, query: str, msg: str = "") -> Self:
        """assert xpath query found element. If in generated code check failed - throw exception with passed msg

        EXPR DO NOT MODIFY variable

        - accept DOCUMENT, return DOCUMENT
        """
        if self.stack_last_ret != VariableType.DOCUMENT:
            self._raise_wrong_type_error(
                self.stack_last_ret, VariableType.DOCUMENT
            )
        self._add(IsXPathExpression(query=query, msg=msg))
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
            self._raise_wrong_type_error(
                self.stack_last_ret, VariableType.STRING
            )
        elif isinstance(value, int) and self.stack_last_ret != VariableType.INT:
            self._raise_wrong_type_error(self.stack_last_ret, VariableType.INT)
        elif (
            isinstance(value, float)
            and self.stack_last_ret != VariableType.FLOAT
        ):
            self._raise_wrong_type_error(
                self.stack_last_ret, VariableType.FLOAT
            )
        elif self.stack_last_ret not in (
            VariableType.STRING,
            VariableType.INT,
            VariableType.FLOAT,
        ):
            self._raise_wrong_type_error(
                self.stack_last_ret,
                VariableType.STRING,
                VariableType.INT,
                VariableType.FLOAT,
            )
        self._add(IsEqualExpression(value=value, msg=msg))
        return self

    def is_not_equal(self, value: str | int | float, msg: str = "") -> Self:
        """assert not equal by string value. If in generated code check failed - throw exception with passed msg

        EXPR DO NOT MODIFY variable

        - accept STRING, return STRING
        - accept INT, return INT
        - accept FLOAT, return FLOAT
        """
        if (
            isinstance(value, str)
            and self.stack_last_ret != VariableType.STRING
        ):
            self._raise_wrong_type_error(
                self.stack_last_ret, VariableType.STRING
            )
        elif isinstance(value, int) and self.stack_last_ret != VariableType.INT:
            self._raise_wrong_type_error(self.stack_last_ret, VariableType.INT)
        elif (
            isinstance(value, float)
            and self.stack_last_ret != VariableType.FLOAT
        ):
            self._raise_wrong_type_error(
                self.stack_last_ret, VariableType.FLOAT
            )
        elif self.stack_last_ret not in (
            VariableType.STRING,
            VariableType.INT,
            VariableType.FLOAT,
        ):
            self._raise_wrong_type_error(
                self.stack_last_ret,
                VariableType.STRING,
                VariableType.INT,
                VariableType.FLOAT,
            )
        self._add(IsNotEqualExpression(value=value, msg=msg))
        return self

    def is_contains(self, item: str | int | float, msg: str = "") -> Self:
        """assert value contains in sequence. If in generated code check failed - throw exception with passed msg

        EXPR DO NOT MODIFY variable

        - accept LIST_STRING, return LIST_STRING
        """
        if (
            isinstance(item, str)
            and self.stack_last_ret != VariableType.LIST_STRING
        ):
            self._raise_wrong_type_error(
                self.stack_last_ret, VariableType.LIST_STRING
            )
        elif (
            isinstance(item, int)
            and self.stack_last_ret != VariableType.LIST_INT
        ):
            self._raise_wrong_type_error(
                self.stack_last_ret, VariableType.LIST_INT
            )
        elif (
            isinstance(item, float)
            and self.stack_last_ret != VariableType.LIST_FLOAT
        ):
            self._raise_wrong_type_error(
                self.stack_last_ret, VariableType.LIST_FLOAT
            )
        elif self.stack_last_ret not in (
            VariableType.LIST_STRING,
            VariableType.LIST_INT,
            VariableType.LIST_FLOAT,
        ):
            self._raise_wrong_type_error(
                self.stack_last_ret,
                VariableType.LIST_STRING,
                VariableType.LIST_INT,
                VariableType.LIST_FLOAT,
            )
        self._add(IsContainsExpression(item=item, msg=msg))
        return self

    def is_regex(self, pattern: str, msg: str = "") -> Self:
        """assert value matched by regex. If in generated code check failed - throw exception with passed msg

        EXPR DO NOT MODIFY variable

        - accept STRING, return STRING
        """
        if self.stack_last_ret != VariableType.STRING:
            self._raise_wrong_type_error(
                self.stack_last_ret, VariableType.STRING
            )
        assert_re_expression(pattern, allow_empty_groups=True)

        self._add(IsRegexMatchExpression(pattern=pattern, msg=msg))
        return self


class NestedDocument(BaseDocument):
    def sub_parser(self, schema: Type["BaseSchema"]) -> Self:
        """mark parse by `schema` config.

        - accept DOCUMENT, return NESTED
        """
        if self.stack_last_ret == VariableType.NESTED:
            raise SyntaxError("Nested already used")
        if self.stack_last_ret != VariableType.DOCUMENT:
            self._raise_wrong_type_error(
                self.stack_last_ret, VariableType.DOCUMENT
            )
        self._add(NestedExpression(schema_cls=schema))
        return self


class NumericDocument(BaseDocument):
    def to_int(self) -> Self:
        """convert string or sequence of string to integer.

        - accept STRING, return FLOAT
        - accept LIST_STRING, return LIST_FLOAT
        """
        match self.stack_last_ret:
            case VariableType.STRING:
                self._add(ToInteger())
            case VariableType.LIST_STRING:
                self._add(ToListInteger())
            case _:
                self._raise_wrong_type_error(
                    self.stack_last_ret,
                    VariableType.STRING,
                    VariableType.LIST_STRING,
                )
        return self

    def to_float(self) -> Self:
        """convert string or sequence of string to float64 or double.

        - accept STRING, return FLOAT
        - accept LIST_STRING, return LIST_FLOAT
        """
        match self.stack_last_ret:
            case VariableType.STRING:
                self._add(ToFloat())
            case VariableType.LIST_STRING:
                self._add(ToListFloat())
            case _:
                self._raise_wrong_type_error(
                    self.stack_last_ret,
                    VariableType.STRING,
                    VariableType.LIST_STRING,
                )
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
        self._add(ToBool())
        return self


class JsonDocument(BaseDocument):
    def jsonify(self, struct: Type[Json]) -> Self:
        """marshal json string to object

        - accept STRING, return JSON
        """
        if self.stack_last_ret != VariableType.STRING:
            self._raise_wrong_type_error(
                self.stack_last_ret, VariableType.STRING
            )
        self._add(ToJson(value=struct))
        return self
