"""Python backend visitor (composition model).

Ports all dialect-agnostic Python codegen from ``PyHtmlBase`` to the new
``BaseWalker`` traversal core.  Handlers return ``list[str]`` (no generators,
no signal protocol).  DOM-specific spelling is delegated to a ``DomSpelling``
strategy set by the concrete dialect subclass.
"""

from __future__ import annotations

import inspect
import json
import re
from typing import Any, cast

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
    PlaceholderSpec,
    PlaceholderTemplate,
    TypeInfo,
    VariableType as VT,
    StructType as ST,
)
from ssc_codegen.ast.struct import RequestHttp
from ssc_codegen.naming import to_pascal_case, to_snake_case
from ssc_codegen.traversal.utils import (
    jsonify_path_to_segments,
    module_has_rest,
    module_is_rest_only,
)
from ssc_codegen.generation.builder import ModuleBuilder
from ssc_codegen.request_spec import validate_json_body
from ssc_codegen.targets.python.http_libs.aiohttp import AioHttpStrategy
from ssc_codegen.targets.python.http_libs.base import HttpLibStrategy
from ssc_codegen.targets.python.http_libs.httpx import HttpxStrategy
from ssc_codegen.targets.python.http_libs.requests import RequestsStrategy
from ssc_codegen.traversal.context import WalkContext
from ssc_codegen.traversal.walker import BaseWalker


# ===========================================================================
# RequestHttp → Python code rendering helpers (pure functions)
# ===========================================================================

_STYLE_SEPARATOR: dict[str, str] = {"csv": ",", "pipe": "|", "space": " "}

PH_PY_TYPES = {"str": "str", "int": "int", "float": "float", "bool": "bool"}

_RUNTIME_BASE_EXPORT_NAMES: list[str] = [
    "repl_map",
    "normalize_text",
    "_UnmatchedTableRow",
    "unescape_text",
    "rm_prefix",
    "rm_suffix",
    "UNMATCHED_TABLE_ROW",
]

_RUNTIME_REST_EXPORT_NAMES: list[str] = [
    "Ok",
    "Err",
    "UnknownErr",
    "TransportErr",
    "ErrMatcher",
    "ssc_dispatch_err",
    "ssc_rest_call",
    "ssc_rest_call_async",
]


def _runtime_export_names(module: Module) -> list[str]:
    names = list(_RUNTIME_BASE_EXPORT_NAMES)
    if module_has_rest(module):
        names.extend(_RUNTIME_REST_EXPORT_NAMES)
    return names


def _escape_fstring(tmpl: PlaceholderTemplate) -> str:
    result: list[str] = []
    for part in tmpl.parts:
        if isinstance(part, PlaceholderSpec):
            result.append("{" + part.name + "}")
        else:
            for ch in part:
                result.append(ch * 2 if ch in "{}" else ch)
    return "".join(result)


def render_value(tmpl: PlaceholderTemplate) -> str:
    if ph := tmpl.single_placeholder():
        if ph.is_array and ph.style in ("csv", "pipe", "space"):
            sep = _STYLE_SEPARATOR[ph.style or "csv"]
            return f"{sep!r}.join(str(_x) for _x in {ph.name})"
        return ph.name
    if tmpl.has_placeholders:
        return f'f"{_escape_fstring(tmpl)}"'
    return repr(tmpl.source)


def render_dict(d: dict[str, PlaceholderTemplate]) -> str:
    if not d:
        return "{}"
    inner = ", ".join(f"{k!r}: {render_value(v)}" for k, v in d.items())
    return "{" + inner + "}"


def emit_dict_builder(
    varname: str, d: dict[str, PlaceholderTemplate], indent: str
) -> list[str]:
    lines: list[str] = [f"{indent}{varname}: dict = {{}}"]
    for key, tmpl in d.items():
        ph = tmpl.single_placeholder()
        if ph is None:
            lines.append(f"{indent}{varname}[{key!r}] = {render_value(tmpl)}")
            continue
        effective_key = (
            f"{key}[]" if (ph.is_array and ph.style == "bracket") else key
        )
        expr = render_value(tmpl)
        if ph.is_optional:
            lines.append(f"{indent}if {ph.name} is not None:")
            lines.append(f"{indent}    {varname}[{effective_key!r}] = {expr}")
        else:
            lines.append(f"{indent}{varname}[{effective_key!r}] = {expr}")
    return lines


