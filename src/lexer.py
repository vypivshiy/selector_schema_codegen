import re
import warnings
from enum import Enum

__all__ = [
    "TokenType",
    "TOKENS",
    "TT_COMMENT",
    "TT_NEW_LINE",
    "Token",
    "tokenize",
]


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
    OP_TRANSLATE_DEFAULT_CODE = 22  # wrap try/catch mark
    OP_TRANSLATE_CODE = 32
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
    # declare skip return statement for translator
    OP_NO_RET = 33

    @classmethod
    def tokens_selector_all(cls):
        return (
            TokenType.OP_CSS,
            TokenType.OP_XPATH,
            TokenType.OP_CSS_ALL,
            TokenType.OP_XPATH_ALL,
        )

    @classmethod
    def tokens_selector_fetch_one(cls):
        return TokenType.OP_CSS, TokenType.OP_XPATH

    @classmethod
    def tokens_selector_fetch_all(cls):
        return TokenType.OP_CSS_ALL, TokenType.OP_XPATH_ALL

    @classmethod
    def tokens_selector_extract(cls):
        return TokenType.OP_ATTR, TokenType.OP_ATTR_TEXT, TokenType.OP_ATTR_RAW

    @classmethod
    def tokens_regex(cls):
        return (
            TokenType.OP_REGEX,
            TokenType.OP_REGEX_ALL,
            TokenType.OP_REGEX_SUB,
        )

    @classmethod
    def tokens_string(cls):
        return (
            TokenType.OP_STRING_FORMAT,
            TokenType.OP_STRING_REPLACE,
            TokenType.OP_STRING_SPLIT,
            TokenType.OP_STRING_L_TRIM,
            TokenType.OP_STRING_R_TRIM,
            TokenType.OP_STRING_TRIM,
        )

    @classmethod
    def tokens_array(cls):
        return (
            TokenType.OP_INDEX,
            TokenType.OP_FIRST,
            TokenType.OP_LAST,
            TokenType.OP_SLICE,
            TokenType.OP_JOIN,
        )

    @classmethod
    def tokens_asserts(cls):
        return (
            TokenType.OP_ASSERT,
            TokenType.OP_ASSERT_STARTSWITH,
            TokenType.OP_ASSERT_ENDSWITH,
            TokenType.OP_ASSERT_CSS,
            TokenType.OP_ASSERT_XPATH,
            TokenType.OP_ASSERT_CONTAINS,
            TokenType.OP_ASSERT_MATCH
        )

    @classmethod
    def token_fluent_optimization(cls):
        return (TokenType.OP_CSS,
                TokenType.OP_XPATH,
                TokenType.OP_XPATH_ALL,
                TokenType.OP_CSS_ALL,
                TokenType.OP_INDEX,
                TokenType.OP_ATTR,
                TokenType.OP_ATTR_RAW,
                TokenType.OP_ATTR_TEXT)


