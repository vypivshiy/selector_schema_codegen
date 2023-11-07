import re
from enum import Enum
from typing import Optional


class TokenType(Enum):
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

    # ARRAY
    OP_INDEX = 15
    OP_FIRST = 16
    OP_LAST = 17
    OP_SLICE = 18
    OP_JOIN = 19

    # ANY
    OP_COMMENT = 20
    OP_DEFAULT = 21
    OP_NEW_LINE = 22
    OP_CUSTOM_FORMATTER = 23


########
# LEXERS
########
LEXERS_MAP = {
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
    "reSub": ("""^reSub (:?['"])(.*)(:?['"])$""", TokenType.OP_REGEX_SUB),
    # STRING
    "strip": ("""^strip (:?['"])(.*)(:?['"])""", TokenType.OP_STRING_TRIM),
    "lstrip": ("""^lstrip (:?['"])(.*)(:?['"])""", TokenType.OP_STRING_L_TRIM),
    "rstrip": ("""^rstrip (:?['"])(.*)(:?['"])""", TokenType.OP_STRING_R_TRIM),
    "replace": (r"""^replace (:?['"])(.*?)(:?['"]) (:?['"])(.*?)(:?['"]) (\d*)""", TokenType.OP_STRING_REPLACE),
    # format string
    "format": (r'''^format ((:?['"]).*{{\w*?}}.*(:?['"]))$''',  # |^format ((:?""").*{{\w*?}}.*(:?"""))$,
               TokenType.OP_STRING_FORMAT),
    # any
    "default": ("^default (.*)?", TokenType.OP_DEFAULT),
    "formatter": ("^formatter (.*?)$", TokenType.OP_CUSTOM_FORMATTER),

    # array
    "slice": (r"^slice -?(\d+) -?(\d*)$", TokenType.OP_SLICE),
    "index": (r"^index -?(\d+)$", TokenType.OP_INDEX),
    "first": (r"^first$", TokenType.OP_FIRST),
    "last": (r"^last$", TokenType.OP_LAST),
    # convert array to string
    "join": (r"""^join ((:?['"])(.*)(:?['"]))$""", TokenType.OP_JOIN)
}


TT_COMMENT = "//"
TT_NEW_LINE = "\n"


class Token:
    def __init__(self,
                 token_type: TokenType,
                 args: tuple[str, ...],
                 line: int,
                 pos: int
                 ):
        self.token_type = token_type
        self.args = args
        self.line = line
        self.pos = pos

    @property
    def values(self) -> Optional[tuple[str]]:
        if not self.args:
            return None
        return tuple(i for i in self.args if i not in ("'", '"'))

    def __repr__(self):
        return f"{self.line}:{self.pos} - {self.token_type}, args={self.args}, values={self.values}"


def tokenize(source_str: str):
    tokens: list[Token] = []
    line: str
    for i, line in enumerate(source_str.split(TT_NEW_LINE), 1):
        if not line:
            tokens.append(Token(TokenType.OP_NEW_LINE, (), i, 0))
            continue
        line = line.strip()

        if line.startswith(TT_COMMENT):
            tokens.append(Token(TokenType.OP_COMMENT, (line, ), i, 0))
            continue

        for start_token, ctx in LEXERS_MAP.items():
            pattern, token_type = ctx
            if line.startswith(start_token):
                if not (result := re.match(pattern, line)):
                    msg = f"Error! line: {i}, command: {line}"
                    raise RuntimeError(msg)
                value = result.groups()
                tokens.append(Token(token_type, value, i, result.endpos))

    print(*tokens, sep="\n")


if __name__ == '__main__':
    example = """
// whitespaces allowed


// end
// xpath command
xpath '//div[@class="image_container"]/a'

// extract attribute `href`
attr "href"
rstrip "//"
// format string 'https://books.toscrape.com/catalogue/' + last value
format "https://books.toscrape.com/catalogue/{{}}"
// any mark or skip value    
format "https://books.toscrape.com/catalogue/{{my_value}}"    
"""
    tokenize(example)
