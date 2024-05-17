from ssc_codegen2.converters.base import BaseCodeConverter
from ssc_codegen2.expression import Expression
from ssc_codegen2.tokens import TokenType
from ssc_codegen2.type_state import TypeVariableState

converter = BaseCodeConverter()

# create variable names function
VAR_NAMES = converter.create_var_names

CONST_METHODS = {
    "__SPLIT_DOC__": "def _part_document(self, el):",
    "__ITEM__": "def _parse_item(self, el):",
    "__KEY__": "def _parse_key(self, el):",
    "__VALUE__": "def _parse_value(self, el):"
}


@converter(TokenType.OP_XPATH)
def op_xpath(e: Expression):
    VAR_L, VAR_R = VAR_NAMES(e)
    query = e.arguments[0]
    return f"{VAR_L} = self._xpath({VAR_R}, {query!r})"


@converter(TokenType.OP_XPATH_ALL)
def op_xpath_all(e):
    VAR_L, VAR_R = VAR_NAMES(e)
    query = e.arguments[0]
    return f"{VAR_L} = self._xpath_all({VAR_R}, {query!r})"


@converter(TokenType.OP_CSS)
def op_css(e):
    VAR_L, VAR_R = VAR_NAMES(e)
    query = e.arguments[0]
    return f"{VAR_L} = self._css({VAR_R}, {query!r})"


@converter(TokenType.OP_CSS_ALL)
def op_css_all(e):
    VAR_L, VAR_R = VAR_NAMES(e)
    query = e.arguments[0]
    return f"{VAR_L} = self._css_all({VAR_R}, {query!r})"


@converter(TokenType.OP_ATTR)
def op_attr(e):
    VAR_L, VAR_R = VAR_NAMES(e)
    name = e.arguments[0]
    return f"{VAR_L} = self._attr({VAR_R}, {name!r})"


@converter(TokenType.OP_ATTR_TEXT)
def op_attr_text(e: Expression):
    VAR_L, VAR_R = VAR_NAMES(e)
    if e.VARIABLE_TYPE == TypeVariableState.STRING:
        return f"{VAR_L} = self._attr_text({VAR_R})"
    return f"{VAR_L} = [self._attr_text(i) for i in {VAR_R}]"


@converter(TokenType.OP_ATTR_RAW)
def op_attr_raw(e: Expression):
    VAR_L, VAR_R = VAR_NAMES(e)
    if e.VARIABLE_TYPE == TypeVariableState.STRING:
        return f"{VAR_L} = self._attr_raw({VAR_R})"
    return f"{VAR_L} = [self._attr_raw(i) for i in {VAR_R}]"


@converter(TokenType.OP_REGEX)
def op_regex(e: Expression):
    VAR_L, VAR_R = VAR_NAMES(e)
    pattern = e.arguments[0]
    if e.VARIABLE_TYPE == TypeVariableState.STRING:
        return f"{VAR_L} = self._re_match({VAR_R}, {pattern!r})"
    return f"{VAR_L} = [self._re_match(i, {pattern!r}) for i in {VAR_R}]"


@converter(TokenType.OP_REGEX_ALL)
def op_regex_all(e: Expression):
    VAR_L, VAR_R = VAR_NAMES(e)
    pattern = e.arguments[0]
    return f"{VAR_L} = self._re_match_all({VAR_R}, {pattern!r})"


@converter(TokenType.OP_REGEX_SUB)
def op_regex_sub(e: Expression):
    VAR_L, VAR_R = VAR_NAMES(e)
    pattern = e.arguments[0]
    if e.VARIABLE_TYPE == TypeVariableState.STRING:
        return f"{VAR_L} = self._re_sub({VAR_R}, {pattern!r})"
    return f"{VAR_L} = [self._re_sub(i, {pattern!r}) for i in {VAR_R}]"


