from typing import Callable

from ..ast_ssc import (
    BaseAstNode,
    ModuleProgram,
    StructParser,
    ModuleImports,
    Variable,
    PreValidateFunction,
    StructFieldFunction,
    Docstring,
    StartParseFunction,
    DefaultValueWrapper,
    PartDocFunction,

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
    TypeDef, TypeDefField,
    IndexDocumentExpression, IndexStringExpression, JoinExpression,

    IsCssExpression, IsXPathExpression, IsEqualExpression, IsContainsExpression,
    IsRegexMatchExpression, IsNotEqualExpression  # TODO: nested impl
)
from ..tokens import TokenType, StructType, VariableType


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

    def pre_convert_node(self, node: BaseAstNode) -> str:
        if self.pre_definitions.get(node.kind):
            return self.pre_definitions[node.kind](node)
        return ""

    def post_convert_node(self, node: BaseAstNode) -> str:
        if self.post_definitions.get(node.kind):
            return self.post_definitions[node.kind](node)
        return ""

    def convert_program(self, ast_program: ModuleProgram, comment: str = '') -> list[str]:
        acc = [comment]
        result = self.convert(ast_program, acc)
        return result

    def convert(self, ast_entry: BaseAstNode, acc: list[str] | None = None):
        if not acc:
            acc = []
        acc.append(self.pre_convert_node(ast_entry))
        if ast_entry.kind == TokenType.STRUCT:
            ast_entry: StructParser
            acc.append(self.pre_convert_node(ast_entry.doc))
            acc.append(self.post_convert_node(ast_entry.doc))
            acc.append(self.pre_convert_node(ast_entry.init))
            acc.append(self.post_convert_node(ast_entry.init))
        if getattr(ast_entry, "body", None):
            if ast_entry.kind == TokenType.STRUCT_FIELD and ast_entry.default:
                acc.append(self.pre_convert_node(ast_entry.default))

            for ast_node in ast_entry.body:
                self.convert(ast_node, acc)

            if ast_entry.kind == TokenType.STRUCT_FIELD and ast_entry.default:
                acc.append(self.post_convert_node(ast_entry.default))
        acc.append(self.post_convert_node(ast_entry))
        return acc


def left_right_var_names(name: str, variable: Variable, prefix: str = "", suffix: str = "") -> tuple[str, str]:
    if variable.num == 0:
        prev = f"{prefix}{name}{suffix}"
    else:
        prev = f"{prefix}{name}{variable.num}{suffix}"
    next_ = f"{prefix}{name}{variable.num_next}{suffix}"
    return prev, next_


converter = BaseCodeConverter()

TYPES = {
    VariableType.STRING: "str",
    VariableType.LIST_STRING: "List[str]",
    VariableType.OPTIONAL_STRING: "Optional[str]",
    VariableType.OPTIONAL_LIST_STRING: "Optional[List[str]]"
}

RESERVED = ['__PRE_VALIDATE__', '__SPLIT_DOC__', '__KEY__', '__VALUE__', '__ITEM__']
MAGIC_METHODS = {"__KEY__": "key",
                 "__VALUE__": "value",
                 "__ITEM__": "item",
                 "__PRE_VALIDATE__": "_pre_validate",
                 "__SPLIT_DOC__": "_split_doc",
                 "__START_PARSE__": "parse"
                 }


@converter.pre(TokenType.TYPEDEF)
def tt_typedef(node: TypeDef):
    # TODO: nested handle
    t_name = f'T_{node.name}'
    # DICT schema
    if all(f.name in ["__KEY__", '__VALUE__'] for f in node.body):
        value_ret = [f for f in node.body if f.name == '__VALUE__'][0].type
        type_ = TYPES.get(value_ret)
        body = f"Dict[str, {type_}]"

    # Flat list schema
    elif all(f.name in ["__ITEM__"] for f in node.body):
        value_ret = [f for f in node.body if f.name == '__ITEM__'][0].type
        type_ = TYPES.get(value_ret)
        body = f"List[{type_}]"
    else:
        body = f"TypedDict({t_name!r}," + '{' + ', '.join(f'{f.name!r}: {TYPES.get(f.type)}' for f in node.body) + '})'
    return f"T_{node.name} = {body}"


# python API
@converter.pre(TokenType.STRUCT)
def tt_struct(node: StructParser) -> str:
    return f"class {node.name}:"


@converter.pre(TokenType.STRUCT_INIT)
def tt_init(_) -> str:
    return "def __init__(self, document: str):"


@converter.post(TokenType.STRUCT_INIT)
def tt_init(_):
    return "self._doc=BeautifulSoup(document, 'lxml')"


@converter.pre(TokenType.DOCSTRING)
def tt_docstring(node: Docstring) -> str:
    if node.value:
        return f'"""{node.value}"""\n'
    return ''


