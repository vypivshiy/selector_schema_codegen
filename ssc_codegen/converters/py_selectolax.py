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
from ssc_codegen.ast_.nodes_filter import (
    ExprDocumentFilter,
    FilterDocAttrContains,
    FilterDocAttrEnds,
    FilterDocAttrEqual,
    FilterDocAttrRegex,
    FilterDocAttrStarts,
    FilterDocCss,
    FilterDocHasAttr,
    FilterDocHasRaw,
    FilterDocHasText,
    FilterDocIsRegexRaw,
    FilterDocIsRegexText,
    FilterDocXpath,
)
from ssc_codegen.ast_.nodes_selectors import (
    ExprCssElementRemove,
    ExprMapAttrs,
    ExprMapAttrsAll,
    ExprXpathElementRemove,
)
from ssc_codegen.converters.helpers import (
    is_first_node_cond,
    is_prev_node_atomic_cond,
    prev_next_var,
    have_default_expr,
    is_last_var_no_ret,
    py_get_classvar_hook_or_value,
    py_regex_flags,
)
from ssc_codegen.converters.py_base import (
    BasePyCodeConverter,
    INDENT_DEFAULT_BODY,
    INDENT_METHOD_BODY,
    INDENT_METHOD,
    MAGIC_METHODS,
    get_field_method_ret_type,
)
from ssc_codegen.converters.templates.py_base import IMPORTS_MIN

CONVERTER = BasePyCodeConverter()


@CONVERTER(StructInitMethod.kind)
def pre_init(_node: StructInitMethod) -> str:
    return (
        INDENT_METHOD
        + "def __init__(self, document: Union[str, HTMLParser, Node]) -> None:\n"
        + INDENT_METHOD_BODY
        + "self._document = HTMLParser(document) if isinstance(document, str) else document"
    )


@CONVERTER(StructPreValidateMethod.kind)
def pre_struct_pre_validate(_node: StructPreValidateMethod) -> str:
    return (
        INDENT_METHOD
        + "def _pre_validate(self, v: Union[HTMLParser, Node]) -> None:"
    )


@CONVERTER(StructPartDocMethod.kind)
def pre_struct_part_doc_method(_node: StructPartDocMethod) -> str:
    return (
        INDENT_METHOD
        + "def _split_doc(self, v: Union[HTMLParser, Node]) -> List[Node]:"
    )


@CONVERTER(StructFieldMethod.kind)
def pre_struct_field_method(node: StructFieldMethod) -> str:
    name = node.kwargs["name"]
    type_ = get_field_method_ret_type(node)
    name = MAGIC_METHODS.get(name, name)
    return (
        INDENT_METHOD
        + f"def _parse_{name}(self, v: Union[HTMLParser, Node]) -> {type_}:"
    )


@CONVERTER(ModuleImports.kind)
def pre_imports(_: ModuleImports) -> str:
    # author recommended use lexbor backend instead modest:
    #
    # As of 2024, the preferred backend is Lexbor.
    # The Modest backend is still available for compatibility reasons and the underlying C library
    # that selectolax uses is not maintained anymore.
    # https://github.com/rushter/selectolax?tab=readme-ov-file#available-backends
    return (
        IMPORTS_MIN
        + "from selectolax.lexbor import LexborHTMLParser as HTMLParser, LexborNode as Node"
    )


@CONVERTER(ExprCss.kind)
def pre_css(node: ExprCss) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    query = py_get_classvar_hook_or_value(node, "query")
    return indent + f"{nxt} = {prv}.css_first({query})"


@CONVERTER(ExprCssAll.kind)
def pre_css_all(node: ExprCssAll) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    query = py_get_classvar_hook_or_value(node, "query")
    return indent + f"{nxt} = {prv}.css({query})"


@CONVERTER(ExprGetHtmlAttr.kind)
def pre_html_attr(node: ExprGetHtmlAttr) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    keys = node.kwargs["key"]
    if len(keys) == 1:
        key = keys[0]
        return indent + f"{nxt} = {prv}.attributes[{key!r}]"
    return (
        indent
        + f"{nxt} = [{prv}.attributes[k] for k in {keys} if {prv}.attributes.get(k)]"
    )


@CONVERTER(ExprGetHtmlAttrAll.kind)
def pre_html_attr_all(node: ExprGetHtmlAttrAll) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    keys = node.kwargs["key"]
    if len(keys) == 1:
        key = keys[0]
        return indent + f"{nxt} = [e.attributes[{key!r}] for e in {prv}]"
    return (
        indent
        + f"{nxt} = [e.attributes[k] for e in {prv} for k in {keys} if e.attributes.get(k)]"
    )


