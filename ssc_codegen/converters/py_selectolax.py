from .py_base import lr_var_names, BasePyCodeConverter
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

converter = BasePyCodeConverter()

SLAX_IMPORTS = "from selectolax.parser import HTMLParser, Node"
SLAX_INIT_BODY = (
    "self._doc=HTMLParser(document) if isinstance(document, str) else document"
)
E_SLAX_CSS = "{} = {}.css_first({})"
E_SLAX_CSS_ALL = "{} = {}.css({})"
E_SLAX_TEXT = "{} = {}.text()"
E_SLAX_TEXT_ALL = "{} = [e.text() for e in {}]"
E_SLAX_RAW = "{} = {}.html"
E_SLAX_RAW_ALL = "{} = [e.html for e in {}]"
E_SLAX_ATTR = "{} = {}.attributes[{}]"
E_SLAX_ATTR_ALL = "{} = [e.attributes[{}] for e in {}]"
E_IS_CSS = "assert {}.css_first({}), {}"


@converter.pre(TokenType.STRUCT_INIT)
def tt_init(_) -> str:
    return py.INDENT_METHOD + py.CLS_INIT_HEAD.format(
        "Union[str, HTMLParser, Node]"
    )


@converter.post(TokenType.STRUCT_INIT)
def tt_init(_):
    return py.INDENT_METHOD_BODY + SLAX_INIT_BODY


@converter.pre(TokenType.IMPORTS)
def tt_imports(_: ModuleImports) -> str:
    imports = py.BASE_IMPORTS + SLAX_IMPORTS
    return imports


@converter.pre(TokenType.STRUCT_PRE_VALIDATE)
def tt_pre_validate(node: PreValidateFunction) -> str:
    # Union[HTMLParser, Node]
    return py.INDENT_METHOD + py.CLS_PRE_VALIDATE_HEAD.format(
        py.MAGIC_METHODS.get(node.name)
    )


@converter.pre(TokenType.STRUCT_PART_DOCUMENT)
def tt_part_document(node: PartDocFunction):
    name = py.MAGIC_METHODS.get(node.name)
    return py.INDENT_METHOD + py.CLS_PART_DOC_HEAD.format(
        name, "Union[str, HTMLParser, Node]", "List[Node]"
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
    p_type = "Union[str, HTMLParser, Node]"
    return py.INDENT_METHOD + py.FN_PARSE.format(name, p_type, type_)


# selectolax API
@converter.pre(TokenType.EXPR_CSS)
def tt_css(node: HtmlCssExpression) -> str:
    q = repr(node.query)
    prv, nxt = lr_var_names(variable=node.variable)
    code = E_SLAX_CSS.format(nxt, prv, q)
    if node.have_default_expr():
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


@converter.pre(TokenType.EXPR_CSS_ALL)
def tt_css_all(node: HtmlCssAllExpression) -> str:
    q = repr(node.query)
    prv, nxt = lr_var_names(variable=node.variable)
    code = E_SLAX_CSS_ALL.format(nxt, prv, q)
    if node.have_default_expr():
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


@converter.pre(TokenType.EXPR_TEXT)
def tt_text(node: HtmlTextExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    code = E_SLAX_TEXT.format(nxt, prv)
    if node.have_default_expr():
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


@converter.pre(TokenType.EXPR_TEXT_ALL)
def tt_text_all(node: HtmlTextAllExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    code = E_SLAX_TEXT_ALL.format(nxt, prv)
    if node.have_default_expr():
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


@converter.pre(TokenType.EXPR_RAW)
def tt_raw(node: HtmlRawExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    code = E_SLAX_RAW.format(nxt, prv)
    if node.have_default_expr():
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


@converter.pre(TokenType.EXPR_RAW_ALL)
def tt_raw_all(node: HtmlRawAllExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    code = E_SLAX_RAW_ALL.format(nxt, prv)
    if node.have_default_expr():
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


@converter.pre(TokenType.EXPR_ATTR)
def tt_attr(node: HtmlAttrExpression):
    attr = repr(node.attr)
    prv, nxt = lr_var_names(variable=node.variable)
    code = E_SLAX_ATTR.format(nxt, prv, attr)
    if node.have_default_expr():
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


@converter.pre(TokenType.EXPR_ATTR_ALL)
def tt_attr_all(node: HtmlAttrAllExpression):
    attr = repr(node.attr)
    prv, nxt = lr_var_names(variable=node.variable)

    code = E_SLAX_ATTR_ALL.format(nxt, attr, prv)
    if node.have_default_expr():
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


@converter.pre(TokenType.IS_CSS)
def tt_is_css(node: IsCssExpression):
    prv, nxt = lr_var_names(variable=node.variable)
    q = repr(node.query)
    msg = repr(node.msg)
    code = E_IS_CSS.format(prv, q, msg)
    indent = (
        py.INDENT_DEFAULT_BODY
        if node.have_default_expr()
        else py.INDENT_METHOD_BODY
    )
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return indent + code
    return f"{indent}{code}\n{indent}{nxt} = {prv}"


@converter.pre(TokenType.EXPR_XPATH)
def tt_xpath(_: HtmlXpathExpression) -> str:
    raise NotImplementedError("Selectolax not support xpath")


@converter.pre(TokenType.EXPR_XPATH_ALL)
def tt_xpath_all(_: HtmlXpathAllExpression) -> str:
    raise NotImplementedError("Selectolax not support xpath")


@converter.pre(TokenType.IS_XPATH)
def tt_is_xpath(_: IsXPathExpression):
    raise NotImplementedError("Selectolax not support xpath")
