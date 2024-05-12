from typing import NamedTuple, Optional, Any
from ssc_codegen2.tokens import TokenType
from ssc_codegen2.type_state import TypeVariableState


class Expression(NamedTuple):
    num: int
    VARIABLE_TYPE: TypeVariableState
    TOKEN_TYPE: TokenType
    arguments: tuple[Any, ...]
    assert_message: Optional[str] = None

    def update_var_type(self, var_type: TypeVariableState) -> "Expression":
        return Expression(
            num=self.num,
            VARIABLE_TYPE=var_type,
            TOKEN_TYPE=self.TOKEN_TYPE,
            arguments=self.arguments,
            assert_message=self.assert_message
        )


class Field:
    def __init__(self, name: str):
        self._name = name
        self._expressions: list["Expression"] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def expressions(self):
        return self._expressions

    def add(self, expr: "Expression"):
        self._expressions.append(expr)
