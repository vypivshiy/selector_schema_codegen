from ssc_codegen.converters.base import BaseCodeConverter
from ssc_codegen.tokens import TokenType

# reserved tokens, not used in converters
EXCLUDE_TOKENS = {
    TokenType.VARIABLE,
    # in ast build step converts to TokenType.EXPR_DEFAULT_START and TokenType.EXPR_DEFAULT_END
    TokenType.EXPR_DEFAULT,
    TokenType.MODULE,  # first node
    # used inner TokenType.STRUCT_PARSE_START node
    # and converts to call parse methods for fields
    TokenType.STRUCT_CALL_FUNCTION,
    # used inner TokenType.TYPEDEF node
    # and converts to types
    TokenType.TYPEDEF_FIELD,
}

# situational tokens
# impl, if target language allowed typing
TYPING_TOKENS_CONVERT_IMPL = {
    TokenType.TYPEDEF,
}

# impl, if target language and backend supports css selections
CSS_TOKENS_IMPL = {
    TokenType.EXPR_CSS,
    TokenType.EXPR_CSS_ALL,
    TokenType.IS_CSS,
}
# impl, if target language and backend supports xpath selections
XPATH_TOKENS_IMPL = {
    TokenType.EXPR_XPATH,
    TokenType.EXPR_XPATH_ALL,
    TokenType.IS_XPATH,
}


REQUIRED_TOKENS_CONVERT_IMPL = {
    t
    for t in TokenType
    if t
    not in TYPING_TOKENS_CONVERT_IMPL
    | CSS_TOKENS_IMPL
    | XPATH_TOKENS_IMPL
    | EXCLUDE_TOKENS
}


def new_converter_check(
    name: str,
    converter: BaseCodeConverter,
    include: set[TokenType],
    exclude: set[TokenType] | None = None,
) -> tuple[str, BaseCodeConverter, set[TokenType], set[TokenType]]:
    exclude = exclude or set()
    return name, converter, include, exclude
