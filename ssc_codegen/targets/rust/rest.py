"""Rust REST and HTTP transport codegen for ``MethodFetch`` and ``MethodRest``.

Implements asynchronous transport using ``reqwest``:
- Placeholders in URL, query parameters, headers, cookies, and body.
- Async ``fetch`` associated methods returning ``Result<Self, rt::SscError>``.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

from ssc_codegen.ast import (
    MatcherListDef,
    MethodFetch,
    MethodRest,
    PlaceholderSpec,
    PlaceholderTemplate,
    ResultAliasDef,
    ResultVariantDef,
    StructBase,
    StructRest,
)
from ssc_codegen.naming import to_pascal_case, to_snake_case
from ssc_codegen.request_spec import parse_json_template
from ssc_codegen.symbols import RUST_RESERVED
from ssc_codegen.traversal.context import WalkContext

if TYPE_CHECKING:
    from ssc_codegen.ast.struct import RequestHttp

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


def rust_ph_type(ph: PlaceholderSpec) -> str:
    """Map a `PlaceholderSpec` to its idiomatic Rust parameter type."""
    if ph.is_array:
        if ph.type_name == "int":
            elem = "i64"
        elif ph.type_name == "float":
            elem = "f64"
        elif ph.type_name == "bool":
            elem = "bool"
        else:
            elem = "&str"
        base = f"&[{elem}]"
        return f"Option<{base}>" if ph.is_optional else base

    if ph.is_optional:
        if ph.type_name == "int":
            return "Option<i64>"
        if ph.type_name == "float":
            return "Option<f64>"
        if ph.type_name == "bool":
            return "Option<bool>"
        return "Option<&str>"

    if ph.type_name == "int":
        return "i64"
    if ph.type_name == "float":
        return "f64"
    if ph.type_name == "bool":
        return "bool"
    return "&str"


def render_template(tmpl: PlaceholderTemplate) -> str:
    """Render a `PlaceholderTemplate` as a Rust string expression."""
    if not tmpl.has_placeholders:
        return _str(tmpl.source)

    fmt_str = ""
    args: list[str] = []
    for part in tmpl.parts:
        if isinstance(part, PlaceholderSpec):
            fmt_str += "{}"
            args.append(_ident(part.name))
        else:
            fmt_str += part.replace("{", "{{").replace("}", "}}")
    return f"format!({_str(fmt_str)}, {', '.join(args)})"


def render_json_body(tmpl: PlaceholderTemplate) -> str:
    """Render a structured JSON request payload using serde_json::json!."""

    def _emit(v: object) -> str:
        if isinstance(v, PlaceholderSpec):
            return f"({_ident(v.name)})"
        if isinstance(v, PlaceholderTemplate):
            if v.has_placeholders:
                return f"({render_template(v)})"
            return _str(v.source)
        if v is None:
            return "null"
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            return repr(v)
        if isinstance(v, str):
            return _str(v)
        if isinstance(v, dict):
            items = ", ".join(
                f"{_str(str(k))}: {_emit(val)}" for k, val in v.items()
            )
            return "{" + items + "}"
        if isinstance(v, list):
            items = ", ".join(_emit(x) for x in v)
            return "[" + items + "]"
        raise TypeError(f"unsupported JSON body element: {type(v).__name__}")

    ast = parse_json_template(tmpl)
    return f"serde_json::json!({_emit(ast)})"


def _emit_kv_pairs(
    var_name: str,
    pairs: dict[str, PlaceholderTemplate],
    indent: str,
) -> list[str]:
    """Emit code populating a `Vec<(&str, String)>` from placeholder templates."""
    lines: list[str] = []
    for key, tmpl in pairs.items():
        ph = tmpl.single_placeholder()
        if ph is not None:
            var = _ident(ph.name)
            effective_key = (
                f"{key}[]" if ph.is_array and ph.style == "bracket" else key
            )
            key_literal = _str(effective_key)
            if ph.is_array:
                if ph.style in ("csv", "pipe", "space"):
                    sep = _str(
                        {"csv": ",", "pipe": "|", "space": " "}[ph.style]
                    )
                    if ph.is_optional:
                        lines.append(f"{indent}if let Some(items) = {var} {{")
                        lines.append(
                            f"{indent}    let val = items.iter().map(|x| x.to_string()).collect::<Vec<_>>().join({sep});"
                        )
                        lines.append(
                            f"{indent}    {var_name}.push(({key_literal}, val));"
                        )
                        lines.append(f"{indent}}}")
                    else:
                        lines.append(
                            f"{indent}let val = {var}.iter().map(|x| x.to_string()).collect::<Vec<_>>().join({sep});"
                        )
                        lines.append(
                            f"{indent}{var_name}.push(({key_literal}, val));"
                        )
                else:
                    if ph.is_optional:
                        lines.append(f"{indent}if let Some(items) = {var} {{")
                        lines.append(f"{indent}    for item in items {{")
                        lines.append(
                            f"{indent}        {var_name}.push(({key_literal}, item.to_string()));"
                        )
                        lines.append(f"{indent}    }}")
                        lines.append(f"{indent}}}")
                    else:
                        lines.append(f"{indent}for item in {var} {{")
                        lines.append(
                            f"{indent}    {var_name}.push(({key_literal}, item.to_string()));"
                        )
                        lines.append(f"{indent}}}")
            else:
                if ph.is_optional:
                    lines.append(f"{indent}if let Some(val) = {var} {{")
                    lines.append(
                        f"{indent}    {var_name}.push(({key_literal}, val.to_string()));"
                    )
                    lines.append(f"{indent}}}")
                else:
                    lines.append(
                        f"{indent}{var_name}.push(({key_literal}, {var}.to_string()));"
                    )
        elif tmpl.has_placeholders:
            val_expr = render_template(tmpl)
            lines.append(f"{indent}{var_name}.push(({_str(key)}, {val_expr}));")
        else:
            lines.append(
                f"{indent}{var_name}.push(({_str(key)}, {_str(tmpl.source)}.to_string()));"
            )
    return lines


def rust_variant_name(struct_name: str, factory_name: str) -> str:
    """Derive idiomatic enum variant name from factory name."""
    pascal = _pascal(struct_name)
    if factory_name.startswith(pascal):
        tail = factory_name[len(pascal) :]
        if tail:
            return tail
    return factory_name


def render_rust_condition(path: str, val: Any) -> str:
    """Render a condition check against a serde_json::Value."""
    path_lit = _str(path)
    if val is None:
        return f"rt::json_opt(_body_val, {path_lit}).is_none()"
    if isinstance(val, bool):
        b = "true" if val else "false"
        return f"rt::json_opt(_body_val, {path_lit}).and_then(|v| v.as_bool()) == Some({b})"
    if isinstance(val, int):
        return f"rt::json_opt(_body_val, {path_lit}).and_then(|v| v.as_i64()) == Some({val})"
    if isinstance(val, float):
        return f"rt::json_opt(_body_val, {path_lit}).and_then(|v| v.as_f64()) == Some({val})"
    s = _str(str(val))
    return f"rt::json_opt(_body_val, {path_lit}).and_then(|v| v.as_str()) == Some({s})"


def _emit_request_builder(
    spec: RequestHttp,
    indent: str,
    context: str = "",
) -> list[str]:
    """Emit code building a reqwest::RequestBuilder into `let mut req`."""
    url_expr = render_template(spec.url)
    method_upper = spec.method.upper()
    if method_upper in (
        "GET",
        "POST",
        "PUT",
        "DELETE",
        "PATCH",
        "HEAD",
        "OPTIONS",
    ):
        method_expr = f"reqwest::Method::{method_upper}"
    else:
        if context:
            method_expr = (
                f"reqwest::Method::from_bytes({_str(method_upper)}.as_bytes())"
                f".map_err(|e| rt::SscError::new({_str(context)}, e.to_string()))?"
            )
        else:
            method_expr = (
                f"reqwest::Method::from_bytes({_str(method_upper)}.as_bytes())"
                f'.expect("valid HTTP method")'
            )

    lines: list[str] = [
        f"{indent}let mut req = client.request({method_expr}, {url_expr});",
        f"{indent}let _ = &mut req;",
    ]

    # Query params.
    if spec.params:
        lines.append(
            f"{indent}let mut query_pairs: Vec<(&str, String)> = Vec::new();"
        )
        lines.extend(_emit_kv_pairs("query_pairs", spec.params, indent))
        lines.append(f"{indent}req = req.query(&query_pairs);")

    # Headers.
    if spec.headers:
        for k, tmpl in spec.headers.items():
            header_ph = tmpl.single_placeholder()
            if header_ph is not None:
                var = _ident(header_ph.name)
                if header_ph.is_optional:
                    lines.append(f"{indent}if let Some(val) = {var} {{")
                    lines.append(
                        f"{indent}    req = req.header({_str(k)}, val.to_string());"
                    )
                    lines.append(f"{indent}}}")
                else:
                    lines.append(
                        f"{indent}req = req.header({_str(k)}, {var}.to_string());"
                    )
            elif tmpl.has_placeholders:
                lines.append(
                    f"{indent}req = req.header({_str(k)}, {render_template(tmpl)});"
                )
            else:
                lines.append(
                    f"{indent}req = req.header({_str(k)}, {_str(tmpl.source)});"
                )

    # Cookies.
    if spec.cookies:
        lines.append(f"{indent}let mut cookies: Vec<String> = Vec::new();")
        for k, tmpl in spec.cookies.items():
            cookie_ph = tmpl.single_placeholder()
            if cookie_ph is not None:
                var = _ident(cookie_ph.name)
                if cookie_ph.is_optional:
                    lines.append(f"{indent}if let Some(val) = {var} {{")
                    lines.append(
                        f'{indent}    cookies.push(format!("{k}={{val}}"));'
                    )
                    lines.append(f"{indent}}}")
                else:
                    lines.append(
                        f'{indent}cookies.push(format!("{k}={{{var}}}"));'
                    )
            elif tmpl.has_placeholders:
                lines.append(
                    f'{indent}cookies.push(format!("{k}={{}}", {render_template(tmpl)}));'
                )
            else:
                lines.append(
                    f"{indent}cookies.push({_str(f'{k}={tmpl.source}')}.to_string());"
                )
        lines.append(f"{indent}if !cookies.is_empty() {{")
        lines.append(
            f'{indent}    req = req.header("Cookie", cookies.join("; "));'
        )
        lines.append(f"{indent}}}")

    # Body.
    if spec.body_kind == "json" and spec.payload is not None:
        if isinstance(spec.payload, PlaceholderTemplate):
            lines.append(
                f"{indent}req = req.json(&{render_json_body(spec.payload)});"
            )
    elif spec.body_kind == "form" and isinstance(spec.payload, dict):
        lines.append(
            f"{indent}let mut form_pairs: Vec<(&str, String)> = Vec::new();"
        )
        lines.extend(
            _emit_kv_pairs(
                "form_pairs",
                cast(dict[str, PlaceholderTemplate], spec.payload),
                indent,
            )
        )
        lines.append(f"{indent}req = req.form(&form_pairs);")
    elif spec.body_kind == "raw" and spec.payload is not None:
        if isinstance(spec.payload, PlaceholderTemplate):
            lines.append(
                f"{indent}req = req.body({render_template(spec.payload)});"
            )

    return lines


def emit_method_fetch(
    node: MethodFetch,
    ctx: WalkContext,
) -> list[str]:
    """Emit an asynchronous `fetch` associated method for an HTML/raw parser struct."""
    spec: RequestHttp = node.http_request.with_renamed_placeholders(
        to_snake_case
    )
    parent = node.parent
    assert isinstance(parent, StructBase)
    struct_name = _pascal(parent.name)
    method_name = f"fetch_{to_snake_case(node.name)}" if node.name else "fetch"
    context = f"{struct_name}.{method_name}"

    ordered_phs = sorted(spec.placeholders, key=lambda p: p.is_optional)
    params = ["client: &reqwest::Client"]
    for ph in ordered_phs:
        params.append(f"{_ident(ph.name)}: {rust_ph_type(ph)}")

    i1 = "    "
    i2 = "        "
    lines: list[str] = [
        f"{i1}pub async fn {method_name}({', '.join(params)}) -> Result<Self, rt::SscError> {{"
    ]

    lines.extend(_emit_request_builder(spec, i2, context=context))

    # Execute request.
    lines.extend(
        [
            f"{i2}let resp = req.send().await.map_err(|e| rt::SscError::new({_str(context)}, e.to_string()))?;",
            f"{i2}let status = resp.status();",
            f"{i2}let body = resp.text().await.map_err(|e| rt::SscError::new({_str(context)}, e.to_string()))?;",
            f"{i2}if status.as_u16() >= 400 {{",
            f'{i2}    return Err(rt::SscError::new({_str(context)}, format!("HTTP {{}}: {{body}}", status.as_u16())));',
            f"{i2}}}",
        ]
    )

    # Response extraction via JSON path.
    if node.response_path:
        lines.append(
            f"{i2}let body_val = rt::parse_json(&body, {_str(node.response_path)}, {_str(context)})?;"
        )
        if node.response_join:
            lines.extend(
                [
                    f"{i2}let body = match body_val {{",
                    f"{i2}    serde_json::Value::Array(items) => items.iter()",
                    f"{i2}        .map(|item| item.as_str().map(|s| s.to_string()).unwrap_or_else(|| item.to_string()))",
                    f"{i2}        .collect::<Vec<_>>()",
                    f"{i2}        .join({_str(node.response_join)}),",
                    f"{i2}    serde_json::Value::String(s) => s,",
                    f"{i2}    other => other.to_string(),",
                    f"{i2}}};",
                ]
            )
        else:
            lines.extend(
                [
                    f"{i2}let body = match body_val {{",
                    f"{i2}    serde_json::Value::String(s) => s,",
                    f"{i2}    other => other.to_string(),",
                    f"{i2}}};",
                ]
            )

    lines.append(f"{i2}Self::new(body)")
    lines.append(f"{i1}}}")
    lines.append("")
    return lines


def emit_result_variant_def(node: ResultVariantDef) -> list[str]:
    """Emit ResultVariantDef - variant items are synthesized into EndpointError enum."""
    return []


def emit_result_alias_def(
    node: ResultAliasDef,
    struct_name: str,
    emitted_aliases: set[str] | None = None,
) -> list[str]:
    """Emit the type alias for a REST endpoint result."""
    struct_pascal = _pascal(struct_name)
    enum_name = f"{struct_pascal}Error"
    if node.response_schema:
        s_pascal = f"{_pascal(node.response_schema)}Json"
        ok_type = f"Vec<{s_pascal}>" if node.response_is_array else s_pascal
    else:
        ok_type = "()"
    alias_str = f"Result<{ok_type}, {enum_name}>"

    lines: list[str] = []
    qualified = f"{struct_pascal}{node.name}"
    if emitted_aliases is not None:
        if node.name not in emitted_aliases:
            emitted_aliases.add(node.name)
            lines.append(f"pub type {node.name} = {alias_str};")
        if qualified != node.name and qualified not in emitted_aliases:
            emitted_aliases.add(qualified)
            lines.append(f"pub type {qualified} = {alias_str};")
    else:
        lines.append(f"pub type {node.name} = {alias_str};")
    if lines:
        lines.append("")
    return lines


def emit_matcher_list_def(
    node: MatcherListDef,
    variants_by_name: dict[str, ResultVariantDef],
    is_single_rest: bool = True,
) -> list[str]:
    """Emit the EndpointError enum, its trait implementations, and dispatcher function."""
    struct_name = node.struct_name
    struct_pascal = _pascal(struct_name)
    struct_snake = to_snake_case(struct_name)
    enum_name = f"{struct_pascal}Error"

    variant_info: dict[str, tuple[str, int, bool]] = {}
    for entry in node.entries:
        v_name = rust_variant_name(struct_name, entry.factory_name)
        if v_name in variant_info:
            continue
        var_def = variants_by_name.get(entry.factory_name)
        if entry.error_schema:
            s_pascal = f"{_pascal(entry.error_schema)}Json"
            is_array = var_def.schema_is_array if var_def else False
            typ = f"Vec<{s_pascal}>" if is_array else s_pascal
            variant_info[v_name] = (typ, entry.status, False)
        else:
            variant_info[v_name] = ("String", entry.status, True)

    lines = [
        "#[derive(Debug)]",
        f"pub enum {enum_name} {{",
    ]
    for v_name, (typ, _, _) in variant_info.items():
        lines.append(f"    {v_name}({typ}),")
    lines.extend(
        [
            "    Transport(reqwest::Error),",
            "    Unknown(u16, serde_json::Value),",
            "}",
            "",
            f"impl {enum_name} {{",
            "    pub fn status(&self) -> Option<u16> {",
            "        match self {",
        ]
    )
    for v_name, (_, status, _) in variant_info.items():
        lines.append(f"            Self::{v_name}(_) => Some({status}),")
    lines.extend(
        [
            "            Self::Unknown(status, _) => Some(*status),",
            "            Self::Transport(_) => None,",
            "        }",
            "    }",
            "}",
            "",
            f"impl std::fmt::Display for {enum_name} {{",
            "    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {",
            "        match self {",
        ]
    )
    for v_name, (_, status, is_str) in variant_info.items():
        fmt_spec = "{}" if is_str else "{:?}"
        lines.append(
            f'            Self::{v_name}(body) => write!(f, "HTTP {status}: {fmt_spec}", body),'
        )
    lines.extend(
        [
            '            Self::Transport(err) => write!(f, "transport error: {}", err),',
            '            Self::Unknown(status, body) => write!(f, "HTTP {}: {}", status, body),',
            "        }",
            "    }",
            "}",
            "",
            f"impl std::error::Error for {enum_name} {{",
            "    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {",
            "        match self {",
            "            Self::Transport(err) => Some(err),",
            "            _ => None,",
            "        }",
            "    }",
            "}",
            "",
            f"impl From<reqwest::Error> for {enum_name} {{",
            "    fn from(err: reqwest::Error) -> Self {",
            "        Self::Transport(err)",
            "    }",
            "}",
            "",
            f"pub type {struct_pascal}EndpointError = {enum_name};",
        ]
    )
    if is_single_rest:
        lines.append(f"pub type EndpointError = {enum_name};")
    for entry in node.entries:
        v_name = rust_variant_name(struct_name, entry.factory_name)
        if entry.factory_name != v_name:
            typ, _, _ = variant_info[v_name]
            lines.append(f"pub type {entry.factory_name} = {typ};")
    lines.append("")

    # Emit matcher dispatch function.
    lines.extend(
        [
            f"fn match_{struct_snake}_error(",
            "    _status: u16,",
            "    _body_val: &serde_json::Value,",
            "    _body_text: &str,",
            f") -> Option<{enum_name}> {{",
        ]
    )
    for entry in node.entries:
        v_name = rust_variant_name(struct_name, entry.factory_name)
        var_def = variants_by_name.get(entry.factory_name)
        is_array = var_def.schema_is_array if var_def else False
        lines.append(f"    if _status == {entry.status} {{")
        checks: list[str] = []
        for k in entry.required_keys:
            checks.append(f"rt::json_opt(_body_val, {_str(k)}).is_some()")
        for path, val in entry.conditions.items():
            checks.append(render_rust_condition(path, val))

        ind = "        "
        if checks:
            cond_str = " && ".join(checks)
            lines.append(f"        if {cond_str} {{")
            ind = "            "

        if entry.error_schema:
            s_pascal = f"{_pascal(entry.error_schema)}Json"
            if is_array:
                lines.extend(
                    [
                        f"{ind}if let Some(items) = _body_val.as_array() {{",
                        f"{ind}    if let Ok(decoded) = items.iter().cloned().map({s_pascal}::from_value).collect::<Result<Vec<_>, _>>() {{",
                        f"{ind}        return Some({enum_name}::{v_name}(decoded));",
                        f"{ind}    }}",
                        f"{ind}}}",
                        f"{ind}return Some({enum_name}::Unknown(_status, _body_val.clone()));",
                    ]
                )
            else:
                lines.extend(
                    [
                        f"{ind}if let Ok(decoded) = {s_pascal}::from_value(_body_val.clone()) {{",
                        f"{ind}    return Some({enum_name}::{v_name}(decoded));",
                        f"{ind}}}",
                        f"{ind}return Some({enum_name}::Unknown(_status, _body_val.clone()));",
                    ]
                )
        else:
            lines.append(
                f"{ind}return Some({enum_name}::{v_name}(_body_text.to_string()));"
            )

        if checks:
            lines.append("        }")
        lines.append("    }")

    lines.extend(
        [
            "    None",
            "}",
            "",
        ]
    )
    return lines


def emit_method_rest(
    node: MethodRest,
    ctx: WalkContext,
) -> list[str]:
    """Emit an asynchronous REST endpoint associated method returning Result<T, EndpointError>."""
    spec: RequestHttp = node.http_request.with_renamed_placeholders(
        to_snake_case
    )
    parent = node.parent
    assert isinstance(parent, StructBase)
    struct_name = parent.name
    struct_pascal = _pascal(struct_name)
    struct_snake = to_snake_case(struct_name)
    enum_name = f"{struct_pascal}Error"
    method_name = to_snake_case(node.name) if node.name else "fetch"
    context = f"{struct_pascal}.{method_name}"

    ordered_phs = sorted(spec.placeholders, key=lambda p: p.is_optional)
    params = ["client: &reqwest::Client"]
    for ph in ordered_phs:
        params.append(f"{_ident(ph.name)}: {rust_ph_type(ph)}")

    if node.response_schema:
        s_pascal = f"{_pascal(node.response_schema)}Json"
        ok_type = (
            f"Vec<{s_pascal}>"
            if getattr(node, "response_is_array", False)
            else s_pascal
        )
    else:
        ok_type = "()"

    i1 = "    "
    i2 = "        "
    lines: list[str] = []
    if node.doc:
        for doc_line in node.doc.splitlines():
            lines.append(f"{i1}// {doc_line}" if doc_line else f"{i1}//")
    lines.append(
        f"{i1}pub async fn {method_name}({', '.join(params)}) -> Result<{ok_type}, {enum_name}> {{"
    )

    lines.extend(_emit_request_builder(spec, i2))

    lines.extend(
        [
            f"{i2}let resp = req.send().await?;",
            f"{i2}let status = resp.status().as_u16();",
            f"{i2}let body_text = resp.text().await?;",
            f"{i2}let body_val: serde_json::Value = serde_json::from_str(&body_text)"
            f".unwrap_or(serde_json::Value::Null);",
            f"{i2}if let Some(err) = match_{struct_snake}_error(status, &body_val, &body_text) {{",
            f"{i2}    return Err(err);",
            f"{i2}}}",
            f"{i2}if status >= 400 {{",
            f"{i2}    let unknown_val = if body_val.is_null() {{",
            f"{i2}        serde_json::Value::String(body_text)",
            f"{i2}    }} else {{",
            f"{i2}        body_val",
            f"{i2}    }};",
            f"{i2}    return Err({enum_name}::Unknown(status, unknown_val));",
            f"{i2}}}",
        ]
    )

    if not node.response_schema:
        lines.append(f"{i2}Ok(())")
    else:
        s_pascal = f"{_pascal(node.response_schema)}Json"
        is_array = getattr(node, "response_is_array", False)
        if node.response_path:
            lines.append(
                f"{i2}let target_val = rt::json_path(&body_val, {_str(node.response_path)}, {_str(context)})"
                f".map_err(|e| {enum_name}::Unknown(status, serde_json::Value::String(e.to_string())))?;"
            )
        else:
            lines.append(f"{i2}let target_val = &body_val;")

        if is_array:
            lines.extend(
                [
                    f"{i2}let items = target_val.as_array()"
                    f'.ok_or_else(|| {enum_name}::Unknown(status, serde_json::Value::String("expected JSON array".to_string())))?;',
                    f"{i2}let result = items.iter().cloned()"
                    f".map({s_pascal}::from_value)"
                    f".collect::<Result<Vec<_>, _>>()"
                    f".map_err(|e| {enum_name}::Unknown(status, serde_json::Value::String(e.to_string())))?;",
                    f"{i2}Ok(result)",
                ]
            )
        else:
            lines.extend(
                [
                    f"{i2}let result = {s_pascal}::from_value(target_val.clone())"
                    f".map_err(|e| {enum_name}::Unknown(status, serde_json::Value::String(e.to_string())))?;",
                    f"{i2}Ok(result)",
                ]
            )

    lines.append(f"{i1}}}")
    lines.append("")
    return lines


def emit_struct_rest(
    node: StructRest,
    ctx: WalkContext,
    walk_fn: Any,
) -> list[str]:
    """Emit the REST API struct container with associated endpoint methods."""
    name = _pascal(node.name)
    lines: list[str] = []
    if node.doc:
        for doc_line in node.doc.splitlines():
            lines.append(f"// {doc_line}" if doc_line else "//")
    lines.extend(
        [
            f"pub struct {name};",
            "",
            f"pub type {name}Parser = {name};",
            "",
            f"impl {name} {{",
            "    pub fn new() -> Self {",
            "        Self",
            "    }",
            "",
        ]
    )
    for child in node.body:
        lines.extend(walk_fn(child, ctx))
    lines.extend(["}", ""])
    return lines
