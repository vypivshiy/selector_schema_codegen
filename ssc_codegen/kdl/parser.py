"""Parser for KDL schema to AST conversion.

Simplified functional implementation - no flexibility needed at AST construction stage.
"""

from ssc_codegen.kdl.ckdl_types import Document, Node
from ssc_codegen.kdl.ast import (
    Module,
    Imports,
    Utilities,
    Docstring,
    Struct,
    BaseAstNode,
    StructPreValidate,
    Select,
    Extract,
    Remove,
    StringOp,
    Format,
    Regex,
    Cast,
    Replace,
    ReplaceMap,
    Jsonify,
    Nested,
    Unescape,
    Join,
    Len,
    Unique,
    Index,
    DefaultStart,
    DefaultEnd,
    Return,
    TableMatch,
    StructTableConfig,
    StructTableMatchKey,
    StructTableMatchValue,
    StructTableRow,
    StructSplit,
    StructField,
    StructInit,
    TypeDef,
    TypeDefField,
    # filter containers
    LogicAnd,
    LogicNot,
    LogicOr,

    # filter exprs (str)
    Filter,
    FilterCmp,
    FilterStr,
    FilterRe,
    FilterRange,
    # filter exprs (DOCUMENT)
    FilterDoc,
    FilterDocSelect,
    FilterDocAttr,
    FilterDocText,
    FilterDocRaw,
    FilterDocHasAttr,
    # assert exprs (GENERIC)
    Assert,
    AssertCmp,
    AssertContains,
    AssertHasAttr,
    AssertRe,
    AssertSelect
)
from ssc_codegen.kdl.tokens import VariableType, TokenType
from typing import Any, cast


# =============================================================================
# EXPRESSION BUILDERS - Direct, no flexibility
# =============================================================================

def _make_select(node: Node, parent: BaseAstNode) -> tuple[Select, VariableType]:
    """Build Select node - always returns DOCUMENT or LIST_DOCUMENT."""
    is_all = node.name.endswith("-all")
    mode = "css" if node.name.startswith("css") else "xpath"
    ret_type = VariableType.LIST_DOCUMENT if is_all else VariableType.DOCUMENT
    
    expr = Select(
        kwargs={"mode": mode, "query": node.args[0]},
        parent=parent,
        ret_type=ret_type,
    )
    return expr, ret_type


def _make_extract(node: Node, parent: BaseAstNode, cursor: VariableType) -> tuple[Extract, VariableType]:
    """Build Extract node - TEXT/RAW/ATTR."""
    keys = tuple(node.args) if node.name == "attr" else None
    ret_type = VariableType.LIST_STRING if cursor == VariableType.LIST_DOCUMENT else VariableType.STRING
    
    expr = Extract(
        kwargs={"mode": node.name, "key": keys},
        accept_type=cursor,
        ret_type=ret_type,
        parent=parent,
    )
    return expr, ret_type


def _make_remove(node: Node, parent: BaseAstNode) -> Remove:
    """Build Remove node."""
    mode = "css" if node.name.startswith("css") else "xpath"
    return Remove(kwargs={"mode": mode, "query": node.args[0]}, parent=parent)


def _make_string_op(node: Node, parent: BaseAstNode, cursor: VariableType, defines: dict) -> tuple[StringOp, VariableType]:
    """Build StringOp node - TRIM/LTRIM/RTRIM/RM-PREFIX/etc."""
    substr = defines.get(node.args[0], node.args[0])
    return (
        StringOp(
            parent=parent,
            accept_type=cursor,
            ret_type=cursor,
            kwargs={"op": node.name, "substr": substr},
        ),
        cursor,
    )


def _make_format(node: Node, parent: BaseAstNode, cursor: VariableType, defines: dict) -> tuple[Format, VariableType]:
    """Build Format node."""
    fmt = defines.get(node.args[0], node.args[0])
    expr = Format(accept_type=cursor, ret_type=cursor, kwargs={"fmt": fmt}, parent=parent)
    return expr, cursor


