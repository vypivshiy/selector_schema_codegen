from typing import cast

from ssc_codegen.converters.base import ConverterContext, BaseConverter

# types
from ssc_codegen.ast import VariableType, StructType

from ssc_codegen.converters.helpers import (
    to_pascal_case,
    to_snake_case,
    jsonify_path_to_segments,
)

# module level
from ssc_codegen.ast import (
    Docstring,
    Imports,
    Utilities,
    JsonDef,
    JsonDefField,
    TypeDef,
    TypeDefField,
    Struct,
    Module,
)

# struct layer
from ssc_codegen.ast import (
    Field,
    Init,
    InitField,
    PreValidate,
    SplitDoc,
    TableConfig,
    TableMatchKey,
    TableRow,
    Key,
    Value,
    StartParse,
    StructDocstring,
)
# expressions layer

# selectors
from ssc_codegen.ast import (
    CssSelect,
    CssSelectAll,
    XpathSelect,
    XpathSelectAll,
    CssRemove,
    XpathRemove,
    Attr,
    Text,
    Raw,
)

# string
from ssc_codegen.ast import (
    Trim,
    Ltrim,
    Rtrim,
    RmPrefix,
    RmSuffix,
    RmPrefixSuffix,
    Fmt,
    Repl,
    ReplMap,
    Lower,
    Upper,
    Split,
    Join,
    Unescape,
    NormalizeSpace,
)

# regex
from ssc_codegen.ast import Re, ReAll, ReSub

# Array
from ssc_codegen.ast import Index, Slice, Len, Unique

# casts
from ssc_codegen.ast import ToInt, ToFloat, ToBool, Jsonify, Nested

# controls
from ssc_codegen.ast import FallbackStart, FallbackEnd, Self, Return

# predicates
from ssc_codegen.ast import (
    Filter,
    Assert,
    Match,
    LogicAnd,
    LogicNot,
    LogicOr,
)

# pred exprs
from ssc_codegen.ast import (
    PredCss,
    PredContains,
    PredCountEq,
    PredCountGt,
    PredCountLt,
    PredEnds,
    PredEq,
    PredGe,
    PredGt,
    PredLe,
    PredHasAttr,
    PredIn,
    PredLt,
    PredNe,
    PredRange,
    PredRe,
    PredReAll,
    PredReAny,
    PredStarts,
    PredXpath,
    PredAttrContains,
    PredAttrEnds,
    PredAttrEq,
    PredAttrNe,
    PredAttrRe,
    PredAttrStarts,
    PredTextContains,
    PredTextEnds,
    PredTextRe,
    PredTextStarts,
)

# transform
from ssc_codegen.ast import TransformCall


PY_BASE_CONVERTER = BaseConverter()


PY_TYPES = {
    VariableType.STRING: "str",
    VariableType.BOOL: "bool",
    VariableType.INT: "int",
    VariableType.FLOAT: "float",
    VariableType.JSON: "{}Json",
    VariableType.NESTED: "{}Type",
    VariableType.OPT_FLOAT: "Optional[float]",
    VariableType.OPT_INT: "Optional[int]",
    VariableType.OPT_STRING: "Optional[str]",
    VariableType.LIST_INT: "List[int]",
    VariableType.LIST_STRING: "List[str]",
    VariableType.LIST_FLOAT: "List[float]",
    VariableType.LIST_DOCUMENT: "ResultSet[Tag]",
    VariableType.DOCUMENT: "Union[Tag, BeautifulSoup]",
    VariableType.NULL: "None",
}


@PY_BASE_CONVERTER(Docstring)
def pre_docstring(node: Docstring, _: ConverterContext):
    return f'''"""{node.value}"""'''


@PY_BASE_CONVERTER(Imports)
def pre_imports(node: Imports, _: ConverterContext):
    base_imports = [
        "import json",
        "import re",
        "import sys",
        "from typing import TypedDict, Optional, Any, List, Dict, Union",
        "from html import unescape as _html_unescape",
    ]

    # Get transform imports for Python (already collected during parsing)
    transform_imports = sorted(node.transform_imports.get("py", set()))

    return base_imports + transform_imports


# hook for add extra dependencies
@PY_BASE_CONVERTER.post(Imports)
def post_imports(node: Imports, _):
    return [
        "from bs4 import BeautifulSoup, ResultSet, Tag",
        # todo: config from CLI
        "BS4_FEATURES = 'lxml'",
    ]


@PY_BASE_CONVERTER(Utilities)
def pre_utilities(node: Utilities, _: ConverterContext):
    # TODO: helper functions
    return [
        "_RE_HEX_ENTITY = re.compile(r'&#x([0-9a-fA-F]+);')",
        "_RE_UNICODE_ENTITY = re.compile(r'\\\\u([0-9a-fA-F]{4})')",
        "_RE_BYTES_ENTITY = re.compile(r'\\\\x([0-9a-fA-F]{2})')",
        "_RE_CHARS_MAP = {'\\b': '\\b', '\\f': '\\f', '\\n': '\\n', '\\r': '\\r', '\\t': '\\t'}",
        "\n",
        "def repl_map(s: str, rmap: Dict[str, str]) -> str:",
        "    for k, v in rmap.items():",
        "        s = s.replace(k, v)",
        "    return s",
        "\n",
        "def normalize_text(text: str) -> str:",
        "    return ' '.join(text.split()) if text else \"\"",
        "\n",
        "class _UnmatchedTableRow:",
        "    pass",
        "\n",
        "def unescape_text(text: str) -> str:",
        "    s = _html_unescape(text)",
        "    s = _RE_HEX_ENTITY.sub(lambda m: chr(int(m.group(1), 16)), s)",
        "    s = _RE_UNICODE_ENTITY.sub(lambda m: chr(int(m.group(1), 16)), s)",
        "    s = _RE_BYTES_ENTITY.sub(lambda m: chr(int(m.group(1), 16)), s)",
        "    for ch, r in _RE_CHARS_MAP.items():",
        "        s = s.replace(ch, r)",
        "    return s",
        "\n",
        # backport funcs
        "if sys.version_info > (3, 10):",
        "    def rm_prefix(s: str, p: str) -> str:",
        "        return s.removeprefix(p)",
        "\n",
        "    def rm_suffix(s: str, p: str) -> str:",
        "        return s.removesuffix(p)",
        "\n",
        "else:",
        "    def rm_prefix(s: str, p: str) -> str:",
        "        return s[len(p):] if s.startswith(p) else s",
        "\n",
        "    def rm_suffix(s: str, p: str) -> str:",
        "        return s[:-(len(p))] if s.endswith(p) else s",
        "\n\n",
        "UNMATCHED_TABLE_ROW = _UnmatchedTableRow()",
        "\n\n",
    ]


