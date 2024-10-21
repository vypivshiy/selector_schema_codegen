"""ast containers for representation module structure"""
from dataclasses import dataclass
from typing import Final

from ssc_codegen.ssc2.tokens import TokenType, VariableType, StructType


@dataclass(kw_only=True)
class BaseAstNode:
    kind: TokenType
    pass


@dataclass(kw_only=True)
class ModuleProgram(BaseAstNode):
    """Main module entrypoint"""
    kind: Final[TokenType] = TokenType.MODULE
    body: list[BaseAstNode]


@dataclass(kw_only=True)
class Variable(BaseAstNode):
    kind: Final[TokenType] = TokenType.VARIABLE

    num: int
    count: int
    type: VariableType

    @property
    def num_next(self):
        return self.num + 1


@dataclass(kw_only=True)
class Docstring(BaseAstNode):
    kind: Final[TokenType] = TokenType.DOCSTRING
    value: str


@dataclass(kw_only=True)
class ModuleImports(BaseAstNode):
    """required imports for generated parser"""
    kind: Final[TokenType] = TokenType.IMPORTS


@dataclass(kw_only=True)
class TypeDefField(BaseAstNode):
    kind: Final[TokenType] = TokenType.TYPEDEF_FIELD
    name: str
    type: VariableType


@dataclass(kw_only=True)
class TypeDef(BaseAstNode):
    """Contains information for typing/annotations"""
    kind: Final[TokenType] = TokenType.TYPEDEF
    name: str
    body: list[TypeDefField]


# ExpressionS
@dataclass(kw_only=True)
class BaseExpression(BaseAstNode):
    variable: Variable | None = None
    accept_type: VariableType
    ret_type: VariableType


@dataclass(kw_only=True)
class DefaultValueWrapper(BaseExpression):
    """return default value if expressions in target code fails.
    Should be a first"""
    kind: Final[TokenType] = TokenType.EXPR_DEFAULT

    accept_type: Final[VariableType] = VariableType.ANY
    ret_type: Final[VariableType] = VariableType.ANY
    value: str | None


# DOCUMENT
@dataclass(kw_only=True)
class HtmlCssExpression(BaseExpression):
    kind: Final[TokenType] = TokenType.EXPR_CSS
    query: str
    accept_type: Final[VariableType] = VariableType.DOCUMENT
    ret_type: Final[VariableType] = VariableType.DOCUMENT


@dataclass(kw_only=True)
class HtmlCssAllExpression(BaseExpression):
    kind: Final[TokenType] = TokenType.EXPR_CSS_ALL

    query: str
    accept_type: Final[VariableType] = VariableType.DOCUMENT
    ret_type: Final[VariableType] = VariableType.LIST_DOCUMENT


@dataclass(kw_only=True)
class HtmlXpathExpression(BaseExpression):
    kind: Final[TokenType] = TokenType.EXPR_XPATH

    query: str
    accept_type: Final[VariableType] = VariableType.DOCUMENT
    ret_type: Final[VariableType] = VariableType.DOCUMENT


@dataclass(kw_only=True)
class HtmlXpathAllExpression(BaseExpression):
    kind: Final[TokenType] = TokenType.EXPR_XPATH_ALL

    query: str
    accept_type: Final[VariableType] = VariableType.DOCUMENT
    ret_type: Final[VariableType] = VariableType.LIST_DOCUMENT


@dataclass(kw_only=True)
class HtmlAttrExpression(BaseExpression):
    kind: Final[TokenType] = TokenType.EXPR_ATTR

    attr: str
    accept_type: Final[VariableType] = VariableType.DOCUMENT
    ret_type: Final[VariableType] = VariableType.STRING


@dataclass(kw_only=True)
class HtmlAttrAllExpression(BaseExpression):
    kind: Final[TokenType] = TokenType.EXPR_ATTR_ALL
    attr: str
    accept_type: Final[VariableType] = VariableType.LIST_DOCUMENT
    ret_type: Final[VariableType] = VariableType.LIST_STRING


@dataclass(kw_only=True)
class HtmlRawExpression(BaseExpression):
    kind: Final[TokenType] = TokenType.EXPR_RAW
    accept_type: Final[VariableType] = VariableType.DOCUMENT
    ret_type: Final[VariableType] = VariableType.STRING


@dataclass(kw_only=True)
class HtmlRawAllExpression(BaseExpression):
    kind: Final[TokenType] = TokenType.EXPR_RAW_ALL

    accept_type: Final[VariableType] = VariableType.LIST_DOCUMENT
    ret_type: Final[VariableType] = VariableType.LIST_STRING


@dataclass(kw_only=True)
class HtmlTextAllExpression(BaseExpression):
    kind: Final[TokenType] = TokenType.EXPR_TEXT_ALL
    accept_type: Final[VariableType] = VariableType.LIST_DOCUMENT
    ret_type: Final[VariableType] = VariableType.LIST_STRING


