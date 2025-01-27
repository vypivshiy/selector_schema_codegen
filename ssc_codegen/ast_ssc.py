"""ast containers for representation module structure"""

from dataclasses import dataclass, field
from typing import Final, Optional, Type, TYPE_CHECKING, Union

from ssc_codegen.consts import (
    M_START_PARSE,
    M_PRE_VALIDATE,
    M_SPLIT_DOC,
    M_VALUE,
    M_KEY,
    M_ITEM,
)
from ssc_codegen.tokens import TokenType, VariableType, StructType

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
    parent: Optional[Union["StructParser", "ModuleProgram"]] = (
        None  # LATE INIT in builder
    )


@dataclass(kw_only=True)
class ModuleImports(BaseAstNode):
    kind: Final[TokenType] = TokenType.IMPORTS


@dataclass(kw_only=True)
class TypeDefField(BaseAstNode):
    kind: Final[TokenType] = TokenType.TYPEDEF_FIELD
    name: str
    ret_type: VariableType
    parent: Optional["TypeDef"] = None

    @property
    def nested_class(self) -> str | None:
        # backport TODO remove:
        if self.ret_type == VariableType.NESTED:
            nested_fn = [
                fn for fn in self.parent.struct_ref.body if fn.name == self.name
            ][0]
            nested_class = [
                e for e in nested_fn.body if e.ret_type == VariableType.NESTED
            ][0].schema
            return nested_class
        return None


@dataclass(kw_only=True)
class TypeDef(BaseAstNode):
    """Contains information for typing/annotations"""

    kind: Final[TokenType] = TokenType.TYPEDEF
    name: str
    body: list[TypeDefField]
    struct_ref: Optional["StructParser"] = None

    def __post_init__(self):
        for f in self.body:
            f.parent = self


@dataclass(kw_only=True)
class BaseExpression(BaseAstNode):
    variable: Variable | None = None
    parent: Optional[
        Union[
            "StructFieldFunction",
            "StartParseFunction",
            "PreValidateFunction",
            "PartDocFunction",
        ]
    ] = None  # LATE INIT
    prev: Optional["BaseExpression"] = None  # LATE INIT
    next: Optional["BaseExpression"] = None  # LATE INIT

    accept_type: VariableType
    ret_type: VariableType

    def have_default_expr(self) -> bool:
        if not self.parent:
            return False
        if self.parent.body[0].kind == TokenType.EXPR_DEFAULT_START:
            return True
        return False

        # parent = self.parent
        # if parent.kind == TokenType.STRUCT_FIELD and parent.default:
        #    return True

    def have_assert_expr(self) -> bool:
        if not self.parent:
            return False
        if self.parent.kind in (
            TokenType.STRUCT_FIELD,
            TokenType.STRUCT_PRE_VALIDATE,
        ):
            return self.parent.have_assert_expr()
        return False


@dataclass(kw_only=True)
class DefaultValueWrapper(BaseExpression):
    """return default value if expressions in target code fails.
    Should be a first"""

    kind: Final[TokenType] = TokenType.EXPR_DEFAULT

    accept_type: Final[VariableType] = VariableType.ANY
    ret_type: Final[VariableType] = VariableType.ANY
    value: str | None


@dataclass(kw_only=True)
class DefaultStart(BaseExpression):
    kind: Final[TokenType] = TokenType.EXPR_DEFAULT_START
    accept_type: Final[VariableType] = VariableType.ANY
    ret_type: Final[VariableType] = VariableType.ANY
    value: str | None


