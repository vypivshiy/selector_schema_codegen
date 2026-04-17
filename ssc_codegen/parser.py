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

Frontend: tree-sitter KDL parse tree
Expected KdlNode interface:
    node.name        : str
    node.args        : list
    node.properties  : dict
    node.children    : list[KdlNode]
    node.has_children: bool
"""

from __future__ import annotations

import ast as _py_ast
import re as _re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, TypeAlias, Protocol, cast

from ssc_codegen._logging import logger
from ssc_codegen.ast import Node as AstNode
from ssc_codegen.exceptions import (
    ParseError,
    BuildTimeError,
    UnknownNodeError,
)
from ssc_codegen.linter._kdl_lang import KDL_PARSER, Node as TSNode
from ssc_codegen.regex_utils import normalize_regex_pattern

# types
from ssc_codegen.ast import StructType, VariableType

# module layer
from ssc_codegen.ast import (
    Module,
    Struct,
    TypeDef,
    TypeDefField,
)

# stuct layer
from ssc_codegen.ast import (
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
    RequestConfig,
    StartParse,
)
# expressions

# selectors
from ssc_codegen.ast import (
    CssSelect,
    CssSelectAll,
    XpathSelect,
    XpathSelectAll,
    CssRemove,
    XpathRemove,
)

# extract
from ssc_codegen.ast import Text, Raw, Attr

# string
from ssc_codegen.ast import (
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
from ssc_codegen.ast import Re, ReAll, ReSub

# array
from ssc_codegen.ast import Index, Slice, Len, Unique

# casts
from ssc_codegen.ast import ToInt, ToFloat, ToBool, Jsonify, Nested

# control
from ssc_codegen.ast import (
    Self,
    Fallback,
    Return,
    FallbackStart,
    FallbackEnd,
)

# predicate containers
from ssc_codegen.ast import Filter, Assert, Match

# predicate logic
from ssc_codegen.ast import LogicOr, LogicAnd, LogicNot

# predicate ops
from ssc_codegen.ast import (
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
    PredAttrEnds,
    PredAttrEq,
    PredAttrNe,
    PredAttrRe,
    PredAttrStarts,
    PredAttrContains,
    PredTextContains,
    PredTextEnds,
    PredTextRe,
    PredTextStarts,
    PredRange,
    PredCountEq,
    PredCountGt,
    PredCountLt,
    PredCountNe,
    PredCountGe,
    PredCountLe,
    PredCountRange,
)

# json
from ssc_codegen.ast import JsonDef, JsonDefField

# transform
from ssc_codegen.ast import TransformDef, TransformTarget, TransformCall


class KdlNode(Protocol):
    name: str
    args: list[Any]
    properties: dict[str, Any]
    children: list["KdlNode"]
    type_annotation: str | None


@dataclass
class TsKdlNode:
    name: str
    args: list[Any] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)
    children: list["TsKdlNode"] = field(default_factory=list)
    type_annotation: str | None = None


@dataclass
class Document:
    nodes: list[TsKdlNode]


@dataclass
class ImportRegistry:
    """Shared across recursive import resolution to detect cycles and cache results."""

    in_progress: set[str] = field(
        default_factory=set
    )  # absolute paths being parsed
    completed: dict[str, "ParseContext"] = field(
        default_factory=dict
    )  # path -> parsed context


@dataclass
class ParseContext:
    property_defines: dict[str, str | int | float | bool] = field(
        default_factory=dict
    )
    children_defines: dict[str, list[KdlNode]] = field(default_factory=dict)
    transforms: dict[str, TransformDef] = field(default_factory=dict)
    # TODO: reg init fields
    init: dict[str, dict[str, str]] = field(default_factory=dict)
    # Store structs during parsing so nested can reference them
    structs: dict[str, Struct] = field(default_factory=dict)
    # Store json definitions so jsonify can resolve types
    json_defs: dict[str, JsonDef] = field(default_factory=dict)
    # Path of the file being parsed (for resolving relative imports)
    source_path: Path | None = None

    def all_names(self) -> set[str]:
        """Return all defined names for conflict detection."""
        return (
            set(self.property_defines)
            | set(self.children_defines)
            | set(self.transforms)
            | set(self.structs)
            | set(self.json_defs)
        )


ParentAstNode: TypeAlias = AstNode

CallbackRegModule = Callable[[KdlNode, Module, ParseContext], AstNode]
CallbackRegContext = Callable[[KdlNode, ParseContext], None]
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
CallbackPred = Callable[[KdlNode, PredicateLikeNode, ParseContext], AstNode]


class AstParser:
    def __init__(self) -> None:
        self._module_handlers: dict[str, CallbackRegModule] = {}
        self._context_handlers: dict[str, CallbackRegContext] = {}
        self._context_structs: dict[str, CallbackRegStruct] = {}
        self._context_expressions: dict[str, CallbackReg] = {}
        self._context_filter: dict[str, CallbackFilter] = {}
        self._context_assert: dict[str, CallbackAssert] = {}
        self._context_match: dict[str, CallbackMatch] = {}
        self.ctx = ParseContext()

    def register_module_context(
        self, name: str
    ) -> Callable[..., Callable[[KdlNode, ParseContext], None]]:
        def decorator(fn: CallbackRegContext) -> CallbackRegContext:
            self._context_handlers[name] = fn
            return fn

        return decorator

    def register_predicate_node(
        self,
        name: str,
        *,
        reg_filter: bool = True,
        reg_assert: bool = True,
        reg_match: bool = True,
    ) -> Callable[..., CallbackPred]:
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
        typedef = TypeDef(
            parent=parent, name=struct.name, struct_type=struct.struct_type
        )
        for item in struct.body:
            # Handle regular fields
            if isinstance(item, Field):
                nested_ref = ""
                json_ref = ""
                is_array = False
                if item.ret == VariableType.NESTED:
                    nested_expr = [
                        i for i in item.body if isinstance(i, Nested)
                    ][0]
                    nested_ref = nested_expr.struct_name
                    is_array = nested_expr.is_array
                elif item.ret == VariableType.JSON:
                    jsonify_expr = [
                        i for i in item.body if isinstance(i, Jsonify)
                    ][0]
                    json_ref = jsonify_expr.schema_name
                    is_array = jsonify_expr.is_array

                typedef.body.append(
                    TypeDefField(
                        parent=typedef,
                        ret=item.ret,
                        name=item.name,
                        nested_ref=nested_ref,
                        json_ref=json_ref,
                        is_array=is_array,
                    )
                )
            # Handle dict type: -key and -value
            elif isinstance(item, (Key, Value)):
                # For dict types, we need to add TypeDefField for key and value
                field_name = "key" if isinstance(item, Key) else "value"
                nested_ref = ""
                json_ref = ""
                is_array = False

                if item.ret == VariableType.NESTED:
                    nested_expr = [
                        i for i in item.body if isinstance(i, Nested)
                    ][0]
                    nested_ref = nested_expr.struct_name
                    is_array = nested_expr.is_array
                elif item.ret == VariableType.JSON:
                    jsonify_expr = [
                        i for i in item.body if isinstance(i, Jsonify)
                    ][0]
                    json_ref = jsonify_expr.schema_name
                    is_array = jsonify_expr.is_array

                typedef.body.append(
                    TypeDefField(
                        parent=typedef,
                        ret=item.ret,
                        name=field_name,
                        nested_ref=nested_ref,
                        json_ref=json_ref,
                        is_array=is_array,
                    )
                )
        return typedef

    def _parse_json_fields(self, nodes: list[KdlNode], parent: JsonDef):
        logger.debug(
            "_parse_json_fields: %r, %d field(s)", parent.name, len(nodes)
        )
        for node in nodes:
            name = node.name
            # field type is encoded as the first parsed argument, optionally with
            # a type annotation prefix such as (array)str.
            type_ = str(node.args[0])
            is_array = type_.startswith("(array)")
            type_ = type_.removeprefix("(array)")
            is_optional = type_.endswith("?")
            type_ = type_.rstrip("?")
            ref_name = ""
            match type_:
                case "str":
                    if is_optional:
                        ret_type = VariableType.OPT_STRING
                    elif is_array:
                        ret_type = VariableType.LIST_STRING
                    else:
                        ret_type = VariableType.STRING
                case "int":
                    if is_optional:
                        ret_type = VariableType.OPT_INT
                    elif is_array:
                        ret_type = VariableType.LIST_INT
                    else:
                        ret_type = VariableType.INT
                case "float":
                    if is_optional:
                        ret_type = VariableType.OPT_FLOAT
                    elif is_array:
                        ret_type = VariableType.LIST_FLOAT
                    else:
                        ret_type = VariableType.FLOAT
                case "bool":
                    ret_type = VariableType.BOOL
                case "null":
                    ret_type = VariableType.NULL
                case _:
                    # apologize, its nested json struct
                    ref_name = str(node.args[0])
                    if ref_name.startswith("(array)"):
                        ref_name = ref_name.removeprefix("(array)")
                        is_array = True
                    ret_type = VariableType.JSON
            # second argument is optional alias (original JSON key)
            alias = str(node.args[1]) if len(node.args) > 1 else ""
            jf = JsonDefField(
                parent=parent,
                ret=ret_type,
                name=name,
                is_optional=is_optional,
                is_array=is_array,
                ref_name=ref_name,
                alias=alias,
            )
            logger.debug(
                "  json field %r: ret=%s, optional=%s, array=%s%s%s",
                name,
                ret_type,
                is_optional,
                is_array,
                f", ref={ref_name!r}" if ref_name else "",
                f", alias={alias!r}" if alias else "",
            )
            parent.body.append(jf)

    def parse(
        self,
        kdl_dsl: str,
        *,
        source_path: Path | None = None,
        _import_registry: ImportRegistry | None = None,
    ) -> Module:
        logger.debug("parse() called, input length=%d chars", len(kdl_dsl))
        self.ctx = ParseContext(source_path=source_path)
        document = parse_document(kdl_dsl)
        module = Module()

        if _import_registry is None:
            _import_registry = ImportRegistry()

        # pass 1 — resolve imports (must run before anything else)
        for node in document.nodes:
            if node.name == "import":
                self._handle_import(node, module, _import_registry)

        # snapshot imported names for conflict detection
        imported_names: set[str] = self.ctx.all_names()

        # collect imported structs/typedefs/json_defs/transforms for module body
        imported_structs: list[Struct] = list(self.ctx.structs.values())
        imported_typedefs: list[TypeDef] = [
            self._typedef_from_struct(s, module) for s in imported_structs
        ]
        imported_json_defs: list[JsonDef] = list(self.ctx.json_defs.values())
        imported_transforms: list[TransformDef] = list(
            self.ctx.transforms.values()
        )

        # pass 2 — everything else
        structs: list[Struct] = []
        typedefs: list[TypeDef] = []

        for node in document.nodes:
            if node.name == "import":
                continue  # already handled

            logger.debug("module node: %r", node.name)
            # built-in
            if node.name == "@doc":
                module.docstring.value = node.args[0]
                logger.debug("  set module docstring")
            elif node.name == "json":
                json_name = node.args[0] if node.args else ""
                if json_name in imported_names:
                    raise ParseError(
                        f"Name conflict: json '{json_name}' conflicts with imported name"
                    )
                expr = self._module_handlers[node.name](node, module, self.ctx)
                expr = cast(JsonDef, expr)
                self._parse_json_fields(node.children, expr)
                # Store in context for jsonify type resolution
                self.ctx.json_defs[expr.name] = expr
                module.body.append(expr)
                logger.debug(
                    "  registered json def: %r",
                    node.args[0] if node.args else "?",
                )
            elif node.name == "define":
                # check conflict before delegating to handler
                self._check_define_conflict(node, imported_names)
                cb = self._context_handlers[node.name]
                cb(node, self.ctx)
            elif node.name == "transform":
                t_name = node.args[0] if node.args else ""
                if t_name in imported_names:
                    raise ParseError(
                        f"Name conflict: transform '{t_name}' conflicts with imported name"
                    )
                cb = self._context_handlers[node.name]
                cb(node, self.ctx)
            # other handlers
            elif cb := self._context_handlers.get(node.name):
                logger.debug("  context handler: %r", node.name)
                cb(node, self.ctx)
            elif cb := self._module_handlers.get(node.name):
                expr = cb(node, module, self.ctx)
                if isinstance(expr, Struct):
                    if expr.name in imported_names:
                        raise ParseError(
                            f"Name conflict: struct '{expr.name}' conflicts with imported name"
                        )
                    logger.debug(
                        "  parsing struct: %r (type=%s)",
                        expr.name,
                        expr.struct_type,
                    )
                    # Store struct in context so nested can reference it
                    self.ctx.structs[expr.name] = expr
                    self._parse_struct(node.children, expr)
                    structs.append(expr)
                    typedefs.append(self._typedef_from_struct(expr, module))
                    logger.debug(
                        "  struct done: %r, fields=%d",
                        expr.name,
                        len(expr.body),
                    )
            else:
                raise UnknownNodeError(node.name, "Unknown keyword node")

        # wire all nodes into module body:
        # imported transforms + local transforms, then imported + local typedefs/structs
        local_transform_defs = [
            td
            for td in self.ctx.transforms.values()
            if td not in imported_transforms
        ]
        all_transforms = imported_transforms + local_transform_defs
        for td in all_transforms:
            td.parent = module

        # re-parent imported nodes
        for node in imported_structs + imported_typedefs + imported_json_defs:
            node.parent = module

        module.body.extend(
            imported_json_defs
            + all_transforms
            + imported_typedefs
            + imported_structs
            + typedefs
            + structs
        )
        logger.debug(
            "parse() done: %d transform(s), %d typedef(s), %d struct(s) "
            "(imported: %d struct(s), %d json(s))",
            len(all_transforms),
            len(imported_typedefs) + len(typedefs),
            len(imported_structs) + len(structs),
            len(imported_structs),
            len(imported_json_defs),
        )
        return module

    # ── Import resolution ─────────────────────────────────────────────────

    _KDL_TEXT_ENCODING = "utf-8-sig"

    def _handle_import(
        self,
        node: KdlNode,
        module: Module,
        registry: ImportRegistry,
    ) -> None:
        """Process a single import node."""
        if not node.args:
            raise ParseError("import requires a path argument")

        raw_path = str(node.args[0])
        source_path = self.ctx.source_path
        if source_path is None:
            raise ParseError(
                "Cannot use 'import' when parsing from string without a file path"
            )

        # resolve relative path
        import_path = (source_path.parent / raw_path).resolve()

        if not import_path.is_file():
            raise ParseError(f"import: file not found: {import_path}")

        # selective import names
        selective: set[str] | None = None
        if node.children:
            selective = {child.name for child in node.children}

        logger.debug(
            "import %r -> %s%s",
            raw_path,
            import_path,
            f" selective={selective}" if selective else "",
        )

        # resolve (parses file, caches result, handles circular detection)
        imported_ctx = self._resolve_import(import_path, registry)

        # validate selective names exist
        if selective is not None:
            available = imported_ctx.all_names()
            missing = selective - available
            if missing:
                raise ParseError(
                    f"import {raw_path}: names not found: {', '.join(sorted(missing))}"
                )

        # merge into current context
        self._merge_imported_context(imported_ctx, selective, import_path)

    def _resolve_import(
        self,
        import_path: Path,
        registry: ImportRegistry,
    ) -> ParseContext:
        """Parse an imported file and return its ParseContext."""
        import_key = str(import_path)

        if import_key in registry.completed:
            return registry.completed[import_key]

        if import_key in registry.in_progress:
            raise ParseError(f"Circular import detected: {import_path}")

        registry.in_progress.add(import_key)
        try:
            src = import_path.read_text(encoding=self._KDL_TEXT_ENCODING)
            # Save current context
            saved_ctx = self.ctx
            try:
                self.parse(
                    src,
                    source_path=import_path,
                    _import_registry=registry,
                )
                result_ctx = self.ctx
            finally:
                # Restore caller's context
                self.ctx = saved_ctx
        finally:
            registry.in_progress.discard(import_key)

        registry.completed[import_key] = result_ctx
        return result_ctx

    def _check_define_conflict(
        self, node: KdlNode, imported_names: set[str]
    ) -> None:
        """Check if a define node conflicts with imported names."""
        if node.children:
            # block define: name is first arg
            name = node.args[0] if node.args else ""
        else:
            # scalar define: names are property keys
            for key in node.properties:
                if key in imported_names:
                    raise ParseError(
                        f"Name conflict: define '{key}' conflicts with imported name"
                    )
            return
        if name in imported_names:
            raise ParseError(
                f"Name conflict: define '{name}' conflicts with imported name"
            )

    def _merge_imported_context(
        self,
        imported_ctx: ParseContext,
        selective: set[str] | None,
        import_path: Path,
    ) -> None:
        """Merge imported ParseContext into self.ctx with conflict detection."""
        target = self.ctx

        def _check_and_merge_dict(target_dict, source_dict, kind: str):
            for name, val in source_dict.items():
                if selective is not None and name not in selective:
                    continue
                if name in target_dict:
                    raise ParseError(
                        f"Name conflict: {kind} '{name}' already defined "
                        f"(imported from {import_path})"
                    )
                target_dict[name] = val

        _check_and_merge_dict(
            target.property_defines, imported_ctx.property_defines, "define"
        )
        _check_and_merge_dict(
            target.children_defines, imported_ctx.children_defines, "define"
        )
        _check_and_merge_dict(
            target.transforms, imported_ctx.transforms, "transform"
        )
        _check_and_merge_dict(target.structs, imported_ctx.structs, "struct")
        _check_and_merge_dict(target.json_defs, imported_ctx.json_defs, "json")

    def _parse_struct(self, kdl_nodes: list[KdlNode], parent: Struct):
        logger.debug(
            "_parse_struct: %r, %d node(s)", parent.name, len(kdl_nodes)
        )
        for node in kdl_nodes:
            logger.debug("  struct node: %r", node.name)
            # built-in
            if node.name == "@doc":
                parent.docstring.value = node.args[0]
            elif node.name == "@init":
                expr = parent.init
                self._parse_init_fields(node.children, expr)
                # parent.body.append(expr)
            elif node.name == "@pre-validate":
                expr = PreValidate(parent=parent)
                self._parse_expressions(node.children, expr)
                parent.body.append(expr)
            elif node.name == "@split-doc":
                expr = SplitDoc(parent=parent)
                self._parse_expressions(node.children, expr)
                parent.body.append(expr)
            elif node.name == "@key":
                expr = Key(parent=parent)
                self._parse_expressions(node.children, expr)
                parent.body.append(expr)
            elif node.name == "@value":
                expr = Value(parent=parent)
                self._parse_expressions(node.children, expr)
                parent.body.append(expr)
            elif node.name == "@table":
                expr = TableConfig(parent=parent)
                self._parse_expressions(node.children, expr)
                parent.body.append(expr)
            elif node.name == "@rows":
                expr = TableRow(parent=parent)
                self._parse_expressions(node.children, expr)
                parent.body.append(expr)
            elif node.name == "@match":
                expr = TableMatchKey(parent=parent)
                self._parse_expressions(node.children, expr)
                parent.body.append(expr)
            elif node.name == "@request":
                if not node.args:
                    raise ParseError(
                        "@request requires a multiline string argument"
                    )
                raw_payload = str(
                    self.ctx.property_defines.get(node.args[0], node.args[0])
                )
                req = RequestConfig(parent=parent)
                req.raw_payload = raw_payload
                req.response_path = str(
                    node.properties.get("response-path", "")
                )
                req.response_join = str(
                    node.properties.get("response-join", "")
                )
                req.name = str(node.properties.get("name", ""))
                parent.body.append(req)
                logger.debug(
                    "  @request: %d chars, placeholders=%r",
                    len(raw_payload),
                    req.placeholders,
                )
            else:
                if parent.struct_type == StructType.TABLE:
                    expr = Field(
                        parent=parent,
                        name=node.name,
                        accept=VariableType.STRING,
                    )
                else:
                    expr = Field(parent=parent, name=node.name)
                self._parse_expressions(node.children, expr)
                parent.body.append(expr)
                logger.debug("  field %r: ret=%s", node.name, expr.ret)
        # finally, add StartParse node
        parent.body.append(StartParse(parent=parent))

    def _parse_init_fields(self, kdl_nodes: list[KdlNode], parent: Init):
        logger.debug("_parse_init_fields: %d field(s)", len(kdl_nodes))
        for node in kdl_nodes:
            expr = InitField(parent=parent, name=node.name)
            self._parse_expressions(node.children, expr)
            expr.ret = expr.body[-1].ret
            logger.debug("  init field %r: ret=%s", node.name, expr.ret)
            parent.body.append(expr)

    def _parse_filter_expr(
        self,
        kdl_nodes: list[KdlNode],
        parent: Filter | LogicAnd | LogicNot | LogicOr,
    ):
        logger.debug(
            "_parse_filter_expr: parent=%s, %d node(s)",
            type(parent).__name__,
            len(kdl_nodes),
        )
        for node in kdl_nodes:
            if (
                node.name in self.ctx.children_defines
                and node.name not in self._context_filter
            ):
                self._parse_filter_expr(
                    self.ctx.children_defines[node.name], parent
                )
                continue
            if cb := self._context_filter.get(node.name):
                expr = cb(node, parent, self.ctx)
                logger.debug(
                    "  filter pred: %r -> %s", node.name, type(expr).__name__
                )
                if isinstance(expr, (LogicAnd, LogicOr, LogicNot)):
                    self._parse_filter_expr(node.children, expr)
                parent.body.append(expr)

    def _parse_assert_expr(
        self,
        kdl_nodes: list[KdlNode],
        parent: Assert | LogicAnd | LogicNot | LogicOr,
    ):
        logger.debug(
            "_parse_assert_expr: parent=%s, %d node(s)",
            type(parent).__name__,
            len(kdl_nodes),
        )
        for node in kdl_nodes:
            if (
                node.name in self.ctx.children_defines
                and node.name not in self._context_assert
            ):
                self._parse_assert_expr(
                    self.ctx.children_defines[node.name], parent
                )
                continue
            if cb := self._context_assert.get(node.name):
                expr = cb(node, parent, self.ctx)
                logger.debug(
                    "  assert pred: %r -> %s", node.name, type(expr).__name__
                )
                if isinstance(expr, (LogicAnd, LogicOr, LogicNot)):
                    self._parse_assert_expr(node.children, expr)
                parent.body.append(expr)

    def _parse_match_expr(
        self,
        kdl_nodes: list[KdlNode],
        parent: Match | LogicAnd | LogicNot | LogicOr,
    ):
        logger.debug(
            "_parse_match_expr: parent=%s, %d node(s)",
            type(parent).__name__,
            len(kdl_nodes),
        )
        for node in kdl_nodes:
            if (
                node.name in self.ctx.children_defines
                and node.name not in self._context_match
            ):
                self._parse_match_expr(
                    self.ctx.children_defines[node.name], parent
                )
                continue
            if cb := self._context_match.get(node.name):
                expr = cb(node, parent, self.ctx)
                logger.debug(
                    "  match pred: %r -> %s", node.name, type(expr).__name__
                )
                if isinstance(expr, (LogicAnd, LogicOr, LogicNot)):
                    self._parse_match_expr(node.children, expr)
                parent.body.append(expr)

    def _parse_expressions(
        self,
        kdl_nodes: list[KdlNode],
        parent: FieldLikeNode,
        *,
        _add_return: bool = True,
    ):
        if not kdl_nodes:
            return

        logger.debug(
            "_parse_expressions: parent=%s, %d node(s), add_return=%s",
            type(parent).__name__,
            len(kdl_nodes),
            _add_return,
        )
        for node in kdl_nodes:
            # block define inlining: if the keyword is a children_define name,
            # expand it as if its children were written inline at this position
            if (
                node.name in self.ctx.children_defines
                and node.name not in self._context_expressions
            ):
                logger.debug("  inlining define: %r", node.name)
                self._parse_expressions(
                    self.ctx.children_defines[node.name],
                    parent,
                    _add_return=False,
                )
                continue

            # @<name> references a pre-computed value from the enclosing @init
            if node.name.startswith("@") and node.name not in {
                "@doc",
                "@init",
                "@pre-validate",
                "@split-doc",
                "@key",
                "@value",
                "@table",
                "@rows",
                "@match",
            }:
                field_name = node.name[1:]
                struct = cast(Struct, parent.parent)
                init_field = next(
                    (
                        i
                        for i in struct.init.body
                        if isinstance(i, InitField) and i.name == field_name
                    ),
                    None,
                )
                if init_field is None:
                    raise BuildTimeError(
                        f"Unknown @init reference '@{field_name}' in {type(parent).__name__}"
                    )

                prev_type = init_field.ret
                expr = Self(
                    parent=parent,
                    accept=prev_type,
                    ret=prev_type,
                    name=field_name,
                )
                logger.debug("  expr: %r -> Self (ret=%s)", node.name, expr.ret)
                parent.body.append(expr)
                continue

            if node.name == "self":
                ref_name = str(node.args[0]) if node.args else "<name>"
                raise BuildTimeError(
                    f"'self {ref_name}' syntax is no longer supported; use '@{ref_name}' instead"
                )

            if cb := self._context_expressions.get(node.name):
                expr = cb(node, parent, self.ctx)
                logger.debug(
                    "  expr: %r -> %s (ret=%s)",
                    node.name,
                    type(expr).__name__,
                    expr.ret,
                )
                if isinstance(expr, Fallback):
                    continue
                elif isinstance(expr, Filter):
                    self._parse_filter_expr(node.children, expr)
                elif isinstance(expr, Assert):
                    self._parse_assert_expr(node.children, expr)
                elif isinstance(expr, Match):
                    self._parse_match_expr(node.children, expr)
                parent.body.append(expr)
        # auto add last expr - return (only at the top-level call, not for inlined defines)
        if _add_return and parent.body:
            last_ret = parent.body[-1].ret
            parent.body.append(
                Return(parent=parent, ret=last_ret, accept=last_ret)
            )
            parent.ret = last_ret
            logger.debug("  auto-return added: ret=%s", last_ret)


PARSER = AstParser()


def parse_document(src: str) -> Document:
    try:
        tree = KDL_PARSER.parse(src.encode("utf-8"))
    except Exception as e:
        msg = str(e)
        raise ParseError(f"Invalid KDL syntax: {msg}") from e
    root = tree.root_node
    first_error = _find_first_syntax_error(root)
    if first_error is not None:
        line = first_error.start_point.row + 1
        col = first_error.start_point.column + 1
        if bool(getattr(first_error, "is_missing", False)):
            raise ParseError(
                f"Invalid KDL syntax at {line}:{col}: expected {first_error.type}"
            )
        snippet = _compact_snippet(
            first_error.text.decode("utf-8", errors="replace")
        )
        raise ParseError(
            f"Invalid KDL syntax at {line}:{col}: {snippet or first_error.type}"
        )
    return Document(
        nodes=[_build_kdl_node(node) for node in _iter_root_nodes(root)]
    )


def _iter_root_nodes(root: TSNode) -> list[TSNode]:
    return [child for child in root.children if child.type == "node"]


def _build_kdl_node(node: TSNode) -> TsKdlNode:
    name = _node_name(node)
    args: list[Any] = []
    properties: dict[str, Any] = {}
    children: list[TsKdlNode] = []

    for child in node.children:
        if child.type == "node_field":
            prop = _parse_prop(child)
            if prop is not None:
                key, value = prop
                properties[key] = value
            else:
                value, type_annotation = _parse_value_field(child)
                args.append(
                    f"{type_annotation}{value}" if type_annotation else value
                )
        elif child.type == "node_children":
            children.extend(_parse_children_block(child))

    return TsKdlNode(
        name=name, args=args, properties=properties, children=children
    )


def _parse_children_block(node_children: TSNode) -> list[TsKdlNode]:
    result: list[TsKdlNode] = []
    current_name: str | None = None
    current_args: list[Any] = []
    current_properties: dict[str, Any] = {}
    current_children: list[TsKdlNode] = []

    def flush_current() -> None:
        nonlocal \
            current_name, \
            current_args, \
            current_properties, \
            current_children
        if current_name is None:
            return
        result.append(
            TsKdlNode(
                name=current_name,
                args=current_args,
                properties=current_properties,
                children=current_children,
            )
        )
        current_name = None
        current_args = []
        current_properties = {}
        current_children = []

    for child in node_children.children:
        if child.type in {"{", "}", ";"}:
            if child.type == ";":
                flush_current()
            continue

        if child.type == "node":
            flush_current()
            result.append(_build_kdl_node(child))
            continue

        if child.type == "identifier":
            flush_current()
            current_name = child.text.decode("utf-8")
            continue

        if child.type == "node_field":
            if current_name is None:
                continue
            prop = _parse_prop(child)
            if prop is not None:
                key, value = prop
                current_properties[key] = value
            else:
                value, type_annotation = _parse_value_field(child)
                current_args.append(
                    f"{type_annotation}{value}" if type_annotation else value
                )
            continue

        if child.type == "node_children":
            if current_name is None:
                result.extend(_parse_children_block(child))
            else:
                current_children.extend(_parse_children_block(child))
            continue

    flush_current()
    return result


def _node_name(node: TSNode) -> str:
    for child in node.children:
        if child.type == "identifier":
            return child.text.decode("utf-8")
    return ""


def _parse_prop(node_field: TSNode) -> tuple[str, Any] | None:
    for child in node_field.children:
        if child.type != "prop":
            continue
        key = ""
        value: Any = ""
        for sub in child.children:
            if sub.type == "identifier" and not key:
                key = sub.text.decode("utf-8")
            elif sub.type == "value":
                value, type_annotation = _parse_value_node(sub)
                if type_annotation:
                    value = f"{type_annotation}{value}"
        return key, value
    return None


def _parse_value_field(node_field: TSNode) -> tuple[Any, str | None]:
    for child in node_field.children:
        if child.type == "value":
            return _parse_value_node(child)
    return "", None


def _parse_value_node(value_node: TSNode) -> tuple[Any, str | None]:
    type_annotation: str | None = None
    raw_text: str | None = None
    for child in value_node.children:
        if child.type == "type":
            type_annotation = child.text.decode("utf-8")
            continue
        raw_text = child.text.decode("utf-8")
        break
    if raw_text is None:
        raw_text = value_node.text.decode("utf-8")
    return _decode_scalar(raw_text), type_annotation


def _decode_scalar(text: str) -> Any:
    text = text.strip()
    if text == "#true":
        return True
    if text == "#false":
        return False
    if text == "#null":
        return None
    if _looks_like_raw_string(text):
        return _decode_raw_string(text)
    if text.startswith('"""') and text.endswith('"""'):
        return text[3:-3]
    if text.startswith('"') and text.endswith('"'):
        try:
            return _py_ast.literal_eval(text)
        except Exception:
            return text[1:-1]
    if _INTEGER_RE.fullmatch(text):
        return int(text.replace("_", ""), 10)
    if _FLOAT_RE.fullmatch(text):
        return float(text.replace("_", ""))
    return text


def _looks_like_raw_string(text: str) -> bool:
    return text.startswith("#") and '"' in text and text.endswith("#")


def _decode_raw_string(text: str) -> str:
    m = _re.fullmatch(r'(#+)("""|")(.*)\2\1', text, flags=_re.DOTALL)
    if not m:
        return text
    return m.group(3)


