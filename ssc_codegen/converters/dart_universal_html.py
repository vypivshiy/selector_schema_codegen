import random
import re

from ssc_codegen.converters.base import CodeConverter, VAR_R, VAR_L

__all__ = ["converter"]

from ssc_codegen.converters.utils import sanitize_regex

from ssc_codegen.objects import TokenType, Node, VariableState

converter = CodeConverter(
    templates_path="ssc_codegen.templates.dart.universal_html",
    end=';',
    indent=" " * 2,
    intent_inner_try=" " * 4
)


@converter(TokenType.OP_XPATH)
def op_xpath(_: Node):
    raise NotImplementedError('Not supported xpath')


@converter(TokenType.OP_XPATH_ALL)
def op_xpath_all(_: Node):
    raise NotImplementedError('Not supported xpath')


@converter(TokenType.OP_CSS)
def op_css(node: Node) -> str:
    return ("var "
            + VAR_L(node)
            + " = "
            + VAR_R(node)
            + f".querySelector({node.expression.arguments[0]!r})"
            )


@converter(TokenType.OP_CSS_ALL)
def op_css_all(node: Node) -> str:
    return ("var "
            + VAR_L(node)
            + " = "
            + VAR_R(node)
            + f".querySelectorAll({node.expression.arguments[0]!r})"
            )


@converter(TokenType.OP_ATTR)
def op_attr(node: Node) -> str:
    attr_name = node.expression.arguments[0]
    if node.var_state == VariableState.LIST_DOCUMENT:
        return ("var "
                + VAR_L(node)
                + " = "
                + VAR_R(node)
                + f"?.map((el) => el.attributes[{attr_name!r}]).toList()"
                )

    return ("var "
            + VAR_L(node)
            + " = "
            + VAR_R(node)
            + f"?.attributes[{attr_name!r}]"
            )


@converter(TokenType.OP_ATTR_TEXT)
def op_text(node: Node):
    if node.var_state is VariableState.DOCUMENT:
        return ("var "
                + VAR_L(node)
                + " = "
                + VAR_R(node)
                + '?.text'
                )
    return ("var "
            + VAR_L(node)
            + " = "
            + VAR_R(node)
            + '.map((el) => el.text).toList()'
            )


@converter(TokenType.OP_ATTR_RAW)
def op_attr_raw(node: Node) -> str:
    if node.var_state is VariableState.DOCUMENT:
        return ("var "
                + VAR_L(node)
                + " = "
                + VAR_R(node)
                + '?.innerHtml'
                )
    return ("var "
            + VAR_L(node)
            + " = "
            + VAR_R(node)
            + '.map((el) => el.innerHtml).toList()'
            )


@converter(TokenType.OP_REGEX)
def op_regex(node: Node) -> str:
    pattern = node.expression.arguments[0]
    reg_var = f"regex_{VAR_L(node)}"
    return (f"RegExp {reg_var} = RegExp(r{pattern});\n"
            + "var "
            + VAR_L(node)
            + " = "
            + f"{reg_var}?.firstMatch({VAR_R(node)})?.group(0)"
            )


@converter(TokenType.OP_REGEX_ALL)
def op_regex_all(node: Node) -> str:
    pattern = node.expression.arguments[0]
    reg_var = f"regex_{VAR_L(node)}"
    return (f"RegExp {reg_var} = RegExp(r{pattern!r});\n"
            + "var "
            + VAR_L(node)
            + " = "
            + f"{reg_var}?.allMatches({VAR_R(node)}).map((m) => m.group(0)!).toList()"
            )


@converter(TokenType.OP_REGEX_SUB)
def op_regex_sub(node: Node) -> str:
    pattern = node.expression.arguments[0]
    repl = node.expression.arguments[1]

    return ("var "
            + VAR_L(node)
            + " = "
            + VAR_R(node)
            + f"?.replaceAll(RegExp(r{pattern!r}), {repl!r})"
            )


# TRIM signatures based by:
# https://stackoverflow.com/a/14107914


@converter(TokenType.OP_STRING_TRIM)
def op_string_trim(node: Node) -> str:
    substr = node.expression.arguments[0]

    substr_left = repr('^' + sanitize_regex(substr)).replace('\\\\', '\\')
    substr_right = repr(sanitize_regex(substr) + '$').replace('\\\\', '\\')
    if node.var_state == VariableState.STRING:
        return ("var "
                + VAR_L(node)
                + " = "
                + VAR_R(node)
                + f'?.replaceFirst(RegExp(r{substr_left}), "")'
                + f'.replaceFirst(RegExp(r{substr_right}), "")'
                )
    return ("var "
            + VAR_L(node)
            + " = "
            + VAR_R(node)
            + '.map('
            + f'(s) => s?.replaceFirst(RegExp(r{substr_left}), "")'
            + f'.replaceFirst(RegExp(r{substr_right}), "")'
            + ').toList()'
            )


@converter(TokenType.OP_STRING_L_TRIM)
def op_string_l_trim(node: Node) -> str:
    substr = node.expression.arguments[0]

    substr_left = repr('^' + sanitize_regex(substr)).replace('\\\\', '\\')
    if node.var_state == VariableState.STRING:
        return ("var "
                + VAR_L(node)
                + " = "
                + VAR_R(node)
                + f'?.replaceFirst(RegExp(r{substr_left}), "")'
                )
    return ("var "
            + VAR_L(node)
            + " = "
            + VAR_R(node)
            + f'.map('
            + f'(s) => s?.replaceFirst(RegExp(r{substr_left}), "")'
            + ').toList()'
            )