@dataclass(kw_only=True)
class DefaultEnd(BaseExpression):
    kind: Final[TokenType] = TokenType.EXPR_DEFAULT_END
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
    schema_cls: Type["BaseSchema"]
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

    def have_assert(self) -> bool:
        if self.parent and self.parent.kind == TokenType.STRUCT_FIELD:
            return self.parent.have_assert_expr()
        # try to find by recursion
        if not self.prev:
            return False
        expr = self.prev
        while expr:
            if expr.kind in (
                TokenType.IS_CSS,
                TokenType.IS_EQUAL,
                TokenType.IS_NOT_EQUAL,
                TokenType.IS_CONTAINS,
                TokenType.IS_XPATH,
                TokenType.IS_REGEX_MATCH,
            ):
                return True
            expr = expr.prev
        return False

    def get_default_expr(self) -> None | DefaultValueWrapper:
        if not self.parent:
            return None
        return self.parent.default


@dataclass(kw_only=True)
class NoReturnExpression(BaseExpression):
    kind: Final[TokenType] = TokenType.EXPR_NO_RETURN
    accept_type: Final[VariableType] = VariableType.ANY
    ret_type: Final[VariableType] = VariableType.NULL


@dataclass(kw_only=True)
class CallStructFunctionExpression(BaseExpression):
    kind: Final[TokenType] = TokenType.STRUCT_CALL_FUNCTION
    accept_type: Final[VariableType] = VariableType.DOCUMENT
    fn_ref: Union[
        "StructFieldFunction", "PreValidateFunction", "PartDocFunction", None
    ]
    nested_cls_name_ref: str | None = None
    name: str
    ret_type: VariableType

    def have_assert_expr(self) -> bool:
        if not self.fn_ref:
            return False
        return any(e for e in self.fn_ref.body if e.have_assert_expr())

    def have_default_expr(self) -> bool:
        if not self.fn_ref:
            return False
        return bool(self.fn_ref.default)

    def nested_schema(self) -> Union["StructParser", None]:
        if not self.nested_cls_name_ref:
            return None
        return self.fn_ref.parent


# NUMERIC


@dataclass(kw_only=True)
class ToInteger(BaseExpression):
    kind: Final[TokenType] = TokenType.TO_INT
    accept_type: Final[VariableType] = VariableType.STRING
    ret_type: Final[VariableType] = VariableType.INT


@dataclass(kw_only=True)
class ToListInteger(BaseExpression):
    kind: Final[TokenType] = TokenType.TO_INT_LIST
    accept_type: Final[VariableType] = VariableType.LIST_STRING
    ret_type: Final[VariableType] = VariableType.LIST_INT


@dataclass(kw_only=True)
class ToFloat(BaseExpression):
    kind: Final[TokenType] = TokenType.TO_FLOAT
    accept_type: Final[VariableType] = VariableType.STRING
    ret_type: Final[VariableType] = VariableType.FLOAT


@dataclass(kw_only=True)
class ToListFloat(BaseExpression):
    kind: Final[TokenType] = TokenType.TO_FLOAT_LIST
    accept_type: Final[VariableType] = VariableType.LIST_STRING
    ret_type: Final[VariableType] = VariableType.LIST_FLOAT


# STRUCT


@dataclass(kw_only=True)
class __StructNode(BaseAstNode):
    name: str
    body: list[BaseExpression]

    @property
    def ret_type(self) -> VariableType:
        if not self.body:
            raise TypeError("Function body empty")

        # default expr case
        if self.body[0].kind == TokenType.EXPR_DEFAULT_START:
            return self.body[-2].variable.type
        return self.body[-1].variable.type


@dataclass(kw_only=True)
class StructFieldFunction(__StructNode):
    name: M_ITEM | M_KEY | M_VALUE | str
    kind: Final[TokenType] = TokenType.STRUCT_FIELD
    parent: Optional["StructParser"] = None  # LATE INIT

    def find_associated_typedef(self) -> TypeDef | None:
        if self.ret_type != VariableType.NESTED:
            return None
        elif not self.parent or not self.parent.parent:
            return None

        associated_typedef = [
            fn
            for fn in self.parent.parent.body  # type: ignore
            if getattr(fn, "name", None)
            and fn.name == self.nested_schema_name()  # noqa
            and fn.kind == TokenType.TYPEDEF
        ][0]
        return associated_typedef  # type: ignore

    def nested_schema_name(self) -> str | None:
        if self.ret_type != VariableType.NESTED:
            return None
        # type NestedExpression (naive)
        # last element - ReturnExpr
        return self.body[-2].schema  # noqa

    def have_assert_expr(self) -> bool:
        return any(
            e.kind
            in (
                TokenType.IS_CSS,
                TokenType.IS_EQUAL,
                TokenType.IS_NOT_EQUAL,
                TokenType.IS_CONTAINS,
                TokenType.IS_XPATH,
                TokenType.IS_REGEX_MATCH,
            )
            for e in self.body
            if e
        )