@converter(TokenType.OP_STRING_TRIM)
def op_string_trim(e: Expression):
    VAR_L, VAR_R = VAR_NAMES(e)
    substr = e.arguments[0]
    if e.VARIABLE_TYPE == TypeVariableState.STRING:
        return f"{VAR_L} = self._str_trim({VAR_R}, {substr!r})"
    return f"{VAR_L} = [self._str_trim(i, {substr!r}) for i {VAR_R}]"


@converter(TokenType.OP_STRING_L_TRIM)
def op_string_l_trim(e: Expression):
    VAR_L, VAR_R = VAR_NAMES(e)
    substr = e.arguments[0]
    if e.VARIABLE_TYPE == TypeVariableState.STRING:
        return f"{VAR_L} = self._str_ltrim({VAR_R}, {substr!r})"
    return f"{VAR_L} = [self._str_ltrim(i, {substr!r}) for i in {VAR_R}]"


@converter(TokenType.OP_STRING_R_TRIM)
def op_string_r_trim(e: Expression):
    VAR_L, VAR_R = VAR_NAMES(e)
    substr = e.arguments[0]
    if e.VARIABLE_TYPE == TypeVariableState.STRING:
        return f"{VAR_L} = self._str_rtrim({VAR_R}, {substr!r})"
    return f"{VAR_L} = [self._str_rtrim(i, {substr!r}) for i in {VAR_R}]"


@converter(TokenType.OP_STRING_REPLACE)
def op_string_replace(e: Expression):
    VAR_L, VAR_R = VAR_NAMES(e)
    old, new = e.arguments
    if e.VARIABLE_TYPE == TypeVariableState.STRING:
        return f"{VAR_L} = self._str_replace({VAR_R}, {old!r}, {new!r})"
    return f"[{VAR_L} = self._str_replace(i, {old!r}, {new!r}) for i in {VAR_R}]"


@converter(TokenType.OP_STRING_FORMAT)
def op_string_format(e: Expression):
    VAR_L, VAR_R = VAR_NAMES(e)
    fmt: str = e.arguments[0]
    fmt = fmt.replace("{{}}", "{}", 1)
    if e.VARIABLE_TYPE == TypeVariableState.STRING:
        return f"{VAR_L} = self._str_format({VAR_R}, {fmt!r})"
    return f"{VAR_L} = [self._str_format(i, {fmt!r}) for i in {VAR_R}]"


@converter(TokenType.OP_STRING_SPLIT)
def op_string_split(e: Expression):
    VAR_L, VAR_R = VAR_NAMES(e)
    sep = e.arguments[0]
    return f"{VAR_L} = self._str_spilt({VAR_R}, {sep!r})"


@converter(TokenType.OP_INDEX)
def op_index(e: Expression):
    VAR_L, VAR_R = VAR_NAMES(e)
    ind = e.arguments[0]
    return f"{VAR_L} = {VAR_R}[{ind}]"


@converter(TokenType.OP_JOIN)
def op_join(e: Expression):
    VAR_L, VAR_R = VAR_NAMES(e)
    sep = e.arguments[0]
    return f"{VAR_L} = self._arr_join({VAR_R}, {sep!r})"


@converter(TokenType.OP_DEFAULT)
def op_default(e: Expression):
    default_value = e.arguments[0]
    default_value = repr(default_value) if isinstance(default_value, str) else default_value
    head = "\ttry:\n\t\t"
    block = "{}"
    footer = f"\n\t\texcept Exception:"
    ret = f'\n\t\t\treturn {default_value}'
    return f'{head}{block}{footer}{ret}'


@converter(TokenType.OP_ASSERT_EQUAL)
def op_assert_equal(e: Expression):
    VAR_L, VAR_R = VAR_NAMES(e)
    val, msg = e.arguments
    return f"{VAR_L} = self._assert_eq({VAR_R}, {val!r}, {msg!r})"


