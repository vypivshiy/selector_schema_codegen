from typing import Callable, Tuple

from ssc_codegen.expression import Expression
from ssc_codegen.tokens import TokenType


class BaseCodeConverter:
    def __init__(
        self,
        *,
        # code
        indent_mul: int = 1,  # indent mul
        chr_indent: str = "\t",  # indent char
        end: str = "",  # end line of code
        # default code wrapper
        default_indent: int = 2,
    ):
        self.definitions: dict[TokenType, Callable[[Expression], str]] = {}
        self._indent = indent_mul
        self._chr_indent = chr_indent
        self._end = end
        self._default_indent = default_indent
        self._indent_state = False

    def __call__(self, for_definition: TokenType):
        def decorator(func):
            self.definitions[for_definition] = func
            return func

        return decorator

    def convert(self, expr: Expression) -> str:
        if expr.TOKEN_TYPE == TokenType.ST_METHOD:
            self._indent_state = True

        if cb := self.definitions.get(expr.TOKEN_TYPE):
            code = cb(expr)
            if (
                self._indent_state
                and expr.TOKEN_TYPE is not TokenType.ST_METHOD
            ):
                if expr.TOKEN_TYPE in (TokenType.ST_RET, TokenType.ST_NO_RET):
                    self._indent_state = False
                return self._indent * self._chr_indent + code + self._end
            return code + self._end
        raise KeyError(f"Missing {expr.VARIABLE_TYPE!r} converter rule")

    @staticmethod
    def create_var_names(
        expr: Expression, prefix: str = "var", sep: str = "_"
    ) -> Tuple[str, str]:
        """create var names aliases

        - 0 - LEFT VAR
        - 1 - RIGHT VAR

        """
        if expr.num == 0:
            return prefix, "el"
        elif expr.num == 1:
            return f"{prefix}{sep}1", prefix
        return f"{prefix}{sep}{expr.num}", f"{prefix}{sep}{expr.num - 1}"
