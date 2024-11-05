from .base import BaseCodeConverter, left_right_var_names
from .utils import to_upper_camel_case, wrap_backtick
from ..ast_ssc import (
    StructParser,
    ModuleImports,
    PreValidateFunction,
    StructFieldFunction,
    Docstring,
    StartParseFunction,
    DefaultValueWrapper,
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
    FormatExpression,
    MapFormatExpression,
    TrimExpression,
    MapTrimExpression,
    LTrimExpression,
    MapLTrimExpression,
    RTrimExpression,
    MapRTrimExpression,
    ReplaceExpression,
    MapReplaceExpression,
    SplitExpression,
    NestedExpression,
    RegexExpression,
    RegexSubExpression,
    MapRegexSubExpression,
    RegexAllExpression,
    ReturnExpression,
    NoReturnExpression,
    TypeDef,
    IndexDocumentExpression,
    IndexStringExpression,
    JoinExpression,
    IsCssExpression,
    IsXPathExpression,
    IsEqualExpression,
    IsContainsExpression,
    IsRegexMatchExpression,
    IsNotEqualExpression,
)
from ..consts import RESERVED_METHODS
from ..tokens import TokenType, StructType, VariableType

converter = BaseCodeConverter()

TYPES = {
    VariableType.STRING: "str",
    VariableType.LIST_STRING: "List[str]",
    VariableType.OPTIONAL_STRING: "Optional[str]",
    VariableType.OPTIONAL_LIST_STRING: "Optional[List[str]]",
}

MAGIC_METHODS = {
    "__KEY__": "key",
    "__VALUE__": "value",
    "__ITEM__": "item",
    "__PRE_VALIDATE__": "_preValidate",
    "__SPLIT_DOC__": "_splitDoc",
    "__START_PARSE__": "parse",
}


@converter.pre(TokenType.TYPEDEF)
def tt_typedef(_: TypeDef):
    # pure js didn't have typing features
    return ""


# pure js API
@converter.pre(TokenType.STRUCT)
def tt_struct(node: StructParser) -> str:
    return f"class {node.name} " + "{"


@converter.post(TokenType.STRUCT)
def tt_struct(_: StructParser) -> str:
    return " }"


@converter.pre(TokenType.STRUCT_INIT)
def tt_init(_) -> str:
    return "constructor(doc) { this._doc = typeof document === 'string' ? new DOMParser().parseFromString(doc, 'text/html') : document; }"


@converter.pre(TokenType.DOCSTRING)
def tt_docstring(node: Docstring) -> str:
    if node.value:
        docstr_start = "/**"
        docstr_parts = "\n".join("* " + line for line in node.value.split("\n"))
        docstr_end = "*/"
        return docstr_start + "\n" + docstr_parts + "\n" + docstr_end
    return ""


@converter.pre(TokenType.IMPORTS)
def tt_imports(_: ModuleImports) -> str:
    # pure js dont need imports
    return ""


@converter.pre(TokenType.EXPR_RETURN)
def tt_ret(node: ReturnExpression) -> str:
    _, nxt = left_right_var_names("value", node.variable)
    return f"return {nxt}; "


@converter.pre(TokenType.EXPR_NO_RETURN)
def tt_no_ret(_: NoReturnExpression) -> str:
    return "return null; "