@PY_BASE_CONVERTER(JsonDef)
def pre_json_struct(node: JsonDef, _: ConverterContext):
    name = to_pascal_case(node.name)
    return [f"class {name}Json(TypedDict):"]


@PY_BASE_CONVERTER(JsonDefField)
def pre_json_field(node: JsonDefField, ctx: ConverterContext):
    name = to_snake_case(node.name)
    type_ = PY_TYPES.get(node.ret, "Any")
    if node.ret == VariableType.JSON and node.ref_name:
        type_name = to_pascal_case(node.ref_name)
        type_ = type_.format(type_name)
        if node.is_array:
            type_ = f"List[{type_}]"
    # VariableType.NESTED not used in Json node context
    return [f"{ctx.indent}{name}: {type_}"]


@PY_BASE_CONVERTER(TypeDef)
def pre_typedef(node: TypeDef, _: ConverterContext):
    name = to_pascal_case(node.name)
    if node.struct_type == StructType.DICT:
        return None
    elif node.struct_type == StructType.FLAT:
        return f"{name}Type = List[str]"
    return f"class {name}Type(TypedDict):"


@PY_BASE_CONVERTER(TypeDefField)
def pre_typedef_field(node: TypeDefField, ctx: ConverterContext):
    # alreay created type, skip
    if node.typedef.struct_type == StructType.FLAT:
        return
    name = to_snake_case(node.name)
    type_ = PY_TYPES.get(node.ret, "Any")
    if node.ret == VariableType.JSON and node.json_ref:
        type_name = to_pascal_case(node.json_ref)
        type_ = type_.format(type_name)
        if node.is_array:
            type_ = f"List[{type_}]"
    elif node.ret == VariableType.NESTED and node.nested_ref:
        type_name = to_pascal_case(node.nested_ref)
        type_ = type_.format(type_name)
        if node.is_array:
            type_ = f"List[{type_}]"
    if node.typedef.struct_type == StructType.DICT:
        if to_snake_case(node.name) == "value":
            typedef_name = to_pascal_case(node.typedef.name)
            return f"{typedef_name}Type = Dict[str, {type_}]"
        return None
    return [f"{ctx.indent}{name}: {type_}"]


@PY_BASE_CONVERTER(Struct)
def pre_struct(node: Struct, ctx: ConverterContext):
    name = to_pascal_case(node.name)
    return [f"class {name}:"]


@PY_BASE_CONVERTER(StructDocstring)
def pre_struct_docstring(node: StructDocstring, ctx: ConverterContext):
    if node.value:
        lines = [f'{ctx.indent}"""']
        lines.extend(f"{ctx.indent}{line}" for line in node.value.splitlines())
        lines.append(f'{ctx.indent}"""')
        return lines
    return


@PY_BASE_CONVERTER(StartParse)
def pre_start_parse(node: StartParse, ctx: ConverterContext):
    name = to_pascal_case(node.struct.name)

    match node.struct_type:
        case StructType.ITEM:
            ret_type = f"{name}Type"
        case StructType.LIST:
            ret_type = f"List[{name}Type]"
        case StructType.FLAT:
            ret_type = "List[str]"  # TODO
        case StructType.DICT:
            ret_type = f"{name}Type"
        case StructType.TABLE:
            ret_type = f"{name}Type"
        case _:
            raise NotImplementedError(
                "Unknown struct type", repr(node.struct_type)
            )
    return f"{ctx.indent}def parse(self) -> {ret_type}:"


