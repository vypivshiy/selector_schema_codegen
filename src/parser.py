from typing import Type, TYPE_CHECKING
from src.analyzer import Analyzer, VariableState
from src.lexer import TokenType, tokenize
import warnings

from src.tools import xpath_to_css, css_to_xpath
from src.configs.codegen_tools import ABCExpressionTranslator

if TYPE_CHECKING:
    from src.lexer import Token


class Parser:
    def __init__(self,
                 source_code: str,
                 translator: Type["ABCExpressionTranslator"] | "ABCExpressionTranslator",
                 analyzer: Type[Analyzer] = Analyzer,
                 ):
        self.raw_tokens = tokenize(source_code)
        self.analyzer = analyzer
        if isinstance(translator, ABCExpressionTranslator):
            self.translator = translator
        else:
            self.translator = translator()

    def xpath_to_css(self) -> None:
        warnings.warn(
            "This feature not guaranteed correct convert xpath to css",
            category=RuntimeWarning,
        )
        for token in self.raw_tokens:
            if token.token_type == TokenType.OP_XPATH:
                token.token_type = TokenType.OP_CSS
                query = xpath_to_css(token.values[0])
                token.values = (query,)
            elif token.token_type == TokenType.OP_XPATH_ALL:
                token.token_type = TokenType.OP_CSS_ALL
                query = xpath_to_css(token.values[0])
                token.values = (query,)

    def css_to_xpath(self, prefix: str = "descendant-or-self::") -> None:
        for token in self.raw_tokens:
            if token.token_type == TokenType.OP_CSS:
                token.token_type = TokenType.OP_XPATH
                query = token.values[0]
                token.values = (css_to_xpath(query, prefix),)
            elif token.token_type == TokenType.OP_CSS_ALL:
                token.token_type = TokenType.OP_XPATH_ALL
                query = token.values[0]
                token.values = (css_to_xpath(query, prefix),)

    def parse(self) -> str:
        tree = self.analyzer(self.raw_tokens).build_ast()
        lines = []
        default_node = None
        for node in tree.values():
            if node.token.token_type == TokenType.OP_TRANSLATE_DEFAULT_CODE:
                default_node = node
                continue
            token_args = node.token.values
            translator_method = self.translator.tokens_map[node.token.token_type]
            line = translator_method(node, *token_args)
            lines.append(line)
        code = self.translator.DELIM_LINES.join(lines)
        if default_node:
            code = self.translator.op_wrap_code_with_default_value(default_node, code, *default_node.token.values)
        return code


if __name__ == '__main__':
    from src.configs.python.python_parsel import Translator
    # from src.configs.python.python_bs4 import Translator

    src_code = """
default "0"
raw
//cssAll "title"
//text
//index 0
assertMatch "Books to Scrape - Sandbox"
"""
    p = Parser(src_code, Translator)
    p.xpath_to_css()
    print(p.parse())
