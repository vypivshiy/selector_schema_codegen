"""high-level AST builder interface"""
import re
from typing import Optional, Type

from typing_extensions import deprecated, Self

from .ast_ssc import (
    BaseExpression,
    DefaultValueWrapper,

    HtmlCssExpression,
    HtmlXpathAllExpression,
    HtmlCssAllExpression,
    HtmlAttrAllExpression,
    HtmlAttrExpression,
    HtmlTextExpression,
    HtmlTextAllExpression,
    HtmlRawExpression,
    HtmlRawAllExpression,
    HtmlXpathExpression,
    IndexStringExpression,
    IndexDocumentExpression,
    JoinExpression,

    TrimExpression,
    LTrimExpression,
    RTrimExpression,
    FormatExpression,
    RegexExpression,
    RegexAllExpression,
    RegexSubExpression,
    MapFormatExpression,
    MapTrimExpression,
    MapLTrimExpression,
    MapRTrimExpression,
    ReplaceExpression,
    MapReplaceExpression,
    MapRegexSubExpression,
    SplitExpression,

    IsCssExpression,
    IsXPathExpression,
    IsEqualExpression,
    IsNotEqualExpression,
    IsContainsExpression,
    IsRegexMatchExpression, NestedExpression,

)
from .schema import BaseSchema
from .selector_utils import validate_css_query, validate_xpath_query
from .tokens import VariableType


class BaseDocument:
    def __init__(self):
        self._stack: list[BaseExpression] = []

    @property
    def stack(self) -> list[BaseExpression]:
        return self._stack

    @property
    def count(self):
        return len(self._stack)

    @property
    def stack_last_index(self):
        return len(self._stack) - 1 if self._stack else 0

    @property
    def stack_last_ret(self) -> VariableType:
        if len(self._stack) == 0:
            # always Document or Element type
            return VariableType.DOCUMENT
        return self.stack[-1].ret_type

    @staticmethod
    def _raise_wrong_type_error(type_: VariableType, *expected: VariableType):
        fmt_types = '(' + ','.join(i.name for i in expected) + ')'
        msg = f"Expected type(s): {fmt_types}, got {type_.name}"
        raise SyntaxError(msg)

    def _add(self, expr: BaseExpression):
        self._stack.append(expr)

    def __repr__(self):
        return f"Document(count={self.count}, ret_type={self.stack_last_ret.name})"


class DefaultDocument(BaseDocument):
    def default(self, value: Optional[str]) -> Self:
        """Set default value. Accept string or None. raise error if expr is not first"""
        if self.count != 0:
            raise SyntaxError("default expression should be a first")
        self._add(DefaultValueWrapper(value=value))
        return self


class HTMLDocument(BaseDocument):
    def css(self, query: str) -> Self:
        validate_css_query(query)
        match self.stack_last_ret:
            case VariableType.DOCUMENT:
                self._add(HtmlCssExpression(query=query))
            case VariableType.ANY:
                self._add(HtmlCssExpression(query=query))
            case _:
                self._raise_wrong_type_error(self.stack_last_ret, VariableType.DOCUMENT)
        return self

    def xpath(self, query: str) -> Self:
        validate_xpath_query(query)
        match self.stack_last_ret:
            case VariableType.DOCUMENT:
                self._add(HtmlXpathExpression(query=query))
            case VariableType.ANY:
                self._add(HtmlXpathExpression(query=query))
            case _:
                self._raise_wrong_type_error(self.stack_last_ret, VariableType.DOCUMENT)
        return self

    def css_all(self, query: str) -> Self:
        validate_css_query(query)
        match self.stack_last_ret:
            case VariableType.DOCUMENT:
                self._add(HtmlCssAllExpression(query=query))
            case VariableType.ANY:
                self._add(HtmlCssAllExpression(query=query))
            case _:
                self._raise_wrong_type_error(self.stack_last_ret, VariableType.DOCUMENT)
        return self

    def xpath_all(self, query: str) -> Self:
        validate_xpath_query(query)
        match self.stack_last_ret:
            case VariableType.DOCUMENT:
                self._add(HtmlXpathAllExpression(query=query))
            case VariableType.ANY:
                self._add(HtmlXpathAllExpression(query=query))
            case _:
                self._raise_wrong_type_error(self.stack_last_ret, VariableType.DOCUMENT)
        return self

    def attr(self, name: str) -> Self:
        match self.stack_last_ret:
            case VariableType.DOCUMENT:
                self._add(HtmlAttrExpression(attr=name))
            case VariableType.ANY:
                self._add(HtmlAttrExpression(attr=name))
            case VariableType.LIST_DOCUMENT:
                self._add(HtmlAttrAllExpression(attr=name))
            case _:
                self._raise_wrong_type_error(self.stack_last_ret, VariableType.DOCUMENT, VariableType.LIST_DOCUMENT)
        return self

    def text(self) -> Self:
        match self.stack_last_ret:
            case VariableType.DOCUMENT:
                self._add(HtmlTextExpression())
            case VariableType.ANY:
                self._add(HtmlTextExpression())

            case VariableType.LIST_DOCUMENT:
                self._add(HtmlTextAllExpression())
            case _:
                self._raise_wrong_type_error(self.stack_last_ret, VariableType.DOCUMENT, VariableType.LIST_DOCUMENT)
        return self

    def raw(self) -> Self:
        match self.stack_last_ret:
            case VariableType.DOCUMENT:
                self._add(HtmlRawExpression())
            case VariableType.ANY:
                self._add(HtmlRawExpression())
            case VariableType.LIST_DOCUMENT:
                self._add(HtmlRawAllExpression())
            case _:
                self._raise_wrong_type_error(self.stack_last_ret, VariableType.DOCUMENT, VariableType.LIST_DOCUMENT)
        return self


