from dataclasses import dataclass, field
from typing import TypedDict, ClassVar, TypeVar

from ssc_codegen.ast_.base import T_EMPTY_KWARGS, BaseAstNode
from ssc_codegen.ast_.base import (
    _DisableReprAcceptAndRetType,
    _DisableReprBody,
    _DisableRepr,
)
from ssc_codegen.json_struct import JsonType
from ssc_codegen.tokens import (
    TokenType,
    StructType,
    VariableType,
)

KW_DOCSTRING = TypedDict("KW_DOCSTRING", {"value": str})


@dataclass(kw_only=True)
class Docstring(_DisableRepr, BaseAstNode[KW_DOCSTRING, tuple[str]]):
    kind: ClassVar[TokenType] = TokenType.DOCSTRING
    kwargs: KW_DOCSTRING


@dataclass(kw_only=True)
class ModuleImports(_DisableRepr, BaseAstNode[T_EMPTY_KWARGS, tuple]):
    kind: ClassVar[TokenType] = TokenType.IMPORTS


@dataclass(kw_only=True)
class StructInitMethod(_DisableRepr, BaseAstNode[T_EMPTY_KWARGS, tuple]):
    """mark as class constructor entry if target language not need it - skip"""

    kind: ClassVar[TokenType] = TokenType.STRUCT_INIT

    accept_type: VariableType = field(default=VariableType.ANY, repr=False)
    ret_type: VariableType = field(default=VariableType.ANY, repr=False)


@dataclass(kw_only=True)
class StructPreValidateMethod(
    _DisableReprAcceptAndRetType, BaseAstNode[T_EMPTY_KWARGS, tuple]
):
    """mark optional input validation method.

    - Does not modify document entrypoint
    - Should be a run first before parse document
    """

    kind: ClassVar[TokenType] = TokenType.STRUCT_PRE_VALIDATE


KW_ST_METHOD = TypedDict("KW_ST_METHOD", {"name": str})
ARGS_ST_METHOD = tuple[str]


@dataclass(kw_only=True)
class StructFieldMethod(
    _DisableReprAcceptAndRetType, BaseAstNode[KW_ST_METHOD, ARGS_ST_METHOD]
):
    """mark as method for parse singe field"""

    kind: ClassVar[TokenType] = TokenType.STRUCT_FIELD
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.ANY  # override later


@dataclass(kw_only=True)
class StructPartDocMethod(
    _DisableReprAcceptAndRetType, BaseAstNode[T_EMPTY_KWARGS, tuple]
):
    """mark as method for split html document to elements"""

    kind: ClassVar[TokenType] = TokenType.STRUCT_PART_DOCUMENT
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.LIST_DOCUMENT


@dataclass(kw_only=True)
class StartParseMethod(
    _DisableReprAcceptAndRetType, BaseAstNode[T_EMPTY_KWARGS, tuple]
):
    """mark as method for run parser"""

    kind: ClassVar[TokenType] = TokenType.STRUCT_PARSE_START
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.ANY


KW_EXPR_CALL_METHOD = TypedDict(
    "KW_EXPR_CALL_METHOD",
    {"name": str, "type": VariableType, "cls_nested": str | None},
)
ARGS_EXPR_CALL_METHOD = tuple[str, VariableType, str | None]


@dataclass(kw_only=True)
class ExprCallStructMethod(
    _DisableRepr, BaseAstNode[KW_EXPR_CALL_METHOD, ARGS_ST_METHOD]
):
    """mark as call field method"""

    kind: ClassVar[TokenType] = TokenType.STRUCT_CALL_FUNCTION
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.ANY


KW_STRUCT_PARSER = TypedDict(
    "KW_STRUCT_PARSER",
    {"name": str, "struct_type": StructType, "docstring": str},
)
ARGS_STRUCT_PARSER = tuple[str, StructType, str]


@dataclass(kw_only=True)
class StructParser(BaseAstNode[KW_STRUCT_PARSER, ARGS_STRUCT_PARSER]):
    kind: ClassVar[TokenType] = TokenType.STRUCT

    @property
    def struct_type(self) -> StructType:
        return self.kwargs["struct_type"]

    @property
    def docstring(self) -> str:
        return self.docstring


