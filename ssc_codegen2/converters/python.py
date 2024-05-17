# universal python codegen
from ssc_codegen2.converters.base import BaseCodeConverter
from ssc_codegen2.expression import Expression
from ssc_codegen2.tokens import TokenType
from ssc_codegen2.type_state import TypeVariableState

CONST_METHODS = {
    "__SPLIT_DOC__": "def _part_document(self, el):",
    "__ITEM__": "def _parse_item(self, el):",
    "__KEY__": "def _parse_key(self, el):",
    "__VALUE__": "def _parse_value(self, el):",
    "__PRE_VALIDATE__": "def _pre_validate(self, el):"
}


class PythonCodeConverter(BaseCodeConverter):
    def __init__(self,
                 *,
                 indent: int = 1,  # indent mul
                 chr_indent: str = ' ' * 4,  # indent char
                 end: str = "",  # end line of code
                 default_indent: int = 2,
                 ):
        super().__init__(indent=indent, chr_indent=chr_indent, end=end, default_indent=default_indent)

        self(TokenType.OP_XPATH)(op_xpath)
        self(TokenType.OP_XPATH_ALL)(op_xpath_all)
        self(TokenType.OP_CSS)(op_css)
        self(TokenType.OP_CSS_ALL)(op_css_all)
        self(TokenType.OP_ATTR)(op_attr)
        self(TokenType.OP_ATTR_TEXT)(op_attr_text)
        self(TokenType.OP_ATTR_RAW)(op_attr_raw)
        self(TokenType.OP_REGEX)(op_regex)
        self(TokenType.OP_REGEX_ALL)(op_regex_all)
        self(TokenType.OP_REGEX_SUB)(op_regex_sub)
        self(TokenType.OP_STRING_TRIM)(op_string_trim)
        self(TokenType.OP_STRING_L_TRIM)(op_string_l_trim)
        self(TokenType.OP_STRING_R_TRIM)(op_string_r_trim)
        self(TokenType.OP_STRING_REPLACE)(op_string_replace)
        self(TokenType.OP_STRING_FORMAT)(op_string_format)
        self(TokenType.OP_STRING_SPLIT)(op_string_split)
        self(TokenType.OP_INDEX)(op_index)
        self(TokenType.OP_JOIN)(op_join)
        self(TokenType.OP_DEFAULT)(op_default)
        self(TokenType.OP_ASSERT_EQUAL)(op_assert_equal)
        self(TokenType.OP_ASSERT_CONTAINS)(op_assert_contains)
        self(TokenType.OP_ASSERT_RE_MATCH)(op_assert_re_match)
        self(TokenType.OP_ASSERT_CSS)(op_assert_css)
        self(TokenType.OP_ASSERT_XPATH)(op_assert_xpath)
        self(TokenType.OP_NESTED_SCHEMA)(op_nested_schema)
        self(TokenType.ST_DOCSTRING)(st_docstring)
        self(TokenType.ST_METHOD)(st_method)
        self(TokenType.ST_NO_RET)(st_no_ret)
        self(TokenType.ST_RET)(st_ret)


# create variable names function
VAR_NAMES = PythonCodeConverter.create_var_names


def op_xpath(e: Expression):
    VAR_L, VAR_R = VAR_NAMES(e)
    query = e.arguments[0]
    return f"{VAR_L} = self._xpath({VAR_R}, {query!r})"


def op_xpath_all(e):
    VAR_L, VAR_R = VAR_NAMES(e)
    query = e.arguments[0]
    return f"{VAR_L} = self._xpath_all({VAR_R}, {query!r})"


def op_css(e):
    VAR_L, VAR_R = VAR_NAMES(e)
    query = e.arguments[0]
    return f"{VAR_L} = self._css({VAR_R}, {query!r})"


def op_css_all(e):
    VAR_L, VAR_R = VAR_NAMES(e)
    query = e.arguments[0]
    return f"{VAR_L} = self._css_all({VAR_R}, {query!r})"


def op_attr(e):
    VAR_L, VAR_R = VAR_NAMES(e)
    name = e.arguments[0]
    return f"{VAR_L} = self._attr({VAR_R}, {name!r})"


def op_attr_text(e: Expression):
    VAR_L, VAR_R = VAR_NAMES(e)
    if e.VARIABLE_TYPE == TypeVariableState.STRING:
        return f"{VAR_L} = self._attr_text({VAR_R})"
    return f"{VAR_L} = [self._attr_text(i) for i in {VAR_R}]"


def op_attr_raw(e: Expression):
    VAR_L, VAR_R = VAR_NAMES(e)
    if e.VARIABLE_TYPE == TypeVariableState.STRING:
        return f"{VAR_L} = self._attr_raw({VAR_R})"
    return f"{VAR_L} = [self._attr_raw(i) for i in {VAR_R}]"


def op_regex(e: Expression):
    VAR_L, VAR_R = VAR_NAMES(e)
    pattern = e.arguments[0]
    if e.VARIABLE_TYPE == TypeVariableState.STRING:
        return f"{VAR_L} = self._re_match({VAR_R}, {pattern!r})"
    return f"{VAR_L} = [self._re_match(i, {pattern!r}) for i in {VAR_R}]"


def op_regex_all(e: Expression):
    VAR_L, VAR_R = VAR_NAMES(e)
    pattern = e.arguments[0]
    return f"{VAR_L} = self._re_match_all({VAR_R}, {pattern!r})"


