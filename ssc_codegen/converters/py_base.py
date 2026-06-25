"""Dialect-agnostic Python HTML-parser codegen base (new Visitor API).

``PyHtmlBase`` holds all dialect-agnostic codegen logic (types, struct
scaffolding, string/regex/array/cast/control ops, string-level predicates)
plus the dialect config knobs read from class attributes.

Concrete dialects (``PyBs4`` in py_bs4.py, ``PyLxml`` in py_lxml.py) only set
the config attributes and override the handful of expression methods whose
spelling genuinely differs across parser libraries (selectors, text/raw/attr
extraction, to_bool, document/attr/text predicates).

Std helpers are declared co-located with their caller via ``STD(name, code=,
imports=)`` — no external ``STD_LIBS`` registry. Trivial one-liners are
inlined directly; multi-statement helpers (multi-query select, repl_map,
unescape) use ``STD()`` so they dedupe and can be extracted via ``-R``.
"""

import json
import re

from ssc_codegen.ast.array import Index, Len, Slice, Unique
from ssc_codegen.ast.cast import Jsonify, Nested, ToFloat, ToInt
from ssc_codegen.ast.control import Fallback, Return, Self
from ssc_codegen.ast.jsondef import JsonDef, JsonDefField
from ssc_codegen.ast.module import (
    CodeEndHook,
    CodeStartHook,
    Module,
    Utilities,
)
from ssc_codegen.ast import (
    ErrorResponse,
    StructDocstring,
    TypeInfo,
    VariableType as VT,
    StructType as ST,
)
from ssc_codegen.ast.predicate_containers import Assert, Filter, Match
from ssc_codegen.ast.predicate_ops import (
    LogicAnd,
    LogicNot,
    LogicOr,
    PredStarts,
    PredEnds,
    PredContains,
    PredCountEq,
    PredCountGe,
    PredCountGt,
    PredCountLe,
    PredCountLt,
    PredCountNe,
    PredCountRange,
    PredEq,
    PredNe,
    PredRe,
    PredReAll,
    PredReAny,
)
from ssc_codegen.ast.regex import Re, ReAll, ReSub
from ssc_codegen.ast.string import (
    Fmt,
    Join,
    Lower,
    Ltrim,
    NormalizeSpace,
    Repl,
    ReplMap,
    RmPrefix,
    RmPrefixSuffix,
    RmSuffix,
    Rtrim,
    Split,
    Trim,
    Unescape,
    Upper,
)
from ssc_codegen.ast.struct import (
    CheckMethod,
    Field,
    Init,
    InitField,
    Key,
    MethodBase,
    MethodFetch,
    MethodRest,
    PlaceholderSpec,
    PreValidate,
    SplitDoc,
    StartParse,
    Struct,
    StructRest,
    StructBase,
    TableConfig,
    TableMatchKey,
    TableRows,
    Value,
)
from ssc_codegen.ast.typedef import TypeDef, TypeDefField
from ssc_codegen.converters.base import ConverterContext
from ssc_codegen.converters.helpers import (
    jsonify_path_to_segments,
    to_pascal_case,
    to_snake_case,
)
from ssc_codegen.converters.visitor import (
    IMPORT,
    STD,
    TRAVERSE,
    VisitStream,
    Visitor,
)
from ssc_codegen.request_spec import (
    RequestSpec,
    normalize_placeholder_names,
    validate_json_body,
)


# ===========================================================================
# RequestSpec → Python code rendering (ported from py_render.py)
# ===========================================================================

_STYLE_SEPARATOR: dict[str, str] = {"csv": ",", "pipe": "|", "space": " "}


def _render_array_join(ph: PlaceholderSpec) -> str:
    sep = _STYLE_SEPARATOR[ph.style or "csv"]
    return f"{sep!r}.join(str(_x) for _x in {ph.name})"


def render_value(v: str) -> str:
    """Convert a RequestSpec string value to a Python code fragment."""
    if ph := PlaceholderSpec.parse(v):
        if ph.is_array and ph.style in ("csv", "pipe", "space"):
            return _render_array_join(ph)
        return ph.name
    if PlaceholderSpec.search(v):
        return f'f"{_escape_fstring(v)}"'
    return repr(v)


def _escape_fstring(template: str) -> str:
    result: list[str] = []
    i = 0
    while i < len(template):
        if template[i : i + 2] == "{{":
            matched = PlaceholderSpec.match_at(template, i)
            if matched is not None:
                end, ph = matched
                result.append("{" + ph.name + "}")
                i = end
                continue
        elif template[i] in "{}":
            result.append(template[i] * 2)
            i += 1
        else:
            result.append(template[i])
            i += 1
    return "".join(result)


def render_dict(d: dict[str, str], *, indent: str = "") -> str:
    if not d:
        return "{}"
    inner = ", ".join(f"{k!r}: {render_value(str(v))}" for k, v in d.items())
    return "{" + inner + "}"


def _dict_entry_placeholder(v: str) -> PlaceholderSpec | None:
    return PlaceholderSpec.parse(str(v))


def dict_needs_builder(d: dict[str, str]) -> bool:
    for v in d.values():
        ph = _dict_entry_placeholder(str(v))
        if ph is None:
            continue
        if ph.is_optional:
            return True
        if ph.is_array and ph.style == "bracket":
            return True
    return False


def emit_dict_builder(
    varname: str, d: dict[str, str], indent: str
) -> list[str]:
    lines: list[str] = [f"{indent}{varname}: dict = {{}}"]
    for key, value in d.items():
        value = str(value)
        ph = _dict_entry_placeholder(value)
        if ph is None:
            lines.append(f"{indent}{varname}[{key!r}] = {render_value(value)}")
            continue
        effective_key = (
            f"{key}[]" if (ph.is_array and ph.style == "bracket") else key
        )
        expr = render_value(value)
        if ph.is_optional:
            lines.append(f"{indent}if {ph.name} is not None:")
            lines.append(f"{indent}    {varname}[{effective_key!r}] = {expr}")
        else:
            lines.append(f"{indent}{varname}[{effective_key!r}] = {expr}")
    return lines


def render_json_body(raw: str) -> str:
    validate_json_body(raw)

    sentinels: dict[str, str] = {}
    out: list[str] = []
    i = 0
    n = len(raw)
    in_string = False
    while i < n:
        if raw[i : i + 2] == "{{":
            matched = PlaceholderSpec.match_at(raw, i)
            if matched is not None:
                end, ph = matched
                key = f"__SSC_PH_{len(sentinels)}__"
                sentinels[key] = ph.name
                out.append(key if in_string else '"' + key + '"')
                i = end
                continue
        ch = raw[i]
        if ch == "\\" and i + 1 < n:
            out.append(raw[i : i + 2])
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


