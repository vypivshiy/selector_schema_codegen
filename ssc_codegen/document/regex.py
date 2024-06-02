from ssc_codegen.document.base import BaseDocument, TokenType, TypeVariableState


class DocumentOpRegex(BaseDocument):
    def re(self, pattern: str):
        """get first match by regular expression"""
        self._test_type_state_expr(
            TypeVariableState.STRING, TypeVariableState.LIST_STRING
        )

        self._add_expr(TokenType.OP_REGEX, args=(pattern,))
        return self

    def re_all(self, pattern: str):
        """get all matches by regular expression"""
        self._test_type_state_expr(TypeVariableState.STRING)

        self._add_expr(
            TokenType.OP_REGEX_ALL,
            args=(pattern,),
            new_var_state=TypeVariableState.LIST_STRING,
        )
        return self

    def re_sub(self, pattern: str, repl: str):
        self._test_type_state_expr(
            TypeVariableState.STRING, TypeVariableState.LIST_STRING
        )

        self._add_expr(TokenType.OP_REGEX_SUB, args=(pattern, repl))
        return self
