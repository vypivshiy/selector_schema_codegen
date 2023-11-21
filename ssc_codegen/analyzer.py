import warnings
from typing import Generator

from ssc_codegen.exceptions import (
    SyntaxAttributeError,
    SyntaxCommandError,
    SyntaxVariableTypeError,
)
from ssc_codegen.objects import Node, Token, TokenType, VariableState

__all__ = [
    "VariableState",
    "Analyzer",
]


class Analyzer:
    def __init__(self, tokens: list["Token"]):
        """Analyze tokens to correct syntax rules

        :param tokens: tokenized code
        """
        self.all_tokens = tokens
        # remove comments, empty lines tokens
        self.code_tokens = [
            token
            for token in tokens
            if token.token_type
            not in (TokenType.OP_NEW_LINE, TokenType.OP_COMMENT)
        ]
        # first argument - selector-like value
        self.__variable_state: VariableState = VariableState.SELECTOR

    def lazy_analyze(
        self,
    ) -> Generator[tuple["Token", VariableState], None, None]:
        """lazy analyzer. returns token and variable state in every iteration"""
        for index, token in enumerate(self.code_tokens):
            match token.token_type:
                case TokenType.OP_TRANSLATE_DEFAULT_CODE:
                    self._default(index, token)
                    yield token, self.__variable_state

                # selector
                case TokenType.OP_CSS | TokenType.OP_XPATH:
                    self._selector(index, token)
                    yield token, self.__variable_state

                case TokenType.OP_CSS_ALL | TokenType.OP_XPATH_ALL:
                    # TODO add syntax analyze for this type
                    self._selector_array(index, token)
                    self.__variable_state = VariableState.SELECTOR_ARRAY
                    yield token, self.__variable_state

                # selector end methods
                case TokenType.OP_ATTR | TokenType.OP_ATTR_RAW | TokenType.OP_ATTR_TEXT:
                    self._selector_methods(index, token)
                    if token.token_type in TokenType.tokens_selector_extract():
                        if (
                            self.__variable_state
                            == VariableState.SELECTOR_ARRAY
                        ):
                            self.__variable_state = VariableState.ARRAY
                        else:
                            self.__variable_state = VariableState.TEXT
                    if self.__variable_state == VariableState.SELECTOR_ARRAY:
                        self.__variable_state = VariableState.ARRAY
                    yield token, self.__variable_state

                # strings
                case TokenType.OP_STRING_FORMAT | TokenType.OP_STRING_REPLACE | TokenType.OP_STRING_TRIM | (
                    TokenType.OP_STRING_L_TRIM
                ) | TokenType.OP_STRING_R_TRIM | TokenType.OP_STRING_SPLIT:
                    self._string_methods(index, token)
                    if token.token_type is TokenType.OP_STRING_SPLIT:
                        self.__variable_state = VariableState.ARRAY
                    yield token, self.__variable_state

                # array
                case TokenType.OP_INDEX | TokenType.OP_FIRST | TokenType.OP_LAST | TokenType.OP_LIMIT | (
                    TokenType.OP_JOIN
                ):
                    self._array_methods(index, token)
                    if token.token_type in (
                        TokenType.OP_INDEX,
                        TokenType.OP_FIRST,
                        TokenType.OP_LAST,
                    ):
                        if (
                            self.__variable_state
                            == VariableState.SELECTOR_ARRAY
                        ):
                            self.__variable_state = VariableState.SELECTOR
                        elif self.__variable_state == VariableState.ARRAY:
                            self.__variable_state = VariableState.TEXT
                    elif token.token_type == TokenType.OP_JOIN:
                        if self.__variable_state == VariableState.ARRAY:
                            self.__variable_state = VariableState.TEXT
                        else:
                            msg = self.__err_msg(
                                token, "prev variable is not ARRAY"
                            )
                            raise SyntaxVariableTypeError(msg)
                    yield token, self.__variable_state

                # validators
                case TokenType.OP_ASSERT | TokenType.OP_ASSERT_STARTSWITH | TokenType.OP_ASSERT_ENDSWITH | (
                    TokenType.OP_ASSERT_MATCH
                ) | TokenType.OP_ASSERT_CONTAINS:
                    self._validator_str_methods(index, token)
                    yield token, self.__variable_state
                case TokenType.OP_ASSERT_CSS | TokenType.OP_ASSERT_XPATH:
                    self._validator_selector_methods(index, token)
                    yield token, self.__variable_state

                # regex
                case TokenType.OP_REGEX | TokenType.OP_REGEX_ALL | TokenType.OP_REGEX_SUB:
                    self._regex(index, token)
                    if token.token_type == TokenType.OP_REGEX_ALL:
                        self.__variable_state = VariableState.ARRAY
                    yield token, self.__variable_state

                case TokenType.OP_NO_RET:
                    yield token, self.__variable_state
                case TokenType.OP_RET:
                    yield token, self.__variable_state
                case _:
                    msg = f"Some analyzer issue: missing analyze step check:\n{token}"
                    warnings.warn(msg, category=RuntimeWarning)
                    yield token, self.__variable_state

    def build_ast(self) -> dict[int, Node]:
        """build hash map commands representation
        ast structure:

            0 : Node(... count=n, prev=None, next=1)
            1: Node(..., count=n, prev=0, next=2),
            ...
            n: Node(..., prev=n-1, next=None)

        :return: ast-like structure
        """
        _tree: dict[int, Node] = {}
        count = len(self.code_tokens)

        i: int
        for i, (token, var_state) in enumerate(self.lazy_analyze()):
            node = Node(
                num=i,
                count=count,
                token=token,
                var_state=var_state,
                prev=None,
                next=None,
                ast_tree=_tree,
            )
            if i - 1 >= 0:
                node.prev = i - 1
            if i + 1 < count:
                node.next = i + 1

            _tree[i] = node
        return _tree

    def analyze_and_extract_tokens(self) -> list["Token"]:
        tokens = [token for token, _ in self.lazy_analyze()]
        return tokens

    def _regex(self, index: int, token: "Token"):
        if self.__variable_state == VariableState.TEXT:
            return
        msg = self.__err_msg(token, "Regex command should be accept TEXT")
        raise SyntaxVariableTypeError(msg)

    def _selector_array(self, index: int, token: "Token"):
        if self.__variable_state in (
            VariableState.SELECTOR,
            VariableState.SELECTOR_ARRAY,
        ):
            return
        msg = self.__err_msg(
            token,
            "SELECTOR_ARRAY should be accept SELECTOR or SELECTOR_ARRAY, not TEXT",
        )
        raise SyntaxVariableTypeError(msg)

    @staticmethod
    def __err_msg(token: "Token", msg: str) -> str:
        return f"\n{token.line}:{token.pos} :: {token.raw_code}\n{msg}"

    def _validator_selector_methods(self, index: int, token: "Token"):
        if self.__variable_state == VariableState.SELECTOR:
            return
        msg = self.__err_msg(
            token, "Validator command should be accept selector-like object"
        )
        raise SyntaxVariableTypeError(msg)

    def _validator_str_methods(self, index: int, token: "Token"):
        if self.__variable_state == VariableState.TEXT:
            return
        msg = self.__err_msg(
            token, "Validator command should be accept string-like object"
        )
        raise SyntaxVariableTypeError(msg)

    def _default(self, index: int, token: "Token"):
        if index == 0:
            return
        msg = self.__err_msg(token, "`default` command should be a first")
        raise SyntaxCommandError(msg)

    def _selector(self, index: int, token: "Token"):
        if self.__variable_state in (
            VariableState.SELECTOR,
            VariableState.SELECTOR_ARRAY,
        ):
            for second_token in self.code_tokens[index:]:
                if second_token.token_type in TokenType.tokens_selector_all():
                    if token.token_type in (
                        TokenType.OP_INDEX,
                        TokenType.OP_FIRST,
                        TokenType.OP_LAST,
                    ):
                        return
                    continue
                elif (
                    second_token.token_type
                    in TokenType.tokens_selector_extract()
                ):
                    return
            msg = self.__err_msg(
                token,
                "Selector missing extract attribute ('attr \"<expr>\"', 'raw' or 'text')",
            )
            raise SyntaxAttributeError(msg)

        msg = self.__err_msg(
            token, "Prev variable is not SELECTOR/SELECTOR_ARRAY type"
        )
        raise SyntaxVariableTypeError(msg)

    def _selector_methods(self, index: int, token: "Token"):
        # convert first chunk to text case
        if index == 0 and token.token_type in (
            TokenType.OP_ATTR_TEXT,
            TokenType.OP_ATTR_RAW,
        ):
            return

        elif self.__variable_state in (
            VariableState.SELECTOR,
            VariableState.SELECTOR_ARRAY,
        ):
            return

        msg = self.__err_msg(
            token, "Missing selector command: (xpath, xpathAll, css, cssAll)"
        )
        raise SyntaxCommandError(msg)

    def _string_methods(self, index: int, token: "Token"):
        if self.__variable_state is VariableState.TEXT:
            return
        msg = self.__err_msg(token, "Prev variable is not TEXT")
        raise SyntaxVariableTypeError(msg)

    def _array_methods(self, index: int, token: "Token"):
        if self.__variable_state in (
            VariableState.ARRAY,
            VariableState.SELECTOR_ARRAY,
        ):
            return
        msg = self.__err_msg(token, "Prev variable is not ARRAY")
        raise SyntaxVariableTypeError(msg)


if __name__ == "__main__":
    from ssc_codegen.lexer import tokenize

    src = """
raw
format "raw attr {{}}"
"""
    toks = tokenize(src)
    a = Analyzer(toks)
    tree = a.build_ast()
    print()
