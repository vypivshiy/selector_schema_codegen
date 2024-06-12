from typing import Callable, Tuple, TYPE_CHECKING, Optional

from ssc_codegen.expression import Expression
from ssc_codegen.tokens import TokenType

if TYPE_CHECKING:
    from ssc_codegen.converters.generator import TemplateStruct


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
            type_prefix: str = "T_"
    ):
        self.type_prefix = type_prefix
        self.definitions: dict[TokenType, Callable[[Expression], str]] = {}
        self._cb_type_converter: Optional[Callable[["TemplateStruct"], str]] = None
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

    @property
    def cb_type_converter(self):
        return self._cb_type_converter

    @cb_type_converter.setter
    def cb_type_converter(self, cb: Callable[["TemplateStruct"], str]):
        self._cb_type_converter = cb

    def convert_types(self, struct: "TemplateStruct") -> str:
        if not self.cb_type_converter:
            raise AttributeError("Missing type_converter callback")
        return self._cb_type_converter(struct)

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

    def convert_types(self, struct: "TemplateStruct", prefix: str = "T_") -> str:
        pass

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
