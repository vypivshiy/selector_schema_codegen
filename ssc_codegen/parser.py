import warnings
from typing import Type

from ssc_codegen.analyzer import Analyzer
from ssc_codegen.configs.codegen_tools import ABCExpressionTranslator
from ssc_codegen.lexer import TokenType, tokenize
from ssc_codegen.tools import css_to_xpath, xpath_to_css


class Parser:
    def __init__(
        self,
        source_code: str,
        translator: Type["ABCExpressionTranslator"] | "ABCExpressionTranslator",
        analyzer: Type[Analyzer] = Analyzer,
    ):
        self.raw_tokens = tokenize(source_code)
        self.analyzer = analyzer
        self.tree_ast = self.analyzer(self.raw_tokens).build_ast()
        if isinstance(translator, ABCExpressionTranslator):
            self.translator = translator
        else:
            self.translator = translator()

        # convert selectors
        if self.translator.AUTO_CONVERT_TO_CSS and self.translator.AUTO_CONVERT_TO_XPATH:
            raise TypeError("Should be one config mode set")

        elif self.translator.AUTO_CONVERT_TO_CSS and any(
                t.token_type in TokenType.tokens_selector_xpath() for t in self.raw_tokens):
            self.xpath_to_css()
        elif self.translator.AUTO_CONVERT_TO_XPATH and any(
                t.token_type in TokenType.tokens_selector_css() for t in self.raw_tokens):
            self.css_to_xpath(prefix=self.translator.XPATH_START_PREFIX)

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
        self.tree_ast = self.analyzer(self.raw_tokens).build_ast()
        lines = []
        default_node = None
        for node in self.tree_ast.values():
            if node.token.token_type == TokenType.OP_TRANSLATE_DEFAULT_CODE:
                default_node = node
                continue
            token_args = node.token.values
            translator_method = self.translator.tokens_map[
                node.token.token_type
            ]
            line = translator_method(node, *token_args)
            lines.append(line)
        code = self.translator.DELIM_LINES.join(lines)
        if default_node:
            code = self.translator.op_wrap_code_with_default_value(
                default_node, code, *default_node.token.values
            )
        return code


if __name__ == "__main__":
    # from src.configs.python.python_parsel import Translator
    from ssc_codegen.configs.python.python_bs4 import Translator

    src_code = """
assertCss "head > title"

css "head > title"
text
assertContains "spam"
format "https://books.toscrape.com/catalogue/{{}}"
rstrip "https://"
replace "o" "a"
re "b[oa][oa]ks\."
reSub "\w+" "lol"
"""
    p = Parser(src_code, Translator)
    # p.xpath_to_css()
    print(p.parse())
