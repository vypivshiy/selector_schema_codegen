# TOKENIZE LEXER
class BaseLexerExceptions(SyntaxError):
    pass


class CommandArgumentsError(BaseLexerExceptions):
    pass


class UnknownCommandError(BaseLexerExceptions):
    pass


# SYNTAX ANALYZE
class BaseSyntaxAnalyzeExceptions(SyntaxError):
    pass


class SyntaxVariableTypeError(BaseSyntaxAnalyzeExceptions):
    pass


class SyntaxAttributeError(BaseSyntaxAnalyzeExceptions):
    pass


class SyntaxCommandError(BaseSyntaxAnalyzeExceptions):
    pass
