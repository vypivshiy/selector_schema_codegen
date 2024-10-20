from typing import Callable

from ..ast_ssc import (
    BaseAstNode,
    StructParser,
    Variable,
    PreValidateFunction,
    StructFieldFunction,
    Docstring,
    StartParseFunction,
    ModuleImports,
    DefaultValueWrapper,
    # TODO: STRUCT GEN API

    HtmlCssExpression, HtmlCssAllExpression,
    HtmlAttrExpression, HtmlAttrAllExpression,
    HtmlTextExpression, HtmlTextAllExpression,
    HtmlRawExpression, HtmlRawAllExpression,
    HtmlXpathExpression, HtmlXpathAllExpression,

    FormatExpression, MapFormatExpression,
    TrimExpression, MapTrimExpression,
    LTrimExpression, MapLTrimExpression,
    RTrimExpression, MapRTrimExpression,
    ReplaceExpression, MapReplaceExpression,
    SplitExpression,

    RegexExpression, RegexSubExpression, MapRegexSubExpression, RegexAllExpression,

    ReturnExpression, NoReturnExpression,

    # TODO TYPEDDICT API impl

    IndexDocumentExpression, IndexStringExpression, JoinExpression,

    IsCssExpression, IsXPathExpression, IsEqualExpression, IsContainsExpression,
    IsRegexMatchExpression  # TODO: nested impl
)
from ..tokens import TokenType, StructType


class BaseCodeConverter:
    """base code class converter"""

    def __init__(self):
        self.pre_definitions: dict[TokenType, Callable[[BaseAstNode], str]] = {}
        self.post_definitions: dict[TokenType, Callable[[BaseAstNode], str]] = {}

    def pre(self, for_definition: TokenType):
        def decorator(func: Callable[[BaseAstNode], str]):
            self.pre_definitions[for_definition] = func
            return func

        return decorator

    def post(self, for_definition: TokenType):
        def decorator(func: Callable[[BaseAstNode], str]):
            self.post_definitions[for_definition] = func
            return func

        return decorator

    def convert_node(self, node: BaseAstNode) -> str:
        if self.pre_definitions.get(node.kind):
            return self.pre_definitions[node.kind](node)
        return ""

    def convert_struct(self, ast_struct: StructParser):
        print(self.convert_node(ast_struct))
        print(self.convert_node(ast_struct.doc))
        for fn in ast_struct.body:
            print(self.convert_node(fn))
            if fn.kind == StartParseFunction and fn.default:
                print(self.convert_node(fn.default))
            for expr in fn.body:
                print(self.convert_node(expr))


def left_right_var_names(name: str, variable: Variable, prefix: str = "", suffix: str = "") -> tuple[str, str]:
    if variable.num == 0:
        prev = f"{prefix}{name}{suffix}"
    else:
        prev = f"{prefix}{name}{variable.num}{suffix}"
    next_ = f"{prefix}{name}{variable.num_next}{suffix}"
    return prev, next_


converter = BaseCodeConverter()


# python API
@converter.pre(TokenType.STRUCT)
def tt_struct(node: StructParser) -> str:
    return f"class {node.name}:"


@converter.pre(TokenType.DOCSTRING)
def tt_docstring(node: Docstring) -> str:
    code = ""
    if node.value:
        code += f'"""{node.value}"""\n'
    # TODO: init expression
    code += "def __init__(self, document: str):\n"
    code += "self._doc=BeautifulSoup(document)"
    return code


@converter.pre(TokenType.IMPORTS)
def tt_imports(node: ModuleImports) -> str:
    modules = node.modules
    return "import " + ', '.join(modules)


@converter.pre(TokenType.EXPR_RETURN)
def tt_ret(node: ReturnExpression) -> str:
    _, nxt = left_right_var_names("value", node.variable)
    return f"return {nxt}"


@converter.pre(TokenType.EXPR_NO_RETURN)
def tt_no_ret(node: NoReturnExpression) -> str:
    return "return"


@converter.pre(TokenType.STRUCT_PRE_VALIDATE)
def tt_pre_validate(node: PreValidateFunction) -> str:
    return "def _pre_validate(self, value): pass"


@converter.pre(TokenType.STRUCT_FIELD)
def tt_function(node: StructFieldFunction) -> str:
    return f"def _parse_{node.name}(self, value):"