@PY_BASE_CONVERTER.post(StartParse)
def post_start_parse(node: StartParse, ctx: ConverterContext):
    lines: list[str] = []
    if node.use_pre_validate:
        lines.append(f"{ctx.indent * 2}self._pre_validate(self._doc)")
    # TODO: pre_validate call
    # TODO: move init fields here
    match node.struct_type:
        case StructType.ITEM:
            # return {name: self_parse_name(self._doc), ...}
            lines.append(f"{ctx.indent * 2}return {{")
            for field in node.fields:
                name = to_snake_case(field.name)
                lines.append(
                    f"{ctx.indent * 3}{name!r}: self._parse_{name}(self._doc),"
                )
            lines.append(f"{ctx.indent * 3} }}")
        case StructType.LIST:
            # return [{name, ...} for i in self._split_doc(self.document)]
            lines.append(f"{ctx.indent * 2}return [{{")
            for field in node.fields:
                name = to_snake_case(field.name)
                lines.append(
                    f"{ctx.indent * 3}{name!r}: self._parse_{name}(i),"
                )
            lines.append(
                f"{ctx.indent * 3}}} for i in self._split_doc(self._doc)]"
            )
        case StructType.DICT:
            lines.extend(
                [
                    f"{ctx.indent * 2}return {{",
                    f"{ctx.indent * 3} self._parse_key(i): self._parse_value(i)",
                    f"{ctx.indent * 3} for i in self._split_doc(self._doc)",
                    f"{ctx.indent * 3} }}",
                ]
            )
        case StructType.FLAT:
            lines.append(f"{ctx.indent * 2}result: List[str] = []")
            for field in node.fields:
                name = to_snake_case(field.name)
                if field.ret == VariableType.STRING:
                    lines.append(
                        f"{ctx.indent * 2}result.append(self._parse_{name}(self._doc))"
                    )
                # LIST_STRING type
                else:
                    lines.append(
                        f"{ctx.indent * 2}result.extend(self._parse_{name}(self._doc))"
                    )
            if node.struct.keep_order:
                # py 3.7+ dict.fromkeys guaranteed keep order
                lines.append(
                    f"{ctx.indent * 2}return list(dict.fromkeys(result))"
                )
            else:
                lines.append(f"{ctx.indent * 2}return list(set(result))")
        case StructType.TABLE:
            # For each row in _parse_table_rows(), run _table_match_key() to get
            # the key string, then dispatch to the matching _parse_{field}()
            # method. First successful match for each field wins.
            name = to_pascal_case(node.struct.name)
            lines.append(f"{ctx.indent * 2}_result: {name}Type = {{}}")
            lines.extend(
                [
                    f"{ctx.indent * 2}_table = self._table_config(self._doc)",
                    f"{ctx.indent * 2}for _row in self._parse_table_rows(_table):",
                ]
            )
            for f in node.fields:
                fname = to_snake_case(f.name)
                lines.append(
                    f"{ctx.indent * 3}_{fname} = self._parse_{fname}(_row)"
                )
                lines.append(
                    f"{ctx.indent * 3}if _{fname} != UNMATCHED_TABLE_ROW and {fname!r} not in _result:"
                )
                lines.append(f"{ctx.indent * 4}_result[{fname!r}] = _{fname}")
            lines.append(f"{ctx.indent * 2}return _result")

        case _:
            raise NotImplementedError
    return lines


# required overload for target backend
@PY_BASE_CONVERTER(Init)
def pre_init(node: Init, ctx: ConverterContext):
    init_node_names: list[str] = []
    for i in node.body:
        if isinstance(i, InitField):
            name = to_snake_case(i.name)
            init_node_names.append(name)
    code = [
        f"{ctx.indent}def __init__(self, document: Union[str, BeautifulSoup, Tag]):",
        f"{ctx.indent * 2}if isinstance(document, str):",
        f"{ctx.indent * 3}self._doc = BeautifulSoup(document, features=BS4_FEATURES)",
        f"{ctx.indent * 2}else:",
        f"{ctx.indent * 3}self._doc = document",
    ]
    for name in init_node_names:
        # late init vars
        code.append(
            f"{ctx.indent * 2}self._{name} = self._init_{name}(self._doc)"
        )
    return code


@PY_BASE_CONVERTER(InitField)
def pre_init_field(node: InitField, ctx: ConverterContext):
    name = to_snake_case(node.name)
    # cannot return nested or json, skip check
    ret_type = PY_TYPES.get(node.ret, "Any")
    return [
        f"    def _init_{name}(self, v: Union[Tag, BeautifulSoup]) -> {ret_type}:"
    ]


@PY_BASE_CONVERTER(Field)
def pre_struct_field(node: Field, ctx: ConverterContext):
    name = to_snake_case(node.name)
    ret_type = PY_TYPES.get(node.ret, "Any")
    # issue: how to detect if json arr or json struct simplier?
    if node.ret == VariableType.JSON:
        jsonify_node = [i for i in node.body if isinstance(i, Jsonify)][0]
        ret_type = ret_type.format(jsonify_node.schema_name)
        # Use is_array from jsonify_node (after path resolution), not from JsonDef schema
        if jsonify_node.is_array:
            ret_type = f"List[{ret_type}]"
    elif node.ret == VariableType.NESTED:
        nested_node = [i for i in node.body if isinstance(i, Nested)][0]
        ret_type = ret_type.format(nested_node.struct_name)
        if nested_node.is_array:
            ret_type = f"List[{ret_type}]"
    # table struct fields start with match { ... } and may return a sentinel
    if node.accept == VariableType.STRING:
        return [
            f"    def _parse_{name}(self, v: Union[Tag, BeautifulSoup]) -> Union[{ret_type}, _UnmatchedTableRow]:"
        ]
    return [
        f"    def _parse_{name}(self, v: Union[Tag, BeautifulSoup]) -> {ret_type}:"
    ]


@PY_BASE_CONVERTER(PreValidate)
def pre_struct_pre_validate(node: PreValidate, ctx: ConverterContext):
    # just validate, not modify document
    return [
        "    def _pre_validate(self, v: Union[Tag, BeautifulSoup]) -> None:"
    ]


@PY_BASE_CONVERTER(SplitDoc)
def pre_struct_split_doc(node: SplitDoc, ctx: ConverterContext):
    return [
        "    def _split_doc(self, v: Union[Tag, BeautifulSoup]) -> ResultSet[Tag]:",
    ]


@PY_BASE_CONVERTER(Key)
def pre_struct_key(node: Key, ctx: ConverterContext):
    # ret type always should be a string
    return ["    def _parse_key(self, v: Union[Tag, BeautifulSoup]) -> str:"]


@PY_BASE_CONVERTER(Value)
def pre_struct_value(node: Value, ctx: ConverterContext):
    ret_type = PY_TYPES.get(node.ret, "Any")
    # issue: how to detect if json arr or json struct simplier?
    if node.ret == VariableType.JSON:
        jsonify_node = [i for i in node.body if isinstance(i, Jsonify)][0]
        ret_type = ret_type.format(jsonify_node.schema_name)
        # Use is_array from jsonify_node (after path resolution), not from JsonDef schema
        if jsonify_node.is_array:
            ret_type = f"List[{ret_type}]"
    elif node.ret == VariableType.NESTED:
        nested_node = [i for i in node.body if isinstance(i, Nested)][0]
        ret_type = ret_type.format(nested_node.struct_name)
        if nested_node.is_array:
            ret_type = f"List[{ret_type}]"
    return [
        f"    def _parse_value(self, v: Union[Tag, BeautifulSoup]) -> {ret_type}:"
    ]