def _make_regex(node: Node, parent: BaseAstNode, cursor: VariableType) -> tuple[Regex, VariableType]:
    """Build Regex node - RE/RE-ALL/RE-SUB."""
    pattern = node.args[0]
    repl = node.args[1] if node.name == "re-sub" else None
    
    if node.name == "re-all":
        accept_type = VariableType.STRING
        ret_type = VariableType.LIST_STRING
    elif node.name == "re":
        accept_type = VariableType.STRING
        ret_type = VariableType.STRING
    else:  # re-sub
        accept_type = cursor
        ret_type = cursor

    return (
        Regex(
            accept_type=accept_type,
            ret_type=ret_type,
            parent=parent,
            kwargs={"mode": node.name, "pattern": pattern, "repl": repl},
        ),
        ret_type,
    )


def _make_replace(node: Node, parent: BaseAstNode, cursor: VariableType) -> tuple[Replace | ReplaceMap, VariableType]:
    """Build Replace or ReplaceMap node."""
    if node.children:
        repl_dict = {n.name: n.args[0] for n in node.children}
        return (
            ReplaceMap(accept_type=cursor, ret_type=cursor, parent=parent, kwargs={"repl": repl_dict}),
            cursor,
        )
    else:
        return (
            Replace(accept_type=cursor, ret_type=cursor, parent=parent, kwargs={"old": node.args[0], "new": node.args[1]}),
            cursor,
        )


def _make_cast(node: Node, parent: BaseAstNode, cursor: VariableType) -> tuple[Cast, VariableType]:
    """Build Cast node - TO-INT/TO-FLOAT/TO-BOOL."""
    target = node.name.replace("to-", "")  # "to-int" -> "int"
    
    if target == "int":
        ret_type = VariableType.LIST_INT if cursor == VariableType.LIST_STRING else VariableType.INT
    elif target == "float":
        ret_type = VariableType.LIST_FLOAT if cursor == VariableType.LIST_STRING else VariableType.FLOAT
    else:  # bool
        ret_type = VariableType.BOOL

    return (
        Cast(accept_type=cursor, ret_type=ret_type, parent=parent, kwargs={"target": target}),
        ret_type,
    )


def _make_jsonify(node: Node, parent: BaseAstNode) -> tuple[Jsonify, VariableType]:
    """Build Jsonify node."""
    if not node.args:
        kwargs = {"target": None, "path": None}
    elif len(node.args) == 1:
        kwargs = {"target": node.args[0], "path": None}
    else:
        kwargs = {"target": node.args[0], "path": node.args[1]}
    
    return Jsonify(parent=parent, kwargs=kwargs), VariableType.JSON


def _make_nested(node: Node, parent: BaseAstNode) -> tuple[Nested, VariableType]:
    """Build Nested node."""
    return Nested(parent=parent, kwargs={"target": node.args[0]}), VariableType.NESTED


def _make_join(node: Node, parent: BaseAstNode) -> tuple[Join, VariableType]:
    """Build Join node."""
    return Join(parent=parent, kwargs={"sep": node.args[0]}), VariableType.STRING


def _make_unescape(node: Node, parent: BaseAstNode, cursor: VariableType) -> tuple[Unescape, VariableType]:
    """Build Unescape node."""
    return Unescape(parent=parent, accept_type=cursor), VariableType.STRING


def _make_index(node: Node, parent: BaseAstNode, cursor: VariableType) -> tuple[Index, VariableType]:
    """Build Index node - INDEX/FIRST/LAST."""
    # Determine ret_type from cursor
    if cursor == VariableType.LIST_STRING:
        ret_type = VariableType.STRING
    elif cursor == VariableType.LIST_DOCUMENT:
        ret_type = VariableType.DOCUMENT
    elif cursor == VariableType.LIST_INT:
        ret_type = VariableType.INT
    elif cursor == VariableType.LIST_FLOAT:
        ret_type = VariableType.FLOAT
    else:
        ret_type = VariableType.STRING

    if node.name == "first":
        index = 0
    elif node.name == "last":
        index = -1
    else:
        index = int(node.args[0])

    return Index(parent=parent, kwargs={"index": index}, ret_type=ret_type), ret_type


def _make_len(node: Node, parent: BaseAstNode, cursor: VariableType) -> tuple[Len, VariableType]:
    """Build Len node."""
    return Len(parent=parent, accept_type=cursor), VariableType.INT


def _make_unique(node: Node, parent: BaseAstNode, cursor: VariableType) -> tuple[Unique, VariableType]:
    """Build Unique node."""
    keep_order = node.properties.get("keep-order", False)
    return (
        Unique(parent=parent, kwargs={"keep_order": keep_order}, accept_type=cursor, ret_type=cursor),
        cursor,
    )


