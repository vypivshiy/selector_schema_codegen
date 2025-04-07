from ssc_codegen.ast_ import (
    ExprCss,
    ExprCssAll,
    ModuleImports,
    ExprXpathAll,
    ExprXpath,
    ExprIsXpath,
    ExprGetHtmlAttr,
    ExprGetHtmlAttrAll,
    ExprGetHtmlText,
    ExprGetHtmlTextAll,
    ExprGetHtmlRaw,
    ExprGetHtmlRawAll,
    ExprIsCss,
    StructInitMethod,
    StructFieldMethod,
    StructPreValidateMethod,
    StructPartDocMethod,
    ExprListHasAttr,
    ExprHasAttr,
)
from ssc_codegen.converters.helpers import (
    prev_next_var,
    have_default_expr,
    is_last_var_no_ret,
)
from ssc_codegen.converters.py_base import (
    BasePyCodeConverter,
    INDENT_DEFAULT_BODY,
    INDENT_METHOD_BODY,
    INDENT_METHOD,
    MAGIC_METHODS,
    get_field_method_ret_type,
)

CONVERTER = BasePyCodeConverter()


@CONVERTER(StructInitMethod.kind)
def pre_init(_node: StructInitMethod) -> str:
    return (
        INDENT_METHOD
        + "def __init__(self, document: Union[str, Selector, SelectorList]) -> None:\n"
        + INDENT_METHOD_BODY
        + "self._document = Selector(document) if isinstance(document, str) else document"
    )


@CONVERTER(StructPreValidateMethod.kind)
def pre_struct_pre_validate(_node: StructPreValidateMethod) -> str:
    return (
        INDENT_METHOD
        + "def _pre_validate(self, v: Union[Selector, SelectorList]) -> None:"
    )


@CONVERTER(StructPartDocMethod.kind)
def pre_struct_part_doc_method(_node: StructPartDocMethod) -> str:
    return (
        INDENT_METHOD
        + "def _split_doc(self, v: Union[Selector, SelectorList]) -> SelectorList:"
    )


@CONVERTER(StructFieldMethod.kind)
def pre_struct_field_method(node: StructFieldMethod) -> str:
    name = node.kwargs["name"]
    type_ = get_field_method_ret_type(node)
    name = MAGIC_METHODS.get(name, name)
    return (
        INDENT_METHOD
        + f"def _parse_{name}(self, v: Union[Selector, SelectorList]) -> {type_}:"
    )


@CONVERTER.post(ModuleImports.kind)
def post_imports(_: ModuleImports) -> str:
    return """from parsel import Selector, SelectorList"""


@CONVERTER(ExprCss.kind)
def pre_css(node: ExprCss) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    query = node.kwargs["query"]
    return indent + f"{nxt} = {prv}.css({query!r})"


@CONVERTER(ExprCssAll.kind)
def pre_css_all(node: ExprCssAll) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    query = node.kwargs["query"]
    return indent + f"{nxt} = {prv}.css({query!r})"


@CONVERTER(ExprXpath.kind)
def pre_xpath(node: ExprXpath) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    query = node.kwargs["query"]
    return indent + f"{nxt} = {prv}.xpath({query!r})"


@CONVERTER(ExprXpathAll.kind)
def pre_xpath_all(node: ExprXpathAll) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    query = node.kwargs["query"]
    return indent + f"{nxt} = {prv}.xpath({query!r})"


@CONVERTER(ExprGetHtmlAttr.kind)
def pre_html_attr(node: ExprGetHtmlAttr) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    key = node.kwargs["key"]
    return indent + f"{nxt} = {prv}.attrib[{key!r}]"


@CONVERTER(ExprGetHtmlAttrAll.kind)
def pre_html_attr_all(node: ExprGetHtmlAttrAll) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    key = node.kwargs["key"]
    return indent + f"{nxt} = [e.attrib[{key!r}] for e in {prv}]"


@CONVERTER(ExprGetHtmlText.kind)
def pre_html_text(node: ExprGetHtmlText) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    return indent + f'{nxt} = "".join({prv}.css("::text").getall())'


@CONVERTER(ExprGetHtmlTextAll.kind)
def pre_html_text_all(node: ExprGetHtmlTextAll) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    return indent + f'{nxt} = {prv}.css("::text").getall()'


@CONVERTER(ExprGetHtmlRaw.kind)
def pre_html_raw(node: ExprGetHtmlRaw) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    return indent + f"{nxt} = {prv}.get()"


@CONVERTER(ExprGetHtmlRawAll.kind)
def pre_html_raw_all(node: ExprGetHtmlRawAll) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    return indent + f"{nxt} = {prv}.getall()"


@CONVERTER(ExprIsCss.kind)
def pre_is_css(node: ExprIsCss) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    query, msg = node.unpack_args()
    expr = indent + f"assert {prv}.css({query!r}), {msg!r}"
    if is_last_var_no_ret(node):
        return expr
    return expr + "\n" + indent + f"{nxt} = {prv}"


@CONVERTER(ExprIsXpath.kind)
def pre_is_xpath(node: ExprIsXpath) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    query, msg = node.unpack_args()
    expr = indent + f"assert {prv}.xpath({query!r}), {msg!r}"
    if is_last_var_no_ret(node):
        return expr
    return expr + "\n" + indent + f"{nxt} = {prv}"


@CONVERTER(ExprHasAttr.kind)
def pre_has_attr(node: ExprHasAttr) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    key, msg = node.unpack_args()
    expr = indent + f"assert {prv}.attrib.get({key!r}, None), {msg!r}"
    if is_last_var_no_ret(node):
        return expr
    return expr + "\n" + indent + f"{nxt} = {prv}"


@CONVERTER(ExprListHasAttr.kind)
def pre_list_has_attr(node: ExprListHasAttr) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    key, msg = node.unpack_args()
    expr = (
        indent
        + f"assert all(i.attrib.get({key!r}, None) for i in {prv}), {msg!r}"
    )
    if is_last_var_no_ret(node):
        return expr
    return expr + "\n" + indent + f"{nxt} = {prv}"
