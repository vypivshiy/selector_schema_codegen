from .ast_utils import find_json_struct_instance
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
    StructInit,
)
from ssc_codegen.tokens import TokenType, VariableType, StructType
from .py_base import BasePyCodeConverter, lr_var_names
from .templates import py
from .templates.template_bindings import TemplateBindings

# setup converter
BINDINGS_POST = TemplateBindings()
BINDINGS_POST[TokenType.STRUCT_INIT] = (
    "self._doc=Selector(document) if isinstance(document, str) else document"
)
BINDINGS_POST[TokenType.IMPORTS] = (
    "from parsel import Selector, SelectorList\nfrom parsel.selector import _SelectorType  # noqa"
)

# extend default bindings
py.BINDINGS[TokenType.EXPR_CSS] = "{} = {}.css({})"
py.BINDINGS[TokenType.EXPR_CSS_ALL] = "{} = {}.css({})"
py.BINDINGS[TokenType.EXPR_XPATH] = "{} = {}.xpath({})"
py.BINDINGS[TokenType.EXPR_XPATH_ALL] = "{} = {}.xpath({})"

# parsel get() method returns single match instead full text element scope
py.BINDINGS[TokenType.EXPR_TEXT] = '{} = "".join({}.css("::text").getall())'
py.BINDINGS[TokenType.EXPR_TEXT_ALL] = '{} = {}.css("::text").getall()'
py.BINDINGS[TokenType.EXPR_RAW] = "{} = {}.get()"
py.BINDINGS[TokenType.EXPR_RAW_ALL] = "{} = {}.getall()"
py.BINDINGS[TokenType.EXPR_ATTR] = "{} = {}.attrib[{}]"
py.BINDINGS[TokenType.EXPR_ATTR_ALL] = "{} = [i.attrib[{}] for i in {}]"
py.BINDINGS[TokenType.IS_CSS] = "assert {}.css({}), {}"
py.BINDINGS[TokenType.IS_XPATH] = "assert {}.xpath({}), {}"

converter = BasePyCodeConverter()


@converter.pre(TokenType.STRUCT_INIT)
def tt_init(node: StructInit) -> str:
    p_type = "Union[str, _SelectorType]"
    return py.INDENT_METHOD + py.BINDINGS[node.kind, p_type]


@converter.post(TokenType.STRUCT_INIT)
def tt_init_post(node: StructInit) -> str:
    return py.INDENT_METHOD_BODY + BINDINGS_POST[node.kind]


@converter.post(TokenType.IMPORTS)
def tt_imports_post(node: ModuleImports) -> str:
    return BINDINGS_POST[node.kind]


@converter.pre(TokenType.STRUCT_PRE_VALIDATE)
def tt_pre_validate(node: PreValidateFunction) -> str:
    name = py.MAGIC_METHODS_NAME.get(node.name)
    p_type = "Union[_SelectorType]"
    return py.INDENT_METHOD + py.BINDINGS[node.kind, name, p_type]


@converter.pre(TokenType.STRUCT_PART_DOCUMENT)
def tt_part_document(node: PartDocFunction) -> str:
    p_type = "_SelectorType"
    ret_type = "SelectorList"
    name = py.MAGIC_METHODS_NAME.get(node.name)
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
        instance = find_json_struct_instance(node)  # noqa
        ret_type = f"J_{instance.__name__}"
        if instance.__IS_ARRAY__:
            ret_type = f"List[{ret_type}]"
    else:
        ret_type = py.TYPES.get(node.ret_type)
    p_type = "Selector"
    return py.INDENT_METHOD + py.BINDINGS[node.kind, name, p_type, ret_type]


# PARSEL API
@converter.pre(TokenType.EXPR_CSS)
def tt_css(node: HtmlCssExpression) -> str:
    indent = py.suggest_indent(node)

    q = repr(node.query)
    prv, nxt = lr_var_names(variable=node.variable)
    code = py.BINDINGS[node.kind, nxt, prv, q]
    return indent + code


@converter.pre(TokenType.EXPR_CSS_ALL)
def tt_css_all(node: HtmlCssAllExpression) -> str:
    indent = py.suggest_indent(node)

    q = repr(node.query)
    prv, nxt = lr_var_names(variable=node.variable)
    code = py.BINDINGS[node.kind, nxt, prv, q]
    return indent + code


@converter.pre(TokenType.EXPR_XPATH)
def tt_xpath(node: HtmlXpathExpression) -> str:
    indent = py.suggest_indent(node)

    q = repr(node.query)
    prv, nxt = lr_var_names(variable=node.variable)
    code = py.BINDINGS[node.kind, nxt, prv, q]
    return indent + code


@converter.pre(TokenType.EXPR_XPATH_ALL)
def tt_xpath_all(node: HtmlXpathAllExpression) -> str:
    indent = py.suggest_indent(node)
    q = repr(node.query)
    prv, nxt = lr_var_names(variable=node.variable)
    code = py.BINDINGS[node.kind, nxt, prv, q]
    return indent + code


@converter.pre(TokenType.EXPR_TEXT)
def tt_text(node: HtmlTextExpression) -> str:
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    code = py.BINDINGS[node.kind, nxt, prv]
    return indent + code


@converter.pre(TokenType.EXPR_TEXT_ALL)
def tt_text_all(node: HtmlTextAllExpression) -> str:
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    code = py.BINDINGS[node.kind, nxt, prv]
    return indent + code


@converter.pre(TokenType.EXPR_RAW)
def tt_raw(node: HtmlRawExpression) -> str:
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    code = py.BINDINGS[node.kind, nxt, prv]
    return indent + code


@converter.pre(TokenType.EXPR_RAW_ALL)
def tt_raw_all(node: HtmlRawAllExpression) -> str:
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    code = py.BINDINGS[node.kind, nxt, prv]
    return indent + code


@converter.pre(TokenType.EXPR_ATTR)
def tt_attr(node: HtmlAttrExpression):
    indent = py.suggest_indent(node)

    n = repr(node.attr)
    prv, nxt = lr_var_names(variable=node.variable)
    code = py.BINDINGS[node.kind, nxt, prv, n]
    return indent + code


@converter.pre(TokenType.EXPR_ATTR_ALL)
def tt_attr_all(node: HtmlAttrAllExpression):
    indent = py.suggest_indent(node)

    n = repr(node.attr)
    prv, nxt = lr_var_names(variable=node.variable)
    code = py.BINDINGS[node.kind, nxt, n, prv]
    return indent + code


@converter.pre(TokenType.IS_CSS)
def tt_is_css(node: IsCssExpression):
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    q = repr(node.query)
    msg = repr(node.msg)
    code = py.BINDINGS[node.kind, prv, q, msg]
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return indent + code
    return indent + code + "\n" + indent + f"{nxt} = {prv}"


@converter.pre(TokenType.IS_XPATH)
def tt_is_xpath(node: IsXPathExpression):
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    q = repr(node.query)
    msg = repr(node.msg)
    code = py.BINDINGS[node.kind, prv, q, msg]
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return indent + code
    return indent + code + "\n" + indent + f"{nxt} = {prv}"
