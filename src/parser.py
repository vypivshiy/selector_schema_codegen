from typing import Type, Optional, TYPE_CHECKING
from src.analyzer import Analyzer, VariableState
from src.lexer import TokenType, tokenize
import warnings

from src.tools import xpath_to_css, css_to_xpath

if TYPE_CHECKING:
    from src.lexer import Token
    from src.codegen_tools import ABCExpressionTranslator


class Parser:
    def __init__(self,
                 source_code: str,
                 translator: Type["ABCExpressionTranslator"],
                 analyzer: Type[Analyzer] = Analyzer,
                 *,
                 fluent_optimization: bool = False):
        self.raw_tokens = tokenize(source_code)
        self.analyzer = analyzer
        self._fluent_optimization = fluent_optimization
        self.translator = translator(
            fluent_optimisation=fluent_optimization)

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

    def _build_ast(self) -> dict[int, tuple["Token", VariableState]]:
        i: int
        ast_tokens: dict[int, tuple["Token", VariableState]] = {}
        for i, (token, var_state) in enumerate(self.analyzer(self.raw_tokens).lazy_analyze()):
            ast_tokens[i] = (token, var_state)
        return ast_tokens

    def _fluent_parse(self):
        ast_tree = self._build_ast()
        no_ret_token = False
        default_token = False
        selector_code = ""
        lines_of_code: list[str] = []
        asserts_code_indexes: list[int] = []
        last_index = 0

        for num, (token, var_state) in ast_tree.items():
            if token.token_type == TokenType.OP_TRANSLATE_DEFAULT_CODE:
                default_token = token
                continue
            # detect asserts and store indexes
            elif token.token_type in TokenType.tokens_asserts():
                asserts_code_indexes.append(num)
                continue

            translate_method = self.translator.tokens_map.get(token.token_type)
            line = translate_method(var_state, num, *token.values)

            if token.token_type in (TokenType.OP_FIRST, TokenType.OP_LAST, TokenType.OP_INDEX,
                                    TokenType.OP_CSS, TokenType.OP_CSS_ALL, TokenType.OP_XPATH_ALL,
                                    TokenType.OP_XPATH,
                                    TokenType.OP_ATTR, TokenType.OP_ATTR_RAW, TokenType.OP_ATTR_TEXT):
                selector_code += line
                last_index = num
            else:
                break

        if asserts_code_indexes:
            for num in asserts_code_indexes:
                token, var_state = ast_tree.get(num)
                translate_method = self.translator.tokens_map.get(token.token_type)
                line = translate_method(var_state, num, *token.values)
                lines_of_code.append(line)

        line = (f"{self.translator.FIRST_VAR_ASSIGMENT} {self.translator.FIRST_ASSIGMENT} "
                f"{self.translator.VAR_NAME}{selector_code}")
        lines_of_code.append(line)

        for num, (token, var_state) in ast_tree.items():
            if num <= last_index or token.token_type == TokenType.OP_TRANSLATE_DEFAULT_CODE:
                continue

            translate_method = self.translator.tokens_map.get(token.token_type)
            line = translate_method(var_state, num, *token.values)

            if token.token_type == TokenType.OP_NO_RET:
                no_ret_token = token

            else:
                if token.token_type == TokenType.OP_STRING_FORMAT:
                    line = f"{self.translator.VAR_NAME} {self.translator.ASSIGMENT} {line}"
                else:
                    line = f"{self.translator.VAR_NAME} {self.translator.ASSIGMENT} {self.translator.VAR_NAME}{line}"
                lines_of_code.append(line)

        if default_token:
            code = self.translator.DELIM_LINES.join(lines_of_code)
            code = self.translator.op_wrap_code_with_default_value(None, 0, code, *default_token.values)
            return code
        else:
            code = self.translator.DELIM_LINES.join(lines_of_code)
            code = self.translator.op_wrap_code(None, 0, code)
        if no_ret_token:
            return code + self.translator.DELIM_LINES + self.translator.op_no_ret(None, 0)
        return code + self.translator.DELIM_LINES + self.translator.op_ret(None, 0)

    def _default_parse(self):
        ast_tree = self._build_ast()
        lines_of_code: list[str] = []
        last_index = list(ast_tree.keys())[-1]
        first_index = list(ast_tree.keys())[0]

        first_assigment = False
        no_ret_token = None
        default_token = None

        for num, (token, var_state) in ast_tree.items():
            if token.token_type == TokenType.OP_TRANSLATE_DEFAULT_CODE:
                default_token = token
                continue

            translate_method = self.translator.tokens_map.get(token.token_type)
            line = translate_method(var_state, num, *token.values)

            if token.token_type in TokenType.tokens_asserts():
                lines_of_code.append(line)

            elif not first_assigment:
                first_assigment = True
                line = (f"{self.translator.FIRST_VAR_ASSIGMENT} {self.translator.FIRST_ASSIGMENT} "
                        f"{self.translator.VAR_NAME}{line}")
                lines_of_code.append(line)
            elif token.token_type == TokenType.OP_NO_RET and num == last_index:
                no_ret_token = token
            else:
                if token.token_type == TokenType.OP_STRING_FORMAT:
                    line = f"{self.translator.VAR_NAME} {self.translator.ASSIGMENT} {line}"
                else:
                    line = f"{self.translator.VAR_NAME} {self.translator.ASSIGMENT} {self.translator.VAR_NAME}{line}"
                lines_of_code.append(line)

        if default_token:
            code = self.translator.DELIM_LINES.join(lines_of_code)
            code = self.translator.op_wrap_code_with_default_value(None, 0, code, *default_token.values)
            return code
        else:
            code = self.translator.DELIM_LINES.join(lines_of_code)
            code = self.translator.op_wrap_code(None, 0, code)

        if no_ret_token:
            return code + self.translator.DELIM_LINES + code + self.translator.op_no_ret(None, 0)
        return code + self.translator.DELIM_LINES + self.translator.op_ret(None, 0)

    def parse(self):
        if self._fluent_optimization:
            return self._fluent_parse()
        else:
            return self._default_parse()


if __name__ == '__main__':
    from src.configs.python_parsel import Translator

    fluent_optimization = True
    src_code = """
default "0"
assertCss "head > title"
xpathAll "//div/a"
attr "href"
// format "spam{{}}"
"""
    p = Parser(src_code, Translator, fluent_optimization=fluent_optimization)
    p.xpath_to_css()
    print(p.parse())
