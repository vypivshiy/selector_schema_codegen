"""ast containers for representation module structure"""
from dataclasses import dataclass, field
from typing import Final, Optional, Type, TYPE_CHECKING

from ssc_codegen.ssc2.consts import M_START_PARSE, M_PRE_VALIDATE, M_SPLIT_DOC, M_VALUE, M_KEY, M_ITEM
from ssc_codegen.ssc2.tokens import TokenType, VariableType, StructType

if TYPE_CHECKING:
    from .schema import BaseSchema

@dataclass(kw_only=True)
class BaseAstNode:
    kind: TokenType


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
    kind: Final[TokenType] = TokenType.IMPORTS


@dataclass(kw_only=True)
class TypeDefField(BaseAstNode):
    kind: Final[TokenType] = TokenType.TYPEDEF_FIELD
    name: str
    type: VariableType
    parent: Optional['TypeDef'] = None

    @property
    def nested_class(self) -> str | None:
        # backport TODO remove:
        if self.type == VariableType.NESTED:
            nested_fn = [fn for fn in self.parent.struct.body if fn.name == self.name][0]
            nested_class = [e for e in nested_fn.body if e.ret_type == VariableType.NESTED][0].schema
            return nested_class
        return None


@dataclass(kw_only=True)
class TypeDef(BaseAstNode):
    """Contains information for typing/annotations"""
    kind: Final[TokenType] = TokenType.TYPEDEF
    name: str
    body: list[TypeDefField]
    struct: Optional['StructParser'] = None

    def __post_init__(self):
        for f in self.body:
            f.parent = self


@dataclass(kw_only=True)
class BaseExpression(BaseAstNode):
    variable: Variable | None = None
    parent: Optional['StructParser'] = None  # LATE INIT
    prev: Optional['BaseExpression'] = None  # LATE INIT
    next: Optional['BaseExpression'] = None  # LATE INIT

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
    schema_cls: Type['BaseSchema']
    accept_type: Final[VariableType] = VariableType.DOCUMENT
    ret_type: Final[VariableType] = VariableType.NESTED

    @property
    def schema(self):
        return self.schema_cls.__name__

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

    @property
    def ret_type(self) -> VariableType:
        if not self.body:
            raise TypeError("Function body empty")
        return self.body[-1].variable.type


@dataclass(kw_only=True)
class StructFieldFunction(__StructNode):
    name: M_ITEM | M_KEY | M_VALUE | str
    kind: Final[TokenType] = TokenType.STRUCT_FIELD
    default: DefaultValueWrapper | None = None
    parent: Optional['StructParser'] = None  # LATE INIT


@dataclass(kw_only=True)
class PreValidateFunction(__StructNode):
    kind: Final[TokenType] = TokenType.STRUCT_PRE_VALIDATE
    name: M_PRE_VALIDATE = '__PRE_VALIDATE__'


@dataclass(kw_only=True)
class PartDocFunction(__StructNode):
    kind: Final[TokenType] = TokenType.STRUCT_PART_DOCUMENT
    name: M_SPLIT_DOC = '__SPLIT_DOC__'


@dataclass(kw_only=True)
class StartParseFunction(__StructNode):
    name: M_START_PARSE = "__START_PARSE__"
    kind: Final[TokenType] = TokenType.STRUCT_PARSE_START
    body: list[CallStructFunctionExpression]
    parent: Optional['StructParser'] = None  # LATE INIT
    type: StructType


@dataclass(kw_only=True)
class StructInit(BaseAstNode):
    kind: Final[TokenType] = TokenType.STRUCT_INIT
    parent: Optional['StructParser'] = None  # LATE INIT
    name: str


@dataclass(kw_only=True)
class StructParser(BaseAstNode):
    kind: Final[TokenType] = TokenType.STRUCT
    init: StructInit = field(init=False)
    docstring_class_top: bool = False
    type: StructType

    name: str
    doc: Docstring
    body: list[StructFieldFunction | StartParseFunction | PreValidateFunction | PartDocFunction]
    typedef: Optional['TypeDef'] = field(init=False)

    def _build_typedef(self):
        ast_typedef = TypeDef(
            name=self.name,
            struct=self,
            body=[
                TypeDefField(name=fn.name, type=fn.ret_type)
                for fn in self.body if fn.kind == TokenType.STRUCT_FIELD
            ]
        )
        self.typedef = ast_typedef

    def __post_init__(self):
        self.init = StructInit(name=self.name, parent=self)
        self._build_typedef()

        self.body.append(
            StartParseFunction(
                parent=self,
                type=self.type,
                body=[CallStructFunctionExpression(name=fn.name, ret_type=VariableType.NULL) for fn in self.body],
            )
        )
        # extend nodes information
        for fn in self.body:
            fn.parent = self
            for i, expr in enumerate(fn.body):
                expr.parent = fn
                if i > 0:
                    expr.prev = fn.body[i - 1]
                if i + 1 < len(fn.body):
                    expr.next = fn.body[i + 1]