@CONVERTER(ExprGetHtmlText.kind)
def pre_html_text(node: ExprGetHtmlText) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    return indent + f"{nxt} = {prv}.text()"


@CONVERTER(ExprGetHtmlTextAll.kind)
def pre_html_text_all(node: ExprGetHtmlTextAll) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    return indent + f"{nxt} = [e.text() for e in {prv}]"


@CONVERTER(ExprGetHtmlRaw.kind)
def pre_html_raw(node: ExprGetHtmlRaw) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    return indent + f"{nxt} = {prv}.html"


@CONVERTER(ExprGetHtmlRawAll.kind)
def pre_html_raw_all(node: ExprGetHtmlRawAll) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    return indent + f"{nxt} = [e.html for e in {prv}]"


@CONVERTER(ExprIsCss.kind)
def pre_is_css(node: ExprIsCss) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    query = py_get_classvar_hook_or_value(node, "query")
    msg = py_get_classvar_hook_or_value(node, "msg")
    invert = node.kwargs["invert"]

    expr = f"{prv}.css_first({query})"
    if invert:
        expr = f"not {expr}"

    expr = indent + f"assert {expr}, {msg}"
    if is_last_var_no_ret(node):
        return expr
    return "\n".join([expr, indent + f"{nxt} = {prv}"])


@CONVERTER(ExprHasAttr.kind)
def pre_has_attr(node: ExprHasAttr) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    key = py_get_classvar_hook_or_value(node, "key")
    msg = py_get_classvar_hook_or_value(node, "msg")
    invert = node.kwargs["invert"]

    expr = f"{prv}.attributes.get({key}, None)"
    if invert:
        expr = f"not ({expr})"
    expr = indent + f"assert {expr}, {msg}"

    if is_last_var_no_ret(node):
        return expr
    return "\n".join([expr, indent + f"{nxt} = {prv}"])


@CONVERTER(ExprListHasAttr.kind)
def pre_list_has_attr(node: ExprListHasAttr) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)

    key = py_get_classvar_hook_or_value(node, "key")
    msg = py_get_classvar_hook_or_value(node, "msg")
    invert = node.kwargs["invert"]

    expr = f"all(i.attributes.get({key!r}, None) for i in {prv})"
    if invert:
        expr = f"not {expr}"

    expr = indent + f"assert {expr}, {msg!r}"
    if is_last_var_no_ret(node):
        return expr
    return "\n".join([expr, indent + f"{nxt} = {prv}"])


@CONVERTER(ExprMapAttrs.kind)
def pre_map_attrs(node: ExprMapAttrs) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    return indent + f"{nxt} = list({prv}.attributes.values())"


@CONVERTER(ExprMapAttrsAll.kind)
def pre_map_attrs_all(node: ExprMapAttrsAll) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    return indent + f"{nxt} = [i for e in {prv} for i in e.attributes.values()]"


@CONVERTER(ExprCssElementRemove.kind)
def pre_css_remove(node: ExprCssElementRemove) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    query = py_get_classvar_hook_or_value(node, "query")
    return (
        indent
        + f"[i.decompose() for i in {prv}.css({query})]\n"
        + indent
        + f"{nxt} = {prv}"
    )


# NOT SUPPORT
@CONVERTER(ExprXpath.kind)
def pre_xpath(_: ExprXpath) -> str:
    raise NotImplementedError("selectolax not support xpath")


@CONVERTER(ExprXpathAll.kind)
def pre_xpath_all(_: ExprXpathAll) -> str:
    raise NotImplementedError("selectolax not support xpath")


@CONVERTER(ExprIsXpath.kind)
def pre_is_xpath(_: ExprIsXpath) -> str:
    raise NotImplementedError("selectolax not support xpath")


@CONVERTER(ExprXpathElementRemove.kind)
def pre_xpath_remove(_: ExprXpathElementRemove) -> str:
    raise NotImplementedError("selectolax not support xpath")


# document filters


@CONVERTER(ExprDocumentFilter.kind, post_callback=lambda _: "]")
def pre_expr_doc_filter(node: ExprDocumentFilter) -> str:
    indent = (
        INDENT_DEFAULT_BODY if have_default_expr(node) else INDENT_METHOD_BODY
    )
    prv, nxt = prev_next_var(node)
    return indent + f"{nxt} = [e for e in {prv} if "


@CONVERTER(FilterDocCss.kind)
def pre_doc_filter_css(node: FilterDocCss) -> str:
    query = node.kwargs["query"]
    expr = f"bool(e.css_first({query!r}))"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return "and " + expr
    return expr