@PY_BASE_CONVERTER(TableConfig)
def pre_struct_table_config(node: TableConfig, ctx: ConverterContext):
    # should be a selector
    return [
        "    def _table_config(self,  v: Union[Tag, BeautifulSoup]) -> Tag:"
    ]


@PY_BASE_CONVERTER(TableMatchKey)
def pre_struct_table_match_key(node: TableMatchKey, ctx: ConverterContext):
    # should be returns a string
    return [
        "    def _table_match_key(self, v: Union[Tag, BeautifulSoup]) -> str:",
    ]


@PY_BASE_CONVERTER(TableRow)
def pre_struct_table_row(node: TableRow, ctx: ConverterContext):
    return [
        "    def _parse_table_rows(self, v: Union[Tag, BeautifulSoup]) -> ResultSet[Tag]:"
    ]


# EXPRESSIONS:


# SELECTORS
@PY_BASE_CONVERTER(CssSelect)
def pre_expr_css_select(node: CssSelect, ctx: ConverterContext):
    query = repr(node.query)
    return f"{ctx.indent}{ctx.nxt} = {ctx.prv}.select_one({query})"


@PY_BASE_CONVERTER(CssSelectAll)
def pre_expr_css_select_all(node: CssSelectAll, ctx: ConverterContext):
    query = repr(node.query)
    return f"{ctx.indent}{ctx.nxt} = {ctx.prv}.select({query})"


@PY_BASE_CONVERTER(XpathSelect)
def pre_expr_xpath_select(node: XpathSelect, ctx: ConverterContext):
    raise NotImplementedError("BS4 not supports xpath queries")


@PY_BASE_CONVERTER(XpathSelectAll)
def pre_expr_xpath_select_all(node: XpathSelectAll, ctx: ConverterContext):
    raise NotImplementedError("BS4 not supports xpath queries")


@PY_BASE_CONVERTER(CssRemove)
def pre_expr_css_remove(node: CssRemove, ctx: ConverterContext):
    query = repr(node.query)
    # note: side effect call
    return [
        f"{ctx.indent}[i.decompose() for i in {ctx.prv}.select({query})]",
        f"{ctx.indent}{ctx.nxt} = {ctx.prv}",
    ]


@PY_BASE_CONVERTER(XpathRemove)
def pre_expr_xpath_remove(node: XpathRemove, ctx: ConverterContext):
    raise NotImplementedError("BS4 not supports xpath queries")


@PY_BASE_CONVERTER(Attr)
def pre_expr_attr(node: Attr, ctx: ConverterContext):
    keys = node.keys
    # bs4 return list of attrs if several values set in attr key, set string for API consistence
    # eg bs4 extract attrs workflow:
    # class="foo bar" -> ["foo", "bar"]
    if node.accept == VariableType.DOCUMENT:
        if len(keys) == 1:
            return f"{ctx.indent}{ctx.nxt} = ' '.join({ctx.prv}.get_attribute_list({keys[0]!r}))"
        return f"{ctx.indent}{ctx.nxt}=[' '.join({ctx.prv}.get_attribute_list(k)) for k in {keys} if {ctx.prv}.get(k)]"
    # LIST_DOCUMENT
    if len(keys) == 1:
        return f"{ctx.indent}{ctx.nxt} = [' '.join(e.get_attribute_list({keys[0]!r})) for e in {ctx.prv}]"
    return f"{ctx.indent}{ctx.nxt} = [' '.join(e.get_attribute_list(k)) for e in {ctx.prv} for k in {keys} if e.get(k)]"


@PY_BASE_CONVERTER(Text)
def pre_expr_text(node: Text, ctx: ConverterContext):
    if node.accept == VariableType.DOCUMENT:
        return f"{ctx.indent}{ctx.nxt} = {ctx.prv}.text"
    # LIST_DOCUMENT
    return f"{ctx.indent}{ctx.nxt} = [i.text for i in {ctx.prv}]"


@PY_BASE_CONVERTER(Raw)
def pre_expr_raw(node: Raw, ctx: ConverterContext):
    # in bs4 for extract raw html tag, need cast by str(TAG) expr
    if node.accept == VariableType.DOCUMENT:
        return f"{ctx.indent}{ctx.nxt} = str({ctx.prv})"
    # LIST_DOCUMENT
    return f"{ctx.indent}{ctx.nxt} = [str(i) for i in {ctx.prv}]"


# STRING
@PY_BASE_CONVERTER(Trim)
def pre_expr_trim(node: Trim, ctx: ConverterContext):
    if node.substr == "":
        value = ""
    else:
        value = repr(node.substr)
    if node.accept == VariableType.STRING:
        return [f"{ctx.indent}{ctx.nxt} = {ctx.prv}.strip({value})"]
    return [f"{ctx.indent}{ctx.nxt} = [i.strip({value}) for i in {ctx.prv}]"]


@PY_BASE_CONVERTER(Ltrim)
def pre_expr_ltrim(node: Ltrim, ctx: ConverterContext):
    if node.substr == "":
        value = ""
    else:
        value = repr(node.substr)
    if node.accept == VariableType.STRING:
        return [f"{ctx.indent}{ctx.nxt} = {ctx.prv}.lstrip({value})"]
    return [f"{ctx.indent}{ctx.nxt} = [i.lstrip({value}) for i in {ctx.prv}]"]


@PY_BASE_CONVERTER(Rtrim)
def pre_expr_rtrim(node: Rtrim, ctx: ConverterContext):
    if node.substr == "":
        value = ""
    else:
        value = repr(node.substr)
    if node.accept == VariableType.STRING:
        return [f"{ctx.indent}{ctx.nxt} = {ctx.prv}.rstrip({value})"]
    return [f"{ctx.indent}{ctx.nxt} = [i.rstrip({value}) for i in {ctx.prv}]"]


