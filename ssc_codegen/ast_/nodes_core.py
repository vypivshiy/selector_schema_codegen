from dataclasses import dataclass, field
from typing import Sequence, TypedDict, ClassVar, TypeVar

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
    """AST node representing a docstring in the generated code.

    This node contains documentation strings that will be added to the
    generated classes, methods, or other code elements.

    Kwargs:
        "value": str - docstring value (represents as it, required manually translate to target syntax)

    eg: add `//` for every line, or wrap to `/*`,`*/` chars

    NOTE:
        not represented this node in `StructParser` node, only in module doscring
    """

    kind: ClassVar[TokenType] = TokenType.DOCSTRING
    kwargs: KW_DOCSTRING


@dataclass(kw_only=True)
class ModuleImports(_DisableRepr, BaseAstNode[T_EMPTY_KWARGS, tuple]):
    """AST node representing module import statements.

    This node contains import statements that will be added to the
    generated module to ensure required dependencies are available.
    """

    kind: ClassVar[TokenType] = TokenType.IMPORTS


@dataclass(kw_only=True)
class StructInitMethod(_DisableRepr, BaseAstNode[T_EMPTY_KWARGS, tuple]):
    """AST node representing a structure initialization method.

    This node marks a class constructor entry point. If the target language
    does not require explicit constructors, this node will be skipped during
    code generation.
    """

    kind: ClassVar[TokenType] = TokenType.STRUCT_INIT

    accept_type: VariableType = field(default=VariableType.ANY, repr=False)
    ret_type: VariableType = field(default=VariableType.ANY, repr=False)


@dataclass(kw_only=True)
class StructPreValidateMethod(
    _DisableReprAcceptAndRetType, BaseAstNode[T_EMPTY_KWARGS, tuple]
):
    """AST node representing an optional input validation method.

    This node marks an optional input validation method that runs before
    the main document parsing logic. It does not modify the document entrypoint.
    """

    kind: ClassVar[TokenType] = TokenType.STRUCT_PRE_VALIDATE


KW_ST_METHOD = TypedDict("KW_ST_METHOD", {"name": str})
ARGS_ST_METHOD = tuple[str]


@dataclass(kw_only=True)
class StructFieldMethod(
    _DisableReprAcceptAndRetType, BaseAstNode[KW_ST_METHOD, ARGS_ST_METHOD]
):
    """AST node representing a method for parsing a single field.

    This node marks a method responsible for parsing a specific field in a structure.
    The return type will be overridden later in the processing pipeline.

    Kwargs:
        "name": str - name field name from struct parser

    Note:
        optionally, convert to required name for needed code style (camelCase, PascalCase etc)
    Example:
        foo = D().css("a::attr(href)) # name="foo"
    """

    kind: ClassVar[TokenType] = TokenType.STRUCT_FIELD
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.ANY  # override later


@dataclass(kw_only=True)
class StructPartDocMethod(
    _DisableReprAcceptAndRetType, BaseAstNode[T_EMPTY_KWARGS, tuple]
):
    """AST node representing a method for splitting an HTML document into elements.

    This node marks a method responsible for splitting a document into smaller
    parts for processing by multiple structures.
    """

    kind: ClassVar[TokenType] = TokenType.STRUCT_PART_DOCUMENT
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.LIST_DOCUMENT


@dataclass(kw_only=True)
class StartParseMethod(
    _DisableReprAcceptAndRetType, BaseAstNode[T_EMPTY_KWARGS, tuple]
):
    """AST node representing the main parser execution method.

    This node marks the method that starts the parsing process for a structure.
    """

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
    """AST node representing a call to a field parsing method.

    This node marks the invocation of a field parsing method, including
    the method name, type, and potential nested class information.

    Kwargs:
        "name": str - field name (where need call it)
        "type": VariableType - returns type from this field (useful for static-typed languages)
        "cls_nested": str|None - called nested parser name. if not None - this field parse from nested schema


    """

    kind: ClassVar[TokenType] = TokenType.STRUCT_CALL_FUNCTION
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.ANY


KW_EXPR_CALL_CLASSVAR = TypedDict(
    "KW_EXPR_CALL_CLASSVAR",
    {"struct_name": str, "field_name": str, "type": VariableType},
)
ARGS_EXPR_CALL_CLASSVAR = tuple[str, str, VariableType]


@dataclass(kw_only=True)
class ExprCallStructClassVar(
    _DisableRepr, BaseAstNode[KW_EXPR_CALL_CLASSVAR, ARGS_EXPR_CALL_CLASSVAR]
):
    """AST node representing a call to a class variable in a structure.

    This node marks the access or reference to a class variable within a struct.
    It contains information about the structure name, field name, and type.

    Kwargs:
        "struct_name": str - struct name where called this classvar
        "field_name": str - field (classvar) name
        "type": VariableType - classvar variable type (useful for static-typed languages)
    """

    kind: ClassVar[TokenType] = TokenType.STRUCT_CALL_CLASSVAR
    accept_type = VariableType.ANY
    ret_type = VariableType.ANY


