"""Rust source generator backed by ``dom_query`` and ``serde``."""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

from ssc_codegen.ast import (
    Assert,
    Attr,
    CheckMethod,
    CodeEndHook,
    CodeStartHook,
    CssRemove,
    CssSelect,
    CssSelectAll,
    ErrorResponse,
    ExtensionCall,
    Fallback,
    Field,
    Filter,
    Fmt,
    FunctionDef,
    Init,
    InitField,
    InitFieldCall,
    Index,
    JsonDef,
    JsonDefField,
    Jsonify,
    Join,
    Key,
    Len,
    LogicAnd,
    LogicNot,
    LogicOr,
    Lower,
    Ltrim,
    Match,
    MethodFetch,
    MethodRest,
    Module,
    Nested,
    NormalizeSpace,
    PreValidate,
    PredAttrContains,
    PredAttrEnds,
    PredAttrEq,
    PredAttrNe,
    PredAttrRe,
    PredAttrStarts,
    PredContains,
    PredCountEq,
    PredCountGe,
    PredCountGt,
    PredCountLe,
    PredCountLt,
    PredCountNe,
    PredCountRange,
    PredCss,
    PredEnds,
    PredEq,
    PredHasAttr,
    PredNe,
    PredRe,
    PredReAll,
    PredReAny,
    PredXpath,
    PredStarts,
    PredTextContains,
    PredTextEnds,
    PredTextRe,
    PredTextStarts,
    Raw,
    Re,
    ReAll,
    ReSub,
    Repl,
    ReplMap,
    ResultAliasDef,
    ResultVariantDef,
    MatcherListDef,
    Return,
    RmPrefix,
    RmPrefixSuffix,
    RmSuffix,
    Rtrim,
    Self,
    Slice,
    Split,
    SplitDoc,
    StartParse,
    Struct,
    StructBase,
    StructRest,
    StructType as ST,
    TableConfig,
    TableMatchKey,
    TableRows,
    Text,
    ToBool,
    ToFloat,
    ToInt,
    Trim,
    TypeDef,
    TypeDefField,
    TypeInfo,
    Unique,
    Unescape,
    Upper,
    Utilities,
    Value,
    VariableType,
    VariableType as VT,
)
from ssc_codegen.exceptions import BuildTimeError
from ssc_codegen.generation.builder import ModuleBuilder
from ssc_codegen.naming import to_pascal_case, to_snake_case
from ssc_codegen.symbols import RUST_RESERVED
from ssc_codegen.targets.rust import rest
from ssc_codegen.targets.rust.regex import (
    rust_replacement,
    validate_rust_pattern,
)
from ssc_codegen.targets.rust.runtime import rust_runtime_content
from ssc_codegen.traversal.context import WalkContext
from ssc_codegen.traversal.utils import find_predicate_container
from ssc_codegen.traversal.walker import BaseWalker


_RUST_KEYWORDS = RUST_RESERVED


def _str(value: object) -> str:
    """Render a Rust string literal."""
    return json.dumps(str(value), ensure_ascii=False)


def _ident(value: str) -> str:
    """Render a DSL identifier as a valid Rust identifier."""
    name = to_snake_case(value).replace("-", "_") or "value"
    return f"r#{name}" if name in _RUST_KEYWORDS else name


def _pascal(value: str) -> str:
    """Render a generated Rust type name."""
    name = to_pascal_case(value).replace("-", "") or "Value"
    return f"R#{name}" if name in _RUST_KEYWORDS else name


def _rust_key_type(info: TypeInfo | None) -> str:
    """Map a dictionary key type to its Rust type representation."""
    if info is None:
        return "String"
    match info.base:
        case VT.STRING:
            return "String"
        case VT.INT:
            return "i64"
        case VT.FLOAT:
            return "f64"
        case VT.BOOL:
            return "bool"
        case _:
            return "String"


