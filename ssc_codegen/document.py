import warnings
from contextlib import contextmanager
from typing import Optional

from ssc_codegen.objects import VariableState, Expression, TokenType
from ssc_codegen.queries import validate_css_query, validate_xpath_query, css_to_xpath, xpath_to_css

class BaseDocumentOperations:
    def __init__(self):
        self.counter = 1
        self.variable_state = VariableState.DOCUMENT
        self._stack: list[Expression] = []

    def __repr__(self):
        comma_stack = ", ".join([f"{e.token_type.name}{e.arguments}" for e in self._stack])
        return f"Document(len={len(self._stack)}, state={self.variable_state.name}, commands={comma_stack})"

    @property
    def get_stack(self) -> list[Expression]:
        return self._stack

    def append(self, expression: Expression):
        self._stack.append(expression)

    def insert(self, i: int, expression: Expression):
        self._stack.insert(i, expression)

    def pop(self, i: int = -1) -> Expression:
        return self._stack.pop(i)

    def _push(self, expression: Expression, var_state: Optional[VariableState] = None):
        if var_state:
            self.variable_state = var_state
        self._stack.append(expression)
        self.counter += 1

    def _is_valid_variable(self, *variables: VariableState) -> bool:
        if self.variable_state in variables:
            return True
        msg = f"Excepted type(s) {tuple(v.name for v in variables)}, got {self.variable_state.name}"
        raise Exception(msg)

    @contextmanager
    def default(self, value: Optional[str]):
        """Set default value. Accept string or None"""
        if self.counter != 1:
            raise Exception("default operation should be first")
        e = Expression(self.counter,
                       self.variable_state,
                       TokenType.OP_DEFAULT,
                       (value,))
        self._push(e)
        yield self


class ArrayOpDocument(BaseDocumentOperations):
    """operations with array"""

    def first(self):
        """alias index(0)"""
        return self.index(0)

    def last(self):
        """alias index(-1)"""
        return self.index(-1)

    # ARRAY
    def index(self, i: int):
        """get element by index"""
        self._is_valid_variable(VariableState.LIST_STRING, VariableState.LIST_DOCUMENT)
        e = Expression(self.counter,
                       self.variable_state,
                       TokenType.OP_INDEX,
                       (i,))
        if self.variable_state is VariableState.LIST_DOCUMENT:
            self._push(e, var_state=VariableState.DOCUMENT)
        else:
            self._push(e, var_state=VariableState.STRING)
        return self

    def join(self, prefix: str):
        """join list of sting to array"""
        self._is_valid_variable(VariableState.LIST_STRING)
        e = Expression(self.counter,
                       self.variable_state,
                       TokenType.OP_JOIN,
                       (prefix,))
        self._push(e, var_state=VariableState.STRING)
        return self


class RegexOpDocument(BaseDocumentOperations):
    def re(self, expr: str):
        """get first match by regular expression"""
        self._is_valid_variable(VariableState.STRING)
        e = Expression(self.counter,
                       self.variable_state,
                       TokenType.OP_REGEX,
                       (expr,))
        self._push(e)
        return self

    def re_all(self, expr: str):
        """get all matches by regular expression"""
        self._is_valid_variable(VariableState.STRING)
        e = Expression(self.counter,
                       self.variable_state,
                       TokenType.OP_REGEX_ALL,
                       (expr,))
        self._push(e, var_state=VariableState.LIST_STRING)
        return self

    def re_sub(self, pattern: str, repl: str):
        self._is_valid_variable(VariableState.STRING)
        e = Expression(self.counter,
                       self.variable_state,
                       TokenType.OP_REGEX_SUB,
                       (pattern, repl))
        self._push(e)
        return self


