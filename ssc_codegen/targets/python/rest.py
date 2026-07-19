"""Python REST/fetch codegen — pure functions for MethodFetch, MethodRest,
ResultVariantDef, ResultAliasDef, MatcherListDef AST nodes.

Called by PythonVisitor via thin delegate methods.  The HTTP library strategy
(httpx/aiohttp/requests) is passed as a parameter where needed.
"""

from __future__ import annotations

import json
import re
from typing import cast

from ssc_codegen.ast import (
    MatcherListDef,
    MethodFetch,
    MethodRest,
    Module,
    PlaceholderSpec,
    PlaceholderTemplate,
    ResultAliasDef,
    ResultVariantDef,
    StructBase,
)
from ssc_codegen.ast.struct import RequestHttp
from ssc_codegen.naming import to_pascal_case, to_snake_case
from ssc_codegen.request_spec import validate_json_body
from ssc_codegen.targets.python.http_libs.base import HttpLibStrategy
from ssc_codegen.traversal.context import WalkContext
from ssc_codegen.traversal.utils import (
    dict_needs_builder,
    module_has_rest,
    module_is_rest_only,
)


# ===========================================================================
# Placeholder / Template rendering (pure functions)
# ===========================================================================

_STYLE_SEPARATOR: dict[str, str] = {"csv": ",", "pipe": "|", "space": " "}

PH_PY_TYPES = {"str": "str", "int": "int", "float": "float", "bool": "bool"}


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


# ===========================================================================
# Condition lambda rendering
# ===========================================================================


def _py_path_expr(body_var: str, path: str) -> str:
    expr = body_var
    for seg in path.split("."):
        if seg.isdigit():
            expr += f"[{seg}]"
        else:
            expr += f".get({seg!r})"
    return expr


def render_py_condition_lambda(
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
# Runtime export names
# ===========================================================================

_RUNTIME_HTML_EXPORT_NAMES: list[str] = [
    "UNMATCHED_TABLE_ROW",
    "UnmatchedTableRow",
]

_RUNTIME_REST_EXPORT_NAMES: list[str] = [
    "Ok",
    "Err",
    "UnknownErr",
    "TransportErr",
    "ErrMatcher",
    "ssc_rest_call",
    "ssc_rest_call_async",
]


def runtime_export_names(
    module: Module, *, need_fallback: bool = False
) -> list[str]:
    """Compute the list of names the parser file must import from the runtime.

    Selection rules:
    - REST-only module: just REST names (``ssc_dispatch_err`` is internal to
      ``ssc_rest_call`` — never imported by the parser).
    - HTML module (has any non-rest struct): table markers are always
      imported (cheap, may be referenced by visit_field/visit_match).
    - HTML module whose DomSpelling declares ``FALLBACK_HTML_STR`` in
      ``extra_utilities``: also import that constant.
    - Module with REST structs: also import REST names.
    """
    names: list[str] = []
    if not module_is_rest_only(module):
        names.extend(_RUNTIME_HTML_EXPORT_NAMES)
        if need_fallback:
            names.append("FALLBACK_HTML_STR")
    if module_has_rest(module):
        names.extend(_RUNTIME_REST_EXPORT_NAMES)
    return names


# ===========================================================================
# Placeholder parameter signature
# ===========================================================================

_DICT_KWARGS = (
    ("headers", "_headers"),
    ("cookies", "_cookies"),
    ("params", "_params"),
)


def placeholder_params(http: RequestHttp) -> str:
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


# ===========================================================================
# Shared kwargs builder
# ===========================================================================


def _build_kwargs(
    spec: RequestHttp, i2: str, i3: str, include_method_url: bool
) -> tuple[list[str], list[str]]:
    """Build (pre_lines, kwargs_lines) for request call.

    include_method_url=True for fetch (client.request(method, url, ...)).
    include_method_url=False for rest (ssc_rest_call(client, matchers, method, url, ...)).
    """
    pre_lines: list[str] = []
    kwargs_lines: list[str] = []
    if include_method_url:
        kwargs_lines.append(f"{i3}{spec.method!r},")
        kwargs_lines.append(f"{i3}{render_value(spec.url)},")
    for attr, varname in _DICT_KWARGS:
        d = getattr(spec, attr)
        if not d:
            continue
        if dict_needs_builder(d):
            pre_lines.extend(emit_dict_builder(varname, d, i2))
            kwargs_lines.append(f"{i3}{attr}={varname},")
        else:
            kwargs_lines.append(f"{i3}{attr}={render_dict(d)},")
    body_result = render_body(spec)
    if body_result:
        kwargs_lines.append(f"{i3}{body_result[0]}={body_result[1]},")
    return pre_lines, kwargs_lines


# ===========================================================================
# Emit functions (called by PythonVisitor)
# ===========================================================================


def emit_method_fetch(
    node: MethodFetch, ctx: WalkContext, http: HttpLibStrategy
) -> list[str]:
    spec = node.http_request.with_renamed_placeholders(to_snake_case)
    assert node.parent is not None
    struct_name = to_pascal_case(cast(StructBase, node.parent).name)
    suffix = ("_" + to_snake_case(node.name)) if node.name else ""
    ph_params = placeholder_params(spec)

    i1 = ctx.indent
    i2 = i1 + ctx.indent_char
    i3 = i2 + ctx.indent_char

    pre_lines, kwargs_lines = _build_kwargs(
        spec, i2, i3, include_method_url=True
    )

    post_lines: list[str] = [f"{i2}_resp.raise_for_status()"]
    if node.response_path:
        accessor = "".join(f"[{p!r}]" for p in node.response_path.split("."))
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
        f'{i1}def fetch{suffix}(cls, client: {http.sync_client_type}{ph_params}) -> "{struct_name}":'
    )
    lines.extend(pre_lines)
    lines.extend([f"{i2}_resp = client.request(", *kwargs_lines, f"{i2})"])
    lines.extend(post_lines)
    lines.append("")

    lines.append(f"{i1}@classmethod")
    lines.append(
        f'{i1}async def async_fetch{suffix}(cls, client: {http.async_client_type}{ph_params}) -> "{struct_name}":'
    )
    lines.extend(pre_lines)
    lines.extend(
        [f"{i2}_resp = await client.request(", *kwargs_lines, f"{i2})"]
    )
    lines.extend(post_lines)
    return lines