KW_TYPEDEF_FIELD = TypedDict(
    "KW_TYPEDEF_FIELD",
    {
        "name": str,
        "type": VariableType,
        "cls_nested": str | None,
        "cls_nested_type": StructType | None,
    },
)
ARGS_TYPEDEF_FIELD = tuple[str, VariableType, str | None, StructType | None]
T_TYPEDEF = TypeVar("T_TYPEDEF", bound="TypeDef")


@dataclass(kw_only=True)
class TypeDefField(
    _DisableRepr, BaseAstNode[KW_TYPEDEF_FIELD, ARGS_TYPEDEF_FIELD]
):
    kind: ClassVar[TokenType] = TokenType.TYPEDEF_FIELD


KW_TYPEDEF = TypedDict("KW_TYPEDEF", {"name": str, "struct_type": StructType})
ARGS_TYPEDEF = tuple[str, StructType]


@dataclass(kw_only=True)
class TypeDef(
    _DisableReprAcceptAndRetType, BaseAstNode[KW_TYPEDEF, ARGS_TYPEDEF]
):
    kind: ClassVar[TokenType] = TokenType.TYPEDEF

    @property
    def struct_type(self) -> StructType:
        return self.kwargs["struct_type"]


KW_JSON_ST_FIELD = TypedDict(
    "KW_JSON_ST_FIELD", {"name": str, "type": JsonType}
)
ARGS_JSON_ST_FIELD = tuple[str, JsonType]
T_JSON_ST = TypeVar("T_JSON_ST", bound="JsonStruct")


@dataclass(kw_only=True)
class JsonStructField(
    _DisableRepr, BaseAstNode[KW_JSON_ST_FIELD, ARGS_JSON_ST_FIELD]
):
    kind: ClassVar[TokenType] = TokenType.JSON_FIELD


KW_JSON_ST = TypedDict("KW_JSON_ST", {"name": str, "is_array": bool})
ARGS_JSON_ST = tuple[str, bool]


@dataclass(kw_only=True)
class JsonStruct(
    _DisableReprAcceptAndRetType, BaseAstNode[KW_JSON_ST, ARGS_JSON_ST]
):
    kind: ClassVar[TokenType] = TokenType.JSON_STRUCT


@dataclass(kw_only=True)
class ModuleProgram(
    _DisableReprAcceptAndRetType, BaseAstNode[T_EMPTY_KWARGS, tuple]
):
    kind: ClassVar[TokenType] = TokenType.MODULE


KW_AST_DEFAULT = TypedDict(
    "KW_AST_DEFAULT", {"value": str | int | float | bool | list | None}
)
ARGS_AST_DEFAULT = tuple[str | int | float | bool | list | None]


@dataclass(kw_only=True)
class ExprDefaultValueWrapper(
    _DisableReprBody, BaseAstNode[KW_AST_DEFAULT, ARGS_AST_DEFAULT]
):
    # later insert ExprDefaultValueStart to the first pos
    # and insert ExprDefaultValueEnd to the last pos
    kind: ClassVar[TokenType] = TokenType.EXPR_DEFAULT
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT


@dataclass(kw_only=True)
class ExprDefaultValueStart(
    _DisableReprBody, BaseAstNode[KW_AST_DEFAULT, ARGS_AST_DEFAULT]
):
    kind: ClassVar[TokenType] = TokenType.EXPR_DEFAULT_START


@dataclass(kw_only=True)
class ExprDefaultValueEnd(
    _DisableReprBody, BaseAstNode[KW_AST_DEFAULT, ARGS_AST_DEFAULT]
):
    kind: ClassVar[TokenType] = TokenType.EXPR_DEFAULT_END


@dataclass(kw_only=True)
class ExprReturn(_DisableReprBody, BaseAstNode[T_EMPTY_KWARGS, tuple]):
    kind: ClassVar[TokenType] = TokenType.EXPR_RETURN


@dataclass(kw_only=True)
class ExprNoReturn(_DisableReprBody, BaseAstNode[T_EMPTY_KWARGS, tuple]):
    kind: ClassVar[TokenType] = TokenType.EXPR_NO_RETURN