class StringOpDocument(BaseDocumentOperations):
    def lstrip(self, prefix: str):
        """remove prefix from string (from left)"""
        self._is_valid_variable(VariableState.STRING, VariableState.LIST_STRING)
        e = Expression(self.counter,
                       self.variable_state,
                       TokenType.OP_STRING_L_TRIM,
                       (prefix,))
        self._push(e)
        return self

    def rstrip(self, suffix: str):
        """remove suffix from string (from right)"""
        self._is_valid_variable(VariableState.STRING, VariableState.LIST_STRING)
        e = Expression(self.counter,
                       self.variable_state,
                       TokenType.OP_STRING_R_TRIM,
                       (suffix,))
        self._push(e)
        return self

    def strip(self, sting: str):
        """strip string from string (from left and right)"""
        self._is_valid_variable(VariableState.STRING, VariableState.LIST_STRING)
        e = Expression(self.counter,
                       self.variable_state,
                       TokenType.OP_STRING_TRIM,
                       (sting,))
        self._push(e)
        return self

    def format(self, fmt: str):
        """format string by pattern.

        fmt argument should be contained {{}} mark"""
        self._is_valid_variable(VariableState.STRING, VariableState.LIST_STRING)
        if "{{}}" not in fmt:
            raise Exception("Missing `{{}}` mark")
        e = Expression(self.counter,
                       self.variable_state,
                       TokenType.OP_STRING_FORMAT,
                       (fmt,))
        self._push(e)
        return self

    def split(self, sep: str):
        """split string by `sep` argument"""
        self._is_valid_variable(VariableState.STRING)
        e = Expression(self.counter,
                       self.variable_state,
                       TokenType.OP_STRING_SPLIT,
                       (sep,))
        self._push(e, var_state=VariableState.LIST_STRING)
        return self

    def replace(self, old: str, new: str):
        """replace `old` arg in string in all places to `new` """
        self._is_valid_variable(VariableState.STRING, VariableState.LIST_STRING)
        e = Expression(self.counter,
                       self.variable_state,
                       TokenType.OP_STRING_REPLACE,
                       (old, new))
        self._push(e)
        return self