KW_STRUCT_PARSER = TypedDict(
    "KW_STRUCT_PARSER",
    {"name": str, "struct_type": StructType, "docstring": str},
)
ARGS_STRUCT_PARSER = tuple[str, StructType, str]


@dataclass(kw_only=True)
class StructParser(BaseAstNode[KW_STRUCT_PARSER, ARGS_STRUCT_PARSER]):
    """AST node representing a structure parser.

    This node represents the main parser for a structure, containing
    information about the structure name, type, and documentation string.

    Kwargs:
        - "name": str - struct parser name
        - "struct_type": StructType - struct type (parse document stategy)
        - "docstring": str - socstring for this struct parser. if not exitsts - return empty string + parsed signature metadata
    """

    kind: ClassVar[TokenType] = TokenType.STRUCT

    @property
    def struct_type(self) -> StructType:
        """Get the structure type for this parser.

        Returns:
            The structure type from the kwargs.
        """
        return self.kwargs["struct_type"]

    @property
    def docstring(self) -> str:
        """Get the documentation string for this parser.

        Returns:
            The documentation string from the kwargs.
        """
        return self.kwargs["docstring"]


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
    """AST node representing a field in a type definition by defined struct parser.

    This node represents a field within a type definition, containing
    information about the field name, type, and potential nested class information.

    If target languages not support static typing or annotatons - you can generate docstring-styled types
    (eg: JSDoc, EmmyLua)

    Kwargs:
        "name": str - field name
        "type": VariableType - field type
        "cls_nested": str | None - if not None, this field called from nested schema, add reference
        "cls_nested_type": StructType | None - schema type.
        in current project used in case if struct_type==StructType.LIST and cast nested class to array-like type
    """

    kind: ClassVar[TokenType] = TokenType.TYPEDEF_FIELD


KW_TYPEDEF = TypedDict("KW_TYPEDEF", {"name": str, "struct_type": StructType})
ARGS_TYPEDEF = tuple[str, StructType]


@dataclass(kw_only=True)
class TypeDef(
    _DisableReprAcceptAndRetType, BaseAstNode[KW_TYPEDEF, ARGS_TYPEDEF]
):
    """AST node representing a type definition.

    This node represents a type definition, containing information about
    the type name and structure type based on defined struct parser.

    Kwargs:
        "name": str - struct name from defined schema. For avoid conficts after code generation recommended add prefix `T`
        "struct_type": StructType - struct type from defined schema
    """

    kind: ClassVar[TokenType] = TokenType.TYPEDEF

    @property
    def struct_type(self) -> StructType:
        """Get the structure type for this type definition.

        Returns:
            The structure type from the kwargs.
        """
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
    """AST node representing a field in a JSON structure for serialization raw json data.

    This node represents a field within a JSON structure, containing
    information about the field name and JSON type.

    Kwargs:
        "name": str - field name
        "type": JsonType - json field type
    """

    kind: ClassVar[TokenType] = TokenType.JSON_FIELD


KW_JSON_ST = TypedDict("KW_JSON_ST", {"name": str, "is_array": bool})
ARGS_JSON_ST = tuple[str, bool]


@dataclass(kw_only=True)
class JsonStruct(
    _DisableReprAcceptAndRetType, BaseAstNode[KW_JSON_ST, ARGS_JSON_ST]
):
    """AST node representing a JSON structure for serialization raw json data.

    This node represents a JSON structure, containing information about
    the structure name and whether it's an array.

    Kwargs:
        "name": str - json struct name
        "is_array": bool - if true - entypoint is array else map structure

    Example:

        ```
        # generate is_array=True
        # expected json data: {"a": 1, "b": "a"}
        def Foo(Json):
            a: int
            b: str

        # generate is_array=True
        # expected json data: [{"a": 1, b: "a"}, {"a": 2, b: "b"}, ...]
        def Bar(Json):
            __IS_ARRAY__ = True

            a: int
            b: str
        ```
    """

    kind: ClassVar[TokenType] = TokenType.JSON_STRUCT


@dataclass(kw_only=True)
class ModuleProgram(
    _DisableReprAcceptAndRetType, BaseAstNode[T_EMPTY_KWARGS, tuple]
):
    """first AST node enrtypoint, representing a complete program module.

    This node represents the top-level container for an entire program module,
    containing all the structures, imports, and other elements that make up
    the generated code file.
    """

    kind: ClassVar[TokenType] = TokenType.MODULE


KW_AST_DEFAULT = TypedDict(
    "KW_AST_DEFAULT", {"value": str | int | float | bool | list | None}
)
ARGS_AST_DEFAULT = tuple[str | int | float | bool | list | None]