def render_body(spec: RequestSpec) -> tuple[str, str] | None:
    if spec.body_kind == "empty" or spec.body is None:
        return None
    if spec.body_kind == "json":
        return ("json", render_json_body(str(spec.body)))
    if spec.body_kind == "form":
        assert isinstance(spec.body, dict)
        return ("data", render_dict(spec.body))
    return ("data", render_value(str(spec.body)))


# ===========================================================================
# REST infrastructure (ported from runtime/, py_bs4.py)
# ===========================================================================

PH_PY_TYPES = {"str": "str", "int": "int", "float": "float", "bool": "bool"}

REST_UTILITIES = (
    "_T = TypeVar('_T')",
    "_E = TypeVar('_E')",
    "",
    "@dataclass(frozen=True)",
    "class Ok(Generic[_T]):",
    "    status: int = 0",
    "    headers: Mapping[str, str] = field(default_factory=dict)",
    "    value: _T = None  # type: ignore[assignment]",
    "    is_ok: Literal[True] = True",
    "",
    "@dataclass(frozen=True)",
    "class Err(Generic[_E]):",
    "    status: int = 0",
    "    headers: Mapping[str, str] = field(default_factory=dict)",
    "    value: _E = None  # type: ignore[assignment]",
    "    is_ok: Literal[False] = False",
    "",
    "@dataclass(frozen=True)",
    "class UnknownErr(Err[Any]):",
    "    pass",
    "",
    "@dataclass(frozen=True)",
    "class TransportErr(Err[None]):",
    "    status: Literal[0] = 0",
    "    cause: str = ''",
    "    value: None = None",
    "    headers: Mapping[str, str] = field(default_factory=dict)",
    "",
    "",
    "def ssc_parse_response(_resp):",
    "    _status = _resp.status_code",
    "    _headers = {k.lower(): v for k, v in _resp.headers.items()}",
    "    try:",
    "        _body = _resp.json()",
    "    except Exception:",
    "        _body = None",
    "    return _status, _headers, _body",
    "",
)


def module_has_rest(module: Module) -> bool:
    return any(isinstance(n, StructRest) for n in module.body)


def module_is_rest_only(module: Module) -> bool:
    structs = [n for n in module.body if isinstance(n, StructBase)]
    return len(structs) == 0 or all(isinstance(s, StructRest) for s in structs)


def err_subclass_name(struct_name: str, err: ErrorResponse) -> str:
    base = f"{to_pascal_case(struct_name)}Err{err.status}"
    for key in err.required_keys:
        base += to_pascal_case(key.replace(".", "_").replace("-", "_"))
    if err.conditions:
        for key in err.conditions:
            base += to_pascal_case(key.replace(".", "_").replace("-", "_"))
    return base


def err_value_type(err: ErrorResponse, struct: StructBase) -> str:
    schema = err.schema_name
    if not schema:
        return "Any"
    type_name = f"{to_pascal_case(schema)}Json"
    mod = struct.parent
    if mod is not None:
        for n in mod.body:
            if isinstance(n, JsonDef) and n.name == schema and n.is_array:
                return f"List[{type_name}]"
    return type_name


def rest_err_union_type(struct: StructBase) -> str:
    variants: list[str] = []
    seen: set[str] = set()
    for err in struct.errors:
        cls_name = err_subclass_name(struct.name, err)
        if cls_name not in seen:
            seen.add(cls_name)
            variants.append(cls_name)
    return "Union[" + ", ".join([*variants, "UnknownErr", "None"]) + "]"


def resolve_path_expr(body_var: str, path: str) -> str:
    parts = path.split(".")
    expr = body_var
    for seg in parts:
        if seg.isdigit():
            expr += f"[{seg}]"
        else:
            expr += f".get({seg!r})"
    return expr


def condition_check_expr(err: ErrorResponse) -> str:
    parts: list[str] = []
    for key in err.required_keys:
        parts.append(f"{key!r} in _body")
    for path, value in err.conditions.items():
        lhs = resolve_path_expr("_body", path)
        if isinstance(value, bool):
            parts.append(f"{lhs} == {value}")
        elif value is None:
            parts.append(f"{lhs} is None")
        elif isinstance(value, (int, float)):
            parts.append(f"{lhs} == {value}")
        else:
            parts.append(f"{lhs} == {value!r}")
    return " and ".join(parts)


def result_alias_name(raw_name: str) -> str:
    return to_pascal_case(raw_name or "fetch") + "Result"


def resolve_ok_payload_type(node: MethodRest) -> str:
    if not node.response_schema:
        return "None"
    struct = node.parent
    mod = struct.parent if struct is not None else None
    schema_type = f"{to_pascal_case(node.response_schema)}Json"
    if mod is not None:
        for n in mod.body:
            if isinstance(n, JsonDef) and n.name == node.response_schema:
                if n.is_array:
                    return f"List[{schema_type}]"
                break
    return schema_type


def emit_rest_error_subclasses(node: StructBase) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()
    for err in node.errors:
        cls_name = err_subclass_name(node.name, err)
        if cls_name in seen:
            continue
        seen.add(cls_name)
        value_type = err_value_type(err, node)
        lines.append("@dataclass(frozen=True)")
        lines.append(f"class {cls_name}(Err[{value_type}]):")
        lines.append(f"    status: Literal[{err.status}] = {err.status}")
        lines.append("")
    return lines


def emit_result_aliases(struct: StructBase) -> list[str]:
    lines: list[str] = []
    for child in struct.body:
        if not isinstance(child, MethodRest):
            continue
        raw_name = child.name or "fetch"
        alias_name = result_alias_name(raw_name)
        payload = resolve_ok_payload_type(child)
        err_variants: list[str] = []
        seen: set[str] = set()
        for err in struct.errors:
            cls_name = err_subclass_name(struct.name, err)
            if cls_name not in seen:
                seen.add(cls_name)
                err_variants.append(cls_name)
        parts = [f"Ok[{payload}]", *err_variants, "UnknownErr", "TransportErr"]
        lines.append(f"{alias_name} = Union[" + ", ".join(parts) + "]")
    return lines


