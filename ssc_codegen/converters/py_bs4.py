from .py_base import BasePyCodeConverter, lr_var_names
from .templates import py
from .utils import have_default_expr, find_nested_associated_typedef_by_st_field_fn
from ..ast_ssc import (
    ModuleImports,
    StructFieldFunction,
    PartDocFunction,

    HtmlCssExpression, HtmlCssAllExpression,
    HtmlAttrExpression, HtmlAttrAllExpression,
    HtmlTextExpression, HtmlTextAllExpression,
    HtmlRawExpression, HtmlRawAllExpression,
    HtmlXpathExpression, HtmlXpathAllExpression,

    IsCssExpression, IsXPathExpression, PreValidateFunction
)
from ..tokens import TokenType, StructType, VariableType

BS4_INIT = "self._doc=BeautifulSoup(document, 'lxml') if isinstance(document, str) else document"
BS4_IMPORTS = "from bs4 import BeautifulSoup, ResultSet, Tag  # noqa (for typing)"

E_BS4_CSS = "{} = {}.select_one({})"
E_BS4_CSS_ALL = "{} = {}.select({})"
E_BS4_TEXT = "{} = {}.text"
E_BS4_TEXT_ALL = "{} = [e.text for e in {}]"
# bs4 auto convert multiattr values to list
# most libs return attr value as string
E_BS4_ATTR = "{} = {}[{}] if isinstance({}[{}], str) else ' '.join({}[{}])"
E_BS4_ATTR_ALL = "{} = [e[{}] if isinstance(e[{}], str) else ' '.join(e[{}]) for e in {}]"
E_BS4_RAW = "{} = str({}) if {} else {}"  # maybe None
E_BS4_RAW_ALL = "{} = [e for e in {} if e]"  # maybe None
E_BS4_IS_CSS = "assert {}.select_one({}), {}"

converter = BasePyCodeConverter()


@converter.pre(TokenType.STRUCT_INIT)
def tt_init(_) -> str:
    return py.INDENT_METHOD + py.CLS_INIT_HEAD.format('Union[str, BeautifulSoup, Tag]')


@converter.post(TokenType.STRUCT_INIT)
def tt_init(_):
    return py.INDENT_METHOD_BODY + BS4_INIT


@converter.pre(TokenType.IMPORTS)
def tt_imports(_: ModuleImports) -> str:
    return py.BASE_IMPORTS + BS4_IMPORTS


@converter.pre(TokenType.STRUCT_PRE_VALIDATE)
def tt_pre_validate(node: PreValidateFunction) -> str:
    return py.INDENT_METHOD + f"def {py.MAGIC_METHODS.get(node.name)}(self, value: Union[BeautifulSoup, Tag]) -> None:"


@converter.pre(TokenType.STRUCT_PART_DOCUMENT)
def tt_part_document(_: PartDocFunction):
    name = py.MAGIC_METHODS.get('__SPLIT_DOC__')
    p_type = "Union[BeautifulSoup, Tag]"
    ret_type = "ResultSet"
    return py.INDENT_METHOD + py.CLS_PART_DOC_HEAD.format(name, p_type, ret_type)


@converter.pre(TokenType.STRUCT_FIELD)
def tt_function(node: StructFieldFunction) -> str:
    name = py.MAGIC_METHODS.get(node.name, node.name)
    if node.ret_type == VariableType.NESTED:
        t_def = find_nested_associated_typedef_by_st_field_fn(node)
        if t_def.struct.type == StructType.LIST:
            t_name = py.TYPE_PREFIX.format(t_def.struct.name)
            type_ = py.TYPE_LIST.format(t_name)
        else:
            type_ = py.TYPE_PREFIX.format(t_def.struct.name)
    else:
        type_ = py.TYPES.get(node.ret_type)
    p_type = "Union[BeautifulSoup, Tag]"
    return py.INDENT_METHOD + py.FN_PARSE.format(name, p_type, type_)


# BS4 API
@converter.pre(TokenType.EXPR_CSS)
def tt_css(node: HtmlCssExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    q = repr(node.query)

    code = E_BS4_CSS.format(nxt, prv, q)
    if have_default_expr(node):
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


@converter.pre(TokenType.EXPR_CSS_ALL)
def tt_css_all(node: HtmlCssAllExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    q = repr(node.query)
    code = E_BS4_CSS_ALL.format(nxt, prv, q)
    if have_default_expr(node):
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


@converter.pre(TokenType.EXPR_TEXT)
def tt_text(node: HtmlTextExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    code = E_BS4_TEXT.format(nxt, prv)
    if have_default_expr(node):
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


@converter.pre(TokenType.EXPR_TEXT_ALL)
def tt_text_all(node: HtmlTextAllExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    code = E_BS4_TEXT_ALL.format(nxt, prv)
    if have_default_expr(node):
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


@converter.pre(TokenType.EXPR_RAW)
def tt_raw(node: HtmlRawExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    code = E_BS4_RAW.format(nxt, prv, prv, prv)
    if have_default_expr(node):
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


@converter.pre(TokenType.EXPR_RAW_ALL)
def tt_raw_all(node: HtmlRawAllExpression) -> str:
    prv, nxt = lr_var_names(variable=node.variable)
    code = E_BS4_RAW_ALL.format(nxt, prv)
    if have_default_expr(node):
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


@converter.pre(TokenType.EXPR_ATTR)
def tt_attr(node: HtmlAttrExpression):
    attr = repr(node.attr)
    prv, nxt = lr_var_names(variable=node.variable)
    code = E_BS4_ATTR.format(nxt, prv, attr, prv, attr, prv, attr)
    if have_default_expr(node):
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


@converter.pre(TokenType.EXPR_ATTR_ALL)
def tt_attr_all(node: HtmlAttrAllExpression):
    attr = repr(node.attr)
    prv, nxt = lr_var_names(variable=node.variable)
    code = E_BS4_ATTR_ALL.format(nxt, attr, attr, attr, prv)
    if have_default_expr(node):
        return py.INDENT_DEFAULT_BODY + code
    return py.INDENT_METHOD_BODY + code


@converter.pre(TokenType.IS_CSS)
def tt_is_css(node: IsCssExpression):
    prv, nxt = lr_var_names(variable=node.variable)
    q = repr(node.query)
    msg = repr(node.msg)
    code = E_BS4_IS_CSS.format(prv, q, msg)
    indent = py.INDENT_DEFAULT_BODY if have_default_expr(node) else py.INDENT_METHOD_BODY
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return indent + code
    return f'{indent}{code}\n{indent}{nxt} = {prv}'


@converter.pre(TokenType.EXPR_XPATH)
def tt_xpath(_: HtmlXpathExpression) -> str:
    raise NotImplementedError("bs4 not support xpath")


@converter.pre(TokenType.EXPR_XPATH_ALL)
def tt_xpath_all(_: HtmlXpathAllExpression) -> str:
    raise NotImplementedError("bs4 not support xpath")


@converter.pre(TokenType.IS_XPATH)
def tt_is_xpath(_: IsXPathExpression):
    raise NotImplementedError("Bs4 not support xpath")