def _make_default(node: Node, parent: BaseAstNode) -> tuple[DefaultStart, DefaultEnd, VariableType]:
    """Build Default nodes - returns start and end expressions."""
    if node.children:
        value = []
    else:
        value = node.args[0]
    
    expr_start = DefaultStart(parent=parent, kwargs={"value": value})
    expr_end = DefaultEnd(parent=parent, kwargs={"value": value})
    return expr_start, expr_end, VariableType.ANY


def _make_filter_expr(nodes: list[Node], parent: Filter | LogicAnd | LogicOr | LogicNot) -> None:
    for node in nodes:
        # LIST_STRING | LIST_DOCUMENT
        if node.name in ("starts", "ends", "contains", "in"):
            expr = FilterStr(parent=parent, kwargs={'op': node.name, 'values': node.args})
            parent.body.append(expr)
        elif node.name in ("eq", "ne", "gt", "le", "ge", "le"):
            expr = FilterCmp(parent=parent, kwargs={'op': node.name, 'value': node.args})
            parent.body.append(expr)
        elif node.name == "re":
            # TODO regex compile
            expr = FilterRe(parent=parent, kwargs={'pattern': node.args[0], 'ignore_case': False, 'dotall': False})
            parent.body.append(expr)
        elif node.name == "range":
            # TODO: validate
            start, end = node.args  
            expr = FilterRange(parent=parent, kwargs={'start': int(start), 'end': int(end)})
            parent.body.append(expr)
        # recursive insert exprs
        elif node.name == "and":
            expr = LogicAnd(parent=parent)
            _make_filter_expr(node.children, expr)
            parent.body.append(expr)
        elif node.name == "or":
            expr = LogicOr(parent=parent)
            _make_filter_expr(node.children, expr)
            parent.body.append(expr)
        elif node.name == "not":
            expr = LogicNot(parent=parent)
            _make_filter_expr(node.children, expr)
            parent.body.append(expr)
        else:
            raise NotImplementedError(node.name)
            


def _make_filter(node: Node, parent: BaseAstNode, cursor: VariableType) -> tuple[Filter, VariableType]:
    """Build Filter node. LIST_STR"""
    expr = Filter(parent=parent, accept_type=cursor, ret_type=cursor)
    _make_filter_expr(node.children, expr)
    return expr, cursor


def _make_assert_expr(nodes: list[Node], parent: Assert | LogicNot):
    # TODO: check context parent.accept_type (STRING, DOCUMENT, LIST_STRING?)
    for node in nodes:
        # TODO: message API
        # STRING ONLY (TODO eq, ne op only)
        if node.name in ("eq", "ne", "gt", "le", "ge", "le"):
            expr = AssertCmp(parent=parent, kwargs={'op': node.name, 'value': node.args[0], 'msg': ''})
            parent.body.append(expr)
        elif node.name == 'contains':
            expr = AssertContains(parent=parent, kwargs={'value': node.args[0], 'msg': ''})
            parent.body.append(expr)
        # re-any, re-all for LIST_STRING
        elif node.name in ('re', 're-any', 're-all'):
            #TODO: regex check
            expr = AssertRe(parent=parent, kwargs={'op': node.name, 'pattern': node.args[0], 'ignore_case':False, 'dotall': False, 'msg': ''})
            parent.body.append(expr)
        # DOCUMENT ONLY
        elif node.name == 'attr':
            expr = AssertHasAttr(parent=parent, kwargs={'name': node.args[0], 'msg': ''})
            parent.body.append(expr)
        elif node.name in ('css', 'xpath'):
            expr = AssertSelect(parent=parent, kwargs={'mode': node.name, 'query': node.args[0], msg: ''})
            parent.body.append(expr)
        # currently used invert only operator
        elif node.name == 'not':
            expr = LogicNot(parent=parent)
            _make_assert_expr(node.children, expr)
        else:
            raise NotImplementedError(node.name)

def _make_assert(node: Node, parent: BaseAstNode, cursor: VariableType) -> tuple[Assert, VariableType]:
    """Build Assert node."""
    expr = Assert(parent=parent, accept_type=cursor, ret_type=cursor)
    _make_assert_expr(node.children, expr)
    return expr, cursor

