# TODO: NOT TESTED
from ssc_codegen.ast_ssc import (
    HtmlAttrAllExpression,
    HtmlAttrExpression,
    HtmlCssAllExpression,
    HtmlCssExpression,
    HtmlRawAllExpression,
    HtmlRawExpression,
    HtmlTextAllExpression,
    HtmlTextExpression,
    HtmlXpathAllExpression,
    HtmlXpathExpression,
    IsCssExpression,
    IsXPathExpression,
    ModuleImports,
    PartDocFunction,
    PreValidateFunction,
    StructFieldFunction,
)
from ssc_codegen.tokens import TokenType, VariableType, StructType
from .ast_utils import find_json_struct_instance
from .py_base import BasePyCodeConverter, lr_var_names
from .templates import py
from .templates.template_bindings import TemplateBindings

POST_BINDINGS = TemplateBindings()
POST_BINDINGS[TokenType.IMPORTS] = (
    "from scrapy.selector import Selector, SelectorList\n"
    + "from scrapy.http.response import Response"
)

py.BINDINGS[TokenType.EXPR_CSS] = "{} = {}.css({})"
py.BINDINGS[TokenType.EXPR_CSS_ALL] = "{} = {}.css({})"
py.BINDINGS[TokenType.EXPR_XPATH] = "{} = {}.xpath({})"
py.BINDINGS[TokenType.EXPR_XPATH_ALL] = "{} = {}.xpath({})"
py.BINDINGS[TokenType.EXPR_TEXT] = '{} = {}.css("::text").get()'
py.BINDINGS[TokenType.EXPR_TEXT_ALL] = '{} = {}.css("::text").getall()'
py.BINDINGS[TokenType.EXPR_RAW] = "{} = {}.get()"
py.BINDINGS[TokenType.EXPR_RAW_ALL] = "{} = {}.getall()"
py.BINDINGS[TokenType.EXPR_ATTR] = "{} = {}.css('::attr({})').get()"
py.BINDINGS[TokenType.EXPR_ATTR_ALL] = "{} = {}.css('::attr({})').getall()"
py.BINDINGS[TokenType.IS_CSS] = "assert {}.css({}), {}"
py.BINDINGS[TokenType.IS_XPATH] = "assert {}.xpath({}), {}"

# https://docs.scrapy.org/en/latest/topics/selectors.html#constructing-selectors
POST_BINDINGS[TokenType.STRUCT_INIT] = (
    py.INDENT_METHOD_BODY
    + "if isinstance(document, Response): self._doc = document.selector  # type: ignore\n"
    + py.INDENT_METHOD_BODY
    + "elif isinstance(document, str): self._doc = Selector(document)  # type: ignore\n"
    + py.INDENT_METHOD_BODY
    + "else: self._doc = document\n"
)

converter = BasePyCodeConverter()


@converter.pre(TokenType.STRUCT_INIT)
def tt_init(node) -> str:
    p_type = "Union[str, SelectorList, Selector, Response]"
    return py.INDENT_METHOD + py.BINDINGS[node.kind, p_type]


@converter.post(TokenType.STRUCT_INIT)
def ptt_init(node) -> str:
    return POST_BINDINGS[node.kind]


@converter.post(TokenType.IMPORTS)
def tt_imports(node: ModuleImports) -> str:
    return POST_BINDINGS[node.kind]


@converter.pre(TokenType.STRUCT_PRE_VALIDATE)
def tt_pre_validate(node: PreValidateFunction) -> str:
    p_type = "Union[SelectorList, Selector]"
    name = py.MAGIC_METHODS_NAME.get(node.name)
    return py.INDENT_METHOD + py.BINDINGS[node.kind, name, p_type]


@converter.pre(TokenType.STRUCT_PART_DOCUMENT)
def tt_part_document(node: PartDocFunction):
    name = py.MAGIC_METHODS_NAME.get(node.name)
    p_type = "Union[SelectorList, Selector]"
    ret_type = "SelectorList"
    return py.INDENT_METHOD + py.BINDINGS[node.kind, name, p_type, ret_type]


