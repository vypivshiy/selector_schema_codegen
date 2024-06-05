import re

from ssc_codegen.document.base import BaseDocument, TokenType, TypeVariableState
from ssc_codegen.utils.re_validator import try_compile_pattern_expr


class DocumentOpRegex(BaseDocument):
    def re(self, pattern: str, group: int = 1):
        """get first match by regular expression"""
        self._test_type_state_expr(
            TypeVariableState.STRING, TypeVariableState.LIST_STRING
        )
        try_compile_pattern_expr(pattern)

        self._add_expr(TokenType.OP_REGEX, args=(pattern, group))
        return self

    def re_all(self, pattern: str):
        """get all matches by regular expression"""
        self._test_type_state_expr(TypeVariableState.STRING)
        try_compile_pattern_expr(pattern)

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
        try_compile_pattern_expr(pattern)

        self._add_expr(TokenType.OP_REGEX_SUB, args=(pattern, repl))
        return self
