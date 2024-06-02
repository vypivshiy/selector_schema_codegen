from ssc_codegen2.converters.base import BaseCodeConverter
from ssc_codegen2.converters.generator import CodeGenerator
from ssc_codegen2.expression import Expression
from ssc_codegen2.tokens import TokenType
from ssc_codegen2.type_state import TypeVariableState
from functools import partial

CONST_METHODS = {
    "__SPLIT_DOC__": """
@override
m_partDocument(el)""",

    "__PRE_VALIDATE__": """
@override
m_preValidate(el)""",
    "__ITEM__": "_parseItem(el)",
    "__KEY__": "_parseKey(el)",
    "__VALUE__": "_parseValue(el)",
}


class DartCodeConverter(BaseCodeConverter):
    pass


converter = DartCodeConverter(chr_indent=' ' * 2)
VAR_NAMES = partial(DartCodeConverter.create_var_names, prefix="val", sep='')


@converter(TokenType.OP_XPATH)
def op_xpath(_):
    raise NotImplementedError("Not supported")


@converter(TokenType.OP_XPATH_ALL)
def op_xpath_all(_):
    raise NotImplementedError("Not supported")


@converter(TokenType.OP_CSS)
def op_css(expr: Expression):
    VAR_L, VAR_R = VAR_NAMES(expr)
    query = expr.arguments[0]
    return f"var {VAR_L} = m_css({VAR_R}, {query!r});"


@converter(TokenType.OP_CSS_ALL)
def op_css_all(expr: Expression):
    VAR_L, VAR_R = VAR_NAMES(expr)
    query = expr.arguments[0]
    return f"var {VAR_L} = m_cssAll({VAR_R}, {query!r});"


@converter(TokenType.OP_ATTR)
def op_attr(expr: Expression):
    VAR_L, VAR_R = VAR_NAMES(expr)
    name = expr.arguments[0]
    if expr.VARIABLE_TYPE == TypeVariableState.STRING:
        return f"var {VAR_L} = m_attr({VAR_R}, {name!r});"
    return f"var {VAR_L} = m_attrAll({VAR_R}, {name!r});"


@converter(TokenType.OP_ATTR_TEXT)
def op_attr_text(expr: Expression):
    VAR_L, VAR_R = VAR_NAMES(expr)
    if expr.VARIABLE_TYPE == TypeVariableState.STRING:
        return f"var {VAR_L} = m_attrText({VAR_R});"

    return f"var {VAR_L} = m_attrTextAll({VAR_R});"


@converter(TokenType.OP_ATTR_RAW)
def op_attr_raw(expr: Expression):
    VAR_L, VAR_R = VAR_NAMES(expr)
    if expr.VARIABLE_TYPE == TypeVariableState.STRING:
        return f"var {VAR_L} = m_attrRaw({VAR_R});"
    return f"var {VAR_L} = m_attrRawAll({VAR_R});"


@converter(TokenType.OP_REGEX)
def op_regex(expr: Expression):
    VAR_L, VAR_R = VAR_NAMES(expr)
    pattern = expr.arguments[0]
    # FIXME: sanitize regex (unescape issue)
    if expr.VARIABLE_TYPE == TypeVariableState.STRING:
        return f"var {VAR_L} = m_reMatch({VAR_R}, {pattern!r});"
    return f"var {VAR_L} = {VAR_R}.map((e) => m_reMatch(e, {pattern!r})).toList();"


@converter(TokenType.OP_REGEX_ALL)
def op_regex_all(expr: Expression):
    VAR_L, VAR_R = VAR_NAMES(expr)
    pattern = expr.arguments[0]
    # FIXME: sanitize regex (unescape issue)
    return f"var {VAR_L} = m_reMatchAll({VAR_R}, {pattern!r});"


@converter(TokenType.OP_REGEX_SUB)
def op_regex_sub(expr: Expression):
    VAR_L, VAR_R = VAR_NAMES(expr)
    pattern = expr.arguments[0]
    # FIXME: sanitize regex (unescape issue)
    return f"var {VAR_L} = m_reSub({VAR_R}, {pattern!r});"


@converter(TokenType.OP_STRING_TRIM)
def op_string_trim(expr: Expression):
    VAR_L, VAR_R = VAR_NAMES(expr)
    substr = expr.arguments[0]
    if expr.VARIABLE_TYPE.STRING:
        return f"var {VAR_L} = m_strTrim({VAR_R}, {substr!r});"
    return f"var {VAR_L} = {VAR_R}.map((e) => m_strTrim(e, {substr!r})).toList();"


@converter(TokenType.OP_STRING_L_TRIM)
def op_string_l_trim(expr: Expression):
    VAR_L, VAR_R = VAR_NAMES(expr)
    substr = expr.arguments[0]
    if expr.VARIABLE_TYPE.STRING:
        return f"var {VAR_L} = m_strLTrim({VAR_R}, {substr!r});"
    return f"var {VAR_L} = {VAR_R}.map((e) => m_strLTrim(e, {substr!r})).toList();"


