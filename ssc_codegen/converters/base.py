from typing import Callable, cast, Any, TypeVar

from ssc_codegen.ast_ import (
    BaseAstNode,
    ModuleProgram,
    Docstring,
    ModuleImports,
    TypeDef,
    TypeDefField,
    JsonStruct,
    JsonStructField,
    StructParser,
    StructFieldMethod,
    StructInitMethod,
    StructPartDocMethod,
    StructPreValidateMethod,
)
from ssc_codegen.tokens import TokenType

T_NODE = TypeVar("T_NODE", bound=BaseAstNode[Any, Any])
CB_FMT_DEBUG_COMMENT = Callable[[BaseAstNode[Any, Any], str], str]
CB_AST_BIND = Callable[[T_NODE], str]
CB_AST_DECORATOR = Callable[[CB_AST_BIND], CB_AST_BIND]


def debug_comment_cb(node: BaseAstNode, comment_prefix: str) -> str:
    match node.kind:
        case TokenType.EXPR_RETURN:
            return f"{comment_prefix}Token: {node.kind.name} ret_type: {node.ret_type.name}"
        case TokenType.EXPR_NO_RETURN:
            return f"{comment_prefix}Token: {node.kind.name}"
        case TokenType.STRUCT_PARSE_START:
            parent = node.parent
            parent = cast(StructParser, parent)
            return f"{comment_prefix}Token: {node.kind.name}, type: {parent.struct_type.name}"
        case _:
            return f"{comment_prefix}Token: {node.kind.name}, kwargs: {node.kwargs}"


