import re
import warnings
from enum import Enum

__all__ = ["TokenType", "TOKENS", "TT_COMMENT", "TT_NEW_LINE", "Token", "tokenize"]


class TokenType(Enum):
    """all command enum representation"""
    # SELECTORS
    OP_XPATH = 0
    OP_XPATH_ALL = 1
    OP_CSS = 2
    OP_CSS_ALL = 3
    OP_ATTR = 4
    OP_ATTR_TEXT = 5
    OP_ATTR_RAW = 6
    # REGEX
    OP_REGEX = 7
    OP_REGEX_ALL = 8
    OP_REGEX_SUB = 9
    # STRINGS
    OP_STRING_TRIM = 10
    OP_STRING_L_TRIM = 11
    OP_STRING_R_TRIM = 12
    OP_STRING_REPLACE = 13
    OP_STRING_FORMAT = 14
    OP_STRING_SPLIT = 15
    # ARRAY
    OP_INDEX = 16
    OP_FIRST = 17
    OP_LAST = 18
    OP_SLICE = 19
    OP_JOIN = 20
    # ANY
    OP_COMMENT = 21
    OP_DEFAULT = 22
    OP_DEFAULT_CODE = 32  # without wrap try/catch mark
    OP_NEW_LINE = 23
    OP_CUSTOM_FORMATTER = 24
    # VALIDATORS
    OP_ASSERT = 25
    OP_ASSERT_CONTAINS = 26
    OP_ASSERT_STARTSWITH = 27
    OP_ASSERT_ENDSWITH = 28
    OP_ASSERT_MATCH = 29
    OP_ASSERT_CSS = 30
    OP_ASSERT_XPATH = 31


ASSERT_ENUMS = (TokenType.OP_ASSERT, TokenType.OP_ASSERT_STARTSWITH, TokenType.OP_ASSERT_ENDSWITH,
                TokenType.OP_ASSERT_CSS, TokenType.OP_ASSERT_XPATH, TokenType.OP_ASSERT_CONTAINS)

########
# LEXERS key: pattern, Enum
########
TOKENS = {
    # css/xpath
    "xpath": ('''^xpath (:?['"])(.*)(:?['"])$''', TokenType.OP_XPATH),
    "xpathAll": ("""^xpathAll (:?['"])(.*)(:?['"])$""", TokenType.OP_XPATH_ALL),
    "css": ("""^css (:?['"])(.*)(:?['"])$""", TokenType.OP_CSS),
    "cssAll": ("""^cssAll (:?['"])(.*)(:?['"])$""", TokenType.OP_CSS_ALL),
    "attr": ("""^attr (:?['"])(.*)(:?['"])$""", TokenType.OP_ATTR),
    "text": ("^text$", TokenType.OP_ATTR_TEXT),
    "raw": ("^raw$", TokenType.OP_ATTR_RAW),
    # REGEX
    "re": ('''^re (:?['"])(.*)(:?['"])$''', TokenType.OP_REGEX),
    "reAll": ("""^reAll (:?['"])(.*)(:?['"])$""", TokenType.OP_REGEX_ALL),
    "reSub": (r"""^reSub (:?['"])(.*)(:?['"]) (:?['"])(.*)(:?['"]) (\d*)$""", TokenType.OP_REGEX_SUB),
    # STRING
    "strip": ("""^strip (:?['"])(.*)(:?['"])""", TokenType.OP_STRING_TRIM),
    "lstrip": ("""^lstrip (:?['"])(.*)(:?['"])""", TokenType.OP_STRING_L_TRIM),
    "rstrip": ("""^rstrip (:?['"])(.*)(:?['"])""", TokenType.OP_STRING_R_TRIM),
    "replace": (r"""^replace (:?['"])(.*?)(:?['"]) (:?['"])(.*?)(:?['"]) (\d*)""", TokenType.OP_STRING_REPLACE),
    # format string
    "format": (r'''^format ((:?['"]).*{{\w*?}}.*(:?['"]))$''',  # |^format ((:?""").*{{\w*?}}.*(:?"""))$,
               TokenType.OP_STRING_FORMAT),
    "split": (r'''^split (:?['"])(.*)(:?['"]) -?(\d+)''', TokenType.OP_STRING_SPLIT),
    # any
    "default": ("^default (.*)?", TokenType.OP_DEFAULT),
    "formatter": ("^formatter (.*?)$", TokenType.OP_CUSTOM_FORMATTER),

    # array
    "slice": (r"^slice -?(\d+) -?(\d*)$", TokenType.OP_SLICE),
    "index": (r"^index -?(\d+)$", TokenType.OP_INDEX),
    "first": (r"^first$", TokenType.OP_FIRST),
    "last": (r"^last$", TokenType.OP_LAST),
    # convert array to string
    "join": (r"""^join ((:?['"])(.*)(:?['"]))$""", TokenType.OP_JOIN),

    # validate
    "assertEqual": (r"""^assertEqual ((:?['"])(.*)(:?['"]))$""", TokenType.OP_ASSERT),
    "assertContains": (r"""^assertContains ((:?['"])(.*)(:?['"]))$""", TokenType.OP_ASSERT),
    "assertStarts": (r"""^assertStarts ((:?['"])(.*)(:?['"]))$""", TokenType.OP_ASSERT_STARTSWITH),
    "assertEnds": (r"""^assertEnds ((:?['"])(.*)(:?['"]))$""", TokenType.OP_ASSERT_STARTSWITH),
    "assertMatch": (r"""^assertMatch ((:?['"])(.*)(:?['"]))$""", TokenType.OP_ASSERT_MATCH),
    "assertCss": (r"""^assertCss ((:?['"])(.*)(:?['"]))$""", TokenType.OP_ASSERT_CSS),
    "assertXpath": (r"""^assertXpath ((:?['"])(.*)(:?['"]))$""", TokenType.OP_ASSERT_XPATH),

}


