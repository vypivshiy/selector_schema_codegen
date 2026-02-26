"""Parser for KDL schema to AST conversion.

This module demonstrates the visitor pattern for building AST
from KDL document structure.
"""

import re

from ssc_codegen.kdl.ckdl_types import parse, Document, Node
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
    Filter,
    Assert,
    TableMatch,
    StructTableConfig,
    StructTableMatchKey,
    StructTableMatchValue,
    StructTableRow,
    StructSplit,
    StructField,
    StructInit,
    TypeDef,
    TypeDefField
)
from ssc_codegen.kdl.tokens import VariableType
from typing import Any, TypeVar, TypedDict, cast

import pprint

T_KWARGS = TypeVar("T_KWARGS", bound=TypedDict)
T_ARGS = TypeVar("T_ARGS", bound=tuple)
T_NODE_PARENT = TypeVar("T_NODE_PARENT", bound=BaseAstNode[T_KWARGS, T_ARGS])

# TODO: impl other

def build_expressions(
    nodes: list[Node], defines: dict[str, Any], field: T_NODE_PARENT
):
    cursor_type = VariableType.DOCUMENT  # always first type
    for node in nodes:
        match node.name:
            # selectors
            case "css" | "css-all" | "xpath" | "xpath-all":
                mode = "css" if node.name.startswith("css") else "xpath"
                ret_type = VariableType.LIST_DOCUMENT if node.name.endswith("-all") else VariableType.DOCUMENT
                expr = Select(
                    kwargs={"mode": mode, "query": node.args[0]},
                    parent=field,
                    ret_type=ret_type
                )
                field.body.append(expr)
                cursor_type = expr.ret_type
            case "text" | "raw" | "attr":
                keys = tuple(node.args) if node.name == "attr" else None
                ret_type = (
                    VariableType.LIST_STRING
                    if cursor_type == VariableType.LIST_DOCUMENT
                    else VariableType.STRING
                )
                expr = Extract(
                    kwargs={"mode": node.name, "key": keys},
                    accept_type=cursor_type,
                    ret_type=ret_type,
                    parent=field
                )
                field.body.append(expr)
                cursor_type = expr.ret_type
            case "css-remove" | "xpath-remove":
                mode = "css" if node.name.startswith("css") else "xpath"
                expr = Remove(kwargs={"mode": mode, "query": node.args[0]}, parent=field)
                field.body.append(expr)
                cursor_type = expr.ret_type
            # string
            case ("trim" | "ltrim" | "rtrim"
                  | "rm-prefix" | "rm-suffix" | "rm-prefix-suffix"
                ):
                # type: LIST_STRING, STRING
                # todo: optimize definitions: move to classvars after generate
                substr = defines.get(node.args[0], node.args[0])  
                expr = StringOp(parent=field,
                                accept_type=cursor_type,
                                ret_type=cursor_type,
                                kwargs={'op': node.name, "substr": substr})  # type: ignore
                field.body.append(expr)
                cursor_type = expr.ret_type
            case "fmt":
                fmt = defines.get(node.args[0], node.args[0])
                expr = Format(accept_type=cursor_type, 
                              ret_type=cursor_type,
                              kwargs={'fmt': fmt})
                field.body.append(expr)
                cursor_type = expr.ret_type
            case "re" | "re-all" | "re-sub":
                # Regex
                # TODO: unpack regex flags, convert to inline
                pattern = node.args[0]
                 # re-sub
                repl = node.args[1] if node.name == 're-sub' else None
                if node.name == 're-all':
                    accept_type = VariableType.STRING
                    ret_type = VariableType.LIST_STRING
                elif node.name == 're':
                    accept_type = VariableType.STRING
                    ret_type = VariableType.STRING
                else: # re-sub
                    accept_type = cursor_type
                    ret_type = cursor_type

                expr = Regex(accept_type=accept_type, ret_type=ret_type, parent=field,
                             kwargs={'pattern': pattern, 'mode':node.name, 'repl': repl})
                field.body.append(expr)
                cursor_type=ret_type
            case "repl":
                if node.children:
                    expr = ReplaceMap(accept_type=cursor_type, ret_type=cursor_type, parent=field, 
                                      kwargs={'repl': {n.name: n.args[0] for n in node.children}})
                else:
                    expr = Replace(accept_type=cursor_type, ret_type=cursor_type, parent=field,
                                   kwargs={'old': node.args[0], 'new': node.args[1]})
                field.body.append(expr)
                cursor_type=expr.ret_type
            case 'to-int':
                ret_type = VariableType.LIST_INT if cursor_type == VariableType.LIST_STRING else VariableType.INT
                expr = Cast(accept_type=cursor_type, ret_type=ret_type, parent=field, kwargs={'target':'int'})
                field.body.append(expr)
                cursor_type=ret_type
            case "to-float":
                ret_type = VariableType.LIST_FLOAT if cursor_type == VariableType.LIST_STRING else VariableType.FLOAT
                expr = Cast(accept_type=cursor_type, ret_type=ret_type, parent=field, kwargs={'target':'float'})
                field.body.append(expr)
                cursor_type=ret_type
            case 'to-bool':
                ret_type = VariableType.BOOL
                expr = Cast(accept_type=cursor_type, ret_type=ret_type, parent=field, kwargs={'target':'bool'})
                field.body.append(expr)
                cursor_type=ret_type
            case "jsonify":
                ret_type = VariableType.JSON
                if not node.args:
                    kwargs = {'target': None, 'path': None}
                elif len(node.args) == 1:
                    kwargs = {'target': node.args[0], 'path': None}
                else:
                    kwargs = {'target': node.args[0], 'path': node.args[1]}
                expr = Jsonify(parent=field,
                               kwargs=kwargs)
                field.body.append(expr)
                cursor_type=expr.ret_type
            case "nested":
                expr = Nested(parent=field, kwargs={"target": node.args[0]})
                field.body.append(expr)
                cursor_type=expr.ret_type
            case "join":
                expr = Join(parent=field, kwargs={"sep": node.args[0]})
                field.body.append(expr)
                cursor_type=expr.ret_type
            case "unescape":
                expr = Unescape(parent=field, accept_type=cursor_type)
                field.body.append(expr)
                cursor_type=expr.ret_type
            # array
            case "index" | "first" | "last":
                match cursor_type:
                    case VariableType.LIST_STRING:
                        ret_type = VariableType.STRING
                    case VariableType.LIST_DOCUMENT:
                        ret_type = VariableType.DOCUMENT
                    case VariableType.LIST_INT:
                        ret_type = VariableType.INT
                    case VariableType.LIST_FLOAT:
                        ret_type = VariableType.FLOAT
                    case _:
                        ret_type = VariableType.STRING  # TODO

                if node.name == "first":
                    expr = Index(parent=field, kwargs={'index': 0}, ret_type=ret_type)
                elif node.name == "last":
                    expr = Index(parent=field, kwargs={'index': -1}, ret_type=ret_type)
                else:
                    index = int(node.args[0])
                    expr = Index(parent=field, kwargs={'index': index}, ret_type=ret_type)
                field.body.append(expr)
                cursor_type=ret_type
            case "len":
                # todo: test generic list
                expr = Len(parent=field, accept_type=cursor_type)
                field.body.append(expr)
                cursor_type=expr.ret_type
            case "unique":
                keep_order = node.properties.get("keep-order", False)
                expr=Unique(parent=field, kwargs={'keep_order': keep_order}, accept_type=cursor_type, ret_type=cursor_type)
                field.body.append(expr)
            case "transform":
                pass
            case "default":
                # empty array default shortcut
                if node.children:  # empty node `default {}`
                    value = []
                else:
                    value = node.args[0]
                expr_start = DefaultStart(parent=field, kwargs={'value': value})
                field.body.insert(0, expr_start)
                expr_end = DefaultEnd(parent=field, kwargs={'value': value})
                field.body.append(expr_end)
            case "filter":
                expr = Filter(parent=field, accept_type=cursor_type, ret_type=cursor_type)
                # TODO builder func, fill expr.body (node.children)
                field.body.append(expr)
            case "assert":
                expr = Assert(parent=field, accept_type=cursor_type, ret_type=cursor_type)
                # TODO builder func, fill expr.body (node.children)
                field.body.append(expr)
            # table expr
            case "match":
                expr = TableMatch(parent=field)
                # TODO builder func, fill expr.body (node.children)
                field.body.append(expr)
                cursor_type=expr.ret_type
            case _:
                raise NotImplementedError(node.name, node.args, node.properties, node.children)
    # add return expr
    expr = Return(parent=field, accept_type=cursor_type, ret_type=cursor_type)
    field.ret_type=cursor_type
    field.body.append(expr)

