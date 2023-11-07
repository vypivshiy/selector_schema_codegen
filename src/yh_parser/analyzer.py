import re
import warnings
from typing import TYPE_CHECKING
from enum import Enum

from lexer import tokenize, TokenType

if TYPE_CHECKING:
    from lexer import Token

SELECTOR_TOKENS = (TokenType.OP_XPATH, TokenType.OP_XPATH_ALL,
                   TokenType.OP_CSS, TokenType.OP_CSS_ALL)
SELECTOR_METHODS = (TokenType.OP_ATTR, TokenType.OP_ATTR_RAW, TokenType.OP_ATTR_TEXT)

SELECTOR_ARRAY_METHODS = (TokenType.OP_XPATH_ALL, TokenType.OP_CSS_ALL)

STRING_METHODS = (TokenType.OP_STRING_FORMAT, TokenType.OP_STRING_REPLACE, TokenType.OP_STRING_TRIM,
                  TokenType.OP_STRING_L_TRIM, TokenType.OP_STRING_R_TRIM, TokenType.OP_STRING_SPLIT)
ARRAY_METHODS = (TokenType.OP_INDEX, TokenType.OP_FIRST, TokenType.OP_LAST, TokenType.OP_SLICE,
                 TokenType.OP_JOIN)

COMMENT_TOKENS = (TokenType.OP_NEW_LINE, TokenType.OP_COMMENT)


class VariableState(Enum):
    SELECTOR = 0
    TEXT = 1
    ARRAY = 2


class Analyzer:

    def __init__(self, tokens: list["Token"]):
        self.tokens = tokens
        # remove comments, empty lines tokens
        self.code_tokens = [token for token in tokens if token.token_type not in COMMENT_TOKENS]
        self.__variable_state: VariableState = VariableState.SELECTOR

    def analyze(self) -> list["Token"]:
        for index, token in enumerate(self.code_tokens):
            token_type = TokenType[token.token_type.name]
            match token.token_type:
                case TokenType.OP_DEFAULT:
                    self._default(index, token)
                # selector
                case TokenType.OP_CSS | TokenType.OP_CSS_ALL | TokenType.OP_XPATH | TokenType.OP_XPATH_ALL:
                    self._selector(index, token)
                # selector end methods
                case TokenType.OP_ATTR | TokenType.OP_ATTR_RAW | TokenType.OP_ATTR_TEXT:
                    self._selector_methods(index, token)
                    if token.token_type in SELECTOR_METHODS:
                        self.__variable_state = VariableState.TEXT
                    elif token.token_type in SELECTOR_ARRAY_METHODS:
                        self.__variable_state = VariableState.ARRAY
                # strings
                case TokenType.OP_STRING_FORMAT | TokenType.OP_STRING_REPLACE | TokenType.OP_STRING_TRIM \
                        | TokenType.OP_STRING_L_TRIM | TokenType.OP_STRING_R_TRIM | TokenType.OP_STRING_SPLIT:
                    self._string_methods(index, token)
                    if token.token_type is TokenType.OP_STRING_SPLIT:
                        self.__variable_state = VariableState.ARRAY
                # array
                case TokenType.OP_INDEX | TokenType.OP_FIRST | TokenType.OP_LAST \
                        | TokenType.OP_SLICE | TokenType.OP_JOIN:
                    self._array_methods(index, token)
                    if token.token_type in (TokenType.OP_JOIN, TokenType.OP_INDEX, TokenType.OP_FIRST, TokenType.OP_LAST):
                        self.__variable_state = VariableState.TEXT
                case _:
                    warnings.warn("Some analyzer issue: missing step check")
        return self.code_tokens

    def _default(self, index: int, token: "Token"):
        if index == 0:
            return
        msg = (f"\n{token.line}:{token.pos} :: {token.code}\n"
               f"default command should be a first")
        raise SyntaxError(msg)

    def _selector(self, index: int, token: "Token"):
        if self.__variable_state != VariableState.SELECTOR:
            msg = (f"\n{token.line}:{token.pos} :: {token.code}\n"
                   f"prev variable is not selector type")
            raise SyntaxError(msg)

        for second_token in self.code_tokens[index:]:
            if second_token.token_type in SELECTOR_TOKENS:
                continue
            elif second_token.token_type in SELECTOR_METHODS:
                return
        msg = (f"\n{token.line}:{token.pos} :: {token.code}\n"
               f"Selector missing extract attribute "
               f"('attr <expr>', 'raw' or 'text')")
        raise SyntaxError(msg)

    def _selector_methods(self, index: int, token: "Token"):
        prev_token_i = index - 1
        # convert first chunk to text
        if index == 0 and token.token_type == TokenType.OP_ATTR_TEXT:
            return

        elif (self.code_tokens[prev_token_i].token_type in SELECTOR_TOKENS and
              self.__variable_state == VariableState.SELECTOR):
            return

        msg = (f"\n{token.line}:{token.pos} :: {token.code}\n"
               f"Missing selector command: "
               f"(xpath, xpathAll, css, cssAll)")
        raise SyntaxError(msg)

    def _string_methods(self, index: int, token: "Token"):
        if self.__variable_state != VariableState.TEXT:
            msg = (f"\n{token.line}:{token.pos} :: {token.code}\n"
                   f"prev variable is not string")
            raise SyntaxError(msg)

    def _array_methods(self, index: int, token: "Token"):
        if self.__variable_state != VariableState.ARRAY:
            msg = (f"\n{token.line}:{token.pos} :: {token.code}\n"
                   f"prev variable is not array")
            raise SyntaxError(msg)


def dummy_codegen(tokens: list["Token"]):
    code = """
from parsel import Selector


def dummy_parser(value: Selector):
"""
    code += "\t"
    for token in tokens:
        if token.token_type == TokenType.OP_XPATH:
            code += f"value = value.xpath({token.values[0]!r})"
        elif token.token_type == TokenType.OP_ATTR:
            code += f"value = value.attrib.get({token.values[0]!r})"
        elif token.token_type == TokenType.OP_ATTR_TEXT:
            code += f"value = value.xpath('//text()').get()"
        elif token.token_type == TokenType.OP_STRING_R_TRIM:
            code += f"value = value.rstrip({token.values[0]!r})"
        elif token.token_type == TokenType.OP_STRING_FORMAT:
            val = token.values[0]
            val = re.sub(r'\{\{.*}}', '{}', val)
            code += f"value = {val}.format(value)"
        code += '\n\t'
    code += "return value\n\n"
    return code


if __name__ == '__main__':
    example = """xpath '//div[@class="image_container"]/a'
    xpath '//a/a'
    text
    rstrip "//"
    format "https://books.toscrape.com/catalogue/{{}}"
    format "https://books.toscrape.com/catalogue/{{my_value}}"    
    """
    tokens_ = tokenize(example)
    checked_tokens = Analyzer(tokens_).analyze()
    print(dummy_codegen(checked_tokens))