def render_json_body(tmpl: PlaceholderTemplate) -> str:
    validate_json_body(tmpl.source)
    sentinels: dict[str, str] = {}
    out: list[str] = []
    in_string = False
    for part in tmpl.parts:
        if isinstance(part, PlaceholderSpec):
            key = f"__SSC_PH_{len(sentinels)}__"
            sentinels[key] = part.name
            out.append(key if in_string else '"' + key + '"')
        else:
            i = 0
            n = len(part)
            while i < n:
                ch = part[i]
                if ch == "\\" and i + 1 < n:
                    out.append(part[i : i + 2])
                    i += 2
                    continue
                if ch == '"':
                    in_string = not in_string
                out.append(ch)
                i += 1
    substituted = "".join(out)
    parsed = json.loads(substituted)
    sentinel_re = re.compile(r"__SSC_PH_\d+__")

    def _emit(v: object) -> str:
        if v is None:
            return "None"
        if isinstance(v, bool):
            return "True" if v else "False"
        if isinstance(v, (int, float)):
            return repr(v)
        if isinstance(v, str):
            if v in sentinels:
                return sentinels[v]
            if sentinel_re.search(v):

                def _fmt(m: re.Match) -> str:
                    return "{" + sentinels[m.group(0)] + "}"

                escaped = v.replace("\\", "\\\\").replace("'", "\\'")
                escaped = escaped.replace("{", "{{").replace("}", "}}")
                body = sentinel_re.sub(_fmt, escaped)
                return "f'" + body + "'"
            return repr(v)
        if isinstance(v, dict):
            items = ", ".join(f"{k!r}: {_emit(val)}" for k, val in v.items())
            return "{" + items + "}"
        if isinstance(v, list):
            items = ", ".join(_emit(x) for x in v)
            return "[" + items + "]"
        raise TypeError(f"unsupported JSON body element: {type(v).__name__}")

    return _emit(parsed)


def render_body(spec: RequestHttp) -> tuple[str, str] | None:
    if spec.body_kind == "empty" or spec.body is None:
        return None
    if spec.body_kind == "json":
        assert isinstance(spec.body, PlaceholderTemplate)
        return ("json", render_json_body(spec.body))
    if spec.body_kind == "form":
        assert isinstance(spec.body, dict)
        return ("data", render_dict(spec.body))
    assert isinstance(spec.body, PlaceholderTemplate)
    return ("data", render_value(spec.body))


def _py_path_expr(body_var: str, path: str) -> str:
    expr = body_var
    for seg in path.split("."):
        if seg.isdigit():
            expr += f"[{seg}]"
        else:
            expr += f".get({seg!r})"
    return expr


def _render_py_condition_lambda(
    required_keys: list[str], conditions: dict[str, object]
) -> str | None:
    parts: list[str] = []
    for key in required_keys:
        parts.append(f"{key!r} in _b")
    for path, value in conditions.items():
        lhs = _py_path_expr("_b", path)
        if isinstance(value, bool):
            parts.append(f"{lhs} is {value}")
        elif value is None:
            parts.append(f"{lhs} is None")
        elif isinstance(value, (int, float)):
            parts.append(f"{lhs} == {value}")
        else:
            parts.append(f"{lhs} == {value!r}")
    if not parts:
        return None
    return f"lambda _b: {' and '.join(parts)}"


# ===========================================================================
# PythonVisitor
# ===========================================================================


