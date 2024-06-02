from typing_extensions import deprecated

from ssc_codegen.document.base import BaseDocument, TokenType, TypeVariableState


class DocumentOpString(BaseDocument):
    @deprecated("Use ltrim instead")
    def lstrip(self, prefix: str):
        return self.ltrim(prefix)

    def ltrim(self, prefix: str):
        """remove prefix from string (from the left)"""
        self._test_type_state_expr(
            TypeVariableState.STRING, TypeVariableState.LIST_STRING
        )
        self._add_expr(TokenType.OP_STRING_L_TRIM, args=(prefix,))
        return self

    @deprecated("Use rtrim instead")
    def rstrip(self, suffix: str):
        """remove suffix from string (from the right)"""
        return self.rtrim(suffix)

    def rtrim(self, suffix: str):
        """remove suffix from string (from the right)"""
        self._test_type_state_expr(
            TypeVariableState.STRING, TypeVariableState.LIST_STRING
        )
        self._add_expr(TokenType.OP_STRING_R_TRIM, args=(suffix,))
        return self

    @deprecated("Use trim instead")
    def strip(self, sting: str):
        """strip string from string (from the left and right)"""
        return self.trim(sting)

    def trim(self, string_: str):
        """strip string from string (from the left and right)"""
        self._test_type_state_expr(
            TypeVariableState.STRING, TypeVariableState.LIST_STRING
        )

        self._add_expr(TokenType.OP_STRING_TRIM, args=(string_,))
        return self

    def split(self, sep: str):
        """split string by `sep` argument"""
        self._test_type_state_expr(TypeVariableState.STRING)

        self._add_expr(
            TokenType.OP_STRING_SPLIT,
            args=(sep,),
            new_var_state=TypeVariableState.LIST_STRING,
        )
        return self

    def format(self, template: str):
        """format string by pattern.

        fmt argument should be contained {{}} mark"""
        self._test_type_state_expr(
            TypeVariableState.STRING, TypeVariableState.LIST_STRING
        )
        if "{{}}" not in template:
            raise SyntaxError("Missing `{{}}` mark in template argument")
        self._add_expr(TokenType.OP_STRING_FORMAT, args=(template,))
        return self

    def fmt(self, template: str):
        """format method shortcut"""
        return self.format(template)

    def replace(self, old: str, new: str):
        """replace `old` arg in string in all places to `new`"""
        self._test_type_state_expr(
            TypeVariableState.STRING, TypeVariableState.LIST_STRING
        )
        self._add_expr(TokenType.OP_STRING_REPLACE, args=(old, new))
        return self

    def repl(self, old: str, new: str):
        """replace method shortcut"""
        return self.replace(old, new)