class HtmlOpDocument(BaseDocumentOperations):

    def convert_css_to_xpath(self, xpath_prefix: str = "descendant-or-self::") -> None:
        """convert all css operations to XPATH (guaranteed)"""
        expr: Expression

        stack_copy = self.get_stack.copy()
        for i, expr in enumerate(stack_copy):
            if expr.token_type == TokenType.OP_CSS:
                css_query = expr.arguments[0]
                new_query = css_to_xpath(css_query, xpath_prefix)
                stack_copy[i] = Expression(
                    num=expr.num,
                    arguments=(new_query,),
                    token_type=TokenType.OP_XPATH,
                    message=expr.message,
                    variable_state=expr.variable_state
                )

            elif expr.token_type == TokenType.OP_CSS_ALL:
                css_query = expr.arguments[0]
                new_query = css_to_xpath(css_query, xpath_prefix)
                stack_copy[i] = Expression(
                    num=expr.num,
                    arguments=(new_query,),
                    token_type=TokenType.OP_XPATH_ALL,
                    message=expr.message,
                    variable_state=expr.variable_state
                )

            elif expr.token_type == TokenType.OP_ASSERT_CSS:
                css_query = expr.arguments[0]
                new_query = css_to_xpath(css_query, xpath_prefix)
                stack_copy[i] = Expression(
                    num=expr.num,
                    arguments=(new_query,),
                    token_type=TokenType.OP_ASSERT_XPATH,
                    message=expr.message,
                    variable_state=expr.variable_state
                )
        self._stack = stack_copy

    def convert_xpath_to_css(self):
        """convert all css operations to XPATH (works with simple expressions)"""
        expr: Expression
        stack_copy = self.get_stack.copy()
        for i, expr in enumerate(stack_copy):
            if expr.token_type == TokenType.OP_XPATH:
                xpath_query = expr.arguments[0]
                new_query = xpath_to_css(xpath_query)
                stack_copy[i] = Expression(
                    num=expr.num,
                    arguments=(new_query,),
                    token_type=TokenType.OP_CSS,
                    message=expr.message,
                    variable_state=expr.variable_state
                )

            elif expr.token_type == TokenType.OP_XPATH_ALL:
                xpath_query = expr.arguments[0]
                new_query = xpath_to_css(xpath_query)
                stack_copy[i] = Expression(
                    num=expr.num,
                    arguments=(new_query,),
                    token_type=TokenType.OP_CSS_ALL,
                    message=expr.message,
                    variable_state=expr.variable_state
                )

            elif expr.token_type == TokenType.OP_ASSERT_XPATH:
                xpath_query = expr.arguments[0]
                new_query = xpath_to_css(xpath_query)
                stack_copy[i] = Expression(
                    num=expr.num,
                    arguments=(new_query,),
                    token_type=TokenType.OP_ASSERT_CSS,
                    message=expr.message,
                    variable_state=expr.variable_state
                )

    def css(self, query: str):
        """get first element by css query"""
        validate_css_query(query)
        self._is_valid_variable(VariableState.DOCUMENT)
        e = Expression(self.counter,
                       self.variable_state,
                       TokenType.OP_CSS,
                       (query,))
        self._push(e)
        return self

    def xpath(self, query: str):
        """get first element by xpath query"""
        validate_xpath_query(query)
        self._is_valid_variable(VariableState.DOCUMENT)
        e = Expression(self.counter,
                       self.variable_state,
                       TokenType.OP_XPATH,
                       (query,))
        self._push(e)
        return self

    def css_all(self, query: str):
        """get all elements by css query"""
        validate_css_query(query)
        self._is_valid_variable(VariableState.DOCUMENT)
        e = Expression(self.counter,
                       self.variable_state,
                       TokenType.OP_CSS_ALL,
                       (query,))
        self._push(e, var_state=VariableState.LIST_DOCUMENT)
        return self

    def xpath_all(self, query: str):
        """get all elements by xpath query"""
        validate_xpath_query(query)
        self._is_valid_variable(VariableState.DOCUMENT)
        e = Expression(self.counter,
                       self.variable_state,
                       TokenType.OP_XPATH_ALL,
                       (query,))
        self._push(e, var_state=VariableState.LIST_DOCUMENT)
        return self

    def attr(self, name: str):
        """get attribute value from element"""
        self._is_valid_variable(VariableState.DOCUMENT, VariableState.LIST_DOCUMENT)
        e = Expression(self.counter,
                       self.variable_state,
                       TokenType.OP_ATTR,
                       (name,))
        if self.variable_state is VariableState.DOCUMENT:
            self._push(e, var_state=VariableState.STRING)
        else:
            self._push(e, var_state=VariableState.LIST_STRING)
        return self

    def text(self):
        """get inner text from element"""
        self._is_valid_variable(VariableState.DOCUMENT, VariableState.LIST_DOCUMENT)
        e = Expression(self.counter,
                       self.variable_state,
                       TokenType.OP_ATTR_TEXT,
                       ())
        if self.variable_state is VariableState.DOCUMENT:
            self._push(e, var_state=VariableState.STRING)
        else:
            self._push(e, var_state=VariableState.LIST_STRING)
        return self

    def raw(self):
        """get raw element tag"""
        self._is_valid_variable(VariableState.DOCUMENT, VariableState.LIST_DOCUMENT)
        e = Expression(self.counter,
                       self.variable_state,
                       TokenType.OP_ATTR_TEXT,
                       ())
        if self.variable_state is VariableState.DOCUMENT:
            self._push(e, var_state=VariableState.STRING)
        else:
            self._push(e, var_state=VariableState.LIST_STRING)
        return self


class Document(ArrayOpDocument,
               RegexOpDocument,
               StringOpDocument,
               HtmlOpDocument):
    """Base document-like attribute provide DSL parser logic for generating code"""
    pass