def op_regex_sub(e: Expression):
    VAR_L, VAR_R = VAR_NAMES(e)
    pattern = e.arguments[0]
    if e.VARIABLE_TYPE == TypeVariableState.STRING:
        return f"{VAR_L} = self._re_sub({VAR_R}, {pattern!r})"
    return f"{VAR_L} = [self._re_sub(i, {pattern!r}) for i in {VAR_R}]"


def op_string_trim(e: Expression):
    VAR_L, VAR_R = VAR_NAMES(e)
    substr = e.arguments[0]
    if e.VARIABLE_TYPE == TypeVariableState.STRING:
        return f"{VAR_L} = self._str_trim({VAR_R}, {substr!r})"
    return f"{VAR_L} = [self._str_trim(i, {substr!r}) for i {VAR_R}]"


def op_string_l_trim(e: Expression):
    VAR_L, VAR_R = VAR_NAMES(e)
    substr = e.arguments[0]
    if e.VARIABLE_TYPE == TypeVariableState.STRING:
        return f"{VAR_L} = self._str_ltrim({VAR_R}, {substr!r})"
    return f"{VAR_L} = [self._str_ltrim(i, {substr!r}) for i in {VAR_R}]"


def op_string_r_trim(e: Expression):
    VAR_L, VAR_R = VAR_NAMES(e)
    substr = e.arguments[0]
    if e.VARIABLE_TYPE == TypeVariableState.STRING:
        return f"{VAR_L} = self._str_rtrim({VAR_R}, {substr!r})"
    return f"{VAR_L} = [self._str_rtrim(i, {substr!r}) for i in {VAR_R}]"


def op_string_replace(e: Expression):
    VAR_L, VAR_R = VAR_NAMES(e)
    old, new = e.arguments
    if e.VARIABLE_TYPE == TypeVariableState.STRING:
        return f"{VAR_L} = self._str_replace({VAR_R}, {old!r}, {new!r})"
    return f"[{VAR_L} = self._str_replace(i, {old!r}, {new!r}) for i in {VAR_R}]"


def op_string_format(e: Expression):
    VAR_L, VAR_R = VAR_NAMES(e)
    fmt: str = e.arguments[0]
    fmt = fmt.replace("{{}}", "{}", 1)
    if e.VARIABLE_TYPE == TypeVariableState.STRING:
        return f"{VAR_L} = self._str_format({VAR_R}, {fmt!r})"
    return f"{VAR_L} = [self._str_format(i, {fmt!r}) for i in {VAR_R}]"


def op_string_split(e: Expression):
    VAR_L, VAR_R = VAR_NAMES(e)
    sep = e.arguments[0]
    return f"{VAR_L} = self._str_spilt({VAR_R}, {sep!r})"


def op_index(e: Expression):
    VAR_L, VAR_R = VAR_NAMES(e)
    ind = e.arguments[0]
    return f"{VAR_L} = {VAR_R}[{ind}]"


def op_join(e: Expression):
    VAR_L, VAR_R = VAR_NAMES(e)
    sep = e.arguments[0]
    return f"{VAR_L} = self._arr_join({VAR_R}, {sep!r})"


def op_default(e: Expression):
    default_value = e.arguments[0]
    default_value = repr(default_value) if isinstance(default_value, str) else default_value
    t = ' ' * 4
    head = f"{t}try:\n{t * 2}"
    block = "{}"
    footer = f"\n{t}except Exception:"
    ret = f'\n{t * 3}return {default_value}'
    return f'{head}{block}{footer}{ret}'


def op_assert_equal(e: Expression):
    VAR_L, VAR_R = VAR_NAMES(e)
    val, msg = e.arguments
    return f"{VAR_L} = self._assert_eq({VAR_R}, {val!r}, {msg!r})"


def op_assert_contains(e: Expression):
    VAR_L, VAR_R = VAR_NAMES(e)
    val, msg = e.arguments
    return f"{VAR_L} = self._assert_contains({VAR_R}, {val!r}, {msg!r})"


def op_assert_re_match(e: Expression):
    VAR_L, VAR_R = VAR_NAMES(e)
    val, msg = e.arguments
    return f"{VAR_L} = self._assert_re_match({VAR_R}, {val!r}, {msg!r})"


def op_assert_css(e: Expression):
    VAR_L, VAR_R = VAR_NAMES(e)
    val, msg = e.arguments
    return f"{VAR_L} = self._assert_css({VAR_R}, {val!r}, {msg!r})"


def op_assert_xpath(e: Expression):
    VAR_L, VAR_R = VAR_NAMES(e)
    val, msg = e.arguments
    return f"{VAR_L} = self._assert_xpath({VAR_R}, {val!r}, {msg!r})"


def st_docstring(e: Expression):
    docstr = e.arguments[0]
    return f'''
    """
    {docstr}
    """
    '''


def st_method(e):
    name = e.arguments[0]
    if magic_method := CONST_METHODS.get(name):
        return magic_method
    return f"def _parse_{name}(self, el):"


def st_no_ret(_):
    return "return"


def st_ret(e):
    VAR_L, _ = VAR_NAMES(e)
    return f"return {VAR_L}"


def op_nested_schema(e: Expression):
    VAR_L, VAR_R = VAR_NAMES(e)
    sc_klass = e.arguments[0]
    return f"{VAR_L} = self._nested_parser({VAR_R}, {sc_klass})"
