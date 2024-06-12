from typing import TYPE_CHECKING, Type

from ssc_codegen.document.base import BaseDocument, TokenType, TypeVariableState

if TYPE_CHECKING:
    from ssc_codegen.schema.base import BaseSchema


class DocumentOpNested(BaseDocument):
    """merge document by anoter schema"""

    def sub_parser(self, schema: Type["BaseSchema"]):
        """call another schema and return result. All commands will be ignored."""
        self._test_type_state_expr(TypeVariableState.DOCUMENT)

        self._add_expr(
            TokenType.OP_NESTED_SCHEMA,
            args=(
                schema.__name__,
                schema,
            ),  # instance for generate docstring fields signature
            new_var_state=TypeVariableState.NESTED,
        )
        return self