def _make_table_match(node: Node, parent: BaseAstNode) -> tuple[TableMatch, VariableType]:
    """Build TableMatch node."""
    return TableMatch(parent=parent), VariableType.DOCUMENT



# =============================================================================
# MAIN BUILDERS
# =============================================================================

def build_expressions(nodes: list[Node], defines: dict[str, Any], field: BaseAstNode) -> None:
    """Build expression chain for a field.
    
    Simplified: directly builds AST without flexible type inference.
    """
    cursor_type = VariableType.DOCUMENT  # always start with document
    
    for node in nodes:
        # SELECTORS
        if node.name in ("css", "css-all", "xpath", "xpath-all"):
            expr, cursor_type = _make_select(node, field)
            field.body.append(expr)
            
        # EXTRACT
        elif node.name in ("text", "raw", "attr"):
            expr, cursor_type = _make_extract(node, field, cursor_type)
            field.body.append(expr)
            
        # REMOVE
        elif node.name in ("css-remove", "xpath-remove"):
            expr = _make_remove(node, field)
            field.body.append(expr)
            
        # STRING OPS
        elif node.name in ("trim", "ltrim", "rtrim", "rm-prefix", "rm-suffix", "rm-prefix-suffix"):
            expr, cursor_type = _make_string_op(node, field, cursor_type, defines)
            field.body.append(expr)
            
        # FORMAT
        elif node.name == "fmt":
            expr, cursor_type = _make_format(node, field, cursor_type, defines)
            field.body.append(expr)
            
        # REGEX
        elif node.name in ("re", "re-all", "re-sub"):
            expr, cursor_type = _make_regex(node, field, cursor_type)
            field.body.append(expr)
            
        # REPLACE
        elif node.name == "repl":
            expr, cursor_type = _make_replace(node, field, cursor_type)
            field.body.append(expr)
            
        # CAST
        elif node.name in ("to-int", "to-float", "to-bool"):
            expr, cursor_type = _make_cast(node, field, cursor_type)
            field.body.append(expr)
            
        # JSONIFY
        elif node.name == "jsonify":
            expr, cursor_type = _make_jsonify(node, field)
            field.body.append(expr)
            
        # NESTED
        elif node.name == "nested":
            expr, cursor_type = _make_nested(node, field)
            field.body.append(expr)
            
        # JOIN
        elif node.name == "join":
            expr, cursor_type = _make_join(node, field)
            field.body.append(expr)
            
        # UNESCAPE
        elif node.name == "unescape":
            expr, cursor_type = _make_unescape(node, field, cursor_type)
            field.body.append(expr)
            
        # INDEX
        elif node.name in ("index", "first", "last"):
            expr, cursor_type = _make_index(node, field, cursor_type)
            field.body.append(expr)
            
        # LEN
        elif node.name == "len":
            expr, cursor_type = _make_len(node, field, cursor_type)
            field.body.append(expr)
            
        # UNIQUE
        elif node.name == "unique":
            expr, cursor_type = _make_unique(node, field, cursor_type)
            field.body.append(expr)
            
        # DEFAULT
        elif node.name == "default":
            expr_start, expr_end, _ = _make_default(node, field)
            field.body.insert(0, expr_start)
            field.body.append(expr_end)
            
        # FILTER
        elif node.name == "filter":
            expr, cursor_type = _make_filter(node, field, cursor_type)
            field.body.append(expr)
            # TODO: filter build
            
        # ASSERT
        elif node.name == "assert":
            expr, cursor_type = _make_assert(node, field, cursor_type)
            field.body.append(expr)
            # TODO: assert build
            
        # TABLE MATCH
        elif node.name == "match":
            expr, cursor_type = _make_table_match(node, field)
            field.body.append(expr)
            # TODO: match build

        # UNKNOWN
        else:
            raise NotImplementedError(node.name)

    # Always add return expression
    ret_expr = Return(parent=field, accept_type=cursor_type, ret_type=cursor_type)
    field.ret_type = cursor_type
    field.body.append(ret_expr)