def build_struct(
    nodes: list[Node], defines: dict[str, Any], struct: Struct
) -> None:
    # generic
    field_init = StructInit(parent=struct)
    struct.body.append(field_init)

    for node in nodes:
        match node.name:
            case "-doc":
                struct.kwargs["docstring"] = node.args[0]
            # validate func, wout modify document
            case "-pre-validate":
                field = StructPreValidate(parent=struct)
                build_expressions(node.children, defines, field)
                field.ret_type = VariableType.NULL  
                struct.body.append(field)
            # struct type=list|dict specific
            case "-split-doc":
                field = StructSplit(parent=struct)
                build_expressions(node.children, defines, field)
                struct.body.append(field)
            # struct type=dict specific
            case "-key":
                field = StructField(parent=struct, kwargs={'name': 'key'})
                build_expressions(node.children, defines, field)
                struct.body.append(field)
            # struct type=dict specific
            case "-value":
                if struct.kwargs['struct_type'] == 'table':
                    field = StructTableMatchValue(parent=struct)
                else:
                    field = StructField(parent=struct, kwargs={'name': 'value'})
                build_expressions(node.children, defines, field)
                struct.body.append(field)
            # struct type=table specific
            case "-table":
                field = StructTableConfig(parent=struct)
                build_expressions(node.children, defines, field)
                struct.body.append(field)
            # struct type=table specific
            case "-row":
                field = StructTableRow(parent=struct)
                build_expressions(node.children, defines, field)
                struct.body.append(field)
            # struct type=table specific
            case "-match":
                field = StructTableMatchKey(parent=struct)
                build_expressions(node.children, defines, field)
                struct.body.append(field)
            # other fields
            case _:
                field = StructField(parent=struct, kwargs={'name': node.name})
                build_expressions(node.children, defines, field)
                struct.body.append(field)