@dataclass(kw_only=True)
class ExprDefaultValueWrapper(
    _DisableReprBody, BaseAstNode[KW_AST_DEFAULT, ARGS_AST_DEFAULT]
):
    """AST node representing a default value wrapper expression.

    This node wraps a default value expression that will be processed
    by inserting start and end nodes at the beginning and end of the body.

    Kwargs:
        "value": str | int | float | bool | list | None - defined default value
    """

    # later insert ExprDefaultValueStart to the first pos
    # and insert ExprDefaultValueEnd to the last pos
    kind: ClassVar[TokenType] = TokenType.EXPR_DEFAULT
    accept_type: VariableType = VariableType.DOCUMENT
    ret_type: VariableType = VariableType.DOCUMENT


@dataclass(kw_only=True)
class ExprDefaultValueStart(
    _DisableReprBody, BaseAstNode[KW_AST_DEFAULT, ARGS_AST_DEFAULT]
):
    """AST node representing the start of a default value expression.

    This node marks the beginning of a default value expression block.
    It is automatically inserted at the first position when processing
    default value wrappers.

    Kwargs:
        "value": str | int | float | bool | list | None - defined default value
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_DEFAULT_START


@dataclass(kw_only=True)
class ExprDefaultValueEnd(
    _DisableReprBody, BaseAstNode[KW_AST_DEFAULT, ARGS_AST_DEFAULT]
):
    """AST node representing the end of a default value expression.

    This node marks the end of a default value expression block.
    It is automatically inserted at the last position when processing
    default value wrappers.

    Kwargs:
        "value": str | int | float | bool | list | None - defined default value
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_DEFAULT_END


@dataclass(kw_only=True)
class ExprReturn(_DisableReprBody, BaseAstNode[T_EMPTY_KWARGS, tuple]):
    """AST node representing a return expression.

    This node marks an expression that returns a value from a function
    or method, indicating that the parsed result should be returned.
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_RETURN


@dataclass(kw_only=True)
class ExprNoReturn(_DisableReprBody, BaseAstNode[T_EMPTY_KWARGS, tuple]):
    """AST node representing a non-return expression.

    This node marks an expression that does not return a value,
    typically used in pre-validation contexts where the result
    should not be returned from the function.
    """

    kind: ClassVar[TokenType] = TokenType.EXPR_NO_RETURN


# regex pattern auto converts to string
T_CLASSVAR = int | str | bool | float | None
KW_CLASSVAR = TypedDict(
    "KW_CLASSVAR",
    {
        "value": T_CLASSVAR,
        "struct_name": str,
        "field_name": str,
        "parse_returns": bool,
        "is_regex": bool,
    },
)
ARGS_CLASSVAR = tuple[T_CLASSVAR, str, str, bool, bool]


@dataclass(kw_only=True)
class ExprClassVar(_DisableReprBody, BaseAstNode[KW_CLASSVAR, ARGS_CLASSVAR]):
    """AST node representing a class variable expression.

    This node represents a class variable that should not change in multithreaded
    parse mode due to the risk of race conditions or other side effects.
    It contains the variable value and reference information.

    Kwargs:
        "value":  int | str | bool | float | None - defined first classvar value
        "struct_name": str - parent struct name
        "field_name": str - classvar field name
        "parse_returns": bool - used in self-defined classvar inner structes.
            marks its shoud be returns with parse resuls
        "is_regex": bool - is regex-compiled variable (currently not used)
    """

    kind: ClassVar[TokenType] = TokenType.CLASSVAR
    exclude_types: Sequence[VariableType] = field(
        default=(
            VariableType.DOCUMENT,
            VariableType.LIST_DOCUMENT,
            VariableType.JSON,
            VariableType.NESTED,
            VariableType.LIST_ANY,
            VariableType.LIST_INT,
            VariableType.LIST_STRING,
        ),
        repr=False,
    )

    @property
    def value(self) -> T_CLASSVAR:
        """Get the value of the class variable.

        Returns:
            The value stored in the class variable.
        """
        return self.kwargs["value"]

    @value.setter
    def value(self, val: T_CLASSVAR) -> None:
        """Set the value of the class variable.

        Args:
            val: The new value to store in the class variable.
        """
        self.kwargs["value"] = val

    @property
    def literal_ref_name(self) -> tuple[str, str]:
        """Get the literal reference name for the class variable.

        Returns:
            A tuple containing the structure name and field name.
        """
        return self.kwargs["struct_name"], self.kwargs["field_name"]


@dataclass(kw_only=True)
class CodeStart(_DisableRepr, BaseAstNode):
    """AST node representing the start of custom code insertion.

    This node marks a location where custom code can be injected after
    generating docstrings and imports strings. It serves as an entrypoint
    for adding custom logic at the beginning of the generated code.
    """

    kind: ClassVar[TokenType] = TokenType.CODE_START


@dataclass(kw_only=True)
class CodeEnd(_DisableRepr, BaseAstNode):
    """AST node representing the end of custom code insertion.

    This node marks a location where custom code can be injected at
    the end of the AST tree. It serves as an entrypoint for adding
    custom logic or code at the conclusion of the generated code.
    """

    kind: ClassVar[TokenType] = TokenType.CODE_END
