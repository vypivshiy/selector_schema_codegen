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
    NestedExpression,
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
def tt_init_post(node):
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
    p_type = "Union[BeautifulSoup, Tag]"
    return py.INDENT_METHOD + py.BINDINGS[node.kind, name, p_type, ret_type]


# BS4 API
@converter.pre(TokenType.EXPR_NESTED)
def tt_nested(node: NestedExpression) -> str:
    # create new BeautifulSoup instance avoid missing parse data
    # from Tag object in many-nested schemas cases
    prv, nxt = lr_var_names(variable=node.variable)
    if node.have_default_expr():
        indent = py.INDENT_DEFAULT_BODY
    else:
        indent = py.INDENT_METHOD_BODY
    return indent + py.BINDINGS[node.kind, nxt, node.schema, f"str({prv})"]


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
