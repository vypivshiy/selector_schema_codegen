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
from .py_base import BasePyCodeConverter, lr_var_names
from .templates import py
from .templates.template_bindings import TemplateBindings
from .ast_utils import find_json_struct_instance

POST_BINDINGS = TemplateBindings()
POST_BINDINGS[TokenType.IMPORTS] = (
    "from selectolax.lexbor import LexborHTMLParser as HTMLParser, Node"
)
POST_BINDINGS[TokenType.STRUCT_INIT] = (
    "self._doc=HTMLParser(document) if isinstance(document, str) else document"
)

py.BINDINGS[TokenType.EXPR_CSS] = "{} = {}.css_first({})"
py.BINDINGS[TokenType.EXPR_CSS_ALL] = "{} = {}.css({})"
py.BINDINGS[TokenType.EXPR_TEXT] = "{} = {}.text()"
py.BINDINGS[TokenType.EXPR_TEXT_ALL] = "{} = [e.text() for e in {}]"
py.BINDINGS[TokenType.EXPR_RAW] = "{} = {}.html"
py.BINDINGS[TokenType.EXPR_RAW_ALL] = "{} = [e.html for e in {}]"
py.BINDINGS[TokenType.EXPR_ATTR] = "{} = {}.attributes[{}]"
py.BINDINGS[TokenType.EXPR_ATTR_ALL] = "{} = [e.attributes[{}] for e in {}]"
py.BINDINGS[TokenType.IS_CSS] = "assert {}.css_first({}), {}"

converter = BasePyCodeConverter()


@converter.pre(TokenType.STRUCT_INIT)
def tt_init(node) -> str:
    p_type = "Union[str, HTMLParser, Node]"
    return py.INDENT_METHOD + py.BINDINGS[node.kind, p_type]


@converter.post(TokenType.STRUCT_INIT)
def tt_init_post(node) -> str:
    return py.INDENT_METHOD_BODY + POST_BINDINGS[node.kind]


@converter.post(TokenType.IMPORTS)
def tt_imports(node: ModuleImports) -> str:
    return POST_BINDINGS[node.kind]


@converter.pre(TokenType.STRUCT_PRE_VALIDATE)
def tt_pre_validate(node: PreValidateFunction) -> str:
    p_type = "Union[HTMLParser, Node]"
    name = py.MAGIC_METHODS_NAME.get(node.name)
    return py.INDENT_METHOD + py.BINDINGS[node.kind, name, p_type]


@converter.pre(TokenType.STRUCT_PART_DOCUMENT)
def tt_part_document(node: PartDocFunction) -> str:
    name = py.MAGIC_METHODS_NAME.get(node.name)
    return (
        py.INDENT_METHOD
        + py.BINDINGS[
            node.kind, name, "Union[str, HTMLParser, Node]", "List[Node]"
        ]
    )


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
    p_type = "Union[str, HTMLParser, Node]"
    return py.INDENT_METHOD + py.BINDINGS[node.kind, name, p_type, ret_type]


# selectolax API
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

    attr = repr(node.attr)
    prv, nxt = lr_var_names(variable=node.variable)
    return indent + py.BINDINGS[node.kind, nxt, prv, attr]


@converter.pre(TokenType.EXPR_ATTR_ALL)
def tt_attr_all(node: HtmlAttrAllExpression) -> str:
    indent = py.suggest_indent(node)

    attr = repr(node.attr)
    prv, nxt = lr_var_names(variable=node.variable)
    return indent + py.BINDINGS[node.kind, nxt, attr, prv]


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


@converter.pre(TokenType.EXPR_XPATH)
def tt_xpath(_: HtmlXpathExpression) -> str:
    raise NotImplementedError("Selectolax not support xpath")


@converter.pre(TokenType.EXPR_XPATH_ALL)
def tt_xpath_all(_: HtmlXpathAllExpression) -> str:
    raise NotImplementedError("Selectolax not support xpath")


@converter.pre(TokenType.IS_XPATH)
def tt_is_xpath(_: IsXPathExpression):
    raise NotImplementedError("Selectolax not support xpath")