@PY_BASE_CONVERTER(RmPrefix)
def pre_expr_rm_prefix(node: RmPrefix, ctx: ConverterContext):
    value = repr(node.substr)
    # TODO: backport for Python < 3.10
    if node.accept == VariableType.STRING:
        return [f"{ctx.indent}{ctx.nxt} = rm_prefix({ctx.prv}, {value})"]
    return [
        f"{ctx.indent}{ctx.nxt} = [rm_prefix(i, {value}) for i in {ctx.prv}]"
    ]


@PY_BASE_CONVERTER(RmSuffix)
def pre_expr_rm_suffix(node: RmSuffix, ctx: ConverterContext):
    value = repr(node.substr)
    # TODO: backport for Python < 3.10
    if node.accept == VariableType.STRING:
        return [f"{ctx.indent}{ctx.nxt} = rm_suffix({ctx.prv}, {value})"]
    return [
        f"{ctx.indent}{ctx.nxt} = [rm_suffix(i, {value}) for i in {ctx.prv}]"
    ]


@PY_BASE_CONVERTER(RmPrefixSuffix)
def pre_expr_rm_prefix_suffix(node: RmPrefixSuffix, ctx: ConverterContext):
    prefix = repr(node.substr)
    suffix = repr(node.substr)
    # TODO: backport for Python < 3.10
    if node.accept == VariableType.STRING:
        return [
            f"{ctx.indent}{ctx.nxt} = rm_suffix(rm_prefix({ctx.prv}, {prefix}), {suffix})"
        ]
    return [
        f"{ctx.indent}{ctx.nxt} = [rm_suffix(rm_prefix(i, {prefix}), {suffix}) for i in {ctx.prv}]"
    ]


@PY_BASE_CONVERTER(Fmt)
def pre_expr_fmt(node: Fmt, ctx: ConverterContext):
    template = repr(node.template.replace("{{}}", "{}", 1))
    if node.accept == VariableType.STRING:
        return [f"{ctx.indent}{ctx.nxt} = {template}.format({ctx.prv})"]
    return [
        f"{ctx.indent}{ctx.nxt} = [{template}.format(i) for i in {ctx.prv}]"
    ]


@PY_BASE_CONVERTER(Repl)
def pre_expr_repl(node: Repl, ctx: ConverterContext):
    old = repr(node.old)
    new = repr(node.new)
    if node.accept == VariableType.STRING:
        return [f"{ctx.indent}{ctx.nxt} = {ctx.prv}.replace({old}, {new})"]
    return [
        f"{ctx.indent}{ctx.nxt} = [i.replace({old}, {new}) for i in {ctx.prv}]"
    ]


@PY_BASE_CONVERTER(ReplMap)
def pre_expr_repl_map(node: ReplMap, ctx: ConverterContext):
    repl_dict = repr(node.replacements)
    if node.accept == VariableType.STRING:
        return f"{ctx.indent}{ctx.nxt} = repl_map({ctx.prv}, {repl_dict})"
    return (
        f"{ctx.indent}{ctx.nxt} = [repl_map(i, {repl_dict}) for i in {ctx.prv}]"
    )


@PY_BASE_CONVERTER(Lower)
def pre_expr_lower(node: Lower, ctx: ConverterContext):
    if node.accept == VariableType.STRING:
        return f"{ctx.indent}{ctx.nxt} = {ctx.prv}.lower()"
    return f"{ctx.indent}{ctx.nxt} = [i.lower() for i in {ctx.prv}]"


@PY_BASE_CONVERTER(Upper)
def pre_expr_upper(node: Lower, ctx: ConverterContext):
    if node.accept == VariableType.STRING:
        return f"{ctx.indent}{ctx.nxt} = {ctx.prv}.upper()"
    return f"{ctx.indent}{ctx.nxt} = [i.upper() for i in {ctx.prv}]"


@PY_BASE_CONVERTER(Split)
def pre_expr_split(node: Split, ctx: ConverterContext):
    sep = repr(node.sep)
    # node.accept == VariableType.STRING:
    return f"{ctx.indent}{ctx.nxt} = {ctx.prv}.split({sep})"


@PY_BASE_CONVERTER(Join)
def pre_expr_join(node: Join, ctx: ConverterContext):
    sep = repr(node.sep)
    # node.accept == VariableType.LIST_STRING:
    return f"{ctx.indent}{ctx.nxt} = {sep}.join({ctx.prv})"


@PY_BASE_CONVERTER(NormalizeSpace)
def pre_expr_normalize(node: NormalizeSpace, ctx: ConverterContext):
    if node.accept == VariableType.STRING:
        return f"{ctx.indent}{ctx.nxt} = normalize_text({ctx.prv})"
    return f"{ctx.indent}{ctx.nxt} = [normalize_text(i) for i in {ctx.prv}]"


@PY_BASE_CONVERTER(Unescape)
def pre_expr_unescape(node: Unescape, ctx: ConverterContext):
    if node.accept == VariableType.STRING:
        return f"{ctx.indent}{ctx.nxt} = unescape_text({ctx.prv})"
    return f"{ctx.indent}{ctx.nxt} = [unescape_text(i) for i in {ctx.prv}]"


# REGEX


@PY_BASE_CONVERTER(Re)
def pre_expr_re(node: Re, ctx: ConverterContext):
    pattern = repr(node.pattern)
    if node.accept == VariableType.STRING:
        return f"{ctx.indent}{ctx.nxt} = re.search({pattern}, {ctx.prv})[1]"
    # LIST_STRING — map over items
    return f"{ctx.indent}{ctx.nxt} = [re.search({pattern}, i)[1] for i in {ctx.prv}]"