@converter.pre(TokenType.STRUCT_PARSE_START)
def tt_start_parse(node: StartParseFunction) -> str:
    code = "def parse(self):\n"
    match node.type:
        case StructType.ITEM:
            body = ', '.join([f'"{f.name}": _parse_{f.name}(self._doc)"' for f in node.body])
            body = '{' + body + '}'
            return code + f"return {body}"
        case _:
            raise NotImplementedError("TODO")


@converter.pre(TokenType.EXPR_DEFAULT)
def tt_default(node: DefaultValueWrapper) -> str:
    return "try:"


@converter.post(TokenType.EXPR_DEFAULT)
def tt_default(node: DefaultValueWrapper) -> str:
    # TODO: string fmt
    val = repr(node.value) if isinstance(node.value, str) else node.value
    return f"except Exception:\n    {val}"


@converter.pre(TokenType.EXPR_STRING_FORMAT)
def tt_string_format(node: FormatExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    template = node.fmt.replace('{{}}', "{}")
    return nxt + ' = ' + f"{template!r}.format({prv})"


@converter.pre(TokenType.EXPR_LIST_STRING_FORMAT)
def tt_string_format_all(node: MapFormatExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    template = node.fmt.replace('{{}}', "{}")
    return nxt + ' = ' + f"[{template!r}.format(e) for e in {prv}]"


@converter.pre(TokenType.EXPR_STRING_TRIM)
def tt_string_trim(node: TrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = node.value
    return f"{nxt} = {prv}.strip({chars!r})"


@converter.pre(TokenType.EXPR_LIST_STRING_TRIM)
def tt_string_trim_all(node: MapTrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = node.value
    return f"{nxt} = [e.strip({chars!r}) for e in {prv}]"


@converter.pre(TokenType.EXPR_STRING_LTRIM)
def tt_string_ltrim(node: LTrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = node.value
    return f"{nxt} = {prv}.lstrip({chars!r})"


@converter.pre(TokenType.EXPR_LIST_STRING_LTRIM)
def tt_string_ltrim_all(node: MapLTrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = node.value
    return f"{nxt} = [e.lstrip({chars!r}) for e in {prv}]"


@converter.pre(TokenType.EXPR_STRING_RTRIM)
def tt_string_rtrim(node: RTrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = node.value
    return f"{nxt} = {prv}.rstrip({chars!r})"


@converter.pre(TokenType.EXPR_LIST_STRING_RTRIM)
def tt_string_rtrim_all(node: MapRTrimExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    chars = node.value
    return f"{nxt} = [e.rstrip({chars!r}) for e in {prv}]"


@converter.pre(TokenType.EXPR_STRING_REPLACE)
def tt_string_replace(node: ReplaceExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    old, new = node.old, node.new
    return f"{nxt} = {prv}.replace({old!r}, {new!r})"


@converter.pre(TokenType.EXPR_LIST_STRING_REPLACE)
def tt_string_replace_all(node: MapReplaceExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    old, new = node.old, node.new
    return f"{nxt} = [e.replace({old!r}, {new!r}) for e in {prv}]"


@converter.pre(TokenType.EXPR_STRING_SPLIT)
def tt_string_split(node: SplitExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    sep = node.sep
    return f"{nxt} = {prv}.split({sep!r})"


@converter.pre(TokenType.EXPR_REGEX)
def tt_regex(node: RegexExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    pattern = node.pattern
    group = node.group
    return f"{nxt} = re.search({pattern!r}, {prv})[{group}]"


@converter.pre(TokenType.EXPR_REGEX_ALL)
def tt_regex_all(node: RegexAllExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    pattern = node.pattern
    return f"{nxt} = re.findall({pattern!r}, {prv})"


@converter.pre(TokenType.EXPR_REGEX_SUB)
def tt_regex_sub(node: RegexSubExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    pattern = node.pattern
    repl = node.repl
    return f"{nxt} = re.sub({pattern!r}, {repl!r}, {prv})"


@converter.pre(TokenType.EXPR_LIST_REGEX_SUB)
def tt_regex_sub_all(node: MapRegexSubExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    pattern = node.pattern
    repl = node.repl
    return f"{nxt} = [re.sub({pattern!r}, {repl!r}, e) for e in {prv}]"


@converter.pre(TokenType.EXPR_LIST_STRING_INDEX)
def tt_string_index(node: IndexStringExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    return f"{nxt} = {prv}[{node.value}]"


@converter.pre(TokenType.EXPR_LIST_DOCUMENT_INDEX)
def tt_doc_index(node: IndexDocumentExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    return f"{nxt} = {prv}[{node.value}]"


@converter.pre(TokenType.EXPR_LIST_JOIN)
def tt_join(node: JoinExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    sep = node.sep
    return f"{nxt} = {sep!r}.join({prv})"


@converter.pre(TokenType.IS_EQUAL)
def tt_is_equal(node: IsEqualExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    code = f"assert {prv} == {node.value}, {node.msg!r}"
    code += f"\n{nxt} = {prv}"
    return code


@converter.pre(TokenType.IS_NOT_EQUAL)
def tt_is_equal(node: IsEqualExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    code = f"assert {prv} != {node.value}, {node.msg!r}"
    code += f"\n{nxt} = {prv}"
    return code


@converter.pre(TokenType.IS_CONTAINS)
def tt_is_contains(node: IsContainsExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    code = f"assert {node.item!r} in {prv}, {node.msg!r}"
    code += f"\n{nxt} = {prv}"
    return code


@converter.pre(TokenType.IS_REGEX_MATCH)
def tt_is_regex(node: IsRegexMatchExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    code = f"assert re.search({node.pattern!r}, {prv}), {node.msg!r}"
    code += f"\n{nxt} = {prv}"
    return code


# BS4 API
@converter.pre(TokenType.EXPR_CSS)
def tt_css(node: HtmlCssExpression) -> str:
    q = node.query
    prv, nxt = left_right_var_names("value", node.variable)
    return f"{nxt} = {prv}.select_one({q!r})"


@converter.pre(TokenType.EXPR_CSS_ALL)
def tt_css_all(node: HtmlCssAllExpression) -> str:
    q = node.query
    prv, nxt = left_right_var_names("value", node.variable)
    return f"{nxt} = {prv}.select({q!r})"


@converter.pre(TokenType.EXPR_XPATH)
def tt_xpath(node: HtmlXpathExpression) -> str:
    raise NotImplementedError


@converter.pre(TokenType.EXPR_XPATH_ALL)
def tt_xpath_all(node: HtmlXpathAllExpression) -> str:
    raise NotImplementedError


@converter.pre(TokenType.EXPR_TEXT)
def tt_text(node: HtmlTextExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    return f"{nxt} = {prv}.text"


@converter.pre(TokenType.EXPR_TEXT_ALL)
def tt_text_all(node: HtmlTextAllExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    return f"{nxt} = [e.text for e in {prv}]"


@converter.pre(TokenType.EXPR_RAW)
def tt_raw(node: HtmlRawExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    return f"{nxt} = {prv}.__str__()"


@converter.pre(TokenType.EXPR_RAW_ALL)
def tt_raw_all(node: HtmlRawAllExpression) -> str:
    prv, nxt = left_right_var_names("value", node.variable)
    return f"{nxt} = [e.__str__() for e in {prv}]"


@converter.pre(TokenType.EXPR_ATTR)
def tt_attr(node: HtmlAttrExpression):
    n = node.attr
    prv, nxt = left_right_var_names("value", node.variable)
    # bs4 auto convert multiattr values to list
    # most libs return attr value as string
    return f"{nxt} = {prv}[{n!r}] if isinstance({prv}[{n!r}], str) else ' '.join({prv}[{n!r}])"


@converter.pre(TokenType.EXPR_ATTR_ALL)
def tt_attr_all(node: HtmlAttrAllExpression):
    n = node.attr
    prv, nxt = left_right_var_names("value", node.variable)
    # [el[name] if isinstance(el[name], str) else " ".join(el[name]) for el in els]
    # bs4 auto convert multiattr values to list
    # most libs return attr value as string
    return f"{nxt} = [e[{n!r}] if isinstance(el[{n!r}], str) else ' '.join(e[{n!r}] for e in {prv}]"


@converter.pre(TokenType.IS_CSS)
def tt_is_css(node: IsCssExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    code = f"assert {prv}.select_one({node.query!r}),   {node.msg!r}"
    code += f"\n{nxt} = {prv}"
    return code


@converter.pre(TokenType.IS_XPATH)
def tt_is_css(node: IsXPathExpression):
    raise NotImplementedError
