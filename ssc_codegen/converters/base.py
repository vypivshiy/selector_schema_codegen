from typing import Callable, TypeVar

from ..ast_ssc import (
    BaseAstNode,
    BaseExpression,
    Docstring,
    ModuleImports,
    ModuleProgram,
    PartDocFunction,
    PreValidateFunction,
    StartParseFunction,
    StructFieldFunction,
    StructParser,
    TypeDef,
    TypeDefField,
    Variable,
    JsonStruct,
    JsonStructField,
)
from ..tokens import TokenType

T_NODE = TypeVar("T_NODE", BaseAstNode, BaseExpression)


CB_AST_BIND = Callable[[T_NODE], str]
CB_AST_DECORATOR = Callable[[CB_AST_BIND], CB_AST_BIND]


def debug_msg_cb(node: T_NODE, comment_prefix: str) -> str:
    match node.kind:
        case TokenType.EXPR_RETURN:
            return f"{comment_prefix}Token: {node.kind.name} ret_type: {node.ret_type.name}"
        case TokenType.EXPR_DEFAULT_START:
            return (
                f"{comment_prefix} Token: {node.kind.name}, value: {node.value}"
            )
        case TokenType.STRUCT_PARSE_START:
            return (
                f"{comment_prefix}Token: {node.kind.name} struct_type: {node.type.name}\n"
                f"{comment_prefix}Call instructions count: {len(node.body)}"
            )
        case TokenType.STRUCT:
            return (
                f"{comment_prefix}Token: {node.kind.name} struct_type: {node.type.name}\n"
                f"{comment_prefix}FuncsCount: {len(node.body)}"
            )
        case TokenType.STRUCT_FIELD:
            ret_type = node.body[-1].ret_type.name
            return f"{comment_prefix} Token: {node.kind.name} field: {node.name} ret_type: {ret_type}"

        case TokenType.TYPEDEF:
            if node.struct_ref:
                return f"{comment_prefix}Token: {node.kind.name} type: {node.struct_ref.type.name}"
            return f"{comment_prefix}Token: {node.kind.name}"
        case _:
            return f"{comment_prefix}Token: {node.kind.name}"


class BaseCodeConverter:
    """Base code class converter that translates AST nodes into code."""

    def __init__(
        self,
        debug_instructions: bool = False,
        debug_comment_prefix: str = "",
        debug_cb: Callable[[BaseAstNode, str], str] = debug_msg_cb,
    ):
        self.pre_definitions: dict[TokenType, CB_AST_BIND] = {}
        self.post_definitions: dict[TokenType, CB_AST_BIND] = {}

        self.debug_instructions = debug_instructions
        self.debug_comment_prefix = debug_comment_prefix
        self.debug_msg_cb = debug_cb

    def set_debug_prefix(self, comment_prefix: str) -> None:
        """Set the debug comment prefix and enable debug instructions."""
        self.debug_comment_prefix = comment_prefix
        self.debug_instructions = True

    def disable_debug(self) -> None:
        """Disable debug instructions."""
        self.debug_instructions = False

    def __call__(self, for_definition: TokenType) -> CB_AST_DECORATOR:
        """Alias for pre decorator."""
        return self.pre(for_definition)

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

    def _get_debug_prefix(self, node: BaseAstNode) -> str:
        """Generate debug prefix for the given node."""
        return self.debug_msg_cb(node, self.debug_comment_prefix)

    def _pre_convert_node(self, node: BaseAstNode) -> str:
        """Convert the AST node using the pre-definition function."""
        if pre_func := self.pre_definitions.get(node.kind):
            if self.debug_instructions:
                prefix = self._get_debug_prefix(node)
                return f"{prefix}\n{pre_func(node)}"
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
                self._convert_module(ast_entry, acc)  # type: ignore[arg-type]
            case TokenType.DOCSTRING:
                self._convert_module_docstring(ast_entry, acc)  # type: ignore[arg-type]
            case TokenType.IMPORTS:
                self._convert_imports(ast_entry, acc)  # type: ignore[arg-type]
            case TokenType.TYPEDEF:
                self._convert_typedef(ast_entry, acc)  # type: ignore[arg-type]
            case TokenType.TYPEDEF_FIELD:
                self._convert_typedef_field(ast_entry, acc)  # type: ignore[arg-type]
            case TokenType.STRUCT:
                self._convert_struct(ast_entry, acc)  # type: ignore[arg-type]
            case TokenType.JSON_STRUCT:
                self._convert_json_struct(ast_entry, acc)  # type: ignore[arg-type]
            case TokenType.JSON_FIELD:
                self._convert_json_struct_field(ast_entry, acc)  # type: ignore[arg-type]
            case _ if ast_entry.kind in {
                TokenType.STRUCT_PART_DOCUMENT,
                TokenType.STRUCT_PRE_VALIDATE,
                TokenType.STRUCT_PARSE_START,
                TokenType.STRUCT_FIELD,
            }:
                self._convert_struct_method(ast_entry, acc)  # type: ignore[arg-type]
            case _:
                self._convert_default(ast_entry, acc)
        return acc

    def _convert_module(self, ast_entry: ModuleProgram, acc: list[str]) -> None:
        """Handle module conversion."""
        for node in ast_entry.body:
            self.convert(node, acc)

    def _convert_module_docstring(
        self, ast_entry: Docstring, acc: list[str]
    ) -> None:
        """Handle docstring conversion."""
        if ast_entry.parent.kind == TokenType.MODULE:
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
        if getattr(ast_entry, "docstring_class_top", False) and getattr(
            ast_entry, "doc", False
        ):
            # pre_DOCSTRING + post_DOCSTIRNG
            # pre_CLASS/STRUCT HEADER
            # pre_CONSTRUCTOR post_CONSTRUCTOR
            # BODY
            # post_CLASS/STRUCT

            # doc -> class header -> constructor -> body -> class footer
            acc.append(self._pre_convert_node(ast_entry.doc))
            acc.append(self._post_convert_node(ast_entry.doc))

            acc.append(self._pre_convert_node(ast_entry))

            acc.append(self._pre_convert_node(ast_entry.init))
            acc.append(self._post_convert_node(ast_entry.init))
            for node in ast_entry.body:
                self.convert(node, acc)
            acc.append(self._post_convert_node(ast_entry))

        else:
            # pre_CLASS/STRUCT HEADER
            # pre_DOCSTRING + post_DOCSTIRNG
            # pre_CONSTRUCTOR post_CONSTRUCTOR
            # BODY
            # post_CLASS/STRUCT
            # class header -> doc -> costructor -> body -> class footer
            acc.append(self._pre_convert_node(ast_entry))

            acc.append(self._pre_convert_node(ast_entry.doc))
            acc.append(self._post_convert_node(ast_entry.doc))

            acc.append(self._pre_convert_node(ast_entry.init))
            acc.append(self._post_convert_node(ast_entry.init))

            for node in ast_entry.body:
                self.convert(node, acc)

            acc.append(self._post_convert_node(ast_entry))

    def _convert_struct_method(
        self,
        ast_entry: StructFieldFunction
        | StartParseFunction
        | PreValidateFunction
        | PartDocFunction,
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


def left_right_var_names(name: str, variable: Variable) -> tuple[str, str]:
    """helper var counter for generate variable names

    returns prev, next variable names
    """
    if variable.num == 0:
        prev = name
    else:
        prev = f"{name}{variable.num}"
    next_ = f"{name}{variable.num_next}"
    return prev, next_