def _find_first_syntax_error(node: TSNode) -> TSNode | None:
    if node.type == "ERROR" or bool(getattr(node, "is_missing", False)):
        return node
    if not node.has_error:
        return None
    for child in node.children:
        found = _find_first_syntax_error(child)
        if found is not None:
            return found
    return None


def _compact_snippet(text: str) -> str:
    return _re.sub(r"\s+", " ", text).strip()[:80]


_INTEGER_RE = _re.compile(r"[+-]?\d(?:[\d_])*\Z")
_FLOAT_RE = _re.compile(
    r"[+-]?(?:\d(?:[\d_])*\.\d(?:[\d_])*|\d(?:[\d_])*[eE][+-]?\d(?:[\d_])*|\d(?:[\d_]*)\.\d(?:[\d_]*)[eE][+-]?\d(?:[\d_])*)\Z"
)


# contexts
@PARSER.register_module_context("define")
def reg_define(node: KdlNode, ctx: ParseContext):
    if node.children:
        ctx.children_defines[node.args[0]] = node.children
        logger.debug(
            "define: children block %r (%d child node(s))",
            node.args[0],
            len(node.children),
        )
    else:
        pair = list(node.properties.items())[0]
        ctx.property_defines[pair[0]] = pair[1]
        logger.debug("define: property %r = %r", pair[0], pair[1])