class ArrayDocument(BaseDocument):
    def first(self) -> Self:
        """alias index(0)"""
        return self.index(0)

    def last(self) -> Self:
        """alias index(-1). NOTE: several languages does not support get last index"""
        return self.index(-1)

    def index(self, i: int) -> Self:
        last_ret = self.stack[-1].ret_type
        match last_ret:
            case VariableType.LIST_DOCUMENT:
                self._add(IndexDocumentExpression(value=i))
            case VariableType.LIST_STRING:
                self._add(IndexStringExpression(value=i))
            case _:
                self._raise_wrong_type_error(self.stack_last_ret, VariableType.LIST_STRING, VariableType.LIST_DOCUMENT)
        return self

    def join(self, s: str) -> Self:
        self._add(JoinExpression(sep=s))
        return self


class StringDocument(BaseDocument):
    def trim(self, string: str = " ") -> Self:
        match self.stack_last_ret:
            case VariableType.LIST_STRING:
                self._add(MapTrimExpression(value=string))
            case VariableType.STRING:
                self._add(TrimExpression(value=string))
            case _:
                self._raise_wrong_type_error(self.stack_last_ret, VariableType.STRING, VariableType.LIST_STRING)
        return self

    def ltrim(self, string: str = " ") -> Self:
        match self.stack_last_ret:
            case VariableType.LIST_STRING:
                self._add(MapLTrimExpression(value=string))
            case VariableType.STRING:
                self._add(LTrimExpression(value=string))
            case _:
                self._raise_wrong_type_error(self.stack_last_ret, VariableType.STRING, VariableType.LIST_STRING)
        return self

    def rtrim(self, string: str = " ") -> Self:
        match self.stack_last_ret:
            case VariableType.LIST_STRING:
                self._add(MapRTrimExpression(value=string))
            case VariableType.STRING:
                self._add(RTrimExpression(value=string))
            case _:
                self._raise_wrong_type_error(self.stack_last_ret, VariableType.STRING, VariableType.LIST_STRING)
        return self

    def split(self, sep: str) -> Self:
        self._add(SplitExpression(sep=sep))
        return self

    @deprecated("Use fmt method instead")
    def format(self, fmt_string: str) -> Self:
        return self.fmt(fmt_string)

    def fmt(self, fmt_string: str) -> Self:
        if "{{}}" not in fmt_string:
            raise SyntaxError("Missing `{{}}` mark in template argument")

        match self.stack_last_ret:
            case VariableType.LIST_STRING:
                self._add(MapFormatExpression(fmt=fmt_string))
            case VariableType.STRING:
                self._add(FormatExpression(fmt=fmt_string))
            case _:
                self._raise_wrong_type_error(self.stack_last_ret, VariableType.STRING, VariableType.LIST_STRING)
        return self

    @deprecated("Use repl method instead")
    def replace(self, old: str, new: str) -> Self:
        return self.repl(old, new)

    def repl(self, old: str, new: str) -> Self:
        match self.stack_last_index:
            case VariableType.LIST_STRING:
                self._add(MapReplaceExpression(old=old, new=new))
            case VariableType.STRING:
                self._add(ReplaceExpression(old=old, new=new))
            case _:
                self._raise_wrong_type_error(self.stack_last_ret, VariableType.STRING, VariableType.LIST_STRING)
        return self

    def re(self, pattern: str, group: int = 1) -> Self:
        try:
            re.compile(pattern)
        except re.error as e:
            raise SyntaxError("Wrong regular expression pattern") from e
        self._add(RegexExpression(pattern=pattern, group=group))
        return self

    def re_all(self, pattern: str) -> Self:
        try:
            re.compile(pattern)
        except re.error as e:
            raise SyntaxError("Wrong regular expression pattern") from e

        self._add(RegexAllExpression(pattern=pattern))
        return self

    def re_sub(self, pattern: str, repl: str = "") -> Self:
        try:
            re.compile(pattern)
        except re.error as e:
            raise SyntaxError("Wrong regular expression pattern") from e

        match self.stack_last_index:
            case VariableType.LIST_STRING:
                self._add(MapRegexSubExpression(pattern=pattern, repl=repl))
            case VariableType.STRING:
                self._add(RegexSubExpression(pattern=pattern, repl=repl))
            case _:
                self._raise_wrong_type_error(self.stack_last_ret, VariableType.STRING, VariableType.LIST_STRING)
        return self


class IsRegexExpression:
    pass


class AssertDocument(BaseDocument):
    def is_css(self, query: str, msg: str = "") -> Self:
        self._add(IsCssExpression(query=query, msg=msg))
        return self

    def is_xpath(self, query: str, msg: str = "") -> Self:
        self._add(IsXPathExpression(query=query, msg=msg))
        return self

    def is_equal(self, value: str, msg: str = "") -> Self:
        self._add(IsEqualExpression(value=value, msg=msg))
        return self

    def is_not_equal(self, value: str, msg: str = "") -> Self:
        self._add(IsNotEqualExpression(value=value, msg=msg))
        return self

    def is_contains(self, item: str, msg: str = "") -> Self:
        self._add(IsContainsExpression(item=item, msg=msg))
        return self

    def is_regex(self, pattern: str, msg: str = "") -> Self:
        self._add(IsRegexMatchExpression(pattern=pattern, msg=msg))
        return self


class NestedDocument(BaseDocument):
    def sub_parser(self, schema: Type['BaseSchema']) -> Self:
        self._add(NestedExpression(schema_cls=schema))
        return self
