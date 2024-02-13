from ssc_codegen.converters.base import CodeConverter, VAR_R, VAR_L

__all__ = ["converter"]

from ssc_codegen.objects import TokenType, Node, VariableState

converter = CodeConverter(
    templates_path="ssc_codegen.templates.python.selectolax"
)


@converter(TokenType.OP_XPATH)
def op_xpath(_: Node):
    raise NotImplementedError("selectolax not support xpath")


@converter(TokenType.OP_XPATH_ALL)
def op_xpath_all(_: Node):
    raise NotImplementedError("selectolax not support xpath")


@converter(TokenType.OP_CSS)
def op_css(node: Node) -> str:
    return (
            VAR_L(node)
            + " = "
            + VAR_R(node)
            + f".css_first({node.expression.arguments[0]!r})"
    )


@converter(TokenType.OP_CSS_ALL)
def op_css_all(node: Node) -> str:
    return (
            VAR_L(node)
            + " = "
            + VAR_R(node)
            + f".css({node.expression.arguments[0]!r})"
    )


@converter(TokenType.OP_ATTR)
def op_attr(node: Node) -> str:
    attr = node.expression.arguments[0]
    if node.var_state == VariableState.DOCUMENT:
        return (
                VAR_L(node)
                + " = "
                + VAR_R(node)
                + f".attributes[{attr!r}]"
        )
    return (
            VAR_L(node)
            + " = "
            + f'[el.attributes[{attr!r}] for el in {VAR_R(node)}]'
    )


@converter(TokenType.OP_ATTR_TEXT)
def op_text(node: Node):
    if node.var_state is VariableState.DOCUMENT:
        return (VAR_L(node)
                + " = "
                + VAR_R(node)
                + '.text()'
                )
    return (
            VAR_L(node)
            + " = "
            + f'[el.text() for el in {VAR_R(node)}]'
    )


@converter(TokenType.OP_ATTR_RAW)
def op_attr_raw(node: Node) -> str:
    if node.var_state is VariableState.DOCUMENT:
        return (
                VAR_L(node)
                + " = "
                + VAR_R(node)
                + '.html'
        )
    return (
            VAR_L(node)
            + " = "
            + VAR_R(node)
            + f'[el.html for el in {VAR_R(node)}]'
    )


@converter(TokenType.OP_REGEX)
def op_regex(node: Node) -> str:
    pattern = node.expression.arguments[0]
    return (
            VAR_L(node)
            + " = "
            + f"re.search(r{pattern!r}, {VAR_R(node)})"
            + "[1]"
    )


@converter(TokenType.OP_REGEX_ALL)
def op_regex_all(node: Node) -> str:
    pattern = node.expression.arguments[0]
    return (
            VAR_L(node)
            + " = "
            + f"re.findall(r{pattern!r}, {VAR_R(node)})"
    )


@converter(TokenType.OP_REGEX_SUB)
def op_regex_sub(node: Node) -> str:
    pattern = node.expression.arguments[0]
    repl = node.expression.arguments[1]
    return (
            f"{VAR_L(node)} = "
            + f"re.sub(r{pattern!r}, {repl!r}, {VAR_R(node)})"
    )


@converter(TokenType.OP_STRING_TRIM)
def op_string_trim(node: Node) -> str:
    substr = node.expression.arguments[0]
    if node.var_state == VariableState.STRING:
        return (
                VAR_L(node)
                + " = "
                + f"{VAR_R(node)}.strip({substr!r})"
        )
    return (
        VAR_L(node)
        + " = "
        + f"[s.strip({substr!r}) for s in {VAR_R(node)}]"
    )


@converter(TokenType.OP_STRING_L_TRIM)
def op_string_l_trim(node: Node) -> str:
    substr = node.expression.arguments[0]
    if node.var_state == VariableState.STRING:
        return (
                VAR_L(node)
                + " = "
                + f"{VAR_R(node)}.lstrip({substr!r})"
        )
    return (
            VAR_L(node)
            + " = "
            + f"[s.lstrip({substr!r}) for s in {VAR_R(node)}]"
    )


