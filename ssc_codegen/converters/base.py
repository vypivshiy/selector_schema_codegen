from typing import Callable

from ..ast_ssc import BaseAstNode, ModuleProgram, StructParser, Variable
from ..tokens import TokenType


class BaseCodeConverter:
    """base code class converter"""

    def __init__(self):
        self.pre_definitions: dict[TokenType, Callable[[BaseAstNode], str]] = {}
        self.post_definitions: dict[
            TokenType, Callable[[BaseAstNode], str]
        ] = {}

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
        return result

    def convert(
        self, ast_entry: BaseAstNode, acc: list[str] | None = None
    ) -> list[str]:
        """convert ast to code parts"""
        acc = acc or []
        if ast_entry.kind == TokenType.STRUCT and getattr(
            ast_entry, "docstring_class_top", False
        ):
            ast_entry: StructParser
            acc.append(self._pre_convert_node(ast_entry.doc))
            acc.append(self._post_convert_node(ast_entry.doc))

        acc.append(self._pre_convert_node(ast_entry))
        if ast_entry.kind == TokenType.STRUCT:
            ast_entry: StructParser
            if not ast_entry.docstring_class_top:
                acc.append(self._pre_convert_node(ast_entry.doc))
                acc.append(self._post_convert_node(ast_entry.doc))

            acc.append(self._pre_convert_node(ast_entry.init))
            acc.append(self._post_convert_node(ast_entry.init))
        if getattr(ast_entry, "body", None):
            if ast_entry.kind == TokenType.STRUCT_FIELD and ast_entry.default:
                acc.append(self._pre_convert_node(ast_entry.default))

            for ast_node in ast_entry.body:
                self.convert(ast_node, acc)

            if ast_entry.kind == TokenType.STRUCT_FIELD and ast_entry.default:
                acc.append(self._post_convert_node(ast_entry.default))
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