def emit_dispatch_err(node: StructBase, ctx: ConverterContext) -> list[str]:
    i1 = ctx.indent
    i2 = i1 + ctx.indent_char
    i3 = i2 + ctx.indent_char
    i4 = i3 + ctx.indent_char

    errors = node.errors
    status_errors = [
        e for e in errors if not e.conditions and not e.required_keys
    ]
    field_errors = [e for e in errors if e.conditions or e.required_keys]
    union_type = rest_err_union_type(node)

    lines: list[str] = [
        f"{i1}@staticmethod",
        f"{i1}def ssc_dispatch_err("
        f"_status: int, _headers: Mapping[str, str], _body: Any"
        f") -> {union_type}:",
        f"{i2}if 200 <= _status < 300:",
    ]

    if field_errors:
        lines.append(f"{i3}if isinstance(_body, dict):")
        emitted_field_branch = False
        for err in field_errors:
            if 200 <= err.status < 300:
                cls_name = err_subclass_name(node.name, err)
                cond = condition_check_expr(err)
                lines.append(f"{i4}if _status == {err.status} and {cond}:")
                lines.append(
                    f"{i4}{ctx.indent_char}return {cls_name}("
                    f"headers=_headers, value=_body)"
                )
                emitted_field_branch = True
        if not emitted_field_branch:
            lines.pop()
    lines.append(f"{i3}return None")

    for err in status_errors:
        cls_name = err_subclass_name(node.name, err)
        lines.append(f"{i2}if _status == {err.status}:")
        lines.append(f"{i3}return {cls_name}(headers=_headers, value=_body)")

    for err in field_errors:
        if not (200 <= err.status < 300):
            cls_name = err_subclass_name(node.name, err)
            cond = condition_check_expr(err)
            lines.append(
                f"{i2}if _status == {err.status} "
                f"and isinstance(_body, dict) and {cond}:"
            )
            lines.append(
                f"{i3}return {cls_name}(headers=_headers, value=_body)"
            )

    lines.append(
        f"{i2}return UnknownErr(status=_status, headers=_headers, value=_body)"
    )
    return lines


