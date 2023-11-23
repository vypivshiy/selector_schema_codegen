import re
import warnings

from cssselect import HTMLTranslator
from lxml import etree

from ssc_codegen.exceptions import CommandArgumentsError, UnknownCommandError
from ssc_codegen.objects import TT_COMMENT, TT_NEW_LINE, Token, TokenType

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
        r'^reSub\s+(".*")\s+(".*")\s*?(-?\d*)?$',
        TokenType.OP_REGEX_SUB,
    ),
    # STRING
    "strip": (r'^strip\s+(".*")$', TokenType.OP_STRING_TRIM),
    "lstrip": (r'^lstrip\s+(".*")$', TokenType.OP_STRING_L_TRIM),
    "lStrip": (r'^lStrip\s+(".*")$', TokenType.OP_STRING_L_TRIM),
    "rStrip": (r'^rStrip\s+(".*")$', TokenType.OP_STRING_R_TRIM),
    "rstrip": (r'^rstrip\s+(".*")$', TokenType.OP_STRING_R_TRIM),
    "replace": (
        r'^replace\s+(".*")\s+(".*")\s*?(\d*)$',
        TokenType.OP_STRING_REPLACE,
    ),
    # format string
    "format": (
        r'^format\s+(".*{{\w*?}}.*")$',
        TokenType.OP_STRING_FORMAT,
    ),
    "split": (
        r'^split\s+(".*")\s*?(-?\d+)?$',
        TokenType.OP_STRING_SPLIT,
    ),
    # any
    "default": (r"^default\s+(.+)?$", TokenType.OP_TRANSLATE_DEFAULT_CODE),
    # "formatter": ("^formatter (.*?)$", TokenType.OP_CUSTOM_FORMATTER),
    # array
    "limit": (r"^limit\s+(\d+)$", TokenType.OP_LIMIT),
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
    # declare return statement for translator
    "noRet": (r"^noRet$", TokenType.OP_NO_RET),
    "ret": (r"^ret$", TokenType.OP_RET),
}


def _check_css_query(query: str):
    try:
        HTMLTranslator().css_to_xpath(query.strip('"'))
    except Exception:
        msg = f"{query} is not valid CSS selector"
        raise CommandArgumentsError(msg)


def _check_xpath_query(query: str):
    try:
        etree.XPath(query.strip('"'))
    except Exception:
        msg = f"{query} is not valid XPATH selector"
        raise CommandArgumentsError(msg)


def tokenize(source_str: str) -> list[Token]:
    """convert source script code to tokens"""
    tokens: list[Token] = []
    _have_default_op = False
    _have_no_ret = False
    line: str

    for i, line in enumerate(source_str.split(TT_NEW_LINE), 1):
        line = line.rstrip()
        if not line:
            tokens.append(Token(TokenType.OP_NEW_LINE, (), i, 0, line))
            continue

        if line.startswith(TT_COMMENT):
            tokens.append(Token(TokenType.OP_COMMENT, (), i, 0, line))
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
                    msg = f'{i}::0 `{line}` Maybe missing quote `"` symbol or wrong arguments passed?'
                    raise CommandArgumentsError(msg)

                # detect asserts + default stmts
                if token_type is TokenType.OP_TRANSLATE_DEFAULT_CODE:
                    _have_default_op = True

                if token_type is TokenType.OP_NO_RET:
                    _have_no_ret = True

                value = result.groups()
                # validate CSS, XPATH
                if token_type in TokenType.tokens_selector_css():
                    _check_css_query(*value)
                elif token_type in TokenType.tokens_selector_xpath():
                    _check_xpath_query(*value)

                tokens.append(Token(token_type, value, i, result.endpos, line))
                break
        else:
            msg = f"{i}::0 `{line}` Unknown command"
            raise UnknownCommandError(msg)

    if _have_no_ret and _have_default_op:
        raise SyntaxError("`default` token not allowed with `noRet` token")

    # auto add return operator
    if all(t.token_type != TokenType.OP_NO_RET for t in tokens):
        tokens.append(Token(TokenType.OP_RET, (), len(tokens) + 1, 0, "ret"))

    # crop tokens list to OP_RET/OP_NO_RET command
    complete_tokens: list[Token] = []
    for t in tokens:
        if t.token_type in (TokenType.OP_RET, TokenType.OP_NO_RET):
            complete_tokens.append(t)
            break
        complete_tokens.append(t)
    return complete_tokens


if __name__ == "__main__":
    src = """
cssAll   "div > a"
attr     "href"

"""
    toks = tokenize(src)
    print()
