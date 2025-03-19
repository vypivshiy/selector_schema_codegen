from dataclasses import dataclass
from typing import TypedDict, Sequence, ClassVar

from ssc_codegen.ast_.base import BaseAstNode, T_EMPTY_KWARGS, BaseAstNode
from ssc_codegen.tokens import TokenType, StructType, VariableType

KW_DOCSTRING = TypedDict("KW_DOCSTRING", {"value": str})


@dataclass(kw_only=True)
class Docstring(BaseAstNode[KW_DOCSTRING, tuple[str]]):
    kind: ClassVar[TokenType] = TokenType.DOCSTRING
    kwargs: KW_DOCSTRING


@dataclass(kw_only=True)
class ModuleImports(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    kind: ClassVar[TokenType] = TokenType.IMPORTS


KW_STRUCT_PARSER = TypedDict(
    "KW_STRUCT_PARSER", {"struct_type": StructType, "docstring": str}
)


@dataclass(kw_only=True)
class StructInitMethod(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    """mark as class constructor entry if target language not need it - skip"""

    kind: ClassVar[TokenType] = TokenType.STRUCT_INIT


@dataclass(kw_only=True)
class PreValidateMethod(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    """mark optional input validation method.

    - Does not modify document entrypoint
    - Should be a run first before parse document
    """

    kind: ClassVar[TokenType] = TokenType.STRUCT_PRE_VALIDATE


@dataclass(kw_only=True)
class StructFieldMethod(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    """mark as method for parse singe field"""

    kind: ClassVar[TokenType] = TokenType.STRUCT_FIELD


@dataclass(kw_only=True)
class StructPartDocMethod(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    """mark as method for split html document to elements"""

    kind: ClassVar[TokenType] = TokenType.STRUCT_PART_DOCUMENT


@dataclass(kw_only=True)
class StartParseMethod(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    """mark as method for run parser"""

    kind: ClassVar[TokenType] = TokenType.STRUCT_PARSE_START


@dataclass(kw_only=True)
class ExprCallStructMethod(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    """mark as call field method"""

    kind: ClassVar[TokenType] = TokenType.STRUCT_CALL_FUNCTION


@dataclass(kw_only=True)
class StructParser(BaseAstNode[KW_STRUCT_PARSER, tuple[StructType, str]]):
    kind: ClassVar[TokenType] = TokenType.STRUCT


# TODO: API for relation with StructParser
@dataclass(kw_only=True)
class TypeDefField(BaseAstNode):
    kind: ClassVar[TokenType] = TokenType.TYPEDEF_FIELD


@dataclass(kw_only=True)
class TypeDef(BaseAstNode):
    kind: ClassVar[TokenType] = TokenType.TYPEDEF
    body: Sequence[TypeDefField]


@dataclass(kw_only=True)
class JsonStructField(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    kind: ClassVar[TokenType] = TokenType.JSON_FIELD


@dataclass(kw_only=True)
class JsonStruct(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    kind: ClassVar[TokenType] = TokenType.JSON_STRUCT
    body: Sequence[JsonStructField]


@dataclass(kw_only=True)
class ModuleProgram(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    kind: ClassVar[TokenType] = TokenType.MODULE
    kwargs: T_EMPTY_KWARGS
    parent = None


KW_DEFAULT = TypedDict("KW_DEFAULT", {"value": str | int | float | bool | None})
_AST_DEFAULT_ARGS = tuple[str | int | float | bool | None]


@dataclass(kw_only=True)
class ExprDefaultValueWrapper(BaseAstNode[KW_DEFAULT, _AST_DEFAULT_ARGS]):
    # later insert ExprDefaultValueStart to the first pos
    # and insert ExprDefaultValueEnd to the last pos
    kind: ClassVar[TokenType] = TokenType.EXPR_DEFAULT
    accept_type: VariableType = VariableType.DOCUMENT


@dataclass(kw_only=True)
class ExprDefaultValueStart(BaseAstNode[KW_DEFAULT, _AST_DEFAULT_ARGS]):
    kind: ClassVar[TokenType] = TokenType.EXPR_DEFAULT_START


@dataclass(kw_only=True)
class ExprDefaultValueEnd(BaseAstNode[KW_DEFAULT, _AST_DEFAULT_ARGS]):
    kind: ClassVar[TokenType] = TokenType.EXPR_DEFAULT_END


@dataclass(kw_only=True)
class ExprReturn(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    kind: ClassVar[TokenType] = TokenType.EXPR_RETURN


@dataclass(kw_only=True)
class ExprNoReturn(BaseAstNode[T_EMPTY_KWARGS, tuple]):
    kind: ClassVar[TokenType] = TokenType.EXPR_NO_RETURN
