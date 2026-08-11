"""Go backend visitor (goquery + net/http + gjson).

Self-contained ``BaseWalker`` subclass emitting Go parser code using the
goquery DOM API.  All ``visit_*`` handlers return ``list[str]``.

Codegen conventions:

- Go 1.26+ (generics for Result types, stdFallback).
- goquery v1.12+ for HTML parsing.
- gjson for JSON path queries (Jsonify), encoding/json for typed schemas.
- Package name from ``ctx.meta["package"]`` (default: output dir name).
- Helper functions NEVER inlined in parser files — they live in
  ``sscgen_runtime.go`` (same package, no import needed).  This prevents
  duplicate-symbol errors when multiple ``.go`` files share a package.
- Indentation: tabs (gofmt standard).
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Any

from ssc_codegen.ast import (
    Attr,
    Assert,
    CheckMethod,
    CodeEndHook,
    CodeStartHook,
    CssRemove,
    CssSelect,
    CssSelectAll,
    ErrorResponse,
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
    PredStarts,
    PredTextContains,
    PredTextEnds,
    PredTextRe,
    PredTextStarts,
    PredXpath,
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
    VariableType as VT,
    XpathRemove,
    XpathSelect,
    XpathSelectAll,
)
from ssc_codegen.naming import (
    to_camel_case,
    to_pascal_case,
    to_snake_case,
)
from ssc_codegen.traversal.utils import (
    find_predicate_container,
    module_has_html_struct,
    module_has_rest,
    module_uses_http,
)
from ssc_codegen.generation.builder import ModuleBuilder
from ssc_codegen.targets.golang.literals import (
    go_str as _go_str,
    go_str_array as _go_str_array,
    go_str_map as _go_str_map,
)
from ssc_codegen.targets.golang.regex import py_re_to_go_raw
from ssc_codegen.targets.golang.runtime import (
    BASE_REST_RUNTIME,
    BASE_RUNTIME,
    GO_RUNTIME,
)
from ssc_codegen.targets.golang import rest
from ssc_codegen.targets.golang.http_libs.base import GoHttpLibStrategy
from ssc_codegen.targets.golang.http_libs.nethttp import NetHttpStrategy
from ssc_codegen.traversal.context import WalkContext
from ssc_codegen.traversal.walker import BaseWalker


# ===========================================================================
# Naming helpers
# ===========================================================================


def _receiver(struct_name: str) -> str:
    """Short receiver name from struct name (first lowercase char)."""
    if not struct_name:
        return "x"
    return struct_name[0].lower()


def _go_method_name(field_name: str) -> str:
    """Field method name: parseXxx (PascalCase, unexported)."""
    return f"parse{to_pascal_case(field_name)}"


def _go_field_name(field_name: str) -> str:
    """Struct field name: PascalCase for exported JSON-serializable fields."""
    return to_pascal_case(field_name)


def _json_tag(field_name: str) -> str:
    """JSON struct tag from DSL field name."""
    return to_snake_case(field_name)


def _go_zero(go_type: str) -> str:
    """Go zero literal for a type string.

    Used for early-return in ``(value, bool)`` TABLE field pattern.
    """
    if go_type.startswith("*"):
        return "nil"
    if go_type.startswith("[]"):
        return go_type + "{}"
    if go_type in ("string",):
        return '""'
    if go_type in ("int64", "int", "int32", "float64", "float32", "bool"):
        return "0"
    if go_type == "any":
        return "nil"
    # struct types — zero value via composite literal.
    return f"{go_type}{{}}"


def _in_table_field(node) -> bool:
    """True if ``node`` is inside a TABLE struct's field body."""
    current = node.parent
    seen_field = False
    while current is not None:
        if isinstance(current, Field):
            seen_field = True
        if seen_field and isinstance(current, StructBase):
            return current.type == ST.TABLE
        current = current.parent
    return False