@PY_BASE_CONVERTER(ReAll)
def pre_expr_re_all(node: ReAll, ctx: ConverterContext):
    pattern = repr(node.pattern)
    return f"{ctx.indent}{ctx.nxt} = re.findall({pattern}, {ctx.prv})"


@PY_BASE_CONVERTER(ReSub)
def pre_expr_re_sub(node: ReSub, ctx: ConverterContext):
    pattern = repr(node.pattern)
    repl = repr(node.repl)
    if node.accept == VariableType.STRING:
        return f"{ctx.indent}{ctx.nxt} = re.sub({pattern}, {repl}, {ctx.prv})"
    return f"{ctx.indent}{ctx.nxt} = [re.sub({pattern}, {repl}, i) for i in {ctx.prv}]"


# array
@PY_BASE_CONVERTER(Index)
def pre_expr_index(node: Index, ctx: ConverterContext):
    idx = node.i
    return f"{ctx.indent}{ctx.nxt} = {ctx.prv}[{idx}]"


@PY_BASE_CONVERTER(Slice)
def pre_expr_slice(node: Slice, ctx: ConverterContext):
    start = node.start
    end = node.end
    return f"{ctx.indent}{ctx.nxt} = {ctx.prv}[{start}:{end}]"


@PY_BASE_CONVERTER(Len)
def pre_expr_len(node: Len, ctx: ConverterContext):
    return f"{ctx.indent}{ctx.nxt} = len({ctx.prv})"


@PY_BASE_CONVERTER(Unique)
def pre_expr_unique(node: Unique, ctx: ConverterContext):
    if node.keep_order:
        # py3.7+ dict preserves insertion order, so we can use it to remove duplicates while keeping order
        return f"{ctx.indent}{ctx.nxt} = list(dict.fromkeys({ctx.prv}))"
    return f"{ctx.indent}{ctx.nxt} = list(set({ctx.prv}))"


# casts
@PY_BASE_CONVERTER(ToInt)
def pre_expr_to_int(node: ToInt, ctx: ConverterContext):
    if node.accept == VariableType.STRING:
        return f"{ctx.indent}{ctx.nxt} = int({ctx.prv})"
    return f"{ctx.indent}{ctx.nxt} = [int(i) for i in {ctx.prv}]"


@PY_BASE_CONVERTER(ToFloat)
def pre_expr_to_float(node: ToFloat, ctx: ConverterContext):
    if node.accept == VariableType.STRING:
        return f"{ctx.indent}{ctx.nxt} = float({ctx.prv})"
    return f"{ctx.indent}{ctx.nxt} = [float(i) for i in {ctx.prv}]"


@PY_BASE_CONVERTER(ToBool)
def pre_expr_to_bool(node: ToBool, ctx: ConverterContext):
    # todo bool rule:
    return f"{ctx.indent}{ctx.nxt} = bool({ctx.prv})"


@PY_BASE_CONVERTER(Jsonify)
def pre_expr_jsonify(node: Jsonify, ctx: ConverterContext):
    # schema_name = to_pascal_case(node.schema_name) (used in type annotations, not in codegen)
    if node.path:
        path = ""
        parts = jsonify_path_to_segments(node.path)
        for part in parts:
            if part.isdigit():
                path += f"[{part}]"
            else:
                path += f"[{part}]"
        return f"{ctx.indent}{ctx.nxt} = json.loads({ctx.prv}){path}"
    return f"{ctx.indent}{ctx.nxt} = json.loads({ctx.prv})"


@PY_BASE_CONVERTER(Nested)
def pre_expr_nested(node: Nested, ctx: ConverterContext):
    struct_name = to_pascal_case(node.struct_name)
    return f"{ctx.indent}{ctx.nxt} = {struct_name}({ctx.prv}).parse()"


# controls
@PY_BASE_CONVERTER(Self)
def pre_expr_self(node: Self, ctx: ConverterContext):
    name = to_snake_case(node.name)
    # todo: standart pre calculated fields
    return f"{ctx.indent}{ctx.nxt} = self._{name}"


@PY_BASE_CONVERTER(TransformCall)
def pre_expr_transform_call(node: TransformCall, ctx: ConverterContext):
    # Find the Python implementation from transform_def
    if not node.transform_def:
        raise ValueError(f"TransformCall '{node.name}': transform_def is None")

    # Get Python-specific target
    py_target = None
    for target in node.transform_def.body:
        if target.lang == "py":
            py_target = target
            break

    if not py_target:
        raise ValueError(
            f"TransformCall '{node.name}': no 'py' implementation found"
        )

    # Generate code by substituting {{PRV}} and {{NXT}}
    lines = []
    for code_line in py_target.code:
        # Replace placeholders
        code_line = code_line.replace("{{PRV}}", ctx.prv)
        code_line = code_line.replace("{{NXT}}", ctx.nxt)
        lines.append(f"{ctx.indent}{code_line}")

    return lines


@PY_BASE_CONVERTER(Return)
def pre_expr_return(node: Return, ctx: ConverterContext):
    if isinstance(node.parent, PreValidate):
        return f"{ctx.indent}return"
    return f"{ctx.indent}return {ctx.prv}"


# TODO: recalc indents. Maybe required change node and fill Fallback body?
@PY_BASE_CONVERTER(FallbackStart)
def pre_expr_fallback_start(node: FallbackStart, ctx: ConverterContext):
    return f"{ctx.indent}try:"


@PY_BASE_CONVERTER(FallbackEnd)
def pre_expr_fallback_end(node: FallbackEnd, ctx: ConverterContext):
    return [
        f"{ctx.indent}except Exception:",
        f"{ctx.indent}{ctx.indent_char}return {node.value!r}",
    ]


# predicates
@PY_BASE_CONVERTER(
    Filter, post_callback=lambda _, ctx: ctx.deeper().indent + "]"
)
def pre_expr_filter(node: Filter, ctx: ConverterContext):
    # NXT = [i for i in PRV if ({CONDS...})]
    return f"{ctx.indent}{ctx.nxt} = [i for i in {ctx.prv} if "