@CONVERTER(FilterDocHasAttr.kind)
def pre_doc_filter_has_attr(node: FilterDocHasAttr) -> str:
    keys = node.kwargs["keys"]
    if len(keys) == 1:
        expr = f"{keys[0]!r} in e.attributes"
    else:
        expr = f"any(i in e.attributes for i in {keys})"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return "and " + expr
    return expr


@CONVERTER(FilterDocAttrEqual.kind)
def pre_doc_filter_attr_eq(node: FilterDocAttrEqual) -> str:
    key, values = node.unpack_args()
    if len(values) == 1:
        expr = f"e.attributes[{key!r}] == {values[0]!r}"
    else:
        expr = f"e.attributes[{key!r}] in {values}"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return "and " + expr
    return expr


@CONVERTER(FilterDocAttrContains.kind)
def pre_doc_filter_attr_contains(node: FilterDocAttrContains) -> str:
    key, values = node.unpack_args()
    if len(values) == 1:
        expr = f"{values[0]!r} in e.attributes[{key!r}]"
    else:
        expr = f"any(i in e.attributes[{key!r}] for i in {values})"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return "and " + expr
    return expr


@CONVERTER(FilterDocAttrStarts.kind)
def pre_doc_filter_attr_starts(node: FilterDocAttrStarts) -> str:
    key, values = node.unpack_args()
    if len(values) == 1:
        expr = f"e.attributes[{key!r}].startswith({values[0]!r})"
    else:
        # str.startswith() arg allow tuple[str, ...]
        expr = f"e.attributes[{key!r}].startswith({values})"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return "and " + expr
    return expr


@CONVERTER(FilterDocAttrEnds.kind)
def pre_doc_filter_attr_ends(node: FilterDocAttrEnds) -> str:
    key, values = node.unpack_args()
    if len(values) == 1:
        expr = f"e.attributes[{key!r}].endswith({values[0]!r})"
    else:
        # str.endswith() arg allow tuple[str, ...]
        expr = f"e.attributes[{key!r}].endswith({values})"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return "and " + expr
    return expr


@CONVERTER(FilterDocAttrRegex.kind)
def pre_doc_filter_attr_re(node: FilterDocAttrRegex) -> str:
    key, pattern, ignore_case = node.unpack_args()
    flags = py_regex_flags(ignore_case)
    if flags:
        expr = f"re.search({pattern!r}, e.attributes[{key!r}], {flags})"
    else:
        expr = f"re.search({pattern!r}, e.attributes[{key!r}], ''))"
    expr = f"bool({expr})"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return "and " + expr
    return expr


@CONVERTER(FilterDocIsRegexText.kind)
def pre_doc_filter_is_regex_text(node: FilterDocIsRegexText) -> str:
    pattern, ignore_case = node.unpack_args()

    flags = py_regex_flags(ignore_case)
    if flags:
        expr = f"re.search({pattern!r}, e.text(), {flags})"
    else:
        expr = f"re.search({pattern!r}, e.text())"
    expr = f"bool({expr})"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return "and " + expr
    return expr


@CONVERTER(FilterDocIsRegexRaw.kind)
def pre_doc_filter_is_regex_raw(node: FilterDocIsRegexRaw) -> str:
    pattern, ignore_case = node.unpack_args()

    flags = py_regex_flags(ignore_case)
    if flags:
        expr = f"re.search({pattern!r}, e.html, {flags})"
    else:
        expr = f"re.search({pattern!r}, e.html)"
    expr = f"bool({expr})"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return "and " + expr
    return expr


@CONVERTER(FilterDocHasText.kind)
def pre_doc_filter_has_text(node: FilterDocHasText) -> str:
    values = node.kwargs["values"]
    if len(values) == 1:
        expr = f"{values[0]!r} in e.text()"
    else:
        expr = f"any(i in e.text()) for i in {values})"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return "and " + expr
    return expr


@CONVERTER(FilterDocHasRaw.kind)
def pre_doc_filter_has_raw(node: FilterDocHasText) -> str:
    values = node.kwargs["values"]
    if len(values) == 1:
        expr = f"{values[0]!r} in (e.html or '')"
    else:
        expr = f"any(i in (e.html or '') for i in {values})"
    if not is_first_node_cond(node) and is_prev_node_atomic_cond(node):
        return "and " + expr
    return expr


# not supported XPATH
@CONVERTER(FilterDocXpath.kind)
def pre_xpath_filter(node: FilterDocXpath) -> str:
    raise NotImplementedError("selectolax not support xpath")