@converter.pre(TokenType.STRUCT_FIELD)
def tt_function(node: StructFieldFunction) -> str:
    name = py.MAGIC_METHODS_NAME.get(node.name, node.name)
    if node.ret_type == VariableType.NESTED:
        t_def = node.find_associated_typedef()
        ret_type = f"T_{t_def.struct_ref.name}"

        if t_def.struct_ref.type == StructType.LIST:
            ret_type = f"List[{ret_type}]"
    elif node.ret_type == VariableType.JSON:
        instance = find_json_struct_instance(node)
        ret_type = f"J_{instance.__name__}"
        if instance.__IS_ARRAY__:
            ret_type = f"List[{ret_type}]"
    else:
        ret_type = py.TYPES.get(node.ret_type)
    p_type = "Selector"

    return py.INDENT_METHOD + py.BINDINGS[node.kind, name, p_type, ret_type]


# Scrapy API (simular as parsel)
@converter.pre(TokenType.EXPR_CSS)
def tt_css(node: HtmlCssExpression) -> str:
    indent = py.suggest_indent(node)
    q = repr(node.query)
    prv, nxt = lr_var_names(variable=node.variable)

    return indent + py.BINDINGS[node.kind, nxt, prv, q]


@converter.pre(TokenType.EXPR_CSS_ALL)
def tt_css_all(node: HtmlCssAllExpression) -> str:
    indent = py.suggest_indent(node)
    q = repr(node.query)
    prv, nxt = lr_var_names(variable=node.variable)
    return indent + py.BINDINGS[node.kind, nxt, prv, q]


@converter.pre(TokenType.EXPR_XPATH)
def tt_xpath(node: HtmlXpathExpression) -> str:
    indent = py.suggest_indent(node)

    q = repr(node.query)
    prv, nxt = lr_var_names(variable=node.variable)
    return indent + py.BINDINGS[node.kind, nxt, prv, q]


@converter.pre(TokenType.EXPR_XPATH_ALL)
def tt_xpath_all(node: HtmlXpathAllExpression) -> str:
    indent = py.suggest_indent(node)

    q = repr(node.query)
    prv, nxt = lr_var_names(variable=node.variable)
    return indent + py.BINDINGS[node.kind, nxt, prv, q]


@converter.pre(TokenType.EXPR_TEXT)
def tt_text(node: HtmlTextExpression) -> str:
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    return indent + py.BINDINGS[node.kind, nxt, prv]


@converter.pre(TokenType.EXPR_TEXT_ALL)
def tt_text_all(node: HtmlTextAllExpression) -> str:
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    return indent + py.BINDINGS[node.kind, nxt, prv]


@converter.pre(TokenType.EXPR_RAW)
def tt_raw(node: HtmlRawExpression) -> str:
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    return indent + py.BINDINGS[node.kind, nxt, prv]


@converter.pre(TokenType.EXPR_RAW_ALL)
def tt_raw_all(node: HtmlRawAllExpression) -> str:
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    return indent + py.BINDINGS[node.kind, nxt, prv]


@converter.pre(TokenType.EXPR_ATTR)
def tt_attr(node: HtmlAttrExpression) -> str:
    indent = py.suggest_indent(node)

    n = node.attr
    prv, nxt = lr_var_names(variable=node.variable)

    return indent + py.BINDINGS[node.kind, nxt, prv, n]


@converter.pre(TokenType.EXPR_ATTR_ALL)
def tt_attr_all(node: HtmlAttrAllExpression) -> str:
    indent = py.suggest_indent(node)
    n = node.attr
    prv, nxt = lr_var_names(variable=node.variable)
    return indent + py.BINDINGS[node.kind, nxt, prv, n]


@converter.pre(TokenType.IS_CSS)
def tt_is_css(node: IsCssExpression) -> str:
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    q = repr(node.query)
    msg = repr(node.msg)
    code = py.BINDINGS[node.kind, prv, q, msg]
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return indent + code
    return indent + code + "\n" + indent + f"{nxt} = {prv}"


@converter.pre(TokenType.IS_XPATH)
def tt_is_xpath(node: IsXPathExpression) -> str:
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    q = repr(node.query)
    msg = repr(node.msg)
    code = py.BINDINGS[node.kind, prv, q, msg]
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return indent + code
    return indent + code + "\n" + indent + f"{nxt} = {prv}"