def typedef_from_struct(struct: Struct) -> TypeDef:
    is_array = struct.kwargs['struct_type'] in ('list', 'table')
    
    typedef = TypeDef(kwargs={'is_array': is_array})
    for field in struct.body:
        if field.kind != StructField.kind:
            continue
        field = cast(StructField, field)
        field_name = field.kwargs['name']
        # reference type from return expr
        if field.ret_type == VariableType.NESTED:
            nested_node = field.find_by_token(Nested.kind)
            nested_node = cast(Nested, nested_node)
            typedef.body.append(TypeDefField(ret_type=field.ret_type, parent=typedef, 
                                             kwargs={"name": field_name, 'nested_ref': nested_node.kwargs['target'], 'json_ref': None}))
        elif field.ret_type == VariableType.JSON:
            raise NotImplementedError()  # TODO: JSON REF IMPL
        else:
            typedef.body.append(TypeDefField(ret_type=field.ret_type, parent=typedef, kwargs={'name': field_name, 'nested_ref': None, 'json_ref': None}))
    return typedef

def build_module(document: Document) -> Module:
    module = Module()
    defines = {}
    typedefs, structs = [], []
    module.body.extend([Docstring(parent=module), Imports(parent=module), Utilities(parent=module)])
    for node in document.nodes:
        match node.name:
            # defined, skip
            case "doc":
                module.body[0].kwargs['value'] = node.args[0]
            case "define":
                key, value = list(node.properties.items())[0]
                # todo: check if already defined
                defines[key] = value
            case "struct":
                type_ = node.properties.get("type", "item")
                struct = Struct(
                    parent=module,
                    kwargs={"name": node.args[0], "struct_type": type_},
                )
                build_struct(node.children, defines, struct)
                structs.append(struct)
                # generate structure for generate static types or annotations
                typedef = typedef_from_struct(struct)
                typedef.parent = module
                typedefs.append(typedef)
            case _:
                raise Exception(
                    "Not impl:",
                    node.name,
                    node.args,
                    node.properties,
                    node.children,
                )
    # 1. typedefs insert first , second - structs
    module.body.extend(typedefs)
    module.body.extend(structs)
    return module


def parse_ast() -> Module:
    """
    Parse KDL document and build AST module.

    Returns:
        Module AST node with all top-level definitions.
    """
    document = parse('''
// define module docstring
doc """
example config parser for books.toscrape shop
"""

// constants (passed to expression)
// {{}} placeholder replaced to target language equalent
define FMT_URL="https://books.toscrape.com/catalogue/{{}}"
define FMT_BASE="https://books.toscrape.com/{{}}"
define FMT_URL_CURRENT="https://books.toscrape.com/catalogue/page-{{}}.html"
                  
struct MainCatalogue type=item {
    -doc """
    test123 doc
    abcdef
    """
    -pre-validate {
                     css a
                     attr href
                     }
    title {
     css title
     text                             
    }
                     
    title-len {
     css title
     text
     to-int                         
    }
                    
}
''')
    return build_module(document)


if __name__ == "__main__":
    module = parse_ast()
    pprint.pprint(module, indent=2, sort_dicts=False, width=160)
