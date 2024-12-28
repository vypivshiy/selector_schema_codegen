from typing import Callable

from ..ast_ssc import BaseAstNode, ModuleProgram, Variable
from ..tokens import TokenType


class BaseCodeConverter:
    """base code class converter"""

    def __init__(self,
                 debug_instructions: bool = False,
                 debug_comment_prefix: str = ""):
        self.pre_definitions: dict[TokenType, Callable[[BaseAstNode], str]] = {}
        self.post_definitions: dict[
            TokenType, Callable[[BaseAstNode], str]
        ] = {}

        self.debug_instructions = debug_instructions
        self.debug_comment_prefix = debug_comment_prefix

    def set_debug_prefix(self, comment_prefix: str) -> None:
        self.debug_comment_prefix = comment_prefix
        self.debug_instructions = True

    def disable_debug(self) -> None:
        self.debug_instructions = False

    def __call__(self, for_definition: TokenType):
        """alias of pre decorator"""
        return self.pre(for_definition)

    def pre(self, for_definition: TokenType):
        """before translate ast to code"""

        def decorator(func: Callable[[BaseAstNode], str]):
            self.pre_definitions[for_definition] = func
            return func

        return decorator

    def post(self, for_definition: TokenType):
        """after translate ast to code"""

        def decorator(func: Callable[[BaseAstNode], str]):
            self.post_definitions[for_definition] = func
            return func

        return decorator

    def _pre_convert_node(self, node: BaseAstNode) -> str:
        if self.pre_definitions.get(node.kind):
            if self.debug_instructions:
                if node.kind == TokenType.EXPR_RETURN:
                    prefix = f"{self.debug_comment_prefix}Token: {node.kind.name} ret_type: {node.ret_type.name}"
                else:
                    prefix = f"{self.debug_comment_prefix}Token: {node.kind.name}"
                return f"{prefix}\n{self.pre_definitions[node.kind](node)}"
            return self.pre_definitions[node.kind](node)
        return ""

    def _post_convert_node(self, node: BaseAstNode) -> str:
        if self.post_definitions.get(node.kind):
            return self.post_definitions[node.kind](node)
        return ""

    def convert_program(
            self, ast_program: ModuleProgram, comment: str = ""
    ) -> list[str]:
        """convert module AST to code parts"""
        acc = [comment]
        result = self.convert(ast_program, acc)
        return [i for i in result if i]

    def convert(
            self, ast_entry: BaseAstNode, acc: list[str] | None = None
    ) -> list[str]:
        """convert ast to code parts"""
        acc = acc or []
        # MODULE DOCSTRING
        match ast_entry.kind:
            # module entrypoint
            case TokenType.MODULE:
                for node in ast_entry.body:
                    self.convert(node, acc)
            case TokenType.DOCSTRING:
                # TOP DOC MODULE
                if ast_entry.parent.kind == TokenType.MODULE:
                    acc.append(self._pre_convert_node(ast_entry))
                    acc.append(self._post_convert_node(ast_entry))
            # IMPORTS
            case TokenType.IMPORTS:
                acc.append(self._pre_convert_node(ast_entry))
                acc.append(self._post_convert_node(ast_entry))
            # TYPEDEF
            case TokenType.TYPEDEF:
                acc.append(self._pre_convert_node(ast_entry))
                for node in ast_entry.body:
                    self.convert(node, acc)
                acc.append(self._post_convert_node(ast_entry))

            # TYPEDEF FIELD
            case TokenType.TYPEDEF_FIELD:
                acc.append(self._pre_convert_node(ast_entry))
                acc.append(self._post_convert_node(ast_entry))

            # STRUCT
            case TokenType.STRUCT:
                # struct docstring
                if getattr(ast_entry, "docstring_class_top", False) and getattr(ast_entry, "doc", False):
                    # doc
                    acc.append(self._pre_convert_node(ast_entry.doc))
                    acc.append(self._post_convert_node(ast_entry.doc))
                    # struct header
                    acc.append(self._pre_convert_node(ast_entry))
                    acc.append(self._post_convert_node(ast_entry))

                    for node in ast_entry.body:
                        self.convert(node, acc)

                else:
                    # struct header
                    acc.append(self._pre_convert_node(ast_entry))
                    # doc
                    acc.append(self._pre_convert_node(ast_entry.doc))
                    acc.append(self._post_convert_node(ast_entry.doc))

                    acc.append(self._post_convert_node(ast_entry))
                # constructor-like interface
                acc.append(self._pre_convert_node(ast_entry.init))
                acc.append(self._post_convert_node(ast_entry.init))

                # struct methods
                for node in ast_entry.body:
                    self.convert(node, acc)
            # struct methods headers
            case ast_entry.kind if (
                    ast_entry.kind in
                    (
                        TokenType.STRUCT_PART_DOCUMENT,
                        TokenType.STRUCT_PRE_VALIDATE,
                        TokenType.STRUCT_PARSE_START,
                        TokenType.STRUCT_FIELD
                    )):
                acc.append(self._pre_convert_node(ast_entry))
                # method instructions
                for node in ast_entry.body:
                    # default wrapper
                    self.convert(node, acc)
                acc.append(self._post_convert_node(ast_entry))
            # methods
            case _:
                acc.append(self._pre_convert_node(ast_entry))
                acc.append(self._post_convert_node(ast_entry))
        return acc


def left_right_var_names(name: str, variable: Variable) -> tuple[str, str]:
    """helper generate variable names"""
    if variable.num == 0:
        prev = name
    else:
        prev = f"{name}{variable.num}"
    next_ = f"{name}{variable.num_next}"
    return prev, next_