def _rustfmt(source: str) -> str:
    """Format generated Rust when the stable toolchain is available.

    Args:
        source: Unformatted Rust source code.

    Returns:
        Formatted Rust source code, or unchanged source if rustfmt is missing.

    Raises:
        BuildTimeError: If rustfmt execution fails or exits with an error.
    """
    rustfmt = shutil.which("rustfmt")
    if rustfmt is None:
        return source
    try:
        result = subprocess.run(
            [rustfmt, "--edition", "2021", "--emit", "stdout"],
            input=source.encode("utf-8"),
            capture_output=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BuildTimeError(f"failed to execute rustfmt: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise BuildTimeError(
            f"rustfmt failed: {detail or 'invalid Rust source'}"
        )
    return result.stdout.decode("utf-8")


class RustVisitor(BaseWalker):
    """Generate an owned, fallible Rust parser module.

    DOM values are represented as ``Vec<NodeId>``.  The parser owns the
    ``dom_query::Document`` through ``Rc<RefCell<_>>`` and stores only stable
    node IDs, which avoids self-referential structs while preserving detached
    cached nodes and nested-parser identity.
    """

    TYPES = {
        VT.STRING: "String",
        VT.INT: "i64",
        VT.FLOAT: "f64",
        VT.BOOL: "bool",
        VT.NULL: "()",
        VT.AUTO: "String",
    }
    DEFAULT_TYPE = "String"
    DOCUMENT_TYPE = "rt::Nodes"
    DOCUMENT_ARRAY_TYPE = "rt::Nodes"
    ARRAY_TYPE_FMT = "Vec<{}>"
    OPTIONAL_TYPE_FMT = "Option<{}>"
    OPTIONAL_ON_OMITEMPTY = True
    AND_OP = "&&"

    def __init__(self, var_name: str = "v", indent: str = "    ") -> None:
        """Initialize a Rust visitor."""
        self.var_name = var_name
        self.indent = indent
        self._builder = ModuleBuilder()
        self._structs: dict[str, StructBase] = {}
        self._json_defs: dict[str, JsonDef] = {}
        self._result_variants: dict[str, ResultVariantDef] = {}
        self._emitted_aliases: set[str] = set()
        self._runtime_imports: list[str] = []
        self._runtime_helpers: list[str] = []
        self._predicate_locals: dict[int, tuple[str, bool]] = {}

    def _reset_state(self) -> None:
        self._builder.reset()
        self._structs = {}
        self._json_defs = {}
        self._result_variants = {}
        self._emitted_aliases = set()
        self._predicate_locals = {}

    def _ctx(self, meta: dict[str, Any]) -> WalkContext:
        return WalkContext(
            var_name=self.var_name, indent_char=self.indent, meta=dict(meta)
        )

    def convert(self, module_ast: Module, **meta: Any) -> str:
        """Convert one module AST to Rust source.

        Args:
            module_ast: The parsed DSL module AST.
            **meta: Target build options.

        Returns:
            The generated Rust parser source code.

        Raises:
            BuildTimeError: On unsupported DSL operations or syntax.
        """
        return self.convert_all(module_ast, **meta)[""]

    def convert_all(self, module_ast: Module, **meta: Any) -> dict[str, str]:
        """Run the two traversal passes and return parser source files.

        Args:
            module_ast: The parsed DSL module AST.
            **meta: Target build options.

        Returns:
            Mapping of file paths (empty string for primary module) to code.

        Raises:
            BuildTimeError: On unsupported DSL operations or syntax.
        """
        self._reset_state()
        self._structs = {
            n.name: n for n in module_ast.body if isinstance(n, StructBase)
        }
        self._json_defs = {
            n.name: n for n in module_ast.body if isinstance(n, JsonDef)
        }
        ctx = self._ctx(meta)
        self._walk_module(module_ast, ctx)
        self._emitted_aliases.clear()
        lines = self._walk_module(module_ast, ctx)
        imports = [
            "use std::cell::RefCell;",
            "use std::rc::Rc;",
            "use dom_query::{Document, NodeId};",
            "use super::sscgen_runtime as rt;",
            "use serde::Serialize;",
        ]
        imports.extend(self._builder.imports)
        imports = list(dict.fromkeys(imports))
        source = "// Code generated by ssc-gen. DO NOT EDIT.\n"
        source += "#![allow(dead_code, unused_imports)]\n\n"
        source += "\n".join(imports) + "\n\n"
        source += "\n".join(lines).rstrip() + "\n"
        return {"": _rustfmt(source)}

    def emit_runtime(self) -> str:
        """Return the shared ``sscgen_runtime.rs`` source.

        Returns:
            Formatted Rust runtime source code.

        Raises:
            BuildTimeError: If formatting the runtime fails.
        """
        return _rustfmt(
            rust_runtime_content(self._runtime_imports, self._runtime_helpers)
        )

    def _walk_module(self, module: Module, ctx: WalkContext) -> list[str]:
        lines = list(self.visit_module(module, ctx))
        for node in module.body:
            lines.extend(self.walk(node, ctx))
        return lines

    def _line(self, ctx: WalkContext, expression: str) -> str:
        return f"{ctx.indent}{expression}"

    def _context(self, node: Any) -> str:
        current = node
        field = ""
        struct = ""
        while current is not None:
            if (
                isinstance(current, (Field, InitField, CheckMethod))
                and not field
            ):
                field = getattr(current, "name", "") or "check"
            if isinstance(current, FunctionDef):
                return current.name or "fn"
            if isinstance(current, StructBase):
                struct = current.name
                break
            current = getattr(current, "parent", None)
        return f"{struct}.{field}" if struct and field else struct or "pipeline"

    def _is_in_function(self, node: Any) -> bool:
        current = node
        while current is not None:
            if isinstance(current, FunctionDef):
                return True
            if isinstance(current, StructBase):
                return False
            current = getattr(current, "parent", None)
        return False

    def _dom_ref(self, node: Any) -> str:
        return "&dom" if self._is_in_function(node) else "&self.dom"

    def _dom_clone(self, node: Any) -> str:
        return (
            "dom.clone()" if self._is_in_function(node) else "self.dom.clone()"
        )

    def _type(self, info: TypeInfo | None, *, field: bool = False) -> str:
        if info is None:
            return self.DEFAULT_TYPE
        if info.is_dict:
            key_type = _rust_key_type(info.key_type_info)
            val_type = self._type(info.value_type_info)
            result = f"std::collections::HashMap<{key_type}, {val_type}>"
            if info.is_optional or info.omitempty:
                result = self.OPTIONAL_TYPE_FMT.format(result)
            return result
        if info.base == VT.DOCUMENT:
            result = self.DOCUMENT_TYPE
        elif info.base == VT.NESTED and info.ref:
            result = self._struct_result_type(info.ref)
        elif info.base == VT.JSON and info.ref:
            result = f"{_pascal(info.ref)}Json"
        else:
            result = self.TYPES.get(info.base, self.DEFAULT_TYPE)
        if info.is_array and info.base not in (VT.DOCUMENT, VT.NESTED, VT.JSON):
            result = self.ARRAY_TYPE_FMT.format(result)
        if info.base == VT.JSON and info.is_array:
            result = self.ARRAY_TYPE_FMT.format(result)
        if info.is_optional or info.omitempty:
            result = self.OPTIONAL_TYPE_FMT.format(result)
        return result

    def _struct_result_type(self, name: str) -> str:
        struct = self._structs.get(name)
        if struct is None:
            return f"{_pascal(name)}Type"
        base = f"{_pascal(name)}Type"
        if struct.type == ST.LIST:
            return f"Vec<{base}>"
        if struct.type == ST.FLAT:
            return "Vec<String>"
        return base

    def _field_type(self, node: Field | TypeDefField) -> str:
        if isinstance(node, Field):
            for child in reversed(node.body):
                info = getattr(child, "ret_type_info", None)
                if info and info.base not in (VT.AUTO, VT.NULL):
                    return self._type(info, field=True)
        return self._type(node.ret_type_info, field=True)

    def _enclosing_struct(self, node: Any) -> StructBase | None:
        current = getattr(node, "parent", None)
        while current is not None:
            if isinstance(current, StructBase):
                return current
            current = getattr(current, "parent", None)
        return None

    def _is_raw(self, node: Any) -> bool:
        current = node
        while current is not None:
            if isinstance(current, StructBase):
                return isinstance(current, Struct) and current.type == ST.RAW
            if isinstance(current, FunctionDef):
                return current.is_raw
            current = getattr(current, "parent", None)
        return False

    # === module and declarations ==========================================

    def visit_module(self, node: Module, ctx: WalkContext) -> list[str]:
        """Emit module documentation; imports are added after pass one."""
        lines: list[str] = []
        if node.doc:
            lines.extend(
                f"// {line}" if line else "//" for line in node.doc.splitlines()
            )
            lines.append("")
        return lines

    def visit_utilities(self, node: Utilities, ctx: WalkContext) -> list[str]:
        """Utilities are represented by normal Rust imports."""
        return []

    def visit_code_start_hook(
        self, node: CodeStartHook, ctx: WalkContext
    ) -> list[str]:
        return []

    def visit_code_end_hook(
        self, node: CodeEndHook, ctx: WalkContext
    ) -> list[str]:
        return []

    def visit_typedef(self, node: TypeDef, ctx: WalkContext) -> list[str]:
        name = f"{_pascal(node.name)}Type"
        if node.struct_type == ST.REST:
            return []
        if node.struct_type == ST.FLAT:
            return [f"pub type {name} = Vec<String>;", ""]
        if node.struct_type == ST.DICT:
            value = next(
                (f for f in node.fields if _ident(f.name) == "value"), None
            )
            typ = self._type(value.ret_type_info if value else None)
            return [
                f"pub type {name} = std::collections::HashMap<String, {typ}>;",
                "",
            ]
        if node.struct_type == ST.TABLE:
            return [
                f"pub type {name} = std::collections::HashMap<String, serde_json::Value>;",
                "",
            ]
        lines = ["#[derive(Debug, Clone, Serialize)]", f"pub struct {name} {{"]
        lines.extend(self.walk_children(node, ctx))
        lines.extend(["}", ""])
        return lines

    def visit_typedef_field(
        self, node: TypeDefField, ctx: WalkContext
    ) -> list[str]:
        if node.typedef.struct_type in (ST.DICT, ST.FLAT, ST.TABLE, ST.REST):
            return []
        typ = self._field_type(node)
        attr = (
            '#[serde(skip_serializing_if = "Option::is_none")]'
            if node.ret_type_info
            and (node.ret_type_info.is_optional or node.ret_type_info.omitempty)
            else ""
        )
        lines = [f"{ctx.indent}{attr}"] if attr else []
        lines.append(f"{ctx.indent}pub {_ident(node.name)}: {typ},")
        return lines

    def visit_jsondef(self, node: JsonDef, ctx: WalkContext) -> list[str]:
        if node.is_dict:
            name = f"{_pascal(node.name)}Json"
            key_type = _rust_key_type(node.key_type_info)
            val_type = self._type(node.value_type_info)
            return [
                f"pub type {name} = std::collections::HashMap<{key_type}, {val_type}>;",
                "",
            ]
        self._builder.require_import("use serde_json::Value;")
        self._builder.require_import("use serde::Deserialize;")
        name = f"{_pascal(node.name)}Json"
        lines = [
            "#[derive(Debug, Clone, Serialize, Deserialize)]",
            f"pub struct {name} {{",
        ]
        lines.extend(self.walk_children(node, ctx))
        lines.extend(
            [
                "}",
                "",
                f"impl {name} {{",
                "    pub fn from_value(value: Value) -> Result<Self, rt::SscError> {",
            ]
        )
        lines.append(
            '        value.as_object().ok_or_else(|| rt::SscError::new("jsonify", "expected JSON object"))?;'
        )
        for field in node.body:
            if not isinstance(field, JsonDefField) or (
                field.ret_type_info and field.ret_type_info.skip
            ):
                continue
            lines.extend(self._json_field_decode(field))
        lines.append("        Ok(Self {")
        for field in node.body:
            if isinstance(field, JsonDefField) and not (
                field.ret_type_info and field.ret_type_info.skip
            ):
                lines.append(f"            {_ident(field.name)},")
        lines.extend(["        })", "    }", "", "}", ""])
        return lines

    def _json_field_decode(self, field: JsonDefField) -> list[str]:
        info = field.ret_type_info or TypeInfo(base=VT.STRING)
        name = _ident(field.name)
        wire = field.alias or field.name
        optional = info.is_optional or info.omitempty
        typ = self._type(info)
        path = _str(wire)
        lines = [
            f'        let {name} = match rt::json_path(&value, {path}, "jsonify.{field.name}") {{'
        ]
        lines.extend(
            [
                "            Ok(raw) if !raw.is_null() => {",
            ]
        )
        is_dict = (
            field.is_dict
            or info.is_dict
            or bool(
                info.ref
                and self._json_defs.get(info.ref)
                and self._json_defs[info.ref].is_dict
            )
        )
        if is_dict:
            inner_type = typ[7:-1] if typ.startswith("Option<") else typ
            decoded = f'rt::decode::<{inner_type}>(raw.clone(), "jsonify.{field.name}")?'
            lines.append(
                f"                {('Some(' + decoded + ')') if optional else decoded}"
            )
        elif info.base == VT.JSON and info.ref:
            child = f"{_pascal(info.ref)}Json"
            if info.is_array:
                decoded = f"values.iter().cloned().map({child}::from_value).collect::<Result<Vec<_>, _>>()?"
                lines.extend(
                    [
                        '                let values = raw.as_array().ok_or_else(|| rt::SscError::new("jsonify", "expected JSON array"))?;',
                        f"                {('Some(' + decoded + ')') if optional else decoded}",
                    ]
                )
            else:
                decoded = f"{child}::from_value(raw.clone())?"
                lines.append(
                    f"                {('Some(' + decoded + ')') if optional else decoded}"
                )
        else:
            inner_type = typ[7:-1] if typ.startswith("Option<") else typ
            decoded = f'rt::decode::<{inner_type}>(raw.clone(), "jsonify.{field.name}")?'
            lines.append(
                f"                {('Some(' + decoded + ')') if optional else decoded}"
            )
        lines.append("            },")
        if optional:
            lines.append("            Ok(_) => None,")
        else:
            lines.append(
                f'            Ok(_) => return Err(rt::SscError::new("jsonify.{field.name}", "required field is null")),'
            )
        if optional:
            lines.append("            Err(_) => None,")
        else:
            lines.append("            Err(error) => return Err(error),")
        lines.extend(
            [
                "        };",
            ]
        )
        return lines

    def visit_jsondef_field(
        self, node: JsonDefField, ctx: WalkContext
    ) -> list[str]:
        if node.ret_type_info and node.ret_type_info.skip:
            return []
        info = node.ret_type_info or TypeInfo(base=VT.STRING)
        typ = self._type(info)
        serde_items: list[str] = []
        if node.alias and "." not in node.alias:
            alias_escaped = node.alias.replace("\\", "\\\\").replace('"', '\\"')
            serde_items.append(f'alias = "{alias_escaped}"')
        if info.is_optional or info.omitempty:
            serde_items.append('skip_serializing_if = "Option::is_none"')
        lines = []
        if serde_items:
            lines.append(f"{ctx.indent}#[serde({', '.join(serde_items)})]")
        lines.append(f"{ctx.indent}pub {_ident(node.name)}: {typ},")
        return lines

    def visit_struct(self, node: Struct, ctx: WalkContext) -> list[str]:
        if node.type == ST.TABLE:
            self._builder.require_import("use serde_json::Value;")
        name = _pascal(node.name)
        raw = node.type == ST.RAW
        lines = [f"pub struct {name}Parser {{"]
        lines.append(f"    {'source: String' if raw else 'dom: rt::Dom,'}")
        if not raw:
            lines.append("    root: NodeId,")
        for init in (n for n in node.body if isinstance(n, InitField)):
            lines.append(
                f"    {_ident(init.name)}: {self._type(init.ret_type_info)},"
            )
        lines.extend(["}", "", f"impl {name}Parser {{"])
        lines.extend(self._constructor(node))
        if not raw:
            lines.extend(
                [
                    "    fn root_nodes(&self) -> rt::Nodes { vec![self.root] }",
                    "",
                ]
            )
        for child in node.body:
            lines.extend(self.walk(child, ctx))
        lines.extend(["}", ""])
        return lines

    def visit_struct_rest(
        self, node: StructRest, ctx: WalkContext
    ) -> list[str]:
        self._builder.require_import("use serde_json::Value;")
        return rest.emit_struct_rest(node, ctx, self.walk)

    def _constructor(self, node: Struct) -> list[str]:
        raw = node.type == ST.RAW
        fields = [n for n in node.body if isinstance(n, InitField)]
        if raw:
            lines = [
                "    pub fn new(input: impl Into<String>) -> Result<Self, rt::SscError> {",
                "        let mut parser = Self {",
                "            source: input.into(),",
            ]
        else:
            lines = [
                "    pub fn new(input: impl Into<String>) -> Result<Self, rt::SscError> {",
                "        let document = Document::from(input.into());",
                "        let dom = Rc::new(RefCell::new(document));",
                "        let root = rt::root_id(&dom);",
                "        let mut parser = Self {",
                "            dom,",
            ]
            lines.append("            root,")
        for field in fields:
            lines.append(
                f"            {_ident(field.name)}: Default::default(),"
            )
        lines.extend(
            [
                "        };",
                "        parser.init()?;",
                "        Ok(parser)",
                "    }",
                "",
            ]
        )
        if not raw:
            lines.extend(
                [
                    "    fn from_existing(dom: rt::Dom, root: NodeId) -> Result<Self, rt::SscError> {",
                    "        let mut parser = Self {",
                    "            dom,",
                    "            root,",
                ]
            )
            for field in fields:
                lines.append(
                    f"            {_ident(field.name)}: Default::default(),"
                )
            lines.extend(
                [
                    "        };",
                    "        parser.init()?;",
                    "        Ok(parser)",
                    "    }",
                    "",
                ]
            )
        return lines

    # === lifecycle and structural nodes ===================================

    def visit_init(self, node: Init, ctx: WalkContext) -> list[str]:
        struct = self._enclosing_struct(node)
        if not isinstance(struct, Struct):
            return []
        lines = ["    fn init(&mut self) -> Result<(), rt::SscError> {"]
        lines.extend(self.walk_children(node, ctx.deeper()))
        if not any(isinstance(child, Return) for child in node.body):
            lines.append("        Ok(())")
        lines.extend(["    }", ""])
        return lines

    def visit_init_field_call(
        self, node: InitFieldCall, ctx: WalkContext
    ) -> list[str]:
        if self._is_raw(node):
            value = "self.source.clone()"
        else:
            value = "self.root_nodes()"
        return [
            self._line(
                ctx,
                f"self.{_ident(node.name)} = self.init_{_ident(node.name)}({value})?;",
            )
        ]

    def visit_init_field(self, node: InitField, ctx: WalkContext) -> list[str]:
        arg = "String" if self._is_raw(node) else "rt::Nodes"
        lines = [
            f"    fn init_{_ident(node.name)}(&mut self, v: {arg}) -> Result<{self._type(node.ret_type_info)}, rt::SscError> {{"
        ]
        lines.extend(self.walk_children(node, ctx.deeper()))
        if not any(isinstance(n, Return) for n in node.body):
            last = f"v{len(node.body)}" if node.body else "v"
            lines.append(f"        Ok({last})")
        lines.extend(["    }", ""])
        return lines

    def visit_pre_validate(
        self, node: PreValidate, ctx: WalkContext
    ) -> list[str]:
        arg = "String" if self._is_raw(node) else "rt::Nodes"
        lines = [
            f"    fn pre_validate(&mut self, v: {arg}) -> Result<(), rt::SscError> {{"
        ]
        lines.extend(self.walk_children(node, ctx.deeper()))
        if not any(isinstance(child, Return) for child in node.body):
            lines.extend(["        Ok(())"])
        lines.extend(["    }", ""])
        return lines

    def visit_check_method(
        self, node: CheckMethod, ctx: WalkContext
    ) -> list[str]:
        arg = "String" if self._is_raw(node) else "rt::Nodes"
        lines = [
            f"    pub fn {_ident(node.name)}(&mut self) -> Result<bool, rt::SscError> {{",
            f"        let v: {arg} = self.{'source.clone()' if self._is_raw(node) else 'root_nodes()'}; ",
        ]
        lines.extend(self.walk_children(node, ctx.deeper()))
        last = f"v{len(node.body)}" if node.body else "v"
        if not any(isinstance(child, Return) for child in node.body):
            lines.append(f"        Ok({last})")
        lines.extend(["    }", ""])
        return lines

    def visit_start_parse(
        self, node: StartParse, ctx: WalkContext
    ) -> list[str]:
        struct = node.struct
        name = _pascal(struct.name)
        result_type = self._start_parse_type(struct)
        lines = [
            f"    pub fn parse(&mut self) -> Result<{result_type}, rt::SscError> {{"
        ]
        if node.use_pre_validate:
            value = (
                "self.source.clone()"
                if self._is_raw(struct)
                else "self.root_nodes()"
            )
            lines.append(f"        self.pre_validate({value})?;")
        fields = node.fields
        has_raw_split = struct.type == ST.RAW and any(
            isinstance(child, SplitDoc) for child in struct.body
        )
        if struct.type == ST.LIST or has_raw_split:
            input_val = (
                "self.source.clone()" if has_raw_split else "self.root_nodes()"
            )
            lines.append(f"        let rows = self.split_doc({input_val})?;")
            lines.append("        let mut result = Vec::new();")
            lines.append("        for row in rows {")
            if not has_raw_split:
                lines.append("            let row = vec![row];")
            lines.append(f"            result.push({name}Type {{")
            for field in fields:
                lines.append(
                    f"                {_ident(field.name)}: self.{_ident(field.name)}(row.clone())?,"
                )
            lines.extend(["            });", "        }", "        Ok(result)"])
        elif struct.type == ST.FLAT:
            lines.append("        let mut result = Vec::new();")
            for field in fields:
                call = f"self.{_ident(field.name)}(self.root_nodes())?"
                if self._field_type(field).startswith("Vec<"):
                    lines.append(f"        result.extend({call});")
                else:
                    lines.append(f"        result.push({call});")
            lines.append("        Ok(rt::unique(result))")
        elif struct.type == ST.DICT:
            lines.extend(
                [
                    "        let rows = self.split_doc(self.root_nodes())?;",
                    "        let mut result = std::collections::HashMap::new();",
                    "        for row in rows {",
                    "            let row = vec![row];",
                    "            result.insert(self.parse_key(row.clone())?, self.parse_value(row)?);",
                    "        }",
                    "        Ok(result)",
                ]
            )
        elif struct.type == ST.TABLE:
            lines.extend(
                [
                    "        let table = self.table_config(self.root_nodes())?;",
                    "        let rows = self.table_rows(table)?;",
                    "        let mut result = std::collections::HashMap::new();",
                    "        for row in rows {",
                    "            let row = vec![row];",
                ]
            )
            for field in fields:
                lines.extend(
                    [
                        f"            if !result.contains_key({_str(field.name)}) {{",
                        f"                if let Some(value) = self.{_ident(field.name)}(row.clone())? {{",
                        f'                    result.insert({_str(field.name)}.to_string(), serde_json::to_value(value).map_err(|error| rt::SscError::new("{name}.{field.name}", error.to_string()))?);',
                        "                }",
                        "            }",
                    ]
                )
            lines.extend(["        }", "        Ok(result)"])
        else:
            lines.append(f"        Ok({name}Type {{")
            for field in fields:
                value = (
                    "self.source.clone()"
                    if self._is_raw(struct)
                    else "self.root_nodes()"
                )
                lines.append(
                    f"            {_ident(field.name)}: self.{_ident(field.name)}({value})?,"
                )
            lines.extend(["        })"])
        lines.extend(["    }", ""])
        return lines

    def _start_parse_type(self, struct: StructBase) -> str:
        """Return the owned result type for a parser's public ``parse`` method."""
        name = f"{_pascal(struct.name)}Type"
        if struct.type == ST.LIST:
            return f"Vec<{name}>"
        if struct.type == ST.FLAT:
            return "Vec<String>"
        if struct.type == ST.RAW and any(
            isinstance(child, SplitDoc) for child in struct.body
        ):
            return f"Vec<{name}>"
        return name

    def visit_field(self, node: Field, ctx: WalkContext) -> list[str]:
        struct = self._enclosing_struct(node)
        if struct is not None and struct.type == ST.TABLE:
            return self._visit_table_field(node, ctx)
        arg = "String" if self._is_raw(node) else "rt::Nodes"
        lines = [
            f"    fn {_ident(node.name)}(&mut self, v: {arg}) -> Result<{self._field_type(node)}, rt::SscError> {{"
        ]
        lines.extend(self.walk_children(node, ctx.deeper()))
        if not any(isinstance(n, Return) for n in node.body):
            last = f"v{len(node.body)}" if node.body else "v"
            lines.append(f"        Ok({last})")
        lines.extend(["    }", ""])
        return lines

    def _visit_table_field(self, node: Field, ctx: WalkContext) -> list[str]:
        field_type = self._field_type(node)
        lines = [
            f"    fn {_ident(node.name)}(&mut self, v: rt::Nodes) -> Result<Option<{field_type}>, rt::SscError> {{"
        ]
        inner_ctx = ctx.deeper()
        match_node = None
        fb_node = None
        remaining_nodes: list[Any] = []
        if node.body and isinstance(node.body[0], Match):
            match_node = node.body[0]
            remaining_nodes = [
                n for n in node.body[1:] if not isinstance(n, Return)
            ]
        elif (
            node.body
            and isinstance(node.body[0], Fallback)
            and node.body[0].body
            and isinstance(node.body[0].body[0], Match)
        ):
            fb_node = node.body[0]
            first_child = fb_node.body[0]
            assert isinstance(first_child, Match)
            match_node = first_child
            remaining_nodes = [
                n for n in fb_node.body[1:] if not isinstance(n, Return)
            ]
        elif node.body and isinstance(node.body[0], Fallback):
            fb_node = node.body[0]
            remaining_nodes = [
                n for n in fb_node.body if not isinstance(n, Return)
            ]
        else:
            remaining_nodes = [
                n for n in node.body if not isinstance(n, Return)
            ]

        if match_node is not None:
            self._predicate_locals[id(match_node)] = ("_key", False)
            cond = self._cond_expr(match_node, inner_ctx)
            lines.append(
                self._line(
                    inner_ctx,
                    "let _key = self.table_match_key(v.clone())?;",
                )
            )
            lines.append(
                self._line(
                    inner_ctx,
                    f"if !({cond}) {{ return Ok(None); }}",
                )
            )
        lines.append(
            self._line(
                inner_ctx,
                "let v1 = self.parse_value(v)?;",
            )
        )
        pipe_ctx = inner_ctx.advance()
        if fb_node is not None:
            fallback_lit = self._literal(fb_node.value, field_type)
            closure_ctx = pipe_ctx.deeper()
            lines.append(
                self._line(
                    inner_ctx,
                    f"let value = match (|| -> Result<{field_type}, rt::SscError> {{",
                )
            )
            if remaining_nodes:
                lines.extend(self.walk_pipeline(remaining_nodes, closure_ctx))
                last = f"v{1 + len(remaining_nodes)}"
            else:
                last = "v1"
            lines.append(self._line(closure_ctx, f"Ok({last})"))
            lines.append(
                self._line(
                    inner_ctx,
                    f"}})() {{ Ok(val) => val, Err(_) => {fallback_lit} }};",
                )
            )
            lines.append(self._line(inner_ctx, "Ok(Some(value))"))
        else:
            if remaining_nodes:
                lines.extend(self.walk_pipeline(remaining_nodes, pipe_ctx))
                last = f"v{1 + len(remaining_nodes)}"
            else:
                last = "v1"
            lines.append(self._line(inner_ctx, f"Ok(Some({last}))"))
        lines.extend(["    }", ""])
        return lines

    def visit_split_doc(self, node: SplitDoc, ctx: WalkContext) -> list[str]:
        raw = self._is_raw(node)
        arg = "String" if raw else "rt::Nodes"
        ret = "Vec<String>" if raw else "rt::Nodes"
        lines = [
            f"    fn split_doc(&mut self, v: {arg}) -> Result<{ret}, rt::SscError> {{"
        ]
        lines.extend(self.walk_children(node, ctx.deeper()))
        if not any(isinstance(child, Return) for child in node.body):
            lines.append(
                f"        Ok({f'v{len(node.body)}' if node.body else 'v'})"
            )
        lines.extend(["    }", ""])
        return lines

    def visit_key(self, node: Key, ctx: WalkContext) -> list[str]:
        return self._pipeline_fn(node, ctx, "parse_key")

    def visit_value(self, node: Value, ctx: WalkContext) -> list[str]:
        return self._pipeline_fn(node, ctx, "parse_value")

    def visit_table_config(
        self, node: TableConfig, ctx: WalkContext
    ) -> list[str]:
        self._builder.require_import("use serde_json::Value;")
        return self._pipeline_fn(node, ctx, "table_config")

    def visit_table_match_key(
        self, node: TableMatchKey, ctx: WalkContext
    ) -> list[str]:
        return self._pipeline_fn(node, ctx, "table_match_key")

    def visit_table_rows(self, node: TableRows, ctx: WalkContext) -> list[str]:
        return self._pipeline_fn(node, ctx, "table_rows")

    def _pipeline_fn(self, node: Any, ctx: WalkContext, name: str) -> list[str]:
        arg = "String" if self._is_raw(node) else "rt::Nodes"
        lines = [
            f"    fn {name}(&mut self, v: {arg}) -> Result<{self._type(node.ret_type_info)}, rt::SscError> {{"
        ]
        lines.extend(self.walk_children(node, ctx.deeper()))
        if not any(isinstance(child, Return) for child in node.body):
            lines.append(
                f"        Ok({f'v{len(node.body)}' if node.body else 'v'})"
            )
        lines.extend(["    }", ""])
        return lines

    def visit_return(self, node: Return, ctx: WalkContext) -> list[str]:
        if isinstance(node.parent, PreValidate):
            return [self._line(ctx, "return Ok(());")]
        body = getattr(node.parent, "body", [])
        try:
            index = body.index(node)
        except ValueError:
            index = -1
        if index > 0 and isinstance(body[index - 1], Fallback):
            return []
        return [self._line(ctx, f"return Ok({ctx.prv});")]

    def visit_self(self, node: Self, ctx: WalkContext) -> list[str]:
        return [
            self._line(
                ctx, f"let {ctx.nxt} = self.{_ident(node.name)}.clone();"
            )
        ]

    def visit_nested(self, node: Nested, ctx: WalkContext) -> list[str]:
        cls = _pascal(node.struct_name)
        child_struct = self._structs.get(node.struct_name)
        is_child_raw = (
            isinstance(child_struct, Struct) and child_struct.type == ST.RAW
        )
        is_input_str = bool(
            node.accept_type_info
            and node.accept_type_info.base == VariableType.STRING
        )
        if self._is_raw(node) or is_child_raw or is_input_str:
            return [
                self._line(
                    ctx,
                    f"let {ctx.nxt} = {cls}Parser::new(&{ctx.prv})?.parse()?;",
                )
            ]
        dom = self._dom_clone(node)
        return [
            self._line(
                ctx,
                f'let {ctx.nxt} = {cls}Parser::from_existing({dom}, rt::first_node(&{ctx.prv}, "{self._context(node)}")?)?.parse()?;',
            )
        ]

    def visit_fallback(self, node: Fallback, ctx: WalkContext) -> list[str]:
        typ = self._type(node.ret_type_info)
        fallback = self._literal(node.value, typ)
        inner = ctx.deeper()
        lines = [
            self._line(
                ctx,
                f"return Ok(match (|| -> Result<{typ}, rt::SscError> {{",
            )
        ]
        lines.extend(self.walk_pipeline(node.body, inner))
        last = f"v{ctx.index + len(node.body)}" if node.body else ctx.prv
        lines.extend(
            [
                self._line(
                    inner,
                    f"Ok({'Some(' + last + ')' if typ.startswith('Option<') else last})",
                ),
                self._line(
                    ctx,
                    f"}})() {{ Ok(value) => value, Err(_) => {fallback} }});",
                ),
            ]
        )
        return lines

    def _literal(self, value: Any, typ: str) -> str:
        if value is None or value == "null":
            return "None" if typ.startswith("Option<") else "Default::default()"
        if typ.startswith("Option<"):
            return f"Some({self._literal(value, typ[7:-1])})"
        if typ == "String":
            return f"{_str(value)}.to_string()"
        if typ == "bool":
            return "true" if value else "false"
        if typ == "i64":
            return str(int(value))
        if typ == "f64":
            return repr(float(value))
        if typ.startswith("Vec<"):
            return "Vec::new()"
        return "Default::default()"

    # === selectors and extraction =========================================

    def visit_css_select(self, node: CssSelect, ctx: WalkContext) -> list[str]:
        queries = ", ".join(_str(q) for q in node.queries)
        dom = self._dom_ref(node)
        return [
            self._line(
                ctx,
                f'let {ctx.nxt} = rt::select({dom}, &{ctx.prv}, &[{queries}], "{self._context(node)}")?;',
            )
        ]

    def visit_css_select_all(
        self, node: CssSelectAll, ctx: WalkContext
    ) -> list[str]:
        queries = ", ".join(_str(q) for q in node.queries)
        dom = self._dom_ref(node)
        return [
            self._line(
                ctx,
                f'let {ctx.nxt} = rt::select_all({dom}, &{ctx.prv}, &[{queries}], "{self._context(node)}")?;',
            )
        ]

    def visit_css_remove(self, node: CssRemove, ctx: WalkContext) -> list[str]:
        removed = f"_{ctx.nxt}_removed"
        dom = self._dom_ref(node)
        return [
            self._line(
                ctx,
                f'let {removed} = rt::select_all({dom}, &{ctx.prv}, &[{_str(node.query)}], "{self._context(node)}")?;',
            ),
            self._line(ctx, f"rt::remove({dom}, &{removed})?;"),
            self._line(ctx, f"let {ctx.nxt} = {ctx.prv}.clone();"),
        ]

    def _xpath(self, node: Any, ctx: WalkContext) -> list[str]:
        raise BuildTimeError(
            f"Rust target does not support XPath operation '{type(node).__name__}'; use CSS selectors"
        )

    visit_xpath_select = _xpath
    visit_xpath_select_all = _xpath
    visit_xpath_remove = _xpath

    def visit_text(self, node: Text, ctx: WalkContext) -> list[str]:
        dom = self._dom_ref(node)
        if node.ret_type_info.is_array:
            return [
                self._line(
                    ctx, f"let {ctx.nxt} = rt::text_all({dom}, &{ctx.prv});"
                )
            ]
        return [
            self._line(
                ctx,
                f'let {ctx.nxt} = rt::text({dom}, &{ctx.prv}, "{self._context(node)}")?;',
            )
        ]

    def visit_raw(self, node: Raw, ctx: WalkContext) -> list[str]:
        inner = node.mode == "inner"
        dom = self._dom_ref(node)
        if node.ret_type_info.is_array:
            return [
                self._line(
                    ctx,
                    f"let {ctx.nxt} = rt::raw_all({dom}, &{ctx.prv}, {str(inner).lower()});",
                )
            ]
        return [
            self._line(
                ctx,
                f'let {ctx.nxt} = rt::raw({dom}, &{ctx.prv}, {str(inner).lower()}, "{self._context(node)}")?;',
            )
        ]

    def visit_attr(self, node: Attr, ctx: WalkContext) -> list[str]:
        names = ", ".join(_str(q) for q in node.keys)
        dom = self._dom_ref(node)
        if node.ret_type_info.is_array:
            return [
                self._line(
                    ctx,
                    f"let {ctx.nxt} = rt::attr_all({dom}, &{ctx.prv}, &[{names}]);",
                )
            ]
        return [
            self._line(
                ctx,
                f'let {ctx.nxt} = rt::attr({dom}, &{ctx.prv}, &[{names}], "{self._context(node)}")?;',
            )
        ]

    def _string_call(
        self, node: Any, ctx: WalkContext, function: str, *args: str
    ) -> list[str]:
        suffix = ", " + ", ".join(args) if args else ""
        if node.ret_type_info.is_array:
            expr = f"{ctx.prv}.into_iter().map(|value| rt::{function}(value{suffix})).collect::<Vec<_>>()"
        else:
            expr = f"rt::{function}({ctx.prv}{suffix})"
        return [self._line(ctx, f"let {ctx.nxt} = {expr};")]

    def visit_trim(self, node: Trim, ctx: WalkContext) -> list[str]:
        return self._string_call(
            node,
            ctx,
            "trim",
            "Some(" + _str(node.substr) + ")" if node.substr else "None",
        )

    def visit_l_trim(self, node: Ltrim, ctx: WalkContext) -> list[str]:
        return self._string_call(
            node,
            ctx,
            "ltrim",
            "Some(" + _str(node.substr) + ")" if node.substr else "None",
        )

    def visit_r_trim(self, node: Rtrim, ctx: WalkContext) -> list[str]:
        return self._string_call(
            node,
            ctx,
            "rtrim",
            "Some(" + _str(node.substr) + ")" if node.substr else "None",
        )

    def visit_rm_prefix(self, node: RmPrefix, ctx: WalkContext) -> list[str]:
        return self._string_call(node, ctx, "rm_prefix", _str(node.substr))

    def visit_rm_suffix(self, node: RmSuffix, ctx: WalkContext) -> list[str]:
        return self._string_call(node, ctx, "rm_suffix", _str(node.substr))

    def visit_rm_prefix_suffix(
        self, node: RmPrefixSuffix, ctx: WalkContext
    ) -> list[str]:
        return self._string_call(
            node, ctx, "rm_prefix_suffix", _str(node.substr)
        )

    def visit_format(self, node: Fmt, ctx: WalkContext) -> list[str]:
        if node.ret_type_info.is_array:
            return [
                self._line(
                    ctx,
                    f"let {ctx.nxt} = {ctx.prv}.into_iter().map(|value| rt::fmt_value({_str(node.template)}, &value)).collect::<Vec<_>>();",
                )
            ]
        return [
            self._line(
                ctx,
                f"let {ctx.nxt} = rt::fmt_value({_str(node.template)}, &{ctx.prv});",
            )
        ]

    def visit_repl(self, node: Repl, ctx: WalkContext) -> list[str]:
        return self._string_call(
            node, ctx, "repl", _str(node.old), _str(node.new)
        )

    def visit_repl_map(self, node: ReplMap, ctx: WalkContext) -> list[str]:
        expr = ctx.prv
        for old, new in node.replacements.items():
            expr = f"rt::repl({expr}, {_str(old)}, {_str(new)})"
        return [self._line(ctx, f"let {ctx.nxt} = {expr};")]

    def visit_lower(self, node: Lower, ctx: WalkContext) -> list[str]:
        return self._string_call(node, ctx, "lower")

    def visit_upper(self, node: Upper, ctx: WalkContext) -> list[str]:
        return self._string_call(node, ctx, "upper")

    def visit_split(self, node: Split, ctx: WalkContext) -> list[str]:
        return [
            self._line(
                ctx,
                f"let {ctx.nxt} = {ctx.prv}.split({_str(node.sep)}).map(str::to_string).collect::<Vec<_>>();",
            )
        ]

    def visit_join(self, node: Join, ctx: WalkContext) -> list[str]:
        return [
            self._line(
                ctx, f"let {ctx.nxt} = {ctx.prv}.join({_str(node.sep)});"
            )
        ]

    def visit_norm_space(
        self, node: NormalizeSpace, ctx: WalkContext
    ) -> list[str]:
        return self._string_call(node, ctx, "normalize_space")

    def visit_unescape(self, node: Unescape, ctx: WalkContext) -> list[str]:
        return self._string_call(node, ctx, "unescape")

    # === regex, arrays and casts ===========================================

    def visit_re(self, node: Re, ctx: WalkContext) -> list[str]:
        pattern = validate_rust_pattern(node.pattern)
        if node.ret_type_info.is_array:
            expr = f'{ctx.prv}.into_iter().map(|value| rt::regex_search(value, {_str(pattern)}, "{self._context(node)}")).collect::<Result<Vec<_>, _>>()?'
        else:
            expr = f'rt::regex_search({ctx.prv}, {_str(pattern)}, "{self._context(node)}")?'
        return [self._line(ctx, f"let {ctx.nxt} = {expr};")]

    def visit_re_all(self, node: ReAll, ctx: WalkContext) -> list[str]:
        pattern = validate_rust_pattern(node.pattern)
        return [
            self._line(
                ctx,
                f'let {ctx.nxt} = rt::regex_all({ctx.prv}, {_str(pattern)}, "{self._context(node)}")?;',
            )
        ]

    def visit_re_sub(self, node: ReSub, ctx: WalkContext) -> list[str]:
        pattern = validate_rust_pattern(node.pattern)
        repl = rust_replacement(node.repl)
        if node.ret_type_info.is_array:
            expr = f'{ctx.prv}.into_iter().map(|value| rt::regex_sub(value, {_str(pattern)}, {_str(repl)}, "{self._context(node)}")).collect::<Result<Vec<_>, _>>()?'
        else:
            expr = f'rt::regex_sub({ctx.prv}, {_str(pattern)}, {_str(repl)}, "{self._context(node)}")?'
        return [self._line(ctx, f"let {ctx.nxt} = {expr};")]

    def visit_index(self, node: Index, ctx: WalkContext) -> list[str]:
        if node.accept_type_info.base == VT.DOCUMENT:
            return [
                self._line(
                    ctx,
                    f'let {ctx.nxt} = rt::node_at(&{ctx.prv}, {node.i}, "{self._context(node)}")?;',
                )
            ]
        if node.accept_type_info.is_array:
            return [
                self._line(
                    ctx,
                    f'let {ctx.nxt} = rt::item_at(&{ctx.prv}, {node.i}, "{self._context(node)}")?;',
                )
            ]
        return [
            self._line(
                ctx,
                f'let {ctx.nxt} = rt::index(&{ctx.prv}, {node.i}, "{self._context(node)}")?;',
            )
        ]

    def visit_slice(self, node: Slice, ctx: WalkContext) -> list[str]:
        if (
            node.accept_type_info.base == VT.STRING
            and not node.accept_type_info.is_array
        ):
            return [
                self._line(
                    ctx,
                    f"let {ctx.nxt} = rt::slice(&{ctx.prv}, {node.start}, {node.end});",
                )
            ]
        return [
            self._line(
                ctx,
                f"let {ctx.nxt} = rt::slice_vec(&{ctx.prv}, {node.start}, {node.end});",
            )
        ]

    def visit_len(self, node: Len, ctx: WalkContext) -> list[str]:
        expr = f"{ctx.prv}.len() as i64"
        if (
            node.accept_type_info.base == VT.STRING
            and not node.accept_type_info.is_array
        ):
            expr = f"{ctx.prv}.chars().count() as i64"
        return [self._line(ctx, f"let {ctx.nxt} = {expr};")]

    def visit_unique(self, node: Unique, ctx: WalkContext) -> list[str]:
        return [self._line(ctx, f"let {ctx.nxt} = rt::unique({ctx.prv});")]

    def visit_to_int(self, node: ToInt, ctx: WalkContext) -> list[str]:
        if node.ret_type_info.is_array:
            return [
                self._line(
                    ctx,
                    f'let {ctx.nxt} = {ctx.prv}.into_iter().map(|value| rt::to_int(value, "{self._context(node)}")).collect::<Result<Vec<_>, _>>()?;',
                )
            ]
        return [
            self._line(
                ctx,
                f'let {ctx.nxt} = rt::to_int({ctx.prv}, "{self._context(node)}")?;',
            )
        ]

    def visit_to_float(self, node: ToFloat, ctx: WalkContext) -> list[str]:
        if node.ret_type_info.is_array:
            return [
                self._line(
                    ctx,
                    f'let {ctx.nxt} = {ctx.prv}.into_iter().map(|value| rt::to_float(value, "{self._context(node)}")).collect::<Result<Vec<_>, _>>()?;',
                )
            ]
        return [
            self._line(
                ctx,
                f'let {ctx.nxt} = rt::to_float({ctx.prv}, "{self._context(node)}")?;',
            )
        ]

    def visit_to_bool(self, node: ToBool, ctx: WalkContext) -> list[str]:
        if node.accept_type_info.base == VT.DOCUMENT:
            expr = f"rt::node_bool(&{ctx.prv})"
        elif node.accept_type_info.is_array:
            expr = f"!{ctx.prv}.is_empty()"
        else:
            expr = f"rt::string_bool(&{ctx.prv})"
        return [self._line(ctx, f"let {ctx.nxt} = {expr};")]

    def visit_jsonify(self, node: Jsonify, ctx: WalkContext) -> list[str]:
        if not node.ret_type_info.ref:
            raise BuildTimeError(
                f"jsonify {node.schema_name} has no resolved JSON schema reference"
            )
        name = f"{_pascal(node.schema_name)}Json"
        parsed = f'rt::parse_json(&{ctx.prv}, {_str(node.path or "")}, "{self._context(node)}")?'
        target_def = self._json_defs.get(node.schema_name)
        if target_def and target_def.is_dict:
            target_type = (
                f"Vec<{name}>" if node.ret_type_info.is_array else name
            )
            expr = f'rt::decode::<{target_type}>({parsed}, "{self._context(node)}")?'
        elif node.ret_type_info.is_array:
            expr = f'{parsed}.as_array().ok_or_else(|| rt::SscError::new("{self._context(node)}", "expected JSON array"))?.iter().cloned().map({name}::from_value).collect::<Result<Vec<_>, _>>()?'
        else:
            expr = f"{name}::from_value({parsed})?"
        return [self._line(ctx, f"let {ctx.nxt} = {expr};")]

    # === predicates ========================================================

    def _predicate_target(self, node: Any) -> str:
        container = find_predicate_container(node)
        local = self._predicate_locals.get(id(container))
        if local is not None:
            local_name, is_document = local
            return f"&{local_name}" if is_document else local_name
        info = getattr(container, "accept_type_info", None)
        if isinstance(container, Filter):
            return (
                "&i" if info is not None and info.base == VT.DOCUMENT else "i"
            )
        return "&v" if info is not None and info.base == VT.DOCUMENT else "v"

    def _pred_line(self, condition: str, ctx: WalkContext) -> list[str]:
        prefix = "" if ctx.index == 0 else "&& "
        return [self._line(ctx, f"{prefix}{condition}")]

    def _or(self, expressions: list[str]) -> str:
        return (
            expressions[0]
            if len(expressions) == 1
            else "(" + " || ".join(expressions) + ")"
        )

    def _and(self, expressions: list[str]) -> str:
        return (
            expressions[0]
            if len(expressions) == 1
            else "(" + " && ".join(expressions) + ")"
        )

    def _cond_expr(self, node: Any, ctx: WalkContext) -> str:
        parts = []
        for line in self.walk_children(node, ctx):
            part = line.strip()
            if part.startswith("&& "):
                part = part[3:]
            parts.append(part)
        return self._and(parts) if parts else "true"

    def visit_filter(self, node: Filter, ctx: WalkContext) -> list[str]:
        condition = self._cond_expr(node, ctx)
        if node.accept_type_info.base == VT.DOCUMENT:
            return [
                self._line(ctx, f"let {ctx.nxt} = {{"),
                self._line(ctx.deeper(), "let mut out = Vec::new();"),
                self._line(ctx.deeper(), f"for id in {ctx.prv}.iter() {{"),
                self._line(ctx.deeper().deeper(), "let i = vec![*id];"),
                self._line(
                    ctx.deeper().deeper(),
                    f"if {condition} {{ out.push(*id); }}",
                ),
                self._line(ctx.deeper(), "}"),
                self._line(ctx.deeper(), "out"),
                self._line(ctx, "};"),
            ]
        return [
            self._line(ctx, f"let {ctx.nxt} = {{"),
            self._line(ctx.deeper(), "let mut out = Vec::new();"),
            self._line(ctx.deeper(), f"for i in {ctx.prv}.into_iter() {{"),
            self._line(
                ctx.deeper().deeper(), f"if {condition} {{ out.push(i); }}"
            ),
            self._line(ctx.deeper(), "}"),
            self._line(ctx.deeper(), "out"),
            self._line(ctx, "};"),
        ]

    def visit_assert(self, node: Assert, ctx: WalkContext) -> list[str]:
        self._predicate_locals[id(node)] = (
            ctx.prv,
            node.accept_type_info.base == VT.DOCUMENT,
        )
        condition = self._cond_expr(node, ctx)
        context = self._context(node)
        message = node.message or "assertion failed"
        lines = [
            self._line(
                ctx,
                f"rt::assert_true({condition}, {_str(context)}, {_str(message)})?;",
            )
        ]
        if not isinstance(node.parent, PreValidate):
            lines.append(self._line(ctx, f"let {ctx.nxt} = {ctx.prv}.clone();"))
        return lines

    def visit_match(self, node: Match, ctx: WalkContext) -> list[str]:
        self._predicate_locals[id(node)] = ("_key", False)
        condition = self._cond_expr(node, ctx)
        context = self._context(node)
        return [
            self._line(
                ctx,
                f"let _key = self.table_match_key({ctx.prv}.clone())?;",
            ),
            self._line(
                ctx,
                f'rt::assert_true({condition}, {_str(context)}, "match failed")?;',
            ),
            self._line(
                ctx,
                f"let {ctx.nxt} = self.parse_value({ctx.prv}.clone())?;",
            ),
        ]

    def visit_logic_and(self, node: LogicAnd, ctx: WalkContext) -> list[str]:
        return self._pred_line(f"({self._cond_expr(node, ctx)})", ctx)

    def visit_logic_or(self, node: LogicOr, ctx: WalkContext) -> list[str]:
        parts = [
            line.strip().lstrip("&& ") for line in self.walk_children(node, ctx)
        ]
        return self._pred_line(f"({self._or(parts)})", ctx)

    def visit_logic_not(self, node: LogicNot, ctx: WalkContext) -> list[str]:
        return self._pred_line(f"!({self._cond_expr(node, ctx)})", ctx)

    def visit_predicate_css(self, node: PredCss, ctx: WalkContext) -> list[str]:
        target = self._predicate_target(node)
        dom = self._dom_ref(node)
        return self._pred_line(
            f"rt::pred_css({dom}, {target}, {_str(node.query)})", ctx
        )

    def visit_predicate_xpath(
        self, node: PredXpath, ctx: WalkContext
    ) -> list[str]:
        return self._xpath(node, ctx)

    def _attr_pred(
        self, node: Any, ctx: WalkContext, operation: str
    ) -> list[str]:
        if operation == "re":
            validate_rust_pattern(node.pattern)
        target = self._predicate_target(node)
        dom = self._dom_ref(node)
        attr = f"rt::pred_attr({dom}, {target}, {_str(node.name)}).unwrap_or_default()"
        values = [_str(value) for value in getattr(node, "values", ())]
        if operation == "eq":
            expr = self._or([f"{attr} == {value}" for value in values])
        elif operation == "ne":
            expr = self._and([f"{attr} != {value}" for value in values])
        elif operation == "starts":
            expr = self._or(
                [f"rt::starts(&{attr}, {value})" for value in values]
            )
        elif operation == "ends":
            expr = self._or([f"rt::ends(&{attr}, {value})" for value in values])
        elif operation == "contains":
            expr = self._or(
                [f"rt::contains(&{attr}, {value})" for value in values]
            )
        else:
            expr = f"rt::regex_match(&{attr}, {_str(node.pattern)})"
        return self._pred_line(expr, ctx)

    def visit_predicate_has_attr(
        self, node: PredHasAttr, ctx: WalkContext
    ) -> list[str]:
        target = self._predicate_target(node)
        dom = self._dom_ref(node)
        # pred_attr returns a value; an empty value is still a present attribute,
        # so query the DOM directly through a non-empty-name fallback.
        checks = [
            f"rt::pred_attr({dom}, {target}, {_str(name)}).is_some()"
            for name in node.attrs
        ]
        return self._pred_line(self._or(checks), ctx)

    def visit_predicate_attr_eq(
        self, node: PredAttrEq, ctx: WalkContext
    ) -> list[str]:
        return self._attr_pred(node, ctx, "eq")

    def visit_predicate_attr_ne(
        self, node: PredAttrNe, ctx: WalkContext
    ) -> list[str]:
        return self._attr_pred(node, ctx, "ne")

    def visit_predicate_attr_starts(
        self, node: PredAttrStarts, ctx: WalkContext
    ) -> list[str]:
        return self._attr_pred(node, ctx, "starts")

    def visit_predicate_attr_ends(
        self, node: PredAttrEnds, ctx: WalkContext
    ) -> list[str]:
        return self._attr_pred(node, ctx, "ends")

    def visit_predicate_attr_contains(
        self, node: PredAttrContains, ctx: WalkContext
    ) -> list[str]:
        return self._attr_pred(node, ctx, "contains")

    def visit_predicate_attr_re(
        self, node: PredAttrRe, ctx: WalkContext
    ) -> list[str]:
        return self._attr_pred(node, ctx, "re")

    def _text_pred(
        self, node: Any, ctx: WalkContext, operation: str
    ) -> list[str]:
        if operation == "re":
            validate_rust_pattern(node.pattern)
        target = self._predicate_target(node)
        dom = self._dom_ref(node)
        if target.startswith("&"):
            value = f"rt::pred_text({dom}, {target})"
        else:
            value = target
        values = (
            [_str(item) for item in node.values]
            if hasattr(node, "values")
            else []
        )
        if operation == "contains":
            expr = self._or(
                [f"rt::contains(&{value}, {item})" for item in values]
            )
        elif operation == "starts":
            expr = self._or(
                [f"rt::starts(&{value}, {item})" for item in values]
            )
        elif operation == "ends":
            expr = self._or([f"rt::ends(&{value}, {item})" for item in values])
        else:
            expr = f"rt::regex_match(&{value}, {_str(node.pattern)})"
        return self._pred_line(expr, ctx)

    def visit_predicate_text_contains(
        self, node: PredTextContains, ctx: WalkContext
    ) -> list[str]:
        return self._text_pred(node, ctx, "contains")

    def visit_predicate_text_starts(
        self, node: PredTextStarts, ctx: WalkContext
    ) -> list[str]:
        return self._text_pred(node, ctx, "starts")

    def visit_predicate_text_ends(
        self, node: PredTextEnds, ctx: WalkContext
    ) -> list[str]:
        return self._text_pred(node, ctx, "ends")

    def visit_predicate_text_re(
        self, node: PredTextRe, ctx: WalkContext
    ) -> list[str]:
        return self._text_pred(node, ctx, "re")

    def visit_predicate_contains(
        self, node: PredContains, ctx: WalkContext
    ) -> list[str]:
        return self._text_pred(node, ctx, "contains")

    def visit_predicate_starts(
        self, node: PredStarts, ctx: WalkContext
    ) -> list[str]:
        return self._text_pred(node, ctx, "starts")

    def visit_predicate_ends(
        self, node: PredEnds, ctx: WalkContext
    ) -> list[str]:
        return self._text_pred(node, ctx, "ends")

    def visit_predicate_re(self, node: PredRe, ctx: WalkContext) -> list[str]:
        return self._text_pred(node, ctx, "re")

    def _count_pred(self, node: Any, ctx: WalkContext, op: str) -> list[str]:
        target = self._predicate_target(node)
        count = f"{target}.len()"
        return self._pred_line(f"{count} {op} {node.value}", ctx)

    def visit_predicate_eq(self, node: PredEq, ctx: WalkContext) -> list[str]:
        target = self._predicate_target(node)
        if node.values and isinstance(node.values[0], int):
            return self._pred_line(
                self._or([f"{target}.len() == {v}" for v in node.values]), ctx
            )
        return self._pred_line(
            self._or([f"{target} == {_str(v)}" for v in node.values]), ctx
        )

    def visit_predicate_ne(self, node: PredNe, ctx: WalkContext) -> list[str]:
        target = self._predicate_target(node)
        if node.values and isinstance(node.values[0], int):
            return self._pred_line(
                self._and([f"{target}.len() != {v}" for v in node.values]), ctx
            )
        return self._pred_line(
            self._and([f"{target} != {_str(v)}" for v in node.values]), ctx
        )

    def visit_predicate_count_eq(
        self, node: PredCountEq, ctx: WalkContext
    ) -> list[str]:
        return self._count_pred(node, ctx, "==")

    def visit_predicate_count_gt(
        self, node: PredCountGt, ctx: WalkContext
    ) -> list[str]:
        return self._count_pred(node, ctx, ">")

    def visit_predicate_count_lt(
        self, node: PredCountLt, ctx: WalkContext
    ) -> list[str]:
        return self._count_pred(node, ctx, "<")

    def visit_predicate_count_ne(
        self, node: PredCountNe, ctx: WalkContext
    ) -> list[str]:
        return self._count_pred(node, ctx, "!=")

    def visit_predicate_count_ge(
        self, node: PredCountGe, ctx: WalkContext
    ) -> list[str]:
        return self._count_pred(node, ctx, ">=")

    def visit_predicate_count_le(
        self, node: PredCountLe, ctx: WalkContext
    ) -> list[str]:
        return self._count_pred(node, ctx, "<=")

    def visit_pred_count_range(
        self, node: PredCountRange, ctx: WalkContext
    ) -> list[str]:
        target = self._predicate_target(node)
        return self._pred_line(
            f"{node.start} < {target}.len() && {target}.len() < {node.end}", ctx
        )

    def visit_predicate_re_all(
        self, node: PredReAll, ctx: WalkContext
    ) -> list[str]:
        validate_rust_pattern(node.pattern)
        target = self._predicate_target(node)
        return self._pred_line(
            f"{target}.iter().all(|value| rt::regex_match(value, {_str(node.pattern)}))",
            ctx,
        )

    def visit_predicate_re_any(
        self, node: PredReAny, ctx: WalkContext
    ) -> list[str]:
        validate_rust_pattern(node.pattern)
        target = self._predicate_target(node)
        return self._pred_line(
            f"{target}.iter().any(|value| rt::regex_match(value, {_str(node.pattern)}))",
            ctx,
        )

    # === extensions and unsupported transport =============================

    def visit_extension_call(
        self, node: ExtensionCall, ctx: WalkContext
    ) -> list[str]:
        definition = node.definition
        target = definition.targets.get("rust") if definition else None
        if target is None:
            raise BuildTimeError(
                f"extension operation '{node.qualified_name}' has no 'rust' target"
            )
        for item in target.imports:
            self._builder.require_import(item.value)
            if item.value not in self._runtime_imports:
                self._runtime_imports.append(item.value)
        for helper in target.helpers:
            helper_imports = [item.value for item in helper.imports]
            self._builder.require_runtime(
                helper.name,
                code=helper.source,
                imports=helper_imports,
            )
            if helper.source not in self._runtime_helpers:
                self._runtime_helpers.append(helper.source)
            for item in helper.imports:
                if item.value not in self._runtime_imports:
                    self._runtime_imports.append(item.value)
        rendered = target.emit
        replacements = {
            "{{in}}": ctx.prv,
            "{{out}}": ctx.nxt,
            "{{in_type}}": self._type(node.accept_type_info),
            "{{out_type}}": self._type(node.ret_type_info),
        }
        for old, new in replacements.items():
            rendered = rendered.replace(old, new)
        return [self._line(ctx, line) for line in rendered.splitlines()]

    def visit_method_fetch(
        self, node: MethodFetch, ctx: WalkContext
    ) -> list[str]:
        self._builder.require_import("use serde_json::Value;")
        return rest.emit_method_fetch(node, ctx)

    def visit_method_rest(
        self, node: MethodRest, ctx: WalkContext
    ) -> list[str]:
        self._builder.require_import("use serde_json::Value;")
        return rest.emit_method_rest(node, ctx)

    def visit_error_response(
        self, node: ErrorResponse, ctx: WalkContext
    ) -> list[str]:
        return []

    def visit_result_variant_def(
        self, node: ResultVariantDef, ctx: WalkContext
    ) -> list[str]:
        self._builder.require_import("use serde_json::Value;")
        self._result_variants[node.name] = node
        return rest.emit_result_variant_def(node)

    def visit_result_alias_def(
        self, node: ResultAliasDef, ctx: WalkContext
    ) -> list[str]:
        return rest.emit_result_alias_def(
            node,
            emitted_aliases=self._emitted_aliases,
            result_variants=self._result_variants,
        )

    def visit_matcher_list_def(
        self, node: MatcherListDef, ctx: WalkContext
    ) -> list[str]:
        self._builder.require_import("use serde_json::Value;")
        is_single_rest = True
        if isinstance(node.parent, Module):
            rest_count = sum(
                1 for n in node.parent.body if isinstance(n, StructRest)
            )
            is_single_rest = rest_count <= 1
        return rest.emit_matcher_list_def(
            node, self._result_variants, is_single_rest
        )

    def visit_function_def(
        self, node: FunctionDef, ctx: WalkContext
    ) -> list[str]:
        name = _ident(node.name)
        typ = self._type(node.ret_type_info)
        lines: list[str] = []
        if node.doc:
            lines.extend(
                f"/// {line}" if line else "///"
                for line in node.doc.splitlines()
            )
        lines.append(
            f"pub fn {name}(document: impl Into<String>) -> Result<{typ}, rt::SscError> {{"
        )
        if node.is_raw:
            lines.append("    let v = document.into();")
        else:
            lines.extend(
                [
                    "    let document = Document::from(document.into());",
                    "    let dom = Rc::new(RefCell::new(document));",
                    "    let root = rt::root_id(&dom);",
                    "    let v = vec![root];",
                ]
            )
        lines.extend(self.walk_children(node, ctx))
        if not any(isinstance(n, Return) for n in node.body):
            lines.append(
                f"    Ok({f'v{len(node.body)}' if node.body else 'v'})"
            )
        lines.extend(["}", ""])
        return lines