@dataclass(kw_only=True)
class HtmlTextExpression(BaseExpression):
    kind: Final[TokenType] = TokenType.EXPR_TEXT
    accept_type: Final[VariableType] = VariableType.DOCUMENT
    ret_type: Final[VariableType] = VariableType.STRING


# ARRAY
@dataclass(kw_only=True)
class IndexDocumentExpression(BaseExpression):
    kind: Final[TokenType] = TokenType.EXPR_LIST_DOCUMENT_INDEX

    value: int
    accept_type: Final[VariableType] = VariableType.LIST_DOCUMENT
    ret_type: Final[VariableType] = VariableType.DOCUMENT


@dataclass(kw_only=True)
class IndexStringExpression(BaseExpression):
    kind: Final[TokenType] = TokenType.EXPR_LIST_STRING_INDEX

    value: int
    accept_type: Final[VariableType] = VariableType.LIST_STRING
    ret_type: Final[VariableType] = VariableType.STRING


@dataclass(kw_only=True)
class JoinExpression(BaseExpression):
    kind: Final[TokenType] = TokenType.EXPR_LIST_JOIN

    sep: str
    accept_type: Final[VariableType] = VariableType.LIST_STRING
    ret_type: Final[VariableType] = VariableType.STRING


# STRING
@dataclass(kw_only=True)
class __TrimNode(BaseExpression):
    value: str
    accept_type: Final[VariableType] = VariableType.STRING
    ret_type: Final[VariableType] = VariableType.STRING


@dataclass(kw_only=True)
class TrimExpression(__TrimNode):
    kind: Final[TokenType] = TokenType.EXPR_STRING_TRIM


@dataclass(kw_only=True)
class LTrimExpression(__TrimNode):
    kind: Final[TokenType] = TokenType.EXPR_STRING_LTRIM


@dataclass(kw_only=True)
class RTrimExpression(__TrimNode):
    kind: Final[TokenType] = TokenType.EXPR_STRING_RTRIM


@dataclass(kw_only=True)
class __MapTrimNode(BaseExpression):
    value: str
    accept_type: Final[VariableType] = VariableType.LIST_STRING
    ret_type: Final[VariableType] = VariableType.LIST_STRING


@dataclass(kw_only=True)
class MapTrimExpression(__MapTrimNode):
    kind: Final[TokenType] = TokenType.EXPR_LIST_STRING_TRIM


@dataclass(kw_only=True)
class MapLTrimExpression(__MapTrimNode):
    kind: Final[TokenType] = TokenType.EXPR_LIST_STRING_LTRIM


@dataclass(kw_only=True)
class MapRTrimExpression(__MapTrimNode):
    kind: Final[TokenType] = TokenType.EXPR_LIST_STRING_RTRIM


@dataclass(kw_only=True)
class SplitExpression(BaseExpression):
    kind: Final[TokenType] = TokenType.EXPR_STRING_SPLIT
    sep: str
    accept_type: Final[VariableType] = VariableType.STRING
    ret_type: Final[VariableType] = VariableType.LIST_STRING


@dataclass(kw_only=True)
class FormatExpression(BaseExpression):
    kind: Final[TokenType] = TokenType.EXPR_STRING_FORMAT
    fmt: str
    accept_type: Final[VariableType] = VariableType.STRING
    ret_type: Final[VariableType] = VariableType.STRING


@dataclass(kw_only=True)
class MapFormatExpression(BaseExpression):
    kind: Final[TokenType] = TokenType.EXPR_LIST_STRING_FORMAT
    fmt: str
    accept_type: Final[VariableType] = VariableType.LIST_STRING
    ret_type: Final[VariableType] = VariableType.LIST_STRING


@dataclass(kw_only=True)
class ReplaceExpression(BaseExpression):
    kind: Final[TokenType] = TokenType.EXPR_STRING_REPLACE
    old: str
    new: str
    accept_type: Final[VariableType] = VariableType.STRING
    ret_type: Final[VariableType] = VariableType.STRING


@dataclass(kw_only=True)
class MapReplaceExpression(BaseExpression):
    kind: Final[TokenType] = TokenType.EXPR_LIST_STRING_REPLACE
    old: str
    new: str
    accept_type: Final[VariableType] = VariableType.LIST_STRING
    ret_type: Final[VariableType] = VariableType.LIST_STRING


# REGEX
@dataclass(kw_only=True)
class RegexExpression(BaseExpression):
    kind: Final[TokenType] = TokenType.EXPR_REGEX

    pattern: str
    group: int
    accept_type: Final[VariableType] = VariableType.STRING
    ret_type: Final[VariableType] = VariableType.STRING


@dataclass(kw_only=True)
class RegexAllExpression(BaseExpression):
    kind: Final[TokenType] = TokenType.EXPR_REGEX_ALL

    pattern: str
    accept_type: Final[VariableType] = VariableType.STRING
    ret_type: Final[VariableType] = VariableType.LIST_STRING


@dataclass(kw_only=True)
class RegexSubExpression(BaseExpression):
    kind: Final[TokenType] = TokenType.EXPR_REGEX_SUB

    pattern: str
    repl: str
    accept_type: Final[VariableType] = VariableType.STRING
    ret_type: Final[VariableType] = VariableType.STRING