class PyHtmlBase(Visitor):
    """Shared Python HTML-parser codegen. Override config attrs + spelling
    methods in concrete dialects (PyBs4, PyLxml, ...).

    Dialect config (class attributes — plain values, not a descriptor entity):
        PARSER_IMPORTS     — parser-library import lines for visit_module.
        DOCUMENT_TYPE      — scalar annotation for VT.DOCUMENT.
        DOCUMENT_ARRAY_TYPE— annotation for VT.DOCUMENT with is_array=True.
        INIT_ARG_TYPE      — __init__ argument annotation.
        INIT_FROM_STR_EXPR — expression turning a str document into the parser
                             object (referenced inside __init__).
        EXTRA_UTILITIES    — dialect-specific module constants emitted before
                             the std section (e.g. BS4_FEATURES, FALLBACK_HTML_STR).
    """

    # === DIALECT CONFIG (override in subclasses) ===
    PARSER_IMPORTS: tuple[str, ...] = ()
    DOCUMENT_TYPE: str = "Any"
    DOCUMENT_ARRAY_TYPE: str = "List[Any]"
    INIT_ARG_TYPE: str = "Any"
    INIT_FROM_STR_EXPR: str = "document"
    EXTRA_UTILITIES: tuple[str, ...] = ()

    PY_TYPES = {
        VT.STRING: "str",
        VT.BOOL: "bool",
        VT.INT: "int",
        VT.FLOAT: "float",
        VT.NULL: "None",
        VT.JSON: "Any",
        VT.NESTED: "Any",
        VT.AUTO: "Any",
    }
    PARSE_RETURN_TYPE = {
        ST.ITEM: "{}Type",
        ST.LIST: "List[{}Type]",
        ST.FLAT: "List[str]",
        ST.DICT: "{}Type",
        ST.TABLE: "{}Type",
    }

    def _resolve_py_start_parse_t_ret(
        self, struct: StructBase, name: str
    ) -> str:
        return self.PARSE_RETURN_TYPE[struct.type].format(name)

    def _resolve_py_type(self, type_info: TypeInfo | None) -> str:
        """Render TypeInfo into a Python type annotation string.

        VT.DOCUMENT is resolved from DOCUMENT_TYPE / DOCUMENT_ARRAY_TYPE
        (dialect config), not from PY_TYPES — that is the single override
        point for the parser-specific element type.
        """
        if type_info is None:
            return "Any"
        if type_info.base == VT.NESTED and type_info.ref:
            t = f"{to_pascal_case(type_info.ref)}Type"
        elif type_info.base == VT.JSON and type_info.ref:
            t = f"{to_pascal_case(type_info.ref)}Json"
        elif type_info.base == VT.DOCUMENT:
            t = (
                self.DOCUMENT_ARRAY_TYPE
                if type_info.is_array
                else self.DOCUMENT_TYPE
            )
        else:
            t = self.PY_TYPES.get(type_info.base, "Any")
        if type_info.is_array and type_info.base != VT.DOCUMENT:
            t = f"List[{t}]"
        if type_info.is_optional:
            t = f"Optional[{t}]"
        return t

    def _pred_line(self, ctx: ConverterContext, cond: str) -> str:
        """Format one predicate condition; join siblings with ``and``."""
        prefix = "" if ctx.index == 0 else "and "
        return f"{ctx.indent}{prefix}{cond}"

    # === module ===

    def visit_module(self, node: Module, ctx: ConverterContext) -> VisitStream:
        yield "# autogenerated by ssc-gen. DO NOT EDIT"
        if node.doc:
            yield '"""'
            yield node.doc
            yield '"""'
        has_rest = module_has_rest(node)
        is_rest_only = module_is_rest_only(node)
        runtime = ctx.meta.get("runtime_module")
        if not is_rest_only:
            for line in self.PARSER_IMPORTS:
                yield IMPORT(line)
        yield IMPORT(
            "from typing import Any, Dict, List, Optional, TypedDict, Union"
        )
        yield IMPORT("from typing_extensions import NotRequired")
        yield IMPORT("import re")
        yield IMPORT("import json")
        if has_rest:
            if not runtime:
                yield IMPORT("from dataclasses import dataclass, field")
                yield IMPORT(
                    "from typing import Generic, Literal, Mapping, TypeVar"
                )
            yield IMPORT("import httpx")

    def visit_utilities(
        self, node: Utilities, ctx: ConverterContext
    ) -> VisitStream:
        runtime = ctx.meta.get("runtime_module")
        if runtime:
            from ssc_codegen.converters.runtime.py_rest import (
                runtime_export_names,
            )

            mod = node.parent
            if isinstance(mod, Module):
                names = runtime_export_names(mod)
            else:
                names = []
            yield f"from .{runtime} import " + ", ".join(names)
            yield ""
            result = super().visit_utilities(node, ctx)
            if result is not None:
                yield from result
            return
        # module-level imports (always — collected from IMPORT signals in
        # pass 1; must appear regardless of std-helper usage)
        for line in self._main_imports:
            yield line
        yield ""
        mod = node.parent
        is_rest_only = isinstance(mod, Module) and module_is_rest_only(mod)
        if not is_rest_only:
            # table sentinel — shared across all dialects
            yield "class _UnmatchedTableRow:"
            yield "    pass"
            yield ""
            yield "UNMATCHED_TABLE_ROW = _UnmatchedTableRow()"
            yield ""
            # dialect-specific constants (BS4_FEATURES, FALLBACK_HTML_STR, ...)
            for line in self.EXTRA_UTILITIES:
                yield line
        # REST runtime (Ok/Err/TransportErr/ssc_parse_response)
        if isinstance(mod, Module) and module_has_rest(mod):
            for line in REST_UTILITIES:
                yield line
        # std section (inline helpers or `from ssc_std import ...`)
        result = super().visit_utilities(node, ctx)
        if result is not None:
            yield from result

    def visit_code_start_hook(
        self, node: CodeStartHook, ctx: ConverterContext
    ) -> VisitStream:
        return

    def visit_code_end_hook(
        self, node: CodeEndHook, ctx: ConverterContext
    ) -> VisitStream:
        return

    # TODO: AST: REMOVE Docstring nodes
    def visit_struct_docstring(
        self, node: StructDocstring, ctx: ConverterContext
    ) -> VisitStream:
        return

    def visit_error_response(
        self, node: ErrorResponse, ctx: ConverterContext
    ) -> VisitStream:
        # TODO: define the error-response contract.
        return

    # === types ===

    def visit_jsondef(
        self, node: JsonDef, ctx: ConverterContext
    ) -> VisitStream:
        name = to_pascal_case(node.name)
        yield f'{name}Json = TypedDict("{name}Json", {{'
        yield TRAVERSE
        yield "})"

    def visit_jsondef_field(
        self, node: JsonDefField, ctx: ConverterContext
    ) -> VisitStream:
        if node.type_info and node.type_info.skip:
            return
        # TypedDict not allowed aliases — not use `node.alias`
        name = node.name
        t = self._resolve_py_type(node.type_info)
        if node.type_info and node.type_info.omitempty:
            t = f"NotRequired[{t}]"
        yield f"{name!r}: {t},"

    def visit_typedef(
        self, node: TypeDef, ctx: ConverterContext
    ) -> VisitStream:
        name = to_pascal_case(node.name)
        match node.struct_type:
            # not allowed use type in rests
            case ST.REST:
                return
            case ST.DICT:
                # generate in typedef_field visitor
                yield TRAVERSE
            case ST.FLAT:
                yield f"{name}Type = List[str]"
                # skip child body
            case ST.ITEM:
                yield f'{name}Type = TypedDict("{name}Type", {{'
                yield TRAVERSE
                yield "})"
            case ST.LIST:
                yield f'{name}Type = TypedDict("{name}Type", {{'
                yield TRAVERSE
                yield "})"
            case ST.TABLE:
                yield f'{name}Type = TypedDict("{name}Type", {{'
                yield TRAVERSE
                yield "})"
            case _:
                # not reached
                raise Exception

    def visit_typedef_field(
        self, node: TypeDefField, ctx: ConverterContext
    ) -> VisitStream:
        if node.typedef.struct_type == ST.FLAT:
            return
        name = to_snake_case(node.name)
        t = self._resolve_py_type(node.type_info)
        if node.typedef.struct_type == ST.DICT:
            # DICT is a plain type alias (Dict[str, value_type]), not a
            # TypedDict body — emit the alias once (for the value field) and
            # skip the TypedDict field line entirely.
            if name == "value":
                typedef_name = to_pascal_case(node.typedef.name)
                yield f"{typedef_name}Type = Dict[str, {t}]"
            return
        yield f"{ctx.indent}{name!r}: {t},"

    # === struct ===

    def visit_struct(self, node: Struct, ctx: ConverterContext) -> VisitStream:
        name = to_pascal_case(node.name)
        yield f"class {name}:"
        if node.doc:
            i = ctx.deeper().indent
            yield f'{i}"""'
            yield [i + line for line in node.doc.splitlines()]
            yield f'{i}"""'
        yield TRAVERSE

    def visit_struct_rest(
        self, node: StructRest, ctx: ConverterContext
    ) -> VisitStream:
        # error subclasses (module-level, before class)
        yield emit_rest_error_subclasses(node)
        # result aliases (module-level, before class)
        aliases = emit_result_aliases(node)
        yield aliases
        if aliases:
            yield ""
        # class header
        name = to_pascal_case(node.name)
        yield f"class {name}:"
        # class docstring
        if node.doc:
            i = ctx.deeper().indent
            yield f'{i}"""'
            yield [i + line for line in node.doc.splitlines()]
            yield f'{i}"""'
        # dispatch_err staticmethod (first class member)
        yield emit_dispatch_err(node, ctx.deeper())
        # children (MethodRest, MethodFetch, ErrorResponse)
        yield TRAVERSE

    def visit_init(self, node: Init, ctx: ConverterContext) -> VisitStream:
        i, i2, i3 = (
            ctx.indent,
            ctx.deeper().indent,
            ctx.deeper().deeper().indent,
        )

        yield f"{i}def __init__(self, document: {self.INIT_ARG_TYPE}):"
        yield f"{i2}if isinstance(document, str):"
        yield f"{i3}self._doc = {self.INIT_FROM_STR_EXPR}"
        yield f"{i2}else:"
        yield f"{i3}self._doc = document"
        # init fields if defined
        for field in node.body:
            if not isinstance(field, InitField):
                continue
            name = to_snake_case(field.name)
            yield f"{i2}self._{name} = self._init_{name}(self._doc)"
        # Emit the _init_{name} method definitions at class-body level.
        # The framework's InitField special-case miscalculates indentation,
        # so we emit header + pipeline body manually.
        for field in node.body:
            if not isinstance(field, InitField):
                continue
            name = to_snake_case(field.name)
            t_arg = self._resolve_py_type(field.accept_type_info)
            t_ret = self._resolve_py_type(field.ret_type_info)
            yield f"{i}def _init_{name}(self, v: {t_arg}) -> {t_ret}:"
            yield self._emit_pipeline(field.body, ctx.deeper())

    def visit_init_field(
        self, node: InitField, ctx: ConverterContext
    ) -> VisitStream:
        name = to_snake_case(node.name)
        t_arg = self._resolve_py_type(node.accept_type_info)
        t_ret = self._resolve_py_type(node.ret_type_info)

        yield f"{ctx.indent}def _init_{name}(self, v: {t_arg}) -> {t_ret}:"
        yield TRAVERSE

    def visit_field(self, node: Field, ctx: ConverterContext) -> VisitStream:
        name = to_snake_case(node.name)
        t_arg = self._resolve_py_type(node.accept_type_info)
        t_ret = self._resolve_py_type(node.ret_type_info)
        # sentinel specific type
        if node.struct.type == ST.TABLE:
            t_ret = f"Union[{t_ret}, _UnmatchedTableRow]"
        yield f"{ctx.indent}def _parse_{name}(self, v: {t_arg}) -> {t_ret}:"
        yield TRAVERSE

    def visit_key(self, node: Key, ctx: ConverterContext) -> VisitStream:
        name = "key"
        t_arg = self._resolve_py_type(node.accept_type_info)
        t_ret = self._resolve_py_type(node.ret_type_info)  # string expected
        yield f"{ctx.indent}def _parse_{name}(self, v: {t_arg}) -> {t_ret}:"
        yield TRAVERSE

    def visit_value(self, node: Value, ctx: ConverterContext) -> VisitStream:
        name = "value"
        t_arg = self._resolve_py_type(node.accept_type_info)
        t_ret = self._resolve_py_type(node.ret_type_info)  # string expected
        yield f"{ctx.indent}def _parse_{name}(self, v: {t_arg}) -> {t_ret}:"
        yield TRAVERSE

    def visit_table_config(
        self, node: TableConfig, ctx: ConverterContext
    ) -> VisitStream:
        name = "_table_config"
        t_arg = self._resolve_py_type(node.accept_type_info)
        t_ret = self._resolve_py_type(
            node.ret_type_info
        )  # element or Union[element, parser] expected
        yield f"{ctx.indent}def {name}(self, v: {t_arg}) -> {t_ret}:"
        yield TRAVERSE

    def visit_table_match_key(
        self, node: TableMatchKey, ctx: ConverterContext
    ) -> VisitStream:
        name = "_table_match_key"
        t_arg = self._resolve_py_type(node.accept_type_info)
        t_ret = self._resolve_py_type(node.ret_type_info)  # str expected
        yield f"{ctx.indent}def {name}(self, v: {t_arg}) -> {t_ret}:"
        yield TRAVERSE

    def visit_table_rows(
        self, node: TableRows, ctx: ConverterContext
    ) -> VisitStream:
        name = "_table_rows"
        t_arg = self._resolve_py_type(node.accept_type_info)
        t_ret = self._resolve_py_type(
            node.ret_type_info
        )  # DOCUMENT_ARRAY_TYPE expected
        yield f"{ctx.indent}def {name}(self, v: {t_arg}) -> {t_ret}:"
        yield TRAVERSE

    def visit_pre_validate(
        self, node: PreValidate, ctx: ConverterContext
    ) -> VisitStream:
        name = "_pre_validate"
        t_arg = self._resolve_py_type(node.accept_type_info)
        t_ret = self._resolve_py_type(node.ret_type_info)  # None expected
        yield f"{ctx.indent}def {name}(self, v: {t_arg}) -> {t_ret}:"
        yield TRAVERSE

    def visit_check_method(
        self, node: CheckMethod, ctx: ConverterContext
    ) -> VisitStream:
        name = to_snake_case(node.name)
        t_ret = self._resolve_py_type(node.ret_type_info)  # bool expected
        yield f"{ctx.indent}def {name}(self) -> {t_ret}:"
        # API simplify: v = self._doc
        yield f"{ctx.indent * 2}{ctx.var_name} = self._doc"
        yield TRAVERSE

    def visit_split_doc(
        self, node: SplitDoc, ctx: ConverterContext
    ) -> VisitStream:
        name = "_split_doc"
        t_arg = self._resolve_py_type(node.accept_type_info)
        t_ret = self._resolve_py_type(
            node.ret_type_info
        )  # DOCUMENT_ARRAY_TYPE expected
        yield f"{ctx.indent}def {name}(self, v: {t_arg}) -> {t_ret}:"
        yield TRAVERSE

    def visit_start_parse(
        self, node: StartParse, ctx: ConverterContext
    ) -> VisitStream:
        name = to_pascal_case(node.struct.name)
        t = self._resolve_py_start_parse_t_ret(node.struct, name)
        # 1. header
        yield f"{ctx.indent}def parse(self) -> {t}:"
        # 2. body
        i2 = ctx.deeper().indent
        i3 = ctx.deeper().deeper().indent
        # 2.1 call pre-validate first
        if node.use_pre_validate:
            yield f"{i2}self._pre_validate(self._doc)"

        # 2.2 parse strategies
        match node.struct.type:
            case ST.ITEM:
                yield f"{i2}return {{"
                for field in node.fields:
                    field_name = to_snake_case(field.name)
                    yield f"{i3}{field_name!r}: self._parse_{field_name}(self._doc),"
                yield f"{i3}}}"
            case ST.LIST:
                yield f"{i2}return [{{"
                for field in node.fields:
                    field_name = to_snake_case(field.name)
                    yield f"{i2}{field_name!r}: self._parse_{field_name}(i),"
                yield f"{i3}}} for i in self._split_doc(self._doc)]"
            case ST.DICT:
                yield f"{i2}return {{"
                yield f"{i3}self._parse_key(i): self._parse_value(i) for i in self._split_doc(self._doc)"
                yield f"{i2}}}"
            case ST.FLAT:
                yield f"{i2}_result: List[str] = []"
                for field in node.fields:
                    field_name = to_snake_case(field.name)
                    # string or string[]
                    if field.ret_type_info.is_array:
                        yield f"{i2}_result.extend(self._parse_{field_name}(self._doc))"
                    else:
                        yield f"{i2}_result.append(self._parse_{field_name}(self._doc))"
                if node.struct.keep_order:
                    yield f"{i2}return list(dict.fromkeys(_result))"
                yield f"{i2}return list(set(_result))"
            case ST.TABLE:
                i4 = ctx.deeper().deeper().deeper().indent
                yield f"{i2}_result: {name}Type = {{}}"
                yield f"{i2}_table = self._table_config(self._doc)"
                yield f"{i2}for _row in self._table_rows(_table):"
                for field in node.fields:
                    field_name = to_snake_case(field.name)
                    yield f"{i3}_{field_name} = self._parse_{field_name}(_row)"
                    yield f"{i3}if _{field_name} != UNMATCHED_TABLE_ROW and {field_name!r} not in _result:"
                    yield f"{i4}_result[{field_name!r}] = _{field_name}"
                    yield f"{i4}continue"
                yield f"{i2}return _result"

    # === REST / fetch: request argument helpers ===

    _DICT_KWARGS = (
        ("headers", "_headers"),
        ("cookies", "_cookies"),
        ("params", "_params"),
    )

    def _request_spec(self, node: MethodBase) -> RequestSpec:
        """Build and normalize the RequestSpec from a node's http_request."""
        http = node.http_request
        return normalize_placeholder_names(
            RequestSpec(
                method=http.method,
                url=http.url,
                headers=dict(http.headers),
                cookies=dict(http.cookies),
                params=dict(http.params),
                body_kind=http.body_kind,
                body=http.body,
            ),
            to_snake_case,
        )

    def _placeholder_params(self, spec: RequestSpec) -> str:
        """Render the '', *, name: type, ...'' keyword-arg suffix."""
        if not spec.placeholders:
            return ""
        parts: list[str] = []
        for ph in sorted(spec.placeholders, key=lambda p: p.is_optional):
            t = PH_PY_TYPES[ph.type_name]
            if ph.is_array:
                t = f"List[{t}]"
            parts.append(
                f"{ph.name}: Optional[{t}] = None"
                if ph.is_optional
                else f"{ph.name}: {t}"
            )
        return ", *, " + ", ".join(parts)

    def _pre_lines(self, spec: RequestSpec, indent: str) -> list[str]:
        """Dict builders for headers/cookies/params emitted before the call."""
        lines: list[str] = []
        for attr, varname in self._DICT_KWARGS:
            d = getattr(spec, attr)
            if d and dict_needs_builder(d):
                lines.extend(emit_dict_builder(varname, d, indent))
        return lines

    def _request_call(
        self,
        spec: RequestSpec,
        await_kw: str,
        line_indent: str,
        arg_indent: str,
    ) -> list[str]:
        """Render the ``_resp = await client.request(...)`` block."""
        lines = [
            f"{line_indent}_resp = {await_kw}client.request(",
            f"{arg_indent}{spec.method!r},",
            f"{arg_indent}{render_value(spec.url)},",
        ]
        for attr, varname in self._DICT_KWARGS:
            d = getattr(spec, attr)
            if not d:
                continue
            ref = varname if dict_needs_builder(d) else render_dict(d)
            lines.append(f"{arg_indent}{attr}={ref},")
        body_result = render_body(spec)
        if body_result:
            lines.append(f"{arg_indent}{body_result[0]}={body_result[1]},")
        lines.append(f"{line_indent})")
        return lines

    # === REST / fetch: visitors ===

    def visit_method_fetch(
        self, node: MethodFetch, ctx: ConverterContext
    ) -> VisitStream:
        assert node.parent is not None
        spec = self._request_spec(node)
        struct_name = to_pascal_case(node.parent.name)  # type: ignore[attr-defined]
        suffix = ("_" + to_snake_case(node.name)) if node.name else ""
        ph_params = self._placeholder_params(spec)

        i1 = ctx.indent
        i2 = i1 + ctx.indent_char
        i3 = i2 + ctx.indent_char

        # response-path post-processing (shared by sync & async)
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

        # --- sync ---
        yield f"{i1}@classmethod"
        yield f'{i1}def fetch{suffix}(cls, client: httpx.Client{ph_params}) -> "{struct_name}":'
        yield self._pre_lines(spec, i2)
        yield self._request_call(spec, "", i2, i3)
        yield post_lines
        yield ""
        # --- async ---
        yield f"{i1}@classmethod"
        yield f'{i1}async def async_fetch{suffix}(cls, client: httpx.AsyncClient{ph_params}) -> "{struct_name}":'
        yield self._pre_lines(spec, i2)
        yield self._request_call(spec, "await ", i2, i3)
        yield post_lines

    def visit_method_rest(
        self, node: MethodRest, ctx: ConverterContext
    ) -> VisitStream:
        spec = self._request_spec(node)
        method_name = to_snake_case(node.name) if node.name else "fetch"
        ret_type = result_alias_name(node.name)
        ok_value = "_body" if node.response_schema else "None"
        ph_params = self._placeholder_params(spec)

        i1 = ctx.indent
        i2 = i1 + ctx.indent_char
        i3 = i2 + ctx.indent_char
        i4 = i3 + ctx.indent_char

        doc_line = f'{i2}"""{node.doc}"""' if node.doc else None

        # post-request dispatch (shared by sync & async)
        dispatch_lines = [
            f"{i2}except httpx.HTTPError as _exc:",
            f"{i3}return TransportErr(cause=repr(_exc))",
            f"{i2}_status, _headers, _body = ssc_parse_response(_resp)",
            f"{i2}_err = cls.ssc_dispatch_err(_status, _headers, _body)",
            f"{i2}if _err is not None:",
            f"{i3}return _err",
            f"{i2}return Ok(status=_status, headers=_headers, value={ok_value})",
        ]

        # --- sync ---
        yield f"{i1}@classmethod"
        yield f"{i1}def {method_name}(cls, client: httpx.Client{ph_params}) -> {ret_type}:"
        if doc_line:
            yield doc_line
        yield self._pre_lines(spec, i2)
        yield f"{i2}try:"
        yield self._request_call(spec, "", i3, i4)
        yield dispatch_lines
        yield ""
        # --- async ---
        yield f"{i1}@classmethod"
        yield f"{i1}async def async_{method_name}(cls, client: httpx.AsyncClient{ph_params}) -> {ret_type}:"
        if doc_line:
            yield doc_line
        yield self._pre_lines(spec, i2)
        yield f"{i2}try:"
        yield self._request_call(spec, "await ", i3, i4)
        yield dispatch_lines

    # === string ===

    def visit_trim(self, node: Trim, ctx: ConverterContext) -> VisitStream:
        value = "" if node.substr == "" else repr(node.substr)
        if node.is_array:
            yield f"{ctx.indent}{ctx.nxt} = [i.strip({value}) for i in {ctx.prv}]"
        else:
            yield f"{ctx.indent}{ctx.nxt} = {ctx.prv}.strip({value})"

    def visit_l_trim(self, node: Ltrim, ctx: ConverterContext) -> VisitStream:
        value = "" if node.substr == "" else repr(node.substr)
        if node.is_array:
            yield f"{ctx.indent}{ctx.nxt} = [i.lstrip({value}) for i in {ctx.prv}]"
        else:
            yield f"{ctx.indent}{ctx.nxt} = {ctx.prv}.lstrip({value})"

    def visit_r_trim(self, node: Rtrim, ctx: ConverterContext) -> VisitStream:
        value = "" if node.substr == "" else repr(node.substr)
        if node.is_array:
            yield f"{ctx.indent}{ctx.nxt} = [i.rstrip({value}) for i in {ctx.prv}]"
        else:
            yield f"{ctx.indent}{ctx.nxt} = {ctx.prv}.rstrip({value})"

    def visit_rm_prefix(
        self, node: RmPrefix, ctx: ConverterContext
    ) -> VisitStream:
        value = repr(node.substr)
        if node.is_array:
            yield f"{ctx.indent}{ctx.nxt} = [i.removeprefix({value}) for i in {ctx.prv}]"
        else:
            yield f"{ctx.indent}{ctx.nxt} = {ctx.prv}.removeprefix({value})"

    def visit_rm_suffix(
        self, node: RmSuffix, ctx: ConverterContext
    ) -> VisitStream:
        value = repr(node.substr)
        if node.is_array:
            yield f"{ctx.indent}{ctx.nxt} = [i.removesuffix({value}) for i in {ctx.prv}]"
        else:
            yield f"{ctx.indent}{ctx.nxt} = {ctx.prv}.removesuffix({value})"

    def visit_rm_prefix_suffix(
        self, node: RmPrefixSuffix, ctx: ConverterContext
    ) -> VisitStream:
        value = repr(node.substr)
        if node.is_array:
            yield f"{ctx.indent}{ctx.nxt} = [i.removeprefix({value}).removesuffix({value}) for i in {ctx.prv}]"
        else:
            yield f"{ctx.indent}{ctx.nxt} = {ctx.prv}.removeprefix({value}).removesuffix({value})"

    def visit_format(self, node: Fmt, ctx: ConverterContext) -> VisitStream:
        tmpl = repr(node.template.replace("{{}}", "{}", 1))
        if node.is_array:
            yield f"{ctx.indent}{ctx.nxt} = [{tmpl}.format(i) for i in {ctx.prv}]"
        else:
            yield f"{ctx.indent}{ctx.nxt} = {tmpl}.format({ctx.prv})"

    def visit_repl(self, node: Repl, ctx: ConverterContext) -> VisitStream:
        old = repr(node.old)
        new = repr(node.new)
        if node.is_array:
            yield f"{ctx.indent}{ctx.nxt} = [i.replace({old}, {new}) for i in {ctx.prv}]"
        else:
            yield f"{ctx.indent}{ctx.nxt} = {ctx.prv}.replace({old}, {new})"

    def visit_repl_map(
        self, node: ReplMap, ctx: ConverterContext
    ) -> VisitStream:
        repl_dict = repr(node.replacements)
        yield STD(
            "std_repl_map",
            code="""
                def std_repl_map(s, replacements):
                    for old, new in replacements.items():
                        s = s.replace(old, new)
                    return s
            """,
        )
        if node.is_array:
            yield f"{ctx.indent}{ctx.nxt} = [std_repl_map(i, {repl_dict}) for i in {ctx.prv}]"
        else:
            yield f"{ctx.indent}{ctx.nxt} = std_repl_map({ctx.prv}, {repl_dict})"

    def visit_lower(self, node: Lower, ctx: ConverterContext) -> VisitStream:
        if node.is_array:
            yield f"{ctx.indent}{ctx.nxt} = [i.lower() for i in {ctx.prv}]"
        else:
            yield f"{ctx.indent}{ctx.nxt} = {ctx.prv}.lower()"

    def visit_upper(self, node: Upper, ctx: ConverterContext) -> VisitStream:
        if node.is_array:
            yield f"{ctx.indent}{ctx.nxt} = [i.upper() for i in {ctx.prv}]"
        else:
            yield f"{ctx.indent}{ctx.nxt} = {ctx.prv}.upper()"

    def visit_split(self, node: Split, ctx: ConverterContext) -> VisitStream:
        sep = repr(node.sep)
        yield f"{ctx.indent}{ctx.nxt} = {ctx.prv}.split({sep})"

    def visit_join(self, node: Join, ctx: ConverterContext) -> VisitStream:
        sep = repr(node.sep)
        yield f"{ctx.indent}{ctx.nxt} = {sep}.join({ctx.prv})"

    def visit_norm_space(
        self, node: NormalizeSpace, ctx: ConverterContext
    ) -> VisitStream:
        if node.is_array:
            yield f"{ctx.indent}{ctx.nxt} = [' '.join(i.split()) if i else '' for i in {ctx.prv}]"
        else:
            yield f"{ctx.indent}{ctx.nxt} = ' '.join({ctx.prv}.split()) if {ctx.prv} else ''"

    def visit_unescape(
        self, node: Unescape, ctx: ConverterContext
    ) -> VisitStream:
        yield STD(
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
            yield f"{ctx.indent}{ctx.nxt} = [std_unescape_text(i) for i in {ctx.prv}]"
        else:
            yield f"{ctx.indent}{ctx.nxt} = std_unescape_text({ctx.prv})"

    # === regex ===

    def visit_re(self, node: Re, ctx: ConverterContext) -> VisitStream:
        pattern = repr(node.pattern)
        yield f"{ctx.indent}{ctx.nxt} = re.search({pattern}, {ctx.prv})[1]"

    def visit_re_all(self, node: ReAll, ctx: ConverterContext) -> VisitStream:
        pattern = repr(node.pattern)
        yield f"{ctx.indent}{ctx.nxt} = re.findall({pattern}, {ctx.prv})"

    def visit_re_sub(self, node: ReSub, ctx: ConverterContext) -> VisitStream:
        pattern = repr(node.pattern)
        repl = repr(node.repl)
        if node.is_array:
            yield f"{ctx.indent}{ctx.nxt} = [re.sub({pattern}, {repl}, i) for i in {ctx.prv}]"
        else:
            yield f"{ctx.indent}{ctx.nxt} = re.sub({pattern}, {repl}, {ctx.prv})"

    # === array ===

    def visit_index(self, node: Index, ctx: ConverterContext) -> VisitStream:
        # py supports negative indexes, translate as is
        yield f"{ctx.indent}{ctx.nxt} = {ctx.prv}[{node.i}]"

    def visit_slice(self, node: Slice, ctx: ConverterContext) -> VisitStream:
        yield f"{ctx.indent}{ctx.nxt} = {ctx.prv}[{node.start}:{node.end}]"

    def visit_len(self, node: Len, ctx: ConverterContext) -> VisitStream:
        yield f"{ctx.indent}{ctx.nxt} = len({ctx.prv})"

    def visit_unique(self, node: Unique, ctx: ConverterContext) -> VisitStream:
        if node.keep_order:
            # py3.7+ dict preserves insertion order
            yield f"{ctx.indent}{ctx.nxt} = list(dict.fromkeys({ctx.prv}))"
        else:
            yield f"{ctx.indent}{ctx.nxt} = list(set({ctx.prv}))"

    # === casts ===

    def visit_to_int(self, node: ToInt, ctx: ConverterContext) -> VisitStream:
        if node.is_array:
            yield f"{ctx.indent}{ctx.nxt} = [int(i) for i in {ctx.prv}]"
        else:
            yield f"{ctx.indent}{ctx.nxt} = int({ctx.prv})"

    def visit_to_float(
        self, node: ToFloat, ctx: ConverterContext
    ) -> VisitStream:
        if node.is_array:
            yield f"{ctx.indent}{ctx.nxt} = [float(i) for i in {ctx.prv}]"
        else:
            yield f"{ctx.indent}{ctx.nxt} = float({ctx.prv})"

    def visit_jsonify(
        self, node: Jsonify, ctx: ConverterContext
    ) -> VisitStream:
        if node.path:
            parts = jsonify_path_to_segments(node.path)
            path = ""
            for part in parts:
                # current version not support negative index; index starts from 0
                if part.isdigit():
                    path += f"[{part}]"
                else:
                    path += f"[{part}]"
            yield f"{ctx.indent}{ctx.nxt} = json.loads({ctx.prv}){path}"
        else:
            yield f"{ctx.indent}{ctx.nxt} = json.loads({ctx.prv})"

    def visit_nested(self, node: Nested, ctx: ConverterContext) -> VisitStream:
        struct_name = to_pascal_case(node.struct_name)
        yield f"{ctx.indent}{ctx.nxt} = {struct_name}({ctx.prv}).parse()"

    def visit_self(self, node: Self, ctx: ConverterContext) -> VisitStream:
        name = to_snake_case(node.name)
        yield f"{ctx.indent}{ctx.nxt} = self._{name}"

    # === control ===

    def visit_return(self, node: Return, ctx: ConverterContext) -> VisitStream:
        # standard: PreValidate always returns null/None
        if isinstance(node.parent, PreValidate):
            yield f"{ctx.indent}return"
            return
        # Suppress trailing Return after Fallback: visit_fallback emits its own
        # `return` inside the try-block.
        body = getattr(node.parent, "body", None) or []
        try:
            idx = body.index(node)
        except ValueError:
            idx = -1
        if idx > 0 and isinstance(body[idx - 1], Fallback):
            return
        yield f"{ctx.indent}return {ctx.prv}"

    def visit_fallback(
        self, node: Fallback, ctx: ConverterContext
    ) -> VisitStream:
        inner = ctx.indent + ctx.indent_char
        last_idx = ctx.index + len(node.body)
        last_var = (
            ctx.var_name if last_idx == 0 else f"{ctx.var_name}{last_idx}"
        )
        yield f"{ctx.indent}try:"
        yield TRAVERSE
        yield [
            f"{inner}return {last_var}",
            f"{ctx.indent}except Exception:",
            f"{inner}return {node.value!r}",
        ]

    def visit_filter(self, node: Filter, ctx: ConverterContext) -> VisitStream:
        yield f"{ctx.indent}{ctx.nxt} = [i for i in {ctx.prv} if "
        yield TRAVERSE
        yield f"{ctx.indent}]"

    def visit_assert(self, node: Assert, ctx: ConverterContext) -> VisitStream:
        yield [
            f"{ctx.indent}i = {ctx.prv}",
            f"{ctx.indent}assert (",
        ]
        yield TRAVERSE
        yield [ctx.deeper().indent + ")", f"{ctx.indent}{ctx.nxt} = {ctx.prv}"]

    def visit_match(self, node: Match, ctx: ConverterContext) -> VisitStream:
        yield [
            f"{ctx.indent}i = self._table_match_key({ctx.prv})",
            f"{ctx.indent}if not (",
        ]
        yield TRAVERSE
        yield [
            f"{ctx.indent}):",
            f"{ctx.deeper().indent}return UNMATCHED_TABLE_ROW",
            f"{ctx.indent}{ctx.nxt} = self._parse_value({ctx.prv})",
        ]

    # === logic ===

    def visit_logic_and(
        self, node: LogicAnd, ctx: ConverterContext
    ) -> VisitStream:
        if ctx.index == 0:
            yield f"{ctx.indent}("
            yield TRAVERSE
            yield f"{ctx.indent})"
        else:
            yield f"{ctx.indent}and ("
            yield TRAVERSE
            yield f"{ctx.indent})"

    def visit_logic_or(
        self, node: LogicOr, ctx: ConverterContext
    ) -> VisitStream:
        if ctx.index == 0:
            yield f"{ctx.indent}("
            yield TRAVERSE
            yield f"{ctx.indent})"
        else:
            yield f"{ctx.indent}or ("
            yield TRAVERSE
            yield f"{ctx.indent})"

    def visit_logic_not(
        self, node: LogicNot, ctx: ConverterContext
    ) -> VisitStream:
        if ctx.index == 0:
            yield f"{ctx.indent}not ("
            yield TRAVERSE
            yield f"{ctx.indent})"
        else:
            yield f"{ctx.indent}and not ("
            yield TRAVERSE
            yield f"{ctx.indent})"

    # === string-level / count / regex predicates (dialect-agnostic) ===

    def visit_predicate_contains(
        self, node: PredContains, ctx: ConverterContext
    ) -> VisitStream:
        vals = repr(node.values)
        yield self._pred_line(ctx, f"any(v in i for v in {vals})")

    def visit_predicate_eq(
        self, node: PredEq, ctx: ConverterContext
    ) -> VisitStream:
        values = node.values
        if len(values) == 1 and isinstance(values[0], int):
            cond = f"len(i) == {values[0]}"
        else:
            cond = f"any(i == v for v in {values!r})"
        yield self._pred_line(ctx, cond)

    def visit_predicate_ne(
        self, node: PredNe, ctx: ConverterContext
    ) -> VisitStream:
        values = node.values
        if len(values) == 1 and isinstance(values[0], int):
            cond = f"len(i) != {values[0]}"
        else:
            cond = f"all(i != v for v in {values!r})"
        yield self._pred_line(ctx, cond)

    def visit_predicate_starts(
        self, node: PredStarts, ctx: ConverterContext
    ) -> VisitStream:
        vals = repr(node.values)
        yield self._pred_line(ctx, f"i.startswith({vals})")

    def visit_predicate_ends(
        self, node: PredEnds, ctx: ConverterContext
    ) -> VisitStream:
        vals = repr(node.values)
        yield self._pred_line(ctx, f"i.endswith({vals})")

    def visit_pred_count_range(
        self, node: PredCountRange, ctx: ConverterContext
    ) -> VisitStream:
        yield self._pred_line(ctx, f"{node.start} < len(i) < {node.end}")

    def visit_predicate_count_eq(
        self, node: PredCountEq, ctx: ConverterContext
    ) -> VisitStream:
        yield self._pred_line(ctx, f"len(i) == {node.value}")

    def visit_predicate_count_ge(
        self, node: PredCountGe, ctx: ConverterContext
    ) -> VisitStream:
        yield self._pred_line(ctx, f"len(i) >= {node.value}")

    def visit_predicate_count_gt(
        self, node: PredCountGt, ctx: ConverterContext
    ) -> VisitStream:
        yield self._pred_line(ctx, f"len(i) > {node.value}")

    def visit_predicate_count_le(
        self, node: PredCountLe, ctx: ConverterContext
    ) -> VisitStream:
        yield self._pred_line(ctx, f"len(i) <= {node.value}")

    def visit_predicate_count_lt(
        self, node: PredCountLt, ctx: ConverterContext
    ) -> VisitStream:
        yield self._pred_line(ctx, f"len(i) < {node.value}")

    def visit_predicate_count_ne(
        self, node: PredCountNe, ctx: ConverterContext
    ) -> VisitStream:
        yield self._pred_line(ctx, f"len(i) != {node.value}")

    def visit_predicate_re(
        self, node: PredRe, ctx: ConverterContext
    ) -> VisitStream:
        pat = repr(node.pattern)
        yield self._pred_line(ctx, f"bool(re.search({pat}, i))")

    def visit_predicate_re_any(
        self, node: PredReAny, ctx: ConverterContext
    ) -> VisitStream:
        pat = repr(node.pattern)
        yield self._pred_line(ctx, f"any(bool(re.search({pat}, j)) for j in i)")

    def visit_predicate_re_all(
        self, node: PredReAll, ctx: ConverterContext
    ) -> VisitStream:
        pat = repr(node.pattern)
        yield self._pred_line(ctx, f"all(bool(re.search({pat}, j)) for j in i)")
