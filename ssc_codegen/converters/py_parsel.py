from .py_base import BasePyCodeConverter, lr_var_names
from .templates import py
from ..ast_ssc import (
    ModuleImports,
    PreValidateFunction,
    StructFieldFunction,
    PartDocFunction,
    HtmlCssExpression,
    HtmlCssAllExpression,
    HtmlAttrExpression,
    HtmlAttrAllExpression,
    HtmlTextExpression,
    HtmlTextAllExpression,
    HtmlRawExpression,
    HtmlRawAllExpression,
    HtmlXpathExpression,
    HtmlXpathAllExpression,
    IsCssExpression,
    IsXPathExpression,
)
from ..tokens import TokenType, StructType, VariableType

PARSEL_INIT = (
    "self._doc=Selector(document) if isinstance(document, str) else document"
)
PARSEL_IMPORTS = "from parsel import Selector, SelectorList"
E_PARSEL_CSS = "{} = {}.css({})"
E_PARSEL_CSS_ALL = E_PARSEL_CSS
E_PARSEL_XPATH = "{} = {}.css({})"
E_PARSEL_XPATH_ALL = E_PARSEL_XPATH
E_PARSEL_TEXT = '{} = {}.css("::text").get()'
E_PARSEL_TEXT_ALL = '{} = {}.css("::text").getall()'
E_PARSEL_RAW = "{} = {}.get()"
E_PARSEL_RAW_ALL = "{} = {}.getall()"
E_PARSEL_ATTR = "{} = {}.css('::attr({})').get()"
E_PARSEL_ATTR_ALL = "{} = {}.css('::attr({})').getall()"
E_PARSEL_IS_CSS = "assert {}.css({}), {}"
E_PARSEL_IS_XPATH = "assert {}.xpath({}), {}"

converter = BasePyCodeConverter()


@converter.pre(TokenType.STRUCT_INIT)
def tt_init(_) -> str:
    p_type = "Union[str, SelectorList, Selector]"
    return py.INDENT_METHOD + py.CLS_INIT_HEAD.format(p_type)


@converter.post(TokenType.STRUCT_INIT)
def tt_init(_):
    return py.INDENT_METHOD_BODY + PARSEL_INIT


@converter.pre(TokenType.IMPORTS)
def tt_imports(_: ModuleImports) -> str:
    imports = py.BASE_IMPORTS + PARSEL_IMPORTS
    return imports


@converter.pre(TokenType.STRUCT_PRE_VALIDATE)
def tt_pre_validate(node: PreValidateFunction) -> str:
    return py.INDENT_METHOD + py.CLS_PRE_VALIDATE_HEAD.format(
        py.MAGIC_METHODS.get(node.name)
    )


@converter.pre(TokenType.STRUCT_PART_DOCUMENT)
def tt_part_document(node: PartDocFunction):
    p_type = "Selector"
    ret_type = "SelectorList"
    name = py.MAGIC_METHODS.get(node.name)
    return py.INDENT_METHOD + py.CLS_PART_DOC_HEAD.format(
        name, p_type, ret_type
    )


@converter.pre(TokenType.STRUCT_FIELD)
def tt_function(node: StructFieldFunction) -> str:
    name = py.MAGIC_METHODS.get(node.name, node.name)
    if node.ret_type == VariableType.NESTED:
        t_def = node.find_associated_typedef()
        if t_def.struct_ref.type == StructType.LIST:
            t_name = py.TYPE_PREFIX.format(t_def.struct_ref.name)
            type_ = py.TYPE_LIST.format(t_name)
        else:
            type_ = py.TYPE_PREFIX.format(t_def.struct_ref.name)
    else:
        type_ = py.TYPES.get(node.ret_type)
    p_type = "Selector"
    return py.INDENT_METHOD + py.FN_PARSE.format(name, p_type, type_)


# PARSEL API
@converter.pre(TokenType.EXPR_CSS)
def tt_css(node: HtmlCssExpression) -> str:
    q = repr(node.query)
    prv, nxt = lr_var_names(variable=node.variable)
    code = E_PARSEL_CSS.format(nxt, prv, q)

    if node.have_default_expr():
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


@converter.pre(TokenType.EXPR_CSS_ALL)
def tt_css_all(node: HtmlCssAllExpression) -> str:
    q = repr(node.query)
    prv, nxt = lr_var_names(variable=node.variable)
    code = E_PARSEL_CSS_ALL.format(nxt, prv, q)
    if node.have_default_expr():
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


@converter.pre(TokenType.EXPR_XPATH)
def tt_xpath(node: HtmlXpathExpression) -> str:
    q = repr(node.query)
    prv, nxt = lr_var_names(variable=node.variable)
    code = E_PARSEL_XPATH.format(nxt, prv, q)
    if node.have_default_expr():
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


@converter.pre(TokenType.EXPR_XPATH_ALL)
def tt_xpath_all(node: HtmlXpathAllExpression) -> str:
    q = repr(node.query)
    prv, nxt = lr_var_names(variable=node.variable)
    code = E_PARSEL_XPATH_ALL.format(nxt, prv, q)
    if node.have_default_expr():
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


@converter.pre(TokenType.EXPR_TEXT)
def tt_text(node: HtmlTextExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    code = E_PARSEL_TEXT.format(nxt, prv)
    if node.have_default_expr():
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


@converter.pre(TokenType.EXPR_TEXT_ALL)
def tt_text_all(node: HtmlTextAllExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    code = E_PARSEL_TEXT_ALL.format(nxt, prv)
    if node.have_default_expr():
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


@converter.pre(TokenType.EXPR_RAW)
def tt_raw(node: HtmlRawExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    code = E_PARSEL_RAW.format(nxt, prv)
    if node.have_default_expr():
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


@converter.pre(TokenType.EXPR_RAW_ALL)
def tt_raw_all(node: HtmlRawAllExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    code = E_PARSEL_RAW_ALL.format(nxt, prv)
    if node.have_default_expr():
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


@converter.pre(TokenType.EXPR_ATTR)
def tt_attr(node: HtmlAttrExpression):
    n = node.attr
    prv, nxt = lr_var_names(variable=node.variable)
    code = E_PARSEL_ATTR.format(nxt, prv, n)
    if node.have_default_expr():
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


@converter.pre(TokenType.EXPR_ATTR_ALL)
def tt_attr_all(node: HtmlAttrAllExpression):
    n = node.attr
    prv, nxt = lr_var_names(variable=node.variable)
    code = E_PARSEL_ATTR_ALL.format(nxt, prv, n)
    if node.have_default_expr():
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


@converter.pre(TokenType.IS_CSS)
def tt_is_css(node: IsCssExpression):
    prv, nxt = lr_var_names(variable=node.variable)
    q = repr(node.query)
    msg = repr(node.msg)
    code = E_PARSEL_IS_CSS.format(prv, q, msg)
    indent = (
        py.INDENT_DEFAULT_BODY
        if node.have_default_expr()
        else py.INDENT_METHOD_BODY
    )
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return indent + code
    return f"{indent}{code}\n{indent}{nxt} = {prv}"


@converter.pre(TokenType.IS_XPATH)
def tt_is_xpath(node: IsXPathExpression):
    prv, nxt = lr_var_names(variable=node.variable)
    q = repr(node.query)
    msg = repr(node.msg)
    code = E_PARSEL_IS_XPATH.format(prv, q, msg)
    indent = (
        py.INDENT_DEFAULT_BODY
        if node.have_default_expr()
        else py.INDENT_METHOD_BODY
    )
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return indent + code
    return f"{indent}{code}\n{indent}{nxt} = {prv}"