@converter(TokenType.OP_STRING_R_TRIM)
def op_string_r_trim(node: Node) -> str:
    substr = node.expression.arguments[0]

    substr_right = repr(sanitize_regex(substr) + '$').replace('\\\\', '\\')
    if node.var_state == VariableState.STRING:
        return ("var "
                + VAR_L(node)
                + " = "
                + VAR_R(node)
                + f'?.replaceFirst(RegExp(r{substr_right}), "")'
                )
    return ("var "
            + VAR_L(node)
            + " = "
            + VAR_R(node)
            + f'.map((s) => s?.replaceFirst(RegExp(r{substr_right}), "")'
            + '.toList()'
            )


@converter(TokenType.OP_STRING_REPLACE)
def op_string_replace(node: Node) -> str:
    old = node.expression.arguments[0]
    new = node.expression.arguments[1]
    if node.var_state == VariableState.STRING:
        return ("var "
                + VAR_L(node)
                + " = "
                + f"{VAR_R(node)}?.replaceAll(RegExp({old!r}), {new!r})"
                )
    return ("var "
            + VAR_L(node)
            + " = "
            + VAR_R(node)
            + f'.map((s) => s?.replaceAll(RegExp({old!r}), {new!r})'
            + '.toList()'
            )


@converter(TokenType.OP_STRING_FORMAT)
def op_string_format(node: Node) -> str:
    fmt_str = node.expression.arguments[0]

    if node.var_state == VariableState.STRING:
        fmt_str = re.sub(r'\{\{}}', f"${VAR_R(node)}", fmt_str)
        return ("var "
                + VAR_L(node)
                + " = "
                + repr(fmt_str)
                )

    fmt_str = re.sub(r'\{\{}}', f"$_repl", fmt_str)
    return ("var "
            + VAR_L(node)
            + " = "
            + VAR_R(node)
            + f'.map((_repl) => {fmt_str!r})'
            )


@converter(TokenType.OP_STRING_SPLIT)
def op_string_split(node: Node) -> str:
    sep = node.expression.arguments[0]
    return ("var "
            + VAR_L(node)
            + " = "
            + VAR_R(node)
            + f".split({sep!r})"
            )


@converter(TokenType.OP_INDEX)
def op_string_index(node: Node) -> str:
    i = node.expression.arguments[0]
    return ("var "
            + VAR_L(node)
            + " = "
            + VAR_R(node)
            + f"[{i}]"
            )


@converter(TokenType.OP_JOIN)
def op_join(node: Node) -> str:
    prefix = node.expression.arguments[0]
    return ("var "
            + VAR_L(node)
            + " = "
            + VAR_R(node)
            + f".join({prefix!r})"
            )


# TODO add assert errors msg

@converter(TokenType.OP_ASSERT_EQUAL)
def op_assert_equal(node: Node) -> str:
    value = node.expression.arguments[0]
    value = "null" if value == None else repr(value)

    return (
            "assert("
            + VAR_R(node)
            + " == "
            + value
            + ")"
    )


@converter(TokenType.OP_ASSERT_CONTAINS)
def op_assert_contains(node: Node) -> str:
    value = node.expression.arguments[0]
    return (
            "assert("
            + VAR_R(node)
            + "!= null"
            + " && "
            + VAR_R(node)
            + ".contains("
            + f"{value!r})"
            + ")"
    )


@converter(TokenType.OP_ASSERT_RE_MATCH)
def op_assert_re_match(node: Node) -> str:
    pattern = node.expression.arguments[0]
    re_var = f"re_{node.num}"
    return (
            f"RegExp {re_var} = RegExp(r{pattern!r});\n"
            + "assert("
            + VAR_R(node)
            + " != null"
            + " && "
            + re_var
            + ".firstMatch("
            + VAR_R(node)
            + ")"
            + " != null)"
    )


@converter(TokenType.OP_ASSERT_CSS)
def op_assert_css(node: Node) -> str:
    query = node.expression.arguments[0]
    return (
            "assert("
            + VAR_R(node)
            + " != null "
            + " && "
            + VAR_R(node)
            + f".querySelector({query!r})"
            + " != null)"
    )


@converter(TokenType.OP_ASSERT_XPATH)
def op_assert_xpath(_: Node) -> str:
    raise NotImplementedError("dart universal html not support xpath")


@converter(TokenType.OP_INIT)
def op_init(_: Node) -> str:
    return "var var_0 = doc"


@converter(TokenType.OP_RET)
def op_ret(node: Node):
    return f'return {VAR_R(node)}'


@converter(TokenType.OP_NO_RET)
def op_no_ret(_: Node):
    return 'return'


@converter(TokenType.OP_DEFAULT_START)
def op_default_start(_: Node) -> str:
    return "try {"


@converter(TokenType.OP_DEFAULT_END)
def op_default_end(node: Node) -> str:
    value = node.expression.arguments[0]
    value = "null" if value == None else repr(value)

    return (
            "} catch (e) {"
            + f" return {value};"
            + "}"
    )
