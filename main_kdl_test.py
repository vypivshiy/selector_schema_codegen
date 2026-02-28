"""
KDL → AST base parser.

Usage:
    parser = KDLParser()
    module = parser.parse(kdl_document)

Adding a pipeline op:
    @parser.pipeline("css", "css-all")
    def _(node, parent, cursor, ctx):
        return CssSelect(query=node.args[0]), VariableType.DOCUMENT

Adding a predicate op:
    @parser.predicate("eq", "ne")
    def _(node, parent, ctx):
        return PredEq(values=tuple(node.args))

KDL library: ckdl (pip install ckdl)
Expected KdlNode interface:
    node.name        : str
    node.args        : list
    node.properties  : dict
    node.children    : list[KdlNode]
    node.has_children: bool
"""

from __future__ import annotations

from ast import arg
from dataclasses import dataclass, field
from typing import Callable, TypeAlias, cast

from ssc_codegen.kdl.ckdl_types import KdlNode, parse
from ssc_codegen.kdl.ast import Node as AstNode

# exprs
from ssc_codegen.kdl.exceptions import (
    ParseError,
    BuildTimeError,
    UnknownNodeError,
)

# types
from ssc_codegen.kdl.ast import StructType, VariableType

# module layer
from ssc_codegen.kdl.ast import (
    Module,
    Imports,
    Utilities,
    CodeStartHook,
    Docstring,
    Struct,
    TypeDef,
    TypeDefField,
)

# stuct layer
from ssc_codegen.kdl.ast import (
    PreValidate,
    SplitDoc,
    TableConfig,
    TableMatchKey,
    TableRow,
    Field,
    Init,
    InitField,
    Key,
    Value,
)
# expressions

# selectors
from ssc_codegen.kdl.ast import (
    CssSelect,
    CssSelectAll,
    XpathSelect,
    XpathSelectAll,
    CssRemove,
    XpathRemove,
)

# extract
from ssc_codegen.kdl.ast import Text, Raw, Attr

# string
from ssc_codegen.kdl.ast import (
    Trim,
    Ltrim,
    Rtrim,
    NormalizeSpace,
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
)

# regex
from ssc_codegen.kdl.ast import Re, ReAll, ReSub

# array
from ssc_codegen.kdl.ast import Index, Slice, Len, Unique

# casts
from ssc_codegen.kdl.ast import ToInt, ToFloat, ToBool, Jsonify, Nested

# control
from ssc_codegen.kdl.ast import (
    Self,
    Fallback,
    Return,
    FallbackStart,
    FallbackEnd,
)

# predicate containers
from ssc_codegen.kdl.ast import Filter, Assert, Match

# predicate logic
from ssc_codegen.kdl.ast import LogicOr, LogicAnd, LogicNot

# predicate ops
from ssc_codegen.kdl.ast import (
    PredEq,
    PredNe,
    PredGt,
    PredLt,
    PredGe,
    PredLe,
    PredIn,
    PredStarts,
    PredEnds,
    PredContains,
    PredRe,
    PredReAny,
    PredReAll,
    PredCss,
    PredXpath,
    PredHasAttr,
    PredCountEq,
    PredCountGt,
    PredCountLt,
    PredRange,
)


@dataclass
class ParseContext:
    property_defines: dict[str, str | int | float | bool] = field(
        default_factory=dict
    )
    children_defines: dict[str, list[KdlNode]] = field(default_factory=dict)
    transforms: dict[str, list[KdlNode]] = field(default_factory=dict)
    # TODO: reg init fields
    init: dict[str, dict[str, str]] = field(default_factory=dict)


ParentAstNode: TypeAlias = AstNode

CallbackRegModule = Callable[[KdlNode, Module, ParseContext], AstNode]
CallbcakRegContext = Callable[[KdlNode, ParseContext], None]
CallbackRegStruct = Callable[[KdlNode, Struct, ParseContext], AstNode]
FieldLikeNode: TypeAlias = (
    PreValidate
    | SplitDoc
    | TableConfig
    | TableRow
    | TableMatchKey
    | Key
    | Value
    | Field
    | InitField
)
CallbackReg = Callable[[KdlNode, FieldLikeNode, ParseContext], AstNode]
CallbackFilter = Callable[[KdlNode, Filter, ParseContext], AstNode]
CallbackAssert = Callable[[KdlNode, Assert, ParseContext], AstNode]
CallbackMatch = Callable[[KdlNode, Match, ParseContext], AstNode]
PredicateLikeNode: TypeAlias = (
    LogicNot | LogicAnd | LogicOr | Filter | Assert | Match
)
CallbackPred = Callable[[KdlNode,PredicateLikeNode, ParseContext], AstNode]


