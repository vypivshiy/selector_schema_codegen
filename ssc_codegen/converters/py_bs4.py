from .py_base import BasePyCodeConverter, lr_var_names
from .templates import py
from .templates.utils import TemplateBindings
from ..ast_ssc import (
    ModuleImports,
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
    PreValidateFunction,
)
from ..tokens import TokenType, StructType, VariableType

POST_BINDINGS = TemplateBindings()
POST_BINDINGS[TokenType.STRUCT_INIT] = (
    "self._doc=BeautifulSoup(document, 'lxml')"
    + " if isinstance(document, str) else document"
)
POST_BINDINGS[TokenType.IMPORTS] = (
    "from bs4 import BeautifulSoup, ResultSet, Tag  # noqa (for typing)"
)

BS4_INIT = "self._doc=BeautifulSoup(document, 'lxml') if isinstance(document, str) else document"
BS4_IMPORTS = (
    "from bs4 import BeautifulSoup, ResultSet, Tag  # noqa (for typing)"
)
# extends
py.BINDINGS[TokenType.EXPR_CSS] = "{} = {}.select_one({})"
py.BINDINGS[TokenType.EXPR_CSS_ALL] = "{} = {}.select({})"
py.BINDINGS[TokenType.EXPR_TEXT] = "{} = {}.text"
py.BINDINGS[TokenType.EXPR_TEXT_ALL] = "{} = [e.text for e in {}]"

# bs4 auto convert multiattr values to list
# most libs return attr value as string, remove this feature
py.BINDINGS[TokenType.EXPR_ATTR] = (
    "{} = {}[{}] if isinstance({}[{}], str) else ' '.join({}[{}])"
)
py.BINDINGS[TokenType.EXPR_ATTR_ALL] = (
    "{} = [e[{}] if isinstance(e[{}], str) else ' '.join(e[{}]) for e in {}]"
)

# maybe returns None
py.BINDINGS[TokenType.EXPR_RAW] = "{} = str({}) if {} else {}"
# maybe returns None
py.BINDINGS[TokenType.EXPR_RAW_ALL] = "{} = [e for e in {} if e]"

py.BINDINGS[TokenType.IS_CSS] = "assert {}.select_one({}), {}"

converter = BasePyCodeConverter()


@converter.pre(TokenType.STRUCT_INIT)
def tt_init(node) -> str:
    return (
        py.INDENT_METHOD
        + py.BINDINGS[node.kind, "Union[str, BeautifulSoup, Tag]"]
    )


@converter.post(TokenType.STRUCT_INIT)
def tt_init(node):
    return py.INDENT_METHOD_BODY + POST_BINDINGS[node.kind]


@converter.post(TokenType.IMPORTS)
def tt_imports(node: ModuleImports) -> str:
    return POST_BINDINGS[node.kind]


@converter.pre(TokenType.STRUCT_PRE_VALIDATE)
def tt_pre_validate(node: PreValidateFunction) -> str:
    name = py.MAGIC_METHODS_NAME.get(node.name)
    p_type = "Union[BeautifulSoup, Tag]"
    return py.INDENT_METHOD + py.BINDINGS[node.kind, name, p_type]


@converter.pre(TokenType.STRUCT_PART_DOCUMENT)
def tt_part_document(node: PartDocFunction):
    name = py.MAGIC_METHODS_NAME.get("__SPLIT_DOC__")
    p_type = "Union[BeautifulSoup, Tag]"
    ret_type = "ResultSet"
    return py.INDENT_METHOD + py.BINDINGS[node.kind, name, p_type, ret_type]


@converter.pre(TokenType.STRUCT_FIELD)
def tt_function(node: StructFieldFunction) -> str:
    name = py.MAGIC_METHODS_NAME.get(node.name, node.name)
    if node.ret_type == VariableType.NESTED:
        t_def = node.find_associated_typedef()
        if t_def.struct_ref.type == StructType.LIST:
            t_name = py.TYPE_PREFIX.format(t_def.struct_ref.name)
            type_ = py.TYPE_LIST.format(t_name)
        else:
            type_ = py.TYPE_PREFIX.format(t_def.struct_ref.name)
    else:
        type_ = py.TYPES.get(node.ret_type)
    p_type = "Union[BeautifulSoup, Tag]"
    return py.INDENT_METHOD + py.BINDINGS[node.kind, name, p_type, type_]


# BS4 API
@converter.pre(TokenType.EXPR_CSS)
def tt_css(node: HtmlCssExpression) -> str:
    indent = py.suggest_indent(node)
    prv, nxt = lr_var_names(variable=node.variable)
    q = repr(node.query)

    return indent + py.BINDINGS[node.kind, nxt, prv, q]


@converter.pre(TokenType.EXPR_CSS_ALL)
def tt_css_all(node: HtmlCssAllExpression) -> str:
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    q = repr(node.query)
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
    return indent + py.BINDINGS[node.kind, nxt, prv, prv, prv]


@converter.pre(TokenType.EXPR_RAW_ALL)
def tt_raw_all(node: HtmlRawAllExpression) -> str:
    indent = py.suggest_indent(node)

    prv, nxt = lr_var_names(variable=node.variable)
    return indent + py.BINDINGS[node.kind, nxt, prv]


@converter.pre(TokenType.EXPR_ATTR)
def tt_attr(node: HtmlAttrExpression):
    indent = py.suggest_indent(node)

    attr = repr(node.attr)
    prv, nxt = lr_var_names(variable=node.variable)
    return indent + py.BINDINGS[node.kind, nxt, prv, attr, prv, attr, prv, attr]


@converter.pre(TokenType.EXPR_ATTR_ALL)
def tt_attr_all(node: HtmlAttrAllExpression):
    indent = py.suggest_indent(node)

    attr = repr(node.attr)
    prv, nxt = lr_var_names(variable=node.variable)
    return indent + py.BINDINGS[node.kind, nxt, attr, attr, attr, prv]


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


@converter.pre(TokenType.EXPR_XPATH)
def tt_xpath(_: HtmlXpathExpression) -> str:
    raise NotImplementedError("bs4 not support xpath")


@converter.pre(TokenType.EXPR_XPATH_ALL)
def tt_xpath_all(_: HtmlXpathAllExpression) -> str:
    raise NotImplementedError("bs4 not support xpath")


@converter.pre(TokenType.IS_XPATH)
def tt_is_xpath(_: IsXPathExpression):
    raise NotImplementedError("Bs4 not support xpath")