def emit_method_rest(
    node: MethodRest, ctx: WalkContext, http: HttpLibStrategy
) -> list[str]:
    spec = node.http_request.with_renamed_placeholders(to_snake_case)
    struct = node.parent
    assert isinstance(struct, StructBase)
    method_name = to_snake_case(node.name) if node.name else "fetch"
    ret_type = node.result_alias_name or "None"
    ph_params = placeholder_params(spec)
    matchers_var = f"_{to_snake_case(struct.name)}_matchers"

    i1 = ctx.indent
    i2 = i1 + ctx.indent_char
    i3 = i2 + ctx.indent_char

    doc_line = f'{i2}"""{node.doc}"""' if node.doc else None

    pre_lines, kwargs_lines = _build_kwargs(
        spec, i2, i3, include_method_url=False
    )

    void_kwarg: list[str] = []
    if not node.response_schema:
        void_kwarg = [f"{i3}value_fn=lambda _: None,"]

    def _body(fn_name: str, await_kw: str) -> list[str]:
        body: list[str] = []
        if doc_line:
            body.append(doc_line)
        body.extend(pre_lines)
        # Wrap in cast(): ssc_rest_call returns Union[Ok[_T], Err] (Err
        # base — it cannot know the specific Err subclasses that the
        # heterogeneous matchers list will produce at runtime). The
        # parser-declared Result alias narrows to the precise union
        # (Err400 | UnknownErr | TransportErr | ...). cast() documents
        # this intent at the call site without suppressing mypy via
        # ``# type: ignore``; the wrapping method's return type is the
        # stable monad consumers see.
        body.append(f"{i2}return cast({ret_type}, {await_kw}{fn_name}(")
        body.append(
            f"{i3}client, {matchers_var}, {spec.method!r},"
            f" {render_value(spec.url)},"
        )
        body.extend(void_kwarg)
        body.extend(kwargs_lines)
        body.append(f"{i2}))")
        return body

    lines: list[str] = []
    lines.append(f"{i1}@classmethod")
    lines.append(
        f"{i1}def {method_name}(cls, client: {http.sync_client_type}{ph_params}) -> {ret_type}:"
    )
    lines.extend(_body("ssc_rest_call", ""))
    lines.append("")

    lines.append(f"{i1}@classmethod")
    lines.append(
        f"{i1}async def async_{method_name}(cls, client: {http.async_client_type}{ph_params}) -> {ret_type}:"
    )
    lines.extend(_body("ssc_rest_call_async", "await "))
    return lines


def emit_result_variant_def(node: ResultVariantDef) -> list[str]:
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


def emit_result_alias_def(node: ResultAliasDef) -> list[str]:
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


def emit_matcher_list_def(node: MatcherListDef) -> list[str]:
    var = f"_{to_snake_case(node.struct_name)}_matchers"
    lines = [f"{var}: list[ErrMatcher] = ["]
    for e in node.entries:
        check = render_py_condition_lambda(e.required_keys, e.conditions)
        check_arg = check if check else "None"
        lines.append(
            f"    ErrMatcher({e.status}, {check_arg}, {e.factory_name}),"
        )
    lines.append("]")
    return lines