class BaseCodeConverter:
    """base ast visitor class and code converter

    Visitor is set using decorators pointing to the TokenType

    decorators hooks can be overridden

    - as defaults __call__ methods - set @pre decorator
    - @pre - first trigger visitor entrypoint
    - @post - second trigger visitor entrypoint (for close brackets or other logic, for example)

    """

    def __init__(
        self,
        debug_instructions: bool = False,
        debug_comment_prefix: str = "",
        comment_prefix_sep: str = "\n",
        debug_cb: CB_FMT_DEBUG_COMMENT = debug_comment_cb,
    ) -> None:
        """

        :param debug_instructions: enable debug instructions (add comment for every generated instruction)
        :param debug_comment_prefix: comment line prefix
        :param debug_cb: callback formatting comment
        """
        self._debug_instructions = debug_instructions
        self._debug_comment_prefix = debug_comment_prefix
        self._debug_cb = debug_cb
        self._comment_prefix_sep = comment_prefix_sep
        self.pre_definitions: dict[TokenType | int, CB_AST_BIND] = {}
        self.post_definitions: dict[TokenType | int, CB_AST_BIND] = {}

    @property
    def comment_prefix_sep(self) -> str:
        return self._comment_prefix_sep

    @comment_prefix_sep.setter
    def comment_prefix_sep(self, comment_prefix_sep: str) -> None:
        self._comment_prefix_sep = comment_prefix_sep

    @property
    def comment_prefix(self) -> str:
        return self._debug_comment_prefix

    @comment_prefix.setter
    def comment_prefix(self, value: str) -> None:
        self._debug_comment_prefix = value

    @property
    def debug_instructions(self) -> bool:
        return self._debug_instructions

    @debug_instructions.setter
    def debug_instructions(self, value: bool) -> None:
        self._debug_instructions = value

    def pre(self, for_definition: TokenType) -> CB_AST_DECORATOR:
        """Define a pre-conversion decorator for the given TokenType."""

        def decorator(func: CB_AST_BIND) -> CB_AST_BIND:
            self.pre_definitions[for_definition] = func
            return func

        return decorator

    def post(self, for_definition: TokenType) -> CB_AST_DECORATOR:
        """Define a post-conversion decorator for the given TokenType."""

        def decorator(func: CB_AST_BIND) -> CB_AST_BIND:
            self.post_definitions[for_definition] = func
            return func

        return decorator

    def __call__(self, for_definition: TokenType) -> CB_AST_DECORATOR:
        """Alias for pre decorator."""
        return self.pre(for_definition)

    def _pre_convert_node(self, node: BaseAstNode) -> str:
        """Convert the AST node using the pre-definition function."""
        if pre_func := self.pre_definitions.get(node.kind):
            if self.debug_instructions:
                return f"{self._debug_cb(node, self.comment_prefix)}{self.comment_prefix_sep}{pre_func(node)}"
            return pre_func(node)
        return ""

    def _post_convert_node(self, node: BaseAstNode) -> str:
        """Convert the AST node using the post-definition function."""
        if post_func := self.post_definitions.get(node.kind):
            return post_func(node)
        return ""

    def convert_program(
        self, ast_program: ModuleProgram, comment: str = ""
    ) -> list[str]:
        """Convert the module AST to code parts."""
        acc = [comment]
        result = self.convert(ast_program, acc)
        return [i for i in result if i]

    def convert(
        self, ast_entry: BaseAstNode, acc: list[str] | None = None
    ) -> list[str]:
        """Convert an AST node into code parts."""
        acc = acc or []
        match ast_entry.kind:
            case TokenType.MODULE:
                ast_entry = cast(ModuleProgram, ast_entry)
                self._convert_module(ast_entry, acc)
            case TokenType.DOCSTRING:
                ast_entry = cast(Docstring, ast_entry)
                self._convert_docstring(ast_entry, acc)
            case TokenType.IMPORTS:
                ast_entry = cast(ModuleImports, ast_entry)
                self._convert_imports(ast_entry, acc)
            case TokenType.TYPEDEF:
                ast_entry = cast(TypeDef, ast_entry)
                self._convert_typedef(ast_entry, acc)
            case TokenType.TYPEDEF_FIELD:
                ast_entry = cast(TypeDefField, ast_entry)
                self._convert_typedef_field(ast_entry, acc)
            case TokenType.STRUCT:
                ast_entry = cast(StructParser, ast_entry)
                self._convert_struct(ast_entry, acc)
            case TokenType.JSON_STRUCT:
                ast_entry = cast(JsonStruct, ast_entry)
                self._convert_json_struct(ast_entry, acc)
            case TokenType.JSON_FIELD:
                ast_entry = cast(JsonStructField, ast_entry)
                self._convert_json_struct_field(ast_entry, acc)
            case _ if ast_entry.kind in {
                TokenType.STRUCT_PART_DOCUMENT,
                TokenType.STRUCT_PRE_VALIDATE,
                TokenType.STRUCT_PARSE_START,
                TokenType.STRUCT_FIELD,
            }:
                ast_entry = cast(
                    StructFieldMethod
                    | StructInitMethod
                    | StructPartDocMethod
                    | StructPreValidateMethod,
                    ast_entry,
                )
                self._convert_struct_method(ast_entry, acc)
            case _:
                self._convert_default(ast_entry, acc)
        return acc

    def _convert_module(self, ast_entry: ModuleProgram, acc: list[str]) -> None:
        """Handle module conversion."""
        for node in ast_entry.body:
            self.convert(node, acc)

    def _convert_docstring(self, ast_entry: Docstring, acc: list[str]) -> None:
        """Handle docstring conversion."""
        acc.append(self._pre_convert_node(ast_entry))
        acc.append(self._post_convert_node(ast_entry))

    def _convert_imports(
        self, ast_entry: ModuleImports, acc: list[str]
    ) -> None:
        """Handle imports conversion."""
        acc.append(self._pre_convert_node(ast_entry))
        acc.append(self._post_convert_node(ast_entry))

    def _convert_typedef(self, ast_entry: TypeDef, acc: list[str]) -> None:
        """Handle typedef conversion."""
        acc.append(self._pre_convert_node(ast_entry))
        # TYPEDEF_FIELD call
        for node in ast_entry.body:
            self.convert(node, acc)
        acc.append(self._post_convert_node(ast_entry))

    def _convert_typedef_field(
        self, ast_entry: TypeDefField, acc: list[str]
    ) -> None:
        """Handle typedef field conversion."""
        acc.append(self._pre_convert_node(ast_entry))
        acc.append(self._post_convert_node(ast_entry))

    def _convert_json_struct(
        self, ast_entry: JsonStruct, acc: list[str]
    ) -> None:
        acc.append(self._pre_convert_node(ast_entry))
        # JSON_ST_FIELD call
        for node in ast_entry.body:
            self.convert(node, acc)
        acc.append(self._post_convert_node(ast_entry))

    def _convert_json_struct_field(
        self, ast_entry: JsonStructField, acc: list[str]
    ) -> None:
        acc.append(self._pre_convert_node(ast_entry))
        acc.append(self._post_convert_node(ast_entry))

    def _convert_struct(self, ast_entry: StructParser, acc: list[str]) -> None:
        """Handle struct conversion."""
        # pre_CLASS/STRUCT HEADER
        # pre_CONSTRUCTOR post_CONSTRUCTOR
        # BODY
        # post_CLASS/STRUCT
        # class header (with docstring) -> constructor -> body -> class footer
        acc.append(self._pre_convert_node(ast_entry))
        for node in ast_entry.body:
            self.convert(node, acc)
        acc.append(self._post_convert_node(ast_entry))

    def _convert_struct_method(
        self,
        ast_entry: StructFieldMethod
        | StructInitMethod
        | StructPartDocMethod
        | StructPreValidateMethod,
        acc: list[str],
    ) -> None:
        """Handle struct method headers and bodies."""
        acc.append(self._pre_convert_node(ast_entry))
        for node in ast_entry.body:
            self.convert(node, acc)
        acc.append(self._post_convert_node(ast_entry))

    def _convert_default(self, ast_entry: BaseAstNode, acc: list[str]) -> None:
        """Handle default node conversion."""
        acc.append(self._pre_convert_node(ast_entry))
        acc.append(self._post_convert_node(ast_entry))