class PythonVisitor(BaseWalker):
    """Shared Python codegen visitor.

    All ``visit_*`` handlers return ``list[str]``.  DOM-specific methods
    (selectors, extract, cast, DOM predicates) are overridden by concrete
    dialect subclasses that delegate to a ``DomSpelling`` strategy.
    """

    STD_MODULE_NAME: str = "ssc_std"

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

    # --- predicate formatting ---
    AND_OP: str = "and"

    # --- REST config ---
    REST_SEPARATORS: dict[str, str] = {"csv": ",", "pipe": "|", "space": " "}

    _HTTP_STRATEGIES: dict[str, type[HttpLibStrategy]] = {
        "httpx": HttpxStrategy,
        "aiohttp": AioHttpStrategy,
        "requests": RequestsStrategy,
    }

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
        client = meta.get("http_client")
        if client and client in self._HTTP_STRATEGIES:
            self._http = self._HTTP_STRATEGIES[client]()
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

    def convert_batch(
        self,
        modules: list[tuple[str, Module]],
        **meta,
    ) -> dict[str, str]:
        inline = meta.get("inline_std", True)
        ctx = self._make_ctx({**meta, "inline_std": inline})

        if inline:
            results: dict[str, str] = {}
            for name, module_ast in modules:
                self._reset_state()
                results[name] = "\n".join(self._walk_module(module_ast, ctx))
            return results

        shared_std_defs: dict[str, tuple[list[str], str]] = {}
        shared_std_imports: dict[str, None] = {}
        for _, module_ast in modules:
            self._reset_state()
            self._walk_module(module_ast, ctx)
            shared_std_defs.update(self._builder.std_defs)
            shared_std_imports.update(self._builder._std_imports)

        results = {}
        std_module_name = ctx.meta.get("std_module_name", self.STD_MODULE_NAME)
        if shared_std_defs:
            self._reset_state()
            self._builder._std_defs = dict(shared_std_defs)
            self._builder._std_imports = dict(shared_std_imports)
            results[std_module_name] = self._render_std_module()

        for name, module_ast in modules:
            self._reset_state()
            self._builder._std_defs = dict(shared_std_defs)
            self._builder._std_imports = dict(shared_std_imports)
            self._walk_module(module_ast, ctx)
            self._builder._std_defs = dict(shared_std_defs)
            self._builder._std_imports = dict(shared_std_imports)
            results[name] = "\n".join(self._walk_module(module_ast, ctx))

        return results

    def _walk_module(self, module_ast: Module, ctx: WalkContext) -> list[str]:
        lines: list[str] = list(self.visit_module(module_ast, ctx))
        for node in module_ast.body:
            lines.extend(self.walk(node, ctx))
        return lines

    # === STD RENDERING (Python-specific) ===

    def _render_std_section(self, ctx: WalkContext) -> list[str]:
        if not self._builder.has_std:
            return []
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

    def _pred_line(self, ctx: WalkContext, cond: str) -> str:
        prefix = "" if ctx.index == 0 else f"{self.AND_OP} "
        return f"{ctx.indent}{prefix}{cond}"

    def _resolve_ph_value(self, tmpl: PlaceholderTemplate) -> str:
        if ph := tmpl.single_placeholder():
            if ph.is_array and ph.style in ("csv", "pipe", "space"):
                sep = self.REST_SEPARATORS[ph.style or "csv"]
                return f"{sep!r}.join(str(_x) for _x in {ph.name})"
            return ph.name
        if tmpl.has_placeholders:
            return f'f"{_escape_fstring(tmpl)}"'
        return repr(tmpl.source)

    # === MODULE ===

    def visit_module(self, node: Module, ctx: WalkContext) -> list[str]:
        lines: list[str] = ["# autogenerated by ssc-gen. DO NOT EDIT"]
        if node.doc:
            lines.extend(['"""', node.doc, '"""'])
        has_rest = module_has_rest(node)
        is_rest_only = module_is_rest_only(node)
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
            if not runtime:
                self._builder.require_import(
                    "from dataclasses import dataclass, field"
                )
                self._builder.require_import(
                    "from typing import Callable, Generic, Literal, Mapping, TypeVar"
                )
            self._builder.require_import(self._http.import_line)
        return lines

    def visit_utilities(self, node: Utilities, ctx: WalkContext) -> list[str]:
        lines: list[str] = []
        runtime = ctx.meta.get("runtime_module")
        if runtime:
            mod = node.parent
            if isinstance(mod, Module):
                names = _runtime_export_names(mod)
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
                    "class _UnmatchedTableRow:",
                    "    pass",
                    "",
                    "UNMATCHED_TABLE_ROW = _UnmatchedTableRow()",
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
        if node.schema_name:
            base = f"{to_pascal_case(node.schema_name)}Json"
            value_type = f"List[{base}]" if node.schema_is_array else base
        else:
            value_type = "Any"
        return [
            "@dataclass(frozen=True)",
            f"class {node.name}(Err[{value_type}]):",
            f"    status: Literal[{node.status}] = {node.status}",
            "",
        ]

    def visit_result_alias_def(
        self, node: ResultAliasDef, ctx: WalkContext
    ) -> list[str]:
        if node.response_schema:
            base = f"{to_pascal_case(node.response_schema)}Json"
            ok_type = f"List[{base}]" if node.response_is_array else base
        else:
            ok_type = "None"
        parts = [
            f"Ok[{ok_type}]",
            *node.err_variants,
            "UnknownErr",
            "TransportErr",
        ]
        return [f"{node.name} = Union[{', '.join(parts)}]", ""]

    def visit_matcher_list_def(
        self, node: MatcherListDef, ctx: WalkContext
    ) -> list[str]:
        var = f"_{to_snake_case(node.struct_name)}_matchers"
        lines = [f"{var} = ["]
        for e in node.entries:
            check = _render_py_condition_lambda(e.required_keys, e.conditions)
            check_arg = check if check else "None"
            lines.append(
                f"    ErrMatcher({e.status}, {check_arg}, {e.factory_name}),"
            )
        lines.append("]")
        return lines

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
            t_ret = f"Union[{t_ret}, _UnmatchedTableRow]"
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

    # === REST / FETCH ===

    _DICT_KWARGS = (
        ("headers", "_headers"),
        ("cookies", "_cookies"),
        ("params", "_params"),
    )

    def _placeholder_params(self, http: RequestHttp) -> str:
        if not http.placeholders:
            return ""
        parts: list[str] = []
        for ph in sorted(http.placeholders, key=lambda p: p.is_optional):
            t = PH_PY_TYPES[ph.type_name]
            if ph.is_array:
                t = f"List[{t}]"
            parts.append(
                f"{ph.name}: Optional[{t}] = None"
                if ph.is_optional
                else f"{ph.name}: {t}"
            )
        return ", *, " + ", ".join(parts)

    def visit_method_fetch(
        self, node: MethodFetch, ctx: WalkContext
    ) -> list[str]:
        assert node.parent is not None
        spec = node.http_request.with_renamed_placeholders(to_snake_case)
        struct_name = to_pascal_case(cast(StructBase, node.parent).name)
        suffix = ("_" + to_snake_case(node.name)) if node.name else ""
        ph_params = self._placeholder_params(spec)

        i1 = ctx.indent
        i2 = i1 + ctx.indent_char
        i3 = i2 + ctx.indent_char

        pre_lines: list[str] = []
        kwargs_lines: list[str] = [
            f"{i3}{spec.method!r},",
            f"{i3}{self._resolve_ph_value(spec.url)},",
        ]
        for attr, varname in self._DICT_KWARGS:
            d = getattr(spec, attr)
            if not d:
                continue
            from ssc_codegen.traversal.utils import dict_needs_builder

            if dict_needs_builder(d):
                pre_lines.extend(emit_dict_builder(varname, d, i2))
                kwargs_lines.append(f"{i3}{attr}={varname},")
            else:
                kwargs_lines.append(f"{i3}{attr}={render_dict(d)},")
        body_result = render_body(spec)
        if body_result:
            kwargs_lines.append(f"{i3}{body_result[0]}={body_result[1]},")

        post_lines: list[str] = [f"{i2}_resp.raise_for_status()"]
        if node.response_path:
            accessor = "".join(
                f"[{p!r}]" for p in node.response_path.split(".")
            )
            post_lines.append(f"{i2}_data = _resp.json()")
            if node.response_join:
                post_lines.append(
                    f"{i2}_body = {node.response_join!r}.join(_data{accessor})"
                )
            else:
                post_lines.append(f"{i2}_body = _data{accessor}")
        else:
            post_lines.append(f"{i2}_body = _resp.text")
        post_lines.append(f"{i2}return cls(_body)")

        lines: list[str] = []
        lines.append(f"{i1}@classmethod")
        lines.append(
            f'{i1}def fetch{suffix}(cls, client: {self._http.sync_client_type}{ph_params}) -> "{struct_name}":'
        )
        lines.extend(pre_lines)
        lines.extend([f"{i2}_resp = client.request(", *kwargs_lines, f"{i2})"])
        lines.extend(post_lines)
        lines.append("")

        lines.append(f"{i1}@classmethod")
        lines.append(
            f'{i1}async def async_fetch{suffix}(cls, client: {self._http.async_client_type}{ph_params}) -> "{struct_name}":'
        )
        lines.extend(pre_lines)
        lines.extend(
            [f"{i2}_resp = await client.request(", *kwargs_lines, f"{i2})"]
        )
        lines.extend(post_lines)
        return lines

    def visit_method_rest(
        self, node: MethodRest, ctx: WalkContext
    ) -> list[str]:
        spec = node.http_request.with_renamed_placeholders(to_snake_case)
        struct = node.parent
        assert isinstance(struct, StructBase)
        method_name = to_snake_case(node.name) if node.name else "fetch"
        ret_type = node.result_alias_name or "None"
        ph_params = self._placeholder_params(spec)
        matchers_var = f"_{to_snake_case(struct.name)}_matchers"

        i1 = ctx.indent
        i2 = i1 + ctx.indent_char
        i3 = i2 + ctx.indent_char

        doc_line = f'{i2}"""{node.doc}"""' if node.doc else None

        pre_lines: list[str] = []
        kwargs_lines: list[str] = []
        for attr, varname in self._DICT_KWARGS:
            d = getattr(spec, attr)
            if not d:
                continue
            from ssc_codegen.traversal.utils import dict_needs_builder

            if dict_needs_builder(d):
                pre_lines.extend(emit_dict_builder(varname, d, i2))
                kwargs_lines.append(f"{i3}{attr}={varname},")
            else:
                kwargs_lines.append(f"{i3}{attr}={render_dict(d)},")
        body_result = render_body(spec)
        if body_result:
            kwargs_lines.append(f"{i3}{body_result[0]}={body_result[1]},")

        void_kwarg: list[str] = []
        if not node.response_schema:
            void_kwarg = [f"{i3}_value_fn=lambda _: None,"]

        def _body(fn_name: str, await_kw: str) -> list[str]:
            body: list[str] = []
            if doc_line:
                body.append(doc_line)
            body.extend(pre_lines)
            body.append(f"{i2}return {await_kw}{fn_name}(")
            body.append(
                f"{i3}client, {matchers_var}, {spec.method!r},"
                f" {render_value(spec.url)},"
            )
            body.extend(void_kwarg)
            body.extend(kwargs_lines)
            body.append(f"{i2})")
            return body

        lines: list[str] = []
        lines.append(f"{i1}@classmethod")
        lines.append(
            f"{i1}def {method_name}(cls, client: {self._http.sync_client_type}{ph_params}) -> {ret_type}:"
        )
        lines.extend(_body("ssc_rest_call", ""))
        lines.append("")

        lines.append(f"{i1}@classmethod")
        lines.append(
            f"{i1}async def async_{method_name}(cls, client: {self._http.async_client_type}{ph_params}) -> {ret_type}:"
        )
        lines.extend(_body("ssc_rest_call_async", "await "))
        return lines

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

    def visit_predicate_css(self, node: PredCss, ctx: WalkContext) -> list[str]:
        return [self._pred_line(ctx, self._dom.pred_css(node))]

    def visit_predicate_xpath(
        self, node: PredXpath, ctx: WalkContext
    ) -> list[str]:
        return [self._pred_line(ctx, self._dom.pred_xpath(node))]

    def visit_predicate_has_attr(
        self, node: PredHasAttr, ctx: WalkContext
    ) -> list[str]:
        return [self._pred_line(ctx, self._dom.pred_has_attr(node))]

    def visit_predicate_attr_contains(
        self, node: PredAttrContains, ctx: WalkContext
    ) -> list[str]:
        return [self._pred_line(ctx, self._dom.pred_attr_contains(node))]

    def visit_predicate_attr_starts(
        self, node: PredAttrStarts, ctx: WalkContext
    ) -> list[str]:
        return [self._pred_line(ctx, self._dom.pred_attr_starts(node))]

    def visit_predicate_attr_ends(
        self, node: PredAttrEnds, ctx: WalkContext
    ) -> list[str]:
        return [self._pred_line(ctx, self._dom.pred_attr_ends(node))]

    def visit_predicate_attr_eq(
        self, node: PredAttrEq, ctx: WalkContext
    ) -> list[str]:
        return [self._pred_line(ctx, self._dom.pred_attr_eq(node))]

    def visit_predicate_attr_ne(
        self, node: PredAttrNe, ctx: WalkContext
    ) -> list[str]:
        return [self._pred_line(ctx, self._dom.pred_attr_ne(node))]

    def visit_predicate_attr_re(
        self, node: PredAttrRe, ctx: WalkContext
    ) -> list[str]:
        return [self._pred_line(ctx, self._dom.pred_attr_re(node))]

    def visit_predicate_text_contains(
        self, node: PredTextContains, ctx: WalkContext
    ) -> list[str]:
        return [self._pred_line(ctx, self._dom.pred_text_contains(node))]

    def visit_predicate_text_starts(
        self, node: PredTextStarts, ctx: WalkContext
    ) -> list[str]:
        return [self._pred_line(ctx, self._dom.pred_text_starts(node))]

    def visit_predicate_text_ends(
        self, node: PredTextEnds, ctx: WalkContext
    ) -> list[str]:
        return [self._pred_line(ctx, self._dom.pred_text_ends(node))]

    def visit_predicate_text_re(
        self, node: PredTextRe, ctx: WalkContext
    ) -> list[str]:
        return [self._pred_line(ctx, self._dom.pred_text_re(node))]

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
        pattern = repr(node.pattern)
        return [f"{ctx.indent}{ctx.nxt} = re.search({pattern}, {ctx.prv})[1]"]

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
        return [f"{ctx.indent}{ctx.nxt} = {ctx.prv}[{node.i}]"]

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

    def visit_assert(self, node: Assert, ctx: WalkContext) -> list[str]:
        lines = [
            f"{ctx.indent}i = {ctx.prv}",
            f"{ctx.indent}assert (",
        ]
        lines.extend(self.walk_children(node, ctx))
        lines.extend(
            [ctx.deeper().indent + ")", f"{ctx.indent}{ctx.nxt} = {ctx.prv}"]
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

    # === STRING-LEVEL / COUNT / REGEX PREDICATES ===

    def visit_predicate_contains(
        self, node: PredContains, ctx: WalkContext
    ) -> list[str]:
        vals = repr(node.values)
        return [self._pred_line(ctx, f"any(v in i for v in {vals})")]

    def visit_predicate_eq(self, node: PredEq, ctx: WalkContext) -> list[str]:
        values = node.values
        if len(values) == 1 and isinstance(values[0], int):
            cond = f"len(i) == {values[0]}"
        else:
            cond = f"any(i == v for v in {values!r})"
        return [self._pred_line(ctx, cond)]

    def visit_predicate_ne(self, node: PredNe, ctx: WalkContext) -> list[str]:
        values = node.values
        if len(values) == 1 and isinstance(values[0], int):
            cond = f"len(i) != {values[0]}"
        else:
            cond = f"all(i != v for v in {values!r})"
        return [self._pred_line(ctx, cond)]

    def visit_predicate_starts(
        self, node: PredStarts, ctx: WalkContext
    ) -> list[str]:
        vals = repr(node.values)
        return [self._pred_line(ctx, f"i.startswith({vals})")]

    def visit_predicate_ends(
        self, node: PredEnds, ctx: WalkContext
    ) -> list[str]:
        vals = repr(node.values)
        return [self._pred_line(ctx, f"i.endswith({vals})")]

    def visit_pred_count_range(
        self, node: PredCountRange, ctx: WalkContext
    ) -> list[str]:
        return [self._pred_line(ctx, f"{node.start} < len(i) < {node.end}")]

    def visit_predicate_count_eq(
        self, node: PredCountEq, ctx: WalkContext
    ) -> list[str]:
        return [self._pred_line(ctx, f"len(i) == {node.value}")]

    def visit_predicate_count_ge(
        self, node: PredCountGe, ctx: WalkContext
    ) -> list[str]:
        return [self._pred_line(ctx, f"len(i) >= {node.value}")]

    def visit_predicate_count_gt(
        self, node: PredCountGt, ctx: WalkContext
    ) -> list[str]:
        return [self._pred_line(ctx, f"len(i) > {node.value}")]

    def visit_predicate_count_le(
        self, node: PredCountLe, ctx: WalkContext
    ) -> list[str]:
        return [self._pred_line(ctx, f"len(i) <= {node.value}")]

    def visit_predicate_count_lt(
        self, node: PredCountLt, ctx: WalkContext
    ) -> list[str]:
        return [self._pred_line(ctx, f"len(i) < {node.value}")]

    def visit_predicate_count_ne(
        self, node: PredCountNe, ctx: WalkContext
    ) -> list[str]:
        return [self._pred_line(ctx, f"len(i) != {node.value}")]

    def visit_predicate_re(self, node: PredRe, ctx: WalkContext) -> list[str]:
        pat = repr(node.pattern)
        return [self._pred_line(ctx, f"bool(re.search({pat}, i))")]

    def visit_predicate_re_any(
        self, node: PredReAny, ctx: WalkContext
    ) -> list[str]:
        pat = repr(node.pattern)
        return [
            self._pred_line(ctx, f"any(bool(re.search({pat}, j)) for j in i)")
        ]

    def visit_predicate_re_all(
        self, node: PredReAll, ctx: WalkContext
    ) -> list[str]:
        pat = repr(node.pattern)
        return [
            self._pred_line(ctx, f"all(bool(re.search({pat}, j)) for j in i)")
        ]
