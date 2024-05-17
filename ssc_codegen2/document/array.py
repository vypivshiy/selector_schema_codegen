from ssc_codegen2.document.base import (
    BaseDocument,
    TypeVariableState,
    TokenType,
)


class DocumentOpArray(BaseDocument):
    """operations with array"""

    def first(self):
        """alias index(0)"""
        return self.index(0)

    def last(self):
        """alias index(-1)"""
        return self.index(-1)

    def index(self, i: int):
        """get element by index from collection"""
        self._test_type_state_expr(
            TypeVariableState.LIST_STRING, TypeVariableState.LIST_DOCUMENT
        )

        if self.last_var_type is TypeVariableState.LIST_DOCUMENT:
            self._add_expr(
                TokenType.OP_INDEX,
                args=(i,),
                new_var_state=TypeVariableState.DOCUMENT,
            )
        elif self.last_var_type is TypeVariableState.LIST_STRING:
            self._add_expr(
                TokenType.OP_INDEX,
                new_var_state=TypeVariableState.STRING,
                args=(i,),
            )
        else:
            raise SyntaxError("TODO")
        return self

    def join(self, prefix: str):
        """join list of sting to array"""
        self._test_type_state_expr(TypeVariableState.LIST_STRING)

        self._add_expr(
            TokenType.OP_JOIN,
            args=(prefix,),
            new_var_state=TypeVariableState.STRING,
        )
        return self
