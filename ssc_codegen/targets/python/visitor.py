"""Python backend visitor (composition model).

Ports all dialect-agnostic Python codegen from ``PyHtmlBase`` to the new
``BaseWalker`` traversal core.  Handlers return ``list[str]`` (no generators,
no signal protocol).  DOM-specific spelling is delegated to a ``DomSpelling``
strategy set by the concrete dialect subclass.

REST/fetch method generation is delegated to ``rest.py``.
"""

from __future__ import annotations

import inspect
from typing import Any

from ssc_codegen.ast import (
    Module,
    Utilities,
    JsonDef,
    JsonDefField,
    TypeDef,
    TypeDefField,
    Struct,
    StructBase,
    StructRest,
    StartParse,
    Init,
    InitFieldCall,
    InitField,
    Field,
    PreValidate,
    CheckMethod,
    SplitDoc,
    Key,
    Value,
    TableConfig,
    TableMatchKey,
    TableRows,
    MethodRest,
    MethodFetch,
    ErrorResponse,
    ResultVariantDef,
    ResultAliasDef,
    MatcherListDef,
    CssSelect,
    CssSelectAll,
    CssRemove,
    XpathSelect,
    XpathSelectAll,
    XpathRemove,
    Attr,
    Text,
    Raw,
    Fmt,
    Repl,
    ReplMap,
    Lower,
    Upper,
    Split,
    Join,
    NormalizeSpace,
    Unescape,
    Trim,
    Ltrim,
    Rtrim,
    RmPrefix,
    RmSuffix,
    RmPrefixSuffix,
    Re,
    ReAll,
    ReSub,
    Index,
    Slice,
    Len,
    Unique,
    ToInt,
    ToFloat,
    ToBool,
    Jsonify,
    Nested,
    Self,
    Return,
    Node,
    Fallback,
    Filter,
    Assert,
    Match,
    LogicAnd,
    LogicNot,
    LogicOr,
    PredCss,
    PredXpath,
    PredHasAttr,
    PredAttrContains,
    PredAttrStarts,
    PredAttrEnds,
    PredAttrEq,
    PredAttrNe,
    PredAttrRe,
    PredTextContains,
    PredTextStarts,
    PredTextEnds,
    PredTextRe,
    PredContains,
    PredEq,
    PredNe,
    PredStarts,
    PredEnds,
    PredCountEq,
    PredCountGt,
    PredCountLt,
    PredCountNe,
    PredCountGe,
    PredCountLe,
    PredCountRange,
    PredRe,
    PredReAll,
    PredReAny,
    CodeEndHook,
    CodeStartHook,
    TypeInfo,
    VariableType as VT,
    StructType as ST,
)
from ssc_codegen.naming import to_pascal_case, to_snake_case
from ssc_codegen.traversal.utils import (
    jsonify_path_to_segments,
    module_has_rest,
    module_is_rest_only,
    module_uses_http,
)
from ssc_codegen.generation.builder import ModuleBuilder
from ssc_codegen.targets.python import rest
from ssc_codegen.targets.python.http_libs.aiohttp import AioHttpStrategy
from ssc_codegen.targets.python.http_libs.base import HttpLibStrategy
from ssc_codegen.targets.python.http_libs.httpx import HttpxStrategy
from ssc_codegen.targets.python.http_libs.requests import RequestsStrategy
from ssc_codegen.traversal.context import WalkContext
from ssc_codegen.traversal.walker import BaseWalker