class AstParser:
    def __init__(self) -> None:
        self._module_handlers: dict[str, CallbackRegModule] = {}
        self._context_handlers: dict[str, CallbcakRegContext] = {}
        self._context_structs: dict[str, CallbackRegStruct] = {}
        self._context_expressions: dict[str, CallbackReg] = {}
        self._context_filter: dict[str, CallbackFilter] = {}
        self._context_assert: dict[str, CallbackAssert] = {}
        self._context_match: dict[str, CallbackMatch] = {}
        self.ctx = ParseContext()

    def register_module_context(
        self, name: str
    ) -> Callable[..., Callable[[KdlNode, ParseContext], None]]:
        def decorator(fn: CallbcakRegContext) -> CallbcakRegContext:
            self._context_handlers[name] = fn
            return fn

        return decorator
    

    def register_predicate_node(self, name: str, *, 
                                reg_filter: bool = True,
                                reg_assert: bool = True,
                                reg_match: bool = True) -> Callable[..., CallbackPred]:
        """reg in filter, assert and match"""
        def decorator(fn: CallbackPred):
            if reg_filter:
                self._context_filter[name] = fn
            if reg_assert:
                self._context_assert[name] = fn
            if reg_match:
                self._context_match[name] = fn
            return fn
        return decorator

    def register_module_node(
        self, name: str
    ) -> Callable[..., CallbackRegModule]:
        def decorator(fn: CallbackRegModule) -> CallbackRegModule:
            self._module_handlers[name] = fn
            return fn

        return decorator

    def register_struct_node(
        self, name: str
    ) -> Callable[..., CallbackRegStruct]:
        def decorator(fn: CallbackRegStruct) -> CallbackRegStruct:
            self._context_structs[name] = fn
            return fn

        return decorator

    def register_expression_node(self, name: str):
        def decorator(cb: CallbackReg):
            self._context_expressions[name] = cb
            return cb

        return decorator

    def register_filter_node(self, name: str) -> Callable[..., CallbackFilter]:
        def decorator(cb: CallbackFilter) -> CallbackFilter:
            self._context_filter[name] = cb
            return cb

        return decorator

    def register_assert_node(self, name: str) -> Callable[..., CallbackAssert]:
        def decorator(cb: CallbackAssert) -> CallbackAssert:
            self._context_assert[name] = cb
            return cb

        return decorator

    def register_match_node(self, name: str) -> Callable[..., CallbackMatch]:
        def decorator(cb: CallbackMatch) -> CallbackMatch:
            self._context_match[name] = cb
            return cb

        return decorator
    
    def _typedef_from_struct(self, struct: Struct, parent: Module) -> TypeDef:
        typedef = TypeDef(parent=parent, name=struct.name, struct_type=struct.struct_type)
        for field in struct.body:
            if isinstance(field, Field):
                nested_ref = ''
                json_ref = ''
                if field.ret == VariableType.NESTED:
                    nested_ref = [i for i in field.body if isinstance(i, Nested)][0].struct_name
                elif field.ret == VariableType.JSON:
                    json_ref = [i for i in field.body if isinstance(i, Jsonify)][0].schema_name

                typedef.body.append(
                    TypeDefField(parent=typedef, ret=field.ret, 
                                 name=field.name, nested_ref=nested_ref, json_ref=json_ref)
                                 )
        return typedef

    def parse(self, kdl_dsl: str) -> Module:
        document = parse(kdl_dsl)
        module = Module()
        # collect struct, generate typedefs
        # tydefes shoud be instert before parse structs
        structs: list[Struct] = []
        typedefs: list[TypeDef] = []

        # layer 1 - module
        for node in document.nodes:
            # built-in
            if node.name == "-doc":
                module.docstring.value = node.args[0]
            # handlers
            elif cb := self._context_handlers.get(node.name):
                cb(node, self.ctx)
            elif cb := self._module_handlers.get(node.name):
                expr = cb(node, module, self.ctx)
                if isinstance(expr, Struct):
                    self._parse_struct(node.children, expr)
                    structs.append(expr)
                    typedefs.append(self._typedef_from_struct(expr, module))
            else:
                raise UnknownNodeError(node.name, "Unknown keyword node")
        module.body.extend(typedefs + structs)
        return module

    def _parse_struct(self, kdl_nodes: list[KdlNode], parent: Struct):
        for node in kdl_nodes:
            # built-in
            if node.name == "-doc":
                parent.docstring.value = node.args[0]
            elif node.name == "-init":
                expr = Init(parent=parent)
                self._parse_init_fields(node.children, expr)
                parent.body.append(expr)
            elif node.name == "-pre-validate":
                expr = PreValidate(parent=parent)
                self._parse_expressions(node.children, expr)
                parent.body.append(expr)
            elif node.name == "-split-doc":
                expr = SplitDoc(parent=parent)
                self._parse_expressions(node.children, expr)
                parent.body.append(expr)
            elif node.name == "-key":
                expr = Key(parent=parent)
                self._parse_expressions(node.children, expr)
                parent.body.append(expr)
            elif node.name == "-value":
                expr = Value(parent=parent)
                self._parse_expressions(node.children, expr)
                parent.body.append(expr)
            elif node.name == "-table":
                expr = TableConfig(parent=parent)
                self._parse_expressions(node.children, expr)
                parent.body.append(expr)
            elif node.name == "-row":
                expr = TableRow(parent=parent)
                self._parse_expressions(node.children, expr)
                parent.body.append(expr)
            elif node.name == "-match":
                expr = TableMatchKey(parent=parent)
                self._parse_expressions(node.children, expr)
                parent.body.append(expr)
            else:
                expr = Field(parent=parent, name=node.name)
                self._parse_expressions(node.children, expr)
                parent.body.append(expr)

    def _parse_init_fields(self, kdl_nodes: list[KdlNode], parent: Init):
        for node in kdl_nodes:
            expr = InitField(parent=parent)
            self._parse_expressions(node.children, expr)
            parent.body.append(expr)

    def _parse_filter_expr(self, kdl_nodes: list[KdlNode], parent: Filter | LogicAnd | LogicNot | LogicOr):
        for node in kdl_nodes:
            if cb := self._context_filter.get(node.name):
                expr = cb(node, parent, self.ctx)
                if isinstance(expr, (LogicAnd, LogicOr, LogicNot)):
                    self._parse_filter_expr(node.children, expr)
                parent.body.append(expr)

    def _parse_assert_expr(self, kdl_nodes: list[KdlNode], parent: Assert | LogicAnd | LogicNot | LogicOr):
        for node in kdl_nodes:
            if cb := self._context_assert.get(node.name):
                expr = cb(node, parent, self.ctx)
                if isinstance(expr, (LogicAnd, LogicOr, LogicNot)):
                    self._parse_assert_expr(node.children, expr)
                parent.body.append(expr)

    def _parse_match_expr(self, kdl_nodes: list[KdlNode], parent: Match | LogicAnd | LogicNot | LogicOr):
        for node in kdl_nodes:
            if cb := self._context_match.get(node.name):
                expr = cb(node, parent, self.ctx)
                if isinstance(expr, (LogicAnd, LogicOr, LogicNot)):
                    self._parse_match_expr(node.children, expr)
                parent.body.append(expr)

    def _parse_expressions(
        self, kdl_nodes: list[KdlNode], parent: FieldLikeNode
    ):
        for node in kdl_nodes:
            if cb := self._context_expressions.get(node.name):
                expr = cb(node, parent, self.ctx)
                if isinstance(expr, Fallback):
                    continue
                elif isinstance(expr, Filter):
                    self._parse_filter_expr(node.children, expr)
                elif isinstance(expr, Assert):
                    self._parse_assert_expr(node.children, expr)
                elif isinstance(expr, Match):
                    self._parse_match_expr(node.children, expr)
                parent.body.append(expr)
        # auto add last expr - return
        last_ret = parent.body[-1].ret
        parent.body.append(Return(parent=parent, ret=last_ret, accept=last_ret))
        parent.ret = last_ret


