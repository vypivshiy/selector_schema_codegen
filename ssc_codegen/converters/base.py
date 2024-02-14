from functools import partial

from ssc_codegen.objects import TokenType, Node


__all__ = ['CodeConverter', "VAR_L", "VAR_R"]


def var_left(node: Node, prefix: str) -> str:
    """get next variable name"""
    return prefix.format(node.id or 0)


def var_right(node: Node, prefix: str) -> str:
    """get previous variable name"""
    return prefix.format(node.prev_node.id or 0)


# Shortcuts hooks variable name
VAR_L = partial(var_left, prefix='var_{}')
VAR_R = partial(var_right, prefix='var_{}')


class CodeConverter:
    """Translate Expressions into the parser code"""

    def __init__(self,
                 indent: str = " " * 4,
                 end: str = "",
                 intent_inner_try: str = " " * 4 * 2,
                 templates_path: str = ""):

        self.indent = indent
        self.end = end
        self.indent_inner_try = intent_inner_try
        self.definitions: Dict[TokenType, Callable[[Node], str]] = {}  # type: ignore
        self._templates_path: str = templates_path

        self._in_inner_try: bool = False

    @property
    def templates_path(self) -> str:
        return self._templates_path

    def __call__(self, for_definition: TokenType):
        def decorator(func):
            self.definitions[for_definition] = func
            return func

        return decorator

    def convert(self, node: Node) -> str:
        if callback := self.definitions.get(node.token):
            if node.token == TokenType.OP_DEFAULT_START:
                self._in_inner_try = True
                return self.indent + callback(node)

            elif node.token == TokenType.OP_DEFAULT_END:
                self._in_inner_try = False
                return self.indent + callback(node)

            if self._in_inner_try:
                return self.indent_inner_try + callback(node) + self.end
            return self.indent + callback(node) + self.end
        return ""