@converter.pre(TokenType.EXPR_NESTED)
def tt_nested(node: NestedExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    return f"let {nxt} = (new {node.schema}({prv})).parse(); "


@converter.pre(TokenType.STRUCT_PRE_VALIDATE)
def tt_pre_validate(node: PreValidateFunction) -> str:
    return f"{MAGIC_METHODS.get(node.name)}(value) " + "{"


@converter.post(TokenType.STRUCT_PRE_VALIDATE)
def tt_pre_validate(_: PreValidateFunction) -> str:
    return " }"


@converter.pre(TokenType.STRUCT_PART_DOCUMENT)
def tt_part_document(node: PartDocFunction):
    return f"{MAGIC_METHODS.get('__SPLIT_DOC__')}(value) " + "{"


@converter.post(TokenType.STRUCT_PART_DOCUMENT)
def tt_part_document(_: PartDocFunction) -> str:
    return " }"


@converter.pre(TokenType.STRUCT_FIELD)
def tt_function(node: StructFieldFunction) -> str:
    name = MAGIC_METHODS.get(node.name, node.name)
    name = to_upper_camel_case(name)
    return f"_parse{name}(value) " + "{"


@converter.post(TokenType.STRUCT_FIELD)
def tt_function(_: StructFieldFunction) -> str:
    return " }"


@converter.pre(TokenType.STRUCT_PARSE_START)
def tt_start_parse(node: StartParseFunction) -> str:
    return f"{MAGIC_METHODS.get(node.name)}() " + "{"


@converter.post(TokenType.STRUCT_PARSE_START)
def tt_start_parse(node: StartParseFunction):
    code = ""
    if any(f.name == "__PRE_VALIDATE__" for f in node.body):
        n = MAGIC_METHODS.get("__PRE_VALIDATE__")
        code += f"this.{n}(this._doc); "

    match node.type:
        case StructType.ITEM:
            body = ", ".join(
                [
                    f'"{f.name}": this._parse{to_upper_camel_case(f.name)}(self._doc)'
                    for f in node.body
                    if f.name not in RESERVED_METHODS
                ]
            )
            body = "{" + body + "};"
        case StructType.LIST:
            map_body = (
                "{"
                + ", ".join(
                    [
                        f'"{f.name}": this._parse{to_upper_camel_case(f.name)}(e);'
                        for f in node.body
                        if f.name not in RESERVED_METHODS
                    ]
                )
                + "}"
            )
            n = MAGIC_METHODS.get("__SPLIT_DOC__")
            body = f"this.{n}(this._doc).map(e => {map_body});"
        case StructType.DICT:
            key_m = MAGIC_METHODS.get("__KEY__")
            value_m = to_upper_camel_case(MAGIC_METHODS.get("__VALUE__"))
            part_m = MAGIC_METHODS.get("__SPLIT_DOC__")
            body = f"this.{part_m}.reduce((acc, e) => "
            body += (
                "{"
                + f"acc[this._parse{key_m}(e)] = this._parse{value_m}; return acc;"
                + "});"
            )
        case StructType.FLAT_LIST:
            item_m = to_upper_camel_case(MAGIC_METHODS.get("__ITEM__"))
            part_m = MAGIC_METHODS.get("__SPLIT_DOC__")
            body = f"this.{part_m}.map(e => this._parse{item_m}(e)); "
        case _:
            raise NotImplementedError("Unknown struct type")
    return code + f"return {body}" + "}"


@converter.pre(TokenType.EXPR_DEFAULT)
def tt_default(_: DefaultValueWrapper) -> str:
    return "try {"


@converter.post(TokenType.EXPR_DEFAULT)
def tt_default(node: DefaultValueWrapper) -> str:
    val = repr(node.value) if isinstance(node.value, str) else "null"
    return "} catch(Error) {" + f"return {val};" + "}"


@converter.pre(TokenType.EXPR_STRING_FORMAT)
def tt_string_format(node: FormatExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    template = node.fmt.replace("{{}}", f"${prv}")
    return f"let {nxt}" + " = " + wrap_backtick(template) + "; "


@converter.pre(TokenType.EXPR_LIST_STRING_FORMAT)
def tt_string_format_all(node: MapFormatExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    template = node.fmt.replace("{{}}", "${e}")
    f"{prv}.map(e => {template})"
    return f"let {nxt}" + " = " + f"{prv}.map(e => {template}); "


@converter.pre(TokenType.EXPR_STRING_TRIM)
def tt_string_trim(node: TrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = node.value
    # (function (str, chars) {
    #     return str.replace(new RegExp(`^[${chars}]+|[${chars}]+$`, 'g'), '');
    # });
    code = "(function (str, chars){return str.replace(new RegExp(`^[${chars}]+|[${chars}]+$`, 'g'), '');})"
    code += f"({prv}, {chars!r}); "
    return f"let {nxt} = " + code


@converter.pre(TokenType.EXPR_LIST_STRING_TRIM)
def tt_string_trim_all(node: MapTrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = node.value
    map_code = (
        "(function (str, chars)"
        + "{return str.replace(new RegExp(`^[${chars}]+|[${chars}]+$`, 'g'), '');})"
    )
    map_code += f"(e, {chars})"
    return f"let {nxt} = {prv}.map(e => {map_code}); "


@converter.pre(TokenType.EXPR_STRING_LTRIM)
def tt_string_ltrim(node: LTrimExpression) -> str:
    # const ltrim = function (str, chars) {return str.replace(new RegExp(`^[${chars}]+`, 'g'), '');};
    #
    prv, nxt = left_right_var_names("value", node.variable)
    chars = node.value
    code = "(function (str, chars) {return str.replace(new RegExp(`^[${chars}]+`, 'g'), '');})"
    code += f"({prv}, {chars!r}); "
    return f"let {nxt} = {code} "


@converter.pre(TokenType.EXPR_LIST_STRING_LTRIM)
def tt_string_ltrim_all(node: MapLTrimExpression) -> str:
    # const ltrim = function (str, chars) {
    #     return str.replace(new RegExp(`^[${chars}]+`, 'g'), '');
    # };
    prv, nxt = left_right_var_names("value", node.variable)
    chars = node.value
    map_code = (
        "(function (str, chars)"
        + "{return str.replace(new RegExp(`^[${chars}]+`, 'g'), '');})"
    )
    map_code += f"(e, {chars!r})"
    return f"let {nxt} = {prv}.map(e => {map_code}); "


@converter.pre(TokenType.EXPR_STRING_RTRIM)
def tt_string_rtrim(node: RTrimExpression) -> str:
    # const rtrim = function (str, chars) {
    #     return str.replace(new RegExp(`[${chars}]+$`, 'g'), '');
    # };
    #
    prv, nxt = left_right_var_names("value", node.variable)
    chars = node.value
    code = "(function (str, chars) {return str.replace(new RegExp(`^[${chars}]+`, 'g'), '');})"
    code += f"({prv}, {chars!r}); "
    return f"let {nxt} = {code}"


@converter.pre(TokenType.EXPR_LIST_STRING_RTRIM)
def tt_string_rtrim_all(node: MapRTrimExpression) -> str:
    # const rtrim = function (str, chars) {
    #     return str.replace(new RegExp(`[${chars}]+$`, 'g'), '');
    # };
    #
    prv, nxt = left_right_var_names("value", node.variable)
    chars = node.value
    map_code = (
        "(function (str, chars)"
        + "{return str.replace(new RegExp(`[${chars}]+$`, 'g'), '');})"
    )
    map_code += f"(e, {chars!r})"
    return f"let {nxt} = {prv}.map(e => {map_code}); "


@converter.pre(TokenType.EXPR_STRING_REPLACE)
def tt_string_replace(node: ReplaceExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    old, new = node.old, node.new
    return f"let {nxt} = {prv}.replace({old!r}, {new!r}); "


@converter.pre(TokenType.EXPR_LIST_STRING_REPLACE)
def tt_string_replace_all(node: MapReplaceExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    old, new = node.old, node.new
    return f"let {nxt} = {prv}.map(e => e.replace({old!r}, {new!r}));"


@converter.pre(TokenType.EXPR_STRING_SPLIT)
def tt_string_split(node: SplitExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    sep = node.sep
    return f"let {nxt} = {prv}.split({sep!r}); "


@converter.pre(TokenType.EXPR_REGEX)
def tt_regex(node: RegexExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    pattern = "/" + node.pattern + "/g"
    group = node.group - 1
    return f"let {nxt} = {prv}.match({pattern})[{group}]; "


@converter.pre(TokenType.EXPR_REGEX_ALL)
def tt_regex_all(node: RegexAllExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    pattern = "/" + node.pattern + "/g"
    return f"let {nxt} = {prv}.match({pattern}); "


@converter.pre(TokenType.EXPR_REGEX_SUB)
def tt_regex_sub(node: RegexSubExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    pattern = "/" + node.pattern + "/g"
    repl = repr(node.repl)
    return f"let {nxt} = {prv}.replace({pattern}, {repl!r}); "


@converter.pre(TokenType.EXPR_LIST_REGEX_SUB)
def tt_regex_sub_all(node: MapRegexSubExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    pattern = "/" + node.pattern + "/g"
    repl = repr(node.repl)
    return f"let {nxt} = {prv}.map(e => e.replace({pattern}, {repl!r})); "


@converter.pre(TokenType.EXPR_LIST_STRING_INDEX)
def tt_string_index(node: IndexStringExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    return f"let {nxt} = {prv}[{node.value}]; "


@converter.pre(TokenType.EXPR_LIST_DOCUMENT_INDEX)
def tt_doc_index(node: IndexDocumentExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    return f"let {nxt} = {prv}[{node.value}]; "


@converter.pre(TokenType.EXPR_LIST_JOIN)
def tt_join(node: JoinExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    sep = node.sep
    return f"let {nxt} = {prv}.join({sep!r}); "


@converter.pre(TokenType.IS_EQUAL)
def tt_is_equal(node: IsEqualExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    code = f"if ({prv} != {node.value!r}) throw new Error({node.msg!r}); "
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += f"\nlet {nxt} = {prv}; "
    return code


@converter.pre(TokenType.IS_NOT_EQUAL)
def tt_is_not_equal(node: IsNotEqualExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    code = f"if ({prv} == {node.value!r}) throw new Error({node.msg!r}); "
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += f"let {nxt} = {prv}; "
    return code


@converter.pre(TokenType.IS_CONTAINS)
def tt_is_contains(node: IsContainsExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    code = f"if (!({node.item!r} in {prv})) throw new Error({node.msg!r});"
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += f"let {nxt} = {prv}; "
    return code


@converter.pre(TokenType.IS_REGEX_MATCH)
def tt_is_regex(node: IsRegexMatchExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    pattern = "/" + node.pattern + "/"
    code = f"if (!({prv}.match({pattern}) === null)) throw new Error({node.msg!r}); "
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += f"let {nxt} = {prv}; "
    return code


# BS4 API
@converter.pre(TokenType.EXPR_CSS)
def tt_css(node: HtmlCssExpression) -> str:
    q = node.query
    prv, nxt = left_right_var_names("value", node.variable)
    return f"let {nxt} = {prv}.querySelector({q!r}); "


@converter.pre(TokenType.EXPR_CSS_ALL)
def tt_css_all(node: HtmlCssAllExpression) -> str:
    q = node.query
    prv, nxt = left_right_var_names("value", node.variable)
    return f"let {nxt} = {prv}.querySelectorAll({q!r}); "


@converter.pre(TokenType.EXPR_XPATH)
def tt_xpath(node: HtmlXpathExpression) -> str:
    q = node.query
    prv, nxt = left_right_var_names("value", node.variable)
    # const result = document.evaluate(xpath, element, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
    code = f"document.evaluate({q!r}, {prv}, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue; "
    return f"let {nxt} = {code}"


@converter.pre(TokenType.EXPR_XPATH_ALL)
def tt_xpath_all(node: HtmlXpathAllExpression) -> str:
    q = node.query
    prv, nxt = left_right_var_names("value", node.variable)
    xpath_eval = f"document.evaluate({q!r}, {prv}, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null)"
    code = (
        "Array.from({ length: result.snapshotLength }, (_, i) => "
        + f"{xpath_eval}.snapshotItem(i)); "
    )
    return f"let {nxt} = {code}"


@converter.pre(TokenType.EXPR_TEXT)
def tt_text(node: HtmlTextExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    # document object
    if node.variable.num == 0:
        return f'let {nxt} = {prv}.querySelector("html").textContent; '
    return f"let {nxt} = {prv}.textContent; "


@converter.pre(TokenType.EXPR_TEXT_ALL)
def tt_text_all(node: HtmlTextAllExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    return f"let {nxt} = {prv}.map(e => e.textContent); "


@converter.pre(TokenType.EXPR_RAW)
def tt_raw(node: HtmlRawExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    # document object
    if node.variable.num == 0:
        return f'let {nxt} = {prv}.querySelector("html").innerHTML; '
    return f"let {nxt} = {prv}.innerHTML; "


@converter.pre(TokenType.EXPR_RAW_ALL)
def tt_raw_all(node: HtmlRawAllExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    return f"let {nxt} = {prv}.map(e => e.innerHTML); "


@converter.pre(TokenType.EXPR_ATTR)
def tt_attr(node: HtmlAttrExpression):
    attr = node.attr
    prv, nxt = left_right_var_names("value", node.variable)
    return f"let {nxt} = {prv}.getAttribute({attr!r}); "


@converter.pre(TokenType.EXPR_ATTR_ALL)
def tt_attr_all(node: HtmlAttrAllExpression):
    attr = node.attr
    prv, nxt = left_right_var_names("value", node.variable)
    return f"let {nxt} = {prv}.map(e => e.getAttribute({attr!r})); "


@converter.pre(TokenType.IS_CSS)
def tt_is_css(node: IsCssExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    code = f"if (!{prv}.querySelector({node.query!r})) throw new Error({node.msg!r}); "
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += f"let {nxt} = {prv}; "
    return code


@converter.pre(TokenType.IS_XPATH)
def tt_is_xpath(node: IsXPathExpression):
    #   const result = document.evaluate(xpath, context || document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
    #     const node = result.singleNodeValue;
    prv, nxt = left_right_var_names("value", node.variable)
    code = f"document.evaluate({node.query!r}, {prv}, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue"
    code = f"if(!{code}) throw new Error({node.msg!r}); "
    if node.next.kind == TokenType.EXPR_NO_RETURN:
        return code
    code += f"let {nxt} = {prv}; "
    return code