PARSER = AstParser()


# contexts
@PARSER.register_module_context("define")
def reg_define(node: KdlNode, ctx: ParseContext):
    if node.children:
        ctx.children_defines[node.args[0]] = node.children
    else:
        pair = list(node.properties.items())[0]
        ctx.property_defines[pair[0]] = pair[1]


@PARSER.register_module_context("transform")
def reg_transform(node: KdlNode, ctx: ParseContext):
    ctx.transforms[node.args[0]] = node.children


@PARSER.register_module_node("struct")
def reg_module_struct(node: KdlNode, parent: Module, _: ParseContext):
    type_ = node.properties.get("type", "item")
    match type_:
        case "item":
            st_type = StructType.ITEM
        case "list":
            st_type = StructType.LIST
        case "table":
            st_type = StructType.TABLE
        case "dict":
            st_type = StructType.DICT
        case "flat":
            st_type = StructType.FLAT
        case _:
            raise UnknownNodeError(node.name, "Unknown struct type")
    expr = Struct(parent=parent, name=node.args[0], struct_type=st_type)
    return expr


# expressions layer


# selectors
@PARSER.register_expression_node("css")
def reg_expr_css(node: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    query = ctx.property_defines.get(node.args[0], node.args[0])
    query = cast(str, query)
    return CssSelect(parent=parent, query=query)


@PARSER.register_expression_node("css-all")
def reg_expr_css_all(node: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    query = ctx.property_defines.get(node.args[0], node.args[0])
    query = cast(str, query)
    return CssSelectAll(parent=parent, query=query)


@PARSER.register_expression_node("xpath")
def reg_expr_xpath(node: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    query = ctx.property_defines.get(node.args[0], node.args[0])
    query = cast(str, query)
    return XpathSelect(parent=parent, query=query)


@PARSER.register_expression_node("xpath-all")
def reg_expr_xpath_all(node: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    query = ctx.property_defines.get(node.args[0], node.args[0])
    query = cast(str, query)
    return XpathSelectAll(parent=parent, query=query)


@PARSER.register_expression_node("css-remove")
def reg_expr_css_remove(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext
):
    query = ctx.property_defines.get(node.args[0], node.args[0])
    query = cast(str, query)
    return CssRemove(parent=parent, query=query)


@PARSER.register_expression_node("xpath-remove")
def reg_expr_xpath_remove(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext
):
    query = ctx.property_defines.get(node.args[0], node.args[0])
    query = cast(str, query)
    return XpathRemove(parent=parent, query=query)


@PARSER.register_expression_node("text")
def reg_expr_extract_text(
    node: KdlNode, parent: FieldLikeNode, _: ParseContext
):
    prev_node = parent.body[-1]
    prev_type = prev_node.ret
    ret_type = (
        VariableType.LIST_STRING
        if prev_type == VariableType.LIST_DOCUMENT
        else VariableType.STRING
    )
    # cast:
    # DOCUMENT -> STRING
    # LIST_DOCUMENT -> LIST_STRING
    return Text(parent=parent, accept=prev_type, ret=ret_type)


@PARSER.register_expression_node("raw")
def reg_expr_extract_raw(node: KdlNode, parent: FieldLikeNode, _: ParseContext):
    prev_node = parent.body[-1]
    prev_type = prev_node.ret
    ret_type = (
        VariableType.LIST_STRING
        if prev_type == VariableType.LIST_DOCUMENT
        else VariableType.STRING
    )
    # cast:
    # DOCUMENT -> STRING
    # LIST_DOCUMENT -> LIST_STRING
    return Raw(parent=parent, accept=prev_type, ret=ret_type)


@PARSER.register_expression_node("attr")
def reg_expr_extract_attr(
    node: KdlNode, parent: FieldLikeNode, _: ParseContext
):
    prev_node = parent.body[-1]
    prev_type = prev_node.ret
    ret_type = (
        VariableType.LIST_STRING
        if prev_type == VariableType.LIST_DOCUMENT
        else VariableType.STRING
    )
    # cast:
    # DOCUMENT -> STRING
    # LIST_DOCUMENT -> LIST_STRING
    return Attr(parent=parent, accept=prev_type, ret=ret_type, keys=node.args)  # type: ignore


# string
@PARSER.register_expression_node("trim")
def reg_expr_trim(node: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    substr = ctx.property_defines.get(node.args[0], node.args[0])
    substr = cast(str, substr)
    # apologize, last type - STRING, LIST_STRING
    prev_type = parent.body[-1].ret
    return Trim(parent=parent, accept=prev_type, ret=prev_type, substr=substr)


@PARSER.register_expression_node("ltrim")
def reg_expr_ltrim(node: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    substr = ctx.property_defines.get(node.args[0], node.args[0])
    substr = cast(str, substr)
    # apologize, last type - STRING, LIST_STRING
    prev_type = parent.body[-1].ret
    return Ltrim(parent=parent, accept=prev_type, ret=prev_type, substr=substr)


@PARSER.register_expression_node("rtrim")
def reg_expr_rtrim(node: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    substr = ctx.property_defines.get(node.args[0], node.args[0])
    substr = cast(str, substr)
    # apologize, last type - STRING, LIST_STRING
    prev_type = parent.body[-1].ret
    return Rtrim(parent=parent, accept=prev_type, ret=prev_type, substr=substr)


@PARSER.register_expression_node("normalize-space")
def reg_expr_norm_space(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext
):
    # apologize, last type - STRING, LIST_STRING
    prev_type = parent.body[-1].ret
    return NormalizeSpace(parent=parent, accept=prev_type, ret=prev_type)


@PARSER.register_expression_node("rm-prefix")
def reg_expr_rm_prefix(node: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    # apologize, last type - STRING, LIST_STRING
    substr = ctx.property_defines.get(node.args[0], node.args[0])
    substr = cast(str, substr)
    prev_type = parent.body[-1].ret
    return RmPrefix(
        parent=parent, accept=prev_type, ret=prev_type, substr=substr
    )


@PARSER.register_expression_node("rm-suffix")
def reg_expr_rm_suffix(node: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    # apologize, last type - STRING, LIST_STRING
    substr = ctx.property_defines.get(node.args[0], node.args[0])
    substr = cast(str, substr)
    prev_type = parent.body[-1].ret
    return RmSuffix(
        parent=parent, accept=prev_type, ret=prev_type, substr=substr
    )


@PARSER.register_expression_node("rm-prefix-suffix")
def reg_expr_rm_prefix_suffix(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext
):
    # apologize, last type - STRING, LIST_STRING
    substr = ctx.property_defines.get(node.args[0], node.args[0])
    substr = cast(str, substr)
    prev_type = parent.body[-1].ret
    return RmPrefixSuffix(
        parent=parent, accept=prev_type, ret=prev_type, substr=substr
    )


@PARSER.register_expression_node("fmt")
def reg_expr_fmt(node: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    # apologize, last type - STRING, LIST_STRING
    tmpl = ctx.property_defines.get(node.args[0], node.args[0])
    tmpl = cast(str, tmpl)
    prev_type = parent.body[-1].ret
    return Fmt(parent=parent, accept=prev_type, ret=prev_type, template=tmpl)


@PARSER.register_expression_node("repl")
def reg_expr_repl(node: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    # apologize, last type - STRING, LIST_STRING
    prev_type = parent.body[-1].ret
    if node.children:
        items = {str(k): str(v) for k, v in node.properties.items()}
        return ReplMap(
            parent=parent, accept=prev_type, ret=prev_type, replacements=items
        )
    return Repl(
        parent=parent,
        accept=prev_type,
        ret=prev_type,
        old=node.args[0],
        new=node.args[1],
    )


@PARSER.register_expression_node("lower")
def reg_expr_lower(node: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    # apologize, last type - STRING, LIST_STRING
    prev_type = parent.body[-1].ret
    return Lower(parent=parent, accept=prev_type, ret=prev_type)


@PARSER.register_expression_node("upper")
def reg_expr_upper(node: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    # apologize, last type - STRING, LIST_STRING
    prev_type = parent.body[-1].ret
    return Upper(parent=parent, accept=prev_type, ret=prev_type)


@PARSER.register_expression_node("split")
def reg_expr_split(node: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    return Split(parent=parent, sep=node.args[0])


@PARSER.register_expression_node("join")
def reg_expr_join(node: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    return Join(parent=parent, sep=node.args[0])


@PARSER.register_expression_node("unescape")
def reg_expr_unescape(node: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    # apologize, last type - STRING, LIST_STRING
    prev_type = parent.body[-1].ret
    return Unescape(parent=parent, accept=prev_type, ret=prev_type)


# regex
@PARSER.register_expression_node("re")
def reg_expr_re(node: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    pattern = node.args[0]
    # TODO: extract groups, validate regex
    return Re(parent=parent, pattern=pattern)


@PARSER.register_expression_node("re-all")
def reg_expr_re_all(node: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    pattern = node.args[0]
    # TODO: extract groups, validate regex
    return ReAll(parent=parent, pattern=pattern)


@PARSER.register_expression_node("re-all")
def reg_expr_re_sub(node: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    # apologize, last type - STRING, LIST_STRING
    prev_type = parent.body[-1].ret
    pattern = node.args[0]
    # TODO: extract groups, validate regex
    return ReSub(
        parent=parent, accept=prev_type, ret=prev_type, pattern=pattern
    )


# array
@PARSER.register_expression_node("index")
def reg_expr_index(node: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    return Index(parent=parent, i=int(node.args[0]))


@PARSER.register_expression_node("first")
def reg_expr_first(_: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    return Index(parent=parent, i=0)


@PARSER.register_expression_node("last")
def reg_expr_last(_: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    return Index(parent=parent, i=-1)


@PARSER.register_expression_node("slice")
def reg_expr_slice(node: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    start, end = int(node.args[0]), int(node.args[1])
    return Slice(parent=parent, start=start, end=end)


@PARSER.register_expression_node("len")
def reg_expr_len(node: KdlNode, parent: FieldLikeNode, _: ParseContext):
    return Len(parent=parent)


@PARSER.register_expression_node("unique")
def reg_expr_unique(_: KdlNode, parent: FieldLikeNode, _2: ParseContext):
    return Unique(parent=parent)


@PARSER.register_expression_node("to-int")
def reg_expr_to_int(_: KdlNode, parent: FieldLikeNode, _2: ParseContext):
    # LIST_STRING | STRING
    prev_type = parent.body[-1].ret
    ret_type = (
        VariableType.LIST_INT
        if prev_type == VariableType.LIST_STRING
        else VariableType.INT
    )
    return ToInt(parent=parent, accept=prev_type, ret=ret_type)


@PARSER.register_expression_node("to-float")
def reg_expr_to_float(_: KdlNode, parent: FieldLikeNode, _2: ParseContext):
    # LIST_STRING | STRING
    prev_type = parent.body[-1].ret
    ret_type = (
        VariableType.LIST_INT
        if prev_type == VariableType.LIST_STRING
        else VariableType.INT
    )
    return ToFloat(parent=parent, accept=prev_type, ret=ret_type)


@PARSER.register_expression_node("to-bool")
def reg_expr_to_bool(_: KdlNode, parent: FieldLikeNode, _2: ParseContext):
    # AUTO, ANY
    prev_type = parent.body[-1].ret
    return ToBool(parent=parent, accept=prev_type)


@PARSER.register_expression_node("jsonify")
def reg_expr_jsonify(node: KdlNode, parent: FieldLikeNode, _2: ParseContext):
    target = node.args[0]
    if len(node.args) == 2:
        path = node.args[1]
    else:
        path = ""
    return Jsonify(parent=parent, schema_name=target, path=path)


@PARSER.register_expression_node("nested")
def reg_expr_nested(node: KdlNode, parent: FieldLikeNode, _2: ParseContext):
    return Nested(parent=parent, struct_name=node.args[0])


# control
@PARSER.register_expression_node("fallback")
def reg_expr_fallback(node: KdlNode, parent: FieldLikeNode, _: ParseContext):
    # apologize, this finish expr
    value = [] if not node.args else node.args[0]
    prev_type = parent.body[-1].ret
    # corner case: OPTIONAL TYPE
    if value is None:
        prev_type = prev_type.optional
    start_default = FallbackStart(parent=parent, value=value)
    end_default = FallbackEnd(parent=parent, value=value, accept=prev_type, ret=prev_type)
    parent.body.insert(0, start_default)
    parent.body.append(end_default)
    return Fallback(parent=parent, value=value)


@PARSER.register_expression_node("self")
def reg_expr_self(node: KdlNode, parent: FieldLikeNode, _: ParseContext):
    # 1. get init container
    struct = parent.parent
    struct = cast(Struct, struct)
    init_node = [i for i in struct.body if isinstance(i, Init)][0]
    # 2. find field with name
    init_field = [
        i
        for i in init_node.body
        if isinstance(i, InitField) and i.name == node.args[0]
    ][0]
    prev_type = init_field.ret
    return Self(
        parent=parent, accept=prev_type, ret=prev_type, name=node.args[0]
    )


@PARSER.register_expression_node("filter")
def reg_expr_filter(node: KdlNode, parent: FieldLikeNode, _: ParseContext):
    prev_type = parent.body[-1].ret
    return Filter(parent=parent, accept=prev_type, ret=prev_type)


@PARSER.register_expression_node("assert")
def reg_expr_assert(node: KdlNode, parent: FieldLikeNode, _: ParseContext):
    prev_type = parent.body[-1].ret
    return Assert(parent=parent, accept=prev_type, ret=prev_type)


@PARSER.register_expression_node("match")
def reg_expr_match(node: KdlNode, parent: FieldLikeNode, _: ParseContext):
    prev_type = parent.body[-1].ret
    return Assert(parent=parent, accept=prev_type, ret=prev_type)


# FILTER predicates
# CMP
@PARSER.register_predicate_node("eq")
def reg_filter_eq(node: KdlNode, parent: Filter, _: ParseContext):
    prev_type = parent.ret
    return PredEq(parent=parent, values=tuple(node.args), accept=prev_type, ret=prev_type)


@PARSER.register_predicate_node("ne")
def reg_filter_ne(node: KdlNode, parent: Filter, _: ParseContext):
    prev_type = parent.ret
    return PredNe(parent=parent, values=tuple(node.args), accept=prev_type, ret=prev_type)

@PARSER.register_predicate_node("gt")
def reg_filter_gt(node: KdlNode, parent: Filter, _: ParseContext):
    prev_type = parent.ret
    return PredGt(parent=parent, value=node.args[0], accept=prev_type, ret=prev_type)

@PARSER.register_predicate_node("lt")
def reg_filter_lt(node: KdlNode, parent: Filter, _: ParseContext):
    prev_type = parent.ret
    return PredLt(parent=parent, value=node.args[0], accept=prev_type, ret=prev_type)


@PARSER.register_predicate_node("ge")
def reg_filter_ge(node: KdlNode, parent: Filter, _: ParseContext):
    prev_type = parent.ret
    return PredGe(parent=parent, value=node.args[0], accept=prev_type, ret=prev_type)

@PARSER.register_predicate_node("le")
def reg_filter_le(node: KdlNode, parent: Filter, _: ParseContext):
    prev_type = parent.ret
    return PredLe(parent=parent, value=node.args[0], accept=prev_type, ret=prev_type)


@PARSER.register_predicate_node("range")
def reg_filter_range(node: KdlNode, parent: Filter, _: ParseContext):
    prev_type = parent.ret
    start, end = int(node.args[0]), int(node.args[1])
    return PredRange(parent=parent, start=start, end=end, accept=prev_type, ret=prev_type)

# string predicates
@PARSER.register_predicate_node("starts")
def reg_filter_starts(node: KdlNode, parent: Filter, _: ParseContext):
    prev_type = parent.ret
    return PredStarts(parent=parent, values=tuple(node.args), accept=prev_type, ret=prev_type)

@PARSER.register_predicate_node("ends")
def reg_filter_ends(node: KdlNode, parent: Filter, _: ParseContext):
    prev_type = parent.ret
    return PredEnds(parent=parent, values=tuple(node.args), accept=prev_type, ret=prev_type)

@PARSER.register_predicate_node("contains")
def reg_filter_contains(node: KdlNode, parent: Filter, _: ParseContext):
    prev_type = parent.ret
    return PredContains(parent=parent, values=tuple(node.args), accept=prev_type, ret=prev_type)

@PARSER.register_predicate_node("in")
def reg_filter_in(node: KdlNode, parent: Filter, _: ParseContext):
    prev_type = parent.ret
    return PredIn(parent=parent, values=tuple(node.args), accept=prev_type, ret=prev_type)


# regex
@PARSER.register_predicate_node("re")
def reg_filter_re(node: KdlNode, parent: Filter, _: ParseContext):
    pattern = node.args[0]
    prev_type = parent.ret
    return PredRe(parent=parent, pattern=pattern, accept=prev_type, ret=prev_type)


@PARSER.register_assert_node("re-all")
def reg_filter_re_all(node: KdlNode, parent: Filter, _: ParseContext):
    pattern = node.args[0]
    prev_type = parent.ret
    return PredReAny(parent=parent, pattern=pattern, accept=prev_type, ret=prev_type)


@PARSER.register_assert_node("re-any")
def reg_filter_re_any(node: KdlNode, parent: Filter, _: ParseContext):
    pattern = node.args[0]
    prev_type = parent.ret
    return PredReAll(parent=parent, pattern=pattern, accept=prev_type, ret=prev_type)


@PARSER.register_predicate_node("css", reg_match=False)
def reg_filter_css(node: KdlNode, parent: Filter, ctx: ParseContext):
    query = ctx.property_defines.get(node.args[0], node.args[0])
    query = cast(str, query)
    prev_type = parent.ret
    return PredCss(parent=parent, query=query, accept=prev_type, ret=prev_type)


@PARSER.register_predicate_node("xpath", reg_match=False)
def reg_filter_xpath(node: KdlNode, parent: Filter, ctx: ParseContext):
    query = ctx.property_defines.get(node.args[0], node.args[0])
    query = cast(str, query)
    prev_type = parent.ret
    return PredXpath(parent=parent, query=query, accept=prev_type, ret=prev_type)


@PARSER.register_predicate_node("has-attr", reg_match=False)
def reg_filter_has_attr(node: KdlNode, parent: Filter, ctx: ParseContext):
    attr_name = ctx.property_defines.get(node.args[0], node.args[0])
    attr_name = cast(str, attr_name)
    prev_type = parent.ret
    return PredHasAttr(parent=parent, name=attr_name, accept=prev_type, ret=prev_type)

# assert used only expr
@PARSER.register_assert_node("count")
def reg_assert_count(node: KdlNode, parent: Assert, _: ParseContext):
    prev_type = parent.ret
    op = node.args[0]
    value = int(node.args[1])
    match op:
        case "eq":
            return PredCountEq(parent=parent, value=value, accept=prev_type, ret=prev_type)
        case "gt":
            return PredCountGt(parent=parent, value=value, accept=prev_type, ret=prev_type)
        case "lt":
            return PredCountLt(parent=parent, value=value, accept=prev_type, ret=prev_type)
        case _:
            raise UnknownNodeError(node.name, "Unknown count predicate operator")
        
@PARSER.register_predicate_node("and")
def reg_filter_and(node: KdlNode, parent: Filter, _: ParseContext):
    prev_type = parent.ret
    return LogicAnd(parent=parent, accept=prev_type, ret=prev_type)


@PARSER.register_predicate_node("not")
def reg_filter_not(node: KdlNode, parent: Filter, _: ParseContext):
    prev_type = parent.ret
    return LogicNot(parent=parent, accept=prev_type, ret=prev_type)


@PARSER.register_predicate_node("or")
def reg_filter_or(node: KdlNode, parent: Filter, _: ParseContext):
    prev_type = parent.ret
    return LogicOr(parent=parent, accept=prev_type, ret=prev_type)

# transform (TODO)


if __name__ == "__main__":
    import pprint

    cfg = '''
-doc """
doc test 123
"""
 define A="test123"
 define B=100
 define TEST {
    css "a"
    attr "href"
 }

struct Demo {
    title {
        css "title"
        text
        fallback #null
    }

    urls {
        css-all "a"
        attr "href"
        filter {
            starts "http"
            not {
                starts "https"
                ends ".com"
            }
        }
        fallback {}
    }
}
'''
    pprint.pprint(PARSER.parse(cfg))
