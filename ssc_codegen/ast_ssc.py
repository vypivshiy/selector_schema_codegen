"""ast containers for representation module structure"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar, Optional, Type, Union

from ssc_codegen.consts import (
    M_ITEM,
    M_KEY,
    M_PRE_VALIDATE,
    M_SPLIT_DOC,
    M_START_PARSE,
    M_VALUE,
)
from ssc_codegen.tokens import (
    StructType,
    TokenType,
    VariableType,
    JsonVariableType,
)
from .json_struct import BaseJsonType, JsonObject, Json

if TYPE_CHECKING:
    from .schema import BaseSchema


_EXPR_I_START = 0
"""marks first expression in body"""
_EXPR_I_RETURN = -1
"""default return expression in body"""
_EXPR_I_DEFAULT_END = -2
"""default return expression if body wrapped in DEFAULT_START and DEFAULT_END"""


@dataclass(kw_only=True)
class BaseAstNode:
    """base AST container"""

    kind: ClassVar[TokenType]


@dataclass(kw_only=True)
class ModuleProgram(BaseAstNode):
    """Main module entrypoint"""

    kind: ClassVar[TokenType] = TokenType.MODULE
    body: list[BaseAstNode]


@dataclass(kw_only=True)
class Variable(BaseAstNode):
    """represent Variable object

    - num - number of variable
    - count - count of variables in body expressions
    - type - type of variable
    """

    kind: ClassVar[TokenType] = TokenType.VARIABLE

    num: int
    count: int
    type: VariableType

    @property
    def num_next(self) -> int:
        """return next variable number in body.

        used for counter var name
        """
        return self.num + 1

    def __repr__(self) -> str:
        return (
            f"{self.kind.name!r}({self.num!r} of {self.count!r}) {self.type!r}"
        )


@dataclass(kw_only=True)
class Docstring(BaseAstNode):
    """represent docstring Node. Required formatting for language target

    - value - docstring value
    - parent - link to the node to which the docstring belongs
    """

    kind: ClassVar[TokenType] = TokenType.DOCSTRING
    value: str
    parent: Optional[Union["StructParser", "ModuleProgram"]] = field(
        default=None, repr=False
    )


@dataclass(kw_only=True)
class ModuleImports(BaseAstNode):
    """represent imports node. Always constant value, later fix code formatter"""

    kind: ClassVar[TokenType] = TokenType.IMPORTS


@dataclass(kw_only=True)
class TypeDefField(BaseAstNode):
    """represent type definition field or structure

    name - field name in schema
    ret_type - field's type
    parent - link to the parent 'TypeDef' node
    """

    kind: ClassVar[TokenType] = TokenType.TYPEDEF_FIELD
    name: str
    ret_type: VariableType
    parent: Optional["TypeDef"] = field(default=None, repr=False)

    @property
    def nested_class(self) -> str | None:
        """return name link of original schema"""
        # backport TODO remove:
        if self.ret_type == VariableType.NESTED:
            nested_fn = [
                fn
                for fn in self.parent.struct_ref.body  # type: ignore[union-attr]
                if fn.name == self.name  # type: ignore[union-attr]
            ][_EXPR_I_START]  # type: ignore
            nested_class = [
                e for e in nested_fn.body if e.ret_type == VariableType.NESTED
            ][_EXPR_I_START].schema  # type: ignore
            return nested_class
        return None

    @property
    def nested_node_ref(self) -> Union["StructParser", None]:
        """return association StructParser node if ret_type NESTED"""
        if self.ret_type != VariableType.NESTED:
            return None
        return [
            i
            for i in self.parent.parent.body  # type: ignore
            if i.kind == TokenType.STRUCT and i.name == self.nested_class  # noqa
        ][_EXPR_I_START]


@dataclass(kw_only=True)
class TypeDef(BaseAstNode):
    """Helper node for generate typing or annotations

    - name - typedef name (without prefix, get link of original schema target
    - body - typedef fields for annotating
    - struct_ref - link to the parent 'StructParser' node
    """

    kind: ClassVar[TokenType] = TokenType.TYPEDEF
    name: str
    body: list[TypeDefField]
    struct_ref: Optional["StructParser"] = field(default=None, repr=False)
    parent: Optional[ModuleProgram] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        for f in self.body:
            f.parent = self


@dataclass(kw_only=True)
class BaseExpression(BaseAstNode):
    """build-in Expression node

    - variable - container with Variable node
    - parent - link to parent node
    - prev - shortcut for get previous Expression node
    - next - shortcut for get next Expression node
    - accept_type - expression accept type marks
    - ret_type - return type after expression calls
    """

    variable: Variable | None = None
    parent: Optional[
        Union[
            "StructFieldFunction",
            "StartParseFunction",
            "PreValidateFunction",
            "PartDocFunction",
        ]
    ] = field(init=False, repr=False)  # LATE INIT
    prev: Optional["BaseExpression"] = field(
        default=None, repr=False
    )  # LATE INIT
    next: Optional["BaseExpression"] = field(
        default=None, repr=False
    )  # LATE INIT

    accept_type: VariableType
    ret_type: VariableType

    def have_default_expr(self) -> bool:
        """return true if body of expressions has default wrapper"""
        if not self.parent:
            return False
        if self.parent.body[_EXPR_I_START].kind == TokenType.EXPR_DEFAULT_START:
            return True
        return False

        # parent = self.parent
        # if parent.kind == TokenType.STRUCT_FIELD and parent.default:
        #    return True

    def have_assert_expr(self) -> bool:
        """return true if body of expressions has assertion expressions"""
        if not self.parent:
            return False
        if self.parent.kind in (
            TokenType.STRUCT_FIELD,
            TokenType.STRUCT_PRE_VALIDATE,
        ):
            return self.parent.have_assert_expr()  # type: ignore
        return False


@dataclass(kw_only=True)
class DefaultValueWrapper(BaseExpression):
    """return default value if expressions in target code fails. in AST auto insert in start position
    DefaultStart and in end position DefaultEnd

    - Should be a first

    """

    kind: ClassVar[TokenType] = TokenType.EXPR_DEFAULT

    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT
    value: str | int | float | bool | None


@dataclass(kw_only=True)
class DefaultStart(BaseExpression):
    """mark node were stats default expression

    it is assumed that the statement will start with `try` stmt or analogs

    if block of instructions throws any exception - returns default value
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_DEFAULT_START
    accept_type: VariableType = VariableType.ANY
    ret_type: VariableType = VariableType.ANY
    value: str | int | float | bool | None


@dataclass(kw_only=True)
class DefaultEnd(BaseExpression):
    """mark node were ends default expression

    it is assumed that the statement will start with `catch | exception` stmt or analogs

    if block of instructions throws any exception - returns default value

    """

    kind: ClassVar[TokenType] = TokenType.EXPR_DEFAULT_END
    accept_type: VariableType = VariableType.ANY
    ret_type: VariableType = VariableType.ANY
    value: str | int | float | bool | None


# DOCUMENT
@dataclass(kw_only=True)
class HtmlCssExpression(BaseExpression):
    """mark node were calls `CSS` query and extract first founded element"""

    kind: ClassVar[TokenType] = TokenType.EXPR_CSS
    query: str
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT


@dataclass(kw_only=True)
class HtmlCssAllExpression(BaseExpression):
    """mark node were calls `CSS` query and extract all founded element"""

    kind: ClassVar[TokenType] = TokenType.EXPR_CSS_ALL

    query: str
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.LIST_DOCUMENT


@dataclass(kw_only=True)
class HtmlXpathExpression(BaseExpression):
    """mark node where calls `XPATH` query and extract first founded element"""

    kind: ClassVar[TokenType] = TokenType.EXPR_XPATH

    query: str
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT


@dataclass(kw_only=True)
class HtmlXpathAllExpression(BaseExpression):
    """mark node where calls `XPATH` query and extract all founded element"""

    kind: ClassVar[TokenType] = TokenType.EXPR_XPATH_ALL

    query: str
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.LIST_DOCUMENT


@dataclass(kw_only=True)
class HtmlAttrExpression(BaseExpression):
    """mark node where extract attribute value by key for html element

    should be returns string: if lib parse attrs to List<String> type - convert to string
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_ATTR

    attr: str
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class HtmlAttrAllExpression(BaseExpression):
    """mark node where extract attributes value by key from all html element

    should be returns string: if lib parse attrs to List<String> type - convert to string
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_ATTR_ALL
    attr: str
    accept_type: VariableType = VariableType.LIST_DOCUMENT
    ret_type: VariableType = VariableType.LIST_STRING


@dataclass(kw_only=True)
class HtmlRawExpression(BaseExpression):
    """extract raw html from element"""

    kind: ClassVar[TokenType] = TokenType.EXPR_RAW
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class HtmlRawAllExpression(BaseExpression):
    """extract all raw html from elements"""

    kind: ClassVar[TokenType] = TokenType.EXPR_RAW_ALL

    accept_type: VariableType = VariableType.LIST_DOCUMENT
    ret_type: VariableType = VariableType.LIST_STRING


@dataclass(kw_only=True)
class HtmlTextAllExpression(BaseExpression):
    """extract text from html element"""

    kind: ClassVar[TokenType] = TokenType.EXPR_TEXT_ALL
    accept_type: VariableType = VariableType.LIST_DOCUMENT
    ret_type: VariableType = VariableType.LIST_STRING


@dataclass(kw_only=True)
class HtmlTextExpression(BaseExpression):
    """extract text from all html elements"""

    kind: ClassVar[TokenType] = TokenType.EXPR_TEXT
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.STRING


# ARRAY
@dataclass(kw_only=True)
class IndexDocumentExpression(BaseExpression):
    """get element from sequence of elements

    NOTE: if target language not supports negative indexes (like python) - add calculate index:

    pseudocode example:

    len(<VAR_N>) - (value)
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_LIST_DOCUMENT_INDEX

    value: int
    accept_type: VariableType = VariableType.LIST_DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT


@dataclass(kw_only=True)
class IndexStringExpression(BaseExpression):
    """get element from sequence of strings

    NOTE: if target language not supports negative indexes (like python) - add calculate index:

    pseudocode example:

    var index_NEXT = len(<VAR_N>) - (value)
    var val_NEXT = val_PREV[index_NEXT]
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_LIST_STRING_INDEX

    value: int
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class JoinExpression(BaseExpression):
    """join sequence of strings to one string

    pseudocode example:

        ', '.join(["foo", "bar"]) -> "foo, bar"

    """

    kind: ClassVar[TokenType] = TokenType.EXPR_LIST_JOIN

    sep: str
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class ArrayLengthExpression(BaseExpression):
    kind: ClassVar[TokenType] = TokenType.EXPR_LIST_LEN
    accept_type: VariableType = (
        VariableType.LIST_STRING
        | VariableType.LIST_DOCUMENT
        | VariableType.LIST_INT
        | VariableType.LIST_FLOAT
    )
    ret_type: VariableType = VariableType.INT


# STRING
@dataclass(kw_only=True)
class __TrimNode(BaseExpression):
    value: str
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING


@dataclass(kw_only=True)
class TrimExpression(__TrimNode):
    """trim string by substring in LEFT and RIGHT

    note: if target language not exists buildin operations use regex:

    pseudocode examples:
        // build-in methods call
        var VAL_NEXT = VAL_PREV.trim(<value>)

        // by regex trim
        var RE_LEFT = "^" + escape_str(value)
        var RE_RIGHT = escape_str(value) + "$"
        var VAL_NEXT = re.sub(RE_LEFT, "", VAL_PREV).sub(RE_RIGHT, "", VAL_PREV)
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_STRING_TRIM


@dataclass(kw_only=True)
class LTrimExpression(__TrimNode):
    """trim string by substring in LEFT

    note: if target language not exists buildin operations use regex:

    pseudocode examples:

        // build-in methods call
        var VAL_NEXT = VAL_PREV.ltrim(<value>)

        // by regex trim
        var RE_LEFT = "^" + escape_str(value)
        var VAL_NEXT = re.sub(RE_LEFT, "", VAL_PREV)
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_STRING_LTRIM


@dataclass(kw_only=True)
class RTrimExpression(__TrimNode):
    """trim string by substring in RIGHT

    note: if target language not exists buildin operations use regex:

    pseudocode examples:

        // build-in methods call
        var VAL_NEXT = VAL_PREV.rtrim(<value>)

        // by regex trim
        var RE_RIGHT = escape_str(value) + "$"
        var VAL_NEXT = re.sub(RE_RIGHT, "", VAL_PREV)
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_STRING_RTRIM


@dataclass(kw_only=True)
class __MapTrimNode(BaseExpression):
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.LIST_STRING
    value: str


@dataclass(kw_only=True)
class MapTrimExpression(__MapTrimNode):
    """trim sequence of string by substring in LEFT and RIGHT

    note: if target language not exists buildin operations use regex:

    pseudocode examples:
        // build-in methods call
        var VAL_NEXT = VAL_PREV.map((i) => i.trim(<value>))

        // by regex trim
        var RE_LEFT = "^" + escape_str(value)
        var RE_RIGHT = escape_str(value) + "$"
        var VAL_NEXT = VAL_PREV.map((i) => re.sub(RE_LEFT, "", i).sub(RE_RIGHT, "", i))
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_LIST_STRING_TRIM


@dataclass(kw_only=True)
class MapLTrimExpression(__MapTrimNode):
    """trim sequence of string by substring in LEFT

    note: if target language not exists buildin operations use regex:

    pseudocode examples:
        // build-in methods call
        var VAL_NEXT = VAL_PREV.map((i) => i.ltrim(<value>))

        // by regex trim
        var RE_LEFT = "^" + escape_str(value)
        var VAL_NEXT = VAL_PREV.map((i) => re.sub(RE_LEFT, "", i))
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_LIST_STRING_LTRIM


@dataclass(kw_only=True)
class MapRTrimExpression(__MapTrimNode):
    """trim sequence of string by substring in RIGHT

    note: if target language not exists buildin operations use regex:

    pseudocode examples:
        // build-in methods call
        var VAL_NEXT = VAL_PREV.map((i) => i.rtrim(<value>))

        // by regex trim
        var RE_RIGHT = escape_str(value) + "$"
        var VAL_NEXT = VAL_PREV.map((i) => re.sub(RE_RIGHT, "", i))
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_LIST_STRING_RTRIM


@dataclass(kw_only=True)
class SplitExpression(BaseExpression):
    """split string by substring to sequence of string

    pseudocode example:

        var VAL_NEXT = VAL_PREV.split(<value>)
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_STRING_SPLIT
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.LIST_STRING
    sep: str


@dataclass(kw_only=True)
class FormatExpression(BaseExpression):
    """format string by `fmt` value

    note:
        in AST placeholder marks as {{}} strings, replace with a chars that the target language support

    pseudocode example:

        var VAL_NEXT = <fmt>.format(VAL_PREV)
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_STRING_FORMAT
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING
    fmt: str


@dataclass(kw_only=True)
class MapFormatExpression(BaseExpression):
    """format sequence of strings by `fmt` value

    note:
        in AST placeholder marks as {{}} strings, replace with a chars that the target language support

    pseudocode example:

        var VAL_NEXT = VAL_PREV.map(i => <fmt>.format(i))
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_LIST_STRING_FORMAT
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.LIST_STRING
    fmt: str


@dataclass(kw_only=True)
class ReplaceExpression(BaseExpression):
    """replace string by all occurrences of substring old replaced by new

    pseudocode example:

        var val_NEXT = val_PREV.replace(<old>, <new>)
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_STRING_REPLACE
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING
    old: str
    new: str


@dataclass(kw_only=True)
class MapReplaceExpression(BaseExpression):
    """replace sequence of strings by all occurrences of substring old replaced by new

    pseudocode example:

        var val_NEXT = val_PREV.map(i => i.replace(<old>, <new>))
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_LIST_STRING_REPLACE
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.LIST_STRING
    old: str
    new: str


# REGEX
@dataclass(kw_only=True)
class RegexExpression(BaseExpression):
    """match <group> first result by regex pattern

    note:
        don't forget mark group in the pattern

    pseudocode example:

        var val_NEXT = regex.search(<pattern>, val_PREV)[<group>]
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_REGEX
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING
    pattern: str
    group: int


@dataclass(kw_only=True)
class RegexAllExpression(BaseExpression):
    """match all results by regex pattern

    note:
        don't forget mark group in the pattern
        should be contains one group mark

    pseudocode example:

        var val_NEXT = regex.findall(<pattern>, val_PREV)
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_REGEX_ALL
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.LIST_STRING
    pattern: str


@dataclass(kw_only=True)
class RegexSubExpression(BaseExpression):
    """sub target string to substring by regex pattern


    pseudocode example:

        var val_NEXT = regex.sub(<pattern>, <repl>, val_PREV)
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_REGEX_SUB
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING
    pattern: str
    repl: str


@dataclass(kw_only=True)
class MapRegexSubExpression(BaseExpression):
    """sub a sequence of strings to substring by regex pattern


    pseudocode example:

        var val_NEXT = val_PREV.map(i => regex.sub(<pattern>, <repl>, i))
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_LIST_REGEX_SUB
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.LIST_STRING
    pattern: str
    repl: str


# asserts - validators - not modify variables
@dataclass(kw_only=True)
class IsEqualExpression(BaseExpression):
    """check equal value (by assert stmt). do not modify previous value

    throw error with message, if not passed

    pseudocode example:

        assert val_PREV == <value>, msg
        // hack: avoid recalc variables
        var val_NEXT = val_PREV
    """

    kind: ClassVar[TokenType] = TokenType.IS_EQUAL
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING
    value: str | int | float
    msg: str


@dataclass(kw_only=True)
class IsNotEqualExpression(BaseExpression):
    """check not equal value (by assert stmt). do not modify previous value

    throw error with message, if not passed

    pseudocode example:

        assert val_PREV != <value>, msg
        // hack: avoid recalc variable nums
        var val_NEXT = val_PREV
    """

    kind: ClassVar[TokenType] = TokenType.IS_NOT_EQUAL
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING
    value: str | int | float
    msg: str


@dataclass(kw_only=True)
class IsCssExpression(BaseExpression):
    """check valid css query for variable (by assert stmt). do not modify previous value

    passed if first value is founded

    throw error with message, if not passed

    pseudocode example:

        assert val_PREV.css(<query>), msg
        // hack: avoid recalc variables nums
        var val_NEXT = val_PREV

    """

    kind: ClassVar[TokenType] = TokenType.IS_CSS
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT
    query: str
    msg: str


@dataclass(kw_only=True)
class IsXPathExpression(BaseExpression):
    """check valid xpath query for variable (by assert stmt). do not modify previous value

    passed if first value is founded

    throw error with message, if not passed

    pseudocode example:

        assert val_PREV.xpath(<query>), msg
        // hack: avoid recalc variable nums
        var val_NEXT = val_PREV

    """

    kind: ClassVar[TokenType] = TokenType.IS_XPATH
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT
    query: str
    msg: str


@dataclass(kw_only=True)
class IsContainsExpression(BaseExpression):
    """check contains value in sequence of string (by assert stmt). do not modify previous value

    passed if first value is founded

    throw error with message, if not passed

    pseudocode example:

        assert val_PREV.contains(<value>), msg
        // hack: avoid recalc variables
        var val_NEXT = val_PREV

    """

    kind: ClassVar[TokenType] = TokenType.IS_CONTAINS
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.LIST_STRING
    item: str | int | float
    msg: str


@dataclass(kw_only=True)
class IsRegexMatchExpression(BaseExpression):
    """check valid regex pattern for variable (by assert stmt). do not modify previous value

    passed if first value is founded

    throw error with message, if not passed

    pseudocode example:

        assert re.search(val_PREV, <pattern>), msg
        // hack: avoid recalc variables
        var val_NEXT = val_PREV
    """

    kind: ClassVar[TokenType] = TokenType.IS_REGEX_MATCH
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.STRING
    pattern: str
    msg: str


@dataclass(kw_only=True)
class NestedExpression(BaseExpression):
    """send element to another marked schema

    - schema_cls - configured BaseSchema instance  target
    - schema - configured BaseSchema instance target name
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_NESTED
    schema_cls: Type["BaseSchema"]
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.NESTED

    @property
    def schema(self) -> str:
        return self.schema_cls.__name__


@dataclass(kw_only=True)
class ReturnExpression(BaseExpression):
    """mark return expression"""

    kind: ClassVar[TokenType] = TokenType.EXPR_RETURN
    accept_type: VariableType = VariableType.ANY
    ret_type: VariableType = VariableType.ANY

    def have_assert(self) -> bool:
        if self.parent and self.parent.kind == TokenType.STRUCT_FIELD:
            return self.parent.have_assert_expr()  # type: ignore
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
            expr = expr.prev  # type: ignore
        return False

    def get_default_expr(self) -> None | DefaultValueWrapper:
        if not self.parent:
            return None
        return self.parent.default  # type: ignore


@dataclass(kw_only=True)
class NoReturnExpression(BaseExpression):
    """mark were body does not return anything or null

    in current project, used in `__PRE_VALIDATE__` method
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_NO_RETURN
    accept_type: VariableType = VariableType.ANY
    ret_type: VariableType = VariableType.NULL


@dataclass(kw_only=True)
class CallStructFunctionExpression(BaseExpression):
    """mark call structure method call

    used in `__START_PARSE__` entrypoint

    - fn_ref - call Node link
    - nested_cls_name_ref - call NestedStruct name (if nested_schema expr)
    - name - call field name
    - ret_type return type from called Node

    """

    kind: ClassVar[TokenType] = TokenType.STRUCT_CALL_FUNCTION
    accept_type: VariableType = VariableType.DOCUMENT
    fn_ref: Union[
        "StructFieldFunction", "PreValidateFunction", "PartDocFunction", None
    ] = field(default=None, repr=False)
    nested_cls_name_ref: str | None = None
    name: str
    ret_type: VariableType

    def have_assert_expr(self) -> bool:
        """return True if target called function have an assert stmt"""
        if not self.fn_ref:
            return False
        return any(e for e in self.fn_ref.body if e.have_assert_expr())

    def have_default_expr(self) -> bool:
        """return True if target called function have a default stmt"""

        if not self.fn_ref:
            return False
        return bool(self.fn_ref.body[0].have_default_expr())  # type: ignore

    def nested_schema(self) -> Union["StructParser", None]:
        """return True if reference stmt is nested"""
        if not self.nested_cls_name_ref:
            return None
        return self.fn_ref.parent  # type: ignore


# NUMERIC


@dataclass(kw_only=True)
class ToInteger(BaseExpression):
    """convert string variable to int (naive)

    pseudocode example:
        var val_NEXT = val_PREV.to_int()
    """

    kind: ClassVar[TokenType] = TokenType.TO_INT
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.INT


@dataclass(kw_only=True)
class ToListInteger(BaseExpression):
    """convert sequence of strings variable to int (naive)

    pseudocode example:
        var val_NEXT = val_PREV.map(i => i.to_int())
    """

    kind: ClassVar[TokenType] = TokenType.TO_INT_LIST
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.LIST_INT


@dataclass(kw_only=True)
class ToFloat(BaseExpression):
    """convert string variable to float (naive)

    pseudocode example:
        var val_NEXT = val_PREV.to_float()
    """

    kind: ClassVar[TokenType] = TokenType.TO_FLOAT
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.FLOAT


@dataclass(kw_only=True)
class ToListFloat(BaseExpression):
    """convert sequence of strings variable to int (naive)

    pseudocode example:
        var val_NEXT = val_PREV.map(i => i.to_float())
    """

    kind: ClassVar[TokenType] = TokenType.TO_FLOAT_LIST
    accept_type: VariableType = VariableType.LIST_STRING
    ret_type: VariableType = VariableType.LIST_FLOAT


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
        if self.body[_EXPR_I_START].kind == TokenType.EXPR_DEFAULT_START:
            # last token type -> TokenType.EXPR_DEFAULT_END
            return self.body[_EXPR_I_DEFAULT_END].variable.type  # type: ignore
        return self.body[_EXPR_I_RETURN].variable.type  # type: ignore


@dataclass(kw_only=True)
class StructFieldFunction(__StructNode):
    """header method in StructParser field

    pseudocode example:
     // struct parser header...
     func <field_name>(Document val) {
    // ... body code
    """

    name: M_ITEM | M_KEY | M_VALUE | str
    kind: ClassVar[TokenType] = TokenType.STRUCT_FIELD
    parent: Optional["StructParser"] = field(
        default=None, repr=False
    )  # LATE INIT

    def find_associated_typedef(self) -> TypeDef | None:
        """try get associated typedef Node

        - for cases, where function should be return parsed NestedSchema or typing
        """
        if self.ret_type != VariableType.NESTED:
            return None
        elif not self.parent or not self.parent.parent:
            return None

        associated_typedef = [
            fn
            for fn in self.parent.parent.body  # type: ignore
            if getattr(fn, "name", None)
            and fn.name == self.nested_schema_name()  # type: ignore[attr-defined]
            and fn.kind == TokenType.TYPEDEF
        ][0]
        return associated_typedef  # type: ignore

    def nested_schema_name(self) -> str | None:
        """try get associated typedef Node name

        - for cases, where function should be return parsed NestedSchema or typing
        """
        if self.ret_type != VariableType.NESTED:
            return None
        # type NestedExpression (naive)
        # last element - ReturnExpr
        return self.body[-2].schema  # type: ignore[attr-defined]

    def have_assert_expr(self) -> bool:
        """return True if StructFieldFunction contains assert expr"""
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
    """mark `__PRE_VALIDATE__` entrypoint.

    does not modify document and retrun anything. used for optional validate document before parse

    pseudocode example:

        // StructParser code...
        func _pre_validate(Document val) {
        // ... body expr
    """

    kind: ClassVar[TokenType] = TokenType.STRUCT_PRE_VALIDATE
    name: M_PRE_VALIDATE = "__PRE_VALIDATE__"
    parent: Optional["StructParser"] = field(
        default=None, init=False, repr=False
    )  # LATE INIT


@dataclass(kw_only=True)
class PartDocFunction(__StructNode):
    """mark `__SPLIT_DOC__` entrypoint.

    used for split document to elements in LIST_ITEM, DICT_ITEM, FLAT_LIST structs before parse

     pseudocode example:

        // StructParser code...
        func _part_document(Document val) Sequence<Element>{
        // ... body expr
    """

    kind: ClassVar[TokenType] = TokenType.STRUCT_PART_DOCUMENT
    name: M_SPLIT_DOC = "__SPLIT_DOC__"
    parent: Optional["StructParser"] = None  # LATE INIT


@dataclass(kw_only=True)
class StartParseFunction(__StructNode):
    """`__START_PARSE__` struct entrypoint

    - body CallStructFunctionExpression node expr
    - type struct type, for choice generate strategy
    """

    name: M_START_PARSE = "__START_PARSE__"
    kind: ClassVar[TokenType] = TokenType.STRUCT_PARSE_START
    body: list[CallStructFunctionExpression]
    type: StructType
    parent: Optional["StructParser"] = field(
        default=None, repr=False
    )  # LATE INIT

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
    """helper node for make constructor

    pseudocode example:

    // StructParser code...
    constructor(<name>) new ...
    """

    kind: ClassVar[TokenType] = TokenType.STRUCT_INIT
    parent: Optional["StructParser"] = field(
        default=None, repr=False
    )  # LATE INIT
    name: str


@dataclass(kw_only=True)
class StructParser(BaseAstNode):
    """parent struct node

    - init - Node helper for add constructor (if required)
    - docstring_class_top - docstring position (top or bottom in StructParser header)
    - name - schema name
    - doc - docstring Node
    - body sequence of StructFieldFunction, StartParseFunction, PreValidateFunction and PartDocFunction Nodes
    - typedef - link to TypeDef Node (for typing)
    - parent - ModuleProgram Node
    """

    kind: ClassVar[TokenType] = TokenType.STRUCT
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
    typedef: Optional["TypeDef"] = field(default=None, repr=False)
    parent: Optional[ModuleProgram] = field(
        default=None, repr=False
    )  # LATE INIT

    def _build_typedef(self) -> None:
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

    def __post_init__(self) -> None:
        self.init = StructInit(name=self.name, parent=self)
        self._build_typedef()

        self.body.append(  # type: ignore
            StartParseFunction(
                parent=self,
                type=self.type,
                body=[
                    CallStructFunctionExpression(
                        name=fn.name,
                        ret_type=fn.ret_type,
                        fn_ref=fn,  # type: ignore
                        nested_cls_name_ref=fn.nested_schema_name()  # type: ignore
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


# JSON
@dataclass(kw_only=True)
class JsonStruct(BaseAstNode):
    kind: ClassVar[TokenType] = TokenType.JSON_STRUCT
    name: str
    body: list["JsonStructField"]

    parent: Optional[ModuleProgram] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        for f in self.body:
            f.parent = self


@dataclass(kw_only=True)
class JsonStructField(BaseAstNode):
    kind: ClassVar[TokenType] = TokenType.JSON_FIELD
    name: str
    value: BaseJsonType

    parent: Optional[JsonStruct] = field(default=None, repr=False)  # LATE INIT

    @property
    def ret_type(self) -> BaseJsonType | dict[str, BaseJsonType]:
        if isinstance(self.value.TYPE, JsonVariableType):
            return self.value
        return self.value.TYPE

    @property
    def struct_ref(self) -> str | None:
        """return JsonObject ref name"""
        return self.value.name if isinstance(self.value, JsonObject) else None


@dataclass(kw_only=True)
class ToJson(BaseExpression):
    """jsonify string to structure"""

    kind: ClassVar[TokenType] = TokenType.TO_JSON
    accept_type: VariableType = VariableType.STRING
    ret_type: VariableType = VariableType.JSON
    value: Type[Json]

    @property
    def instance_name(self) -> str:
        return self.value.__name__

    @property
    def is_array_entrypoint(self) -> bool:
        return self.value.__IS_ARRAY__


# BOOLEAN
@dataclass(kw_only=True)
class ToBool(BaseExpression):
    """convert variable to boolean

    boolean convert rules

    None, nil, empty array, empty string - False
    other - True
    """

    kind: ClassVar[TokenType] = TokenType.TO_BOOL
    accept_type: VariableType = VariableType.ANY
    ret_type: VariableType = VariableType.BOOL