@converter(TokenType.OP_STRING_R_TRIM)
def op_string_r_trim(expr: Expression):
    VAR_L, VAR_R = VAR_NAMES(expr)
    substr = expr.arguments[0]
    if expr.VARIABLE_TYPE.STRING:
        return f"var {VAR_L} = m_strRTrim({VAR_R}, {substr!r});"
    return f"var {VAR_L} = {VAR_R}.map((e) => m_strRTrim(e, {substr!r})).toList();"


@converter(TokenType.OP_STRING_REPLACE)
def op_string_replace(expr: Expression):
    VAR_L, VAR_R = VAR_NAMES(expr)
    old, new = expr.arguments
    if expr.VARIABLE_TYPE.STRING:
        return f"var {VAR_L} = m_strReplace({VAR_R}, {old!r}, {new!r});"
    return f"var {VAR_L} = {VAR_R}.map((e) => m_strReplace(e, {old!r}, {new!r})).toList();"


@converter(TokenType.OP_STRING_FORMAT)
def op_string_format(expr: Expression):
    VAR_L, VAR_R = VAR_NAMES(expr)
    template = expr.arguments[0]
    if expr.VARIABLE_TYPE.STRING:
        return f"var {VAR_L} = m_strFormat({VAR_R}, {template!r});"
    return f"var {VAR_L} = {VAR_R}.map((e) => m_strFormat({VAR_R}, {template!r})).toList();"


@converter(TokenType.OP_STRING_SPLIT)
def op_string_split(expr: Expression):
    VAR_L, VAR_R = VAR_NAMES(expr)
    sep = expr.arguments[0]
    return f"var {VAR_L} = m_strSplit({VAR_R}, {sep!r});"


@converter(TokenType.OP_INDEX)
def op_index(expr: Expression):
    VAR_L, VAR_R = VAR_NAMES(expr)
    ind = expr.arguments[0]
    return f"var {VAR_L} = {VAR_R}[{ind}];"


@converter(TokenType.OP_JOIN)
def op_join(expr: Expression):
    VAR_L, VAR_R = VAR_NAMES(expr)
    sep = expr.arguments[0]
    return f"var {VAR_L} = m_arrJoin({VAR_R}, {sep!r});"


@converter(TokenType.ST_DEFAULT)
def st_default(expr: Expression):
    default_value = expr.arguments[0]
    default_value = repr(default_value) if isinstance(default_value, str) else 'null'
    t = ' ' * 2
    head = f'{t}try {{ {t * 2}'
    block = "{}"
    footer = f"\n{t} }} catch(e) {{"
    ret = f'\n{t * 3}return {default_value}; }}'
    return f'{head}{block}{footer}{ret}'


@converter(TokenType.OP_ASSERT_EQUAL)
def op_assert_equal(expr: Expression):
    VAR_L, VAR_R = VAR_NAMES(expr)
    val, msg = expr.arguments
    return f"var {VAR_L} = m_assertEq({VAR_R}, {val!r}, {msg!r});"


@converter(TokenType.OP_ASSERT_CONTAINS)
def op_assert_contains(expr: Expression):
    VAR_L, VAR_R = VAR_NAMES(expr)
    val, msg = expr.arguments
    return f"var {VAR_L} = m_assertEq({VAR_R}, {val!r}, {msg!r});"


@converter(TokenType.OP_ASSERT_RE_MATCH)
def op_assert_re_match(expr: Expression):
    VAR_L, VAR_R = VAR_NAMES(expr)
    val, msg = expr.arguments
    return f"var {VAR_L} = m_assertReMatch({VAR_R}, {val!r}, {msg!r});"


@converter(TokenType.OP_ASSERT_CSS)
def op_assert_css(expr: Expression):
    VAR_L, VAR_R = VAR_NAMES(expr)
    q, msg = expr.arguments
    return f"var {VAR_L} = m_assertCss({VAR_R}, {q!r}, {msg!r})"


@converter(TokenType.OP_ASSERT_XPATH)
def op_assert_xpath(_):
    raise NotImplementedError("Not supported")


@converter(TokenType.OP_NESTED_SCHEMA)
def op_nested_schema(expr: Expression):
    VAR_L, VAR_R = VAR_NAMES(expr)
    cls = expr.arguments[0]
    # 0 - Document type
    # 0> - Element type
    if expr.num == 0:
        return f"var {VAR_L} = {cls}.fromDocument({VAR_R}).parse();"
    return f"var {VAR_L} = {cls}.fromElement({VAR_R}).parse();"


@converter(TokenType.ST_DOCSTRING)
def st_docstring(expr: Expression):
    doc = expr.arguments[0]
    return '\n'.join([f"/// {line}" for line in doc.split('\n')])


@converter(TokenType.ST_METHOD)
def st_method(expr: Expression):
    name = expr.arguments[0]
    if c_name := CONST_METHODS.get(name):
        return c_name + \
            '{'  # method body open

    return f"_parse{name.lower().capitalize()}(el)" \
        + '{'  # method body open


@converter(TokenType.ST_NO_RET)
def st_no_ret(_):
    return "return null;" \
        + '}'  # method body close


@converter(TokenType.ST_RET)
def st_ret(expr: Expression):
    VAR_L, _ = VAR_NAMES(expr)
    return f"return {VAR_L};" \
        + "}"  # method body close


code_generator = CodeGenerator(
    templates_path='ssc_codegen2.converters.templates.dart',
    base_struct_path='universal_html',
    converter=converter)