# TODO: msg API
@PY_BASE_CONVERTER(
    Assert, post_callback=lambda _, ctx: ctx.deeper().indent + ")"
)
def pre_expr_assert(node: Assert, ctx: ConverterContext):
    return [
        f"{ctx.indent}i = {ctx.prv}",
        f"{ctx.indent}assert (",
    ]


@PY_BASE_CONVERTER.post(Assert)
def post_expr_assert(node: Assert, ctx: ConverterContext):
    return [ctx.deeper().indent + ")", f"{ctx.indent}{ctx.nxt} = {ctx.prv}"]


@PY_BASE_CONVERTER(Match)
def pre_expr_match(node: Match, ctx: ConverterContext):
    # _key = self._table_match_key(v)  — the row key to match against
    # predicates use `i` as the current item (the key string)
    # `i` alias lets all predicate handlers work unchanged inside match blocks
    return [
        f"{ctx.indent}i = self._table_match_key({ctx.prv})",
        f"{ctx.indent}if not (",
    ]


@PY_BASE_CONVERTER.post(Match)
def post_expr_match(node: Match, ctx: ConverterContext):
    # close the condition; if it doesn't match, return sentinel
    # if it matched, get the value cell via _parse_value and continue pipeline
    # ctx.indent = pipeline body level (e.g. depth=2 → 8 spaces)
    # deeper indent for the return statement inside the if-block
    return [
        f"{ctx.indent}):",
        f"{ctx.indent}{ctx.indent_char}return UNMATCHED_TABLE_ROW",
        f"{ctx.indent}{ctx.nxt} = self._parse_value({ctx.prv})",
    ]


@PY_BASE_CONVERTER(LogicAnd, post_callback=lambda _, ctx: ctx.indent + ")")
def pre_expr_logic_and(node: LogicAnd, ctx: ConverterContext):
    # and ({CONDS...})
    return f"{ctx.indent}and ("


@PY_BASE_CONVERTER(LogicOr, post_callback=lambda _, ctx: ctx.indent + ")")
def pre_expr_logic_or(node: LogicOr, ctx: ConverterContext):
    # or ({CONDS...})
    return f"{ctx.indent}or ("


@PY_BASE_CONVERTER(LogicNot, post_callback=lambda _, ctx: ctx.indent + ")")
def pre_expr_logic_not(node: LogicNot, ctx: ConverterContext):
    # and not ({CONDS...})
    return f"{ctx.indent}and not ("


# note: all step-by-step conds acc by AND on
@PY_BASE_CONVERTER(PredCss)
def pre_expr_pred_css(node: PredCss, ctx: ConverterContext):
    query = repr(node.query)
    cond = f"i.select_one({query})"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_BASE_CONVERTER(PredXpath)
def pre_expr_pred_xpath(node: PredXpath, ctx: ConverterContext):
    raise NotImplementedError("BS4 not supports XPATH queries")


@PY_BASE_CONVERTER(PredContains)
def pre_expr_pred_contains(node: PredContains, ctx: ConverterContext):
    values = node.values
    if len(values) == 1:
        cond = f"{values[0]!r} in i"
    else:
        cond = f"any(v in i for v in {values!r})"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_BASE_CONVERTER(PredEq)
def pre_expr_pred_eq(node: PredEq, ctx: ConverterContext):
    values = node.values

    # should be single value (cmp by len)
    if isinstance(values[0], int):
        cond = f"len(i) == {values[0]}"
    elif len(values) == 1 and isinstance(values[0], str):
        cond = f"i == {values[0]!r}"
    # series of strings
    else:
        cond = f"any(i == v for v in {values!r})"

    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f" and {cond}"


@PY_BASE_CONVERTER(PredNe)
def pre_expr_pred_ne(node: PredNe, ctx: ConverterContext):
    values = node.values

    # should be single value (cmp by len)
    if isinstance(values[0], int):
        cond = f"len(i) != {values[0]}"
    elif len(values) == 1 and isinstance(values[0], str):
        cond = f"i != {values[0]!r}"
    # series of strings
    else:
        # todo: change spec: for many args in ne - convert to all({COND...})
        cond = ctx.indent + f"all(i != v for v in {values!r})"
    if ctx.index == 0:
        return cond
    return ctx.indent + f"and {cond}"


@PY_BASE_CONVERTER(PredStarts)
def pre_expr_pred_starts(node: PredStarts, ctx: ConverterContext):
    values = node.values
    if len(values) == 1:
        cond = f"i.startswith({values[0]!r})"
    else:
        cond = f"any(i.startswith(v) for v in {values!r})"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_BASE_CONVERTER(PredEnds)
def pre_expr_pred_ends(node: PredEnds, ctx: ConverterContext):
    values = node.values
    if len(values) == 1:
        cond = f"i.endswith({values[0]!r})"
    else:
        cond = f"any(i.endswith(v) for v in {values!r})"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


# TODO: count expr simplify - reuse eq,gt,le with int argument
@PY_BASE_CONVERTER(PredCountEq)
def pre_expr_pred_count_eq(node: PredCountEq, ctx: ConverterContext):
    value = node.value
    cond = f"len(i) == {value}"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_BASE_CONVERTER(PredCountGt)
def pre_expr_pred_count_gt(node: PredCountGt, ctx: ConverterContext):
    value = node.value
    cond = f"len(i) > {value}"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_BASE_CONVERTER(PredCountLt)
def pre_expr_pred_count_lt(node: PredCountLt, ctx: ConverterContext):
    value = node.value
    cond = f"len(i) < {value}"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_BASE_CONVERTER(PredHasAttr)
def pre_expr_pred_has_attr(node: PredHasAttr, ctx: ConverterContext):
    keys = node.attrs
    if len(keys) == 1:
        cond = f"bool(i.get({keys[0]!r}, False))"
    else:
        cond = f"any(bool(i.get(k, False)) for k in {keys!r})"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_BASE_CONVERTER(PredAttrContains)
