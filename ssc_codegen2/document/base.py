# high level expression collector
from typing import Optional, Any, Tuple
from typing_extensions import Self
from ssc_codegen2.expression import Expression
from ssc_codegen2.tokens import TokenType
from ssc_codegen2.type_state import TypeVariableState


class BaseDocument:
    def __init__(self):
        self._stack_instructions: list[Expression] = []

    def __repr__(self):
        comma_stack = ", ".join(
            [
                f"{e.TOKEN_TYPE.name}{repr(e.arguments).rstrip(',)') + ')' or ''}"
                for e in self._stack_instructions
            ]
        )
        return f"Document(len={self.num}, ret_type={self.last_var_type.name}, commands=[{comma_stack}])"

    @property
    def instructions(self) -> list[Expression]:
        return self._stack_instructions

    @property
    def num(self):
        return len(self._stack_instructions)

    @property
    def _last_index(self) -> int:
        len_ = len(self._stack_instructions)
        return 0 if len_ == 0 else len_ - 1

    def _add_expr(
        self,
        token_type: TokenType,
        new_var_state: Optional[TypeVariableState] = None,
        args: Tuple[Any, ...] = (),
    ):
        state = new_var_state or self.last_var_type
        e = Expression(
            num=self.num,
            VARIABLE_TYPE=state,
            TOKEN_TYPE=token_type,
            arguments=args,
        )
        self._stack_instructions.append(e)

    def _test_type_state_expr(self, *var_types: TypeVariableState) -> None:
        if self._last_index == 0:
            return

        expr = self._stack_instructions[self._last_index]
        if expr.VARIABLE_TYPE in var_types:
            return
        msg = f"Excepted type(s) {tuple(v.name for v in var_types)}, got {expr.VARIABLE_TYPE.name}"
        raise SyntaxError(msg)

    @property
    def last_var_type(self) -> TypeVariableState:
        if self.num == 0:
            return TypeVariableState.DOCUMENT
        return self._stack_instructions[self._last_index].VARIABLE_TYPE

    def default(self, value: Optional[str]) -> Self:
        """Set default value. Accept string or None"""
        if self.num != 0:
            raise Exception("default expression should be first")
        self._add_expr(TokenType.ST_DEFAULT, args=(value,))
        return self