def _gofmt(source: str) -> str:
    """Run ``gofmt`` on generated source if the toolchain is available.

    Returns the original source unchanged if gofmt is not on PATH (e.g. in
    environments without a Go install). gofmt normalises tabs, struct-field
    column alignment, and import grouping — guarantees the output is what
    a Go developer would produce by hand.
    """
    gofmt = shutil.which("gofmt")
    if not gofmt:
        return source
    try:
        proc = subprocess.run(
            [gofmt],
            input=source,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode == 0 and proc.stdout:
            return proc.stdout
    except (subprocess.SubprocessError, OSError):
        pass
    return source


# ===========================================================================
# GoVisitor
# ===========================================================================


class GoVisitor(BaseWalker):
    """Go codegen visitor (goquery + net/http + gjson).

    All ``visit_*`` handlers return ``list[str]``.
    """

    TYPES: dict[VT, str] = {
        VT.STRING: "string",
        VT.BOOL: "bool",
        VT.INT: "int64",
        VT.FLOAT: "float64",
        VT.NULL: "any",
        VT.JSON: "any",
        VT.NESTED: "any",
        VT.AUTO: "any",
    }
    DEFAULT_TYPE = "any"
    ARRAY_TYPE_FMT = "[]{}"
    OPTIONAL_TYPE_FMT = "*{}"
    OPTIONAL_ON_OMITEMPTY = True
    DOCUMENT_TYPE = "*goquery.Selection"
    DOCUMENT_ARRAY_TYPE = "*goquery.Selection"
    STD_MODULE_NAME = "sscgen_runtime"

    def __init__(self, var_name: str = "v", indent: str = "\t") -> None:
        self.var_name = var_name
        self.indent = indent
        self._file_providers: dict[str, Any] = {}
        self._all_std_defs: dict[str, tuple[list[str], str]] = {}
        self._all_std_imports: list[str] = []
        self._has_rest: bool = False
        self._err_schema_map: dict[str, str] = {}
        self._reset_state()

    # === STATE ===

    def _reset_state(self) -> None:
        self._builder = ModuleBuilder()
        self._http: GoHttpLibStrategy = NetHttpStrategy()
        self._err_schema_map = {}

    def _make_ctx(self, meta: dict) -> WalkContext:
        return WalkContext(
            var_name=self.var_name, indent_char=self.indent, meta=dict(meta)
        )

    # === FILE PROVIDERS ===

    def file(self, filename: str):
        def decorator(fn):
            self._file_providers[filename] = fn
            return fn

        return decorator

    # === PUBLIC API ===

    def convert(self, module_ast: Module, **meta) -> str:
        return self.convert_all(module_ast, **meta)[""]

    def convert_all(self, module_ast: Module, **meta) -> dict[str, str]:
        self._reset_state()
        ctx = self._make_ctx(meta)
        # pass 1: collect std/import registrations.
        self._walk_module(module_ast, ctx)
        # pass 2: emit output.
        lines = self._walk_module(module_ast, ctx)
        self._all_std_defs.update(self._builder.std_defs)
        for imp in self._builder.std_imports:
            if imp not in self._all_std_imports:
                self._all_std_imports.append(imp)
        if module_has_rest(module_ast):
            self._has_rest = True
        out: dict[str, str] = {"": _gofmt("\n".join(lines))}
        for fname, provider in self._file_providers.items():
            out[fname] = provider(module_ast, ctx.meta)
        return out

    def _walk_module(self, module_ast: Module, ctx: WalkContext) -> list[str]:
        lines: list[str] = list(self.visit_module(module_ast, ctx))
        for node in module_ast.body:
            lines.extend(self.walk(node, ctx))
        return lines

    # === RUNTIME EMISSION ===

    def emit_runtime(self, package: str) -> str:
        """Emit sscgen_runtime.go with all accumulated helper functions.

        Same package as parser files — no import needed.
        Called by main.py after all modules are converted.
        """
        lines: list[str] = [
            "// Code generated by ssc-gen. DO NOT EDIT.",
            "",
            f"package {package}",
            "",
        ]

        imports = sorted(set(self._all_std_imports))
        if self._has_rest:
            for imp in self._http.rest_imports:
                if imp not in imports:
                    imports.append(imp)
            imports = sorted(imports)
        if imports:
            lines.append("import (")
            for imp in imports:
                lines.append(f"\t{imp}")
            lines.append(")")
            lines.append("")

        lines.extend(BASE_RUNTIME)

        if self._has_rest:
            lines.extend(BASE_REST_RUNTIME)
            lines.extend(self._http.rest_runtime_lines())

        for _imps, code in self._all_std_defs.values():
            # GO_RUNTIME entries are pre-formatted with literal tabs — do NOT
            # route through inspect.cleandoc, it converts tabs to 8 spaces.
            lines.extend(code.strip().splitlines())
            lines.append("")

        return _gofmt("\n".join(lines))

    def _require(self, name: str) -> None:
        """Register a runtime helper from GO_RUNTIME by name.

        If ``name`` ends with ``Arr``, also registers its scalar base
        (e.g. ``stdTrimArr`` pulls in ``stdTrim``).
        """
        if name.endswith("Arr"):
            base = name[:-3]
            if base in GO_RUNTIME:
                imps, code = GO_RUNTIME[base]
                self._builder.require_std(base, code=code, imports=imps)
        imports, code = GO_RUNTIME[name]
        self._builder.require_std(name, code=code, imports=imports)

    # === TYPE RESOLUTION ===

    def _resolve_type(self, type_info: TypeInfo | None) -> str:
        if type_info is None:
            return self.DEFAULT_TYPE
        if type_info.base == VT.NESTED and type_info.ref:
            t = f"{to_pascal_case(type_info.ref)}Type"
        elif type_info.base == VT.JSON and type_info.ref:
            t = f"{to_pascal_case(type_info.ref)}Json"
        elif type_info.base == VT.DOCUMENT:
            t = self.DOCUMENT_TYPE
        else:
            t = self.TYPES.get(type_info.base, self.DEFAULT_TYPE)
        if type_info.is_array and type_info.base != VT.DOCUMENT:
            t = self.ARRAY_TYPE_FMT.format(t)
        if type_info.is_optional or (
            self.OPTIONAL_ON_OMITEMPTY and type_info.omitempty
        ):
            t = self.OPTIONAL_TYPE_FMT.format(t)
        return t

    def _resolve_start_parse_ret(self, struct: StructBase, name: str) -> str:
        match struct.type:
            case ST.ITEM | ST.DICT | ST.TABLE:
                return f"{name}Type"
            case ST.LIST:
                return f"[]{name}Type"
            case ST.FLAT:
                return "[]string"
            case ST.RAW:
                has_split = any(isinstance(n, SplitDoc) for n in struct.body)
                return f"[]{name}Type" if has_split else f"{name}Type"
            case _:
                return "any"

    # === MODULE ===

    def visit_module(self, node: Module, ctx: WalkContext) -> list[str]:
        package = ctx.meta.get("package", "sscgen")
        lines: list[str] = [
            "// Code generated by ssc-gen. DO NOT EDIT.",
            "",
            f"package {package}",
            "",
        ]
        if node.doc:
            for doc_line in node.doc.splitlines():
                lines.append(f"// {doc_line}" if doc_line else "//")
            lines.append("")

        uses_http = module_uses_http(node)

        if module_has_html_struct(node):
            self._builder.require_import('"github.com/PuerkitoBio/goquery"')
            self._builder.require_import('"strings"')
        if uses_http:
            self._builder.require_import('"' + self._http.import_path + '"')
        return lines

    def visit_utilities(self, node: Utilities, ctx: WalkContext) -> list[str]:
        lines: list[str] = ["import ("]
        std_imports = sorted(set(self._builder.imports))
        for imp in std_imports:
            lines.append(f"\t{imp}")
        lines.append(")")
        lines.append("")
        return lines

    def visit_code_start_hook(
        self, node: CodeStartHook, ctx: WalkContext
    ) -> list[str]:
        return []

    def visit_code_end_hook(
        self, node: CodeEndHook, ctx: WalkContext
    ) -> list[str]:
        return []

    def visit_error_response(
        self, node: ErrorResponse, ctx: WalkContext
    ) -> list[str]:
        return []

    # === TYPES ===

    def visit_jsondef(self, node: JsonDef, ctx: WalkContext) -> list[str]:
        name = to_pascal_case(node.name)
        lines = [f"type {name}Json struct {{", "\t// JSON schema"]
        lines.extend(self.walk_children(node, ctx))
        lines.append("}")
        lines.append("")
        return lines

    def visit_jsondef_field(
        self, node: JsonDefField, ctx: WalkContext
    ) -> list[str]:
        if node.type_info and node.type_info.skip:
            return []
        field_name = to_pascal_case(node.name)
        go_type = self._resolve_type(node.type_info)
        tag = _json_tag(node.name)
        omitempty = (
            ",omitempty" if node.type_info and node.type_info.omitempty else ""
        )
        return [f'\t{field_name} {go_type} `json:"{tag}{omitempty}"`']

    def visit_typedef(self, node: TypeDef, ctx: WalkContext) -> list[str]:
        name = to_pascal_case(node.name)
        match node.struct_type:
            case ST.REST:
                return []
            case ST.FLAT:
                return [f"type {name}Type = []string", ""]
            case ST.DICT:
                value_field = next(
                    (
                        f
                        for f in node.fields
                        if to_camel_case(f.name) == "value"
                    ),
                    None,
                )
                if value_field:
                    vt = self._resolve_type(value_field.type_info)
                else:
                    vt = "any"
                return [f"type {name}Type = map[string]{vt}", ""]
            case ST.TABLE:
                return [f"type {name}Type = map[string]any", ""]
            case ST.ITEM | ST.LIST | ST.RAW:
                lines = [f"type {name}Type struct {{"]
                lines.extend(self.walk_children(node, ctx))
                lines.append("}")
                lines.append("")
                return lines
            case _:
                return []

    def visit_typedef_field(
        self, node: TypeDefField, ctx: WalkContext
    ) -> list[str]:
        if node.typedef.struct_type in (ST.DICT, ST.FLAT, ST.TABLE, ST.REST):
            return []
        field_name = _go_field_name(node.name)
        if node.typedef.struct_type == ST.TABLE and field_name == "Value":
            return []
        go_type = self._resolve_typedef_field_type(node)
        tag = _json_tag(node.name)
        omitempty = (
            ",omitempty" if node.type_info and node.type_info.omitempty else ""
        )
        return [f'\t{field_name} {go_type} `json:"{tag}{omitempty}"`']

    def _resolve_typedef_field_type(self, node: TypeDefField) -> str:
        """Resolve Go type from original struct field body for accuracy."""
        td = node.typedef
        mod = td.parent
        if isinstance(mod, Module):
            struct_name = td.name
            for child in mod.body:
                if isinstance(child, StructBase) and child.name == struct_name:
                    for field in child.body:
                        if isinstance(field, Field) and field.name == node.name:
                            return self._resolve_field_ret_type(field)
        return self._resolve_type(node.type_info)

    # === STRUCT ===

    def _collect_init_fields(
        self, node: StructBase
    ) -> list[tuple[str, str, str]]:
        """Return [(camelName, goType, jsonTag), ...] for init fields.

        InitField nodes are siblings of Init in the struct body
        (Init.body only contains InitFieldCall assignments).
        """
        result: list[tuple[str, str, str]] = []
        for child in node.body:
            if isinstance(child, InitField):
                cn = to_camel_case(child.name)
                gt = self._resolve_type(child.ret_type_info)
                jt = _json_tag(child.name)
                result.append((cn, gt, jt))
        return result

    def visit_struct(self, node: Struct, ctx: WalkContext) -> list[str]:
        lines = self._emit_struct_header(node, ctx)
        for child in node.body:
            lines.extend(self.walk(child, ctx))
        return lines

    def visit_struct_rest(
        self, node: StructRest, ctx: WalkContext
    ) -> list[str]:
        name = to_pascal_case(node.name)
        lines: list[str] = []
        if node.doc:
            for doc_line in node.doc.splitlines():
                lines.append(
                    f"{ctx.indent}// {doc_line}"
                    if doc_line
                    else f"{ctx.indent}//"
                )
        lines.append(f"type {name} struct {{")
        lines.append("}")
        lines.append("")
        # Empty-struct factory: caller writes New<Name>().Method(...) —
        # the struct is a pure namespace marker (no state), receiver
        # methods namespaced by type avoid collisions across schemas in
        # the same package.
        lines.append(f"func New{name}() {name} {{ return {name}{{}} }}")
        lines.append("")
        for child in node.body:
            lines.extend(self.walk(child, ctx))
        return lines

    def _emit_struct_header(
        self, node: StructBase, ctx: WalkContext
    ) -> list[str]:
        name = to_pascal_case(node.name)
        rcv = _receiver(name)
        lines: list[str] = []
        if node.doc:
            for doc_line in node.doc.splitlines():
                lines.append(
                    f"{ctx.indent}// {doc_line}"
                    if doc_line
                    else f"{ctx.indent}//"
                )
        lines.append(f"type {name} struct {{")
        is_raw = isinstance(node, Struct) and node.type == ST.RAW
        sel_type = "string" if is_raw else "*goquery.Selection"
        lines.append(f"\tsel {sel_type}")
        init_fields = self._collect_init_fields(node)
        for cn, gt, _ in init_fields:
            lines.append(f"\t{cn} {gt}")
        lines.append("}")
        lines.append("")

        # Constructor (HTML string → parsed struct)
        if not isinstance(node, StructRest):
            lines.extend(self._emit_constructor(name, rcv, node, ctx))

        return lines

    def _emit_constructor(
        self,
        name: str,
        rcv: str,
        node: StructBase,
        ctx: WalkContext,
    ) -> list[str]:
        i = ctx.indent
        i2 = ctx.deeper().indent
        is_raw = isinstance(node, Struct) and node.type == ST.RAW
        if is_raw:
            lines: list[str] = [
                f"func New{name}(input string) *{name} {{",
                f"{i2}{rcv} := &{name}{{sel: input}}",
            ]
        else:
            lines = [
                f"func New{name}(input string) (*{name}, error) {{",
                f"{i2}doc, err := goquery.NewDocumentFromReader(strings.NewReader(input))",
                f"{i2}if err != nil {{",
                f"{i2}\treturn nil, err",
                f"{i2}}}",
                f"{i2}{rcv} := &{name}{{sel: doc.Selection}}",
            ]
        init_fields = self._collect_init_fields(node)
        if init_fields:
            lines.append(f"{i2}{rcv}.init()")
        if is_raw:
            lines.append(f"{i2}return {rcv}")
        else:
            lines.append(f"{i2}return {rcv}, nil")
        lines.append(f"{i}}}")
        lines.append("")
        return lines

    def visit_result_variant_def(
        self, node: ResultVariantDef, ctx: WalkContext
    ) -> list[str]:
        self._err_schema_map[node.name] = node.schema_name
        self._builder.require_import('"fmt"')
        if node.schema_name:
            self._builder.require_import('"encoding/json"')
        return rest.emit_result_variant_def(node)

    def visit_result_alias_def(
        self, node: ResultAliasDef, ctx: WalkContext
    ) -> list[str]:
        # Go backend uses (value, error) tuples — no marker interface.
        # Imports for json/fmt are pulled in via emit_method_rest instead.
        return []

    def visit_matcher_list_def(
        self, node: MatcherListDef, ctx: WalkContext
    ) -> list[str]:
        has_checks = any(e.required_keys or e.conditions for e in node.entries)
        has_schema_body = any(
            self._err_schema_map.get(e.factory_name) for e in node.entries
        )
        if has_schema_body:
            self._builder.require_import('"encoding/json"')
        if has_checks:
            self._builder.require_import('"github.com/tidwall/gjson"')
        return rest.emit_matcher_list_def(node, self._err_schema_map)

    # === INIT / FIELD METHODS ===

    def visit_init(self, node: Init, ctx: WalkContext) -> list[str]:
        if isinstance(node.parent, StructRest):
            return []
        struct = node.parent
        name = (
            to_pascal_case(struct.name)
            if isinstance(struct, StructBase)
            else "X"
        )
        rcv = _receiver(name)
        i = ctx.indent
        lines = [f"{i}func ({rcv} *{name}) init() {{"]
        lines.extend(self.walk_children(node, ctx))
        lines.append(f"{i}}}")
        lines.append("")
        return lines

    def visit_init_field_call(
        self, node: InitFieldCall, ctx: WalkContext
    ) -> list[str]:
        struct = self._enclosing_struct_name(node)
        rcv = _receiver(struct)
        cn = to_camel_case(node.name)
        cap = cn[0].upper() + cn[1:]
        return [f"{ctx.indent}{rcv}.{cn} = {rcv}.init{cap}({rcv}.sel)"]

    def visit_init_field(self, node: InitField, ctx: WalkContext) -> list[str]:
        struct = self._enclosing_struct_name(node)
        rcv = _receiver(struct)
        cn = to_camel_case(node.name)
        cap = cn[0].upper() + cn[1:]
        t_arg = self._resolve_type(node.accept_type_info)
        t_ret = self._resolve_type(node.ret_type_info)
        lines = [
            f"{ctx.indent}func ({rcv} *{struct}) init{cap}(v {t_arg}) {t_ret} {{"
        ]
        lines.extend(self.walk_children(node, ctx))
        lines.append(f"{ctx.indent}}}")
        lines.append("")
        return lines

    def _nested_struct_ret_type(self, struct_name: str, nested_node) -> str:
        """Resolve Go return type for a Nested call by looking up struct type."""
        p = nested_node.parent
        while p and not isinstance(p, Module):
            p = p.parent
        if isinstance(p, Module):
            for child in p.body:
                if isinstance(child, StructBase) and child.name == struct_name:
                    gt = to_pascal_case(struct_name) + "Type"
                    st = getattr(child, "type", None)
                    if st == ST.FLAT:
                        return "[]string"
                    if st == ST.LIST:
                        return "[]" + gt
                    return gt
        gt = to_pascal_case(struct_name) + "Type"
        bc_arr = getattr(nested_node, "is_array", False)
        return ("[]" + gt) if bc_arr else gt

    def _resolve_field_ret_type(self, node: Field) -> str:
        """Determine Go return type from pipeline body, not field declaration.

        The field's ``ret_type_info`` can lag behind the actual pipeline
        output (e.g. split → []string).  Scan body in reverse for a node
        with concrete type info.
        """
        for child in reversed(node.body):
            ti = getattr(child, "ret_type_info", None)
            if ti and ti.base not in (VT.AUTO, VT.NULL):
                if ti.base == VT.NESTED and not ti.ref:
                    for bc in node.body:
                        sn = getattr(bc, "struct_name", None)
                        if sn:
                            return self._nested_struct_ret_type(sn, bc)
                if ti.base == VT.JSON and not ti.ref:
                    for bc in node.body:
                        sn = getattr(bc, "schema_name", None)
                        if sn:
                            gt = to_pascal_case(sn) + "Json"
                            return ("[]" + gt) if ti.is_array else gt
                return self._resolve_type(ti)
        return self._resolve_type(node.ret_type_info)

    def visit_field(self, node: Field, ctx: WalkContext) -> list[str]:
        struct = self._enclosing_struct_name(node)
        rcv = _receiver(struct)
        mn = _go_method_name(node.name)
        t_arg = self._resolve_type(node.accept_type_info)
        t_ret = self._resolve_field_ret_type(node)
        if node.struct.type == ST.TABLE:
            # Strong-typed (value, bool) pattern: second value signals whether
            # the match predicate succeeded. Caller adds to result map only
            # when bool is true. Eliminates the ``any`` / sentinel workaround.
            t_arg = "*goquery.Selection"
            i1 = ctx.indent
            i2 = ctx.deeper().indent
            lines = [
                f"{i1}func ({rcv} *{struct}) {mn}(v {t_arg}) ({t_ret}, bool) {{",
                f"{i2}_matched := true",
                f"{i2}_result := func() {t_ret} {{",
            ]
            inner_ctx = ctx.deeper().deeper()
            lines.extend(self.walk_children(node, inner_ctx))
            lines.append(f"{i2}}}()")
            lines.append(f"{i2}return _result, _matched")
            lines.append(f"{i1}}}")
            lines.append("")
            return lines
        lines = [
            f"{ctx.indent}func ({rcv} *{struct}) {mn}(v {t_arg}) {t_ret} {{"
        ]
        lines.extend(self.walk_children(node, ctx))
        lines.append(f"{ctx.indent}}}")
        lines.append("")
        return lines

    def visit_pre_validate(
        self, node: PreValidate, ctx: WalkContext
    ) -> list[str]:
        struct = self._enclosing_struct_name(node)
        rcv = _receiver(struct)
        t_arg = self._resolve_type(node.accept_type_info)
        lines = [
            f"{ctx.indent}func ({rcv} *{struct}) preValidate(v {t_arg}) {{"
        ]
        lines.extend(self.walk_children(node, ctx))
        lines.append(f"{ctx.indent}}}")
        lines.append("")
        return lines

    def visit_check_method(
        self, node: CheckMethod, ctx: WalkContext
    ) -> list[str]:
        struct = self._enclosing_struct_name(node)
        rcv = _receiver(struct)
        mn = to_camel_case(node.name)
        t_ret = self._resolve_type(node.ret_type_info)
        lines = [
            f"{ctx.indent}func ({rcv} *{struct}) {mn}() {t_ret} {{",
            f"{ctx.indent * 2}v := {rcv}.sel",
        ]
        lines.extend(self.walk_children(node, ctx))
        lines.append(f"{ctx.indent}}}")
        lines.append("")
        return lines

    def visit_function_def(
        self, node: FunctionDef, ctx: WalkContext
    ) -> list[str]:
        name = to_pascal_case(node.name)
        t_ret = self._resolve_type(node.ret_type_info)
        inner = ctx.deeper()
        lines: list[str] = []
        if node.doc:
            for doc_line in node.doc.splitlines():
                lines.append(f"// {doc_line}")
        lines.append(f"func {name}(document string) {t_ret} {{")
        if node.is_raw:
            lines.append(f"{inner.indent}{inner.var_name} := document")
        else:
            self._builder.require_import('"strings"')
            lines.append(
                f"{inner.indent}doc, err := goquery.NewDocumentFromReader(strings.NewReader(document))"
            )
            lines.append(f"{inner.indent}if err != nil {{")
            lines.append(f"{inner.indent}\tpanic(err)")
            lines.append(f"{inner.indent}}}")
            lines.append(f"{inner.indent}{inner.var_name} := doc.Selection")
        lines.extend(self.walk_children(node, ctx))
        lines.append("}")
        lines.append("")
        return lines

    def visit_split_doc(self, node: SplitDoc, ctx: WalkContext) -> list[str]:
        struct = self._enclosing_struct_name(node)
        rcv = _receiver(struct)
        t_arg = self._resolve_type(node.accept_type_info)
        t_ret = self._resolve_type(node.ret_type_info)
        lines = [
            f"{ctx.indent}func ({rcv} *{struct}) splitDoc(v {t_arg}) {t_ret} {{"
        ]
        lines.extend(self.walk_children(node, ctx))
        lines.append(f"{ctx.indent}}}")
        lines.append("")
        return lines

    def visit_key(self, node: Key, ctx: WalkContext) -> list[str]:
        struct = self._enclosing_struct_name(node)
        rcv = _receiver(struct)
        t_arg = self._resolve_type(node.accept_type_info)
        t_ret = self._resolve_type(node.ret_type_info)
        lines = [
            f"{ctx.indent}func ({rcv} *{struct}) parseKey(v {t_arg}) {t_ret} {{"
        ]
        lines.extend(self.walk_children(node, ctx))
        lines.append(f"{ctx.indent}}}")
        lines.append("")
        return lines

    def visit_value(self, node: Value, ctx: WalkContext) -> list[str]:
        struct = self._enclosing_struct_name(node)
        rcv = _receiver(struct)
        t_arg = self._resolve_type(node.accept_type_info)
        t_ret = self._resolve_type(node.ret_type_info)
        lines = [
            f"{ctx.indent}func ({rcv} *{struct}) parseValue(v {t_arg}) {t_ret} {{"
        ]
        lines.extend(self.walk_children(node, ctx))
        lines.append(f"{ctx.indent}}}")
        lines.append("")
        return lines

    def visit_table_config(
        self, node: TableConfig, ctx: WalkContext
    ) -> list[str]:
        struct = self._enclosing_struct_name(node)
        rcv = _receiver(struct)
        t_arg = self._resolve_type(node.accept_type_info)
        t_ret = self._resolve_type(node.ret_type_info)
        lines = [
            f"{ctx.indent}func ({rcv} *{struct}) tableConfig(v {t_arg}) {t_ret} {{"
        ]
        lines.extend(self.walk_children(node, ctx))
        lines.append(f"{ctx.indent}}}")
        lines.append("")
        return lines

    def visit_table_match_key(
        self, node: TableMatchKey, ctx: WalkContext
    ) -> list[str]:
        struct = self._enclosing_struct_name(node)
        rcv = _receiver(struct)
        t_arg = self._resolve_type(node.accept_type_info)
        t_ret = self._resolve_type(node.ret_type_info)
        lines = [
            f"{ctx.indent}func ({rcv} *{struct}) tableMatchKey(v {t_arg}) {t_ret} {{"
        ]
        lines.extend(self.walk_children(node, ctx))
        lines.append(f"{ctx.indent}}}")
        lines.append("")
        return lines

    def visit_table_rows(self, node: TableRows, ctx: WalkContext) -> list[str]:
        struct = self._enclosing_struct_name(node)
        rcv = _receiver(struct)
        t_arg = self._resolve_type(node.accept_type_info)
        t_ret = self._resolve_type(node.ret_type_info)
        lines = [
            f"{ctx.indent}func ({rcv} *{struct}) tableRows(v {t_arg}) {t_ret} {{"
        ]
        lines.extend(self.walk_children(node, ctx))
        lines.append(f"{ctx.indent}}}")
        lines.append("")
        return lines

    # === START_PARSE ===

    def visit_start_parse(
        self, node: StartParse, ctx: WalkContext
    ) -> list[str]:
        struct = node.struct
        name = to_pascal_case(struct.name)
        rcv = _receiver(name)
        ret_type = self._resolve_start_parse_ret(struct, name)
        ind = ctx.indent_char
        i, i2, i3, i4 = "", ind, ind * 2, ind * 3
        lines: list[str] = [f"{i}func ({rcv} *{name}) Parse() {ret_type} {{"]
        if node.use_pre_validate:
            lines.append(f"{i2}{rcv}.preValidate({rcv}.sel)")

        match struct.type:
            case ST.ITEM:
                if node.fields:
                    lines.append(f"{i2}return {name}Type{{")
                    for f in node.fields:
                        fn = _go_field_name(f.name)
                        mn = _go_method_name(f.name)
                        lines.append(f"{i3}{fn}: {rcv}.{mn}({rcv}.sel),")
                    lines.append(f"{i2}}}")
                else:
                    lines.append(f"{i2}return {name}Type{{}}")
            case ST.RAW:
                if node.use_split_doc:
                    lines.append(f"{i2}rows := {rcv}.splitDoc({rcv}.sel)")
                    lines.append(
                        f"{i2}result := make([]{name}Type, 0, len(rows))"
                    )
                    lines.append(f"{i2}for _, item := range rows {{")
                    lines.append(f"{i3}result = append(result, {name}Type{{")
                    for f in node.fields:
                        fn = _go_field_name(f.name)
                        mn = _go_method_name(f.name)
                        lines.append(f"{i4}{fn}: {rcv}.{mn}(item),")
                    lines.append(f"{i3}}})")
                    lines.append(f"{i2}}}")
                    lines.append(f"{i2}return result")
                else:
                    if node.fields:
                        lines.append(f"{i2}return {name}Type{{")
                        for f in node.fields:
                            fn = _go_field_name(f.name)
                            mn = _go_method_name(f.name)
                            lines.append(f"{i3}{fn}: {rcv}.{mn}({rcv}.sel),")
                        lines.append(f"{i2}}}")
                    else:
                        lines.append(f"{i2}return {name}Type{{}}")
            case ST.LIST:
                lines.append(f"{i2}rows := {rcv}.splitDoc({rcv}.sel)")
                lines.append(
                    f"{i2}result := make([]{name}Type, 0, rows.Length())"
                )
                lines.append(
                    f"{i2}rows.Each(func(_ int, item *goquery.Selection) {{"
                )
                lines.append(f"{i3}result = append(result, {name}Type{{")
                for f in node.fields:
                    fn = _go_field_name(f.name)
                    mn = _go_method_name(f.name)
                    lines.append(f"{i4}{fn}: {rcv}.{mn}(item),")
                lines.append(f"{i3}}})")
                lines.append(f"{i2}}})")
                lines.append(f"{i2}return result")
            case ST.FLAT:
                self._require("stdUnique")
                lines.append(f"{i2}var result []string")
                for f in node.fields:
                    mn = _go_method_name(f.name)
                    if f.ret_type_info and f.ret_type_info.is_array:
                        lines.append(
                            f"{i2}result = append(result, {rcv}.{mn}({rcv}.sel)...)"
                        )
                    else:
                        lines.append(
                            f"{i2}result = append(result, {rcv}.{mn}({rcv}.sel))"
                        )
                lines.append(f"{i2}return stdUnique(result)")
            case ST.DICT:
                lines.append(f"{i2}rows := {rcv}.splitDoc({rcv}.sel)")
                lines.append(f"{i2}result := make({name}Type)")
                lines.append(
                    f"{i2}rows.Each(func(_ int, item *goquery.Selection) {{"
                )
                lines.append(
                    f"{i3}result[{rcv}.parseKey(item)] = {rcv}.parseValue(item)"
                )
                lines.append(f"{i2}}})")
                lines.append(f"{i2}return result")
            case ST.TABLE:
                lines.append(f"{i2}result := make({name}Type)")
                lines.append(f"{i2}table := {rcv}.tableConfig({rcv}.sel)")
                lines.append(
                    f"{i2}{rcv}.tableRows(table).Each(func(_ int, _row *goquery.Selection) {{"
                )
                for f in node.fields:
                    mn = _go_method_name(f.name)
                    tag = _json_tag(f.name)
                    lines.append(
                        f"{i3}if _val, _ok := {rcv}.{mn}(_row); _ok {{"
                    )
                    lines.append(
                        f"{i3}\tif _, _exists := result[{_go_str(tag)}]; !_exists {{"
                    )
                    lines.append(f"{i3}\t\tresult[{_go_str(tag)}] = _val")
                    lines.append(f"{i3}\t}}")
                    lines.append(f"{i3}}}")
                lines.append(f"{i2}}})")
                lines.append(f"{i2}return result")

        lines.append(f"{i}}}")
        lines.append("")
        return lines

    # === SELECTORS ===

    def visit_css_select(self, node: CssSelect, ctx: WalkContext) -> list[str]:
        queries = node.queries or [node.query]
        if len(queries) == 1:
            q = _go_str(queries[0])
            return [f"{ctx.indent}{ctx.nxt} := {ctx.prv}.Find({q}).First()"]
        lines: list[str] = []
        for i, query in enumerate(queries):
            q = _go_str(query)
            if i == 0:
                lines.append(
                    f"{ctx.indent}{ctx.nxt} := {ctx.prv}.Find({q}).First()"
                )
            else:
                lines.append(f"{ctx.indent}if {ctx.nxt}.Length() == 0 {{")
                lines.append(
                    f"{ctx.indent}\t{ctx.nxt} = {ctx.prv}.Find({q}).First()"
                )
                lines.append(f"{ctx.indent}}}")
        return lines

    def visit_css_select_all(
        self, node: CssSelectAll, ctx: WalkContext
    ) -> list[str]:
        queries = node.queries or [node.query]
        if len(queries) == 1:
            q = _go_str(queries[0])
            return [f"{ctx.indent}{ctx.nxt} := {ctx.prv}.Find({q})"]
        lines: list[str] = []
        for i, query in enumerate(queries):
            q = _go_str(query)
            if i == 0:
                lines.append(f"{ctx.indent}{ctx.nxt} := {ctx.prv}.Find({q})")
            else:
                lines.append(f"{ctx.indent}if {ctx.nxt}.Length() == 0 {{")
                lines.append(f"{ctx.indent}\t{ctx.nxt} = {ctx.prv}.Find({q})")
                lines.append(f"{ctx.indent}}}")
        return lines

    def visit_css_remove(self, node: CssRemove, ctx: WalkContext) -> list[str]:
        q = _go_str(node.query)
        return [
            f"{ctx.indent}{ctx.prv}.Find({q}).Remove()",
            f"{ctx.indent}{ctx.nxt} := {ctx.prv}",
        ]

    def visit_xpath_select(
        self, node: XpathSelect, ctx: WalkContext
    ) -> list[str]:
        raise NotImplementedError(
            "XPath is not supported in the Go backend (goquery has no XPath). "
            "Use CSS selectors instead."
        )

    def visit_xpath_select_all(
        self, node: XpathSelectAll, ctx: WalkContext
    ) -> list[str]:
        raise NotImplementedError(
            "XPath is not supported in the Go backend (goquery has no XPath). "
            "Use CSS selectors instead."
        )

    def visit_xpath_remove(
        self, node: XpathRemove, ctx: WalkContext
    ) -> list[str]:
        raise NotImplementedError(
            "XPath is not supported in the Go backend (goquery has no XPath). "
            "Use CSS selectors instead."
        )

    # === EXTRACTS ===

    def visit_text(self, node: Text, ctx: WalkContext) -> list[str]:
        if not node.is_array:
            return [f"{ctx.indent}{ctx.nxt} := {ctx.prv}.Text()"]
        return [
            f"{ctx.indent}{ctx.nxt} := {ctx.prv}.Map(func(_ int, s *goquery.Selection) string {{",
            f"{ctx.indent}\treturn s.Text()",
            f"{ctx.indent}}})",
        ]

    def visit_raw(self, node: Raw, ctx: WalkContext) -> list[str]:
        if not node.is_array:
            return [
                f"{ctx.indent}_html, _ := {ctx.prv}.Html()",
                f"{ctx.indent}{ctx.nxt} := _html",
            ]
        return [
            f"{ctx.indent}{ctx.nxt} := {ctx.prv}.Map(func(_ int, s *goquery.Selection) string {{",
            f"{ctx.indent}\t_h, _ := s.Html()",
            f"{ctx.indent}\treturn _h",
            f"{ctx.indent}}})",
        ]

    def visit_attr(self, node: Attr, ctx: WalkContext) -> list[str]:
        keys = node.keys
        if not node.is_array:
            if len(keys) == 1:
                k = _go_str(keys[0])
                return [f'{ctx.indent}{ctx.nxt} := {ctx.prv}.AttrOr({k}, "")']
            arr = _go_str_array(keys)
            return [
                f"{ctx.indent}var {ctx.nxt} string",
                f"{ctx.indent}_vals := {arr}",
                f"{ctx.indent}for _, _k := range _vals {{",
                f"{ctx.indent}\tif _v, _ok := {ctx.prv}.Attr(_k); _ok {{",
                f"{ctx.indent}\t\t{ctx.nxt} = _v",
                f"{ctx.indent}\t\tbreak",
                f"{ctx.indent}\t}}",
                f"{ctx.indent}}}",
            ]
        if len(keys) == 1:
            k = _go_str(keys[0])
            return [
                f"{ctx.indent}{ctx.nxt} := {ctx.prv}.Map(func(_ int, s *goquery.Selection) string {{",
                f'{ctx.indent}\treturn s.AttrOr({k}, "")',
                f"{ctx.indent}}})",
            ]
        arr = _go_str_array(keys)
        return [
            f"{ctx.indent}var {ctx.nxt} []string",
            f"{ctx.indent}_keys := {arr}",
            f"{ctx.indent}{ctx.prv}.Each(func(_ int, s *goquery.Selection) {{",
            f"{ctx.indent}\tfor _, _k := range _keys {{",
            f"{ctx.indent}\t\tif _v, _ok := s.Attr(_k); _ok {{",
            f"{ctx.indent}\t\t\t{ctx.nxt} = append({ctx.nxt}, _v)",
            f"{ctx.indent}\t\t}}",
            f"{ctx.indent}\t}}",
            f"{ctx.indent}}})",
        ]

    # === STRING ===

    def visit_trim(self, node: Trim, ctx: WalkContext) -> list[str]:
        fn = "stdTrimArr" if node.is_array else "stdTrim"
        self._require(fn)
        v = _go_str(node.substr) if node.substr else '""'
        return [f"{ctx.indent}{ctx.nxt} := {fn}({ctx.prv}, {v})"]

    def visit_l_trim(self, node: Ltrim, ctx: WalkContext) -> list[str]:
        fn = "stdLTrimArr" if node.is_array else "stdLTrim"
        self._require(fn)
        v = _go_str(node.substr) if node.substr else '""'
        return [f"{ctx.indent}{ctx.nxt} := {fn}({ctx.prv}, {v})"]

    def visit_r_trim(self, node: Rtrim, ctx: WalkContext) -> list[str]:
        fn = "stdRTrimArr" if node.is_array else "stdRTrim"
        self._require(fn)
        v = _go_str(node.substr) if node.substr else '""'
        return [f"{ctx.indent}{ctx.nxt} := {fn}({ctx.prv}, {v})"]

    def visit_rm_prefix(self, node: RmPrefix, ctx: WalkContext) -> list[str]:
        fn = "stdRmPrefixArr" if node.is_array else "stdRmPrefix"
        self._require(fn)
        v = _go_str(node.substr)
        return [f"{ctx.indent}{ctx.nxt} := {fn}({ctx.prv}, {v})"]

    def visit_rm_suffix(self, node: RmSuffix, ctx: WalkContext) -> list[str]:
        fn = "stdRmSuffixArr" if node.is_array else "stdRmSuffix"
        self._require(fn)
        v = _go_str(node.substr)
        return [f"{ctx.indent}{ctx.nxt} := {fn}({ctx.prv}, {v})"]

    def visit_rm_prefix_suffix(
        self, node: RmPrefixSuffix, ctx: WalkContext
    ) -> list[str]:
        fn = "stdRmPrefixSuffixArr" if node.is_array else "stdRmPrefixSuffix"
        self._require(fn)
        v = _go_str(node.substr)
        return [f"{ctx.indent}{ctx.nxt} := {fn}({ctx.prv}, {v})"]

    def visit_format(self, node: Fmt, ctx: WalkContext) -> list[str]:
        fn = "stdFmtArr" if node.is_array else "stdFmt"
        self._require(fn)
        tmpl = _go_str(node.template)
        return [f"{ctx.indent}{ctx.nxt} := {fn}({tmpl}, {ctx.prv})"]

    def visit_repl(self, node: Repl, ctx: WalkContext) -> list[str]:
        fn = "stdReplArr" if node.is_array else "stdRepl"
        self._require(fn)
        old = _go_str(node.old)
        new = _go_str(node.new)
        return [f"{ctx.indent}{ctx.nxt} := {fn}({ctx.prv}, {old}, {new})"]

    def visit_repl_map(self, node: ReplMap, ctx: WalkContext) -> list[str]:
        fn = "stdReplMapArr" if node.is_array else "stdReplMap"
        self._require(fn)
        rmap = _go_str_map(dict(node.replacements))
        return [f"{ctx.indent}{ctx.nxt} := {fn}({ctx.prv}, {rmap})"]

    def visit_lower(self, node: Lower, ctx: WalkContext) -> list[str]:
        if node.is_array:
            self._require("stdLowerArr")
            return [f"{ctx.indent}{ctx.nxt} := stdLowerArr({ctx.prv})"]
        self._builder.require_import('"strings"')
        return [f"{ctx.indent}{ctx.nxt} := strings.ToLower({ctx.prv})"]

    def visit_upper(self, node: Upper, ctx: WalkContext) -> list[str]:
        if node.is_array:
            self._require("stdUpperArr")
            return [f"{ctx.indent}{ctx.nxt} := stdUpperArr({ctx.prv})"]
        self._builder.require_import('"strings"')
        return [f"{ctx.indent}{ctx.nxt} := strings.ToUpper({ctx.prv})"]

    def visit_split(self, node: Split, ctx: WalkContext) -> list[str]:
        self._builder.require_import('"strings"')
        sep = _go_str(node.sep)
        return [f"{ctx.indent}{ctx.nxt} := strings.Split({ctx.prv}, {sep})"]

    def visit_join(self, node: Join, ctx: WalkContext) -> list[str]:
        self._builder.require_import('"strings"')
        sep = _go_str(node.sep)
        return [f"{ctx.indent}{ctx.nxt} := strings.Join({ctx.prv}, {sep})"]

    def visit_norm_space(
        self, node: NormalizeSpace, ctx: WalkContext
    ) -> list[str]:
        fn = "stdNormSpaceArr" if node.is_array else "stdNormSpace"
        self._require(fn)
        return [f"{ctx.indent}{ctx.nxt} := {fn}({ctx.prv})"]

    def visit_unescape(self, node: Unescape, ctx: WalkContext) -> list[str]:
        fn = "stdUnescapeArr" if node.is_array else "stdUnescape"
        self._require(fn)
        return [f"{ctx.indent}{ctx.nxt} := {fn}({ctx.prv})"]

    # === REGEX ===

    def visit_re(self, node: Re, ctx: WalkContext) -> list[str]:
        fn = "stdReSearchArr" if node.is_array else "stdReSearch"
        self._require(fn)
        location = self._resolve_location(node)
        src_file = self._resolve_source_file(node)
        span = node.span
        src_line = span.start.line if span else 0
        src_col = span.start.column if span else 0
        loc_str = f" at {location}" if location else ""
        msg = (
            f"{src_file}:{src_line}:{src_col} "
            f"re-match failed{loc_str} pattern={node.pattern}"
        )
        pattern = py_re_to_go_raw(node.pattern)
        return [
            f"{ctx.indent}{ctx.nxt} := {fn}({pattern}, {ctx.prv}, {_go_str(msg)})"
        ]

    def visit_re_all(self, node: ReAll, ctx: WalkContext) -> list[str]:
        self._builder.require_import('"regexp"')
        pattern = py_re_to_go_raw(node.pattern)
        return [
            f"{ctx.indent}_re := regexp.MustCompile({pattern})",
            f"{ctx.indent}_matches := _re.FindAllStringSubmatch({ctx.prv}, -1)",
            f"{ctx.indent}{ctx.nxt} := make([]string, len(_matches))",
            f"{ctx.indent}for _i, _m := range _matches {{",
            f"{ctx.indent}\t{ctx.nxt}[_i] = _m[1]",
            f"{ctx.indent}}}",
        ]

    def visit_re_sub(self, node: ReSub, ctx: WalkContext) -> list[str]:
        self._builder.require_import('"regexp"')
        pattern = py_re_to_go_raw(node.pattern)
        repl = _go_str(node.repl)
        if not node.is_array:
            return [
                f"{ctx.indent}_re := regexp.MustCompile({pattern})",
                f"{ctx.indent}{ctx.nxt} := _re.ReplaceAllString({ctx.prv}, {repl})",
            ]
        return [
            f"{ctx.indent}_re := regexp.MustCompile({pattern})",
            f"{ctx.indent}{ctx.nxt} := make([]string, len({ctx.prv}))",
            f"{ctx.indent}for _i, _s := range {ctx.prv} {{",
            f"{ctx.indent}\t{ctx.nxt}[_i] = _re.ReplaceAllString(_s, {repl})",
            f"{ctx.indent}}}",
        ]

    # === ARRAY ===

    def visit_index(self, node: Index, ctx: WalkContext) -> list[str]:
        i = node.i
        at = node.accept_type_info
        if at and at.base == VT.STRING and not at.is_array:
            idx = f"len({ctx.prv})-{abs(i)}" if i < 0 else str(i)
            return [f"{ctx.indent}{ctx.nxt} := string({ctx.prv}[{idx}])"]
        if i < 0:
            return [f"{ctx.indent}{ctx.nxt} := {ctx.prv}[len({ctx.prv})+{i}]"]
        return [f"{ctx.indent}{ctx.nxt} := {ctx.prv}[{i}]"]

    def visit_slice(self, node: Slice, ctx: WalkContext) -> list[str]:
        start = node.start
        end = node.end
        return [f"{ctx.indent}{ctx.nxt} := {ctx.prv}[{start}:{end}]"]

    def visit_len(self, node: Len, ctx: WalkContext) -> list[str]:
        # stdLen handles *goquery.Selection | string | []string via type switch.
        # accept_type_info on Len stays AUTO (type-checking doesn't propagate),
        # so we can't pick .Length() vs len() statically without a helper.
        self._require("stdLen")
        return [f"{ctx.indent}{ctx.nxt} := stdLen({ctx.prv})"]

    def visit_unique(self, node: Unique, ctx: WalkContext) -> list[str]:
        self._require("stdUnique")
        return [f"{ctx.indent}{ctx.nxt} := stdUnique({ctx.prv})"]

    # === CASTS ===

    def visit_to_int(self, node: ToInt, ctx: WalkContext) -> list[str]:
        fn = "stdToIntArr" if node.is_array else "stdToInt"
        self._require(fn)
        return [f"{ctx.indent}{ctx.nxt} := {fn}({ctx.prv})"]

    def visit_to_float(self, node: ToFloat, ctx: WalkContext) -> list[str]:
        fn = "stdToFloatArr" if node.is_array else "stdToFloat"
        self._require(fn)
        return [f"{ctx.indent}{ctx.nxt} := {fn}({ctx.prv})"]

    def visit_to_bool(self, node: ToBool, ctx: WalkContext) -> list[str]:
        at = node.accept_type_info
        if at and at.base == VT.DOCUMENT:
            return [f"{ctx.indent}{ctx.nxt} := {ctx.prv}.Length() > 0"]
        if at and at.is_array:
            return [f"{ctx.indent}{ctx.nxt} := len({ctx.prv}) > 0"]
        return [f'{ctx.indent}{ctx.nxt} := {ctx.prv} != ""']

    def visit_jsonify(self, node: Jsonify, ctx: WalkContext) -> list[str]:
        self._require("stdJsonify")
        ti = node.ret_type_info
        if ti.base == VT.JSON and not ti.ref and node.schema_name:
            go_type = to_pascal_case(node.schema_name) + "Json"
            if ti.is_array:
                go_type = "[]" + go_type
        else:
            go_type = self._resolve_type(ti)
        path = _go_str(node.path) if node.path else '""'
        return [
            f"{ctx.indent}var {ctx.nxt} {go_type}",
            f"{ctx.indent}stdJsonify({ctx.prv}, {path}, &{ctx.nxt})",
        ]

    def visit_nested(self, node: Nested, ctx: WalkContext) -> list[str]:
        cls = to_pascal_case(node.struct_name)
        return [f"{ctx.indent}{ctx.nxt} := (&{cls}{{sel: {ctx.prv}}}).Parse()"]

    # === CONTROL ===

    def visit_self(self, node: Self, ctx: WalkContext) -> list[str]:
        struct = self._enclosing_struct_name(node)
        rcv = _receiver(struct)
        name = to_camel_case(node.name)
        return [f"{ctx.indent}{ctx.nxt} := {rcv}.{name}"]

    def visit_return(self, node: Return, ctx: WalkContext) -> list[str]:
        if isinstance(node.parent, PreValidate):
            return [f"{ctx.indent}return"]
        body = getattr(node.parent, "body", None) or []
        try:
            idx = body.index(node)
        except ValueError:
            idx = -1
        if idx > 0 and isinstance(body[idx - 1], Fallback):
            return []
        return [f"{ctx.indent}return {ctx.prv}"]

    def visit_fallback(self, node: Fallback, ctx: WalkContext) -> list[str]:
        inner_ctx = ctx.deeper()
        inner_indent = inner_ctx.indent
        last_idx = ctx.index + len(node.body)
        last_var = (
            ctx.var_name if last_idx == 0 else f"{ctx.var_name}{last_idx}"
        )
        ret_type = self._resolve_fallback_type(node)
        val = self._go_fallback_value(node.value, ret_type)
        lines = [f"{ctx.indent}return stdFallback(func() {ret_type} {{"]
        lines.extend(self.walk_pipeline(node.body, inner_ctx))
        lines.append(f"{inner_indent}return {last_var}")
        lines.append(f"{ctx.indent}}}, {val})")
        return lines

    def _go_fallback_value(self, value: Any, go_type: str) -> str:
        """Type-aware fallback literal matching the Go return type."""
        if go_type.startswith("[]"):
            return go_type + "{}"
        if go_type.startswith("*"):
            return "nil"
        if go_type == "string":
            return _go_str(str(value)) if value is not None else '""'
        if go_type == "int64":
            try:
                return str(int(value))
            except (TypeError, ValueError):
                return "0"
        if go_type == "float64":
            try:
                return repr(float(value))
            except (TypeError, ValueError):
                return "0.0"
        if go_type == "bool":
            return "true" if value else "false"
        return "nil"

    # === PREDICATE CONTAINERS ===

    def _cond_expr(self, node, ctx: WalkContext) -> str:
        """Collect predicate children via walk_children, join to expression."""
        lines = self.walk_children(node, ctx)
        parts = [ln.strip() for ln in lines if ln.strip()]
        return " ".join(parts) if parts else "true"

    def visit_filter(self, node: Filter, ctx: WalkContext) -> list[str]:
        expr = self._cond_expr(node, ctx)
        i1, i2 = ctx.indent, ctx.deeper().indent
        at = getattr(node, "accept_type_info", None)
        if at and at.base == VT.DOCUMENT:
            return [
                f"{i1}{ctx.nxt} := {ctx.prv}.FilterFunction(func(_ int, i *goquery.Selection) bool {{",
                f"{i2}return {expr}",
                f"{i1}}})",
            ]
        return [
            f"{i1}var {ctx.nxt} []string",
            f"{i1}for _, i := range {ctx.prv} {{",
            f"{i2}if {expr} {{",
            f"{i2}\t{ctx.nxt} = append({ctx.nxt}, i)",
            f"{i2}}}",
            f"{i1}}}",
        ]

    def _resolve_location(self, node) -> str:
        struct_name = ""
        field_part = ""
        current = node.parent
        while current is not None:
            if isinstance(current, PreValidate) and not field_part:
                field_part = "@pre-validate"
            elif isinstance(current, (Field, Key, Value)) and not field_part:
                field_part = getattr(current, "name", "") or (
                    "value" if isinstance(current, Value) else "key"
                )
            if isinstance(current, StructBase):
                struct_name = to_pascal_case(current.name)
                break
            current = current.parent
        if field_part:
            return f"{struct_name}.{field_part}" if struct_name else field_part
        return struct_name

    def _resolve_source_file(self, node) -> str:
        current = node
        while current is not None:
            if isinstance(current, Module):
                return current.source_file
            current = current.parent
        return ""

    def _enclosing_struct_name(self, node) -> str:
        current = node.parent
        while current is not None:
            if isinstance(current, StructBase):
                return to_pascal_case(current.name)
            current = current.parent
        return "X"

    def _resolve_fallback_type(self, node) -> str:
        """Determine the Go return type for a Fallback closure.

        Prefers the inferred type from the fallback body's last operation.
        Falls back to the enclosing field's declared return type.
        """
        if node.body:
            last = node.body[-1]
            for attr in ("ret_type_info", "accept_type_info"):
                ti = getattr(last, attr, None)
                if ti and ti.base not in (VT.AUTO, VT.NULL):
                    return self._resolve_type(ti)
        current = node.parent
        while current is not None:
            if isinstance(current, (Field, Key, Value, InitField)):
                return self._resolve_type(current.ret_type_info)
            current = current.parent
        return "string"

    def visit_assert(self, node: Assert, ctx: WalkContext) -> list[str]:
        location = self._resolve_location(node)
        if node.message:
            msg = node.message
        else:
            loc_str = f" at {location}" if location else ""
            src_file = self._resolve_source_file(node)
            span = node.span
            src_line = span.start.line if span else 0
            src_col = span.start.column if span else 0
            msg = f"{src_file}:{src_line}:{src_col} assertion failed{loc_str}"
        self._require("stdAssert")
        expr = self._cond_expr(node, ctx)
        if isinstance(node.parent, PreValidate):
            setattr(node, "_local_name", "v")
            return [f"{ctx.indent}stdAssert({expr}, {_go_str(msg)})"]
        setattr(node, "_local_name", ctx.prv)
        return [
            f"{ctx.indent}stdAssert({expr}, {_go_str(msg)})",
            f"{ctx.indent}{ctx.nxt} := {ctx.prv}",
        ]

    def visit_match(self, node: Match, ctx: WalkContext) -> list[str]:
        struct = self._enclosing_struct_name(node)
        rcv = _receiver(struct)
        setattr(node, "_local_name", "_key")
        expr = self._cond_expr(node, ctx)
        i1, i2 = ctx.indent, ctx.deeper().indent
        # Match lives inside a TABLE field body wrapped in an IIFE that
        # captures ``_matched``. On no-match: flip the flag and return the
        # zero of the field's return type.
        field = node.parent
        t_ret = (
            self._resolve_field_ret_type(field)
            if isinstance(field, Field)
            else "any"
        )
        zero = _go_zero(t_ret)
        lines = [
            f"{i1}_key := {rcv}.tableMatchKey({ctx.prv})",
            f"{i1}if !({expr}) {{",
            f"{i2}_matched = false",
            f"{i2}return {zero}",
            f"{i1}}}",
            f"{i1}{ctx.nxt} := {rcv}.parseValue({ctx.prv})",
        ]
        return lines

    # === LOGIC ===

    def visit_logic_and(self, node: LogicAnd, ctx: WalkContext) -> list[str]:
        expr = self._cond_expr(node, ctx)
        return self._pred_line(f"({expr})", ctx)

    def visit_logic_or(self, node: LogicOr, ctx: WalkContext) -> list[str]:
        expr = self._cond_expr(node, ctx)
        return self._pred_line(f"({expr})", ctx, op="||")

    def visit_logic_not(self, node: LogicNot, ctx: WalkContext) -> list[str]:
        expr = self._cond_expr(node, ctx)
        return self._pred_line(f"!({expr})", ctx)

    # === PREDICATES ===

    def _pred_target(self, node) -> str:
        container = find_predicate_container(node)
        if isinstance(container, Filter):
            return "i"
        if isinstance(container, (Match, Assert, PreValidate)):
            return getattr(container, "_local_name", "i")
        return "v"

    def _pred_text_target(self, node, ctx: WalkContext) -> str:
        target = self._pred_target(node)
        container = find_predicate_container(node)
        if target == "i" and isinstance(container, Filter):
            at = getattr(container, "accept_type_info", None)
            if at and at.base == VT.DOCUMENT:
                return "i.Text()"
        return target

    def _any_of(self, fmt: str, target: str, values) -> str:
        """Join checks with || (any-of semantics), wrapped in parens."""
        parts = [fmt.format(t=target, v=_go_str(val)) for val in values]
        if len(parts) == 1:
            return parts[0]
        return "(" + " || ".join(parts) + ")"

    def _all_of(self, fmt: str, target: str, values) -> str:
        """Join checks with && (all-of semantics), wrapped in parens."""
        parts = [fmt.format(t=target, v=_go_str(val)) for val in values]
        if len(parts) == 1:
            return parts[0]
        return "(" + " && ".join(parts) + ")"

    def _pred_line(
        self, cond: str, ctx: WalkContext, op: str = "&&"
    ) -> list[str]:
        prefix = "" if ctx.index == 0 else f"{op} "
        return [f"{ctx.indent}{prefix}{cond}"]

    def visit_predicate_css(self, node: PredCss, ctx: WalkContext) -> list[str]:
        q = _go_str(node.query)
        target = self._pred_target(node)
        return self._pred_line(f"{target}.Find({q}).Length() > 0", ctx)

    def visit_predicate_xpath(
        self, node: PredXpath, ctx: WalkContext
    ) -> list[str]:
        raise NotImplementedError(
            "XPath predicates are not supported in the Go backend."
        )

    def visit_predicate_has_attr(
        self, node: PredHasAttr, ctx: WalkContext
    ) -> list[str]:
        self._require("stdHasAttr")
        target = self._pred_target(node)
        keys = node.attrs
        if len(keys) == 1:
            cond = f"stdHasAttr({target}, {_go_str(keys[0])})"
        else:
            cond = self._any_of("stdHasAttr({t}, {v})", target, keys)
        return self._pred_line(cond, ctx)

    def visit_predicate_attr_eq(
        self, node: PredAttrEq, ctx: WalkContext
    ) -> list[str]:
        self._require("stdAttrOr")
        name = _go_str(node.name)
        expr = f"stdAttrOr({self._pred_target(node)}, {name})"
        cond = self._any_of("{t} == {v}", expr, node.values)
        return self._pred_line(cond, ctx)

    def visit_predicate_attr_ne(
        self, node: PredAttrNe, ctx: WalkContext
    ) -> list[str]:
        self._require("stdAttrOr")
        name = _go_str(node.name)
        expr = f"stdAttrOr({self._pred_target(node)}, {name})"
        cond = self._all_of("{t} != {v}", expr, node.values)
        return self._pred_line(cond, ctx)

    def visit_predicate_attr_starts(
        self, node: PredAttrStarts, ctx: WalkContext
    ) -> list[str]:
        self._builder.require_import('"strings"')
        self._require("stdAttrOr")
        name = _go_str(node.name)
        expr = f"stdAttrOr({self._pred_target(node)}, {name})"
        cond = self._any_of("strings.HasPrefix({t}, {v})", expr, node.values)
        return self._pred_line(cond, ctx)

    def visit_predicate_attr_ends(
        self, node: PredAttrEnds, ctx: WalkContext
    ) -> list[str]:
        self._builder.require_import('"strings"')
        self._require("stdAttrOr")
        name = _go_str(node.name)
        expr = f"stdAttrOr({self._pred_target(node)}, {name})"
        cond = self._any_of("strings.HasSuffix({t}, {v})", expr, node.values)
        return self._pred_line(cond, ctx)

    def visit_predicate_attr_contains(
        self, node: PredAttrContains, ctx: WalkContext
    ) -> list[str]:
        self._builder.require_import('"strings"')
        self._require("stdAttrOr")
        name = _go_str(node.name)
        expr = f"stdAttrOr({self._pred_target(node)}, {name})"
        cond = self._any_of("strings.Contains({t}, {v})", expr, node.values)
        return self._pred_line(cond, ctx)

    def visit_predicate_attr_re(
        self, node: PredAttrRe, ctx: WalkContext
    ) -> list[str]:
        self._require("stdReMatch")
        self._require("stdAttrOr")
        rx = py_re_to_go_raw(node.pattern)
        name = _go_str(node.name)
        target = self._pred_target(node)
        cond = f"stdReMatch({rx}, stdAttrOr({target}, {name}))"
        return self._pred_line(cond, ctx)

    def visit_predicate_text_contains(
        self, node: PredTextContains, ctx: WalkContext
    ) -> list[str]:
        self._builder.require_import('"strings"')
        target = self._pred_text_target(node, ctx)
        cond = self._any_of("strings.Contains({t}, {v})", target, node.values)
        return self._pred_line(cond, ctx)

    def visit_predicate_text_starts(
        self, node: PredTextStarts, ctx: WalkContext
    ) -> list[str]:
        self._builder.require_import('"strings"')
        target = self._pred_text_target(node, ctx)
        cond = self._any_of("strings.HasPrefix({t}, {v})", target, node.values)
        return self._pred_line(cond, ctx)

    def visit_predicate_text_ends(
        self, node: PredTextEnds, ctx: WalkContext
    ) -> list[str]:
        self._builder.require_import('"strings"')
        target = self._pred_text_target(node, ctx)
        cond = self._any_of("strings.HasSuffix({t}, {v})", target, node.values)
        return self._pred_line(cond, ctx)

    def visit_predicate_text_re(
        self, node: PredTextRe, ctx: WalkContext
    ) -> list[str]:
        self._require("stdReMatch")
        rx = py_re_to_go_raw(node.pattern)
        target = self._pred_text_target(node, ctx)
        cond = f"stdReMatch({rx}, {target})"
        return self._pred_line(cond, ctx)

    def visit_predicate_contains(
        self, node: PredContains, ctx: WalkContext
    ) -> list[str]:
        self._builder.require_import('"strings"')
        target = self._pred_text_target(node, ctx)
        cond = self._any_of("strings.Contains({t}, {v})", target, node.values)
        return self._pred_line(cond, ctx)

    def visit_predicate_eq(self, node: PredEq, ctx: WalkContext) -> list[str]:
        target = self._pred_text_target(node, ctx)
        if isinstance(node.values[0], int):
            return self._pred_line(f"len({target}) == {node.values[0]}", ctx)
        cond = self._any_of("{t} == {v}", target, node.values)
        return self._pred_line(cond, ctx)

    def visit_predicate_ne(self, node: PredNe, ctx: WalkContext) -> list[str]:
        target = self._pred_text_target(node, ctx)
        if isinstance(node.values[0], int):
            return self._pred_line(f"len({target}) != {node.values[0]}", ctx)
        cond = self._all_of("{t} != {v}", target, node.values)
        return self._pred_line(cond, ctx)

    def visit_predicate_starts(
        self, node: PredStarts, ctx: WalkContext
    ) -> list[str]:
        self._builder.require_import('"strings"')
        target = self._pred_text_target(node, ctx)
        cond = self._any_of("strings.HasPrefix({t}, {v})", target, node.values)
        return self._pred_line(cond, ctx)

    def visit_predicate_ends(
        self, node: PredEnds, ctx: WalkContext
    ) -> list[str]:
        self._builder.require_import('"strings"')
        target = self._pred_text_target(node, ctx)
        cond = self._any_of("strings.HasSuffix({t}, {v})", target, node.values)
        return self._pred_line(cond, ctx)

    def _count_expr(self, node) -> str:
        """Count expression — ``stdLen`` type-switches over Selection/string/[]string."""
        self._require("stdLen")
        target = self._pred_target(node)
        return f"stdLen({target})"

    def visit_predicate_count_eq(
        self, node: PredCountEq, ctx: WalkContext
    ) -> list[str]:
        return self._pred_line(f"{self._count_expr(node)} == {node.value}", ctx)

    def visit_predicate_count_gt(
        self, node: PredCountGt, ctx: WalkContext
    ) -> list[str]:
        return self._pred_line(f"{self._count_expr(node)} > {node.value}", ctx)

    def visit_predicate_count_lt(
        self, node: PredCountLt, ctx: WalkContext
    ) -> list[str]:
        return self._pred_line(f"{self._count_expr(node)} < {node.value}", ctx)

    def visit_predicate_count_ne(
        self, node: PredCountNe, ctx: WalkContext
    ) -> list[str]:
        return self._pred_line(f"{self._count_expr(node)} != {node.value}", ctx)

    def visit_predicate_count_ge(
        self, node: PredCountGe, ctx: WalkContext
    ) -> list[str]:
        return self._pred_line(f"{self._count_expr(node)} >= {node.value}", ctx)

    def visit_predicate_count_le(
        self, node: PredCountLe, ctx: WalkContext
    ) -> list[str]:
        return self._pred_line(f"{self._count_expr(node)} <= {node.value}", ctx)

    def visit_pred_count_range(
        self, node: PredCountRange, ctx: WalkContext
    ) -> list[str]:
        cnt = self._count_expr(node)
        return self._pred_line(
            f"{node.start} < {cnt} && {cnt} < {node.end}", ctx
        )

    def visit_predicate_re(self, node: PredRe, ctx: WalkContext) -> list[str]:
        self._require("stdReMatch")
        rx = py_re_to_go_raw(node.pattern)
        target = self._pred_text_target(node, ctx)
        cond = f"stdReMatch({rx}, {target})"
        return self._pred_line(cond, ctx)

    def visit_predicate_re_all(
        self, node: PredReAll, ctx: WalkContext
    ) -> list[str]:
        self._require("stdReAllMatch")
        rx = py_re_to_go_raw(node.pattern)
        target = self._pred_target(node)
        return self._pred_line(f"stdReAllMatch({rx}, {target})", ctx)

    def visit_predicate_re_any(
        self, node: PredReAny, ctx: WalkContext
    ) -> list[str]:
        self._require("stdReAnyMatch")
        rx = py_re_to_go_raw(node.pattern)
        target = self._pred_target(node)
        return self._pred_line(f"stdReAnyMatch({rx}, {target})", ctx)

    # === REST / FETCH ===

    def visit_method_rest(
        self, node: MethodRest, ctx: WalkContext
    ) -> list[str]:
        self._builder.require_import('"fmt"')
        if node.response_schema:
            self._builder.require_import('"encoding/json"')
        if node.response_path:
            self._builder.require_import('"github.com/tidwall/gjson"')
        spec = node.http_request
        if spec.body_kind == "form" and isinstance(spec.body, dict):
            self._builder.require_import('"net/url"')
        self._builder.require_import('"' + self._http.import_path + '"')
        struct = node.parent
        name = (
            to_pascal_case(struct.name)
            if isinstance(struct, StructBase)
            else "X"
        )
        rcv = _receiver(name)
        return rest.emit_method_rest(node, ctx, self._http, rcv)

    def visit_method_fetch(
        self, node: MethodFetch, ctx: WalkContext
    ) -> list[str]:
        # Free function Fetch(ctx, client, ...) (*Name, error) for HTML structs.
        self._builder.require_import('"context"')
        self._builder.require_import('"fmt"')
        self._builder.require_import('"io"')
        self._builder.require_import('"net/http"')
        self._builder.require_import('"strings"')
        spec = node.http_request
        if spec.body_kind == "form" and isinstance(spec.body, dict):
            self._builder.require_import('"net/url"')
        if node.response_path:
            self._builder.require_import('"github.com/tidwall/gjson"')
        return rest.emit_method_fetch(node, ctx, self._http)