def pre_expr_pred_attr_contains(node: PredAttrContains, ctx: ConverterContext):
    name = node.name
    values = node.values
    # dont need check exists key
    if len(values) == 1:
        cond = f"{values[0]!r} in (' '.join(i.get_attribute_list({name!r})))"
    else:
        cond = f"any(v in (' '.join(i.get_attribute_list({name!r}))) for v in {values!r})"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_BASE_CONVERTER(PredAttrEnds)
def pre_expr_pred_attr_ends(node: PredAttrEnds, ctx: ConverterContext):
    name = node.name
    values = node.values
    # dont need check exists key
    attr_value = f"(' '.join(i.get_attribute_list({name!r})))"
    if len(values) == 1:
        cond = f"{attr_value}.endswith({values[0]!r})"
    else:
        cond = f"{attr_value}.endswith({tuple(values)!r})"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_BASE_CONVERTER(PredAttrEq)
def pre_expr_pred_attr_eq(node: PredAttrEq, ctx: ConverterContext):
    name = node.name
    values = node.values
    # dont need check exists key
    if len(values) == 1:
        cond = f"(' '.join(i.get_attribute_list({name!r}))) == {values[0]!r}"
    else:
        cond = f"any((' '.join(i.get_attribute_list({name!r}))) == v for v in {values!r})"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_BASE_CONVERTER(PredAttrNe)
def pre_expr_pred_attr_ne(node: PredAttrNe, ctx: ConverterContext):
    name = node.name
    values = node.values
    # dont need check exists key
    attr_value = f"(' '.join(i.get_attribute_list({name!r})))"
    if len(values) == 1:
        cond = f"{attr_value} != {values[0]!r}"
    else:
        cond = f"all({attr_value} != v for v in {values!r})"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_BASE_CONVERTER(PredAttrRe)
def pre_expr_pred_attr_re(node: PredAttrRe, ctx: ConverterContext):
    name = node.name
    pattern = repr(node.pattern)
    # dont need check exists key
    cond = f"bool(re.search({pattern}, (' '.join(i.get_attribute_list({name!r})))))"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_BASE_CONVERTER(PredAttrStarts)
def pre_expr_pred_attr_starts(node: PredAttrStarts, ctx: ConverterContext):
    name = node.name
    values = node.values
    # dont need check exists key
    attr_value = f"(' '.join(i.get_attribute_list({name!r})))"
    if len(values) == 1:
        cond = f"{attr_value}.startswith({values[0]!r})"
    else:
        cond = f"{attr_value}.startswith({tuple(values)!r})"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_BASE_CONVERTER(PredTextContains)
def pre_expr_pred_text_contains(node: PredTextContains, ctx: ConverterContext):
    values = node.values
    if len(values) == 1:
        cond = f"{values[0]!r} in i.text"
    else:
        cond = f"any(v in i.text for v in {values!r})"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_BASE_CONVERTER(PredTextEnds)
def pre_expr_pred_text_ends(node: PredTextEnds, ctx: ConverterContext):
    values = node.values
    if len(values) == 1:
        cond = f"i.text.endswith({values[0]!r})"
    else:
        cond = f"any(i.text.endswith(v) for v in {values!r})"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_BASE_CONVERTER(PredTextRe)
def pre_expr_pred_text_re(node: PredTextRe, ctx: ConverterContext):
    pattern = repr(node.pattern)
    cond = f"bool(re.search({pattern}, i.text))"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_BASE_CONVERTER(PredTextStarts)
def pre_expr_pred_text_starts(node: PredTextStarts, ctx: ConverterContext):
    values = node.values
    if len(values) == 1:
        cond = f"i.text.startswith({values[0]!r})"
    else:
        cond = f"any(i.text.startswith(v) for v in {values!r})"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_BASE_CONVERTER(PredIn)
def pre_expr_pred_in(node: PredIn, ctx: ConverterContext):
    values = node.values
    if len(values) == 1:
        cond = f"{values[0]!r} in i"
    else:
        cond = f"any(v in i for v in {values!r})"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_BASE_CONVERTER(PredGe)
def pre_expr_pred_ge(node: PredGe, ctx: ConverterContext):
    value = node.value
    cond = f"len(i) >= {value}"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_BASE_CONVERTER(PredGt)
def pre_expr_pred_gt(node: PredGt, ctx: ConverterContext):
    value = node.value
    cond = f"len(i) > {value}"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_BASE_CONVERTER(PredLe)
def pre_expr_pred_le(node: PredLe, ctx: ConverterContext):
    value = node.value
    cond = f"len(i) <= {value}"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_BASE_CONVERTER(PredLt)
def pre_expr_pred_lt(node: PredLt, ctx: ConverterContext):
    value = node.value
    cond = f"len(i) < {value}"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_BASE_CONVERTER(PredRange)
def pre_expr_pred_range(node: PredRange, ctx: ConverterContext):
    start = node.start
    end = node.end
    cond = f"{start} < len(i) < {end}"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_BASE_CONVERTER(PredRe)
def pre_expr_pred_re(node: PredRe, ctx: ConverterContext):
    pattern = repr(node.pattern)
    cond = f"bool(re.search({pattern}, i))"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_BASE_CONVERTER(PredReAll)
def pre_expr_pred_re_all(node: PredReAll, ctx: ConverterContext):
    # assert specific expr
    pattern = repr(node.pattern)
    cond = f"all(re.search({pattern}, j) for j in i)"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"


@PY_BASE_CONVERTER(PredReAny)
def pre_expr_pred_re_any(node: PredReAny, ctx: ConverterContext):
    # assert specific expr
    pattern = repr(node.pattern)
    cond = f"any(re.search({pattern}, j) for j in i)"
    if ctx.index == 0:
        return ctx.indent + cond
    return ctx.indent + f"and {cond}"
