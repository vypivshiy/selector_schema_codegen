from typing import Any, NamedTuple

from ssc_codegen.tokens import TokenType
from ssc_codegen.type_state import TypeVariableState


class Expression(NamedTuple):
    num: int
    VARIABLE_TYPE: TypeVariableState
    TOKEN_TYPE: TokenType
    arguments: tuple[Any, ...] = ()

    def update_var_type(self, var_type: TypeVariableState) -> "Expression":
        return Expression(
            num=self.num,
            VARIABLE_TYPE=var_type,
            TOKEN_TYPE=self.TOKEN_TYPE,
            arguments=self.arguments,
        )