TT_COMMENT = "//"
TT_NEW_LINE = "\n"


class Token:
    def __init__(self,
                 token_type: TokenType,
                 args: tuple[str, ...],
                 line: int,
                 pos: int,
                 code: str
                 ):
        """Token model

        :param token_type: token type, enum
        :param args: command arguments. tuple of strings
        :param line: line num
        :param pos: line position
        :param code: raw line command
        """
        self.token_type = token_type
        self.args = args
        self.line = line
        self.pos = pos
        self._code = code

    @property
    def code(self):
        return self._code

    @property
    def values(self) -> tuple[str, ...]:
        """remove quotes matched groups `'"` """
        if not self.args:
            return ()
        return tuple(i for i in self.args if i not in ("'", '"'))

    @values.setter
    def values(self, value: tuple[..., ]):
        self.args = value

    def __repr__(self):
        return f"{self.line}:{self.pos} - {self.token_type}, args={self.args}, values={self.values}"


def tokenize(source_str: str) -> list[Token]:
    """convert source script code to tokens"""
    tokens: list[Token] = []
    _have_default_op = False
    line: str
    for i, line in enumerate(source_str.split(TT_NEW_LINE), 1):
        line = line.strip()
        if not line:
            tokens.append(Token(TokenType.OP_NEW_LINE, (), i, 0, line))
            continue

        if line.startswith(TT_COMMENT):
            tokens.append(Token(TokenType.OP_COMMENT, (line, ), i, 0, line))
            continue

        for start_token, ctx in TOKENS.items():
            pattern, token_type = ctx
            if token_type == TokenType.OP_DEFAULT:
                _have_default_op = TokenType

            elif _have_default_op and token_type in ASSERT_ENUMS:
                warnings.warn("Detect default and validator operator. "
                              "`default` operator ignores `validator`", category=SyntaxWarning, stacklevel=2)

            command_directive = line.split(" ", 1)[0]
            if command_directive == start_token:
                if not (result := re.match(pattern, line)):
                    msg = f"{i}::0 {line} Arguments error. Maybe missing quotas `'\"` symbols or wrong args passed?"
                    raise SyntaxError(msg)
                value = result.groups()
                tokens.append(Token(token_type, value, i, result.endpos, line))
                break
        else:
            msg = f"{i}::0 `{line}` Unknown command"
            raise SyntaxError(msg)

    return tokens