@converter(TokenType.OP_ASSERT_CONTAINS)
def op_assert_contains(e: Expression):
    VAR_L, VAR_R = VAR_NAMES(e)
    val, msg = e.arguments
    return f"{VAR_L} = self._assert_contains({VAR_R}, {val!r}, {msg!r})"


@converter(TokenType.OP_ASSERT_RE_MATCH)
def op_assert_re_match(e: Expression):
    VAR_L, VAR_R = VAR_NAMES(e)
    val, msg = e.arguments
    return f"{VAR_L} = self._assert_re_match({VAR_R}, {val!r}, {msg!r})"


@converter(TokenType.OP_ASSERT_CSS)
def op_assert_css(e: Expression):
    VAR_L, VAR_R = VAR_NAMES(e)
    val, msg = e.arguments
    return f"{VAR_L} = self._assert_css({VAR_R}, {val!r}, {msg!r})"


@converter(TokenType.OP_ASSERT_XPATH)
def op_assert_xpath(e: Expression):
    VAR_L, VAR_R = VAR_NAMES(e)
    val, msg = e.arguments
    return f"{VAR_L} = self._assert_xpath({VAR_R}, {val!r}, {msg!r})"


@converter(TokenType.ST_DOCSTRING)
def op_docstring(e: Expression):
    docstr = e.arguments[0]
    return f'''
    """
    {docstr}
    """
    '''


@converter(TokenType.ST_METHOD)
def op_method_name(e):
    name = e.arguments[0]
    # TODO move to constants
    if magic_method := CONST_METHODS.get(name):
        return magic_method
    return f"def _parse_{name}(self, el: Selector):"


@converter(TokenType.ST_NO_RET)
def op_no_ret(_):
    return "return"


@converter(TokenType.ST_RET)
def op_ret(e):
    VAR_L, _ = VAR_NAMES(e)
    return f"return {VAR_L}"


@converter(TokenType.OP_NESTED_SCHEMA)
def op_nested_schema(e: Expression):
    VAR_L, VAR_R = VAR_NAMES(e)
    sc_klass = e.arguments[0]
    return f"{VAR_L} = self._nested_parser({VAR_R}, {sc_klass})"


if __name__ == '__main__':
    from ssc_codegen2.schema import ItemSchema, ListSchema, DictSchema, FlattenListSchema
    from ssc_codegen2.document import D, N
    from ssc_codegen2.converters.generator import TemplateStruct, generate_code_from_schemas

    class Links(DictSchema):
        __SPLIT_DOC__ = D().css_all('a')
        __KEY__ = D().text().trim(" ")
        __VALUE__ = D().attr('href')
        __SIGNATURE__ = {"link_name": "link_url", "...": "..."}


    class Books(ListSchema):
        __SPLIT_DOC__ = D().css_all('.col-lg-3')

        image = D().css('.thumbnail').attr('src')
        name = D().css('.thumbnail').attr('alt')
        price = D().css('p.price_color').text()

    class CataloguePage(ItemSchema):
        __PRE_VALIDATE__ = D().css('title').text().assert_re("Books to Scrape - Sandbox")

        links: Links = N().sub_parser(Links)
        books: Books = N().sub_parser(Books)


    # t2 = TemplateStruct(Test, converter, {})
    generate_code_from_schemas("templates/py/parsel", converter, Links, Books, CataloguePage)
    # print(t2.name)
    #
    # print(t2.docstring)
    # print(t2.methods_names, end='\n\t')
    # print(*t2.methods_code(), sep='\n\n')
    # struct = SubSchema.get_ast_struct()
    # print(struct.docstring().arguments[0])
    # for f in struct.fields:
    #     print(converter.convert(f.method))
    #     code = [converter.convert(e) for e in f.expressions]
    #     if f.default:
    #         wrapper = converter.convert(f.default)
    #         print(wrapper.format('\n'.join(code)))
    #     else:
    #         print(*code, sep='\n')