@dataclass(kw_only=True)
class PreValidateFunction(__StructNode):
    kind: Final[TokenType] = TokenType.STRUCT_PRE_VALIDATE
    name: M_PRE_VALIDATE = "__PRE_VALIDATE__"
    parent: Optional["StructParser"] = None  # LATE INIT


@dataclass(kw_only=True)
class PartDocFunction(__StructNode):
    kind: Final[TokenType] = TokenType.STRUCT_PART_DOCUMENT
    name: M_SPLIT_DOC = "__SPLIT_DOC__"
    parent: Optional["StructParser"] = None  # LATE INIT


@dataclass(kw_only=True)
class StartParseFunction(__StructNode):
    name: M_START_PARSE = "__START_PARSE__"
    kind: Final[TokenType] = TokenType.STRUCT_PARSE_START
    body: list[CallStructFunctionExpression]
    type: StructType
    parent: Optional["StructParser"] = None  # LATE INIT

    def have_assert_expr(self) -> bool:
        for expr in self.body:
            if expr.ret_type == VariableType.NESTED and expr.have_assert_expr():
                return True
        return False

    def have_default_expr(self) -> bool:
        for expr in self.body:
            if (
                expr.ret_type == VariableType.NESTED
                and expr.have_default_expr()
            ):
                return True
        return False


@dataclass(kw_only=True)
class StructInit(BaseAstNode):
    kind: Final[TokenType] = TokenType.STRUCT_INIT
    parent: Optional["StructParser"] = None  # LATE INIT
    name: str


@dataclass(kw_only=True)
class StructParser(BaseAstNode):
    kind: Final[TokenType] = TokenType.STRUCT
    init: StructInit = field(init=False)
    docstring_class_top: bool = False
    type: StructType

    name: str
    doc: Docstring
    body: list[
        StructFieldFunction
        | StartParseFunction
        | PreValidateFunction
        | PartDocFunction
    ]
    typedef: Optional["TypeDef"] = field(init=False)
    parent: Optional[ModuleProgram] = None  # LATE INIT

    def _build_typedef(self):
        ast_typedef = TypeDef(
            name=self.name,
            struct_ref=self,
            body=[
                TypeDefField(name=fn.name, ret_type=fn.ret_type)
                for fn in self.body
                if fn.kind == TokenType.STRUCT_FIELD
            ],
        )
        self.typedef = ast_typedef

    def __post_init__(self):
        self.init = StructInit(name=self.name, parent=self)
        self._build_typedef()

        self.body.append(
            StartParseFunction(
                parent=self,
                type=self.type,
                body=[
                    CallStructFunctionExpression(
                        name=fn.name,
                        ret_type=fn.ret_type,
                        fn_ref=fn,
                        nested_cls_name_ref=fn.nested_schema_name()
                        if fn.ret_type == VariableType.NESTED
                        else None,
                    )
                    for fn in self.body
                ],
            )
        )

        # add nodes refs, assigns
        self.doc.parent = self
        for fn in self.body:
            fn.parent = self
            for i, expr in enumerate(fn.body):
                expr.parent = fn
                if i > 0:
                    expr.prev = fn.body[i - 1]
                if i + 1 < len(fn.body):
                    expr.next = fn.body[i + 1]