@dataclass(kw_only=True)
class MapRegexSubExpression(BaseExpression):
    kind: Final[TokenType] = TokenType.EXPR_LIST_REGEX_SUB

    pattern: str
    repl: str
    accept_type: Final[VariableType] = VariableType.LIST_STRING
    ret_type: Final[VariableType] = VariableType.LIST_STRING


# asserts - validators - not modify variables
@dataclass(kw_only=True)
class IsEqualExpression(BaseExpression):
    kind: Final[TokenType] = TokenType.IS_EQUAL

    value: str
    msg: str
    accept_type: Final[VariableType] = VariableType.STRING
    ret_type: Final[VariableType] = VariableType.STRING


@dataclass(kw_only=True)
class IsNotEqualExpression(BaseExpression):
    kind: Final[TokenType] = TokenType.IS_NOT_EQUAL

    value: str
    msg: str
    accept_type: Final[VariableType] = VariableType.STRING
    ret_type: Final[VariableType] = VariableType.STRING


@dataclass(kw_only=True)
class IsCssExpression(BaseExpression):
    kind: Final[TokenType] = TokenType.IS_CSS
    query: str
    msg: str
    accept_type: Final[VariableType] = VariableType.DOCUMENT
    ret_type: Final[VariableType] = VariableType.DOCUMENT


@dataclass(kw_only=True)
class IsXPathExpression(BaseExpression):
    kind: Final[TokenType] = TokenType.IS_XPATH
    query: str
    msg: str
    accept_type: Final[VariableType] = VariableType.DOCUMENT
    ret_type: Final[VariableType] = VariableType.DOCUMENT


@dataclass(kw_only=True)
class IsContainsExpression(BaseExpression):
    kind: Final[TokenType] = TokenType.IS_CONTAINS
    item: str
    msg: str
    accept_type: Final[VariableType] = VariableType.LIST_STRING
    ret_type: Final[VariableType] = VariableType.LIST_STRING


@dataclass(kw_only=True)
class IsRegexMatchExpression(BaseExpression):
    kind: Final[TokenType] = TokenType.IS_REGEX_MATCH
    pattern: str
    msg: str
    accept_type: Final[VariableType] = VariableType.STRING
    ret_type: Final[VariableType] = VariableType.STRING


@dataclass(kw_only=True)
class NestedExpression(BaseExpression):
    kind: Final[TokenType] = TokenType.EXPR_NESTED
    schema: str

    accept_type: Final[VariableType] = VariableType.DOCUMENT
    ret_type: Final[VariableType] = VariableType.NESTED


@dataclass(kw_only=True)
class ReturnExpression(BaseExpression):
    kind: Final[TokenType] = TokenType.EXPR_RETURN
    accept_type: Final[VariableType] = VariableType.ANY
    ret_type: Final[VariableType] = VariableType.ANY


@dataclass(kw_only=True)
class NoReturnExpression(BaseExpression):
    kind: Final[TokenType] = TokenType.EXPR_NO_RETURN
    accept_type: Final[VariableType] = VariableType.ANY
    ret_type: Final[VariableType] = VariableType.NULL


@dataclass(kw_only=True)
class CallStructFunctionExpression(BaseExpression):
    kind: Final[TokenType] = TokenType.STRUCT_CALL_FUNCTION
    accept_type: Final[VariableType] = VariableType.DOCUMENT
    name: str
    ret_type: VariableType


# STRUCT

@dataclass(kw_only=True)
class __StructNode(BaseAstNode):
    name: str
    body: list[BaseExpression]


@dataclass(kw_only=True)
class StructFieldFunction(__StructNode):
    kind: Final[TokenType] = TokenType.STRUCT_FIELD
    default: DefaultValueWrapper | None = None


@dataclass(kw_only=True)
class PreValidateFunction(__StructNode):
    kind: Final[TokenType] = TokenType.STRUCT_PRE_VALIDATE


@dataclass(kw_only=True)
class PartDocFunction(__StructNode):
    kind: Final[TokenType] = TokenType.STRUCT_PART_DOCUMENT


@dataclass(kw_only=True)
class StartParseFunction(__StructNode):
    """entrypoint parser"""
    name: str = "__START_PARSE__"  # todo: literal
    kind: Final[TokenType] = TokenType.STRUCT_PARSE_START
    body: list[CallStructFunctionExpression]
    parent: 'StructParser'
    typedef_signature: TypeDef
    type: StructType


@dataclass(kw_only=True)
class StructInit(BaseAstNode):
    kind: Final[TokenType] = TokenType.STRUCT_INIT

@dataclass(kw_only=True)
class StructParser(BaseAstNode):
    kind: Final[TokenType] = TokenType.STRUCT
    init: Final[StructInit] = StructInit()
    type: StructType
    name: str
    doc: Docstring
    body: list[StructFieldFunction | StartParseFunction | PreValidateFunction | PartDocFunction]