class PythonVisitor(BaseWalker):
    """Shared Python codegen visitor.

    All ``visit_*`` handlers return ``list[str]``.  DOM-specific methods
    (selectors, extract, cast, DOM predicates) are overridden by concrete
    dialect subclasses that delegate to a ``DomSpelling`` strategy.
    """

    STD_MODULE_NAME: str = "ssc_std"

    # Std helpers that exist in the runtime module under the same name.
    # Under -R, import directly instead of inlining their definitions.
    # Library-specific helpers (std_select_first, std_xpath_remove, etc.)
    # are NOT here — they depend on the chosen HTML library and must stay
    # inlined in the parser file.
    _RUNTIME_HELPERS: set[str] = {
        "std_repl_map",
        "std_unescape_text",
        "std_assert",
        "std_re_search",
    }

    # --- type resolution spelling ---
    DEFAULT_TYPE: str = "Any"
    TYPES: dict[VT, str] = {
        VT.STRING: "str",
        VT.BOOL: "bool",
        VT.INT: "int",
        VT.FLOAT: "float",
        VT.NULL: "None",
        VT.JSON: "Any",
        VT.NESTED: "Any",
        VT.AUTO: "Any",
    }
    ARRAY_TYPE_FMT: str = "List[{}]"
    OPTIONAL_TYPE_FMT: str = "Optional[{}]"
    OPTIONAL_ON_OMITEMPTY: bool = False

    _HTTP_STRATEGIES: dict[str, type[HttpLibStrategy]] = {
        "httpx": HttpxStrategy,
        "aiohttp": AioHttpStrategy,
        "requests": RequestsStrategy,
    }

    @classmethod
    def http_strategy_for(cls, http_client: str | None) -> HttpLibStrategy:
        """Return the HTTP strategy that will be used for code generation.

        Single source of truth for "which strategy given user input":
        ``convert_all`` uses it for parser-file imports, ``main.py`` uses
        it to thread ``transport_import_line`` into ``register_runtime_file``
        so the runtime file's ``except <lib>.<Exc>`` clause is consistent
        with the parser file's transport imports.
        """
        if http_client and http_client in cls._HTTP_STRATEGIES:
            return cls._HTTP_STRATEGIES[http_client]()
        return HttpxStrategy()

    def __init__(
        self,
        var_name: str = "v",
        indent: str = " " * 4,
        dom_spelling_cls: type | None = None,
    ) -> None:
        self.var_name = var_name
        self.indent = indent
        self._dom_spelling_cls = dom_spelling_cls
        self._file_providers: dict[str, Any] = {}
        self._reset_state()

    # === STATE ===

    def _reset_state(self) -> None:
        self._builder = ModuleBuilder()
        self._http: HttpLibStrategy = HttpxStrategy()
        if self._dom_spelling_cls is not None:
            self._dom = self._dom_spelling_cls(self._builder)

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
        return self.convert_all(module_ast, inline_std=True, **meta)[""]

    def convert_all(self, module_ast: Module, **meta) -> dict[str, str]:
        self._reset_state()
        self._http = self.http_strategy_for(meta.get("http_client"))
        ctx = self._make_ctx(meta)
        self._walk_module(module_ast, ctx)
        lines = self._walk_module(module_ast, ctx)
        out: dict[str, str] = {"": "\n".join(lines)}
        if not ctx.meta.get("inline_std", True) and self._builder.has_std:
            name = ctx.meta.get("std_module_name", self.STD_MODULE_NAME)
            out[name] = self._render_std_module()
        for fname, provider in self._file_providers.items():
            out[fname] = provider(module_ast, ctx.meta)
        return out

    def _walk_module(self, module_ast: Module, ctx: WalkContext) -> list[str]:
        lines: list[str] = list(self.visit_module(module_ast, ctx))
        for node in module_ast.body:
            lines.extend(self.walk(node, ctx))
        return lines

    # === STD RENDERING (Python-specific) ===

    def _render_std_section(self, ctx: WalkContext) -> list[str]:
        if not self._builder.has_std:
            return []
        runtime = ctx.meta.get("runtime_module")
        if runtime:
            # Under -R: helpers that exist in the runtime module are
            # imported directly (same name on both sides — no aliasing).
            # Library-specific helpers (std_select_first, std_xpath_remove,
            # ...) are still inlined because they depend on the chosen
            # HTML library.
            imported: list[str] = []
            inlined_defs: list[tuple[list[str], str]] = []
            inlined_imports: list[str] = []
            for name, (imps, code) in self._builder.std_defs.items():
                if name in self._RUNTIME_HELPERS:
                    imported.append(name)
                else:
                    inlined_defs.append((imps, code))
                    inlined_imports.extend(imps)
            lines: list[str] = []
            if imported:
                lines.append(f"from .{runtime} import " + ", ".join(imported))
                lines.append("")
            if inlined_defs:
                lines.extend(inlined_imports)
                lines.append("")
                for _imps, code in inlined_defs:
                    lines.extend(inspect.cleandoc(code).splitlines())
                    lines.append("")
            return lines
        if ctx.meta.get("inline_std", True):
            body: list[str] = []
            for _imps, code in self._builder.std_defs.values():
                body.extend(inspect.cleandoc(code).splitlines())
                body.append("")
            return [*self._builder.std_imports, "", *body]
        module_name = ctx.meta.get("std_module_name", self.STD_MODULE_NAME)
        return [
            f"from {module_name} import {', '.join(self._builder.std_names)}"
        ]

    def _render_std_module(self) -> str:
        lines: list[str] = ["# autogenerated std runtime. DO NOT EDIT", ""]
        lines.extend(self._builder.std_imports)
        for _imps, code in self._builder.std_defs.values():
            lines.append("")
            lines.extend(inspect.cleandoc(code).splitlines())
        return "\n".join(lines)

    # === TYPE RESOLUTION ===

    def _resolve_type(self, type_info: TypeInfo | None) -> str:
        if type_info is None:
            return self.DEFAULT_TYPE
        if type_info.base == VT.NESTED and type_info.ref:
            t = f"{to_pascal_case(type_info.ref)}Type"
        elif type_info.base == VT.JSON and type_info.ref:
            t = f"{to_pascal_case(type_info.ref)}Json"
        elif type_info.base == VT.DOCUMENT:
            t = (
                self._dom.document_array_type
                if type_info.is_array
                else self._dom.document_type
            )
        else:
            t = self.TYPES.get(type_info.base, self.DEFAULT_TYPE)
        if type_info.is_array and type_info.base != VT.DOCUMENT:
            t = self.ARRAY_TYPE_FMT.format(t)
        if type_info.is_optional or (
            self.OPTIONAL_ON_OMITEMPTY and type_info.omitempty
        ):
            t = self.OPTIONAL_TYPE_FMT.format(t)
        return t

    def _resolve_start_parse_t_ret(self, struct: StructBase, name: str) -> str:
        match struct.type:
            case ST.ITEM | ST.DICT | ST.TABLE:
                return f"{name}Type"
            case ST.LIST:
                return self.ARRAY_TYPE_FMT.format(f"{name}Type")
            case ST.FLAT:
                return self.ARRAY_TYPE_FMT.format(self.TYPES[VT.STRING])
            case _:
                return self.TYPES[VT.STRING]

    # === MODULE ===

    def visit_module(self, node: Module, ctx: WalkContext) -> list[str]:
        lines: list[str] = ["# autogenerated by ssc-gen. DO NOT EDIT"]
        if node.doc:
            lines.extend(['"""', node.doc, '"""'])
        has_rest = module_has_rest(node)
        is_rest_only = module_is_rest_only(node)
        uses_http = module_uses_http(node)
        runtime = ctx.meta.get("runtime_module")
        if not is_rest_only:
            for line in self._dom.parser_imports:
                self._builder.require_import(line)
        self._builder.require_import(
            "from typing import Any, Dict, List, Optional, TypedDict, Union"
        )
        self._builder.require_import(
            "from typing_extensions import NotRequired"
        )
        self._builder.require_import("import re")
        self._builder.require_import("import json")
        if has_rest:
            # Err subclasses are declared in the parser file regardless of
            # whether runtime separation is enabled — they need @dataclass and
            # Literal[<status>] annotations always.
            self._builder.require_import("from dataclasses import dataclass")
            self._builder.require_import("from typing import Literal")
            # cast() wraps ssc_rest_call return value to narrow
            # Union[Ok[_T], Err] (runtime return type) to the parser's
            # specific Result alias (Union[Ok[_T], Err400, ...]). Without
            # cast, mypy flags the broader Err base as incompatible with
            # the parser's declared union of specific subclasses.
            self._builder.require_import("from typing import cast")
            if not runtime:
                # Runtime-internal helpers (Ok/Err/ErrMatcher factories) are
                # inlined into the parser file only without -R; their imports
                # are runtime-only otherwise.
                self._builder.require_import("from dataclasses import field")
                self._builder.require_import(
                    "from typing import Callable, Generic, Mapping, TypeVar"
                )
        if uses_http:
            # Any fetch/rest method emits signatures like
            # ``client: httpx.Client``; the transport import is needed even
            # when the module is HTML-only with a single fetch shortcut and
            # even under -R (signature lives in the parser file).
            self._builder.require_import(self._http.import_line)
        return lines

    def visit_utilities(self, node: Utilities, ctx: WalkContext) -> list[str]:
        lines: list[str] = []
        runtime = ctx.meta.get("runtime_module")
        if runtime:
            # Even under -R, the parser file still declares TypedDict schemas,
            # @dataclass Err subclasses (Literal[<status>]), uses httpx type
            # hints, lxml types, json/re for jsonify/regex ops, etc.
            # All non-runtime imports must be emitted into the parser file.
            lines.extend(self._builder.imports)
            mod = node.parent
            if isinstance(mod, Module):
                need_fallback = any(
                    "FALLBACK_HTML_STR" in line
                    for line in self._dom.extra_utilities
                )
                names = rest.runtime_export_names(
                    mod, need_fallback=need_fallback
                )
            else:
                names = []
            lines.append(f"from .{runtime} import " + ", ".join(names))
            lines.append("")
            lines.extend(self._render_std_section(ctx))
            return lines
        lines.extend(self._builder.imports)
        lines.append("")
        mod = node.parent
        is_rest_only = isinstance(mod, Module) and module_is_rest_only(mod)
        if not is_rest_only:
            lines.extend(
                [
                    "class UnmatchedTableRow:",
                    "    pass",
                    "",
                    "UNMATCHED_TABLE_ROW = UnmatchedTableRow()",
                    "",
                ]
            )
            for line in self._dom.extra_utilities:
                lines.append(line)
        if isinstance(mod, Module) and module_has_rest(mod):
            lines.extend(self._http.rest_runtime_lines())
        lines.extend(self._render_std_section(ctx))
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
        lines = [f'{name}Json = TypedDict("{name}Json", {{']
        lines.extend(self.walk_children(node, ctx))
        lines.append("})")
        return lines

    def visit_jsondef_field(
        self, node: JsonDefField, ctx: WalkContext
    ) -> list[str]:
        if node.type_info and node.type_info.skip:
            return []
        name = node.name
        t = self._resolve_type(node.type_info)
        if node.type_info and node.type_info.omitempty:
            t = f"NotRequired[{t}]"
        return [f"{name!r}: {t},"]

    def visit_typedef(self, node: TypeDef, ctx: WalkContext) -> list[str]:
        name = to_pascal_case(node.name)
        match node.struct_type:
            case ST.REST:
                return []
            case ST.DICT:
                return self.walk_children(node, ctx)
            case ST.FLAT:
                return [f"{name}Type = List[str]"]
            case ST.ITEM | ST.LIST | ST.TABLE:
                lines = [f'{name}Type = TypedDict("{name}Type", {{']
                lines.extend(self.walk_children(node, ctx))
                lines.append("})")
                return lines
            case _:
                raise Exception

    def visit_typedef_field(
        self, node: TypeDefField, ctx: WalkContext
    ) -> list[str]:
        if node.typedef.struct_type == ST.FLAT:
            return []
        name = to_snake_case(node.name)
        t = self._resolve_type(node.type_info)
        if node.typedef.struct_type == ST.DICT:
            if name == "value":
                typedef_name = to_pascal_case(node.typedef.name)
                return [f"{typedef_name}Type = Dict[str, {t}]"]
            return []
        return [f"{ctx.indent}{name!r}: {t},"]

    # === STRUCT ===

    def visit_struct(self, node: Struct, ctx: WalkContext) -> list[str]:
        name = to_pascal_case(node.name)
        lines = [f"class {name}:"]
        if node.doc:
            i = ctx.deeper().indent
            lines.append(f'{i}"""')
            for line in node.doc.splitlines():
                lines.append(i + line)
            lines.append(f'{i}"""')
        lines.extend(self.walk_children(node, ctx))
        return lines

    def visit_struct_rest(
        self, node: StructRest, ctx: WalkContext
    ) -> list[str]:
        name = to_pascal_case(node.name)
        lines = [f"class {name}:"]
        if node.doc:
            i = ctx.deeper().indent
            lines.append(f'{i}"""')
            for line in node.doc.splitlines():
                lines.append(i + line)
            lines.append(f'{i}"""')
        lines.extend(self.walk_children(node, ctx))
        return lines

    def visit_result_variant_def(
        self, node: ResultVariantDef, ctx: WalkContext
    ) -> list[str]:
        return rest.emit_result_variant_def(node)

    def visit_result_alias_def(
        self, node: ResultAliasDef, ctx: WalkContext
    ) -> list[str]:
        return rest.emit_result_alias_def(node)

    def visit_matcher_list_def(
        self, node: MatcherListDef, ctx: WalkContext
    ) -> list[str]:
        return rest.emit_matcher_list_def(node)

    def visit_init(self, node: Init, ctx: WalkContext) -> list[str]:
        i, i2, i3 = (
            ctx.indent,
            ctx.deeper().indent,
            ctx.deeper().deeper().indent,
        )
        lines = [
            f"{i}def __init__(self, document: {self._dom.init_arg_type}):",
            f"{i2}if isinstance(document, str):",
            f"{i3}self._doc = {self._dom.init_from_str_expr}",
            f"{i2}else:",
            f"{i3}self._doc = document",
        ]
        lines.extend(self.walk_children(node, ctx))
        return lines

    def visit_init_field_call(
        self, node: InitFieldCall, ctx: WalkContext
    ) -> list[str]:
        name = to_snake_case(node.name)
        return [f"{ctx.indent}self._{name} = self._init_{name}(self._doc)"]

    def visit_init_field(self, node: InitField, ctx: WalkContext) -> list[str]:
        name = to_snake_case(node.name)
        t_arg = self._resolve_type(node.accept_type_info)
        t_ret = self._resolve_type(node.ret_type_info)
        lines = [f"{ctx.indent}def _init_{name}(self, v: {t_arg}) -> {t_ret}:"]
        lines.extend(self.walk_children(node, ctx))
        return lines

    def visit_field(self, node: Field, ctx: WalkContext) -> list[str]:
        name = to_snake_case(node.name)
        t_arg = self._resolve_type(node.accept_type_info)
        t_ret = self._resolve_type(node.ret_type_info)
        if node.struct.type == ST.TABLE:
            t_ret = f"Union[{t_ret}, UnmatchedTableRow]"
        lines = [f"{ctx.indent}def _parse_{name}(self, v: {t_arg}) -> {t_ret}:"]
        lines.extend(self.walk_children(node, ctx))
        return lines

    def visit_key(self, node: Key, ctx: WalkContext) -> list[str]:
        t_arg = self._resolve_type(node.accept_type_info)
        t_ret = self._resolve_type(node.ret_type_info)
        lines = [f"{ctx.indent}def _parse_key(self, v: {t_arg}) -> {t_ret}:"]
        lines.extend(self.walk_children(node, ctx))
        return lines

    def visit_value(self, node: Value, ctx: WalkContext) -> list[str]:
        t_arg = self._resolve_type(node.accept_type_info)
        t_ret = self._resolve_type(node.ret_type_info)
        lines = [f"{ctx.indent}def _parse_value(self, v: {t_arg}) -> {t_ret}:"]
        lines.extend(self.walk_children(node, ctx))
        return lines

    def visit_table_config(
        self, node: TableConfig, ctx: WalkContext
    ) -> list[str]:
        t_arg = self._resolve_type(node.accept_type_info)
        t_ret = self._resolve_type(node.ret_type_info)
        lines = [f"{ctx.indent}def _table_config(self, v: {t_arg}) -> {t_ret}:"]
        lines.extend(self.walk_children(node, ctx))
        return lines

    def visit_table_match_key(
        self, node: TableMatchKey, ctx: WalkContext
    ) -> list[str]:
        t_arg = self._resolve_type(node.accept_type_info)
        t_ret = self._resolve_type(node.ret_type_info)
        lines = [
            f"{ctx.indent}def _table_match_key(self, v: {t_arg}) -> {t_ret}:"
        ]
        lines.extend(self.walk_children(node, ctx))
        return lines

    def visit_table_rows(self, node: TableRows, ctx: WalkContext) -> list[str]:
        t_arg = self._resolve_type(node.accept_type_info)
        t_ret = self._resolve_type(node.ret_type_info)
        lines = [f"{ctx.indent}def _table_rows(self, v: {t_arg}) -> {t_ret}:"]
        lines.extend(self.walk_children(node, ctx))
        return lines

    def visit_pre_validate(
        self, node: PreValidate, ctx: WalkContext
    ) -> list[str]:
        t_arg = self._resolve_type(node.accept_type_info)
        t_ret = self._resolve_type(node.ret_type_info)
        lines = [f"{ctx.indent}def _pre_validate(self, v: {t_arg}) -> {t_ret}:"]
        lines.extend(self.walk_children(node, ctx))
        return lines

    def visit_check_method(
        self, node: CheckMethod, ctx: WalkContext
    ) -> list[str]:
        name = to_snake_case(node.name)
        t_ret = self._resolve_type(node.ret_type_info)
        lines = [
            f"{ctx.indent}def {name}(self) -> {t_ret}:",
            f"{ctx.indent * 2}{ctx.var_name} = self._doc",
        ]
        lines.extend(self.walk_children(node, ctx))
        return lines

    def visit_split_doc(self, node: SplitDoc, ctx: WalkContext) -> list[str]:
        t_arg = self._resolve_type(node.accept_type_info)
        t_ret = self._resolve_type(node.ret_type_info)
        lines = [f"{ctx.indent}def _split_doc(self, v: {t_arg}) -> {t_ret}:"]
        lines.extend(self.walk_children(node, ctx))
        return lines

    def visit_start_parse(
        self, node: StartParse, ctx: WalkContext
    ) -> list[str]:
        name = to_pascal_case(node.struct.name)
        t = self._resolve_start_parse_t_ret(node.struct, name)
        i2 = ctx.deeper().indent
        i3 = ctx.deeper().deeper().indent
        i4 = ctx.deeper().deeper().deeper().indent
        lines: list[str] = [f"{ctx.indent}def parse(self) -> {t}:"]
        if node.use_pre_validate:
            lines.append(f"{i2}self._pre_validate(self._doc)")
        match node.struct.type:
            case ST.ITEM:
                lines.append(f"{i2}return {{")
                for field in node.fields:
                    fn = to_snake_case(field.name)
                    lines.append(f"{i3}{fn!r}: self._parse_{fn}(self._doc),")
                lines.append(f"{i3}}}")
            case ST.LIST:
                lines.append(f"{i2}return [{{")
                for field in node.fields:
                    fn = to_snake_case(field.name)
                    lines.append(f"{i2}{fn!r}: self._parse_{fn}(i),")
                lines.append(f"{i3}}} for i in self._split_doc(self._doc)]")
            case ST.DICT:
                lines.append(f"{i2}return {{")
                lines.append(
                    f"{i3}self._parse_key(i): self._parse_value(i) for i in self._split_doc(self._doc)"
                )
                lines.append(f"{i2}}}")
            case ST.FLAT:
                lines.append(f"{i2}_result: List[str] = []")
                for field in node.fields:
                    fn = to_snake_case(field.name)
                    if field.ret_type_info.is_array:
                        lines.append(
                            f"{i2}_result.extend(self._parse_{fn}(self._doc))"
                        )
                    else:
                        lines.append(
                            f"{i2}_result.append(self._parse_{fn}(self._doc))"
                        )
                if node.struct.keep_order:
                    lines.append(f"{i2}return list(dict.fromkeys(_result))")
                lines.append(f"{i2}return list(set(_result))")
            case ST.TABLE:
                lines.append(f"{i2}_result: {name}Type = {{}}")
                lines.append(f"{i2}_table = self._table_config(self._doc)")
                lines.append(f"{i2}for _row in self._table_rows(_table):")
                for field in node.fields:
                    fn = to_snake_case(field.name)
                    lines.append(f"{i3}_{fn} = self._parse_{fn}(_row)")
                    lines.append(
                        f"{i3}if _{fn} != UNMATCHED_TABLE_ROW and {fn!r} not in _result:"
                    )
                    lines.append(f"{i4}_result[{fn!r}] = _{fn}")
                    lines.append(f"{i4}continue")
                lines.append(f"{i2}return _result")
        return lines

    # === REST / FETCH (delegate to rest.py) ===

    def visit_method_fetch(
        self, node: MethodFetch, ctx: WalkContext
    ) -> list[str]:
        return rest.emit_method_fetch(node, ctx, self._http)

    def visit_method_rest(
        self, node: MethodRest, ctx: WalkContext
    ) -> list[str]:
        return rest.emit_method_rest(node, ctx, self._http)

    # === DOM (delegate to spelling) ===

    def visit_css_select(self, node: CssSelect, ctx: WalkContext) -> list[str]:
        return self._dom.css_select(ctx, node)

    def visit_css_select_all(
        self, node: CssSelectAll, ctx: WalkContext
    ) -> list[str]:
        return self._dom.css_select_all(ctx, node)

    def visit_css_remove(self, node: CssRemove, ctx: WalkContext) -> list[str]:
        return self._dom.css_remove(ctx, node)

    def visit_xpath_select(
        self, node: XpathSelect, ctx: WalkContext
    ) -> list[str]:
        return self._dom.xpath_select(ctx, node)

    def visit_xpath_select_all(
        self, node: XpathSelectAll, ctx: WalkContext
    ) -> list[str]:
        return self._dom.xpath_select_all(ctx, node)

    def visit_xpath_remove(
        self, node: XpathRemove, ctx: WalkContext
    ) -> list[str]:
        return self._dom.xpath_remove(ctx, node)

    def visit_text(self, node: Text, ctx: WalkContext) -> list[str]:
        return self._dom.text(ctx, node)

    def visit_raw(self, node: Raw, ctx: WalkContext) -> list[str]:
        return self._dom.raw(ctx, node)

    def visit_attr(self, node: Attr, ctx: WalkContext) -> list[str]:
        return self._dom.attr(ctx, node)

    def visit_to_bool(self, node: ToBool, ctx: WalkContext) -> list[str]:
        return self._dom.to_bool(ctx, node)

    # === DOM PREDICATES (inline predicate formatting, no _pred_line) ===

    def visit_predicate_css(self, node: PredCss, ctx: WalkContext) -> list[str]:
        prefix = "" if ctx.index == 0 else "and "
        return [f"{ctx.indent}{prefix}{self._dom.pred_css(node)}"]

    def visit_predicate_xpath(
        self, node: PredXpath, ctx: WalkContext
    ) -> list[str]:
        prefix = "" if ctx.index == 0 else "and "
        return [f"{ctx.indent}{prefix}{self._dom.pred_xpath(node)}"]

    def visit_predicate_has_attr(
        self, node: PredHasAttr, ctx: WalkContext
    ) -> list[str]:
        prefix = "" if ctx.index == 0 else "and "
        return [f"{ctx.indent}{prefix}{self._dom.pred_has_attr(node)}"]

    def visit_predicate_attr_contains(
        self, node: PredAttrContains, ctx: WalkContext
    ) -> list[str]:
        prefix = "" if ctx.index == 0 else "and "
        return [f"{ctx.indent}{prefix}{self._dom.pred_attr_contains(node)}"]

    def visit_predicate_attr_starts(
        self, node: PredAttrStarts, ctx: WalkContext
    ) -> list[str]:
        prefix = "" if ctx.index == 0 else "and "
        return [f"{ctx.indent}{prefix}{self._dom.pred_attr_starts(node)}"]

    def visit_predicate_attr_ends(
        self, node: PredAttrEnds, ctx: WalkContext
    ) -> list[str]:
        prefix = "" if ctx.index == 0 else "and "
        return [f"{ctx.indent}{prefix}{self._dom.pred_attr_ends(node)}"]

    def visit_predicate_attr_eq(
        self, node: PredAttrEq, ctx: WalkContext
    ) -> list[str]:
        prefix = "" if ctx.index == 0 else "and "
        return [f"{ctx.indent}{prefix}{self._dom.pred_attr_eq(node)}"]

    def visit_predicate_attr_ne(
        self, node: PredAttrNe, ctx: WalkContext
    ) -> list[str]:
        prefix = "" if ctx.index == 0 else "and "
        return [f"{ctx.indent}{prefix}{self._dom.pred_attr_ne(node)}"]

    def visit_predicate_attr_re(
        self, node: PredAttrRe, ctx: WalkContext
    ) -> list[str]:
        prefix = "" if ctx.index == 0 else "and "
        return [f"{ctx.indent}{prefix}{self._dom.pred_attr_re(node)}"]

    def visit_predicate_text_contains(
        self, node: PredTextContains, ctx: WalkContext
    ) -> list[str]:
        prefix = "" if ctx.index == 0 else "and "
        return [f"{ctx.indent}{prefix}{self._dom.pred_text_contains(node)}"]

    def visit_predicate_text_starts(
        self, node: PredTextStarts, ctx: WalkContext
    ) -> list[str]:
        prefix = "" if ctx.index == 0 else "and "
        return [f"{ctx.indent}{prefix}{self._dom.pred_text_starts(node)}"]

    def visit_predicate_text_ends(
        self, node: PredTextEnds, ctx: WalkContext
    ) -> list[str]:
        prefix = "" if ctx.index == 0 else "and "
        return [f"{ctx.indent}{prefix}{self._dom.pred_text_ends(node)}"]

    def visit_predicate_text_re(
        self, node: PredTextRe, ctx: WalkContext
    ) -> list[str]:
        prefix = "" if ctx.index == 0 else "and "
        return [f"{ctx.indent}{prefix}{self._dom.pred_text_re(node)}"]

    # === STRING ===

    def visit_trim(self, node: Trim, ctx: WalkContext) -> list[str]:
        value = "" if node.substr == "" else repr(node.substr)
        if node.is_array:
            return [
                f"{ctx.indent}{ctx.nxt} = [i.strip({value}) for i in {ctx.prv}]"
            ]
        return [f"{ctx.indent}{ctx.nxt} = {ctx.prv}.strip({value})"]

    def visit_l_trim(self, node: Ltrim, ctx: WalkContext) -> list[str]:
        value = "" if node.substr == "" else repr(node.substr)
        if node.is_array:
            return [
                f"{ctx.indent}{ctx.nxt} = [i.lstrip({value}) for i in {ctx.prv}]"
            ]
        return [f"{ctx.indent}{ctx.nxt} = {ctx.prv}.lstrip({value})"]

    def visit_r_trim(self, node: Rtrim, ctx: WalkContext) -> list[str]:
        value = "" if node.substr == "" else repr(node.substr)
        if node.is_array:
            return [
                f"{ctx.indent}{ctx.nxt} = [i.rstrip({value}) for i in {ctx.prv}]"
            ]
        return [f"{ctx.indent}{ctx.nxt} = {ctx.prv}.rstrip({value})"]

    def visit_rm_prefix(self, node: RmPrefix, ctx: WalkContext) -> list[str]:
        value = repr(node.substr)
        if node.is_array:
            return [
                f"{ctx.indent}{ctx.nxt} = [i.removeprefix({value}) for i in {ctx.prv}]"
            ]
        return [f"{ctx.indent}{ctx.nxt} = {ctx.prv}.removeprefix({value})"]

    def visit_rm_suffix(self, node: RmSuffix, ctx: WalkContext) -> list[str]:
        value = repr(node.substr)
        if node.is_array:
            return [
                f"{ctx.indent}{ctx.nxt} = [i.removesuffix({value}) for i in {ctx.prv}]"
            ]
        return [f"{ctx.indent}{ctx.nxt} = {ctx.prv}.removesuffix({value})"]

    def visit_rm_prefix_suffix(
        self, node: RmPrefixSuffix, ctx: WalkContext
    ) -> list[str]:
        value = repr(node.substr)
        if node.is_array:
            return [
                f"{ctx.indent}{ctx.nxt} = [i.removeprefix({value}).removesuffix({value}) for i in {ctx.prv}]"
            ]
        return [
            f"{ctx.indent}{ctx.nxt} = {ctx.prv}.removeprefix({value}).removesuffix({value})"
        ]

    def visit_format(self, node: Fmt, ctx: WalkContext) -> list[str]:
        tmpl = repr(node.template.replace("{{}}", "{}", 1))
        if node.is_array:
            return [
                f"{ctx.indent}{ctx.nxt} = [{tmpl}.format(i) for i in {ctx.prv}]"
            ]
        return [f"{ctx.indent}{ctx.nxt} = {tmpl}.format({ctx.prv})"]

    def visit_repl(self, node: Repl, ctx: WalkContext) -> list[str]:
        old = repr(node.old)
        new = repr(node.new)
        if node.is_array:
            return [
                f"{ctx.indent}{ctx.nxt} = [i.replace({old}, {new}) for i in {ctx.prv}]"
            ]
        return [f"{ctx.indent}{ctx.nxt} = {ctx.prv}.replace({old}, {new})"]

    def visit_repl_map(self, node: ReplMap, ctx: WalkContext) -> list[str]:
        repl_dict = repr(node.replacements)
        self._builder.require_std(
            "std_repl_map",
            code="""
                def std_repl_map(s, replacements):
                    for old, new in replacements.items():
                        s = s.replace(old, new)
                    return s
            """,
        )
        if node.is_array:
            return [
                f"{ctx.indent}{ctx.nxt} = [std_repl_map(i, {repl_dict}) for i in {ctx.prv}]"
            ]
        return [f"{ctx.indent}{ctx.nxt} = std_repl_map({ctx.prv}, {repl_dict})"]

    def visit_lower(self, node: Lower, ctx: WalkContext) -> list[str]:
        if node.is_array:
            return [f"{ctx.indent}{ctx.nxt} = [i.lower() for i in {ctx.prv}]"]
        return [f"{ctx.indent}{ctx.nxt} = {ctx.prv}.lower()"]

    def visit_upper(self, node: Upper, ctx: WalkContext) -> list[str]:
        if node.is_array:
            return [f"{ctx.indent}{ctx.nxt} = [i.upper() for i in {ctx.prv}]"]
        return [f"{ctx.indent}{ctx.nxt} = {ctx.prv}.upper()"]

    def visit_split(self, node: Split, ctx: WalkContext) -> list[str]:
        sep = repr(node.sep)
        return [f"{ctx.indent}{ctx.nxt} = {ctx.prv}.split({sep})"]

    def visit_join(self, node: Join, ctx: WalkContext) -> list[str]:
        sep = repr(node.sep)
        return [f"{ctx.indent}{ctx.nxt} = {sep}.join({ctx.prv})"]

    def visit_norm_space(
        self, node: NormalizeSpace, ctx: WalkContext
    ) -> list[str]:
        if node.is_array:
            return [
                f"{ctx.indent}{ctx.nxt} = [' '.join(i.split()) if i else '' for i in {ctx.prv}]"
            ]
        return [
            f"{ctx.indent}{ctx.nxt} = ' '.join({ctx.prv}.split()) if {ctx.prv} else ''"
        ]

    def visit_unescape(self, node: Unescape, ctx: WalkContext) -> list[str]:
        self._builder.require_std(
            "std_unescape_text",
            imports=["import re", "from html import unescape"],
            code="""
                _RE_HEX_ENTITY = re.compile(r"&#x([0-9a-fA-F]+);")
                _RE_UNICODE_ENTITY = re.compile(r"\\\\u([0-9a-fA-F]{4})")
                _RE_BYTES_ENTITY = re.compile(r"\\\\x([0-9a-fA-F]{2})")
                _RE_CHARS_MAP = {
                    "\\\\b": "\\b", "\\\\f": "\\f",
                    "\\\\n": "\\n", "\\\\r": "\\r", "\\\\t": "\\t",
                }

                def std_unescape_text(text):
                    s = unescape(text)
                    s = _RE_HEX_ENTITY.sub(lambda m: chr(int(m.group(1), 16)), s)
                    s = _RE_UNICODE_ENTITY.sub(lambda m: chr(int(m.group(1), 16)), s)
                    s = _RE_BYTES_ENTITY.sub(lambda m: chr(int(m.group(1), 16)), s)
                    for ch, r in _RE_CHARS_MAP.items():
                        s = s.replace(ch, r)
                    return s
            """,
        )
        if node.is_array:
            return [
                f"{ctx.indent}{ctx.nxt} = [std_unescape_text(i) for i in {ctx.prv}]"
            ]
        return [f"{ctx.indent}{ctx.nxt} = std_unescape_text({ctx.prv})"]

    # === REGEX ===

    def visit_re(self, node: Re, ctx: WalkContext) -> list[str]:
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
        self._builder.require_std(
            "std_re_search",
            code="""
                class SscRegexError(Exception):
                    pass

                def std_re_search(pattern, value, msg=''):
                    m = re.search(pattern, value)
                    if m is None:
                        raise SscRegexError(msg or 'ssc-gen re-match failed')
                    return m[1]
            """,
        )
        pattern = repr(node.pattern)
        if node.is_array:
            return [
                f"{ctx.indent}{ctx.nxt} = [std_re_search({pattern}, i, {msg!r}) for i in {ctx.prv}]"
            ]
        return [
            f"{ctx.indent}{ctx.nxt} = std_re_search({pattern}, {ctx.prv}, {msg!r})"
        ]

    def visit_re_all(self, node: ReAll, ctx: WalkContext) -> list[str]:
        pattern = repr(node.pattern)
        return [f"{ctx.indent}{ctx.nxt} = re.findall({pattern}, {ctx.prv})"]

    def visit_re_sub(self, node: ReSub, ctx: WalkContext) -> list[str]:
        pattern = repr(node.pattern)
        repl = repr(node.repl)
        if node.is_array:
            return [
                f"{ctx.indent}{ctx.nxt} = [re.sub({pattern}, {repl}, i) for i in {ctx.prv}]"
            ]
        return [f"{ctx.indent}{ctx.nxt} = re.sub({pattern}, {repl}, {ctx.prv})"]

    # === ARRAY ===

    def visit_index(self, node: Index, ctx: WalkContext) -> list[str]:
        # Intentional behavior: if the index doesn't match, the code crashes immediately.
        return [
            f"{ctx.indent}{ctx.nxt} = {ctx.prv}[{node.i}]  # type: ignore[index]"
        ]

    def visit_slice(self, node: Slice, ctx: WalkContext) -> list[str]:
        return [f"{ctx.indent}{ctx.nxt} = {ctx.prv}[{node.start}:{node.end}]"]

    def visit_len(self, node: Len, ctx: WalkContext) -> list[str]:
        return [f"{ctx.indent}{ctx.nxt} = len({ctx.prv})"]

    def visit_unique(self, node: Unique, ctx: WalkContext) -> list[str]:
        if node.keep_order:
            return [f"{ctx.indent}{ctx.nxt} = list(dict.fromkeys({ctx.prv}))"]
        return [f"{ctx.indent}{ctx.nxt} = list(set({ctx.prv}))"]

    # === CASTS ===

    def visit_to_int(self, node: ToInt, ctx: WalkContext) -> list[str]:
        if node.is_array:
            return [f"{ctx.indent}{ctx.nxt} = [int(i) for i in {ctx.prv}]"]
        return [f"{ctx.indent}{ctx.nxt} = int({ctx.prv})"]

    def visit_to_float(self, node: ToFloat, ctx: WalkContext) -> list[str]:
        if node.is_array:
            return [f"{ctx.indent}{ctx.nxt} = [float(i) for i in {ctx.prv}]"]
        return [f"{ctx.indent}{ctx.nxt} = float({ctx.prv})"]

    def visit_jsonify(self, node: Jsonify, ctx: WalkContext) -> list[str]:
        if node.path:
            parts = jsonify_path_to_segments(node.path)
            path = ""
            for part in parts:
                if part.isdigit():
                    path += f"[{part}]"
                else:
                    path += f"[{part}]"
            return [f"{ctx.indent}{ctx.nxt} = json.loads({ctx.prv}){path}"]
        return [f"{ctx.indent}{ctx.nxt} = json.loads({ctx.prv})"]

    def visit_nested(self, node: Nested, ctx: WalkContext) -> list[str]:
        struct_name = to_pascal_case(node.struct_name)
        return [f"{ctx.indent}{ctx.nxt} = {struct_name}({ctx.prv}).parse()"]

    def visit_self(self, node: Self, ctx: WalkContext) -> list[str]:
        name = to_snake_case(node.name)
        return [f"{ctx.indent}{ctx.nxt} = self._{name}"]

    # === CONTROL ===

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
        lines = [f"{ctx.indent}try:"]
        lines.extend(self.walk_pipeline(node.body, inner_ctx))
        lines.extend(
            [
                f"{inner_indent}return {last_var}",
                f"{ctx.indent}except Exception:",
                f"{inner_indent}return {node.value!r}",
            ]
        )
        return lines

    def visit_filter(self, node: Filter, ctx: WalkContext) -> list[str]:
        lines = [f"{ctx.indent}{ctx.nxt} = [i for i in {ctx.prv} if "]
        lines.extend(self.walk_children(node, ctx))
        lines.append(f"{ctx.indent}]")
        return lines

    def _resolve_location(self, node: Node) -> str:
        """Walk parent chain to find ``{StructName}.{field_or_marker}``.

        Returns a language-agnostic location string used in default error
        messages (Assert / Re). Reads raw KDL names (snake_case for fields,
        pascal-case for struct class). For ``@pre-validate`` ancestors the
        marker ``@pre-validate`` is used verbatim — matches the DSL syntax
        and is stable across target languages.
        """
        from ssc_codegen.naming import to_pascal_case

        struct_name = ""
        field_part = ""
        current = node.parent
        # First pass: find immediate field-like ancestor (Field/Key/Value
        # or PreValidate). Stop at first StructBase for struct name.
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

    def _resolve_source_file(self, node: Node) -> str:
        """Walk parent chain to Module; return ``Module.source_file`` basename."""
        current: Node | None = node
        while current is not None:
            if isinstance(current, Module):
                return current.source_file
            current = current.parent
        return ""

    def _resolve_assert_location(self, node: Assert) -> str:
        """Back-compat shim; delegates to :meth:`_resolve_location`."""
        return self._resolve_location(node)

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
        self._builder.require_std(
            "std_assert",
            code="""
                class SscAssertionError(Exception):
                    pass

                def std_assert(cond, msg=''):
                    if not cond:
                        raise SscAssertionError(msg or 'ssc-gen assertion failed')
            """,
        )
        i1 = ctx.indent
        i2 = ctx.deeper().indent
        lines = [
            f"{i1}i = {ctx.prv}",
            f"{i1}std_assert(",
            f"{i2}(",
        ]
        lines.extend(self.walk_children(node, ctx))
        lines.extend(
            [
                f"{i2}),",
                f"{i2}{msg!r},",
                f"{i1})",
                f"{i1}{ctx.nxt} = {ctx.prv}",
            ]
        )
        return lines

    def visit_match(self, node: Match, ctx: WalkContext) -> list[str]:
        lines = [
            f"{ctx.indent}i = self._table_match_key({ctx.prv})",
            f"{ctx.indent}if not (",
        ]
        lines.extend(self.walk_children(node, ctx))
        lines.extend(
            [
                f"{ctx.indent}):",
                f"{ctx.deeper().indent}return UNMATCHED_TABLE_ROW",
                f"{ctx.indent}{ctx.nxt} = self._parse_value({ctx.prv})",
            ]
        )
        return lines

    # === LOGIC ===

    def visit_logic_and(self, node: LogicAnd, ctx: WalkContext) -> list[str]:
        lines: list[str] = []
        if ctx.index == 0:
            lines.append(f"{ctx.indent}(")
        else:
            lines.append(f"{ctx.indent}and (")
        lines.extend(self.walk_children(node, ctx))
        lines.append(f"{ctx.indent})")
        return lines

    def visit_logic_or(self, node: LogicOr, ctx: WalkContext) -> list[str]:
        lines: list[str] = []
        if ctx.index == 0:
            lines.append(f"{ctx.indent}(")
        else:
            lines.append(f"{ctx.indent}or (")
        lines.extend(self.walk_children(node, ctx))
        lines.append(f"{ctx.indent})")
        return lines

    def visit_logic_not(self, node: LogicNot, ctx: WalkContext) -> list[str]:
        lines: list[str] = []
        if ctx.index == 0:
            lines.append(f"{ctx.indent}not (")
        else:
            lines.append(f"{ctx.indent}and not (")
        lines.extend(self.walk_children(node, ctx))
        lines.append(f"{ctx.indent})")
        return lines

    # === STRING-LEVEL / COUNT / REGEX PREDICATES (inline formatting) ===

    def visit_predicate_contains(
        self, node: PredContains, ctx: WalkContext
    ) -> list[str]:
        vals = repr(node.values)
        prefix = "" if ctx.index == 0 else "and "
        return [f"{ctx.indent}{prefix}any(v in i for v in {vals})"]

    def visit_predicate_eq(self, node: PredEq, ctx: WalkContext) -> list[str]:
        values = node.values
        if len(values) == 1 and isinstance(values[0], int):
            cond = f"len(i) == {values[0]}"
        else:
            cond = f"any(i == v for v in {values!r})"
        prefix = "" if ctx.index == 0 else "and "
        return [f"{ctx.indent}{prefix}{cond}"]

    def visit_predicate_ne(self, node: PredNe, ctx: WalkContext) -> list[str]:
        values = node.values
        if len(values) == 1 and isinstance(values[0], int):
            cond = f"len(i) != {values[0]}"
        else:
            cond = f"all(i != v for v in {values!r})"
        prefix = "" if ctx.index == 0 else "and "
        return [f"{ctx.indent}{prefix}{cond}"]

    def visit_predicate_starts(
        self, node: PredStarts, ctx: WalkContext
    ) -> list[str]:
        vals = repr(node.values)
        prefix = "" if ctx.index == 0 else "and "
        return [f"{ctx.indent}{prefix}i.startswith({vals})"]

    def visit_predicate_ends(
        self, node: PredEnds, ctx: WalkContext
    ) -> list[str]:
        vals = repr(node.values)
        prefix = "" if ctx.index == 0 else "and "
        return [f"{ctx.indent}{prefix}i.endswith({vals})"]

    def visit_pred_count_range(
        self, node: PredCountRange, ctx: WalkContext
    ) -> list[str]:
        prefix = "" if ctx.index == 0 else "and "
        return [f"{ctx.indent}{prefix}{node.start} < len(i) < {node.end}"]

    def visit_predicate_count_eq(
        self, node: PredCountEq, ctx: WalkContext
    ) -> list[str]:
        prefix = "" if ctx.index == 0 else "and "
        return [f"{ctx.indent}{prefix}len(i) == {node.value}"]

    def visit_predicate_count_ge(
        self, node: PredCountGe, ctx: WalkContext
    ) -> list[str]:
        prefix = "" if ctx.index == 0 else "and "
        return [f"{ctx.indent}{prefix}len(i) >= {node.value}"]

    def visit_predicate_count_gt(
        self, node: PredCountGt, ctx: WalkContext
    ) -> list[str]:
        prefix = "" if ctx.index == 0 else "and "
        return [f"{ctx.indent}{prefix}len(i) > {node.value}"]

    def visit_predicate_count_le(
        self, node: PredCountLe, ctx: WalkContext
    ) -> list[str]:
        prefix = "" if ctx.index == 0 else "and "
        return [f"{ctx.indent}{prefix}len(i) <= {node.value}"]

    def visit_predicate_count_lt(
        self, node: PredCountLt, ctx: WalkContext
    ) -> list[str]:
        prefix = "" if ctx.index == 0 else "and "
        return [f"{ctx.indent}{prefix}len(i) < {node.value}"]

    def visit_predicate_count_ne(
        self, node: PredCountNe, ctx: WalkContext
    ) -> list[str]:
        prefix = "" if ctx.index == 0 else "and "
        return [f"{ctx.indent}{prefix}len(i) != {node.value}"]

    def visit_predicate_re(self, node: PredRe, ctx: WalkContext) -> list[str]:
        pat = repr(node.pattern)
        prefix = "" if ctx.index == 0 else "and "
        return [f"{ctx.indent}{prefix}bool(re.search({pat}, i))"]

    def visit_predicate_re_any(
        self, node: PredReAny, ctx: WalkContext
    ) -> list[str]:
        pat = repr(node.pattern)
        prefix = "" if ctx.index == 0 else "and "
        return [
            f"{ctx.indent}{prefix}any(bool(re.search({pat}, j)) for j in i)"
        ]

    def visit_predicate_re_all(
        self, node: PredReAll, ctx: WalkContext
    ) -> list[str]:
        pat = repr(node.pattern)
        prefix = "" if ctx.index == 0 else "and "
        return [
            f"{ctx.indent}{prefix}all(bool(re.search({pat}, j)) for j in i)"
        ]