_VAR_TYPE_MAP: dict[str, VariableType] = {
    "STRING": VariableType.STRING,
    "OPT_STRING": VariableType.OPT_STRING,
    "LIST_STRING": VariableType.LIST_STRING,
    "INT": VariableType.INT,
    "OPT_INT": VariableType.OPT_INT,
    "LIST_INT": VariableType.LIST_INT,
    "FLOAT": VariableType.FLOAT,
    "OPT_FLOAT": VariableType.OPT_FLOAT,
    "LIST_FLOAT": VariableType.LIST_FLOAT,
    "BOOL": VariableType.BOOL,
    "NULL": VariableType.NULL,
    "DOCUMENT": VariableType.DOCUMENT,
    "LIST_DOCUMENT": VariableType.LIST_DOCUMENT,
    "NESTED": VariableType.NESTED,
    "JSON": VariableType.JSON,
}


@PARSER.register_module_context("transform")
def reg_transform(node: KdlNode, ctx: ParseContext):
    name = node.args[0]
    accept_str = str(node.properties.get("accept", ""))
    ret_str = str(node.properties.get("return", ""))

    if accept_str not in _VAR_TYPE_MAP:
        raise ParseError(
            f"transform '{name}': invalid accept type '{accept_str}' (AUTO not allowed)"
        )
    if ret_str not in _VAR_TYPE_MAP:
        raise ParseError(
            f"transform '{name}': invalid return type '{ret_str}' (AUTO not allowed)"
        )

    accept_type = _VAR_TYPE_MAP[accept_str]
    ret_type = _VAR_TYPE_MAP[ret_str]

    transform_def = TransformDef(name=name, accept=accept_type, ret=ret_type)
    logger.debug("transform %r: accept=%s, ret=%s", name, accept_str, ret_str)

    # each child is a language block: py { import "..."; code "..." }
    for lang_node in node.children:
        lang = lang_node.name
        imports: list[str] = []
        code: list[str] = []

        for item in lang_node.children:
            if item.name == "import":
                imports.extend(str(a) for a in item.args)
            elif item.name == "code":
                code.extend(str(a) for a in item.args)

        target = TransformTarget(
            parent=transform_def,
            lang=lang,
            imports=tuple(imports),
            code=tuple(code),
        )
        logger.debug(
            "  transform %r lang=%r: %d import(s), %d code line(s)",
            name,
            lang,
            len(imports),
            len(code),
        )
        transform_def.body.append(target)

    ctx.transforms[name] = transform_def