########
# LEXERS key: pattern, Enum
########
TOKENS = {
    # css/xpath
    "xpath": (r'^xpath\s+(".*")$', TokenType.OP_XPATH),
    "xpathAll": (r'^xpathAll\s+(".*")$', TokenType.OP_XPATH_ALL),
    "css": (r'^css\s+(".*")$', TokenType.OP_CSS),
    "cssAll": (r'^cssAll\s+(".*")$', TokenType.OP_CSS_ALL),
    "attr": (r'^attr\s+(".*")$', TokenType.OP_ATTR),
    "text": ("^text$", TokenType.OP_ATTR_TEXT),
    "raw": ("^raw$", TokenType.OP_ATTR_RAW),
    # REGEX
    "re": (r'^re\s+(".*")$', TokenType.OP_REGEX),
    "reAll": (r'^reAll\s+(".*")$', TokenType.OP_REGEX_ALL),
    "reSub": (
        r'^reSub\s+(".*")\s+(".*")\s+?-?(\d*)$',
        TokenType.OP_REGEX_SUB,
    ),
    # STRING
    "strip": (r'^strip\s+(".*")$', TokenType.OP_STRING_TRIM),
    "lstrip": (r'^lstrip\s+(".*")$', TokenType.OP_STRING_L_TRIM),
    "rstrip": (r'^rstrip\s+(".*")$', TokenType.OP_STRING_R_TRIM),
    "replace": (
        r'^replace\s+(".*")\s+(".*")\s+?-?(\d*)$',
        TokenType.OP_STRING_REPLACE,
    ),
    # format string
    "format": (
        r'^format\s+(".*{{\w*?}}.*")$',
        TokenType.OP_STRING_FORMAT,
    ),
    "split": (
        r'^split\s+(".*")\s?-?(\d+)$',
        TokenType.OP_STRING_SPLIT,
    ),
    # any
    "default": (r"^default\s+(.+)?$", TokenType.OP_TRANSLATE_DEFAULT_CODE),
    # "formatter": ("^formatter (.*?)$", TokenType.OP_CUSTOM_FORMATTER),
    # array
    "slice": (r"^slice\s+-?(\d+) -?(\d*)$", TokenType.OP_SLICE),
    "index": (r"^index\s+-?(\d+)$", TokenType.OP_INDEX),
    "first": (r"^first$", TokenType.OP_FIRST),
    "last": (r"^last$", TokenType.OP_LAST),
    # convert array to string
    "join": (r'^join\s+(".*")$', TokenType.OP_JOIN),
    # validate
    "assertEqual": (
        r'^assertEqual\s+(".*")$',
        TokenType.OP_ASSERT,
    ),
    "assertContains": (
        r'^assertContains\s+(".*")$',
        TokenType.OP_ASSERT_CONTAINS,
    ),
    "assertStarts": (
        r'^assertStarts\s+(".*")$',
        TokenType.OP_ASSERT_STARTSWITH,
    ),
    "assertEnds": (
        r'^assertEnds\s+(".*")$',
        TokenType.OP_ASSERT_ENDSWITH,
    ),
    "assertMatch": (
        r'^assertMatch\s+(".*")$',
        TokenType.OP_ASSERT_MATCH,
    ),
    "assertCss": (
        r'^assertCss\s+(".*")$',
        TokenType.OP_ASSERT_CSS,
    ),
    "assertXpath": (
        r'^assertXpath\s+(".*")$',
        TokenType.OP_ASSERT_XPATH,
    ),
    # declare no return for translator
    "noRet": (r"^noRet$", TokenType.OP_NO_RET)
}


TT_COMMENT = "//"
TT_NEW_LINE = "\n"


class Token:
    def __init__(
        self,
        token_type: TokenType,
        args: tuple[str, ...],
        line: int,
        pos: int,
        code: str,
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
        """remove quotes matched groups `'"`"""
        if not self.args:
            return ()
        return self.args

    @values.setter
    def values(self, value: tuple[...,]):
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
            tokens.append(Token(TokenType.OP_COMMENT, (line,), i, 0, line))
            continue

        for start_token, ctx in TOKENS.items():
            pattern, token_type = ctx

            if _have_default_op and token_type in TokenType.tokens_asserts():
                warnings.warn(
                    "Detect default and validator operator. "
                    "`default` operator ignores `validator` checks",
                    category=SyntaxWarning,
                    stacklevel=2,
                )

            command_directive = line.split(" ", 1)[0]
            if command_directive == start_token:
                if not (result := re.match(pattern, line)):
                    msg = f"{i}::0 {line} Argument(s) error. Maybe missing quote `\"` symbol or wrong args passed?"
                    raise SyntaxError(msg)

                if token_type is TokenType.OP_TRANSLATE_DEFAULT_CODE:
                    _have_default_op = True

                value = result.groups()
                tokens.append(Token(token_type, value, i, result.endpos, line))
                break
        else:
            msg = f"{i}::0 `{line}` Unknown command"
            raise SyntaxError(msg)

    return tokens