@converter.pre(TokenType.IMPORTS)
def tt_imports(_: ModuleImports) -> str:
    buildin_imports = "from __future__ import annotations\n"
    buildin_imports += "import re\n"
    buildin_imports += "from typing import List, Dict, TypedDict, Union, Optional\n"
    buildin_imports += "from contextlib import suppress\n"
    buildin_imports += "from bs4 import BeautifulSoup, ResultSet, Tag\n"
    return buildin_imports


@converter.pre(TokenType.EXPR_RETURN)
def tt_ret(node: ReturnExpression) -> str:
    _, nxt = left_right_var_names("value", node.variable)
    return f"return {nxt}"


@converter.pre(TokenType.EXPR_NO_RETURN)
def tt_no_ret(_: NoReturnExpression) -> str:
    return "return"


@converter.pre(TokenType.STRUCT_PRE_VALIDATE)
def tt_pre_validate(node: PreValidateFunction) -> str:
    return f"def {MAGIC_METHODS.get(node.name)}(self, value) -> None:"


@converter.pre(TokenType.STRUCT_PART_DOCUMENT)
def tt_part_document(node: PartDocFunction):
    return f"def {MAGIC_METHODS.get('__SPLIT_DOC__')}(self, value: Union[BeautifulSoup, Tag]) -> ResultSet:"


@converter.pre(TokenType.STRUCT_FIELD)
def tt_function(node: StructFieldFunction) -> str:
    # TODO: nested parse API
    name = MAGIC_METHODS.get(node.name, node.name)
    type_ = TYPES.get(node.body[-1].variable.type)
    return f"def _parse_{name}(self, value: Union[BeautifulSoup, Tag]) -> {type_}:"


@converter.pre(TokenType.STRUCT_PARSE_START)
def tt_start_parse(node: StartParseFunction) -> str:
    head = f"def {MAGIC_METHODS.get(node.name)}(self)"
    if node.type == StructType.LIST:
        return f"{head} -> List[T_{node.typedef_signature.name}]:"
    return f"{head} -> T_{node.typedef_signature.name}:"


@converter.post(TokenType.STRUCT_PARSE_START)
def tt_start_parse(node: StartParseFunction):
    code = ""
    if any(f.name == '__PRE_VALIDATE__' for f in node.body):
        n = MAGIC_METHODS.get('__PRE_VALIDATE__')
        code += f"self.{n}(self._doc)\n"

    match node.type:
        case StructType.ITEM:
            body = ', '.join([f'"{f.name}": self._parse_{f.name}(self._doc)' for f in node.body if f.name not in RESERVED])
            body = '{' + body + '}'
        case StructType.LIST:
            body = ', '.join(
                [f'"{f.name}": self._parse_{f.name}(e)' for f in node.body if f.name not in RESERVED]
            )
            body = '{' + body + '}'
            n = MAGIC_METHODS.get('__SPLIT_DOC__')
            body = f"[{body} for e in self.{n}(self._doc)]\n"
        case StructType.DICT:
            key_m = MAGIC_METHODS.get('__KEY__')
            value_m = MAGIC_METHODS.get('__VALUE__')
            part_m = MAGIC_METHODS.get('__SPLIT_DOC__')
            body = '{' + f'self._parse_{key_m}(e): self._parse_{value_m}(e) for e in self.{part_m}(self._doc)' + '}'
        case StructType.FLAT_LIST:
            item_m = MAGIC_METHODS.get('__ITEM__')
            part_m = MAGIC_METHODS.get('__SPLIT_DOC__')
            body = f'[self._parse_{item_m}(e) for e in self.{part_m}(self._doc)]'
        case _:
            raise NotImplementedError("Unknown struct type")
    return code + f"return {body}"


@converter.pre(TokenType.EXPR_DEFAULT)
def tt_default(node: DefaultValueWrapper) -> str:
    return "with suppress(Exception):"


@converter.post(TokenType.EXPR_DEFAULT)
def tt_default(node: DefaultValueWrapper) -> str:
    val = repr(node.value) if isinstance(node.value, str) else node.value
    return f"return {val}"


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
def tt_is_equal(node: IsNotEqualExpression):
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
def tt_xpath(_: HtmlXpathExpression) -> str:
    raise NotImplementedError("bs4 not support xpath")


@converter.pre(TokenType.EXPR_XPATH_ALL)
def tt_xpath_all(_: HtmlXpathAllExpression) -> str:
    raise NotImplementedError("bs4 not support xpath")


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
    # bs4 auto convert multiattr values to list
    # most libs return attr value as string
    return f"{nxt} = [e[{n!r}] if isinstance(e[{n!r}], str) else ' '.join(e[{n!r}]) for e in {prv}]"


@converter.pre(TokenType.IS_CSS)
def tt_is_css(node: IsCssExpression):
    prv, nxt = left_right_var_names("value", node.variable)
    code = f"assert {prv}.select_one({node.query!r}),   {node.msg!r}"
    code += f"\n{nxt} = {prv}"
    return code


@converter.pre(TokenType.IS_XPATH)
def tt_is_xpath(_: IsXPathExpression):
    raise NotImplementedError("Bs4 not support xpath")