@PARSER.register_module_node("struct")
def reg_module_struct(node: KdlNode, parent: Module, _: ParseContext):
    type_ = node.properties.get("type", "item")
    keep_order = node.properties.get("keep-order", False)
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
    expr = Struct(
        parent=parent,
        name=node.args[0],
        struct_type=st_type,
        keep_order=keep_order,
    )
    return expr


@PARSER.register_module_node("json")
def reg_module_json(node: KdlNode, parent: Module, _: ParseContext):
    name = node.args[0]
    is_array = node.properties.get("array", False)
    return JsonDef(parent=parent, name=name, is_array=is_array)


# expressions layer


# selectors
def _resolve_selector_arg(
    query: str | int | float | bool, ctx: ParseContext
) -> str:
    value = ctx.property_defines.get(query, query)
    return value if isinstance(value, str) else str(value)


def _resolve_selector_child_name(name: str, ctx: ParseContext) -> str:
    value = ctx.property_defines.get(name, _decode_scalar(name))
    return value if isinstance(value, str) else str(value)


@PARSER.register_expression_node("css")
def reg_expr_css(node: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    if node.children:
        queries = [
            _resolve_selector_child_name(c.name, ctx) for c in node.children
        ]
        return CssSelect(parent=parent, queries=queries)
    query = _resolve_selector_arg(node.args[0], ctx)
    return CssSelect(parent=parent, query=cast(str, query))


@PARSER.register_expression_node("css-all")
def reg_expr_css_all(node: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    if node.children:
        queries = [
            _resolve_selector_child_name(c.name, ctx) for c in node.children
        ]
        return CssSelectAll(parent=parent, queries=queries)
    query = _resolve_selector_arg(node.args[0], ctx)
    return CssSelectAll(parent=parent, query=cast(str, query))


@PARSER.register_expression_node("xpath")
def reg_expr_xpath(node: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    if node.children:
        queries = [
            _resolve_selector_child_name(c.name, ctx) for c in node.children
        ]
        return XpathSelect(parent=parent, queries=queries)
    query = _resolve_selector_arg(node.args[0], ctx)
    return XpathSelect(parent=parent, query=cast(str, query))


@PARSER.register_expression_node("xpath-all")
def reg_expr_xpath_all(node: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    if node.children:
        queries = [
            _resolve_selector_child_name(c.name, ctx) for c in node.children
        ]
        return XpathSelectAll(parent=parent, queries=queries)
    query = _resolve_selector_arg(node.args[0], ctx)
    return XpathSelectAll(parent=parent, query=cast(str, query))


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
    # If there's no previous expression, assume DOCUMENT (root)
    if not parent.body:
        prev_type = VariableType.DOCUMENT
    else:
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
    # If there's no previous expression, assume DOCUMENT (root)
    if not parent.body:
        prev_type = VariableType.DOCUMENT
    else:
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
    # If there's no previous expression, assume DOCUMENT (root)
    if not parent.body:
        prev_type = VariableType.DOCUMENT
    else:
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
    # trim takes no args — strips whitespace; optional substr arg for compat
    substr = (
        cast(str, ctx.property_defines.get(node.args[0], node.args[0]))
        if node.args
        else ""
    )
    prev_type = parent.body[-1].ret
    return Trim(parent=parent, accept=prev_type, ret=prev_type, substr=substr)


@PARSER.register_expression_node("ltrim")
def reg_expr_ltrim(node: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    substr = (
        cast(str, ctx.property_defines.get(node.args[0], node.args[0]))
        if node.args
        else ""
    )
    prev_type = parent.body[-1].ret
    return Ltrim(parent=parent, accept=prev_type, ret=prev_type, substr=substr)


@PARSER.register_expression_node("rtrim")
def reg_expr_rtrim(node: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    substr = (
        cast(str, ctx.property_defines.get(node.args[0], node.args[0]))
        if node.args
        else ""
    )
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
    prev_type = parent.body[-1].ret
    if node.children:
        # map form: repl { "old" "new"; ... }
        # children are KdlNodes where name="old_str", args[0]="new_str"
        items = {str(child.name): str(child.args[0]) for child in node.children}
        return ReplMap(
            parent=parent, accept=prev_type, ret=prev_type, replacements=items
        )
    old = cast(str, ctx.property_defines.get(node.args[0], node.args[0]))
    new = cast(str, ctx.property_defines.get(node.args[1], node.args[1]))
    return Repl(
        parent=parent,
        accept=prev_type,
        ret=prev_type,
        old=old,
        new=new,
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
    sep = cast(str, ctx.property_defines.get(node.args[0], node.args[0]))
    return Split(parent=parent, sep=sep)


@PARSER.register_expression_node("join")
def reg_expr_join(node: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    sep = cast(str, ctx.property_defines.get(node.args[0], node.args[0]))
    return Join(parent=parent, sep=sep)


@PARSER.register_expression_node("unescape")
def reg_expr_unescape(node: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    # apologize, last type - STRING, LIST_STRING
    prev_type = parent.body[-1].ret
    return Unescape(parent=parent, accept=prev_type, ret=prev_type)


# regex
@PARSER.register_expression_node("re")
def reg_expr_re(node: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    raw = ctx.property_defines.get(node.args[0], node.args[0])
    pattern = normalize_regex_pattern(raw)
    prev_type = parent.body[-1].ret
    return Re(parent=parent, pattern=pattern, accept=prev_type, ret=prev_type)


@PARSER.register_expression_node("re-all")
def reg_expr_re_all(node: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    raw = ctx.property_defines.get(node.args[0], node.args[0])
    pattern = normalize_regex_pattern(raw)
    return ReAll(parent=parent, pattern=pattern)


@PARSER.register_expression_node("re-sub")
def reg_expr_re_sub(node: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    prev_type = parent.body[-1].ret
    raw = ctx.property_defines.get(node.args[0], node.args[0])
    pattern = normalize_regex_pattern(raw)
    repl = cast(str, ctx.property_defines.get(node.args[1], node.args[1]))
    return ReSub(
        parent=parent,
        accept=prev_type,
        ret=prev_type,
        pattern=pattern,
        repl=repl,
    )


# array
def _resolve_index_types(
    parent: FieldLikeNode,
) -> tuple[VariableType, VariableType]:
    """Resolve accept/ret for index/first/last from the previous node's type."""
    if parent.body:
        prev_type = parent.body[-1].ret
        accept = prev_type
        ret = prev_type.scalar if prev_type.is_list else prev_type
    else:
        accept = VariableType.LIST_AUTO
        ret = VariableType.AUTO
    return accept, ret


@PARSER.register_expression_node("index")
def reg_expr_index(node: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    accept, ret = _resolve_index_types(parent)
    return Index(parent=parent, i=int(node.args[0]), accept=accept, ret=ret)


@PARSER.register_expression_node("first")
def reg_expr_first(_: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    accept, ret = _resolve_index_types(parent)
    return Index(parent=parent, i=0, accept=accept, ret=ret)


@PARSER.register_expression_node("last")
def reg_expr_last(_: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    accept, ret = _resolve_index_types(parent)
    return Index(parent=parent, i=-1, accept=accept, ret=ret)


@PARSER.register_expression_node("slice")
def reg_expr_slice(node: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    start, end = int(node.args[0]), int(node.args[1])
    if parent.body:
        prev_type = parent.body[-1].ret
        return Slice(
            parent=parent, start=start, end=end, accept=prev_type, ret=prev_type
        )
    return Slice(parent=parent, start=start, end=end)


@PARSER.register_expression_node("len")
def reg_expr_len(node: KdlNode, parent: FieldLikeNode, _: ParseContext):
    return Len(parent=parent)


@PARSER.register_expression_node("unique")
def reg_expr_unique(node: KdlNode, parent: FieldLikeNode, _: ParseContext):
    keep_order = bool(node.properties.get("keep-order", False))
    return Unique(parent=parent, keep_order=keep_order)


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
        VariableType.LIST_FLOAT
        if prev_type == VariableType.LIST_STRING
        else VariableType.FLOAT
    )
    return ToFloat(parent=parent, accept=prev_type, ret=ret_type)


@PARSER.register_expression_node("to-bool")
def reg_expr_to_bool(_: KdlNode, parent: FieldLikeNode, _2: ParseContext):
    # AUTO, ANY
    prev_type = parent.body[-1].ret
    return ToBool(parent=parent, accept=prev_type)


def _resolve_jsonify_type(
    json_def: JsonDef, path: str, ctx: ParseContext
) -> tuple[VariableType, bool]:
    """Resolve the return type and array flag for jsonify based on schema and path.

    Two use cases:
    1. Path navigates WITHIN schema structure (e.g., Quote path="2.author.slug")
       -> Try to resolve by walking the schema
    2. Path navigates RAW JSON before applying schema (e.g., Content path="props.pageProps.data")
       -> Schema is applied to result, return (JSON, False)

    Returns: (type, is_array)

    Examples:
        Quote (array) + ""              -> (JSON, True)   - array of Quote
        Quote (array) + "0"             -> (JSON, False)  - single Quote
        Quote (array) + "2.author.slug" -> (STRING, False) - navigate within schema
        Content + "props.pageProps.titleResults" -> (JSON, False) - raw JSON navigation
    """
    if not path:
        # No path: return the schema as-is with its array flag
        return VariableType.JSON, json_def.is_array

    # Parse path: "2.author.slug" -> ["2", "author", "slug"]
    segments = path.split(".")

    # Try to navigate within the schema structure
    # If any field is not found, fall back to raw JSON navigation
    current_def = json_def
    current_is_array = json_def.is_array

    for i, segment in enumerate(segments):
        # If current is array and segment is numeric index -> unwrap array
        if current_is_array and segment.isdigit():
            current_is_array = False
            continue

        # Try to find field in current JsonDef (match name or alias)
        field = None
        for f in current_def.body:
            if isinstance(f, JsonDefField) and (
                f.name == segment or f.alias == segment
            ):
                field = f
                break

        if field is None:
            # Field not found in schema -> assume raw JSON navigation
            # Schema is applied to the result of path navigation
            # Return (JSON, False) since we're extracting from raw JSON
            return VariableType.JSON, False

        # Last segment: return field type and array flag
        if i == len(segments) - 1:
            return field.ret, field.is_array

        # Navigate deeper: field must be a nested JSON reference
        if field.ret != VariableType.JSON:
            # Can't navigate deeper through non-JSON field
            # This shouldn't happen in well-formed DSL, but treat as raw JSON navigation
            return VariableType.JSON, False

        # Get nested JsonDef
        if not field.ref_name:
            # No reference -> can't navigate, treat as raw JSON
            return VariableType.JSON, False

        nested_def = ctx.json_defs.get(field.ref_name)
        if not nested_def:
            # Schema not found -> treat as raw JSON
            return VariableType.JSON, False

        current_def = nested_def
        current_is_array = field.is_array

    # Shouldn't reach here, but just in case
    return VariableType.JSON, current_is_array


@PARSER.register_expression_node("jsonify")
def reg_expr_jsonify(node: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    schema_name = node.args[0]
    path = cast(str, node.properties.get("path", ""))

    # Look up JSON schema
    json_def = ctx.json_defs.get(schema_name)
    if json_def is None:
        raise ParseError(f"jsonify: JSON schema '{schema_name}' not found")

    # Resolve return type and array flag based on path
    ret_type, is_array = _resolve_jsonify_type(json_def, path, ctx)

    return Jsonify(
        parent=parent,
        schema_name=schema_name,
        path=path,
        ret=ret_type,
        is_array=is_array,
    )


@PARSER.register_expression_node("nested")
def reg_expr_nested(node: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    # Look up struct from context (structs are registered before being parsed)
    struct_name = node.args[0]
    struct = ctx.structs.get(struct_name)
    if struct is None:
        raise ParseError(f"nested: struct '{struct_name}' not found")
    is_array = struct.struct_type in (StructType.FLAT, StructType.LIST)
    return Nested(parent=parent, struct_name=struct_name, is_array=is_array)


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
    end_default = FallbackEnd(
        parent=parent, value=value, accept=prev_type, ret=prev_type
    )
    parent.body.insert(0, start_default)
    parent.body.append(end_default)
    return Fallback(parent=parent, value=value)


@PARSER.register_expression_node("filter")
def reg_expr_filter(node: KdlNode, parent: FieldLikeNode, _: ParseContext):
    if not parent.body:
        return Filter(
            parent=parent,
            accept=VariableType.DOCUMENT,
            ret=VariableType.DOCUMENT,
        )
    prev_type = parent.body[-1].ret
    return Filter(parent=parent, accept=prev_type, ret=prev_type)


@PARSER.register_expression_node("assert")
def reg_expr_assert(node: KdlNode, parent: FieldLikeNode, _: ParseContext):
    # In PreValidate, assert is the first (and only) op — there is no preceding
    # expression, and the return type is always NULL (pre-validate never
    # produces a value).  For all other field-like parents the previous node
    # carries the cursor type, so we read it as usual.
    if isinstance(parent, PreValidate) and not parent.body:
        return Assert(
            parent=parent, accept=VariableType.DOCUMENT, ret=VariableType.NULL
        )
    if not parent.body:
        return Assert(
            parent=parent,
            accept=VariableType.DOCUMENT,
            ret=VariableType.DOCUMENT,
        )
    prev_type = parent.body[-1].ret
    return Assert(parent=parent, accept=prev_type, ret=prev_type)


@PARSER.register_expression_node("match")
def reg_expr_match(node: KdlNode, parent: FieldLikeNode, _: ParseContext):
    # Match is only valid in table struct fields; it always accepts DOCUMENT
    # and returns STRING (the value cell). It may be the first op in a field
    # pipeline (no preceding op), so we must NOT read parent.body[-1].
    return Match(
        parent=parent, accept=VariableType.DOCUMENT, ret=VariableType.STRING
    )


# FILTER predicates
# CMP
@PARSER.register_predicate_node("eq")
def reg_filter_eq(node: KdlNode, parent: Filter, _: ParseContext):
    prev_type = parent.ret
    return PredEq(
        parent=parent, values=tuple(node.args), accept=prev_type, ret=prev_type
    )


@PARSER.register_predicate_node("ne")
def reg_filter_ne(node: KdlNode, parent: Filter, _: ParseContext):
    prev_type = parent.ret
    return PredNe(
        parent=parent, values=tuple(node.args), accept=prev_type, ret=prev_type
    )


@PARSER.register_predicate_node("gt")
def reg_filter_gt(node: KdlNode, parent: Filter, _: ParseContext):
    prev_type = parent.ret
    return PredGt(
        parent=parent, value=node.args[0], accept=prev_type, ret=prev_type
    )


@PARSER.register_predicate_node("lt")
def reg_filter_lt(node: KdlNode, parent: Filter, _: ParseContext):
    prev_type = parent.ret
    return PredLt(
        parent=parent, value=node.args[0], accept=prev_type, ret=prev_type
    )


@PARSER.register_predicate_node("ge")
def reg_filter_ge(node: KdlNode, parent: Filter, _: ParseContext):
    prev_type = parent.ret
    return PredGe(
        parent=parent, value=node.args[0], accept=prev_type, ret=prev_type
    )


@PARSER.register_predicate_node("le")
def reg_filter_le(node: KdlNode, parent: Filter, _: ParseContext):
    prev_type = parent.ret
    return PredLe(
        parent=parent, value=node.args[0], accept=prev_type, ret=prev_type
    )


@PARSER.register_predicate_node("range")
def reg_filter_range(node: KdlNode, parent: Filter, _: ParseContext):
    prev_type = parent.ret
    start, end = int(node.args[0]), int(node.args[1])
    return PredRange(
        parent=parent, start=start, end=end, accept=prev_type, ret=prev_type
    )


# string predicates
@PARSER.register_predicate_node("starts")
def reg_filter_starts(node: KdlNode, parent: Filter, _: ParseContext):
    prev_type = parent.ret
    return PredStarts(
        parent=parent, values=tuple(node.args), accept=prev_type, ret=prev_type
    )


@PARSER.register_predicate_node("ends")
def reg_filter_ends(node: KdlNode, parent: Filter, _: ParseContext):
    prev_type = parent.ret
    return PredEnds(
        parent=parent, values=tuple(node.args), accept=prev_type, ret=prev_type
    )


@PARSER.register_predicate_node("contains")
def reg_filter_contains(node: KdlNode, parent: Filter, _: ParseContext):
    prev_type = parent.ret
    return PredContains(
        parent=parent, values=tuple(node.args), accept=prev_type, ret=prev_type
    )


@PARSER.register_predicate_node("in")
def reg_filter_in(node: KdlNode, parent: Filter, _: ParseContext):
    prev_type = parent.ret
    return PredIn(
        parent=parent, values=tuple(node.args), accept=prev_type, ret=prev_type
    )


# regex
@PARSER.register_predicate_node("re")
def reg_filter_re(node: KdlNode, parent: Filter, ctx: ParseContext):
    raw = ctx.property_defines.get(node.args[0], node.args[0])
    pattern = normalize_regex_pattern(raw)
    prev_type = parent.ret
    return PredRe(
        parent=parent, pattern=pattern, accept=prev_type, ret=prev_type
    )


@PARSER.register_assert_node("re-all")
def reg_filter_re_all(node: KdlNode, parent: Filter, ctx: ParseContext):
    raw = ctx.property_defines.get(node.args[0], node.args[0])
    pattern = normalize_regex_pattern(raw)
    prev_type = parent.ret
    return PredReAll(
        parent=parent, pattern=pattern, accept=prev_type, ret=prev_type
    )


@PARSER.register_assert_node("re-any")
def reg_filter_re_any(node: KdlNode, parent: Filter, ctx: ParseContext):
    raw = ctx.property_defines.get(node.args[0], node.args[0])
    pattern = normalize_regex_pattern(raw)
    prev_type = parent.ret
    return PredReAny(
        parent=parent, pattern=pattern, accept=prev_type, ret=prev_type
    )


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
    return PredXpath(
        parent=parent, query=query, accept=prev_type, ret=prev_type
    )


@PARSER.register_predicate_node("has-attr", reg_match=False)
def reg_filter_has_attr(node: KdlNode, parent: Filter, ctx: ParseContext):
    attrs = tuple(node.args)
    prev_type = parent.ret
    return PredHasAttr(
        parent=parent, attrs=attrs, accept=prev_type, ret=prev_type
    )


@PARSER.register_predicate_node("attr-eq", reg_match=False)
def reg_filter_attr_eq(node: KdlNode, parent: Filter, ctx: ParseContext):
    name = node.args[0]
    args = node.args[1:]
    prev_type = parent.ret
    return PredAttrEq(
        parent=parent,
        accept=prev_type,
        ret=prev_type,
        values=tuple(args),
        name=name,
    )


@PARSER.register_predicate_node("attr-ne", reg_match=False)
def reg_filter_attr_ne(node: KdlNode, parent: Filter, ctx: ParseContext):
    name = node.args[0]
    args = node.args[1:]
    prev_type = parent.ret
    return PredAttrNe(
        parent=parent,
        accept=prev_type,
        ret=prev_type,
        values=tuple(args),
        name=name,
    )


@PARSER.register_predicate_node("attr-contains", reg_match=False)
def reg_filter_attr_contains(node: KdlNode, parent: Filter, ctx: ParseContext):
    name = node.args[0]
    args = node.args[1:]
    prev_type = parent.ret
    return PredAttrContains(
        parent=parent,
        accept=prev_type,
        ret=prev_type,
        values=tuple(args),
        name=name,
    )


@PARSER.register_predicate_node("attr-re", reg_match=False)
def reg_filter_attr_re(node: KdlNode, parent: Filter, ctx: ParseContext):
    name = node.args[0]
    raw = ctx.property_defines.get(node.args[1], node.args[1])
    pattern = normalize_regex_pattern(raw)
    prev_type = parent.ret
    return PredAttrRe(
        parent=parent,
        accept=prev_type,
        ret=prev_type,
        pattern=pattern,
        name=name,
    )


@PARSER.register_predicate_node("text-contains", reg_match=False)
def reg_filter_predicate_text_contains(
    node: KdlNode, parent: Filter, ctx: ParseContext
):
    args = tuple(node.args)
    prev_type = parent.ret
    return PredTextContains(
        parent=parent, accept=prev_type, ret=prev_type, values=args
    )


@PARSER.register_predicate_node("text-ends", reg_match=False)
def reg_filter_predicate_text_ends(
    node: KdlNode, parent: Filter, ctx: ParseContext
):
    args = tuple(node.args)
    prev_type = parent.ret
    return PredTextEnds(
        parent=parent, accept=prev_type, ret=prev_type, values=args
    )


@PARSER.register_predicate_node("text-starts", reg_match=False)
def reg_filter_predicate_text_starts(
    node: KdlNode, parent: Filter, ctx: ParseContext
):
    args = tuple(node.args)
    prev_type = parent.ret
    return PredTextStarts(
        parent=parent, accept=prev_type, ret=prev_type, values=args
    )


@PARSER.register_predicate_node("text-re", reg_match=False)
def reg_filter_predicate_text_re(
    node: KdlNode, parent: Filter, ctx: ParseContext
):
    raw = ctx.property_defines.get(node.args[0], node.args[0])
    pattern = normalize_regex_pattern(raw)
    prev_type = parent.ret
    return PredTextRe(
        parent=parent, accept=prev_type, ret=prev_type, pattern=pattern
    )


@PARSER.register_predicate_node("attr-starts", reg_match=False)
def reg_filter_attr_starts(node: KdlNode, parent: Filter, ctx: ParseContext):
    name = node.args[0]
    args = node.args[1:]
    prev_type = parent.ret
    return PredAttrStarts(
        parent=parent,
        accept=prev_type,
        ret=prev_type,
        values=tuple(args),
        name=name,
    )


@PARSER.register_predicate_node("attr-ends", reg_match=False)
def reg_filter_attr_ends(node: KdlNode, parent: Filter, ctx: ParseContext):
    name = node.args[0]
    args = node.args[1:]
    prev_type = parent.ret
    return PredAttrEnds(
        parent=parent,
        accept=prev_type,
        ret=prev_type,
        values=tuple(args),
        name=name,
    )


# ASSERT SCOPE ONLY
@PARSER.register_predicate_node("len-eq", reg_match=False, reg_filter=False)
def reg_len_eq(node: KdlNode, parent: Filter, cx: ParseContext):
    value = node.args[1]
    prev_type = parent.ret
    return PredCountEq(
        parent=parent, accept=prev_type, ret=prev_type, value=int(value)
    )


# ASSERT SCOPE ONLY
@PARSER.register_predicate_node("len-gt", reg_match=False, reg_filter=False)
def reg_len_gt(node: KdlNode, parent: Filter, cx: ParseContext):
    value = node.args[1]
    prev_type = parent.ret
    return PredCountGt(
        parent=parent, accept=prev_type, ret=prev_type, value=int(value)
    )


# ASSERT SCOPE ONLY
@PARSER.register_predicate_node("len-lt", reg_match=False, reg_filter=False)
def reg_len_lt(node: KdlNode, parent: Filter, cx: ParseContext):
    value = node.args[1]
    prev_type = parent.ret
    return PredCountLt(
        parent=parent, accept=prev_type, ret=prev_type, value=int(value)
    )


# ASSERT SCOPE ONLY
@PARSER.register_predicate_node("len-ne", reg_match=False, reg_filter=False)
def reg_len_ne(node: KdlNode, parent: Filter, cx: ParseContext):
    value = node.args[1]
    prev_type = parent.ret
    return PredCountNe(
        parent=parent, accept=prev_type, ret=prev_type, value=int(value)
    )


# ASSERT SCOPE ONLY
@PARSER.register_predicate_node("len-ge", reg_match=False, reg_filter=False)
def reg_len_ge(node: KdlNode, parent: Filter, cx: ParseContext):
    value = node.args[1]
    prev_type = parent.ret
    return PredCountGe(
        parent=parent, accept=prev_type, ret=prev_type, value=int(value)
    )


# ASSERT SCOPE ONLY
@PARSER.register_predicate_node("len-le", reg_match=False, reg_filter=False)
def reg_len_le(node: KdlNode, parent: Filter, cx: ParseContext):
    value = node.args[1]
    prev_type = parent.ret
    return PredCountLe(
        parent=parent, accept=prev_type, ret=prev_type, value=int(value)
    )


# ASSERT SCOPE ONLY
@PARSER.register_predicate_node("len-range", reg_match=False, reg_filter=False)
def reg_len_range(node: KdlNode, parent: Filter, cx: ParseContext):
    start, end = int(node.args[0]), int(node.args[1])
    prev_type = parent.ret
    return PredCountRange(
        parent=parent, accept=prev_type, ret=prev_type, start=start, end=end
    )


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


# transform pipeline call
@PARSER.register_expression_node("transform")
def reg_expr_transform(node: KdlNode, parent: FieldLikeNode, ctx: ParseContext):
    name = node.args[0]
    if name not in ctx.transforms:
        raise BuildTimeError(f"transform '{name}' is not defined")
    transform_def = ctx.transforms[name]
    prev_type = parent.body[-1].ret
    if prev_type != transform_def.accept:
        raise BuildTimeError(
            f"transform '{name}': pipeline type {prev_type.name!r} "
            f"does not match accept type {transform_def.accept.name!r}"
        )

    # Register transform imports in Module.imports
    # Walk up the parent chain to find Module
    current = parent
    while current and not isinstance(current, Module):
        current = current.parent

    if current and isinstance(current, Module):
        # Add imports for all language targets in this transform
        for target in transform_def.body:
            if target.lang not in current.imports.transform_imports:
                current.imports.transform_imports[target.lang] = set()
            current.imports.transform_imports[target.lang].update(
                target.imports
            )

    return TransformCall(
        parent=parent,
        name=name,
        accept=transform_def.accept,
        ret=transform_def.ret,
        transform_def=transform_def,
    )