@converter(TokenType.OP_STRING_R_TRIM)
def op_string_r_trim(node: Node) -> str:
    substr = node.expression.arguments[0]
    if node.var_state == VariableState.STRING:
        return (
                VAR_L(node)
                + " = "
                + f"{VAR_R(node)}.rstrip({substr!r})"
        )
    return (
            VAR_L(node)
            + " = "
            + f"[s.lstrip({substr!r}) for s in {VAR_R(node)}]"
    )


@converter(TokenType.OP_STRING_REPLACE)
def op_string_replace(node: Node) -> str:
    old = node.expression.arguments[0]
    new = node.expression.arguments[1]
    if node.var_state == VariableState.STRING:
        return (
                VAR_L(node)
                + " = "
                + f"{VAR_R(node)}.replace({old!r}, {new!r})"
        )
    return (
            VAR_L(node)
            + " = "
            + f"[s.replace({old!r}, {new!r}) for s in {VAR_R(node)}]"
    )


@converter(TokenType.OP_STRING_FORMAT)
def op_string_format(node: Node) -> str:
    fmt_str = node.expression.arguments[0].replace("{{", "{").replace("}}", "}")
    if node.var_state == VariableState.STRING:
        return (
                VAR_L(node)
                + " = "
                + repr(fmt_str)
                + f".format({VAR_R(node)})"
        )
    return (
            VAR_L(node)
            + " = "
            + f"[{fmt_str!r}.format(s) for s in {VAR_R(node)}]"
    )


@converter(TokenType.OP_STRING_SPLIT)
def op_string_split(node: Node) -> str:
    sep = node.expression.arguments[0]
    return (
            VAR_L(node)
            + " = "
            + VAR_R(node)
            + f".split({sep!r})"
    )


@converter(TokenType.OP_INDEX)
def op_string_index(node: Node) -> str:
    i = node.expression.arguments[0]
    return (
            VAR_L(node)
            + " = "
            + VAR_R(node)
            + f"[{i}]"
    )


@converter(TokenType.OP_JOIN)
def op_join(node: Node) -> str:
    prefix = node.expression.arguments[0]
    return (
            VAR_L(node)
            + " = "
            + prefix
            + f".join({VAR_R(node)})"
    )


# TODO add assert errors msg

@converter(TokenType.OP_ASSERT_EQUAL)
def op_assert_equal(node: Node) -> str:
    value = node.expression.arguments[0]
    return (
            "assert"
            + " "
            + VAR_R(node)
            + " == "
            + repr(value)
    )


@converter(TokenType.OP_ASSERT_CONTAINS)
def op_assert_contains(node: Node) -> str:
    value = node.expression.arguments[0]
    return (
            "assert"
            + " "
            + repr(value)
            + " in "
            + VAR_R(node)
    )


@converter(TokenType.OP_ASSERT_RE_MATCH)
def op_assert_re_match(node: Node) -> str:
    pattern = node.expression.arguments[0]
    return (
            "assert"
            + " "
            + f"re.search(r{pattern!r}, {VAR_R(node)})"
    )


@converter(TokenType.OP_ASSERT_CSS)
def op_assert_css(node: Node) -> str:
    query = node.expression.arguments[0]
    return (
            "assert"
            + " "
            + VAR_R(node)
            + f".css_first({query!r}).html"
    )


@converter(TokenType.OP_ASSERT_XPATH)
def op_assert_xpath(node: Node) -> str:
    raise NotImplementedError("selectolax not support xpath")


@converter(TokenType.OP_INIT)
def op_init(_: Node) -> str:
    return "var_0 = doc"


@converter(TokenType.OP_RET)
def op_ret(node: Node):
    return f'return {VAR_R(node)}'


@converter(TokenType.OP_NO_RET)
def op_no_ret(_: Node):
    return 'return'


@converter(TokenType.OP_DEFAULT_START)
def op_default_start(_: Node) -> str:
    return "try:"


@converter(TokenType.OP_DEFAULT_END)
def op_default_end(node: Node) -> str:
    value = node.expression.arguments[0]
    # empty STR set as pytonic None
    if value != None:
        value = repr(value)
    return (
            "except Exception as e:"
            + f" return {value}"
    )