def build_struct(nodes: list[Node], defines: dict[str, Any], struct: Struct) -> None:
    """Build struct AST from KDL nodes.
    
    Simplified: direct mapping without flexibility.
    """
    # Generic init
    field_init = StructInit(parent=struct)
    struct.body.append(field_init)

    for node in nodes:
        # DOCSTRING
        if node.name == "-doc":
            struct.kwargs["docstring"] = node.args[0]
            
        # PRE-VALIDATE
        elif node.name == "-pre-validate":
            field = StructPreValidate(parent=struct)
            build_expressions(node.children, defines, field)
            field.ret_type = VariableType.NULL
            struct.body.append(field)
            
        # SPLIT DOC
        elif node.name == "-split-doc":
            field = StructSplit(parent=struct)
            build_expressions(node.children, defines, field)
            struct.body.append(field)
            
        # KEY
        elif node.name == "-key":
            field = StructField(parent=struct, kwargs={"name": "key"})
            build_expressions(node.children, defines, field)
            struct.body.append(field)
            
        # VALUE
        elif node.name == "-value":
            if struct.kwargs["struct_type"] == "table":
                field = StructTableMatchValue(parent=struct)
            else:
                field = StructField(parent=struct, kwargs={"name": "value"})
            build_expressions(node.children, defines, field)
            struct.body.append(field)
            
        # TABLE CONFIG
        elif node.name == "-table":
            field = StructTableConfig(parent=struct)
            build_expressions(node.children, defines, field)
            struct.body.append(field)
            
        # TABLE ROW
        elif node.name == "-row":
            field = StructTableRow(parent=struct)
            build_expressions(node.children, defines, field)
            struct.body.append(field)
            
        # TABLE MATCH KEY
        elif node.name == "-match":
            field = StructTableMatchKey(parent=struct)
            build_expressions(node.children, defines, field)
            struct.body.append(field)
            
        # REGULAR FIELD
        else:
            field = StructField(parent=struct, kwargs={"name": node.name})
            build_expressions(node.children, defines, field)
            struct.body.append(field)


def typedef_from_struct(struct: Struct) -> TypeDef:
    """Convert struct to TypeDef - simplified direct conversion."""
    is_array = struct.kwargs["struct_type"] in ("list", "table")
    typedef = TypeDef(kwargs={"is_array": is_array})
    
    for field in struct.body:
        if field.kind != StructField.kind:
            continue
        
        field_name = field.kwargs["name"]
        
        if field.ret_type == VariableType.NESTED:
            nested_node = field.find_by_token(TokenType.NESTED)
            typedef.body.append(
                TypeDefField(
                    ret_type=field.ret_type,
                    parent=typedef,
                    kwargs={
                        "name": field_name,
                        "nested_ref": nested_node.kwargs["target"],
                        "json_ref": None,
                    },
                )
            )
        elif field.ret_type == VariableType.JSON:
            raise NotImplementedError("JSON REF not implemented")
        else:
            typedef.body.append(
                TypeDefField(
                    ret_type=field.ret_type,
                    parent=typedef,
                    kwargs={
                        "name": field_name,
                        "nested_ref": None,
                        "json_ref": None,
                    },
                )
            )
    
    return typedef


def build_module(document: Document) -> Module:
    """Build Module AST from KDL document.
    
    Simplified: direct top-level processing.
    """
    module = Module()
    defines = {}
    typedefs: list[TypeDef] = []
    structs: list[Struct] = []
    
    # Standard header
    module.body.extend([
        Docstring(parent=module),
        Imports(parent=module),
        Utilities(parent=module),
    ])
    
    for node in document.nodes:
        # DOCSTRING
        if node.name == "doc":
            module.body[0].kwargs["value"] = node.args[0]
            
        # DEFINE
        elif node.name == "define":
            key, value = list(node.properties.items())[0]
            defines[key] = value
            
        # STRUCT
        elif node.name == "struct":
            type_ = node.properties.get("type", "item")
            struct = Struct(
                parent=module,
                kwargs={"name": node.args[0], "struct_type": type_},
            )
            build_struct(node.children, defines, struct)
            structs.append(struct)
            
            # Generate typedef
            typedef = typedef_from_struct(struct)
            typedef.parent = module
            typedefs.append(typedef)
            
        # UNKNOWN
        else:
            raise Exception("Not impl:", node.name, node.args, node.properties, node.children)
    
    # Add typedefs first, then structs
    module.body.extend(typedefs)
    module.body.extend(structs)
    
    return module


def parse_ast(document: Document) -> Module:
    """Entry point - parse KDL document to AST."""
    return build_module(document)
